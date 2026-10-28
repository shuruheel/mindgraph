"""Write-tool handlers, ported from mindgraph-mcp's ``tools.ts``: ``handleCapture``,
``handleReason``, ``handleCommit``, ``handlePlan`` and ``handleRemember``.

The dispatcher has already injected ``agent_id``, the default idempotency key and
the disposition mutual-exclusion check, so these only map arguments to the SDK.
Bodies drop ``None`` fields at the top level, matching ``JSON.stringify`` dropping
``undefined`` in the TS client; caller-authored ``props`` are passed through as is.
"""

from __future__ import annotations

from typing import Any, Optional

from .results import err, ok
from .runtime import Runtime

_RESOLUTION_KEYS = (
    "idempotency_key",
    "reuse_uid",
    "supersedes_uid",
    "contradicts_uid",
    "confirm_new",
    "on_near_duplicate",
)


def _compact(body: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in body.items() if value is not None}


def _resolution(args: dict[str, Any]) -> dict[str, Any]:
    return {key: args[key] for key in _RESOLUTION_KEYS if args.get(key) is not None}


def _nonblank(value: Any) -> Optional[str]:
    return value.strip() if isinstance(value, str) and value.strip() else None


# ── Remember (fast path) ─────────────────────────────────────────────


def handle_remember(rt: Runtime, args: dict[str, Any]) -> str:
    """``custom_id`` is the upsert contract here, so no idempotency key is sent."""
    action = args.get("action")
    agent_id = args.get("agent_id")
    if action == "remember":
        text = args.get("text")
        if not isinstance(text, str) or not text.strip():
            return err("remember requires non-empty text")
        options: dict[str, Any] = {}
        if custom_id := _nonblank(args.get("custom_id")):
            options["custom_id"] = custom_id
        if _nonblank(args.get("label")):
            options["label"] = args["label"]
        if _nonblank(args.get("space_uid")):
            options["space_uid"] = args["space_uid"]
        if args.get("on_near_duplicate") in ("reuse", "create"):
            options["on_near_duplicate"] = args["on_near_duplicate"]
        if isinstance(args.get("props"), dict):
            options["props"] = args["props"]
        if isinstance(agent_id, str):
            options["agent_id"] = agent_id
        return ok(rt.client.remember(text, **options))
    if action == "forget":
        if uid := _nonblank(args.get("uid")):
            target = {"uid": uid}
        elif custom_id := _nonblank(args.get("custom_id")):
            target = {"custom_id": custom_id}
        else:
            return err("forget requires uid or custom_id")
        options = {}
        if args.get("dry_run") is True:
            options["dry_run"] = True
        if isinstance(args.get("cascade"), bool):
            options["cascade"] = args["cascade"]
        if _nonblank(args.get("reason")):
            options["reason"] = args["reason"]
        if isinstance(agent_id, str):
            options["agent_id"] = agent_id
        return ok(rt.client.forget(**target, **options))
    return err(f"Unknown remember action: {action}")


# ── Capture (Reality + Memory) ───────────────────────────────────────


