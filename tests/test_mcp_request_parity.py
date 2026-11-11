"""Cross-door parity: the plugin sends the HTTP requests mindgraph-mcp sends.

``tests/fixtures/mcp_requests.json`` is recorded by ``scripts/gen_mcp_fixtures.mjs``
from the MCP server's own ``handleTool`` (general profile). Each case is replayed
here through ``dispatch.handle_tool`` with a real ``mindgraph.MindGraph`` client on
a mocked transport that answers every request with ``{}``, as the recorder does.
No governance gate is passed, matching the recorder (the MCP gate runs outside
``handleTool``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
import pytest
from hermes_mindgraph_plugin.dispatch import handle_tool
from hermes_mindgraph_plugin.memory_tool import MemoryRuntimeConfig
from hermes_mindgraph_plugin.results import is_error
from hermes_mindgraph_plugin.runtime import Runtime
from mindgraph import MindGraph

FIXTURES = json.loads((Path(__file__).parent / "fixtures" / "mcp_requests.json").read_text(encoding="utf-8"))

# Body keys the MCP sends that Hermes legitimately does not. Each is a claim.
MCP_ONLY_BODY_KEYS = (
    # The MCP's series_query forwards its whole argument object, which includes
    # the harness invocation context its local hook injects. Hermes has no such
    # argument (sync_from_mcp.mjs strips it from every schema); the plugin's
    # Runtime carries session identity instead.
    "invocation_context",
)


def _normalize(body: Any) -> Any:
    if not isinstance(body, dict):
        return body
    return {key: value for key, value in body.items() if key not in MCP_ONLY_BODY_KEYS}


def _replay(case: dict[str, Any]) -> list[dict[str, Any]]:
    sent: list[dict[str, Any]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        url = urlsplit(str(request.url))
        sent.append(
            {
                "method": request.method,
                "path": url.path + (f"?{url.query}" if url.query else ""),
                "body": json.loads(request.content) if request.content else None,
            }
        )
        return httpx.Response(200, json={})

    client = MindGraph(FIXTURES["base_url"], api_key="mg_test", max_retries=0)
    # The SDK builds its own httpx client; swap in one on the mock transport with
    # the same base URL and headers.
    real = client._client
    client._client = httpx.Client(
        base_url=real.base_url, headers=real.headers, transport=httpx.MockTransport(respond)
    )
    real.close()
    context = FIXTURES["invocation_context"]
    rt = Runtime(
        api_key="mg_test",
        base_url=FIXTURES["base_url"],
        agent_id=FIXTURES["agent_id"],
        session_id=context["harnessSessionId"],
        turn_number=int(context["harnessTurnId"]),
        client=client,
    )
    config = MemoryRuntimeConfig(agent_id=FIXTURES["agent_id"])
    # The dispatcher injects agent_id itself, as the MCP's tools/call wrapper does.
    result = handle_tool(rt, None, config, case["tool"], dict(case["args"]))
    assert not is_error(result), result
    return sent


def test_fixtures_cover_the_canonical_calls():
    ids = {case["id"] for case in FIXTURES["cases"]}
    assert {"retrieve_context_default", "retrieve_context_as_of_exhaustive", "retrieve_context_json"} <= ids
    assert all(case["requests"] for case in FIXTURES["cases"])


@pytest.mark.parametrize("case", FIXTURES["cases"], ids=lambda case: case["id"])
def test_plugin_sends_the_mcp_requests(case):
    expected = [{**request, "body": _normalize(request["body"])} for request in case["requests"]]
    assert _replay(case) == expected
