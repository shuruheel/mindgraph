"""Actual Hermes CLI with local-only model and MindGraph stand-ins."""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from test_real_host import REPO_ROOT, graph, home, node, server  # noqa: F401

pytestmark = pytest.mark.skipif(
    os.environ.get("HERMES_HOST_TESTS") != "1" or sys.platform != "linux",
    reason="needs the pinned Linux Hermes host; no paid endpoints",
)


def test_cli_sends_no_tools_while_provider_recall_and_capture_remain_active(home, server, tmp_path):  # noqa: F811
    temporary = tempfile.TemporaryDirectory(prefix="mgcli-")
    profile = Path(temporary.name) / "home"
    shutil.copytree(home, profile)
    requests = []
    server.context = graph(node("offline-memory", "VoyaOffline status reports",
                                "Use the amber notebook.", kind="Preference"))

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append({"path": self.path, "body": body})
            item = {"id": "msg_offline", "type": "message", "role": "assistant", "status": "completed",
                    "content": [{"type": "output_text", "text": "Noted.", "annotations": []}]}
            response = {"id": "resp_offline", "object": "response", "created_at": 1,
                        "status": "completed", "model": body.get("model", "offline"), "output": [item],
                        "usage": {"input_tokens": 20, "output_tokens": 3, "total_tokens": 23}}
            assert self.path == "/v1/responses"
            if body.get("stream"):
                events = [
                    {"type": "response.created", "response": {**response, "status": "in_progress", "output": []}},
                    {"type": "response.output_item.added", "output_index": 0, "item": {**item, "status": "in_progress", "content": []}},
                    {"type": "response.content_part.added", "item_id": item["id"], "output_index": 0,
                     "content_index": 0, "part": {"type": "output_text", "text": "", "annotations": []}},
                    {"type": "response.output_text.delta", "item_id": item["id"], "output_index": 0,
                     "content_index": 0, "delta": "Noted."},
                    {"type": "response.output_text.done", "item_id": item["id"], "output_index": 0,
                     "content_index": 0, "text": "Noted."},
                    {"type": "response.output_item.done", "output_index": 0, "item": item},
                    {"type": "response.completed", "response": response},
                ]
                data = "".join("data: " + json.dumps({**event, "sequence_number": i}) + "\n\n"
                               for i, event in enumerate(events)).encode()
                kind = "text/event-stream"
            else:
                data, kind = json.dumps(response).encode(), "application/json"
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    model = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=model.serve_forever, daemon=True)
    thread.start()
    # Preserve the real OpenAI/Responses selection. Hermes deliberately switches
    # arbitrary local custom URLs to Chat Completions, so redirect only transport.
    url = f"http://127.0.0.1:{model.server_port}"
    (profile / "config.yaml").write_text((REPO_ROOT / "evals/capture-only.yaml").read_text())
    shim = Path(temporary.name) / "transport"
    shim.mkdir()
    (shim / "sitecustomize.py").write_text(r"""
import os
import httpx

def redirect(request):
    if request.url.host == "api.openai.com":
        request.url = httpx.URL(os.environ["HERMES_TEST_MODEL_URL"] + request.url.raw_path.decode())
    elif request.url.host not in ("127.0.0.1", "localhost", "::1"):
        raise RuntimeError("Offline host test refuses external HTTP")

original = httpx.Client.send
def send(self, request, *args, **kwargs):
    redirect(request)
    return original(self, request, *args, **kwargs)
httpx.Client.send = send
original_async = httpx.AsyncClient.send
async def send_async(self, request, *args, **kwargs):
    redirect(request)
    return await original_async(self, request, *args, **kwargs)
httpx.AsyncClient.send = send_async
""")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("HERMES_", "MINDGRAPH_")) and not k.endswith(("_API_KEY", "_AUTH_TOKEN"))}
    env.update(HERMES_HOME=str(profile), HERMES_TEST_MODEL_URL=url, OPENAI_API_KEY="sk-offline-host-test",
               PYTHONPATH=str(shim) + os.pathsep + env.get("PYTHONPATH", ""),
               MINDGRAPH_API_KEY="mg_host_test_key", MINDGRAPH_BASE_URL=server.url)
    prompt = "For project VoyaOffline, reports use five bullets. Reply only Noted. Do not use tools."
    try:
        result = subprocess.run([sys.executable, "-m", "hermes_cli.main", "chat", "-q", prompt,
                                 "--quiet", "--max-turns", "1", "--run-budget", "20"],
                                cwd=workspace, env=env, text=True, capture_output=True, timeout=45)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "Noted." in result.stdout
        assert len(requests) == 1, requests
        assert not requests[0]["body"].get("tools"), "model received callable tools"
        assert "amber notebook" in json.dumps(requests[0]["body"]), "recalled context never reached the model"
        deadline = time.monotonic() + 10
        while not server.ingested() and time.monotonic() < deadline:
            time.sleep(0.1)
        (body,) = server.ingested()
        assert [s["role"] for s in json.loads(body["context"])["turn_framing"]["spans"]] == ["user", "assistant"]
        assert server.bodies("/retrieve/context"), "recall must remain active with no tools"
    finally:
        # Stop only descendants carrying this fresh profile, never a user's gateway.
        marker = ("HERMES_HOME=" + str(profile)).encode()
        def owned_processes():
            owned = []
            for process in Path("/proc").iterdir():
                if not process.name.isdigit() or int(process.name) == os.getpid():
                    continue
                try:
                    if marker in (process / "environ").read_bytes().split(b"\0"):
                        owned.append(int(process.name))
                except (FileNotFoundError, ProcessLookupError, PermissionError):
                    pass
            return owned

        # Hermes gateways flush files during SIGTERM. Wait for that shutdown
        # before removing the profile; otherwise rmtree races those writes.
        deadline = time.monotonic() + 5
        while owned := owned_processes():
            for pid in owned:
                try:
                    os.kill(pid, signal.SIGTERM if time.monotonic() < deadline else signal.SIGKILL)
                except ProcessLookupError:
                    pass
            if time.monotonic() > deadline + 5:
                raise AssertionError("owned Hermes processes did not stop")
            time.sleep(0.1)
        model.shutdown()
        model.server_close()
        temporary.cleanup()
