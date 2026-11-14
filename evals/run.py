"""Run the memory outcome suite. See README.md.

    python -m evals.run --offline
    MINDGRAPH_EVAL_API_KEY=mg_... python -m evals.run --report evals/report.json
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sqlite3
import statistics
import sys
import tempfile
import time
from contextlib import nullcontext
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from . import _plugin
from .scenarios import SCENARIOS, Scenario

NOT_CURRENT = ("SUPERSEDED", "truth: refuted", "truth: retracted", "OUTSIDE ITS VALIDITY WINDOW")
TERMINAL = ("completed", "completed_with_errors", "failed", "cancelled")
DEFAULT_BASE_URL = "https://api.mindgraph.cloud"


@dataclass
class Outcome:
    scenario: str
    passed: bool
    failures: list[str] = field(default_factory=list)
    injected_chars: int = 0
    injected_items: int = 0
    irrelevant_items: int = 0
    recall_ms: float = 0.0
    injected: str = ""
    retrieval_outcome: str = "not_requested"


def score(scenario: Scenario, injected: str, code: str) -> Outcome:
    """Judge what was injected for the probe. Pure, so it is unit-tested."""
    fill = lambda text: text.replace("{code}", code)  # noqa: E731
    lines = [line for line in injected.splitlines() if line.strip()]
    items = [line for line in lines if line.lstrip().startswith("- [")]
    # Topic answers must come from this run, not an unrelated resume brief.
    owned = [line for line in items if code.lower() in line.lower()
             or f"eval-{code[6:].lower()}-" in line.lower()]
    evidence = lines if scenario.name == "interrupted_work" else owned
    lowered = "\n".join(evidence).lower()
    failures: list[str] = []
    expected = [fill(phrase) for phrase in scenario.expect]
    # The once-per-conversation open-work brief is not topic recall; only recalled items count.
    if scenario.expect_nothing and items:
        failures.append(f"expected no recalled items for an unrelated message, got {len(items)}")
    for phrase in expected:
        if phrase.lower() not in lowered:
            failures.append(f"missing: {phrase!r}")
    for phrase in map(fill, scenario.stale):
        for line in evidence:
            if phrase.lower() not in line.lower():
                continue
            marked = any(tag in line for tag in NOT_CURRENT)
            corrected = any(want.lower() in line.lower() for want in expected)
            if not (marked or corrected):
                failures.append(f"stale shown as current: {phrase!r} in {line.strip()[:120]!r}")
    for phrase in map(fill, scenario.forbid):
        if phrase.lower() in injected.lower():
            failures.append(f"forbidden text came back: {phrase!r}")
    subject = [fill(term).lower() for term in scenario.subject]
    irrelevant = sum(1 for line in items if not any(term in line.lower() for term in subject))
    return Outcome(
        scenario=scenario.name,
        passed=not failures,
        failures=failures,
        injected_chars=len(injected),
        injected_items=len(items),
        irrelevant_items=irrelevant,
        injected=injected,
    )


class Host:
    """The hook order Hermes's MemoryManager drives, for one conversation."""

    def __init__(self, home: Path, session_id: str, *, task_uid: str = "") -> None:
        plugin = _plugin.load()
        from hermes_mindgraph_plugin.provider import MindGraphMemoryProvider  # noqa: F401

        self.session_id = session_id
        self.provider = plugin.provider.MindGraphMemoryProvider()
        self.provider.initialize(session_id, hermes_home=str(home), platform="eval", task_uid=task_uid)
        self.home = home
        self.mirror_receipts: list[dict[str, Any]] = []
        client = self.provider._rt.client
        for operation in ("remember", "forget"):
            original = getattr(client, operation)

            def observed(*args, _call=original, _operation=operation, **kwargs):
                result = _call(*args, **kwargs)
                self.mirror_receipts.append({"operation": _operation, "result": result})
                return result

            setattr(client, operation, observed)
        self.retrieval_outcome = "not_requested"
        recall = self.provider._recall.recall

        def observe_recall(*args, **kwargs):
            result = recall(*args, **kwargs)
            self.retrieval_outcome = result.outcome
            return result

        self.provider._recall.recall = observe_recall
        self.turns = 0

    def turn(self, user: str, assistant: str) -> None:
        self.turns += 1
        self.provider.on_turn_start(self.turns, user)
        self.provider.prefetch(user, session_id=self.session_id)
        self.provider.sync_turn(user, assistant, session_id=self.session_id)
        self.provider.queue_prefetch(user, session_id=self.session_id)

    def probe(self, message: str) -> tuple[str, float]:
        self.provider.on_turn_start(1, message)
        started = time.perf_counter()
        text = self.provider.prefetch(message, session_id=self.session_id)
        return text, (time.perf_counter() - started) * 1000

    def tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        return json.loads(self.provider.handle_tool_call(name, args))

    def end(self) -> None:
        self.provider.on_session_end([])
        self.provider.shutdown()

    def crash(self) -> None:
        """The process dies: no session end, no flush, no shutdown."""
        if self.provider._capture is not None:
            self.provider._capture.close()


