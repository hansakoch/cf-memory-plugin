"""Tests for the Cloudflare Memory client (mocked HTTP)."""

from __future__ import annotations

import json
import pytest
import respx
import httpx

from cloudflare_memory.client import (
    CloudflareMemoryClient,
    MemoryAPIError,
    MemoryEntry,
    RecallResult,
)

ACCOUNT = "0870b0bdbc14bcd31f43fe5e82c3ee8e"
TOKEN = "test-token"
BASE = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}/agent-memory"
NS = f"{BASE}/namespaces/test-ns"
PROF = f"{NS}/profiles/test-prof"


@pytest.fixture
def client():
    return CloudflareMemoryClient(
        account_id=ACCOUNT,
        api_token=TOKEN,
        namespace="test-ns",
        profile="test-prof",
    )


def _ok(result=None):
    return httpx.Response(200, json={"success": True, "result": result or {}})


def _err(status=400, code=1000, msg="bad request"):
    return httpx.Response(status, json={
        "success": False,
        "errors": [{"code": code, "message": msg}],
    })


# ── namespace management ──────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_list_namespaces(client):
    respx.get(f"{BASE}/namespaces").mock(return_value=_ok([
        {"name": "ns1"}, {"name": "ns2"},
    ]))
    async with client:
        ns = await client.list_namespaces()
    assert len(ns) == 2
    assert ns[0]["name"] == "ns1"


@pytest.mark.asyncio
@respx.mock
async def test_create_namespace(client):
    respx.post(f"{BASE}/namespaces").mock(return_value=_ok({"name": "new-ns"}))
    async with client:
        result = await client.create_namespace("new-ns")
    assert result["name"] == "new-ns"


@pytest.mark.asyncio
@respx.mock
async def test_delete_namespace(client):
    respx.delete(f"{BASE}/namespaces/old-ns").mock(return_value=_ok({}))
    async with client:
        result = await client.delete_namespace("old-ns")
    assert result == {}


# ── remember ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_remember(client):
    respx.post(f"{PROF}/remember").mock(return_value=_ok({
        "id": "mem-1",
        "type": "fact",
        "summary": "User likes dark mode",
        "content": "Dark mode preferred.",
        "sessionId": "s1",
        "createdAt": "2026-08-23T00:00:00Z",
        "updatedAt": "2026-08-23T00:00:00Z",
    }))
    async with client:
        entry = await client.remember("Dark mode preferred.", session_id="s1")
    assert isinstance(entry, MemoryEntry)
    assert entry.id == "mem-1"
    assert entry.type == "fact"
    assert entry.summary == "User likes dark mode"
    assert entry.content == "Dark mode preferred."


# ── list ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_list_memories(client):
    respx.get(f"{PROF}/memories").mock(return_value=_ok([
        {"id": "m1", "type": "fact", "summary": "s1"},
        {"id": "m2", "type": "event", "summary": "s2"},
    ]))
    async with client:
        entries = await client.list_memories()
    assert len(entries) == 2
    assert entries[0].content is None  # list omits content


# ── get ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_get_memory(client):
    respx.get(f"{PROF}/memories/mem-1").mock(return_value=_ok({
        "id": "mem-1", "type": "fact", "summary": "s", "content": "full text",
    }))
    async with client:
        entry = await client.get_memory("mem-1")
    assert entry.content == "full text"


# ── delete ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_delete_memory(client):
    respx.delete(f"{PROF}/memories/mem-1").mock(return_value=_ok({}))
    async with client:
        result = await client.delete_memory("mem-1")
    assert result == {}


# ── recall ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_recall(client):
    respx.post(f"{PROF}/recall").mock(return_value=_ok({
        "answer": "Iceberg Media",
        "candidates": [{"id": "c1", "type": "fact", "summary": "s"}],
    }))
    async with client:
        result = await client.recall("What agency?")
    assert isinstance(result, RecallResult)
    assert result.answer == "Iceberg Media"
    assert len(result.candidates) == 1


@pytest.mark.asyncio
async def test_recall_query_too_long(client):
    async with client:
        with pytest.raises(ValueError, match="exceeds"):
            await client.recall("x" * 2000)


# ── ingest ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_ingest(client):
    respx.post(f"{PROF}/ingest").mock(return_value=_ok({
        "success": True, "result": None,
    }))
    async with client:
        result = await client.ingest(
            [{"role": "user", "content": "hello"}],
            session_id="s1",
        )
    assert result["success"] is True


@pytest.mark.asyncio
async def test_ingest_too_many_messages(client):
    async with client:
        with pytest.raises(ValueError, match="Max 500"):
            await client.ingest([{"role": "user", "content": "x"}] * 501)


# ── summary ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_summary(client):
    respx.post(f"{PROF}/summary").mock(return_value=_ok({
        "summary": "# Profile Summary\n- Key fact",
    }))
    async with client:
        text = await client.get_summary()
    assert "Key fact" in text


# ── error handling ────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_api_error(client):
    respx.get(f"{BASE}/namespaces").mock(return_value=_err(401, 10003, "Not allowed"))
    async with client:
        with pytest.raises(MemoryAPIError) as exc_info:
            await client.list_namespaces()
    assert exc_info.value.status == 401
    assert "Not allowed" in str(exc_info.value)
