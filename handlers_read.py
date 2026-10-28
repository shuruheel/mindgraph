"""Read-side tool handlers, ported from mindgraph-mcp ``tools.ts``: retrieve,
series_query, ingest, synthesize and ontology.

Each handler takes the provider's ``Runtime`` and the model's arguments (with
``agent_id`` already injected by the dispatcher) and returns the tool's JSON
string. SDK exceptions propagate; the dispatcher turns them into typed errors.

The TS handlers pass objects whose ``undefined`` members ``JSON.stringify`` drops.
Python passes ``None`` through kwargs-style SDK methods (``retrieve``,
``traverse``, ``series``...), so those payloads go through ``_compact`` to send
the same keys the MCP sends.
"""

from __future__ import annotations

from types import ModuleType
from typing import Any

from .results import err, ok, rendered
from .runtime import Runtime


def _render() -> ModuleType:
    # Imported on use, so a render failure surfaces on the rendered path only.
    from . import render

    return render


def _compact(payload: dict[str, Any]) -> dict[str, Any]:
    """Drop absent members, as ``JSON.stringify`` drops ``undefined``."""
    return {key: value for key, value in payload.items() if value is not None}


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


# ── Series ────────────────────────────────────────────────────────────

_SERIES_ACTIONS = ("list_for_entity", "latest", "window", "aggregate")


def handle_series_query(rt: Runtime, args: dict[str, Any]) -> str:
    """Read-only series actions; writes such as ``append`` are refused here."""
    action = args.get("action") if isinstance(args.get("action"), str) else ""
    if action not in _SERIES_ACTIONS:
        return err(f"Unknown series query action: {action}")
    if action == "list_for_entity" and not isinstance(args.get("entity_uid"), str):
        return err("entity_uid is required for action='list_for_entity'")
    if action != "list_for_entity" and not isinstance(args.get("series_uid"), str):
        return err(f"series_uid is required for action='{action}'")
    if action in ("window", "aggregate") and not (
        _is_number(args.get("from")) and _is_number(args.get("to"))
    ):
        return err(f"from and to are required for action='{action}'")
    if action == "aggregate" and not (
        isinstance(args.get("bucket"), str) and isinstance(args.get("agg"), str)
    ):
        return err("bucket and agg are required for action='aggregate'")
    return ok(rt.client.series(**_compact(args)))


# ── Retrieve ──────────────────────────────────────────────────────────

_STRUCTURED_ACTIONS = (
    "active_goals",
    "open_questions",
    "weak_claims",
    "pending_approvals",
    "unresolved_contradictions",
)


