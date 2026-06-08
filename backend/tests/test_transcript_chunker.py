from app.services.transcript_chunker import chunk_transcript


def test_short_text_returns_one_chunk_with_correct_metadata() -> None:
    text = "Short transcript text."

    chunks = chunk_transcript(text)

    assert len(chunks) == 1
    assert chunks[0].chunk_index == 1
    assert chunks[0].text == text
    assert chunks[0].char_count == len(text)


def test_long_text_returns_multiple_indexed_chunks() -> None:
    sentence = "Deep work needs clear focus and fewer interruptions. "
    text = sentence * 90

    chunks = chunk_transcript(text)

    assert len(chunks) > 1
    assert [chunk.chunk_index for chunk in chunks] == list(range(1, len(chunks) + 1))
    assert all(chunk.char_count == len(chunk.text) for chunk in chunks)
    assert all(chunk.text for chunk in chunks)
