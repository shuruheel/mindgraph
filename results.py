"""Tool result encoding, ported from mindgraph-mcp's ``ok``/``err``/``renderedResult``
(tools.ts) and ``toolError`` (error-detail.ts).

Hermes tool handlers return one JSON string. Successful reads carry rendered text
under ``result``; raw data is the compact JSON itself; failures carry ``error``
plus the server's typed ``code``/``retriable``/``status`` so the model can tell a
refused call from an empty graph.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Optional

from mindgraph import MindGraphError

# Machine-readable fencing state from 409 bodies; must survive as JSON siblings of
# ``error`` (error-detail.ts CONFLICT_STATE_KEYS).
_CONFLICT_STATE_KEYS = (
    "current_version",
    "current_epoch",
    "lease_expires_at",
    "lease_owner_agent_id",
)


def dumps(value: Any) -> str:
    # Compact on purpose: pretty-printing roughly doubles the tokens a model reads.
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False, default=str)


def ok(data: Any) -> str:
    return dumps(data)


def text(rendered: str, **extra: Any) -> str:
    return dumps({"result": rendered, **extra})


def rendered(fmt: Optional[str], raw: Any, render: Callable[[Any], Optional[str]]) -> str:
    """Rendered by default; ``format: "json"`` is the raw escape, and a shape the
    renderer does not recognize falls back to raw."""
    if fmt == "json":
        return ok(raw)
    out = render(raw)
    return text(out) if out is not None else ok(raw)


def err(message: str) -> str:
    return dumps({"error": message})


def error_detail(exc: BaseException) -> str:
    """Server typed-error bodies must reach the model; it can only self-correct on
    errors it can see."""
    if isinstance(exc, MindGraphError) and exc.body is not None:
        detail = exc.body if isinstance(exc.body, str) else dumps(exc.body)
        return f"{exc} — {detail}"
    return str(exc)


def error_payload(exc: BaseException, fallback_code: Optional[str] = None) -> dict[str, Any]:
    body = exc.body if isinstance(exc, MindGraphError) and isinstance(exc.body, dict) else {}
    payload: dict[str, Any] = {"error": error_detail(exc)}
    payload.update({key: body[key] for key in _CONFLICT_STATE_KEYS if body.get(key) is not None})
    if isinstance(exc, MindGraphError):
        payload["status"] = exc.status
    code = body.get("code") if isinstance(body.get("code"), str) else fallback_code
    if code is not None:
        payload["code"] = code
    if isinstance(body.get("retriable"), bool):
        payload["retriable"] = body["retriable"]
    return payload


def tool_error(exc: BaseException, fallback_code: Optional[str] = None) -> str:
    return dumps(error_payload(exc, fallback_code))


def is_error(result: str) -> bool:
    try:
        decoded = json.loads(result)
    except ValueError:
        return False
    return isinstance(decoded, dict) and "error" in decoded
