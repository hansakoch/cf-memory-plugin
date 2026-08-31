"""MCP server for Cloudflare Agent Memory.

Default surface is two tiny tools (remember, recall). Harnesses inject every
tool schema every turn, so extra tools and long descriptions are pure cost.

Admin tools (list/get/delete/ingest/summary/namespaces) stay on the Python
client and CLI. Pass --full only for debugging.

Run: cf-memory serve [--namespace NAME] [--profile NAME] [--full]
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from mcp.server.fastmcp import FastMCP as MCPServer

from cloudflare_memory.client import CloudflareMemoryClient

# Call recall only when a fact is missing. Never every turn; never dump the store.
_INSTRUCTIONS = "Recall only when you lack a fact. Not every turn."

SLIM_TOOL_NAMES = ("remember", "recall")
ADMIN_TOOL_NAMES = (
    "list_memories",
    "get_memory",
    "delete_memory",
    "ingest",
    "summary",
    "list_namespaces",
    "create_namespace",
    "delete_namespace",
)

_client: CloudflareMemoryClient | None = None


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


def _compact(obj: Any) -> str:
    return json.dumps(obj, separators=(",", ":"))


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


# ── core tools (always registered) ────────────────────────────────────

async def remember(content: str) -> str:
    """Store one fact."""
    entry = await _get_client().remember(content)
    return _compact({"id": entry.id, "type": entry.type})


async def recall(query: str) -> str:
    """Answer from stored facts."""
    result = await _get_client().recall(query, thinking_level="low", response_length="short")
    return result.answer


# ── admin tools (--full only) ─────────────────────────────────────────

async def list_memories(page: int = 1, per_page: int = 20) -> str:
    """List memories."""
    entries = await _get_client().list_memories(page, per_page)
    return _compact([_entry_dict(e) for e in entries])


async def get_memory(memory_id: str) -> str:
    """Get one memory by id."""
    entry = await _get_client().get_memory(memory_id)
    return _compact(_entry_dict(entry))


async def delete_memory(memory_id: str) -> str:
    """Delete one memory by id."""
    result = await _get_client().delete_memory(memory_id)
    return _compact(result)


async def ingest(messages: list[dict[str, str]], session_id: str = "") -> str:
    """Extract memories from messages."""
    result = await _get_client().ingest(messages, session_id or None)
    return _compact(result)


async def summary() -> str:
    """Markdown profile summary."""
    return await _get_client().get_summary()


async def list_namespaces() -> str:
    """List namespaces."""
    ns = await _get_client().list_namespaces()
    return _compact(ns)


async def create_namespace(name: str) -> str:
    """Create a namespace."""
    result = await _get_client().create_namespace(name)
    return _compact(result)


async def delete_namespace(name: str) -> str:
    """Delete a namespace."""
    result = await _get_client().delete_namespace(name)
    return _compact(result)


_ADMIN_FUNCS = (
    list_memories,
    get_memory,
    delete_memory,
    ingest,
    summary,
    list_namespaces,
    create_namespace,
    delete_namespace,
)


def create_server(*, full: bool = False) -> MCPServer:
    """Build an MCP server. Default: remember + recall only."""
    server = MCPServer(name="cloudflare-memory", instructions=_INSTRUCTIONS)
    # structured_output=False omits output_schema from the advertised tool list
    server.add_tool(remember, structured_output=False)
    server.add_tool(recall, structured_output=False)
    if full:
        for fn in _ADMIN_FUNCS:
            server.add_tool(fn, structured_output=False)
    return server


def _preflight_check() -> None:
    """Validate credentials before entering the MCP stdio loop.

    Prints clear errors to stderr and exits non-zero if setup is wrong.
    This prevents silent failures where the harness starts the server
    but every tool call returns an auth error.
    """
    import sys

    from cloudflare_memory.credentials import (
        ACCOUNT_ENV,
        TOKEN_ENV,
        CredentialsError,
        require_account_id,
        require_token,
    )

    try:
        require_token()
    except CredentialsError:
        print(
            f"cf-memory: {TOKEN_ENV} is not set.\n"
            f"Create a token at https://dash.cloudflare.com/profile/api-tokens\n"
            f"with 'Agent Memory' permission, then set {TOKEN_ENV} in your environment.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        require_account_id()
    except CredentialsError:
        print(
            f"cf-memory: {ACCOUNT_ENV} is not set.\n"
            f"Find it in the Cloudflare dashboard sidebar: https://dash.cloudflare.com/",
            file=sys.stderr,
        )
        sys.exit(1)


def serve(
    namespace: str = "hermes",
    profile: str = "default",
    transport: str = "stdio",
    full: bool = False,
) -> None:
    """Start the MCP server."""
    _preflight_check()
    os.environ.setdefault("CF_MEMORY_NAMESPACE", namespace)
    os.environ.setdefault("CF_MEMORY_PROFILE", profile)
    server = create_server(full=full)
    if transport == "stdio":
        asyncio.run(server.run_stdio_async())
    else:
        asyncio.run(server.run_sse_async())


if __name__ == "__main__":
    serve()
