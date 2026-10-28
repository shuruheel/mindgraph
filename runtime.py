"""Per-provider binding: the SDK client, identity and session state for one Hermes
profile.

Hermes may serve several profiles from one process, each with its own provider
instance (MemoryProvider multiplexing contract). Everything profile-specific
therefore lives on a ``Runtime`` owned by the provider instance, never at module
level. This module does not import Hermes, so handlers and tests can use it alone.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Optional

from mindgraph import MindGraph

DEFAULT_BASE_URL = "https://api.mindgraph.cloud"
DEFAULT_AGENT_ID = "hermes"
HARNESS = "hermes"


def stable_json(value: Any) -> str:
    """Key-sorted JSON, mirroring mindgraph-mcp's ``stableJson``."""
    if isinstance(value, list):
        return "[" + ",".join(stable_json(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ",".join(
            f"{json.dumps(key, ensure_ascii=False)}:{stable_json(value[key])}" for key in sorted(value)
        ) + "}"
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


@dataclass
class Runtime:
    api_key: str
    base_url: str = DEFAULT_BASE_URL
    agent_id: str = DEFAULT_AGENT_ID
    org_id: Optional[str] = None
    # Hermes conversation identity; the turn number scopes default idempotency keys.
    session_id: str = ""
    turn_number: int = 0
    platform: str = ""
    # "primary" writes; "subagent" / "cron" / "flush" contexts never write automatically.
    agent_context: str = "primary"
    # Interactive budget: Hermes bounds prefetch with its own timeout, and a stuck
    # call must not hold a turn through several SDK retries.
    timeout: float = 15.0
    max_retries: int = 1
    client: Optional[Any] = None

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = MindGraph(
                self.base_url,
                api_key=self.api_key,
                org_id=self.org_id or None,
                timeout=self.timeout,
                max_retries=self.max_retries,
            )

    @property
    def write_enabled(self) -> bool:
        return self.agent_context == "primary"

    def close(self) -> None:
        close = getattr(self.client, "close", None)
        if callable(close):
            close()

    def default_idempotency_key(self, tool: str, args: dict[str, Any]) -> Optional[str]:
        """Port of ``defaultWriteIdempotencyKey``: the same tool call in the same
        Hermes turn replays instead of duplicating."""
        if isinstance(args.get("idempotency_key"), str):
            return args["idempotency_key"]
        if not self.session_id:
            return None
        canonical = {k: v for k, v in args.items() if k not in ("invocation_context", "idempotency_key")}
        return hashlib.sha256(
            stable_json(
                {
                    "harness_session_id": self.session_id,
                    "harness_turn_id": str(self.turn_number) if self.turn_number else None,
                    "tool": tool,
                    "action": args.get("action"),
                    "args": canonical,
                }
            ).encode()
        ).hexdigest()
