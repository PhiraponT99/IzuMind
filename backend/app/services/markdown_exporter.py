from typing import Any


def export_video_to_markdown(video: dict) -> str:
    summary = video.get("summary") if isinstance(video.get("summary"), dict) else {}
    chunks = video.get("chunks") if isinstance(video.get("chunks"), list) else []

    lines = [
        f"# {_text(video.get('title'), 'Untitled Video')}",
        "",
        f"Source: {_text(video.get('source_url'), 'Not provided')}",
        f"Language: {_text(video.get('language'), 'unknown')}",
        f"Created at: {_text(video.get('created_at'), 'unknown')}",
        "",
        "## TL;DR",
        "",
        _text(summary.get("tldr"), "No TL;DR available."),
        "",
        "## Main Ideas",
        "",
        *_format_bullets(summary.get("main_ideas")),
        "",
        "## Key Takeaways",
        "",
        *_format_bullets(summary.get("key_takeaways")),
        "",
        "## Action Items",
        "",
        *_format_bullets(summary.get("action_items")),
        "",
        "## Questions to Think",
        "",
        *_format_bullets(summary.get("questions_to_think")),
        "",
        "## Transcript Chunks",
        "",
        *_format_chunks(chunks),
    ]

    return "\n".join(lines).strip() + "\n"


def _format_bullets(items: Any) -> list[str]:
    if not isinstance(items, list) or not items:
        return ["* None available."]

    return [f"* {_text(item, 'No content')}" for item in items]


def _format_chunks(chunks: list[Any]) -> list[str]:
    if not chunks:
        return ["No transcript chunks available."]

    lines: list[str] = []
    for fallback_index, chunk in enumerate(chunks, start=1):
        if not isinstance(chunk, dict):
            continue

        chunk_index = chunk.get("chunk_index", fallback_index)
        chunk_text = _text(chunk.get("text"), "No chunk text available.")
        lines.extend(
            [
                f"### Chunk {chunk_index}",
                "",
                chunk_text,
                "",
            ]
        )

    return lines or ["No transcript chunks available."]


def _text(value: Any, fallback: str) -> str:
    if value is None:
        return fallback

    normalized = str(value).strip()
    return normalized or fallback
