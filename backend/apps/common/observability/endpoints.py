"""HTTP path helpers for low-cardinality metric labels."""

from __future__ import annotations

import re

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
NUMERIC_RE = re.compile(r"^\d+$")


def normalize_endpoint(path: str) -> str:
    if not path:
        return "/"
    parts = []
    for segment in path.split("/"):
        if not segment:
            continue
        if UUID_RE.match(segment) or NUMERIC_RE.match(segment):
            parts.append(":id")
        else:
            parts.append(segment)
    return "/" + "/".join(parts) if parts else "/"
