"""Evidence plan R2: the renderer passes the server's own text through."""

from hermes_mindgraph_plugin.render import render_context  # noqa: F401


def test_server_context_text_is_passed_through():
    raw = {
        "context_text": "Legend: …\nAs of: 2024-06-01\n[2024-04-05] Claim — budget is $8,000 [current]",
        "graph": {"nodes": [{"uid": "a", "label": "ignored", "node_type": "Claim"}], "edges": []},
    }
    assert render_context(raw) == raw["context_text"]


def test_server_context_text_respects_the_character_budget():
    raw = {"context_text": "x" * 5000, "graph": {"nodes": [], "edges": []}}
    out = render_context(raw, 1024)
    assert out.startswith("x" * 1024)
    assert "[truncated to 1024 characters]" in out


def test_local_renderer_still_serves_older_servers():
    raw = {"graph": {"nodes": [{"uid": "a", "label": "Pilot budget", "node_type": "Concept", "summary": "a concept"}], "edges": []}}
    assert "Pilot budget" in (render_context(raw) or "")
