# MindGraph memory plugin installed

Activate it as your memory provider:

```
hermes memory setup
```

Pick **mindgraph**. If you have not set `MINDGRAPH_API_KEY` yet (get one at https://mindgraph.cloud), setup prompts for it.

From the next conversation, Hermes recalls relevant MindGraph context for each message, ingests completed turns as a session transcript, mirrors its built-in memory into MindGraph, and gives the model the mindgraph-mcp tools (`mindgraph_memory`, `mindgraph_capture`, `mindgraph_reason`, `mindgraph_commit`, `mindgraph_plan`, `mindgraph_retrieve`, `mindgraph_remember`, …).

Upgrading from 0.x: the tool names and actions changed in 1.0.0. See the README's "Upgrading from 0.x".

Docs: https://github.com/shuruheel/mindgraph#readme