def handle_capture(rt: Runtime, args: dict[str, Any]) -> str:
    client = rt.client
    action = args.get("action")
    label = args.get("label")
    summary = args.get("summary")
    props = args.get("props")
    agent_id = args.get("agent_id")
    resolution = _resolution(args)

    if action == "lesson":
        return ok(
            client.distill(
                **_compact(
                    {
                        "label": label,
                        "output_type": "lesson",
                        "summary": summary,
                        "confidence": args.get("confidence"),
                        "salience": args.get("salience"),
                        "session_uid": args.get("session_uid"),
                        "work_uid": args.get("work_uid"),
                        "execution_uid": args.get("execution_uid"),
                        **resolution,
                        "summarizes_uids": args.get("summarizes_uids"),
                        "props": props,
                        "agent_id": agent_id,
                    }
                )
            )
        )
    if action == "skill":
        name, description, content = args.get("name"), args.get("description"), args.get("content")
        if not name:
            return err("name is required for action=skill")
        if not description:
            return err("description is required for action=skill")
        if content is None:
            return err("content is required for action=skill")
        summarizes = args.get("summarizes_uids")
        has_provenance = any(
            isinstance(args.get(key), str) and args[key] for key in ("session_uid", "work_uid", "execution_uid")
        ) or (isinstance(summarizes, list) and any(isinstance(uid, str) and uid for uid in summarizes))
        if not has_provenance:
            return err(
                "at least one of session_uid, work_uid, execution_uid, or summarizes_uids is required for action=skill"
            )
        skill_props = {"name": name, "description": description, "content": content}
        if args.get("license"):
            skill_props["license"] = args["license"]
        # Skills accept only a supersession disposition, not reuse/contradiction.
        return ok(
            client.distill(
                **_compact(
                    {
                        "label": label,
                        "output_type": "skill",
                        "summary": summary,
                        "confidence": args.get("confidence"),
                        "salience": args.get("salience"),
                        "session_uid": args.get("session_uid"),
                        "work_uid": args.get("work_uid"),
                        "execution_uid": args.get("execution_uid"),
                        "idempotency_key": args.get("idempotency_key"),
                        "supersedes_uid": args.get("supersedes_uid"),
                        "summarizes_uids": summarizes,
                        "props": skill_props,
                        "agent_id": agent_id,
                    }
                )
            )
        )
    if action == "journal":
        content = args.get("content")
        if not content:
            return err("content is required for action=journal")
        journal_props: dict[str, Any] = {"content": content}
        if args.get("mood"):
            journal_props["mood"] = args["mood"]
        if args.get("tags"):
            journal_props["tags"] = args["tags"]
        # The SDK's journal() helper has no resolution fields, so post the TS
        # client's journal body to /memory/session directly.
        return ok(
            client.session(
                **_compact(
                    {"action": "journal", "label": label, "props": journal_props, "agent_id": agent_id, **resolution}
                )
            )
        )
    if action in ("entity", "concept"):
        entity_props = dict(props or {})
        if action == "entity":
            if summary:
                entity_props["description"] = summary
            entity_props["entity_type"] = args.get("entity_type") or "concept"
        else:
            entity_props["entity_type"] = "concept"
            if summary:
                entity_props["description"] = summary
        return ok(
            client.entity(
                **_compact({"action": "create", "label": label, "props": entity_props, "agent_id": agent_id, **resolution})
            )
        )
    if action in ("observation", "source", "snippet"):
        return ok(
            client.capture(
                **_compact(
                    {
                        "action": action,
                        "label": label,
                        "summary": summary,
                        "source_uid": args.get("source_uid") if action == "snippet" else None,
                        "confidence": args.get("confidence"),
                        "salience": args.get("salience"),
                        "props": props,
                        "agent_id": agent_id,
                        **resolution,
                    }
                )
            )
        )
    return err(f"Unknown capture action: {action}")


# ── Reason (Argue + Inquire) ─────────────────────────────────────────


def handle_reason(rt: Runtime, args: dict[str, Any]) -> str:
    action = args.get("action")
    label = args.get("label")
    resolution = _resolution(args)

    if action == "claim":
        # ArgumentRequest carries prose in props; a top-level ``content`` key is
        # silently dropped by serde, so map content/description into props.
        claim = args.get("claim")
        if claim:
            claim_obj = _compact({"label": claim.get("label"), "confidence": claim.get("confidence")})
            if claim.get("content"):
                claim_obj["props"] = {"content": claim["content"]}
        elif label:
            claim_obj = _compact({"label": label, "confidence": args.get("confidence")})
        else:
            return err("claim object or label is required for action=claim")
        evidence = args.get("evidence")
        warrant = args.get("warrant")
        warrant_obj = None
        if warrant:
            warrant_obj = {"label": warrant.get("label")}
            if warrant.get("content"):
                warrant_obj["props"] = {"content": warrant["content"]}
        return ok(
            rt.client.argue(
                **_compact(
                    {
                        "claim": claim_obj,
                        "evidence": None
                        if evidence is None
                        else [
                            {"label": item.get("label"), **({"props": {"description": item["description"]}} if item.get("description") else {})}
                            for item in evidence
                        ],
                        "warrant": warrant_obj,
                        "argument": args.get("argument"),
                        "agent_id": args.get("agent_id"),
                        **resolution,
                    }
                )
            )
        )

    if not label:
        return err(f"label is required for action={action}")
    return ok(
        rt.client.inquire(
            **_compact(
                {
                    "action": action,
                    "label": label,
                    "summary": args.get("summary"),
                    "confidence": args.get("confidence"),
                    "salience": args.get("salience"),
                    "props": args.get("props"),
                    "agent_id": args.get("agent_id"),
                    **resolution,
                }
            )
        )
    )


