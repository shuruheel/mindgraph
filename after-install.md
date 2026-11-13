# MindGraph memory plugin installed

Activate it as your memory provider:

```
hermes memory setup
```

Pick **mindgraph**. If you have not set `MINDGRAPH_API_KEY` yet (get one at https://mindgraph.cloud), setup prompts for it.

From the next conversation, Hermes recalls relevant MindGraph context, queues completed turns and delegated results on disk, mirrors built-in memory through a durable outbox, and gives the model the mindgraph-mcp tools (`mindgraph_memory`, `mindgraph_capture`, `mindgraph_reason`, `mindgraph_commit`, `mindgraph_plan`, `mindgraph_retrieve`, `mindgraph_remember`, …). Committed queue entries survive a restart; a full queue rejects new capture and reports it in `mindgraph_memory` status.

Automatic turn/delegation capture requires the default `plugins.isolation: in_process`. In isolated `host` mode, status reports that capture is disabled because Hermes's RPC hooks lack the turn identity needed for correct undo. Recall, tools, mirroring and required checkpoint snapshots still work.

Upgrading from 0.x: the tool names and actions changed in 1.0.0. See the README's "Upgrading from 0.x".

Docs: https://github.com/shuruheel/mindgraph#readme
