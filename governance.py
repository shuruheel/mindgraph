"""Tool-invocation governance checkpoint, ported from mindgraph-mcp's governance.ts.

Every tool call is checked against ``/agent/governance`` before it runs. The gate
fails closed: an unreachable server, a refused credential or an obligation this
adapter cannot discharge all refuse the call. Only a server that does not
implement the checkpoint lets calls through, and that verdict is a five-minute
lease, re-probed when it expires. Capability state lives on the gate instance,
one per provider, so profiles never share it.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import httpx

logger = logging.getLogger(__name__)

UNSUPPORTED_LEASE_SECS = 5 * 60
DEFAULT_RETRY_DELAYS_SECS = (0.15, 0.6)
# ``log`` is discharged by the server's synchronous PolicyDecision write and
# ``require_approval`` by blocking with its durable handle. This adapter has no
# trusted delivery channel for ``notify``, so any other duty refuses.
KNOWN_DUTIES = frozenset({"log", "require_approval"})

PLAN_READ_ACTIONS = frozenset({"get_plan", "get_executions", "get_pending", "get_assessments", "resume_work"})
ONTOLOGY_READ_ACTIONS = frozenset(
    {
        "list_schemas",
        "get_schema",
        "query",
        "search_objects",
        "list_objects",
        "get_object",
        "get_context",
        "list_proposals",
        "get_proposal",
    }
)
UID_FIELDS = (
    "uid",
    "source_uid",
    "entity_uid",
    "series_uid",
    "session_uid",
    "work_uid",
    "goal_uid",
    "project_uid",
    "task_uid",
    "plan_uid",
    "step_uid",
    "target_uid",
    "execution_uid",
    "executor_uid",
    "affordance_uid",
    "produces_node_uid",
    "filter_plan_uid",
    "parent_uid",
    "decision_uid",
    "chosen_option_uid",
    "governed_uid",
    "approval_uid",
    "requires_plan_uid",
    "start_uid",
    "end_uid",
)
UID_ARRAY_FIELDS = (
    "related_uids",
    "depends_on_uids",
    "summarizes_uids",
    "informs_uid",
    "target_uids",
    "anchor_uids",
    "scope_uids",
    "produces_node_uids",
)
_GENERATED_READ_SUFFIX = re.compile(r"_(search|get|context|related|query)$")


def tool_mutability(tool_name: str, action: Optional[str]) -> str:
    """Conservative action-aware mutability; anything unrecognized is a write."""
    if tool_name in ("mindgraph_memory", "mindgraph_retrieve", "mindgraph_series_query"):
        return "read"
    if tool_name == "mindgraph_remember":
        return "write"
    if tool_name == "mindgraph_plan":
        return "read" if action in PLAN_READ_ACTIONS else "write"
    if tool_name == "mindgraph_ingest":
        return "read" if action == "job_status" else "write"
    if tool_name == "mindgraph_synthesize":
        return "read" if action == "signals" else "write"
    if tool_name == "mindgraph_ontology":
        return "read" if action in ONTOLOGY_READ_ACTIONS else "write"
    # Generated ontology tools are reads with deployment-defined names and stable suffixes.
    if _GENERATED_READ_SUFFIX.search(tool_name) and tool_name != "mindgraph_capture":
        return "read"
    return "write"


def governance_target(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    action = args.get("action") if isinstance(args.get("action"), str) else None
    uids: dict[str, None] = {}
    for key in UID_FIELDS:
        value = args.get(key)
        if isinstance(value, str) and value:
            uids[value] = None
    for key in UID_ARRAY_FIELDS:
        value = args.get(key)
        if isinstance(value, list):
            uids.update({uid: None for uid in value if isinstance(uid, str) and uid})
    target: dict[str, Any] = {"tool_name": tool_name}
    if action:
        target["action"] = action
    target["mutability"] = tool_mutability(tool_name, action)
    target["target_uids"] = list(uids)
    return target


def _unsupported_response(status: int, body: str) -> bool:
    if status in (404, 405):
        return True
    if status != 400:
        return False
    lower = body.lower()
    return any(
        marker in lower for marker in ("unknown governance action", "unknown action", "invalid_governance_action")
    )


def _transient(status: int) -> bool:
    return status in (408, 425, 429) or status >= 500


@dataclass
class GateResult:
    allowed: bool
    message: str = ""
    decision: Optional[str] = None
    approval_uid: Optional[str] = None
    policy: Optional[str] = None

    def payload(self) -> dict[str, Any]:
        out: dict[str, Any] = {"error": self.message, "allowed": False}
        for key in ("decision", "approval_uid", "policy"):
            if getattr(self, key) is not None:
                out[key] = getattr(self, key)
        return out


@dataclass
class GovernanceGate:
    base_url: str
    api_key: str
    agent_id: str
    org_id: Optional[str] = None
    disabled: bool = False
    retry_delays: tuple[float, ...] = DEFAULT_RETRY_DELAYS_SECS
    post: Optional[Callable[..., httpx.Response]] = None
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    _capability: str = field(default="unknown", repr=False)
    _unsupported_until: float = field(default=0.0, repr=False)
    _unsupported_logged: bool = field(default=False, repr=False)

    def _headers(self) -> dict[str, str]:
        headers = {"authorization": f"Bearer {self.api_key}", "content-type": "application/json"}
        if self.org_id:
            headers["x-mindgraph-org"] = self.org_id
        return headers

    def check(self, tool_name: str, args: dict[str, Any]) -> GateResult:
        if self.disabled:
            return GateResult(True)
        if self._capability == "unsupported":
            if self.clock() < self._unsupported_until:
                return GateResult(True)
            self._capability = "unknown"  # lease expired: probe again
        post = self.post or httpx.post
        url = f"{self.base_url.rstrip('/')}/agent/governance"
        payload = {
            "action": "check",
            "act": "tool_invoke",
            "agent_id": str(args.get("agent_id") or self.agent_id),
            "target": governance_target(tool_name, args),
            "context": {"adapter": "mindgraph-hermes"},
            "tier": "checkpoint",
        }
        response: Optional[httpx.Response] = None
        last_failure = ""
        for attempt in range(len(self.retry_delays) + 1):
            try:
                candidate = post(url, headers=self._headers(), content=json.dumps(payload), timeout=10.0)
            except httpx.HTTPError as exc:
                last_failure = str(exc) or type(exc).__name__
                if attempt < len(self.retry_delays):
                    self.sleep(self.retry_delays[attempt])
                continue
            if _transient(candidate.status_code) and attempt < len(self.retry_delays):
                last_failure = f"HTTP {candidate.status_code}"
                self.sleep(self.retry_delays[attempt])
                continue
            response = candidate
            break

        if response is None:
            # Unevaluated policy is not a permit, but the message must name
            # connectivity: disabling governance cannot help a server that is down.
            return GateResult(
                False,
                f"MindGraph at {self.base_url} is unreachable ({last_failure}; "
                f"{len(self.retry_delays) + 1} attempts). The tool call was NOT evaluated "
                "against policy and NOT executed — this is a connectivity failure, not a "
                "governance denial. Check the network and MINDGRAPH_BASE_URL, then retry.",
            )

        body = response.text
        if not response.is_success:
            if self._capability == "unknown" and _unsupported_response(response.status_code, body):
                self._capability = "unsupported"
                self._unsupported_until = self.clock() + UNSUPPORTED_LEASE_SECS
                if not self._unsupported_logged:
                    self._unsupported_logged = True
                    logger.warning(
                        "This MindGraph server does not implement the governance checkpoint "
                        "(HTTP %s); tool calls proceed ungoverned. Re-probing every %d minutes.",
                        response.status_code,
                        UNSUPPORTED_LEASE_SECS // 60,
                    )
                return GateResult(True)
            if response.status_code in (401, 403):
                # The checkpoint exists and refused this credential; failing open
                # would hand the caller the bypass the policy exists to prevent.
                return GateResult(
                    False,
                    "This credential is not permitted to evaluate MindGraph governance "
                    f"(HTTP {response.status_code}). Use a user-scoped API key, or set "
                    "MINDGRAPH_GOVERNANCE=off to run this provider ungoverned.",
                )
            return GateResult(False, f"MindGraph governance check failed ({response.status_code})")

        self._capability = "supported"
        self._unsupported_logged = False
        try:
            decision = json.loads(body)
        except ValueError:
            decision = None
        if not isinstance(decision, dict):
            return GateResult(False, "MindGraph governance returned an invalid decision")
        obligations = decision.get("obligations") if isinstance(decision.get("obligations"), list) else []
        if any(
            not isinstance(item, dict) or item.get("duty") not in KNOWN_DUTIES for item in obligations
        ):
            return GateResult(
                False,
                "MindGraph governance returned an obligation this adapter cannot safely enforce",
                decision=str(decision.get("decision") or "conditional"),
            )
        verdict = str(decision.get("decision") or "deny")
        if verdict == "permit":
            return GateResult(True)
        fired = decision.get("fired_policies") if isinstance(decision.get("fired_policies"), list) else []
        first = fired[0] if fired and isinstance(fired[0], dict) else {}
        policy = first.get("name") if isinstance(first.get("name"), str) else None
        approval_uid = decision.get("approval_uid") if isinstance(decision.get("approval_uid"), str) else None
        if verdict == "conditional":
            message = "Approval is required" + (f" by policy {policy}" if policy else "")
            message += f" (approval {approval_uid})" if approval_uid else ""
        else:
            message = "Denied by MindGraph governance" + (f" policy {policy}" if policy else "")
        return GateResult(False, message, decision=verdict, approval_uid=approval_uid, policy=policy)