# ── Commit (+ Decide) ────────────────────────────────────────────────


def handle_commit(rt: Runtime, args: dict[str, Any]) -> str:
    client = rt.client
    action = args.get("action")
    label = args.get("label")
    decision_uid = args.get("decision_uid")
    common = {"summary": args.get("summary"), "props": args.get("props"), "agent_id": args.get("agent_id")}
    resolution = _resolution(args)

    if action in ("goal", "project", "milestone"):
        if not label:
            return err(f"label is required for action={action}")
        return ok(
            client.commit(
                **_compact(
                    {
                        "action": action,
                        "label": label,
                        "summary": args.get("summary"),
                        "parent_uid": args.get("parent_uid"),
                        "confidence": args.get("confidence"),
                        "salience": args.get("salience"),
                        "props": args.get("props"),
                        "agent_id": args.get("agent_id"),
                        **resolution,
                    }
                )
            )
        )
    # The SDK's open_decision/add_option/resolve_decision helpers drop resolution
    # fields, so these post the TS client's bodies to /intent/deliberation.
    if action == "open_decision":
        if not label:
            return err("label is required for open_decision")
        return ok(client.deliberate(**_compact({"action": "open_decision", "label": label, **common, **resolution})))
    if action == "add_option":
        if not decision_uid:
            return err("decision_uid is required for add_option")
        if not label:
            return err("label is required for add_option")
        return ok(
            client.deliberate(
                **_compact({"action": "add_option", "decision_uid": decision_uid, "label": label, **common, **resolution})
            )
        )
    if action == "add_constraint":
        if not decision_uid:
            return err("decision_uid is required for add_constraint")
        return ok(
            client.deliberate(
                **_compact({"action": "add_constraint", "label": label, "decision_uid": decision_uid, **common, **resolution})
            )
        )
    if action == "resolve_decision":
        if not decision_uid:
            return err("decision_uid is required for resolve_decision")
        if not args.get("chosen_option_uid"):
            return err("chosen_option_uid is required for resolve_decision")
        return ok(
            client.deliberate(
                **_compact(
                    {
                        "action": "resolve",
                        "decision_uid": decision_uid,
                        "chosen_option_uid": args["chosen_option_uid"],
                        "summary": args.get("summary"),
                        "props": args.get("props"),
                        "informs_uid": args.get("informs_uid"),
                        "as_of_date": args.get("as_of_date"),
                        "session_id": args.get("session_id"),
                        "retrieval_trace_id": args.get("retrieval_trace_id"),
                        "agent_id": args.get("agent_id"),
                        **resolution,
                    }
                )
            )
        )
    if action == "get_open_decisions":
        return ok(client.get_open_decisions())
    return err(f"Unknown commit action: {action}")


# ── Plan (+ Action/Procedure/Risk) ───────────────────────────────────

_PLAN_ACTIONS = frozenset(
    {
        "create_task",
        "create_plan",
        "add_step",
        "update_status",
        "get_plan",
        "resume_work",
        "claim_task",
        "heartbeat",
        "start_iteration",
        "checkpoint_iteration",
        "block_task",
        "complete_task",
        "abandon_iteration",
    }
)