def handle_retrieve(rt: Runtime, args: dict[str, Any]) -> str:
    action = args.get("action")
    fmt = args.get("format")
    max_chars = args.get("max_output_chars")
    query = args.get("query")
    start_uid = args.get("start_uid")
    end_uid = args.get("end_uid")
    limit = args.get("limit")
    node_types = args.get("node_types")
    layer = args.get("layer")
    explain = args.get("explain")
    agent_id = args.get("agent_id")
    client = rt.client

    def node_list(title: str, list_limit: Any = None):
        return lambda raw: _render().render_node_list(raw, title, list_limit, max_chars)

    def traversal(raw: Any) -> Any:
        return _render().render_traversal(raw, max_chars)

    def traverse(**payload: Any) -> Any:
        return client.traverse(**_compact(payload))

    if action == "context":
        if not query:
            return err("query is required for context retrieval")
        # Hermes always runs the general profile: the article leg stays on unless
        # the model sets article_limit or include_documents: false.
        article_limit = args.get("article_limit")
        if article_limit is None and args.get("include_documents") is False:
            article_limit = 0
        graph_expansion_limit = args.get("graph_expansion_limit")
        graph_max_depth = args.get("graph_max_depth")
        return rendered(
            fmt,
            client.retrieve_context(
                query,
                node_limit=limit,
                node_types=node_types,
                layer=layer,
                chunk_limit=(limit if limit is not None else 5) if args.get("include_chunks") else 0,
                article_limit=article_limit,
                valid_at=args.get("valid_at"),
                include_graph=args.get("include_graph"),
                graph_expansion_limit=3 if graph_expansion_limit is None else graph_expansion_limit,
                graph_max_depth=2 if graph_max_depth is None else graph_max_depth,
            ),
            lambda raw: _render().render_context(raw, max_chars),
        )

    if action == "text":
        if not query:
            return err("query is required for text search")
        return rendered(
            fmt,
            client.retrieve(**_compact({
                "action": "text", "query": query, "limit": limit, "node_types": node_types,
                "layer": layer, "explain": explain, "agent_id": agent_id,
            })),
            node_list(f"Text search: {query}"),
        )

    if action in ("semantic", "hybrid"):
        if not query:
            return err(f"query is required for {action} search")
        raw = client.retrieve(**_compact({
            "action": action, "query": query, "k": limit, "node_types": node_types,
            "layer": layer, "explain": explain, "agent_id": agent_id,
        }))
        # With explain, hybrid per-leg scoring must survive: raw JSON only.
        render = (
            (lambda _raw: None)
            if action == "hybrid" and explain
            else node_list(f"{action.capitalize()} search: {query}")
        )
        return rendered(fmt, raw, render)

    # Structured queries go through the generic /retrieve dispatch: the SDK's
    # no-argument conveniences silently dropped limit/offset.
    if action in _STRUCTURED_ACTIONS:
        return rendered(
            fmt,
            client.retrieve(**_compact({
                "action": action, "limit": limit, "offset": args.get("offset"), "agent_id": agent_id,
            })),
            node_list(action.replace("_", " "), limit),
        )

    if action == "stale_derivations":
        return rendered(
            fmt,
            client.retrieve(**_compact({
                "action": "stale_derivations", "limit": limit, "offset": args.get("offset"),
            })),
            node_list("stale derivations", limit),
        )

    if action == "preferences":
        # With a query, topic-relevant preferences (the semantic leg bridges low
        # lexical overlap); without one, all preferences, most salient first.
        payload: dict[str, Any] = {"action": "preferences"}
        if query:
            payload.update(query=query, k=limit)
        payload.update(limit=limit, agent_id=agent_id)
        return rendered(fmt, client.retrieve(**_compact(payload)), node_list("Preferences", limit))

    if action == "layer":
        if not layer:
            return err("layer is required for layer retrieval")
        return rendered(
            fmt,
            client.retrieve(**_compact({
                "action": "layer", "layer": layer, "limit": limit, "node_types": node_types,
                "agent_id": agent_id,
            })),
            node_list(f"Layer: {layer}", limit),
        )

    if action == "recent":
        return rendered(
            fmt,
            client.retrieve(**_compact({
                "action": "recent", "limit": limit, "node_types": node_types,
                "confidence_min": args.get("confidence_min"), "salience_min": args.get("salience_min"),
                "created_after": args.get("created_after"), "created_before": args.get("created_before"),
                "agent_id": agent_id,
            })),
            node_list("Recently ingested", limit),
        )

    if action == "document_index":
        return rendered(
            fmt,
            client.get_nodes(node_type="Document", limit=100 if limit is None else limit),
            node_list("Ingested documents"),
        )

    common = {
        "max_depth": args.get("max_depth"),
        "exclude_edge_types": args.get("exclude_edge_types"),
        "include_provenance": args.get("include_provenance"),
        "max_nodes": args.get("max_nodes"),
    }
    directed = {"direction": args.get("direction"), "edge_types": args.get("edge_types")}

    if action == "chain":
        if not start_uid:
            return err("start_uid is required for chain traversal")
        return rendered(fmt, traverse(action="chain", start_uid=start_uid, **common), traversal)

    if action in ("neighborhood", "subgraph"):
        if not start_uid:
            return err(f"start_uid is required for {action} traversal")
        return rendered(
            fmt, traverse(action=action, start_uid=start_uid, **directed, **common), traversal
        )

    if action == "path":
        if not start_uid:
            return err("start_uid is required for path traversal")
        if not end_uid:
            return err("end_uid is required for path traversal")
        return rendered(
            fmt,
            traverse(action="path", start_uid=start_uid, end_uid=end_uid, **directed, **common),
            traversal,
        )

    if action == "top_k_paths":
        if not start_uid:
            return err("start_uid is required for top_k_paths")
        if not end_uid:
            return err("end_uid is required for top_k_paths")
        return rendered(
            fmt,
            traverse(
                action="top_k_paths", start_uid=start_uid, end_uid=end_uid, k=args.get("k"),
                max_hops=args.get("max_depth"), max_cost=args.get("max_cost"),
                edge_types=args.get("edge_types"), exclude_edge_types=args.get("exclude_edge_types"),
            ),
            traversal,
        )

    return err(f"Unknown retrieve action: {action}")


