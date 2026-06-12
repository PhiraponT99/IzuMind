"""
Unit tests for app.services.transcript_quality.analyze_transcript_quality.

All tests are deterministic — no network, STT, YouTube, or LLM calls.
"""
from __future__ import annotations

import pytest

from app.services.transcript_quality import analyze_transcript_quality


# ---------------------------------------------------------------------------
# Shared sample transcripts
# ---------------------------------------------------------------------------

THAI_HIGH_QUALITY = (
    "วันนี้เราจะพูดถึง deep work "
    "deep work คือการทำงานแบบมีสมาธิลึกและไม่ถูกรบกวน "
    "ปัญหาของยุคนี้คือมือถือ notification และ social media ทำให้เราหลุดโฟกัสบ่อย "
    "เมื่อเราเช็กมือถือ สมองจะได้รับ dopamine สั้น ๆ ทำให้เราติดการสลับความสนใจ "
    "ถ้าอยากทำงานลึก เราควรปิด notification วางมือถือให้ไกล "
    "และกำหนดช่วงเวลาทำงานที่ชัดเจน"
)

ENGLISH_HIGH_QUALITY = (
    "Today we will talk about deep work. "
    "Deep work is the ability to focus without distraction on cognitively demanding tasks. "
    "In the modern world, social media and smartphones interrupt our concentration frequently. "
    "When we check our phone, our brain gets a short dopamine hit that reinforces distraction. "
    "To do deep work, you should turn off notifications and set dedicated work periods."
)

SHORT_TRANSCRIPT = "สวัสดี"  # only 7 chars — below threshold

REPLACEMENT_CHAR_TRANSCRIPT = (
    "วันนี้เราจะพูดถึง deep work \ufffd\ufffd "
    "deep work คือการทำงานแบบมีสมาธิลึกและไม่ถูกรบกวน "
    "ปัญหาของยุคนี้คือมือถือ notification และ social media ทำให้เราหลุดโฟกัสบ่อย "
)

# >35 % Latin chars in a Thai-language transcript
HEAVY_LATIN_IN_THAI = (
    "iPhone 15 Pro Max Samsung Galaxy S24 Ultra Google Pixel 8a OnePlus 12 "
    "วันนี้เราจะพูดถึง smartphone review "
    "Qualcomm Snapdragon 8 Gen 3 Apple A17 Pro MediaTek Dimensity 9300 benchmark test "
    "ความเร็ว performance gaming battery life "
)

REPEATED_PHRASE_TRANSCRIPT = (
    "deep work is focused work " * 8  # same 3-word window repeated >4 times
)


# ---------------------------------------------------------------------------
# 1. High-quality Thai transcript
# ---------------------------------------------------------------------------


def test_high_quality_thai_transcript() -> None:
    result = analyze_transcript_quality(THAI_HIGH_QUALITY, language="thai")
    assert result["transcript_quality"] == "high"
    assert isinstance(result["warnings"], list)
    assert isinstance(result["quality_signals"], dict)
    # No warnings expected for a normal Thai transcript without STT source
    assert not result["warnings"]


# ---------------------------------------------------------------------------
# 2. High-quality English transcript
# ---------------------------------------------------------------------------


def test_high_quality_english_transcript() -> None:
    result = analyze_transcript_quality(ENGLISH_HIGH_QUALITY, language="english")
    assert result["transcript_quality"] == "high"
    assert not result["warnings"]


# ---------------------------------------------------------------------------
# 3. local_stt source always adds a warning
# ---------------------------------------------------------------------------


def test_local_stt_source_adds_warning() -> None:
    result = analyze_transcript_quality(
        THAI_HIGH_QUALITY, transcript_source="local_stt", language="thai"
    )
    assert len(result["warnings"]) >= 1
    warning_text = " ".join(result["warnings"])
    assert "local STT" in warning_text or "STT" in warning_text


# ---------------------------------------------------------------------------
# 4. youtube_caption source on clean transcript — no STT warning
# ---------------------------------------------------------------------------


def test_youtube_caption_source_no_stt_warning() -> None:
    result = analyze_transcript_quality(
        THAI_HIGH_QUALITY, transcript_source="youtube_caption", language="thai"
    )
    stt_warnings = [w for w in result["warnings"] if "STT" in w]
    assert not stt_warnings