# Every /agent/plan contract field, forwarded without renaming.
_PLAN_FIELDS = (
    "label",
    "summary",
    "confidence",
    "salience",
    "goal_uid",
    "plan_uid",
    "task_uid",
    "step_uid",
    "session_uid",
    "target_uid",
    "depends_on_uids",
    "related_uids",
    "status",
    "task_status",
    "step_status",
    "execution_status",
    "execution_uid",
    "expected_version",
    "lease_epoch",
    "lease_ttl_secs",
    "idempotency_key",
    "allow_takeover",
    "release_lease",
    "override_reason",
    "scope_uids",
    "limit",
    "input_snapshot",
    "output_snapshot",
    "side_effects",
    "outcome",
    "error",
    "next_action",
    "checkpoint_summary",
    "test_summary",
    "produces_node_uids",
    "props",
    "agent_id",
)


def _pick(args: dict[str, Any], *keys: str) -> dict[str, Any]:
    return {key: args.get(key) for key in keys}


def handle_plan(rt: Runtime, args: dict[str, Any]) -> str:
    client = rt.client
    action = args.get("action")

    if action in _PLAN_ACTIONS:
        # The MCP resolves ``repo`` into a repository scope through the coding
        # profile's code adapter; Hermes has none, so refuse rather than create
        # a Task without the scope the caller asked for.
        if action == "create_task" and args.get("repo"):
            return err("repo scoping requires the mindgraph-mcp coding profile; pass scope_uids instead")
        return ok(client.plan(**_compact({"action": action, **_pick(args, *_PLAN_FIELDS)})))

    if action == "start_execution":
        return ok(
            client.execution(
                **_compact(
                    {
                        "action": "start",
                        **_pick(
                            args,
                            "label",
                            "summary",
                            "confidence",
                            "salience",
                            "plan_uid",
                            "executor_uid",
                            "affordance_uid",
                            "related_uids",
                            "input_snapshot",
                            "props",
                            "agent_id",
                        ),
                    }
                )
            )
        )
    if action == "complete_execution":
        return ok(
            client.execution(
                **_compact(
                    {
                        "action": "complete",
                        **_pick(
                            args,
                            "execution_uid",
                            "produces_node_uid",
                            "output_snapshot",
                            "side_effects",
                            "outcome",
                            "props",
                            "agent_id",
                        ),
                    }
                )
            )
        )
    if action == "fail_execution":
        return ok(
            client.execution(
                **_compact(
                    {
                        "action": "fail",
                        **_pick(
                            args, "execution_uid", "output_snapshot", "side_effects", "outcome", "error", "props", "agent_id"
                        ),
                    }
                )
            )
        )
    if action == "register_agent":
        return ok(
            client.execution(
                **_compact(
                    {
                        "action": "register_agent",
                        **_pick(args, "label", "summary", "confidence", "salience", "props", "agent_id"),
                    }
                )
            )
        )
    if action == "get_executions":
        return ok(
            client.execution(**_compact({"action": "get_executions", **_pick(args, "filter_plan_uid", "agent_id")}))
        )

    # Governance is read-only from the model by design (C33): it must not author
    # the policy it is judged by, nor raise and clear its own approval gate.
    if action == "get_pending":
        return ok(client.governance(**_compact({"action": "get_pending", "agent_id": args.get("agent_id")})))

    if action in ("create_flow", "add_affordance", "add_control", "add_procedure_step"):
        return ok(
            client.procedure(
                **_compact(
                    {
                        "action": "add_step" if action == "add_procedure_step" else action,
                        **_pick(args, "label", "summary", "target_uid", "props", "agent_id"),
                    }
                )
            )
        )

    if action == "assess_risk":
        return ok(
            client.risk(
                **_compact({"action": "assess", **_pick(args, "label", "summary", "target_uid", "props", "agent_id")})
            )
        )
    if action == "get_assessments":
        return ok(client.risk(**_compact({"action": "get_assessments", **_pick(args, "target_uid", "agent_id")})))

    return err(f"Unknown plan action: {action}")
