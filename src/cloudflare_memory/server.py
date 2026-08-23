"""MCP server for Cloudflare Agent Memory.

Exposes remember, recall, list, get, delete, ingest, summary as MCP tools.
Run: cloudflare-memory serve [--namespace NAME] [--profile NAME]
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from mcp.server.mcpserver import MCPServer

from cloudflare_memory.client import CloudflareMemoryClient, MemoryAPIError

# ── globals ───────────────────────────────────────────────────────────
_client: CloudflareMemoryClient | None = None
server = MCPServer(name="cloudflare-memory", instructions="Cloudflare Agent Memory operations")


def _get_client() -> CloudflareMemoryClient:
    global _client
    if _client is None:
        from cloudflare_memory.credentials import (
            namespace,
            profile,
            require_account_id,
            require_token,
        )

        _client = CloudflareMemoryClient(
            account_id=require_account_id(),
            api_token=require_token(),
            namespace=namespace(),
            profile=profile(),
        )
    return _client


def _entry_dict(e) -> dict:
    d = {"id": e.id, "type": e.type, "summary": e.summary}
    if e.content:
        d["content"] = e.content
    if e.session_id:
        d["sessionId"] = e.session_id
    if e.created_at:
        d["createdAt"] = e.created_at
    if e.updated_at:
        d["updatedAt"] = e.updated_at
    return d


# ── tools via decorator ───────────────────────────────────────────────

@server.tool()
async def remember(content: str, session_id: str = "") -> str:
    """Store a single memory. Returns type + summary. Latency: 1.3–3.8s."""
    client = _get_client()
    entry = await client.remember(content, session_id or None)
    return json.dumps(_entry_dict(entry), indent=2)


@server.tool()
async def recall(query: str, thinking_level: str = "low", response_length: str = "short") -> str:
    """Semantic recall — synthesized answer + candidates. Latency: ~5s."""
    client = _get_client()
    result = await client.recall(query, thinking_level, response_length)
    return json.dumps({
        "answer": result.answer,
        "candidates": [_entry_dict(c) for c in result.candidates],
    }, indent=2)


@server.tool()
async def list_memories(page: int = 1, per_page: int = 20) -> str:
    """List memories (omits content). Fast ~0.4s."""
    client = _get_client()
    entries = await client.list_memories(page, per_page)
    return json.dumps([_entry_dict(e) for e in entries], indent=2)


@server.tool()
async def get_memory(memory_id: str) -> str:
    """Get one memory by ID (includes content). ~1.4s."""
    client = _get_client()
    entry = await client.get_memory(memory_id)
    return json.dumps(_entry_dict(entry), indent=2)


@server.tool()
async def delete_memory(memory_id: str) -> str:
    """Delete a memory by ID."""
    client = _get_client()
    result = await client.delete_memory(memory_id)
    return json.dumps(result, indent=2)


@server.tool()
async def ingest(messages: list[dict[str, str]], session_id: str = "") -> str:
    """Ingest messages for extraction. Max 500. Returns immediately — memories appear 3–8s later."""
    client = _get_client()
    result = await client.ingest(messages, session_id or None)
    return json.dumps(result, indent=2)


@server.tool()
async def summary() -> str:
    """Markdown summary of the profile's memories."""
    client = _get_client()
    return await client.get_summary()


@server.tool()
async def list_namespaces() -> str:
    """List all namespaces in the account."""
    client = _get_client()
    ns = await client.list_namespaces()
    return json.dumps(ns, indent=2)


@server.tool()
async def create_namespace(name: str) -> str:
    """Create a new namespace."""
    client = _get_client()
    result = await client.create_namespace(name)
    return json.dumps(result, indent=2)


@server.tool()
async def delete_namespace(name: str) -> str:
    """Delete a namespace by name."""
    client = _get_client()
    result = await client.delete_namespace(name)
    return json.dumps(result, indent=2)


# ── CLI entry point ───────────────────────────────────────────────────

def serve(
    namespace: str = "hermes",
    profile: str = "default",
    transport: str = "stdio",
) -> None:
    """Start the MCP server."""
    os.environ.setdefault("CF_MEMORY_NAMESPACE", namespace)
    os.environ.setdefault("CF_MEMORY_PROFILE", profile)
    if transport == "stdio":
        asyncio.run(server.run_stdio_async())
    else:
        asyncio.run(server.run_sse_async())