def seed(scenario: Scenario, home: Path, code: str, run: str, problems: list[str],
         deadline: float, receipts: list[dict[str, Any]], task_uids: dict[str, str]) -> int:
    """Play the scenario's conversations; returns the transcript rows synced."""
    rows = 0
    for index, conversation in enumerate(scenario.conversations, start=1):
        host = Host(home, f"eval-{run}-{scenario.name}-{index}")
        crashed = False
        for step in conversation:
            text = step.text.replace("{code}", code)
            if step.kind == "turn":
                host.turn(step.user.replace("{code}", code), step.assistant.replace("{code}", code))
                rows += 2
            elif step.kind == "memory_add":
                host.provider.on_memory_write("add", "memory", text)
                gate = settle(host, deadline)
                remembered = [r["result"] for r in host.mirror_receipts if r["operation"] == "remember"]
                if not gate["ready"] or not remembered or not remembered[-1].get("uid"):
                    problems.append(f"{scenario.name}: memory add was not acknowledged before removal")
                elif not all(remembered[-1].get("searchable", {}).get(k) for k in ("bm25", "vector")):
                    problems.append(f"{scenario.name}: saved memory was not searchable before removal")
            elif step.kind == "memory_remove":
                host.provider.on_memory_write("remove", "memory", "", {"previous_content": text})
                gate = settle(host, deadline)
                forgotten = [r["result"] for r in host.mirror_receipts if r["operation"] == "forget"]
                remembered = [r["result"] for r in host.mirror_receipts if r["operation"] == "remember"]
                if (not gate["ready"] or not forgotten or not remembered
                        or forgotten[-1].get("action") != "forgotten"
                        or forgotten[-1].get("uid") != remembered[-1].get("uid")):
                    problems.append(f"{scenario.name}: matching delete receipt missing")
            elif step.kind == "task":
                result = host.tool("mindgraph_plan", {"action": "create_task", "label": text})
                if "error" in result:
                    problems.append(f"{scenario.name}: create_task failed: {result['error']}")
                else:
                    data = result.get("data", result)
                    uid = data.get("uid") or (data.get("task") or {}).get("uid")
                    if uid:
                        task_uids[scenario.name] = uid
                    else:
                        problems.append(f"{scenario.name}: create_task returned no UID")
            elif step.kind == "crash":
                host.crash()
                crashed = True
        if not crashed:
            host.provider.on_session_end([])
            gate = settle(host, deadline)
            if not gate["ready"]:
                problems.append(f"{scenario.name}: unsettled input: {gate['problems']}")
            receipts.extend(host.mirror_receipts)
            host.provider.shutdown()
        if problems:
            break
    return rows


def queue_report(home: Path) -> dict[str, Any]:
    path = home / "mindgraph" / "capture.db"
    if not path.exists():
        return {"delivered_rows": 0, "jobs": [], "batches": {}}
    db = sqlite3.connect(path)
    try:
        batches = dict(db.execute("SELECT state, COUNT(*) FROM batches GROUP BY state").fetchall())
        delivered = db.execute("SELECT COALESCE(SUM(part_count), 0) FROM batches WHERE state = 'delivered'").fetchone()[0]
        jobs = [row[0] for row in db.execute("SELECT job_id FROM batches WHERE job_id IS NOT NULL").fetchall()]
        missing_jobs = db.execute(
            "SELECT COUNT(*) FROM batches WHERE state = 'delivered' AND job_id IS NULL"
        ).fetchone()[0]
        open_parts = db.execute("SELECT COUNT(*) FROM parts").fetchone()[0]
    finally:
        db.close()
    return {"delivered_rows": int(delivered), "undelivered_rows": int(open_parts), "jobs": jobs, "batches": batches,
            "missing_job_receipts": int(missing_jobs)}


