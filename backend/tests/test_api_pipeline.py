from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main_app
import app.storage.video_store as video_store
from app.main import app

THAI_DEEP_WORK_REQUEST = {
    "title": "Deep Work Test",
    "source_url": "https://youtube.com/test",
    "language": "thai",
    "transcript": (
        "00:01 วันนี้เราจะพูดถึง deep work "
        "00:05 deep work คือการทำงานแบบมีสมาธิลึกและไม่ถูกรบกวน "
        "00:10 ปัญหาของยุคนี้คือมือถือ notification และ social media ทำให้เราหลุดโฟกัสบ่อย "
        "00:15 เมื่อเราเช็กมือถือ สมองจะได้รับ dopamine สั้น ๆ ทำให้เราติดการสลับความสนใจ "
        "00:20 ถ้าอยากทำงานลึก เราควรปิด notification วางมือถือให้ไกล "
        "และกำหนดช่วงเวลาทำงานที่ชัดเจน"
    ),
}


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(video_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(video_store, "VIDEOS_FILE", tmp_path / "videos.json")
    monkeypatch.setattr(main_app, "save_video", video_store.save_video)
    monkeypatch.setattr(main_app, "get_video", video_store.get_video)
    monkeypatch.setattr(main_app, "list_videos", video_store.list_videos)
    return TestClient(app)


def test_process_ask_and_markdown_export_pipeline(client: TestClient) -> None:
    process_response = client.post("/api/videos/process", json=THAI_DEEP_WORK_REQUEST)

    assert process_response.status_code == 200
    process_body = process_response.json()
    assert process_body["video_id"]
    assert process_body["cleaned_transcript"]
    assert process_body["chunks"]
    assert process_body["summary"]
    assert "00:01" not in process_body["cleaned_transcript"]
    assert "00:20" not in process_body["cleaned_transcript"]
    assert any("ปิด notification" in item for item in process_body["summary"]["action_items"])
    assert any("วางมือถือ" in item for item in process_body["summary"]["action_items"])
    assert any("กำหนดช่วงเวลา" in item for item in process_body["summary"]["action_items"])

    video_id = process_body["video_id"]
    ask_response = client.post(
        f"/api/videos/{video_id}/ask",
        json={"question": "วิดีโอนี้พูดถึงมือถือกับ deep work ยังไง"},
    )

    assert ask_response.status_code == 200
    ask_body = ask_response.json()
    assert ask_body["answer"]
    assert ask_body["related_chunks"]

    markdown_response = client.get(f"/api/videos/{video_id}/export/markdown")

    assert markdown_response.status_code == 200
    markdown_text = markdown_response.text
    assert "# Deep Work Test" in markdown_text
    assert "## TL;DR" in markdown_text
    assert "## Main Ideas" in markdown_text
    assert "## Key Takeaways" in markdown_text
    assert "## Action Items" in markdown_text
    assert "## Questions to Think" in markdown_text
    assert "## Transcript Chunks" in markdown_text
