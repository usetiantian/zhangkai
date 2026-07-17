# -*- coding: utf-8 -*-
"""
StreamContext — OpenTelemetry-style async context propagation.
Propagates trace_id, user_id, session_id across async boundaries via contextvars.
"""
import contextvars, logging, time, uuid
from contextlib import contextmanager
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

# ── Context Variables ────────────────────────────────────────────

_trace_id: contextvars.ContextVar[str] = contextvars.ContextVar("stream_trace_id", default="")
_span_id: contextvars.ContextVar[str] = contextvars.ContextVar("stream_span_id", default="")
_user_id: contextvars.ContextVar[str] = contextvars.ContextVar("stream_user_id", default="")
_session_id: contextvars.ContextVar[str] = contextvars.ContextVar("stream_session_id", default="")
_message_id: contextvars.ContextVar[str] = contextvars.ContextVar("stream_message_id", default="")
_request_start: contextvars.ContextVar[float] = contextvars.ContextVar("stream_request_start", default=0.0)
_metadata: contextvars.ContextVar[Dict] = contextvars.ContextVar("stream_metadata", default={})

# ── Context Manager ──────────────────────────────────────────────

class StreamContext:
    """Propagate trace context across async boundaries."""

    def __init__(self, trace_id: str = None, user_id: str = None,
                 session_id: str = None, metadata: Dict = None):
        self._token = None
        self._trace_id = trace_id or uuid.uuid4().hex[:16]
        self._user_id = user_id or ""
        self._session_id = session_id or ""
        self._metadata = metadata or {}

    def __enter__(self):
        self._token = (
            _trace_id.set(self._trace_id),
            _user_id.set(self._user_id),
            _session_id.set(self._session_id),
            _request_start.set(time.time()),
            _metadata.set(self._metadata),
        )
        return self

    def __exit__(self, *args):
        if self._token:
            _trace_id.reset(self._token[0])
            _user_id.reset(self._token[1])
            _session_id.reset(self._token[2])
            _request_start.reset(self._token[3])
            _metadata.reset(self._token[4])

    @staticmethod
    def current() -> Dict:
        """Get current context as dict."""
        return {
            "trace_id": _trace_id.get(),
            "span_id": _span_id.get(),
            "user_id": _user_id.get(),
            "session_id": _session_id.get(),
            "message_id": _message_id.get(),
            "elapsed_ms": round((time.time() - _request_start.get()) * 1000, 1) if _request_start.get() else 0,
            "metadata": _metadata.get(),
        }

    @staticmethod
    def set_span(span_id: str):
        _span_id.set(span_id)

    @staticmethod
    def set_message(msg_id: str):
        _message_id.set(msg_id)

    @staticmethod
    def set_user(uid: str):
        _user_id.set(uid)

    @staticmethod
    def set_session(sid: str):
        _session_id.set(sid)

    @staticmethod
    def set_meta(key: str, value: Any):
        meta = _metadata.get()
        meta[key] = value
        _metadata.set(meta)


@contextmanager
def trace_span(name: str, attributes: Dict = None):
    """Convenience context manager for tracing a span."""
    span_id = uuid.uuid4().hex[:8]
    StreamContext.set_span(span_id)
    start = time.time()
    try:
        yield span_id
    except Exception as e:
        logger.debug("[Trace] span=%s error=%s", name, str(e)[:100])
        raise
    finally:
        elapsed = (time.time() - start) * 1000
        logger.debug("[Trace] span=%s id=%s elapsed=%.1fms attrs=%s",
                     name, span_id, elapsed, attributes or {})
