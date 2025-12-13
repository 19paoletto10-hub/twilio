"""
Date/time utilities for consistent timestamp handling across the application.

Centralizes datetime parsing, formatting, and timezone conversions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


# Standard timestamp format used throughout the application
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S"
TIMESTAMP_FORMAT_WITH_MS = "%Y-%m-%dT%H:%M:%S.%f"


def utc_now() -> datetime:
    """
    Get current UTC time as timezone-aware datetime.

    Returns:
        Current UTC datetime with timezone info
    """
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """
    Get current UTC time as ISO 8601 string.

    Returns:
        ISO 8601 formatted timestamp string

    Examples:
        >>> utc_now_iso()
        '2025-12-13T10:30:45'
    """
    return utc_now().strftime(TIMESTAMP_FORMAT)


def parse_iso_timestamp(value: Optional[str]) -> Optional[datetime]:
    """
    Parse ISO 8601 timestamp string to timezone-aware datetime.

    Handles various ISO formats including:
    - With 'Z' suffix: '2025-12-13T10:30:45Z'
    - Without timezone: '2025-12-13T10:30:45'
    - With microseconds: '2025-12-13T10:30:45.123456'

    Args:
        value: ISO timestamp string to parse

    Returns:
        Timezone-aware datetime in UTC, or None if parsing fails

    Examples:
        >>> parse_iso_timestamp('2025-12-13T10:30:45Z')
        datetime.datetime(2025, 12, 13, 10, 30, 45, tzinfo=datetime.timezone.utc)
        >>> parse_iso_timestamp(None)
        None
    """
    if not value:
        return None

    try:
        # Remove 'Z' suffix if present
        clean_value = value.replace("Z", "").replace("+00:00", "")

        # Try parsing with microseconds first
        try:
            dt = datetime.strptime(clean_value, TIMESTAMP_FORMAT_WITH_MS)
        except ValueError:
            # Fall back to standard format
            dt = datetime.strptime(clean_value, TIMESTAMP_FORMAT)

        # Ensure timezone aware
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt

    except (ValueError, AttributeError):
        return None


def datetime_to_iso(value: Optional[datetime]) -> Optional[str]:
    """
    Convert datetime to ISO 8601 string in UTC.

    Args:
        value: Datetime to convert

    Returns:
        ISO formatted string in UTC, or None if input is None

    Examples:
        >>> from datetime import datetime, timezone
        >>> dt = datetime(2025, 12, 13, 10, 30, 45, tzinfo=timezone.utc)
        >>> datetime_to_iso(dt)
        '2025-12-13T10:30:45'
    """
    if value is None:
        return None

    # Convert to UTC if timezone aware
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc)
    else:
        # Assume UTC if naive
        value = value.replace(tzinfo=timezone.utc)

    return value.strftime(TIMESTAMP_FORMAT)


def is_same_date(dt1: Optional[datetime], dt2: Optional[datetime]) -> bool:
    """
    Check if two datetimes represent the same calendar date (ignoring time).

    Args:
        dt1: First datetime
        dt2: Second datetime

    Returns:
        True if both datetimes are on the same date, False otherwise
    """
    if dt1 is None or dt2 is None:
        return False

    return dt1.date() == dt2.date()


def format_friendly_datetime(value: Optional[datetime]) -> str:
    """
    Format datetime for human-readable display.

    Args:
        value: Datetime to format

    Returns:
        Formatted string like "13 Dec 2025, 10:30"

    Examples:
        >>> from datetime import datetime, timezone
        >>> dt = datetime(2025, 12, 13, 10, 30, 45, tzinfo=timezone.utc)
        >>> format_friendly_datetime(dt)
        '13 Dec 2025, 10:30'
    """
    if value is None:
        return "—"

    try:
        return value.strftime("%d %b %Y, %H:%M")
    except (AttributeError, ValueError):
        return "—"


def seconds_until(target_time: datetime) -> int:
    """
    Calculate seconds from now until target time.

    Args:
        target_time: Target datetime (should be timezone-aware)

    Returns:
        Number of seconds until target time (negative if in past)
    """
    now = utc_now()

    # Ensure both are timezone-aware
    if target_time.tzinfo is None:
        target_time = target_time.replace(tzinfo=timezone.utc)

    delta = target_time - now
    return int(delta.total_seconds())


def add_seconds(dt: datetime, seconds: int) -> datetime:
    """
    Add seconds to datetime.

    Args:
        dt: Base datetime
        seconds: Number of seconds to add (can be negative)

    Returns:
        New datetime with seconds added
    """
    from datetime import timedelta

    return dt + timedelta(seconds=seconds)