def settle(host: Host, deadline: float) -> dict[str, Any]:
    """Keep the provider alive until delivery, mirrors and all newly found jobs settle.

    This is an input gate, not a recall retry. Failed or missing extraction is
    never a passing negative/deletion result. The deadline is shared by the run.
    """
    started = time.monotonic()
    statuses: dict[str, str] = {}
    while True:
        from hermes_mindgraph_plugin.provider import spawn_context_thread

        if host.provider._capture is not None:
            host.provider._capture.seal()
            host.provider._drain("eval input barrier", force=False, wait_s=0.0)
        host.provider._outbox.kick(spawn_context_thread)
        queue = queue_report(host.home)
        mirror = host.provider._outbox.status()
        for job_id in queue["jobs"]:
            if statuses.get(job_id) in TERMINAL:
                continue
            try:
                job = host.provider._rt.client.get_job(job_id)
                statuses[job_id] = str(job.get("status") or "unknown").lower()
            except Exception as exc:
                statuses[job_id] = f"error: {type(exc).__name__}"
        problems = []
        if queue.get("undelivered_rows", 0) or any(
            n for state, n in queue["batches"].items() if state != "delivered"
        ):
            problems.append("transcript delivery incomplete")
        if mirror.get("pending_operations") != 0 or mirror.get("enqueue_failures"):
            problems.append("memory mirror incomplete")
        if queue.get("missing_job_receipts", 0):
            problems.append("delivered transcript has no extraction receipt")
        if any(status != "completed" for status in statuses.values()):
            problems.append("extraction incomplete or failed")
        # Re-read after polling: receipts can appear while jobs are inspected.
        latest = queue_report(host.home)
        if set(latest["jobs"]) != set(statuses):
            problems.append("new extraction receipts pending")
        if not problems or time.monotonic() >= deadline or any(
            s in TERMINAL and s != "completed" for s in statuses.values()
        ):
            return {"ready": not problems, "problems": problems, "queue": latest,
                    "mirror": mirror, "statuses": statuses,
                    "seconds": round(time.monotonic() - started, 1)}
        time.sleep(min(0.2, max(0, deadline - time.monotonic())))


def run_suite(*, base_url: str, api_key: str, home: Path, wait_s: float, only: Optional[str] = None) -> dict[str, Any]:
    os.environ["MINDGRAPH_API_KEY"] = api_key
    os.environ["MINDGRAPH_BASE_URL"] = base_url
    run = secrets.token_hex(3)
    code = f"Zephyr{run.upper()}"
    scenarios = [s for s in SCENARIOS if only in (None, s.name)]
    problems: list[str] = []
    if not scenarios:
        raise ValueError(f"Unknown scenario: {only}")
    deadline = time.monotonic() + wait_s
    receipts: list[dict[str, Any]] = []
    task_uids: dict[str, str] = {}
    synced = 0
    for scenario in scenarios:
        synced += seed(scenario, home, code, run, problems, deadline, receipts, task_uids)
        if problems:
            break

    # Whatever a crashed conversation left is delivered by the next start.
    recovery = Host(home, f"eval-{run}-recovery")
    gate = settle(recovery, deadline)
    queue = gate["queue"]
    recovery.provider.shutdown()
    if not gate["ready"]:
        problems.extend(gate["problems"])
    if queue["delivered_rows"] != synced or queue.get("undelivered_rows", 0):
        problems.append("not all synced transcript rows were delivered")
    extraction = {"seconds": gate["seconds"], "statuses": gate["statuses"]}

    outcomes: list[Outcome] = []
    for scenario in scenarios:
        if problems:
            outcomes.append(Outcome(scenario=scenario.name, passed=False,
                                    failures=["not measured: input prerequisites failed"]))
            continue
        host = Host(home, f"eval-{run}-{scenario.name}-probe", task_uid=task_uids.get(scenario.name, ""))
        injected, elapsed = host.probe(scenario.probe.replace("{code}", code))
        host.provider.shutdown()
        outcome = score(scenario, injected, code)
        outcome.retrieval_outcome = host.retrieval_outcome
        if host.retrieval_outcome != "success":
            outcome.passed = False
            outcome.failures.append(f"retrieval did not complete successfully: {host.retrieval_outcome}")
        outcome.recall_ms = round(elapsed, 1)
        outcomes.append(outcome)

    latencies = [outcome.recall_ms for outcome in outcomes]
    return {
        "run": run,
        "codename": code,
        "base_url": base_url,
        "passed": sum(outcome.passed for outcome in outcomes),
        "total": len(outcomes),
        "outcomes": [asdict(outcome) for outcome in outcomes],
        "recall_ms": {"p50": round(statistics.median(latencies), 1), "max": max(latencies)} if latencies else {},
        "injected_chars_per_probe": round(statistics.mean(o.injected_chars for o in outcomes), 1) if outcomes else 0,
        "irrelevant_items": sum(outcome.irrelevant_items for outcome in outcomes),
        "capture": {
            "rows_synced": synced,
            "rows_accepted": queue["delivered_rows"],
            "rows_undelivered": queue.get("undelivered_rows", 0),
            "batches": queue["batches"],
        },
        "extraction": extraction,
        "problems": problems,
        "input_ready": not problems,
        "mirror_receipts": receipts,
        "task_uids": task_uids,
    }


