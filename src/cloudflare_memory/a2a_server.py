"""A2A server for Cloudflare Memory.

Serves the agent card and handles A2A JSON-RPC requests.
Run: cloudflare-memory a2a [--port 9120]
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any

try:
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from starlette.routing import Route
    HAS_STARLETTE = True
except ImportError:
    HAS_STARLETTE = False

from cloudflare_memory.a2a_card import AGENT_CARD
from cloudflare_memory.client import CloudflareMemoryClient, MemoryAPIError


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


async def _handle_skill(skill_id: str, params: dict) -> dict:
    """Dispatch an A2A skill call to the CF Memory client."""
    client = _get_client()
    try:
        if skill_id == "remember":
            entry = await client.remember(params["content"], params.get("session_id"))
            return {"id": entry.id, "type": entry.type, "summary": entry.summary}

        elif skill_id == "recall":
            result = await client.recall(params["query"])
            return {
                "answer": result.answer,
                "candidates": [{"id": c.id, "type": c.type, "summary": c.summary} for c in result.candidates],
            }

        elif skill_id == "ingest":
            r = await client.ingest(params["messages"], params.get("session_id"))
            return {"success": r.get("success", False), "note": "Memories appear 3–8s later"}

        elif skill_id == "list":
            entries = await client.list_memories(params.get("page", 1), params.get("per_page", 20))
            return [{"id": e.id, "type": e.type, "summary": e.summary} for e in entries]

        elif skill_id == "get":
            entry = await client.get_memory(params["memory_id"])
            return {"id": entry.id, "type": entry.type, "summary": entry.summary, "content": entry.content}

        elif skill_id == "summary":
            text = await client.get_summary()
            return {"summary": text}

        else:
            return {"error": f"Unknown skill: {skill_id}"}

    except MemoryAPIError as e:
        return {"error": str(e), "status": e.status, "code": e.code}
    except Exception as e:
        return {"error": str(e)}


# ── Starlette routes ─────────────────────────────────────────────────

async def agent_card(request: Request) -> JSONResponse:
    """Serve the A2A Agent Card."""
    return JSONResponse(AGENT_CARD)


async def rpc(request: Request) -> JSONResponse:
    """Handle A2A JSON-RPC requests."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": None})

    method = body.get("method", "")
    params = body.get("params", {})
    req_id = body.get("id")

    if method == "tasks/send":
        # Extract skill from message
        message = params.get("message", {})
        parts = message.get("parts", [])
        text = parts[0].get("text", "") if parts else ""

        # Parse skill from text (format: "skill_id: {json_params}")
        skill_id = params.get("skill", "")
        skill_params = params.get("params", {})

        if not skill_id and ":" in text:
            skill_id, _, param_str = text.partition(":")
            skill_id = skill_id.strip()
            try:
                skill_params = json.loads(param_str.strip())
            except json.JSONDecodeError:
                skill_params = {"content": param_str.strip()}
        elif not skill_id:
            skill_id = "recall"
            skill_params = {"query": text}

        result = await _handle_skill(skill_id, skill_params)

        return JSONResponse({
            "jsonrpc": "2.0",
            "result": {
                "id": params.get("id", "task-1"),
                "status": {"state": "completed"},
                "artifacts": [{
                    "parts": [{"type": "text", "text": json.dumps(result, indent=2)}],
                }],
            },
            "id": req_id,
        })

    elif method == "tasks/get":
        return JSONResponse({
            "jsonrpc": "2.0",
            "result": {"id": params.get("id", ""), "status": {"state": "unknown"}},
            "id": req_id,
        })

    else:
        return JSONResponse({
            "jsonrpc": "2.0",
            "error": {"code": -32601, "message": f"Method not found: {method}"},
            "id": req_id,
        })


def create_app():
    """Create the Starlette ASGI app."""
    if not HAS_STARLETTE:
        raise RuntimeError("starlette not installed — pip install starlette")
    return Starlette(routes=[
        Route("/.well-known/agent.json", agent_card),
        Route("/rpc", rpc, methods=["POST"]),
    ])


def serve_a2a(port: int = 9120, host: str = "0.0.0.0") -> None:
    """Start the A2A server."""
    if not HAS_STARLETTE:
        print("ERROR: starlette not installed. Run: pip install starlette uvicorn", file=sys.stderr)
        sys.exit(1)

    import uvicorn
    app = create_app()
    print(f"Cloudflare Memory A2A agent listening on {host}:{port}")
    print(f"Agent card: http://{host}:{port}/.well-known/agent.json")
    uvicorn.run(app, host=host, port=port, log_level="info")
