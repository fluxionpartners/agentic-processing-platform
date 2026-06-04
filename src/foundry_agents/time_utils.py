from datetime import datetime, timezone


def utc_iso() -> str:
    """Return an ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def utc_timestamp() -> float:
    """Return a UTC Unix timestamp."""
    return datetime.now(timezone.utc).timestamp()
