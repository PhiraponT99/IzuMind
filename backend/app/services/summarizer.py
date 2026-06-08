import re
from typing import Any

TLDR_MAX_CHARS = 360
IDEA_MAX_CHARS = 180
TAKEAWAY_MAX_CHARS = 150
SNIPPET_MAX_CHARS = 220

SENTENCE_END_PATTERN = re.compile(r"(?<=[.!?。！？ฯ])\s+")
SPACE_PATTERN = re.compile(r"\s+")


def generate_summary(
    cleaned_transcript: str,
    chunks: list[Any],
    language: str = "thai",
) -> dict:
    transcript = _normalize_spaces(cleaned_transcript)
    chunk_texts = [_get_chunk_text(chunk) for chunk in chunks]
    chunk_texts = [text for text in chunk_texts if text]
    main_sentences = extract_main_sentences(transcript, chunk_texts, max_items=5)

    if _is_thai(language):
        return _generate_thai_summary(transcript, main_sentences)

    return _generate_english_summary(transcript, main_sentences)


def generate_mock_summary(cleaned_transcript: str, chunks: list[Any]) -> dict:
    return generate_summary(cleaned_transcript, chunks, language="english")


def split_sentences(text: str) -> list[str]:
    normalized = _normalize_spaces(text)
    if not normalized:
        return []

    parts = [part.strip() for part in SENTENCE_END_PATTERN.split(normalized)]
    sentences = [part for part in parts if part]

    if len(sentences) > 1:
        return sentences

    return _split_long_text(normalized, SNIPPET_MAX_CHARS)


def truncate_text(text: str, max_chars: int) -> str:
    normalized = _normalize_spaces(text)
    if len(normalized) <= max_chars:
        return normalized

    return f"{normalized[: max_chars - 3].rstrip()}..."


def extract_main_sentences(
    text: str,
    chunks: list[str] | None = None,
    max_items: int = 3,
) -> list[str]:
    candidates = split_sentences(text)

    if len(candidates) < max_items and chunks:
        for chunk_text in chunks:
            candidates.extend(split_sentences(chunk_text))

    seen = set()
    unique_candidates = []
    for candidate in candidates:
        normalized = _normalize_spaces(candidate)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_candidates.append(normalized)

    unique_candidates.sort(key=_sentence_score, reverse=True)
    selected = unique_candidates[:max_items]

    if not selected and text:
        selected = [truncate_text(text, SNIPPET_MAX_CHARS)]

    return selected


def _generate_thai_summary(transcript: str, main_sentences: list[str]) -> dict:
    if not transcript:
        return {
            "tldr": "ยังไม่มีเนื้อหาสำหรับสรุป",
            "main_ideas": [],
            "key_takeaways": [],
            "action_items": [],
            "questions_to_think": [],
        }

    main_ideas = _build_thai_main_ideas(main_sentences)
    takeaways = _build_thai_takeaways(main_sentences)

    return {
        "tldr": _build_thai_tldr(main_sentences, transcript),
        "main_ideas": main_ideas,
        "key_takeaways": takeaways,
        "action_items": _build_thai_action_items(main_sentences),
        "questions_to_think": _build_thai_questions(main_sentences),
    }


def _generate_english_summary(transcript: str, main_sentences: list[str]) -> dict:
    if not transcript:
        return {
            "tldr": "No transcript content is available to summarize.",
            "main_ideas": [],
            "key_takeaways": [],
            "action_items": [],
            "questions_to_think": [],
        }

    main_ideas = _build_english_main_ideas(main_sentences)
    takeaways = _build_english_takeaways(main_sentences)

    return {
        "tldr": _build_english_tldr(main_sentences, transcript),
        "main_ideas": main_ideas,
        "key_takeaways": takeaways,
        "action_items": _build_english_action_items(main_sentences),
        "questions_to_think": _build_english_questions(main_sentences),
    }


def _build_thai_tldr(main_sentences: list[str], transcript: str) -> str:
    selected = main_sentences[:2] or [transcript]
    if len(selected) == 1:
        return truncate_text(f"วิดีโอนี้พูดถึง {selected[0]}", TLDR_MAX_CHARS)

    return truncate_text(
        f"วิดีโอนี้พูดถึง {selected[0]} ประเด็นสำคัญอีกส่วนคือ {selected[1]}",
        TLDR_MAX_CHARS,
    )


def _build_english_tldr(main_sentences: list[str], transcript: str) -> str:
    selected = main_sentences[:2] or [transcript]
    if len(selected) == 1:
        return truncate_text(f"This video discusses {selected[0]}", TLDR_MAX_CHARS)

    return truncate_text(
        f"This video discusses {selected[0]} It also highlights {selected[1]}",
        TLDR_MAX_CHARS,
    )


def _build_thai_main_ideas(main_sentences: list[str]) -> list[str]:
    prefixes = ["พูดถึง", "อธิบายว่า", "ชี้ให้เห็นว่า", "เน้นว่า", "ยกประเด็นว่า"]
    return [
        f"{prefixes[index % len(prefixes)]} {truncate_text(sentence, IDEA_MAX_CHARS)}"
        for index, sentence in enumerate(main_sentences[:5])
    ]


