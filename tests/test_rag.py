from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.rag import cosine_similarity, index_document, search_knowledge, split_text


def test_split_text_overlaps_and_covers_input():
    text = "a" * 2000
    chunks = split_text(text, chunk_size=500, overlap=50)
    assert len(chunks) > 1
    assert all(0 < len(chunk) <= 500 for chunk in chunks)
    assert "".join([chunks[0], *[chunk[50:] for chunk in chunks[1:]]]) == text


def test_split_text_normalizes_whitespace_and_empty_input():
    assert split_text("  hello\\n\\nworld  ") == ["hello world"]
    assert split_text("   ") == []


def test_cosine_similarity_ranks_aligned_vectors():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == -1.0


def test_sqlite_rag_indexes_and_retrieves_without_external_api(tmp_path, monkeypatch):
    import app.rag as rag

    engine = create_engine(f"sqlite:///{tmp_path / 'rag.db'}")
    Base.metadata.create_all(engine)

    def fake_embedding(text, api_key, task_type):
        vector = [0.0] * rag.EMBEDDING_DIMENSIONS
        vector[0] = 1.0 if "sales" in text.lower() else 0.5
        vector[1] = 1.0 if task_type == "RETRIEVAL_QUERY" else 0.0
        return vector

    monkeypatch.setattr(rag, "embed_text", fake_embedding)
    with Session(engine) as session:
        document = index_document(
            session,
            title="Approved sales playbook",
            content="Sales follow-up should be respectful and factual.",
            source="internal/sales-playbook",
            api_key="test-key",
            created_at="2026-10-31T00:00:00+00:00",
        )
        assert document.id is not None

        results = search_knowledge(
            session, "sales follow-up", api_key="test-key", limit=3
        )

    assert len(results) == 1
    assert results[0]["title"] == "Approved sales playbook"
    assert results[0]["source"] == "internal/sales-playbook"
    assert "respectful and factual" in results[0]["content"]
    assert results[0]["score"] > 0
