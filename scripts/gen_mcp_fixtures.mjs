// Record the HTTP requests mindgraph-mcp's own handleTool (general profile) makes
// for a fixed list of canonical tool calls, so tests/test_mcp_request_parity.py
// can assert this plugin sends the same requests for the same calls.
//
//   node scripts/gen_mcp_fixtures.mjs [path/to/mindgraph-mcp]
//
// Uses the MCP checkout's own esbuild and SDK; nothing is installed here. Every
// request is answered with `{}`, so handlers that chain requests see the same
// replies on both doors. Governance is not exercised: it runs in the MCP's
// tools/call wrapper, outside handleTool, and the Python test passes no gate.
import { createRequire } from "node:module";
import { readFileSync, writeFileSync, mkdtempSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const mcp = path.resolve(process.argv[2] ?? path.join(here, "..", "..", "mindgraph-mcp"));
const require = createRequire(path.join(mcp, "package.json"));
const esbuild = require("esbuild");
const version = JSON.parse(readFileSync(path.join(mcp, "package.json"), "utf8")).version;

const out = path.join(mkdtempSync(path.join(tmpdir(), "mg-fixtures-")), "tools.mjs");
await esbuild.build({
  stdin: {
    contents: 'export { handleTool } from "./src/tools.ts"; export { MindGraph } from "mindgraph";',
    resolveDir: mcp,
    loader: "ts",
  },
  bundle: true,
  platform: "node",
  format: "esm",
  outfile: out,
  define: { __PACKAGE_VERSION__: JSON.stringify(version) },
  banner: { js: "import { createRequire as __cr } from 'node:module'; const require = __cr(import.meta.url);" },
  logLevel: "error",
});
const { handleTool, MindGraph } = await import(pathToFileURL(out).href);

// Hermes's identity, mirrored on the Python side: agent_id is the provider
// default, and the invocation context carries the Hermes session and turn the
// plugin's Runtime scopes default idempotency keys by.
const BASE_URL = "http://mindgraph.test";
const AGENT_ID = "hermes";
const INVOCATION_CONTEXT = { harnessSessionId: "hermes-session", harnessTurnId: "1" };

const CASES = [
  ["retrieve_context_default", "mindgraph_retrieve", { action: "context", query: "Kissinger NATO" }],
  [
    "retrieve_context_as_of_exhaustive",
    "mindgraph_retrieve",
    { action: "context", query: "board members", as_of: "2024-03-01", retrieval_mode: "exhaustive", max_output_chars: 8000 },
  ],
  ["retrieve_context_json", "mindgraph_retrieve", { action: "context", query: "q", format: "json", include_documents: false }],
  ["retrieve_context_chunks", "mindgraph_retrieve", { action: "context", query: "q", include_chunks: true, limit: 4 }],
  ["retrieve_text", "mindgraph_retrieve", { action: "text", query: "NATO", limit: 3, node_types: ["Claim"] }],
  ["retrieve_hybrid", "mindgraph_retrieve", { action: "hybrid", query: "NATO", limit: 5, explain: true }],
  [
    "retrieve_neighborhood",
    "mindgraph_retrieve",
    { action: "neighborhood", start_uid: "n1", max_depth: 2, direction: "outgoing", edge_types: ["SUPPORTS"] },
  ],
  ["remember", "mindgraph_remember", { action: "remember", text: "Prefers tea", custom_id: "pref-tea", label: "Tea" }],
  ["forget", "mindgraph_remember", { action: "forget", custom_id: "pref-tea", dry_run: true, reason: "test" }],
  ["capture_journal", "mindgraph_capture", { action: "journal", label: "Day", content: "Shipped", mood: "good", tags: ["x"] }],
  [
    "capture_entity",
    "mindgraph_capture",
    { action: "entity", label: "Ada Lovelace", summary: "Mathematician", entity_type: "person", props: { born: 1815 } },
  ],
  [
    "reason_claim",
    "mindgraph_reason",
    {
      action: "claim",
      claim: { label: "Tea improves focus", content: "Measured", confidence: 0.7 },
      evidence: [{ label: "Study", description: "n=20" }],
      warrant: { label: "Caffeine", content: "Stimulant" },
    },
  ],
  ["commit_goal", "mindgraph_commit", { action: "goal", label: "Ship parity", summary: "Hermes = MCP", salience: 0.8 }],
  [
    "plan_create_task",
    "mindgraph_plan",
    { action: "create_task", label: "Port as_of", summary: "retrieve context", scope_uids: ["space:x"] },
  ],
  ["plan_resume_work", "mindgraph_plan", { action: "resume_work", limit: 5 }],
  [
    "ingest_session",
    "mindgraph_ingest",
    { action: "session", content: "user: hi\nassistant: hello", title: "Chat", layers: ["epistemic"] },
  ],
  ["series_latest", "mindgraph_series_query", { action: "latest", series_uid: "s1" }],
  ["memory_context_topic", "mindgraph_memory", { action: "context", mode: "topic", query: "NATO", limit: 5 }],
];

const realFetch = globalThis.fetch;
let recorded = [];
globalThis.fetch = async (url, init = {}) => {
  const target = new URL(String(url));
  recorded.push({
    method: (init.method ?? "GET").toUpperCase(),
    path: target.pathname + target.search,
    body: init.body === undefined || init.body === null ? null : JSON.parse(init.body),
  });
  return new Response("{}", { status: 200, headers: { "content-type": "application/json" } });
};

const cases = [];
try {
  for (const [id, tool, args] of CASES) {
    recorded = [];
    const client = new MindGraph({ baseUrl: BASE_URL, apiKey: "mg_test", maxRetries: 0 });
    const toolArgs = { ...args, agent_id: AGENT_ID, invocation_context: INVOCATION_CONTEXT };
    const result = await handleTool(client, tool, toolArgs, { profile: "general", harness: "hermes", agentId: AGENT_ID });
    if (result.isError) throw new Error(`${id}: MCP returned an error: ${JSON.stringify(result.content)}`);
    cases.push({ id, tool, args, requests: recorded });
  }
} finally {
  globalThis.fetch = realFetch;
}

const target = path.join(here, "..", "tests", "fixtures", "mcp_requests.json");
mkdirSync(path.dirname(target), { recursive: true });
writeFileSync(
  target,
  JSON.stringify(
    { mcp_version: version, base_url: BASE_URL, agent_id: AGENT_ID, invocation_context: INVOCATION_CONTEXT, cases },
    null,
    2,
  ) + "\n",
);
console.log(`tests/fixtures/mcp_requests.json: mindgraph-mcp ${version}, ${cases.length} cases`);
