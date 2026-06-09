from urllib.parse import parse_qs, urlparse


def extract_youtube_video_id(source_url: str) -> str:
    parsed = urlparse(source_url.strip())
    host = parsed.netloc.lower().removeprefix("www.")

    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/")[0]
        return _validate_video_id(video_id)

    if host in {"youtube.com", "m.youtube.com"}:
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [""])[0]
            return _validate_video_id(video_id)

    raise ValueError("Invalid YouTube URL. Expected a youtube.com/watch?v=... or youtu.be/... URL.")


def _validate_video_id(video_id: str) -> str:
    cleaned = video_id.strip()
    if not cleaned:
        raise ValueError("Invalid YouTube URL. Missing video id.")

    return cleaned