# ---------------------------------------------------------------------------
# 5. Short transcript → low quality
# ---------------------------------------------------------------------------


def test_short_transcript_is_low_quality() -> None:
    result = analyze_transcript_quality(SHORT_TRANSCRIPT, language="thai")
    assert result["transcript_quality"] == "low"
    assert any("short" in w.lower() or "too short" in w.lower() for w in result["warnings"])


# ---------------------------------------------------------------------------
# 6. Empty transcript → low quality
# ---------------------------------------------------------------------------


def test_empty_transcript_is_low_quality() -> None:
    result = analyze_transcript_quality("", language="thai")
    assert result["transcript_quality"] == "low"


def test_whitespace_only_transcript_is_low_quality() -> None:
    result = analyze_transcript_quality("   \n  \t  ", language="thai")
    assert result["transcript_quality"] == "low"


# ---------------------------------------------------------------------------
# 7. Replacement characters → low quality + warning
# ---------------------------------------------------------------------------


def test_replacement_characters_degrade_quality() -> None:
    result = analyze_transcript_quality(REPLACEMENT_CHAR_TRANSCRIPT, language="thai")
    # Should flag replacement chars
    assert result["transcript_quality"] in ("low", "medium")
    warning_text = " ".join(result["warnings"])
    assert "replacement" in warning_text.lower() or "\\ufffd" in warning_text or "encoding" in warning_text.lower()


def test_replacement_character_count_in_signals() -> None:
    result = analyze_transcript_quality(REPLACEMENT_CHAR_TRANSCRIPT, language="thai")
    assert result["quality_signals"]["replacement_character_count"] >= 2


# ---------------------------------------------------------------------------
# 8. High Latin ratio in a Thai transcript → medium or low + warning
# ---------------------------------------------------------------------------


def test_heavy_latin_in_thai_transcript_degrades_quality() -> None:
    result = analyze_transcript_quality(HEAVY_LATIN_IN_THAI, language="thai")
    assert result["transcript_quality"] in ("medium", "low")
    warning_text = " ".join(result["warnings"])
    assert "Latin" in warning_text or "latin" in warning_text.lower()


# ---------------------------------------------------------------------------
# 9. Repeated phrase → low quality + warning
# ---------------------------------------------------------------------------


def test_repeated_phrase_pattern_detected() -> None:
    result = analyze_transcript_quality(REPEATED_PHRASE_TRANSCRIPT, language="english")
    assert result["quality_signals"]["repeated_phrase_detected"] is True
    assert result["transcript_quality"] == "low"
    warning_text = " ".join(result["warnings"])
    assert "repeat" in warning_text.lower() or "loop" in warning_text.lower()


# ---------------------------------------------------------------------------
# 10. Quality signals shape is always present and has correct keys
# ---------------------------------------------------------------------------


def test_quality_signals_always_returned() -> None:
    result = analyze_transcript_quality(THAI_HIGH_QUALITY, language="thai")
    signals = result["quality_signals"]
    assert "char_count" in signals
    assert "unusual_character_ratio" in signals
    assert "latin_character_ratio" in signals
    assert "thai_character_ratio" in signals
    assert "replacement_character_count" in signals
    assert "repeated_phrase_detected" in signals


def test_thai_ratio_present_in_signals_for_thai_text() -> None:
    result = analyze_transcript_quality(THAI_HIGH_QUALITY, language="thai")
    assert result["quality_signals"]["thai_character_ratio"] > 0


# ---------------------------------------------------------------------------
# 11. quality level is always one of three valid values
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "transcript, source, language",
    [
        (THAI_HIGH_QUALITY, None, "thai"),
        (THAI_HIGH_QUALITY, "local_stt", "thai"),
        (ENGLISH_HIGH_QUALITY, "youtube_caption", "english"),
        (SHORT_TRANSCRIPT, None, "thai"),
        ("", None, "thai"),
        (REPLACEMENT_CHAR_TRANSCRIPT, "local_stt", "thai"),
        (HEAVY_LATIN_IN_THAI, None, "thai"),
        (REPEATED_PHRASE_TRANSCRIPT, None, "english"),
    ],
)
def test_quality_level_is_always_valid(transcript, source, language) -> None:
    result = analyze_transcript_quality(transcript, transcript_source=source, language=language)
    assert result["transcript_quality"] in ("high", "medium", "low")
