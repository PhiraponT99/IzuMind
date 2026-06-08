from app.services.transcript_cleaner import clean_transcript


def test_timestamps_become_sentence_boundaries_and_preserve_thai_text() -> None:
    transcript = "00:01 วันนี้เราจะพูดถึง deep work 00:05 deep work คือการทำงานแบบมีสมาธิลึก"

    cleaned = clean_transcript(transcript)

    assert "00:01" not in cleaned
    assert "00:05" not in cleaned
    assert "วันนี้เราจะพูดถึง deep work. deep work คือการทำงานแบบมีสมาธิลึก" in cleaned
    assert "วันนี้เราจะพูดถึง" in cleaned
    assert "  " not in cleaned


def test_duplicate_spacing_and_punctuation_are_normalized() -> None:
    transcript = "[00:01] Hello...   world   [00:01:23] again!!"

    cleaned = clean_transcript(transcript)

    assert cleaned == "Hello. world. again!"
