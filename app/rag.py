import math
import os

from google import genai
from google.genai import types
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import KnowledgeChunk, KnowledgeDocument

EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-2")
EMBEDDING_DIMENSIONS = 768


def split_text(text: str, chunk_size: int = 900, overlap: int = 120) -> list[str]:
    cleaned = " ".join(text.split())
    if not cleaned:
        return []
    chunks = []
    start = 0
    while start < len(cleaned):
        end = min(start + chunk_size, len(cleaned))
        chunks.append(cleaned[start:end])
        if end == len(cleaned):
            break
        start = end - overlap
    return chunks


def embed_text(text: str, api_key: str, task_type: str) -> list[float]:
    client = genai.Client(api_key=api_key)
    if "embedding-2" in EMBEDDING_MODEL:
        instruction = (
            f"task: search result | text: {text}"
            if task_type == "RETRIEVAL_DOCUMENT"
            else f"task: search result | query: {text}"
        )
        response = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=instruction,
            config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMENSIONS),
        )
    else:
        response = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
            config=types.EmbedContentConfig(
                output_dimensionality=EMBEDDING_DIMENSIONS,
                task_type=task_type,
            ),
        )
    if not response.embeddings or not response.embeddings[0].values:
        raise RuntimeError("The embedding service returned no vector.")
    vector = list(response.embeddings[0].values)
    if len(vector) != EMBEDDING_DIMENSIONS:
        raise RuntimeError(f"Expected {EMBEDDING_DIMENSIONS} embedding dimensions.")
    return vector


def cosine_similarity(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


def index_document(
    session: Session,
    *,
    title: str,
    content: str,
    source: str | None,
    api_key: str,
    created_at: str,
) -> KnowledgeDocument:
    chunks = split_text(content)
    if not chunks:
        raise ValueError("Document content must not be empty.")
    vectors = [embed_text(chunk, api_key, "RETRIEVAL_DOCUMENT") for chunk in chunks]
    document = KnowledgeDocument(title=title, source=source, created_at=created_at)
    document.chunks = [
        KnowledgeChunk(chunk_index=index, content=chunk, embedding=vectors[index])
        for index, chunk in enumerate(chunks)
    ]
    session.add(document)
    session.commit()
    session.refresh(document)
    return document


def search_knowledge(
    session: Session, query: str, *, api_key: str, limit: int = 3
) -> list[dict]:
    if not query.strip():
        return []
    if not session.scalar(select(KnowledgeChunk.id).limit(1)):
        return []
    query_vector = embed_text(query, api_key, "RETRIEVAL_QUERY")
    if session.get_bind().dialect.name == "postgresql":
        distance = KnowledgeChunk.embedding.cosine_distance(query_vector)
        rows = session.scalars(
            select(KnowledgeChunk)
            .where(KnowledgeChunk.embedding.is_not(None))
            .order_by(distance)
            .limit(limit)
        ).all()
        scored = [
            {"chunk": row, "score": cosine_similarity(row.embedding, query_vector)}
            for row in rows
        ]
    else:
        rows = session.scalars(
            select(KnowledgeChunk).where(KnowledgeChunk.embedding.is_not(None))
        ).all()
        scored = [
            {"chunk": row, "score": cosine_similarity(row.embedding, query_vector)}
            for row in rows
        ]
        scored.sort(key=lambda item: item["score"], reverse=True)
        scored = scored[:limit]
    results = []
    for item in scored:
        chunk = item["chunk"]
        document = session.get(KnowledgeDocument, chunk.document_id)
        results.append(
            {
                "document_id": chunk.document_id,
                "title": document.title if document else "Unknown document",
                "source": document.source if document else None,
                "content": chunk.content,
                "score": round(item["score"], 4),
            }
        )
    return results
