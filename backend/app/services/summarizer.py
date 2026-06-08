from typing import Any

TLDR_MAX_CHARS = 300
IDEA_MAX_CHARS = 180


def generate_mock_summary(cleaned_transcript: str, chunks: list[Any]) -> dict:
    transcript = cleaned_transcript.strip()
    chunk_texts = [_get_chunk_text(chunk) for chunk in chunks]
    chunk_texts = [text for text in chunk_texts if text]

    return {
        "tldr": _preview(transcript, TLDR_MAX_CHARS),
        "main_ideas": _build_main_ideas(transcript, chunk_texts),
        "key_takeaways": _build_key_takeaways(transcript, chunk_texts),
        "action_items": [
            "Review the generated chunks and refine any transcript sections that need more context.",
            "Use the main ideas as a starting point before replacing this mock summary with an LLM-backed summary.",
        ],
        "questions_to_think": [
            "Which parts of the transcript are most important for the target audience?",
            "What follow-up topics or decisions should be explored after reading this transcript?",
        ],
    }


def _get_chunk_text(chunk: Any) -> str:
    if isinstance(chunk, dict):
        return str(chunk.get("text", "")).strip()

    return str(getattr(chunk, "text", "")).strip()


def _build_main_ideas(transcript: str, chunk_texts: list[str]) -> list[str]:
    if not transcript:
        return []

    ideas = []
    for index, chunk_text in enumerate(chunk_texts[:3], start=1):
        ideas.append(f"Chunk {index}: {_preview(chunk_text, IDEA_MAX_CHARS)}")

    if not ideas:
        ideas.append(_preview(transcript, IDEA_MAX_CHARS))

    return ideas


def _build_key_takeaways(transcript: str, chunk_texts: list[str]) -> list[str]:
    if not transcript:
        return []

    chunk_count = len(chunk_texts) or 1
    return [
        f"The transcript covers a topic across {chunk_count} processed chunk(s).",
        "The cleaned text is ready for manual review or a future LLM summarization step.",
        f"The opening context is: {_preview(transcript, 140)}",
    ]


def _preview(text: str, max_chars: int) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_chars:
        return normalized

    return f"{normalized[: max_chars - 3].rstrip()}..."
