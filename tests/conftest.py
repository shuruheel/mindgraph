"""Test config: load the flat-layout plugin as a package and stub the Hermes surface.

The repo root IS the plugin package (Hermes loads its ``__init__.py`` directly), and
the directory name is not importable, so it is registered as
``hermes_mindgraph_plugin``. ``agent.memory_provider`` and ``agent.secret_scope``
are stubbed so the provider imports outside a Hermes runtime.
"""

from __future__ import annotations

import importlib.util
import inspect
import os
import sys
import threading
import types
from abc import ABC
from pathlib import Path
from typing import Any, Callable

import pytest
from mindgraph import MindGraph

PKG = "hermes_mindgraph_plugin"
REPO_ROOT = Path(__file__).resolve().parent.parent


def _install_hermes_stubs() -> None:
    if "agent.memory_provider" in sys.modules:
        return

    class MemoryProvider(ABC):
        pre_compress_checkpoint_api_version = 1

    def spawn_context_thread(target, *, name, daemon=True, args=(), kwargs=None):
        return threading.Thread(target=target, args=args, kwargs=kwargs, name=name, daemon=daemon)

    agent_pkg = types.ModuleType("agent")
    agent_pkg.__path__ = []
    provider_mod = types.ModuleType("agent.memory_provider")
    provider_mod.MemoryProvider = MemoryProvider
    provider_mod.spawn_context_thread = spawn_context_thread
    secret_mod = types.ModuleType("agent.secret_scope")
    secret_mod.get_secret = lambda name, default=None: os.environ.get(name, default)
    sys.modules.setdefault("agent", agent_pkg)
    sys.modules["agent.memory_provider"] = provider_mod
    sys.modules["agent.secret_scope"] = secret_mod


def _load_plugin_package() -> None:
    if PKG in sys.modules:
        return
    spec = importlib.util.spec_from_file_location(
        PKG, str(REPO_ROOT / "__init__.py"), submodule_search_locations=[str(REPO_ROOT)]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[PKG] = module
    spec.loader.exec_module(module)


_install_hermes_stubs()
_load_plugin_package()


class FakeClient:
    """Records every SDK call; replies come from ``responses``.

    Only methods the real ``MindGraph`` client defines exist, and every call is
    bound against the real signature, so a renamed method or a wrong keyword
    fails the test instead of passing silently. A response may be a value, an
    exception instance (raised), or a callable that receives ``(*args, **kwargs)``.
    Unconfigured methods return ``{}``.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []
        self.responses: dict[str, Any] = {}

    def __getattr__(self, method: str) -> Callable[..., Any]:
        real = getattr(MindGraph, method, None)
        if method.startswith("__") or not callable(real):
            raise AttributeError(method)
        signature = inspect.signature(real)

        def call(*args: Any, **kwargs: Any) -> Any:
            signature.bind(self, *args, **kwargs)
            self.calls.append((method, args, kwargs))
            reply = self.responses.get(method, {})
            if isinstance(reply, BaseException):
                raise reply
            return reply(*args, **kwargs) if callable(reply) else reply

        return call

    def called(self, method: str) -> list[tuple[tuple, dict]]:
        return [(args, kwargs) for name, args, kwargs in self.calls if name == method]


@pytest.fixture
def fake_client() -> FakeClient:
    return FakeClient()


@pytest.fixture
def runtime(fake_client):
    from hermes_mindgraph_plugin.runtime import Runtime

    return Runtime(api_key="mg_test", session_id="sess-1", turn_number=1, client=fake_client)
