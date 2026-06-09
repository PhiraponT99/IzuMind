import re
from dataclasses import dataclass
from typing import Any

TLDR_MAX_CHARS = 360
IDEA_MAX_CHARS = 180
TAKEAWAY_MAX_CHARS = 150
SNIPPET_MAX_CHARS = 220

SENTENCE_END_PATTERN = re.compile(r"(?<=[.!?。！？ฯ])\s+")
SPACE_PATTERN = re.compile(r"\s+")

THAI_USEFUL_KEYWORDS = (
    "คือ",
    "ปัญหา",
    "ทำให้",
    "ควร",
    "ถ้าอยาก",
    "แนวทาง",
    "ช่วย",
    "สมาธิ",
    "notification",
    "มือถือ",
    "deep work",
    "dopamine",
)
THAI_WEAK_INTRO_PATTERNS = (
    "วันนี้เราจะพูดถึง",
    "เราจะพูดถึง",
    "ในวิดีโอนี้",
)


@dataclass(frozen=True)
class SummaryGenerationResult:
    summary: dict
    summary_provider: str
    summary_fallback_used: bool


def generate_summary(
    cleaned_transcript: str,
    chunks: list[Any],
    language: str = "thai",
) -> dict:
    return generate_rule_based_summary(cleaned_transcript, chunks, language)


def generate_summary_with_metadata(
    cleaned_transcript: str,
    chunks: list[Any],
    language: str = "thai",
) -> SummaryGenerationResult:
    return SummaryGenerationResult(
        summary=generate_rule_based_summary(cleaned_transcript, chunks, language),
        summary_provider="rule_based",
        summary_fallback_used=False,
    )


def generate_rule_based_summary(
    cleaned_transcript: str,
    chunks: list[Any],
    language: str = "thai",
) -> dict:
    transcript = _normalize_spaces(cleaned_transcript)
    chunk_texts = [_get_chunk_text(chunk) for chunk in chunks]
    chunk_texts = [text for text in chunk_texts if text]
    main_sentences = extract_main_sentences(
        transcript,
        chunk_texts,
        max_items=5,
        language=language,
    )

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


def rank_sentences(sentences: list[str], language: str) -> list[str]:
    return sorted(
        sentences,
        key=lambda sentence: _rank_score(sentence, language),
        reverse=True,
    )


