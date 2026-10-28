"""MindGraph memory provider for Hermes Agent.

Install from the Hermes plugin catalog::

    hermes plugins install mindgraph
    hermes memory setup   # pick mindgraph

The tool surface is the general profile of the mindgraph-mcp server, generated
into ``mcp_contract.json`` by ``scripts/sync_from_mcp.mjs``. See ``provider.py``
for the Hermes lifecycle.
"""

from __future__ import annotations

__version__ = "1.0.0"


def register(ctx) -> None:
    """Hand Hermes a new provider instance per load (multiplexing contract)."""
    from .provider import MindGraphMemoryProvider

    ctx.register_memory_provider(MindGraphMemoryProvider())
