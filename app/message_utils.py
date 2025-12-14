"""Shared helpers for preparing SMS payloads and enforcing size constraints."""

from __future__ import annotations

from typing import List

MAX_SMS_CHARS = 1500


def split_sms_chunks(text: str, max_length: int = MAX_SMS_CHARS) -> List[str]:
    """Split text into SMS-sized chunks while attempting sentence boundaries."""

    cleaned = (text or "").strip()
    if not cleaned:
        return [""]

    if len(cleaned) <= max_length:
        return [cleaned]

    chunks: List[str] = []
    remaining = cleaned
    delimiters = ["\n\n", "\n", ". ", "! ", "? ", "; "]

    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining.strip())
            break

        split_pos = -1
        for delim in delimiters:
            idx = remaining.rfind(delim, 0, max_length)
            if idx != -1:
                split_pos = idx + len(delim)
                break

        if split_pos == -1:
            split_pos = max_length

        chunk = remaining[:split_pos].strip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[split_pos:].strip()

    return chunks or [""]
