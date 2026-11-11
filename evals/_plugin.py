"""Import the flat-layout plugin as a package outside Hermes.

Hermes loads the repository root as the plugin package. Here the same files are
registered as ``hermes_mindgraph_plugin``; when Hermes is not installed, the two
modules the provider imports from it are stood in for.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import threading
import types
from pathlib import Path

PKG = "hermes_mindgraph_plugin"
ROOT = Path(__file__).resolve().parent.parent


def load() -> types.ModuleType:
    if PKG in sys.modules:
        return sys.modules[PKG]
    try:
        import agent.memory_provider  # noqa: F401  (real Hermes, when present)
        import agent.secret_scope  # noqa: F401
    except ImportError:

        class MemoryProvider:
            pre_compress_checkpoint_api_version = 1

        def spawn_context_thread(target, *, name, daemon=True, args=(), kwargs=None):
            return threading.Thread(target=target, args=args, kwargs=kwargs, name=name, daemon=daemon)

        package = types.ModuleType("agent")
        package.__path__ = []
        provider = types.ModuleType("agent.memory_provider")
        provider.MemoryProvider = MemoryProvider
        provider.spawn_context_thread = spawn_context_thread
        secrets = types.ModuleType("agent.secret_scope")
        secrets.get_secret = lambda name, default=None: os.environ.get(name, default)
        sys.modules.setdefault("agent", package)
        sys.modules["agent.memory_provider"] = provider
        sys.modules["agent.secret_scope"] = secrets
    spec = importlib.util.spec_from_file_location(PKG, str(ROOT / "__init__.py"), submodule_search_locations=[str(ROOT)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[PKG] = module
    spec.loader.exec_module(module)
    return module
