"""Tests for the slim vs full MCP surface."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cloudflare_memory.client import MemoryEntry, RecallResult
from cloudflare_memory.main import build_parser
from cloudflare_memory.server import (
    ADMIN_TOOL_NAMES,
    SLIM_TOOL_NAMES,
    create_server,
)

ADMIN = set(ADMIN_TOOL_NAMES)
SLIM = set(SLIM_TOOL_NAMES)


def _text(result) -> str:
    return result.content[0].text


def _fake_client() -> MagicMock:
    client = MagicMock()
    entry = MemoryEntry(
        id="mem-1",
        type="fact",
        summary="User likes dark mode",
        content="Dark mode preferred.",
        session_id="s1",
        created_at="2026-08-23T00:00:00Z",
        updated_at="2026-08-23T00:00:00Z",
    )
    client.remember = AsyncMock(return_value=entry)
    client.recall = AsyncMock(
        return_value=RecallResult(
            answer="Dark mode",
            candidates=[MemoryEntry(id="c1", type="fact", summary="likes dark mode")],
        )
    )
    client.list_memories = AsyncMock(return_value=[entry])
    client.get_memory = AsyncMock(return_value=entry)
    client.delete_memory = AsyncMock(return_value={})
    client.ingest = AsyncMock(return_value={"success": True, "result": None})
    client.get_summary = AsyncMock(return_value="# Profile\n- fact")
    client.list_namespaces = AsyncMock(return_value=[{"name": "hermes"}])
    client.create_namespace = AsyncMock(return_value={"name": "new-ns"})
    client.delete_namespace = AsyncMock(return_value={})
    return client


@pytest.mark.asyncio
async def test_slim_server_has_exactly_two_tools():
    tools = await create_server().list_tools()
    names = [t.name for t in tools]
    assert names == list(SLIM_TOOL_NAMES)
    assert ADMIN.isdisjoint(names)


@pytest.mark.asyncio
async def test_full_server_includes_admin_tools():
    tools = await create_server(full=True).list_tools()
    names = set(t.name for t in tools)
    assert names == SLIM | ADMIN


@pytest.mark.asyncio
async def test_import_does_not_register_tools_on_a_global_server():
    import cloudflare_memory.server as mod

    assert not hasattr(mod, "server")
    # Factories are independent: full does not leak into a later slim server
    full = create_server(full=True)
    slim = create_server()
    assert {t.name for t in await full.list_tools()} == SLIM | ADMIN
    assert {t.name for t in await slim.list_tools()} == SLIM


@pytest.mark.asyncio
async def test_slim_schemas_are_tiny():
    tools = {t.name: t for t in await create_server().list_tools()}
    remember = tools["remember"]
    recall = tools["recall"]

    assert remember.description == "Store one fact."
    assert recall.description == "Answer from stored facts."
    assert "latency" not in remember.description.lower()
    assert "latency" not in recall.description.lower()

    assert set(remember.input_schema["properties"]) == {"content"}
    assert set(recall.input_schema["properties"]) == {"query"}
    assert "thinking_level" not in recall.input_schema["properties"]
    assert "response_length" not in recall.input_schema["properties"]
    assert "session_id" not in remember.input_schema["properties"]

    assert remember.output_schema is None
    assert recall.output_schema is None

    for t in tools.values():
        assert "\n" not in (t.description or "")
        advertised = json.dumps({"name": t.name, "description": t.description, "inputSchema": t.input_schema})
        assert len(advertised) < 400


@pytest.mark.asyncio
async def test_instructions_are_short():
    server = create_server()
    text = server.instructions or ""
    assert "recall" in text.lower()
    assert "every turn" in text.lower()
    assert len(text) < 200
    assert text.count(".") <= 3


@pytest.mark.asyncio
async def test_remember_returns_compact_id_and_type():
    client = _fake_client()
    with patch("cloudflare_memory.server._get_client", return_value=client):
        result = await create_server().call_tool("remember", {"content": "Dark mode preferred."})
    raw = _text(result)
    data = json.loads(raw)
    assert data == {"id": "mem-1", "type": "fact"}
    assert "summary" not in data
    assert "content" not in data
    assert "\n" not in raw
    client.remember.assert_awaited_once_with("Dark mode preferred.")


@pytest.mark.asyncio
async def test_recall_returns_answer_only_and_hardcodes_low_short():
    client = _fake_client()
    with patch("cloudflare_memory.server._get_client", return_value=client):
        result = await create_server().call_tool("recall", {"query": "theme?"})
    raw = _text(result)
    assert raw == "Dark mode"
    assert "candidates" not in raw
    client.recall.assert_awaited_once_with("theme?", thinking_level="low", response_length="short")


@pytest.mark.asyncio
async def test_slim_rejects_admin_tool_calls():
    with pytest.raises(Exception):
        await create_server().call_tool("list_memories", {})


@pytest.mark.asyncio
async def test_full_admin_tools_callable():
    client = _fake_client()
    server = create_server(full=True)
    with patch("cloudflare_memory.server._get_client", return_value=client):
        listed = json.loads(_text(await server.call_tool("list_memories", {})))
        got = json.loads(_text(await server.call_tool("get_memory", {"memory_id": "mem-1"})))
        deleted = json.loads(_text(await server.call_tool("delete_memory", {"memory_id": "mem-1"})))
        ingested = json.loads(_text(await server.call_tool(
            "ingest", {"messages": [{"role": "user", "content": "hi"}]}
        )))
        summary = _text(await server.call_tool("summary", {}))
        namespaces = json.loads(_text(await server.call_tool("list_namespaces", {})))
        created = json.loads(_text(await server.call_tool("create_namespace", {"name": "new-ns"})))
        ns_deleted = json.loads(_text(await server.call_tool("delete_namespace", {"name": "old-ns"})))

    assert listed[0]["id"] == "mem-1"
    assert got["content"] == "Dark mode preferred."
    assert deleted == {}
    assert ingested["success"] is True
    assert "Profile" in summary
    assert namespaces[0]["name"] == "hermes"
    assert created["name"] == "new-ns"
    assert ns_deleted == {}


def test_serve_parser_full_flag():
    parser = build_parser()
    slim = parser.parse_args(["serve"])
    assert slim.full is False
    full = parser.parse_args(["serve", "--full"])
    assert full.full is True


def test_cli_exposes_admin_commands():
    parser = build_parser()
    needs_id = {"get", "delete", "create-ns", "delete-ns"}
    for cmd in ("list", "get", "delete", "ingest", "summary", "namespaces", "create-ns", "delete-ns"):
        argv = [cmd, "x"] if cmd in needs_id else [cmd]
        assert parser.parse_args(argv).command == cmd
