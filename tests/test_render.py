"""Renderer contract, ported from mindgraph-mcp test/render.test.ts and
render-extension.test.ts (renderer cases; dispatch cases live with the handlers)."""

from __future__ import annotations

import json
import re

import pytest

from hermes_mindgraph_plugin.render import (
    render_context,
    render_jobs,
    render_node_list,
    render_object_list,
    render_ontology_answer,
    render_signals,
    render_traversal,
)


def specimen() -> dict:
    """Modeled on a live prod retrieve-context response (2026-07-30)."""
    return {
        "graph": {
            "nodes": [
                {
                    "uid": "entity-1",
                    "label": "MindGraph",
                    "node_type": "Entity",
                    "confidence": 0.9,
                    "summary": "Semantic graph memory platform",
                    "props": {"canonical_name": "MindGraph", "attributes": None, "identifiers": None},
                    "source_documents": [{"uid": "doc-1", "title": "Strategy Transcript"}],
                    "source_chunks": [
                        {
                            "chunk_uid": f"chunk-{i}",
                            "char_start": i * 100,
                            "char_end": i * 100 + 99,
                            "page_start": None,
                            "page_end": None,
                            "quote": "MindGraph lets AI systems reason over knowledge" if i == 3 else None,
                            "anchor": None,
                        }
                        for i in range(20)
                    ],
                },
                {
                    "uid": "claim-1",
                    "label": "MindGraph improves institutional thinking",
                    "node_type": "Claim",
                    "confidence": 0.76,
                    "summary": "Better representations improve decisions",
                    "truth_status": "unknown. accepted",
                    "props": {"content": "Processing knowledge improves thinking.", "truth_status": "unknown. accepted"},
                    "believed_by": [{"agent_uid": "agent-1", "agent_label": "Shan", "confidence": 0.8}],
                },
                {
                    "uid": "obs-old",
                    "label": "MindGraph current product description (2026)",
                    "node_type": "Observation",
                    "confidence": 1,
                    "summary": "Old description",
                    "superseded": True,
                    "superseded_by": "obs-new",
                    "props": {},
                },
                {
                    "uid": "obs-new",
                    "label": "MindGraph built on mnestic engine",
                    "node_type": "Observation",
                    "confidence": 0.95,
                    "summary": "Current architecture relationship",
                    "props": {},
                },
                {
                    "uid": "custom-1",
                    "label": "ACME row",
                    "node_type": "Custom",
                    "confidence": 1,
                    "props": {"fields": {"region": "EMEA", "arr": 120000, "empty": None}},
                },
                {
                    "uid": "expanded-1",
                    "label": "Expanded neighbor",
                    "node_type": "Observation",
                    "confidence": 1,
                    "summary": "Came from graph expansion",
                    "props": {},
                    "retrieval_origin": "graph_expansion",
                    "retrieval_path_cost": 0.69,
                    "retrieval_depth": 1,
                    "retrieval_parent_uid": "entity-1",
                },
                {"uid": "chunk-node", "label": "raw chunk", "node_type": "Chunk", "props": {}},
            ],
            "edges": [
                {"uid": "e1", "edge_type": "ABOUT", "from_uid": "claim-1", "to_uid": "entity-1", "props": {}},
                {"uid": "e2", "edge_type": "ABOUT", "from_uid": "claim-1", "to_uid": "claim-1", "props": {}},
                {
                    "uid": "e3",
                    "edge_type": "POSSIBLE_DUPLICATE",
                    "from_uid": "obs-old",
                    "to_uid": "obs-new",
                    "props": {"similarity": 0.82, "method": "llm", "rationale": "LLM review: related but distinct"},
                },
                {"uid": "e4", "edge_type": "SUPERSEDES", "from_uid": "obs-new", "to_uid": "obs-old", "props": {}},
            ],
        },
        "articles": [
            {"uid": "article-1", "label": "MindGraph Overview", "content": "Compiled article body.", "article_type": "entity"}
        ],
        "chunks": [
            {
                "chunk_uid": "chunk-3",
                "content": "Full chunk text for citation.",
                "score": 0.8,
                "document_uid": "doc-1",
                "document_title": "Strategy Transcript",
                "chunk_index": 3,
            }
        ],
    }