# ── Ingest ────────────────────────────────────────────────────────────


def handle_ingest(rt: Runtime, args: dict[str, Any]) -> str:
    action = args.get("action")
    content = args.get("content")
    title = args.get("title")
    layers = args.get("layers")
    schema_id = args.get("ontology_schema_id")
    agent_id = args.get("agent_id")
    client = rt.client

    # "ontology" is a targeting flag, not a cognitive layer. The server strips it
    # and returns an empty extraction when the list empties, so forwarding it raw
    # produced a green job over an empty graph (MCP C15).
    targets_ontology = isinstance(layers, list) and "ontology" in layers
    cognitive = [layer for layer in layers if layer != "ontology"] if targets_ontology else layers
    if targets_ontology and not schema_id:
        return err(
            "layers included 'ontology' but no ontology_schema_id was supplied. "
            "Typed Layer-7 extraction is driven by ontology_schema_id, not by the "
            "layers list — pass the schema id, or drop 'ontology' from layers."
        )
    # Omit an emptied list (not []) so the server does not fall back to its
    # per-document-type cognitive defaults; ontology_only says why.
    forwarded = None if isinstance(cognitive, list) and not cognitive else cognitive
    ontology_only = targets_ontology and forwarded is None

    shared = {
        "layers": forwarded,
        "ontology_schema_id": schema_id,
        "participants": args.get("participants"),
        "occurred_at": args.get("occurred_at"),
        "context": args.get("context"),
        "chunk_size": args.get("chunk_size"),
        "chunk_overlap": args.get("chunk_overlap"),
        "agent_id": agent_id,
    }

    if action == "chunk":
        if not content:
            return err("content is required for chunk ingestion")
        # /ingest/chunk runs its ontology pass inline from ontology_schema_id
        # alone and has no ontology_only switch.
        return ok(client.ingest_chunk(
            content, label=title, document_uid=args.get("document_uid"),
            chunk_index=args.get("chunk_index"), layers=forwarded, agent_id=agent_id,
            ontology_schema_id=schema_id,
        ))

    if action == "document":
        if not content:
            return err("content is required for document ingestion")
        fields = {
            "title": title,
            "source_uri": args.get("source_uri") or args.get("source"),  # deprecated alias
            "content_type": args.get("content_type"),
            "document_type": args.get("document_type"),
            **shared,
        }
        if ontology_only:
            return ok(_ingest_ontology_only(client, "/ingest/document", content, fields))
        return ok(client.ingest_document(content, **fields))

    if action == "session":
        if not content:
            return err("content is required for session ingestion")
        fields = {"title": title, **shared}
        if ontology_only:
            return ok(_ingest_ontology_only(client, "/ingest/session", content, fields))
        return ok(client.ingest_session(content, **fields))

    if action == "job_status":
        job_id = args.get("job_id")
        if job_id:
            return ok(client.get_job(job_id))
        # The bare list was unbounded raw JSON of every job; render it
        # newest-first and capped (format:"json" returns the full raw list).
        return rendered(args.get("format"), client.list_jobs(), lambda raw: _render().render_jobs(raw))

    return err(f"Unknown ingest action: {action}")


def _ingest_ontology_only(client: Any, path: str, content: str, fields: dict[str, Any]) -> Any:
    """mindgraph-sdk 0.16 ``ingest_document``/``ingest_session`` have no
    ``ontology_only`` parameter, so this one request is built here; the body keys
    match what the SDK methods send."""
    body = {"content": content, **_compact(fields), "ontology_only": True}
    return client._request("POST", path, body)


# ── Synthesize ────────────────────────────────────────────────────────


def handle_synthesize(rt: Runtime, args: dict[str, Any]) -> str:
    action = args.get("action")
    project_uid = args.get("project_uid")
    client = rt.client

    if action == "signals":
        if not project_uid:
            return err("project_uid is required for action='signals'")
        return rendered(
            args.get("format"),
            client.signals(project_uid, signals=args.get("signals"), target_types=args.get("target_types")),
            lambda raw: _render().render_signals(raw),
        )

    if action == "run":
        if not project_uid:
            return err("project_uid is required for action='run'")
        return ok(client.run_synthesis(project_uid))

    if action == "job_status":
        job_id = args.get("job_id")
        if not job_id:
            return err("job_id is required for action='job_status'")
        return ok(client.get_job(job_id))

    return err(f"Unknown synthesize action: {action}")


