"""A2A server for Cloudflare Memory.

Serves the agent card and handles A2A JSON-RPC requests.
Run: cloudflare-memory a2a [--port 9120]

Accepts OpenClaw A2A 1.0 SendMessage / message/send on POST / and POST /rpc,
plus the original tasks/send dispatcher.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

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

SEND_METHODS = {"SendMessage", "message/send", "tasks/send"}
GET_METHODS = {"GetTask", "tasks/get"}


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


def _extract_text(params: dict) -> str:
    """Pull user text from A2A message.parts or a bare text field."""
    message = params.get("message") or {}
    if not isinstance(message, dict):
        message = {}
    parts = message.get("parts") or []
    texts: list[str] = []
    for part in parts:
        if isinstance(part, dict):
            text = part.get("text")
            if text:
                texts.append(str(text))
        elif isinstance(part, str) and part.strip():
            texts.append(part)
    if texts:
        return "\n".join(texts).strip()
    for key in ("text", "content", "query"):
        val = params.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


async def _dispatch_from_params(params: dict) -> dict:
    """Map an A2A send payload onto the existing skill dispatcher."""
    text = _extract_text(params)
    skill_id = params.get("skill") or ""
    if not isinstance(skill_id, str):
        skill_id = str(skill_id)
    skill_params = params.get("params") or {}
    if not isinstance(skill_params, dict):
        skill_params = {}

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

    return await _handle_skill(skill_id, skill_params)


def _task_ids(params: dict) -> tuple[str, str]:
    message = params.get("message") or {}
    if not isinstance(message, dict):
        message = {}
    task_id = (
        message.get("taskId")
        or params.get("id")
        or message.get("messageId")
        or f"task-{uuid4()}"
    )
    context_id = message.get("contextId") or params.get("contextId") or f"ctx-{uuid4()}"
    return str(task_id), str(context_id)


def _jsonrpc_error(code: int, message: str, req_id: Any) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "error": {"code": code, "message": message}, "id": req_id})


def _send_response(method: str, params: dict, skill_result: Any, req_id: Any) -> JSONResponse:
    task_id, context_id = _task_ids(params)
    artifact_text = json.dumps(skill_result, indent=2)
    now = datetime.now(timezone.utc).isoformat()

    if method == "tasks/send":
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "result": {
                    "id": task_id,
                    "status": {"state": "completed"},
                    "artifacts": [{"parts": [{"type": "text", "text": artifact_text}]}],
                    "task": {
                        "id": task_id,
                        "contextId": context_id,
                        "status": {"state": "completed", "timestamp": now},
                    },
                },
                "id": req_id,
            }
        )

    # SendMessage / message/send — OpenClaw A2A 1.0 expects result.task
    return JSONResponse(
        {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "task": {
                    "id": task_id,
                    "contextId": context_id,
                    "status": {
                        "state": "TASK_STATE_COMPLETED",
                        "timestamp": now,
                    },
                    "artifacts": [
                        {
                            "artifactId": f"art-{task_id}",
                            "parts": [{"text": artifact_text}],
                        }
                    ],
                    "history": [],
                }
            },
        }
    )


# ── Starlette routes ─────────────────────────────────────────────────

async def agent_card(request: Request) -> JSONResponse:
    """Serve the A2A Agent Card."""
    return JSONResponse(AGENT_CARD)


async def rpc(request: Request) -> JSONResponse:
    """Handle A2A JSON-RPC on POST / and POST /rpc."""
    try:
        body = await request.json()
    except Exception:
        return _jsonrpc_error(-32700, "Parse error", None)

    if not isinstance(body, dict):
        return _jsonrpc_error(-32600, "Invalid Request", None)

    method = body.get("method", "") or ""
    params = body.get("params") or {}
    if not isinstance(params, dict):
        params = {}
    req_id = body.get("id")

    if method in SEND_METHODS:
        result = await _dispatch_from_params(params)
        return _send_response(method, params, result, req_id)

    if method in GET_METHODS:
        task_id = params.get("id", "")
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "result": {"id": task_id, "status": {"state": "unknown"}},
                "id": req_id,
            }
        )

    return _jsonrpc_error(-32601, f"Method not found: {method}", req_id)


def create_app():
    """Create the Starlette ASGI app."""
    if not HAS_STARLETTE:
        raise RuntimeError("starlette not installed — pip install starlette")
    return Starlette(
        routes=[
            Route("/.well-known/agent.json", agent_card),
            Route("/.well-known/agent-card.json", agent_card),
            Route("/rpc", rpc, methods=["POST"]),
            Route("/", rpc, methods=["POST"]),
        ]
    )


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