def is_json(text: str) -> bool:
    try:
        json.loads(text)
    except ValueError:
        return False
    return True


class TestRenderContext:
    def test_keeps_signal_and_drops_wire_noise(self):
        text = render_context(specimen())
        assert "**MindGraph** [entity-1] (Entity, confidence 0.9)" in text
        assert "Semantic graph memory platform" in text
        assert 'source quote: "MindGraph lets AI systems reason over knowledge"' in text
        assert "from: Strategy Transcript" in text
        assert "believed by: Shan (0.8)" in text
        assert "### Claim" in text
        assert "[truth: unknown. accepted]" in text
        assert "[SUPERSEDED by obs-new]" in text
        assert "fields: region: EMEA; arr: 120000" in text
        assert "## Knowledge articles" in text
        assert "Compiled article body." in text
        assert 'from "Strategy Transcript": "Full chunk text for citation."' in text
        assert "MindGraph improves institutional thinking —ABOUT→ MindGraph" in text
        assert "POSSIBLE_DUPLICATE" not in text
        assert "LLM review" not in text
        assert not re.search(r"—ABOUT→ MindGraph improves institutional thinking", text)
        for noise in ("char_start", "chunk-7", "retrieval_path_cost", "tombstone", "raw chunk"):
            assert noise not in text

    def test_integer_confidence_renders_like_javascript(self):
        assert "(Observation, confidence 1)" in render_context(specimen())

    def test_is_much_smaller_than_pretty_json(self):
        assert len(render_context(specimen())) < len(json.dumps(specimen(), indent=2)) / 3

    def test_empty_case_is_prose(self):
        assert render_context({"graph": {"nodes": [], "edges": []}}) == "No results found for this search."

    def test_bounds_oversized_content_with_truthful_marker(self):
        big = specimen()
        big["articles"] = [
            {"uid": f"article-{i}", "label": f"Article {i}", "content": "x" * 8_000, "article_type": "entity"}
            for i in range(30)
        ]
        text = render_context(big)
        assert len(text) < 26_000
        assert "[rendered context bounded" in text
        assert "x" * 6_100 not in text

    def test_later_small_section_survives_oversized_earlier_one(self):
        big = {
            "graph": {
                "nodes": [
                    {
                        "uid": f"node-{i}",
                        "label": f"{'L' * 170} {i}",
                        "node_type": "Observation",
                        "props": {"content": "s" * 390},
                    }
                    for i in range(60)
                ],
                "edges": [],
            },
            "chunks": [
                {
                    "chunk_uid": "chunk-final",
                    "content": "small excerpt",
                    "score": 1,
                    "document_uid": "d",
                    "document_title": "Doc",
                    "chunk_index": 0,
                }
            ],
        }
        assert "chunk-final" in render_context(big)

    def test_policy_prose_rules_render_joined(self):
        text = render_context(
            {
                "graph": {"nodes": [{"uid": "n1", "label": "X", "node_type": "Entity", "props": {}}], "edges": []},
                "applicable_policies": [
                    {"uid": "p1", "name": "Data policy", "prose_rules": ["Never expose PII", "Log all access"]}
                ],
            }
        )
        assert "- Data policy: Never expose PII; Log all access" in text

    def test_hidden_count_and_policies_render_on_empty_graph(self):
        text = render_context(
            {
                "graph": {"nodes": [], "edges": []},
                "hidden_item_count": "1-9",
                "applicable_policies": [{"uid": "p1", "name": "Scope policy", "prose_rules": ["Stay in project"]}],
            }
        )
        assert "No graph results matched this search." in text
        assert "hidden by access scoping" in text
        assert "Scope policy" in text

    def test_infra_only_matches_explain_themselves(self):
        text = render_context(
            {"graph": {"nodes": [{"uid": "d1", "label": "Some Doc", "node_type": "Document", "props": {}}], "edges": []}}
        )
        assert "document/chunk node(s) matched" in text

    def test_max_chars_is_a_hard_bound(self):
        nodes = [
            {"uid": f"n{i}", "label": f"Node {i} {'description ' * 12}", "node_type": "Observation", "props": {}}
            for i in range(20)
        ]
        text = render_context({"graph": {"nodes": nodes, "edges": []}}, 700)
        assert len(text) <= 700
        assert "bounded to 700 chars" in text


