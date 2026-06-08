import re
from typing import Any

MAX_RELATED_CHUNKS = 3
ANSWER_SNIPPET_CHARS = 260

KEYWORD_PATTERN = re.compile(r"[0-9A-Za-z\u0E00-\u0E7F]+")
ENGLISH_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "what",
    "when",
    "where",
    "why",
    "with",
}


def answer_question(question: str, chunks: list[dict]) -> dict:
    normalized_question = _normalize_text(question)
    keywords = _extract_keywords(normalized_question)

    if not chunks:
        return {
            "answer": "No chunks are available for this video yet, so this keyword-based Q&A engine cannot answer from source text.",
            "related_chunks": [],
        }

    if not keywords:
        return {
            "answer": "Please ask a more specific question. This simple keyword-based Q&A engine needs searchable words to match against transcript chunks.",
            "related_chunks": [],
        }

    scored_chunks = []
    for chunk in chunks:
        text = str(chunk.get("text", ""))
        normalized_chunk = _normalize_text(text)
        score = _score_chunk(normalized_chunk, keywords)
        if score > 0:
            scored_chunks.append(
                {
                    "chunk_index": int(chunk.get("chunk_index", 0)),
                    "text": text,
                    "char_count": int(chunk.get("char_count", len(text))),
                    "score": score,
                }
            )

    scored_chunks.sort(key=lambda item: (-item["score"], item["chunk_index"]))
    related_chunks = scored_chunks[:MAX_RELATED_CHUNKS]

    if not related_chunks:
        return {
            "answer": "I could not find a reliable keyword match in the saved transcript chunks. This answer is limited to deterministic keyword retrieval and will not invent details outside the transcript.",
            "related_chunks": [],
        }

    snippets = [
        f"Chunk {chunk['chunk_index']}: {_preview(chunk['text'], ANSWER_SNIPPET_CHARS)}"
        for chunk in related_chunks
    ]
    answer = (
        "This is a simple keyword-based answer from the saved chunks. "
        "The most related transcript sections say: "
        + " ".join(snippets)
    )

    return {
        "answer": answer,
        "related_chunks": related_chunks,
    }


def _normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def _extract_keywords(text: str) -> list[str]:
    keywords = []
    for keyword in KEYWORD_PATTERN.findall(text):
        if keyword in ENGLISH_STOPWORDS:
            continue
        if len(keyword) < 2:
            continue
        keywords.append(keyword)

    return list(dict.fromkeys(keywords))


def _score_chunk(normalized_chunk: str, keywords: list[str]) -> int:
    score = 0
    for keyword in keywords:
        if keyword in normalized_chunk:
            score += 1
    return score


def _preview(text: Any, max_chars: int) -> str:
    normalized = " ".join(str(text).split())
    if len(normalized) <= max_chars:
        return normalized

    return f"{normalized[: max_chars - 3].rstrip()}..."
