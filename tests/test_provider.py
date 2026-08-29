"""Hermes native provider stays independent of the MCP server."""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest


def _install_hermes_stubs():
    if "agent.memory_provider" in sys.modules:
        return
    agent = types.ModuleType("agent")
    mp = types.ModuleType("agent.memory_provider")

    class MemoryProvider:
        pass

    class RecallStatus:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    def is_trivial_prompt(text):
        return False

    mp.MemoryProvider = MemoryProvider
    mp.RecallStatus = RecallStatus
    mp.is_trivial_prompt = is_trivial_prompt
    sys.modules["agent"] = agent
    sys.modules["agent.memory_provider"] = mp


_install_hermes_stubs()

from cloudflare_memory.provider import CloudflareMemoryProvider  # noqa: E402


def test_hermes_provider_does_not_use_mcp_server():
    import cloudflare_memory.provider as provider_mod

    assert not hasattr(provider_mod, "create_server")
    src = open(provider_mod.__file__).read()
    # Native provider talks HTTP via the client, not MCP tool registration
    assert "from cloudflare_memory.server" not in src
    assert "import cloudflare_memory.server" not in src


def test_hermes_native_tools_still_registered():
    names = [t["name"] for t in CloudflareMemoryProvider().get_tool_schemas()]
    assert "cf_remember" in names
    assert "cf_recall" in names
    # Native tools are host-side, not the 10-tool MCP tax
    assert "list_namespaces" not in names
    assert "create_namespace" not in names


def test_hermes_prefetch_is_non_blocking(monkeypatch):
    provider = CloudflareMemoryProvider()
    provider._client = MagicMock()
    fired = []

    def _fire(query, session_id):
        fired.append((query, session_id))

    monkeypatch.setattr(provider, "_fire_background_recall", _fire)
    result = provider.prefetch("what is the theme?")
    assert result == ""
    assert fired == [("what is the theme?", "")]


def test_hermes_sync_turn_starts_background_ingest(monkeypatch):
    provider = CloudflareMemoryProvider()
    provider._client = MagicMock()
    started = []

    class FakeThread:
        def __init__(self, target=None, daemon=None):
            self.target = target
            self.daemon = daemon

        def start(self):
            started.append(self.daemon)

    monkeypatch.setattr("cloudflare_memory.provider.threading.Thread", FakeThread)
    provider.sync_turn("remember that I like dark mode", "ok")
    assert started == [True]