class TestRenderNodeList:
    def test_bare_node_arrays(self):
        text = render_node_list(
            [
                {"uid": "goal-1", "label": "Land 3 design partners", "node_type": "Goal", "confidence": 0.9, "props": {}},
                {"uid": "goal-2", "label": "Ship 0.16", "node_type": "Goal", "props": {}},
            ],
            "active goals",
        )
        assert "# active goals (2)" in text
        assert "**Land 3 design partners** [goal-1]" in text

    def test_nothing_node_shaped_returns_none(self):
        assert render_node_list({"pairs": [{"claim_a": "x", "claim_b": "y"}]}, "contradictions") is None
        assert render_node_list({"count": 3}, "counts") is None

    def test_unwraps_search_results_with_rounded_scores(self):
        wire = [
            {"node": {"uid": "n1", "label": "MindGraph", "node_type": "Entity", "confidence": 1, "props": {}}, "score": 0.874},
            {"node": {"uid": "n2", "label": "Claim about memory", "node_type": "Claim", "props": {}}, "score": 0.61},
        ]
        text = render_node_list(wire, "Hybrid search: mindgraph")
        assert "**MindGraph** [n1] (Entity, confidence 1, score 0.87)" in text
        assert "**Claim about memory** [n2]" in text

    def test_oversized_section_packs_item_wise(self):
        nodes = [
            {"uid": f"node-{i}", "label": f"{'L' * 170} {i}", "node_type": "Observation", "props": {"content": "s" * 390}}
            for i in range(50)
        ]
        text = render_node_list(nodes, "Recently ingested")
        assert "[node-0]" in text
        assert re.search(r"\(\+\d+ more not shown\)", text)
        assert len(text) < 26_000

    def test_caps_at_caller_limit(self):
        nodes = [{"uid": f"goal-{i}", "label": f"Goal {i}", "node_type": "Goal", "props": {}} for i in range(30)]
        text = render_node_list(nodes, "active goals", 5)
        assert "# active goals (5 of 30)" in text
        assert "goal-7" not in text

    def test_serde_tagged_custom_nodes(self):
        text = render_node_list(
            [
                {
                    "uid": "c1",
                    "label": "ACME",
                    "node_type": {"Custom": "Customer"},
                    "props": {
                        "_type": "Custom",
                        "type_name": "Customer",
                        "layer": "ontology",
                        "data": {"domain_type": "Customer", "fields": {"region": "EMEA", "arr": 5}},
                    },
                }
            ],
            "objects",
        )
        assert "### Customer" in text
        assert "### Node" not in text
        assert "fields: region: EMEA; arr: 5" in text


