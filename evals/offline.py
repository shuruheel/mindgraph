"""A scripted MindGraph for the harness self-test.

It answers each probe with what an ideal memory would return, so a run proves
the runner drives the hooks, waits on receipts and scores correctly. It cannot
say anything about extraction or retrieval quality: nothing here extracts or
retrieves. ``flawed`` makes it answer the way a poor memory would, which is how
the scoring is shown to fail when it should.
"""

from __future__ import annotations

import importlib.util
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

_FAKE = Path(__file__).resolve().parent.parent / "tests" / "support" / "fake_mindgraph.py"


def _fake_class():
    spec = importlib.util.spec_from_file_location("_eval_fake_mindgraph", _FAKE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.FakeMindGraph


def _node(uid: str, label: str, **extra: Any) -> dict[str, Any]:
    return {"uid": uid, "label": label, "node_type": "Decision", "props": {}, **extra}


def _answer(query: str, code: str, flawed: bool) -> list[dict[str, Any]]:
    low = code.lower()
    if "status" in query and "report" in query:
        old = _node("p1", f"{code} status reports as long-form prose", superseded=not flawed, superseded_by="p2")
        return [_node("p2", f"{code} status reports are a five-bullet summary"), old]
    if "budget" in query:
        if flawed:
            return [_node("b1", f"{code} pilot budget is $8,000")]
        return [_node("b2", f"{code} pilot budget is $12,500, corrected from $8,000")]
    if "cache" in query:
        return [_node("c1", f"{code} session cache: Redis, chosen for per-key expiry")]
    if "flexbox" in query or "css" in query:
        return [_node("u1", f"{code} launch pricing for a flexbox child in CSS")] if flawed else [
            _node("u1", f"{code} launch pricing is $49 per seat")
        ]
    if "door" in query:
        return [_node("m1", f"The {code} door code is 4417-ELM")] if flawed else []
    return [_node("x1", f"{low} note")]


@contextmanager
def oracle(*, flawed: bool = False) -> Iterator[Any]:
    server = _fake_class()().start()
    state: dict[str, Any] = {"code": ""}

    def context(body: Any) -> dict[str, Any]:
        query = str((body or {}).get("query") or "")
        found = re.search(r"zephyr[0-9a-f]{6}", query)
        code = f"Zephyr{found.group(0)[6:].upper()}" if found else state["code"]
        return {"graph": {"nodes": _answer(query, code, flawed), "edges": []}, "chunks": [], "articles": []}

    server.context = context
    route = server._route

    def routed(method: str, path: str, body: Any) -> tuple[int, Any]:
        if path == "/memory/forget":
            return 200, {"uid": "mem-1", "action": "forgotten"}
        if path == "/agent/plan" and isinstance(body, dict):
            if body.get("action") == "create_task":
                state["task"] = {"uid": "task-1", "label": body.get("label"), "props": {}}
                return 200, {"uid": "task-1", "label": body.get("label")}
            if body.get("action") == "resume_work":
                task = state.get("task")
                if task and not flawed:
                    return 200, {"status": "selected", "task": task}
                return 200, {"status": "no_eligible_work"}
        return route(method, path, body)

    server._route = routed
    try:
        yield server
    finally:
        server.stop()
