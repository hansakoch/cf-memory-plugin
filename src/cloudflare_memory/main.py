"""CLI entry point for cloudflare-memory."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cf-memory",
        description="Cloudflare Agent Memory — client, MCP server, A2A agent, Hermes provider",
    )
    sub = parser.add_subparsers(dest="command")

    # ── serve (MCP server) ────────────────────────────────────────────
    p_serve = sub.add_parser(
        "serve",
        help="Start MCP server (stdio/SSE). Default: remember + recall only",
    )
    p_serve.add_argument("--namespace", default="hermes", help="Namespace name")
    p_serve.add_argument("--profile", default="default", help="Profile name")
    p_serve.add_argument("--transport", default="stdio", choices=["stdio", "sse"])
    p_serve.add_argument(
        "--full",
        action="store_true",
        help="Expose admin tools (list/get/delete/ingest/summary/namespaces) for debugging",
    )

    # ── a2a (A2A agent server) ────────────────────────────────────────
    p_a2a = sub.add_parser("a2a", help="Start A2A agent server")
    p_a2a.add_argument("--port", type=int, default=9120, help="Listen port")
    p_a2a.add_argument("--host", default="127.0.0.1", help="Bind address (default localhost)")

    # ── test (quick connectivity check) ───────────────────────────────
    p_test = sub.add_parser("test", help="Test API connectivity")
    _add_scope(p_test)

    # ── card (print agent card) ───────────────────────────────────────
    sub.add_parser("card", help="Print A2A agent card JSON")

    # ── admin (CLI-only; not on the default MCP server) ───────────────
    p_list = sub.add_parser("list", help="List memories (CLI-only)")
    _add_scope(p_list)
    p_list.add_argument("--page", type=int, default=1)
    p_list.add_argument("--per-page", type=int, default=20)

    p_get = sub.add_parser("get", help="Get one memory by id (CLI-only)")
    _add_scope(p_get)
    p_get.add_argument("memory_id")

    p_delete = sub.add_parser("delete", help="Delete one memory by id (CLI-only)")
    _add_scope(p_delete)
    p_delete.add_argument("memory_id")

    p_ingest = sub.add_parser(
        "ingest",
        help="Extract memories from a JSON message list (CLI-only; blows MCP context)",
    )
    _add_scope(p_ingest)
    p_ingest.add_argument(
        "file",
        nargs="?",
        help="JSON file of [{role, content}, ...]; stdin if omitted",
    )
    p_ingest.add_argument("--session-id", default="")

    p_summary = sub.add_parser("summary", help="Markdown profile summary (CLI-only; blows MCP context)")
    _add_scope(p_summary)

    p_ns = sub.add_parser("namespaces", help="List namespaces (CLI-only)")
    _add_scope(p_ns)

    p_create_ns = sub.add_parser("create-ns", help="Create a namespace (CLI-only)")
    _add_scope(p_create_ns)
    p_create_ns.add_argument("name", help="Namespace name (≤32 chars)")

    p_delete_ns = sub.add_parser("delete-ns", help="Delete a namespace (CLI-only)")
    _add_scope(p_delete_ns)
    p_delete_ns.add_argument("name", help="Namespace name")

    return parser


def _add_scope(p: argparse.ArgumentParser) -> None:
    p.add_argument("--namespace", default=None, help="Namespace name")
    p.add_argument("--profile", default=None, help="Profile name")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "serve":
        from cloudflare_memory.server import serve

        serve(
            namespace=args.namespace,
            profile=args.profile,
            transport=args.transport,
            full=args.full,
        )

    elif args.command == "a2a":
        from cloudflare_memory.a2a_server import serve_a2a

        serve_a2a(port=args.port, host=args.host)

    elif args.command == "test":
        asyncio.run(_test(args.namespace, args.profile))

    elif args.command == "card":
        from cloudflare_memory.a2a_card import AGENT_CARD

        print(json.dumps(AGENT_CARD, indent=2))

    elif args.command == "list":
        asyncio.run(_cmd_list(args))

    elif args.command == "get":
        asyncio.run(_cmd_get(args))

    elif args.command == "delete":
        asyncio.run(_cmd_delete(args))

    elif args.command == "ingest":
        asyncio.run(_cmd_ingest(args))

    elif args.command == "summary":
        asyncio.run(_cmd_summary(args))

    elif args.command == "namespaces":
        asyncio.run(_cmd_namespaces(args))

    elif args.command == "create-ns":
        asyncio.run(_cmd_create_ns(args))

    elif args.command == "delete-ns":
        asyncio.run(_cmd_delete_ns(args))

    else:
        parser.print_help()
        sys.exit(1)


def _make_client(namespace: str | None = None, profile: str | None = None):
    from cloudflare_memory.client import CloudflareMemoryClient
    from cloudflare_memory.credentials import CredentialsError, require_account_id, require_token

    try:
        token = require_token()
        account = require_account_id()
    except CredentialsError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    ns = namespace or os.environ.get("CF_MEMORY_NAMESPACE") or "hermes"
    prof = profile or os.environ.get("CF_MEMORY_PROFILE") or "default"
    return CloudflareMemoryClient(
        account_id=account,
        api_token=token,
        namespace=ns,
        profile=prof,
    )


async def _test(namespace: str | None, profile: str | None) -> None:
    from cloudflare_memory.client import MemoryAPIError

    client = _make_client(namespace, profile)
    async with client:
        try:
            ns = await client.list_namespaces()
            print(f"✓ Namespaces: {len(ns)} found")
            for n in ns:
                print(f"  - {n.get('name', n)}")
        except MemoryAPIError as e:
            print(f"✗ List namespaces failed: {e}")
            sys.exit(1)

        try:
            entries = await client.list_memories()
            print(f"✓ Memories in {client.namespace}/{client.profile}: {len(entries)}")
            for e in entries[:5]:
                print(f"  [{e.type}] {e.summary[:80]}")
        except MemoryAPIError as e:
            print(f"✗ List memories failed: {e}")

        try:
            s = await client.get_summary()
            print(f"✓ Summary: {len(s)} chars")
            if s:
                print(f"  {s[:200]}...")
        except MemoryAPIError as e:
            print(f"✗ Summary failed: {e}")

    print("\nAll checks passed.")


def _print_json(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


async def _cmd_list(args) -> None:
    client = _make_client(args.namespace, args.profile)
    async with client:
        entries = await client.list_memories(args.page, args.per_page)
        _print_json([
            {"id": e.id, "type": e.type, "summary": e.summary}
            for e in entries
        ])


async def _cmd_get(args) -> None:
    client = _make_client(args.namespace, args.profile)
    async with client:
        e = await client.get_memory(args.memory_id)
        _print_json({
            "id": e.id,
            "type": e.type,
            "summary": e.summary,
            "content": e.content,
            "sessionId": e.session_id,
            "createdAt": e.created_at,
            "updatedAt": e.updated_at,
        })


async def _cmd_delete(args) -> None:
    client = _make_client(args.namespace, args.profile)
    async with client:
        result = await client.delete_memory(args.memory_id)
        _print_json(result)


async def _cmd_ingest(args) -> None:
    if args.file:
        with open(args.file, encoding="utf-8") as fh:
            raw = fh.read()
    else:
        raw = sys.stdin.read()
    messages = json.loads(raw)
    if not isinstance(messages, list):
        print("ERROR: ingest expects a JSON array of {role, content} objects", file=sys.stderr)
        sys.exit(1)
    client = _make_client(args.namespace, args.profile)
    async with client:
        result = await client.ingest(messages, args.session_id or None)
        _print_json(result)


async def _cmd_summary(args) -> None:
    client = _make_client(args.namespace, args.profile)
    async with client:
        print(await client.get_summary())


async def _cmd_namespaces(args) -> None:
    client = _make_client(args.namespace, args.profile)
    async with client:
        _print_json(await client.list_namespaces())


async def _cmd_create_ns(args) -> None:
    client = _make_client(args.namespace, args.profile)
    async with client:
        _print_json(await client.create_namespace(args.name))


async def _cmd_delete_ns(args) -> None:
    client = _make_client(args.namespace, args.profile)
    async with client:
        _print_json(await client.delete_namespace(args.name))


if __name__ == "__main__":
    main()