class TestRenderTraversal:
    def test_nodes_relationships_and_paths(self):
        text = render_traversal(
            {
                "paths": [
                    {"nodes": [{"uid": "a", "label": "Start"}, {"uid": "b", "label": "End"}], "path_cost": 1.4, "path_confidence": 0.7}
                ],
                "nodes": [
                    {"uid": "a", "label": "Start", "node_type": "Entity", "props": {}},
                    {"uid": "b", "label": "End", "node_type": "Entity", "props": {}},
                ],
                "edges": [{"uid": "e", "edge_type": "RELATES_TO", "from_uid": "a", "to_uid": "b", "props": {}}],
            }
        )
        assert "1. Start → End (cost 1.4, confidence 0.7)" in text
        assert "Start —RELATES_TO→ End" in text

    def test_unrecognized_shape(self):
        assert render_traversal({"something": True}) is None

    def test_live_path_step_wire_shape(self):
        text = render_traversal(
            {
                "mode": "neighborhood",
                "start_uid": "decision-uid",
                "steps": [
                    {
                        "depth": 1,
                        "edge_from_uid": "decision-uid",
                        "edge_to_uid": "evidence-uid",
                        "edge_type": {"Custom": "SUPPORTED_BY"},
                        "edge_uid": "edge-uid",
                        "label": "benchmark p99_latency_ms=180",
                        "node_type": "Observation",
                        "node_uid": "evidence-uid",
                        "parent_uid": "decision-uid",
                        "path_confidence": 1,
                        "path_cost": 0.6931471824645996,
                        "traversal_role": "outgoing",
                    }
                ],
            }
        )
        assert "# Graph traversal (neighborhood)" in text
        assert "depth 1 outgoing —SUPPORTED_BY→" in text
        assert "**benchmark p99_latency_ms=180** [evidence-uid]" in text
        assert "parent decision-uid" in text
        assert "cost 0.6931471824645996" in text
        assert '"Custom"' not in text

    @pytest.mark.parametrize("mode", ["chain", "path", "subgraph"])
    def test_other_modes_render(self, mode):
        text = render_traversal(
            {
                "mode": mode,
                "start_uid": "start-uid",
                "end_uid": "end-uid" if mode == "path" else None,
                "steps": [
                    {
                        "depth": 1,
                        "edge_from_uid": "start-uid",
                        "edge_to_uid": "end-uid",
                        "edge_type": "DependsOn",
                        "label": "End node",
                        "node_type": "Entity",
                        "node_uid": "end-uid",
                        "parent_uid": "start-uid",
                        "path_confidence": 0.9,
                        "path_cost": 0.2,
                        "traversal_role": "outgoing",
                    }
                ],
            }
        )
        assert f"# Graph traversal ({mode})" in text
        assert "depth 1 outgoing —DependsOn→" in text
        assert "**End node** [end-uid]" in text
        assert not is_json(text)

    def test_custom_edge_types_in_node_edge_responses(self):
        text = render_traversal(
            {
                "nodes": [
                    {"uid": "a", "label": "Start", "node_type": "Entity", "props": {}},
                    {"uid": "b", "label": "End", "node_type": "Entity", "props": {}},
                ],
                "edges": [{"uid": "edge-1", "edge_type": {"Custom": "SUPPORTED_BY"}, "from_uid": "a", "to_uid": "b", "props": {}}],
            }
        )
        assert "Start —SUPPORTED_BY→ End" in text
        assert "—?→" not in text

    def test_empty_path_is_a_result(self):
        text = render_traversal({"mode": "path", "start_uid": "a", "end_uid": "z", "steps": None})
        assert "No path found from [a] to [z]." in text

    def test_hard_budget_reports_omitted_steps(self):
        steps = [
            {
                "depth": i + 1,
                "edge_from_uid": f"node-{i}",
                "edge_to_uid": f"node-{i + 1}",
                "edge_type": {"Custom": "DEPENDS_ON"},
                "label": f"Dependency {i} {'detail ' * 8}",
                "node_type": "Observation",
                "node_uid": f"node-{i + 1}",
                "parent_uid": f"node-{i}",
                "traversal_role": "outgoing",
            }
            for i in range(30)
        ]
        text = render_traversal({"mode": "neighborhood", "start_uid": "node-0", "steps": steps}, 700)
        assert len(text) <= 700
        assert "rendered context bounded to 700 chars" in text
        assert re.search(r"\d+ item\(s\) omitted", text)

    def test_top_k_paths_wire(self):
        text = render_traversal(
            {
                "mode": "top_k_paths",
                "start_uid": "a",
                "end_uid": "c",
                "k": 2,
                "paths": [
                    {"node_uids": ["a", "b", "c"], "labels": ["Start", "Middle", "End"], "cost": 1.39},
                    {"node_uids": ["a", "c"], "labels": ["Start", "End"], "cost": 2.1},
                ],
            }
        )
        assert "1. Start → Middle → End (cost 1.39)" in text
        assert "uids: a → b → c" in text
        assert "2. Start → End (cost 2.1)" in text

    def test_excludes_pascal_case_possible_duplicate(self):
        text = render_traversal(
            {
                "nodes": [
                    {"uid": "a", "label": "Old obs", "node_type": "Observation", "props": {}},
                    {"uid": "b", "label": "New obs", "node_type": "Observation", "props": {}},
                ],
                "edges": [
                    {"uid": "e1", "edge_type": "PossibleDuplicate", "from_uid": "a", "to_uid": "b", "props": {}},
                    {"uid": "e2", "edge_type": "Supersedes", "from_uid": "b", "to_uid": "a", "props": {}},
                ],
            }
        )
        assert "PossibleDuplicate" not in text
        assert "New obs —Supersedes→ Old obs" in text


