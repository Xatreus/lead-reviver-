from app.rag import cosine_similarity, split_text


def test_split_text_overlaps_and_covers_input():
    text = "a" * 2000
    chunks = split_text(text, chunk_size=500, overlap=50)
    assert len(chunks) > 1
    assert all(0 < len(chunk) <= 500 for chunk in chunks)
    assert "".join([chunks[0], *[chunk[50:] for chunk in chunks[1:]]]) == text


def test_split_text_normalizes_whitespace_and_empty_input():
    assert split_text("  hello\n\nworld  ") == ["hello world"]
    assert split_text("   ") == []


def test_cosine_similarity_ranks_aligned_vectors():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == -1.0