def render(report: dict[str, Any]) -> str:
    lines = [
        f"Memory outcome suite — run {report['run']} against {report['base_url']}",
        f"{report['passed']}/{report['total']} scenarios passed",
        "",
        f"{'scenario':<26}{'result':<8}{'items':>6}{'irrel.':>8}{'chars':>7}{'ms':>9}",
    ]
    for outcome in report["outcomes"]:
        lines.append(
            f"{outcome['scenario']:<26}{'pass' if outcome['passed'] else 'FAIL':<8}{outcome['injected_items']:>6}"
            f"{outcome['irrelevant_items']:>8}{outcome['injected_chars']:>7}{outcome['recall_ms']:>9}"
        )
        lines.extend(f"    - {failure}" for failure in outcome["failures"])
    capture, extraction = report["capture"], report["extraction"]
    lines += [
        "",
        f"recall latency: p50 {report['recall_ms'].get('p50')} ms, max {report['recall_ms'].get('max')} ms",
        f"injected per probe: {report['injected_chars_per_probe']} chars "
        f"(~{round(report['injected_chars_per_probe'] / 4)} tokens); irrelevant items: {report['irrelevant_items']}",
        f"capture: {capture['rows_accepted']}/{capture['rows_synced']} transcript rows accepted, "
        f"{capture['rows_undelivered']} undelivered, batches {capture['batches']}",
        f"extraction: {len(extraction['statuses'])} job(s) in {extraction['seconds']} s: "
        f"{sorted(set(extraction['statuses'].values()))}",
    ]
    lines.extend(f"problem: {problem}" for problem in report["problems"])
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--offline", action="store_true", help="harness self-test against a scripted stand-in")
    parser.add_argument("--report", type=Path, help="write the JSON report here")
    parser.add_argument("--only", choices=[s.name for s in SCENARIOS], help="run one scenario by name")
    parser.add_argument("--home", type=Path, help="new persistent profile directory; refuses existing paths")
    parser.add_argument("--wait", type=float, default=600.0, help="seconds to wait for extraction jobs")
    args = parser.parse_args(argv)

    # Live failures retain their durable queue for diagnosis/recovery.
    context = tempfile.TemporaryDirectory(prefix="mindgraph-eval-") if args.offline and not args.home else nullcontext(None)
    with context as scratch:
        home = args.home or Path(scratch or tempfile.mkdtemp(prefix="mindgraph-live-eval-")) / "hermes-home"
        home.mkdir(parents=True, mode=0o700)
        print(f"Profile: {home}", file=sys.stderr)
        if args.offline:
            from .offline import oracle

            with oracle() as server:
                report = run_suite(base_url=server.url, api_key="mg_offline", home=home, wait_s=10.0, only=args.only)
            report["mode"] = "offline harness self-test: not a measurement of memory quality"
        else:
            api_key = os.environ.get("MINDGRAPH_EVAL_API_KEY", "")
            if not api_key:
                print("Set MINDGRAPH_EVAL_API_KEY to a dedicated test org's key, or pass --offline.", file=sys.stderr)
                return 2
            base_url = os.environ.get("MINDGRAPH_EVAL_BASE_URL", DEFAULT_BASE_URL)
            report = run_suite(base_url=base_url, api_key=api_key, home=home, wait_s=args.wait, only=args.only)
            report["mode"] = "live"
        report["profile"] = str(home)
    print(render(report))
    if args.offline:
        print(f"\n({report['mode']})")
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    return 0 if report["passed"] == report["total"] and not report["problems"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