ONTOLOGY_RESPONSE = {
    "objects": [
        {
            "uid": "cust-1",
            "label": "ACME Corp",
            "node_type": "Custom",
            "confidence": 1,
            "props": {"object_type": "Customer", "fields": {"region": "EMEA", "arr": 120000}},
        }
    ],
    "relations": [
        {"edge_uid": "r1", "from_uid": "cust-1", "to_uid": "req-1", "edge_type": "HAS_REQUIREMENT", "traversal_role": "outgoing", "depth": 1}
    ],
    "cognitive_context": {
        "claims": [{"uid": "claim-1", "label": "ACME renewal is at risk", "node_type": "Claim", "layer": "epistemic", "depth": 1}],
        "risks": [],
    },
    "external_refs": [],
    "graph": {"nodes": [{"uid": "req-1", "label": "SSO requirement", "node_type": "Custom", "layer": "ontology", "depth": 1}], "edges": []},
    "provenance": [
        {"node_uid": "cust-1", "source_uid": "doc-1", "text_span": "ACME signed the enterprise contract", "span_kind": "anchor", "ingested_by_name": "Shan"},
        {"node_uid": "cust-1", "source_uid": "doc-2", "text_span": "Meeting notes from Q2 review covering multiple accounts", "span_kind": "chunk_head"},
    ],
    "confidence": {"overall": 0.82},
    "returned_count": 1,
    "has_more": False,
    "seed_cap_hit": False,
}


class TestRenderOntology:
    def test_objects_relations_context_confidence(self):
        text = render_ontology_answer(ONTOLOGY_RESPONSE)
        assert "### Customer" in text
        assert "**ACME Corp** [cust-1] (Customer, confidence 1)" in text
        assert "fields: region: EMEA; arr: 120000" in text
        assert "ACME Corp —HAS_REQUIREMENT→ SSO requirement" in text
        assert "### Cognitive context — claims" in text
        assert "ACME renewal is at risk [claim-1] (Claim)" in text
        assert "overall confidence 0.82" in text

    def test_c10_anchor_quotes_chunk_head_never_quoted(self):
        text = render_ontology_answer(ONTOLOGY_RESPONSE)
        assert '- "ACME signed the enterprise contract" (ingested by Shan) [source doc-1]' in text
        assert "- context: Meeting notes from Q2 review" in text
        assert '"Meeting notes' not in text

    def test_unknown_shape(self):
        assert render_ontology_answer({"something": True}) is None

    def test_recognized_empty_result(self):
        empty = {
            "objects": [], "relations": [], "cognitive_context": {}, "external_refs": [],
            "graph": {"nodes": [], "edges": []}, "provenance": [], "confidence": {"overall": 0},
            "returned_count": 0, "has_more": False, "seed_cap_hit": False,
        }
        assert render_ontology_answer(empty) == "No matching domain objects."

    def test_object_context_relations_use_cognitive_labels_and_uid_fallback(self):
        text = render_ontology_answer(
            {
                "object": {"uid": "cust-1", "label": "ACME", "node_type": {"Custom": "Customer"}, "props": {"_type": "Custom", "type_name": "Customer", "data": {}}},
                "relations": [
                    {"edge_uid": "e1", "from_uid": "claim-1", "to_uid": "cust-1", "edge_type": "ABOUT", "traversal_role": "incoming", "depth": 1},
                    {"edge_uid": "e2", "from_uid": "cust-1", "to_uid": "mystery-9", "edge_type": "HAS_REQUIREMENT", "traversal_role": "outgoing", "depth": 1},
                ],
                "cognitive_context": {
                    "claims": [{"uid": "claim-1", "label": "ACME renewal at risk", "node_type": "Claim", "layer": "epistemic", "depth": 1}]
                },
                "sources": [],
                "provenance": [],
            }
        )
        assert "ACME renewal at risk —ABOUT→ ACME" in text
        assert "ACME —HAS_REQUIREMENT→ [mystery-9]" in text


