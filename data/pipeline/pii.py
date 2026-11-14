"""Mask contact details in free text before it leaves the pipeline."""

import re

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
URL = re.compile(r"(https?://|www\.)\S+", re.IGNORECASE)
PHONE_CANDIDATE = re.compile(r"(?<!\w)\+?\d[\d\s().-]{7,}\d(?!\w)")
HANDLE = re.compile(r"(?<![\w.])@\w{2,}")
MIN_PHONE_DIGITS = 9  # dates like 2024-02-17 have 8 digits and must survive


def _mask_phone(match: re.Match[str]) -> str:
    digits = sum(char.isdigit() for char in match.group())
    return "[PHONE]" if digits >= MIN_PHONE_DIGITS else match.group()


def mask_pii(text: str) -> str:
    text = EMAIL.sub("[EMAIL]", text)
    text = URL.sub("[URL]", text)
    text = PHONE_CANDIDATE.sub(_mask_phone, text)
    return HANDLE.sub("[HANDLE]", text)
