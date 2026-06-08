import re

TIMESTAMP_PATTERN = re.compile(r"(?<!\d)\[?\b\d{1,2}:\d{2}(?::\d{2})?\b\]?")
WHITESPACE_PATTERN = re.compile(r"\s+")
DUPLICATE_PUNCTUATION_PATTERN = re.compile(r"\s*([.!?\u3002\uff01\uff1f])(?:\s*\1)+\s*")
SPACE_BEFORE_PUNCTUATION_PATTERN = re.compile(r"\s+([.!?\u3002\uff01\uff1f])")
LEADING_BOUNDARY_PATTERN = re.compile(r"^\.\s*")


def clean_transcript(transcript: str) -> str:
    with_sentence_boundaries = TIMESTAMP_PATTERN.sub(". ", transcript)
    normalized_punctuation = DUPLICATE_PUNCTUATION_PATTERN.sub(r"\1 ", with_sentence_boundaries)
    normalized_spacing = WHITESPACE_PATTERN.sub(" ", normalized_punctuation)
    normalized_spacing = SPACE_BEFORE_PUNCTUATION_PATTERN.sub(r"\1", normalized_spacing)
    cleaned = normalized_spacing.strip()
    return LEADING_BOUNDARY_PATTERN.sub("", cleaned).strip()
