import re

TIMESTAMP_PATTERN = re.compile(r"(?<!\d)\[?\b\d{1,2}:\d{2}(?::\d{2})?\b\]?")
WHITESPACE_PATTERN = re.compile(r"\s+")


def clean_transcript(transcript: str) -> str:
    without_timestamps = TIMESTAMP_PATTERN.sub(" ", transcript)
    return WHITESPACE_PATTERN.sub(" ", without_timestamps).strip()
