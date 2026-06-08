import app.config as config
from app.services.summarizer import generate_summary

THAI_DEEP_WORK_TRANSCRIPT = (
    "วันนี้เราจะพูดถึง deep work. "
    "deep work คือการทำงานแบบมีสมาธิลึกและไม่ถูกรบกวน. "
    "ปัญหาของยุคนี้คือมือถือ notification และ social media ทำให้เราหลุดโฟกัสบ่อย. "
    "เมื่อเราเช็กมือถือ สมองจะได้รับ dopamine สั้น ๆ ทำให้เราติดการสลับความสนใจ. "
    "ถ้าอยากทำงานลึก เราควรปิด notification วางมือถือให้ไกล "
    "และกำหนดช่วงเวลาทำงานที่ชัดเจน"
)


def test_thai_summary_shape_and_polished_content() -> None:
    summary = generate_summary(
        THAI_DEEP_WORK_TRANSCRIPT,
        [{"chunk_index": 1, "text": THAI_DEEP_WORK_TRANSCRIPT, "char_count": len(THAI_DEEP_WORK_TRANSCRIPT)}],
        language="thai",
    )

    assert set(summary) == {
        "tldr",
        "main_ideas",
        "key_takeaways",
        "action_items",
        "questions_to_think",
    }
    assert not summary["tldr"].startswith("วิดีโอนี้พูดถึง วันนี้เราจะพูดถึง")
    assert any("ปิด notification" in item for item in summary["action_items"])
    assert any("วางมือถือ" in item for item in summary["action_items"])
    assert any("กำหนดช่วงเวลา" in item for item in summary["action_items"])
    assert summary["questions_to_think"]

    summary_text = " ".join(
        [summary["tldr"]]
        + summary["main_ideas"]
        + summary["key_takeaways"]
        + summary["action_items"]
        + summary["questions_to_think"]
    )
    assert "The transcript covers" not in summary_text
    assert "The cleaned text is ready" not in summary_text
    assert "Use the main ideas" not in summary_text


def test_default_summary_provider_uses_rule_based(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / ".env")
    monkeypatch.delenv("SUMMARY_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    summary = generate_summary(THAI_DEEP_WORK_TRANSCRIPT, [], language="thai")

    assert "tldr" in summary
    assert any("ปิด notification" in item for item in summary["action_items"])


def test_openai_provider_without_config_falls_back_to_rule_based(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / ".env")
    monkeypatch.setenv("SUMMARY_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    summary = generate_summary(THAI_DEEP_WORK_TRANSCRIPT, [], language="thai")

    assert "tldr" in summary
    assert any("วางมือถือ" in item for item in summary["action_items"])
