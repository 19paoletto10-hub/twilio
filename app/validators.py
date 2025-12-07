from __future__ import annotations

import re
from typing import Optional

# Prefer phonenumbers library if available for robust E.164 validation
try:
    import phonenumbers  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    phonenumbers = None  # type: ignore


STRICT_RE = re.compile(r"^\+\d{11}$")


def is_valid_number(value: Optional[str]) -> bool:
    """Validate a phone number.

    Behaviour:
    - If `phonenumbers` is available, parse the number and accept valid E.164 numbers.
    - Otherwise fall back to a strict regex `^\\+\\d{11}$` (plus and 11 digits),
      as requested by the project requirements.

    Returns True when the number is acceptable for sending/receiving SMS in
    this application.
    """
    if not value:
        return False
    value = value.strip()

    if phonenumbers:
        try:
            pn = phonenumbers.parse(value, None)
            # Accept only numbers that are valid and in E.164 format
            return phonenumbers.is_possible_number(pn) and phonenumbers.is_valid_number(pn)
        except Exception:
            return False

    # Fallback: strict pattern (+ and exactly 11 digits)
    return bool(STRICT_RE.match(value))
