"""Request-scoped observability context."""

from __future__ import annotations

from contextvars import ContextVar

user_id_var: ContextVar[str] = ContextVar("user_id", default="-")
endpoint_var: ContextVar[str] = ContextVar("endpoint", default="-")