class TestRenderObjectList:
    def test_items_totals_and_truncation(self):
        text = render_object_list(
            {
                "items": [
                    {"object": {"uid": "c1", "label": "ACME", "node_type": {"Custom": "Customer"}, "props": {"_type": "Custom", "type_name": "Customer", "data": {"fields": {"region": "EMEA"}}}}, "score": 0.9},
                    {"object": {"uid": "c2", "label": "Globex", "node_type": {"Custom": "Customer"}, "props": {"_type": "Custom", "type_name": "Customer", "data": {}}}, "score": 0.7},
                ],
                "returned_count": 2,
                "total_count": 41,
                "total_count_exact": True,
                "has_more": True,
                "truncation_reasons": ["seed_cap"],
            },
            "Customer search: corp",
        )
        assert "# Customer search: corp (2 of 41)" in text
        assert "### Customer" in text
        assert "**ACME** [c1] (Customer, score 0.9)" in text
        assert "fields: region: EMEA" in text
        assert "more results exist" in text
        assert "truncated: seed_cap" in text

    def test_empty_page_and_unknown_shapes(self):
        assert render_object_list({"items": [], "has_more": False}, "Customers") == "# Customers (0 results)"
        assert render_object_list({"rows": [[1, 2]]}, "structured") is None

    def test_related_structured_rows(self):
        text = render_object_list(
            {
                "plan": {},
                "rows": [{"object": {"uid": "r1", "label": "SSO requirement", "node_type": {"Custom": "Requirement"}, "props": {"_type": "Custom", "type_name": "Requirement", "data": {}}}}],
                "relations": [],
                "provenance": [],
                "total_count": 1,
            },
            "Requirement related via HAS_REQUIREMENT",
        )
        assert "**SSO requirement** [r1] (Requirement)" in text


class TestRenderJobs:
    def test_newest_first_bounded_with_progress_and_errors(self):
        jobs = [
            {
                "id": f"job-{i}",
                "title": f"Ingest {i}",
                "status": "failed" if i == 24 else "completed",
                "progress": {"total_chunks": 10, "processed_chunks": 10, "nodes_created": 42, "edges_created": 10},
                "result": None,
                "error": "boom" if i == 24 else None,
                "created_at": 1000 + i,
            }
            for i in range(25)
        ]
        text = render_jobs(jobs)
        assert "# Ingestion jobs (20 of 25)" in text
        assert "[job-24] Ingest 24 — failed, 10/10 chunks, 42 nodes, error: boom" in text
        assert "[job-23] Ingest 23 — completed, 10/10 chunks, 42 nodes" in text
        assert "[job-2]" not in text
        assert "…[rendered context bounded" in text

    def test_empty_list(self):
        assert render_jobs([]) == "No ingestion jobs."

    def test_no_retry_guidance_inferred_from_legacy_text(self):
        job = {"id": "legacy", "status": "failed", "error": "query_timeout retriable: false"}
        text = render_jobs([job])
        assert "error: query_timeout retriable: false" in text
        assert "code:" not in text
        malformed = {**job, "error_details": {"code": 42, "message": [], "status": "504", "retriable": "false"}}
        assert render_jobs([malformed]) == text
        assert render_jobs([{**job, "error_details": []}]) == text
        bounded = render_jobs(
            [{**job, "error_details": {"message": "x" * 1000, "code": "query_timeout", "status": 504, "retriable": False}}]
        )
        assert "code: query_timeout, status: 504, retriable: false" in bounded
        assert "…[rendered context bounded" in bounded


class TestRenderSignals:
    def test_named_arrays_as_sections(self):
        text = render_signals(
            {
                "project_uid": "proj-1",
                "documents": [{"uid": "d1", "title": "Q2 Strategy", "chunk_count": 12}],
                "entity_bridges": [{"uid": "e1", "label": "ACME", "document_count": 3, "score": 0.91}],
                "claim_hubs": [],
            }
        )
        assert "## documents" in text
        assert "Q2 Strategy" in text
        assert "## entity bridges" in text
        assert "ACME [e1]" in text
        assert "score 0.91" in text
        assert "claim_hubs" not in text

    def test_nothing_renders(self):
        assert render_signals({"project_uid": "p"}) is None

    def test_real_label_keys(self):
        text = render_signals(
            {
                "project_uid": "p",
                "claim_hubs": [{"target_uid": "t1", "target_label": "Institutional memory thesis", "claim_count": 14}],
                "dialectical_pairs": [{"from_uid": "a", "from_label": "Memory as retrieval", "to_uid": "b", "to_label": "Memory as reasoning"}],
            }
        )
        assert "Institutional memory thesis [t1] (claim_count 14)" in text
        assert "Memory as retrieval ↔ Memory as reasoning" in text
        assert "(item)" not in text
