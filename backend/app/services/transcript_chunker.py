import re

from app.schemas import TranscriptChunk

MIN_CHUNK_SIZE = 1200
MAX_CHUNK_SIZE = 1800
TARGET_CHUNK_SIZE = 1500

SENTENCE_BOUNDARY_PATTERN = re.compile(r"(?<=[.!?。！？])\s+|\n+")


def chunk_transcript(text: str) -> list[TranscriptChunk]:
    normalized_text = text.strip()
    if not normalized_text:
        return []

    sentences = _split_sentences(normalized_text)
    chunks = _build_chunks(sentences)

    return [
        TranscriptChunk(
            chunk_index=index,
            text=chunk,
            char_count=len(chunk),
        )
        for index, chunk in enumerate(chunks, start=1)
    ]


def _split_sentences(text: str) -> list[str]:
    parts = [part.strip() for part in SENTENCE_BOUNDARY_PATTERN.split(text)]
    sentences = [part for part in parts if part]

    if len(sentences) == 1 and len(sentences[0]) > MAX_CHUNK_SIZE:
        return _split_long_text(sentences[0])

    return sentences


def _build_chunks(sentences: list[str]) -> list[str]:
    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        if len(sentence) > MAX_CHUNK_SIZE:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_split_long_text(sentence))
            continue

        candidate = sentence if not current else f"{current} {sentence}"
        if len(candidate) <= MAX_CHUNK_SIZE:
            current = candidate
            continue

        if current:
            chunks.append(current)
        current = sentence

    if current:
        chunks.append(current)

    return _merge_small_chunks(chunks)


def _split_long_text(text: str) -> list[str]:
    words = text.split(" ")
    if len(words) == 1:
        return [
            text[start : start + TARGET_CHUNK_SIZE].strip()
            for start in range(0, len(text), TARGET_CHUNK_SIZE)
            if text[start : start + TARGET_CHUNK_SIZE].strip()
        ]

    chunks: list[str] = []
    current = ""

    for word in words:
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= TARGET_CHUNK_SIZE:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = word

    if current:
        chunks.append(current)

    return chunks


def _merge_small_chunks(chunks: list[str]) -> list[str]:
    if len(chunks) < 2:
        return chunks

    merged: list[str] = []
    index = 0

    while index < len(chunks):
        current = chunks[index]
        if (
            len(current) < MIN_CHUNK_SIZE
            and index + 1 < len(chunks)
            and len(f"{current} {chunks[index + 1]}") <= MAX_CHUNK_SIZE
        ):
            merged.append(f"{current} {chunks[index + 1]}")
            index += 2
        else:
            merged.append(current)
            index += 1

    return merged
