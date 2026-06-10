from pathlib import Path
import pytest

from app.services.youtube_utils import extract_youtube_video_id


def test_extract_youtube_video_id_from_watch_url() -> None:
    assert extract_youtube_video_id("https://www.youtube.com/watch?v=abc123XYZ_9") == "abc123XYZ_9"


def test_extract_youtube_video_id_from_short_url() -> None:
    assert extract_youtube_video_id("https://youtu.be/abc123XYZ_9") == "abc123XYZ_9"


def test_extract_youtube_video_id_from_url_with_extra_query_params() -> None:
    assert (
        extract_youtube_video_id("https://youtube.com/watch?v=abc123XYZ_9&t=30s&list=playlist")
        == "abc123XYZ_9"
    )


def test_extract_youtube_video_id_rejects_invalid_url() -> None:
    with pytest.raises(ValueError):
        extract_youtube_video_id("https://example.com/watch?v=abc123XYZ_9")


def test_delete_audio_file_success(tmp_path: Path) -> None:
    from app.services.youtube_audio_downloader import delete_audio_file
    temp_file = tmp_path / "test_audio.m4a"
    temp_file.write_text("dummy audio content")
    assert temp_file.exists()

    delete_audio_file(str(temp_file))
    assert not temp_file.exists()


def test_delete_audio_file_nonexistent() -> None:
    from app.services.youtube_audio_downloader import delete_audio_file
    # Should not raise any error
    delete_audio_file("nonexistent_file_path_12345.m4a")


def test_delete_audio_file_handles_exception(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.youtube_audio_downloader import delete_audio_file
    temp_file = tmp_path / "test_audio_fail.m4a"
    temp_file.write_text("dummy audio content")
    assert temp_file.exists()

    def fake_unlink(self, *args, **kwargs):
        raise OSError("Access denied")

    monkeypatch.setattr(Path, "unlink", fake_unlink)

    # This should not raise any exception, but return cleanly
    delete_audio_file(str(temp_file))

    # Since unlink failed, file should still exist
    assert temp_file.exists()
