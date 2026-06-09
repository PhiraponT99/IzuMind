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