# ── Ontology (Layer 7) ────────────────────────────────────────────────


def handle_ontology(rt: Runtime, args: dict[str, Any]) -> str:
    action = args.get("action")
    fmt = args.get("format")
    schema_id = args.get("schema_id")
    query = args.get("query")
    object_type = args.get("object_type")
    uid = args.get("uid")
    proposal_id = args.get("proposal_id")
    limit = args.get("limit")
    client = rt.client

    if action == "schemas":
        return ok(client.list_ontology_schemas())

    if action == "schema":
        if not schema_id:
            return err("schema_id is required for action='schema'")
        return ok(client.get_ontology_schema(schema_id))

    if action == "query":
        if not query:
            return err("query is required for action='query'")
        if not schema_id:
            return err(
                "schema_id is required for action='query' (use action='schemas' to find the active schema)"
            )
        include_cognitive = args.get("include_cognitive_context")
        include_sources = args.get("include_sources")
        return rendered(
            fmt,
            client.query_ontology(query=query, schema_id=schema_id, **_compact({
                "object_types": args.get("object_types"),
                "include_cognitive_context": True if include_cognitive is None else include_cognitive,
                "include_sources": True if include_sources is None else include_sources,
                "depth": args.get("depth"),
                "limit": limit,
            })),
            lambda raw: _render().render_ontology_answer(raw),
        )

    if action == "search":
        if not query:
            return err("query is required for action='search'")
        return rendered(
            fmt,
            client.search_domain_objects(query, **_compact({
                "schema_id": schema_id, "object_types": args.get("object_types"), "limit": limit,
            })),
            lambda raw: _render().render_object_list(raw, f"Domain search: {query}"),
        )

    if action == "objects":
        if not schema_id:
            return err("schema_id is required for action='objects'")
        title = f"Domain objects: {object_type}" if object_type else "Domain objects"
        return rendered(
            fmt,
            client.list_domain_objects(schema_id=schema_id, object_type=object_type, limit=limit),
            lambda raw: _render().render_object_list(raw, title),
        )

    if action == "object":
        if not uid:
            return err("uid is required for action='object'")
        return rendered(
            fmt,
            client.get_domain_object(uid),
            lambda raw: _render().render_node_list([raw], "Domain object"),
        )

    if action == "object_context":
        if not uid:
            return err("uid is required for action='object_context'")
        depth = args.get("depth")
        raw = client.get_domain_object_context(uid) if depth is None else client.get_domain_object_context(uid, depth=depth)
        return rendered(fmt, raw, lambda value: _render().render_ontology_answer(value))

    if action == "proposals":
        status = args.get("status")
        return ok(client.list_ontology_proposals(
            status="pending" if status is None else status, schema_id=schema_id,
            object_type=object_type, limit=limit,
        ))

    if action == "proposal":
        if not proposal_id:
            return err("proposal_id is required for action='proposal'")
        return ok(client.get_ontology_proposal(proposal_id))

    if action == "approve":
        if not proposal_id:
            return err("proposal_id is required for action='approve'")
        return ok(client.approve_ontology_proposal(proposal_id, feedback=args.get("feedback")))

    if action == "reject":
        if not proposal_id:
            return err("proposal_id is required for action='reject'")
        return ok(client.reject_ontology_proposal(proposal_id, args.get("reason")))

    if action == "link":
        from_uid, to_uid, relation_type = args.get("from_uid"), args.get("to_uid"), args.get("relation_type")
        if not from_uid or not to_uid or not relation_type:
            return err("from_uid, to_uid, and relation_type are required for action='link'")
        return ok(client.link_domain_objects(
            from_uid=from_uid, to_uid=to_uid, relation_type=relation_type,
            **_compact({"fields": args.get("fields"), "agent_id": args.get("agent_id")}),
        ))

    if action == "extract":
        if not schema_id:
            return err("schema_id is required for action='extract'")
        source_uids = args.get("source_uids")
        if not source_uids:
            return err("source_uids is required for action='extract'")
        return ok(client.extract_ontology(ontology_schema_id=schema_id, source_uids=source_uids))

    return err(f"Unknown ontology action: {action}")