def _build_english_main_ideas(main_sentences: list[str]) -> list[str]:
    prefixes = ["Discusses", "Explains", "Highlights", "Emphasizes", "Raises the point that"]
    return [
        f"{prefixes[index % len(prefixes)]} {truncate_text(sentence, IDEA_MAX_CHARS)}"
        for index, sentence in enumerate(main_sentences[:5])
    ]


def _build_thai_takeaways(main_sentences: list[str]) -> list[str]:
    selected = _pad_items(main_sentences, 3)
    return [
        f"ควรให้ความสำคัญกับ {truncate_text(selected[0], TAKEAWAY_MAX_CHARS)}",
        f"ปัญหาสำคัญคือ {truncate_text(selected[1], TAKEAWAY_MAX_CHARS)}",
        f"แนวทางที่นำไปใช้ได้คือ {truncate_text(selected[2], TAKEAWAY_MAX_CHARS)}",
    ]


def _build_english_takeaways(main_sentences: list[str]) -> list[str]:
    selected = _pad_items(main_sentences, 3)
    return [
        f"Pay attention to: {truncate_text(selected[0], TAKEAWAY_MAX_CHARS)}",
        f"A key issue is: {truncate_text(selected[1], TAKEAWAY_MAX_CHARS)}",
        f"A practical direction is: {truncate_text(selected[2], TAKEAWAY_MAX_CHARS)}",
    ]


def _build_thai_action_items(main_sentences: list[str]) -> list[str]:
    selected = _pad_items(main_sentences, 3)
    return [
        f"ทบทวนประเด็นเรื่อง {truncate_text(selected[0], TAKEAWAY_MAX_CHARS)}",
        f"ลองนำแนวคิดเรื่อง {truncate_text(selected[1], TAKEAWAY_MAX_CHARS)} ไปใช้กับงานจริง",
        f"จดคำถามต่อยอดจากประเด็น {truncate_text(selected[2], TAKEAWAY_MAX_CHARS)}",
    ]


def _build_english_action_items(main_sentences: list[str]) -> list[str]:
    selected = _pad_items(main_sentences, 3)
    return [
        f"Review the point about {truncate_text(selected[0], TAKEAWAY_MAX_CHARS)}",
        f"Try applying the idea of {truncate_text(selected[1], TAKEAWAY_MAX_CHARS)} to real work.",
        f"Write one follow-up question about {truncate_text(selected[2], TAKEAWAY_MAX_CHARS)}",
    ]


def _build_thai_questions(main_sentences: list[str]) -> list[str]:
    selected = _pad_items(main_sentences, 2)
    return [
        f"ประเด็นเรื่อง {truncate_text(selected[0], TAKEAWAY_MAX_CHARS)} เกี่ยวข้องกับงานหรือชีวิตประจำวันของเราอย่างไร?",
        f"มีจุดไหนจากเรื่อง {truncate_text(selected[1], TAKEAWAY_MAX_CHARS)} ที่ควรศึกษาเพิ่มเติม?",
    ]


def _build_english_questions(main_sentences: list[str]) -> list[str]:
    selected = _pad_items(main_sentences, 2)
    return [
        f"How does the point about {truncate_text(selected[0], TAKEAWAY_MAX_CHARS)} connect to daily work or study?",
        f"What should be explored further from {truncate_text(selected[1], TAKEAWAY_MAX_CHARS)}?",
    ]


def _get_chunk_text(chunk: Any) -> str:
    if isinstance(chunk, dict):
        return _normalize_spaces(str(chunk.get("text", "")))

    return _normalize_spaces(str(getattr(chunk, "text", "")))


def _split_long_text(text: str, max_chars: int) -> list[str]:
    words = text.split(" ")
    if len(words) == 1:
        return [
            text[start : start + max_chars].strip()
            for start in range(0, len(text), max_chars)
            if text[start : start + max_chars].strip()
        ]

    snippets = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
            continue

        if current:
            snippets.append(current)
        current = word

    if current:
        snippets.append(current)

    return snippets


def _sentence_score(sentence: str) -> int:
    score = min(len(sentence), 260)
    lowered = sentence.lower()
    for marker in (
        "คือ",
        "ปัญหา",
        "ควร",
        "สำคัญ",
        "เพราะ",
        "deep work",
        "problem",
        "should",
        "important",
        "because",
        "focus",
    ):
        if marker in lowered:
            score += 80
    return score


def _pad_items(items: list[str], count: int) -> list[str]:
    if not items:
        return ["เนื้อหาหลักของ transcript"] * count

    padded = list(items)
    while len(padded) < count:
        padded.append(padded[-1])

    return padded[:count]


def _normalize_spaces(text: str) -> str:
    return SPACE_PATTERN.sub(" ", text).strip()


def _is_thai(language: str) -> bool:
    return language.lower().strip() == "thai"