def extract_main_sentences(
    text: str,
    chunks: list[str] | None = None,
    max_items: int = 3,
    language: str = "thai",
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

    ranked = rank_sentences(unique_candidates, language)
    selected = [
        sentence
        for sentence in ranked
        if not (_is_thai(language) and _is_weak_thai_intro(sentence))
    ]
    selected = selected[:max_items]

    if not selected:
        selected = ranked[:max_items]

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

    return {
        "tldr": _build_thai_tldr(main_sentences, transcript),
        "main_ideas": _build_thai_main_ideas(main_sentences),
        "key_takeaways": _build_thai_takeaways(transcript, main_sentences),
        "action_items": _build_thai_action_items(transcript, main_sentences),
        "questions_to_think": _build_thai_questions(transcript),
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

    return {
        "tldr": _build_english_tldr(main_sentences, transcript),
        "main_ideas": _build_english_main_ideas(main_sentences),
        "key_takeaways": _build_english_takeaways(main_sentences),
        "action_items": _build_english_action_items(main_sentences),
        "questions_to_think": _build_english_questions(main_sentences),
    }


def _build_thai_tldr(main_sentences: list[str], transcript: str) -> str:
    clauses = []
    if _has_any(transcript, ("มือถือ", "notification", "social media")):
        clauses.append("ปัญหาที่มือถือ notification และ social media ทำให้หลุดโฟกัสบ่อย")
    if _has_any(transcript, ("deep work", "สมาธิลึก")):
        clauses.append("deep work คือการทำงานแบบมีสมาธิลึก")
    if _has_any(transcript, ("ปิด notification", "วางมือถือ", "กำหนดช่วงเวลา")):
        clauses.append("ควรจัดสภาพแวดล้อมและช่วงเวลาทำงานให้ถูกรบกวนน้อยลง")

    if clauses:
        if len(clauses) == 1:
            return truncate_text(f"วิดีโอนี้พูดถึง{clauses[0]}", TLDR_MAX_CHARS)

        return truncate_text(
            f"วิดีโอนี้พูดถึง{clauses[0]} พร้อมอธิบายว่า {_join_thai_clauses(clauses[1:])}",
            TLDR_MAX_CHARS,
        )

    selected = main_sentences[:2] or [transcript]
    if len(selected) == 1:
        return truncate_text(selected[0], TLDR_MAX_CHARS)

    return truncate_text(f"{selected[0]} พร้อมเชื่อมโยงกับ {selected[1]}", TLDR_MAX_CHARS)


def _build_english_tldr(main_sentences: list[str], transcript: str) -> str:
    selected = main_sentences[:2] or [transcript]
    if len(selected) == 1:
        return truncate_text(f"This video discusses {selected[0]}", TLDR_MAX_CHARS)

    return truncate_text(
        f"This video discusses {selected[0]} It also highlights {selected[1]}",
        TLDR_MAX_CHARS,
    )


def _build_thai_main_ideas(main_sentences: list[str]) -> list[str]:
    return [truncate_text(sentence, IDEA_MAX_CHARS) for sentence in main_sentences[:5]]


def _build_english_main_ideas(main_sentences: list[str]) -> list[str]:
    prefixes = ["Discusses", "Explains", "Highlights", "Emphasizes", "Raises the point that"]
    return [
        f"{prefixes[index % len(prefixes)]} {truncate_text(sentence, IDEA_MAX_CHARS)}"
        for index, sentence in enumerate(main_sentences[:5])
    ]


def _build_thai_takeaways(transcript: str, main_sentences: list[str]) -> list[str]:
    takeaways = []
    if _has_any(transcript, ("มือถือ", "notification", "social media")):
        takeaways.append("มือถือ notification และ social media เป็นตัวรบกวนสำคัญที่ทำให้หลุดโฟกัส")
    if _has_any(transcript, ("dopamine", "สลับความสนใจ")):
        takeaways.append("การเช็กมือถือบ่อยทำให้สมองติดการสลับความสนใจ")
    if _has_any(transcript, ("ปิด notification", "วางมือถือ", "กำหนดช่วงเวลา")):
        takeaways.append("การปิด notification วางมือถือให้ไกล และกำหนดเวลาทำงานช่วยเริ่ม deep work ได้ง่ายขึ้น")
    if _has_any(transcript, ("deep work", "สมาธิลึก")):
        takeaways.append("Deep work ต้องอาศัยสมาธิลึกและสภาพแวดล้อมที่ถูกรบกวนน้อย")

    for sentence in main_sentences:
        if len(takeaways) >= 3:
            break
        takeaways.append(truncate_text(sentence, TAKEAWAY_MAX_CHARS))

    return _dedupe(takeaways)[:3]


def _build_english_takeaways(main_sentences: list[str]) -> list[str]:
    selected = _pad_items(main_sentences, 3, "the main transcript idea")
    return [
        f"Pay attention to: {truncate_text(selected[0], TAKEAWAY_MAX_CHARS)}",
        f"A key issue is: {truncate_text(selected[1], TAKEAWAY_MAX_CHARS)}",
        f"A practical direction is: {truncate_text(selected[2], TAKEAWAY_MAX_CHARS)}",
    ]


def _build_thai_action_items(transcript: str, main_sentences: list[str]) -> list[str]:
    actions = []
    if _has_any(transcript, ("ปิด notification", "notification")):
        actions.append("ปิด notification ระหว่างช่วงทำงานลึก")
    if _has_any(transcript, ("วางมือถือ", "มือถือ")):
        actions.append("วางมือถือให้ไกลจากโต๊ะทำงาน")
    if _has_any(transcript, ("กำหนดช่วงเวลา", "ช่วงเวลาทำงาน")):
        actions.append("กำหนดช่วงเวลาทำงานที่ชัดเจน")

    if actions:
        return actions[:3]

    selected = _pad_items(main_sentences, 2, "ประเด็นสำคัญจาก transcript")
    return [
        f"เลือกหนึ่งประเด็นจากเรื่อง {truncate_text(selected[0], TAKEAWAY_MAX_CHARS)} ไปทดลองใช้",
        f"สรุปสิ่งที่ควรปรับจากเรื่อง {truncate_text(selected[1], TAKEAWAY_MAX_CHARS)}",
    ]


def _build_english_action_items(main_sentences: list[str]) -> list[str]:
    selected = _pad_items(main_sentences, 3, "the main transcript idea")
    return [
        f"Review the point about {truncate_text(selected[0], TAKEAWAY_MAX_CHARS)}",
        f"Try applying the idea of {truncate_text(selected[1], TAKEAWAY_MAX_CHARS)} to real work.",
        f"Write one follow-up question about {truncate_text(selected[2], TAKEAWAY_MAX_CHARS)}",
    ]


def _build_thai_questions(transcript: str) -> list[str]:
    questions = []
    if _has_any(transcript, ("มือถือ", "notification", "social media")):
        questions.append("อะไรคือสิ่งที่รบกวนสมาธิเรามากที่สุดระหว่างทำงาน?")
    if _has_any(transcript, ("deep work", "สมาธิลึก", "ช่วงเวลาทำงาน")):
        questions.append("เราจะออกแบบช่วง deep work ในแต่ละวันได้อย่างไร?")
    if _has_any(transcript, ("notification", "แอป", "social media")):
        questions.append("มี notification หรือแอปไหนที่ควรลดการใช้งานก่อน?")

    if questions:
        return questions[:3]

    return [
        "ประเด็นสำคัญจากวิดีโอนี้เกี่ยวข้องกับงานหรือชีวิตประจำวันของเราอย่างไร?",
        "มีจุดไหนที่ควรศึกษาเพิ่มเติมจากวิดีโอนี้?",
    ]


def _build_english_questions(main_sentences: list[str]) -> list[str]:
    selected = _pad_items(main_sentences, 2, "the main transcript idea")
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


def _rank_score(sentence: str, language: str) -> int:
    score = min(len(sentence), 260)
    lowered = sentence.lower()

    if _is_thai(language):
        for keyword in THAI_USEFUL_KEYWORDS:
            if keyword in lowered:
                score += 80
        if _is_weak_thai_intro(sentence):
            score -= 300
        return score

    for marker in ("problem", "should", "important", "because", "focus", "helps", "means"):
        if marker in lowered:
            score += 80
    return score


def _is_weak_thai_intro(sentence: str) -> bool:
    normalized = _normalize_spaces(sentence)
    return any(normalized.startswith(pattern) for pattern in THAI_WEAK_INTRO_PATTERNS)


def _has_any(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    deduped = []
    for item in items:
        normalized = _normalize_spaces(item)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _join_thai_clauses(clauses: list[str]) -> str:
    if len(clauses) <= 1:
        return "".join(clauses)

    return " และ".join(clauses)


def _pad_items(items: list[str], count: int, fallback: str) -> list[str]:
    if not items:
        return [fallback] * count

    padded = list(items)
    while len(padded) < count:
        padded.append(padded[-1])

    return padded[:count]


def _normalize_spaces(text: str) -> str:
    return SPACE_PATTERN.sub(" ", text).strip()


def _is_thai(language: str) -> bool:
    return language.lower().strip() == "thai"
