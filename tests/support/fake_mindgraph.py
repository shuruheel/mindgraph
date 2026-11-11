"""A MindGraph API stand-in on a real socket.

The provider talks to it through the real SDK and the real governance client,
so a test exercises the same HTTP path a user's Hermes does. Every request is
recorded. Responses are the server's shapes with the minimum of state: opened
sessions, created ingest jobs, and whatever ``context`` holds.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Optional


class FakeMindGraph:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str, Any]] = []
        # Jobs live in the server's memory and are lost when it restarts;
        # Documents are durable. ``restart()`` models exactly that.
        self.jobs: list[dict[str, Any]] = []
        self.documents: list[dict[str, Any]] = []
        # What /retrieve/context answers; a callable receives the request body.
        self.context: Any = {"graph": {"nodes": [], "edges": []}, "chunks": [], "articles": []}
        self.work: Any = {"status": "no_eligible_work"}
        self.governance: dict[str, Any] = {"decision": "permit"}
        # Per-path scripted failures, consumed in order: an HTTP status, or
        # "drop" to do the work and then close the socket without answering.
        self.failures: dict[str, list[Any]] = {}
        self.delays: dict[str, float] = {}
        self._lock = threading.Lock()
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever, name="fake-mindgraph", daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def start(self) -> "FakeMindGraph":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    # ── Observation ────────────────────────────────────────────────────────

    def bodies(self, path: str) -> list[Any]:
        with self._lock:
            return [body for _, seen, body in self.requests if seen == path]

    def ingested(self) -> list[dict[str, Any]]:
        """Transcripts the server accepted (a failed request created nothing)."""
        with self._lock:
            return [dict(document["request"]) for document in self.documents]

    def restart(self) -> None:
        """A deploy: the in-memory job list is gone, the graph is not."""
        with self._lock:
            self.jobs.clear()

    def wait_for(self, predicate: Callable[[], bool], timeout: float = 10.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return True
            time.sleep(0.02)
        return predicate()

    # ── Routes ─────────────────────────────────────────────────────────────

    def _route(self, method: str, path: str, body: Any) -> tuple[int, Any]:
        if path == "/agent/governance":
            return 200, self.governance
        if path == "/memory/session":
            action = (body or {}).get("action")
            if action == "open":
                return 200, {"uid": f"session-{(body or {}).get('harness_session_id')}"}
            return 200, {}
        if path == "/ingest/session":
            with self._lock:
                number = len(self.documents) + 1
                title = f"Session Transcript: {(body or {}).get('title')}"
                self.documents.append({"uid": f"doc-{number}", "label": title, "request": body})
                job = {"id": f"job-{number}", "title": title, "status": "completed"}
                self.jobs.append(job)
            return 200, {"job_id": job["id"], "document_uid": f"doc-{number}"}
        if path == "/retrieve" and (body or {}).get("action") == "text":
            # Keyword search over Document labels, as the real server's FTS does.
            words = str((body or {}).get("query") or "").lower().split()
            with self._lock:
                return 200, [
                    {"node": {"uid": d["uid"], "label": d["label"], "node_type": "Document"}, "score": 1.0}
                    for d in self.documents
                    if any(word in d["label"].lower() for word in words)
                ]
        if path == "/jobs" and method == "GET":
            with self._lock:
                return 200, [dict(job) for job in self.jobs]
        if path.startswith("/jobs/") and method == "GET":
            with self._lock:
                for job in self.jobs:
                    if job["id"] == path.rsplit("/", 1)[1]:
                        return 200, dict(job)
            return 404, {"error": "job not found", "code": "not_found"}
        if path == "/retrieve/context":
            return 200, self.context(body) if callable(self.context) else self.context
        if path == "/agent/plan":
            return 200, self.work
        if path in ("/memory/remember", "/memory/forget"):
            return 200, {"uid": "mem-1", "action": "created", "searchable": {"bm25": True, "vector": True}}
        return 404, {"error": f"no fake route for {method} {path}", "code": "not_found"}

    def _handler(self) -> type:
        fake = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args: Any) -> None:  # keep test output clean
                pass

            def _serve(self, method: str) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b""
                try:
                    body: Optional[Any] = json.loads(raw) if raw else None
                except ValueError:
                    body = raw.decode(errors="replace")
                path = self.path.split("?", 1)[0]
                with fake._lock:
                    fake.requests.append((method, path, body))
                    scripted = fake.failures.get(path) or []
                    failure = scripted.pop(0) if scripted else None
                    delay = fake.delays.get(path, 0.0)
                if delay:
                    time.sleep(delay)
                if failure == "drop":
                    fake._route(method, path, body)  # the work happens; the answer is lost
                    self.close_connection = True
                    self.connection.close()
                    return
                if isinstance(failure, int):
                    status, payload = failure, {"error": "scripted failure", "code": "scripted"}
                else:
                    status, payload = fake._route(method, path, body)
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self) -> None:  # noqa: N802
                self._serve("GET")

            def do_POST(self) -> None:  # noqa: N802
                self._serve("POST")

        return Handler
