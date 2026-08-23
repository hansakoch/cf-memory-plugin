"""CLI entry point for cloudflare-memory."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="cloudflare-memory",
        description="Cloudflare Agent Memory — client, MCP server, A2A agent, Hermes provider",
    )
    sub = parser.add_subparsers(dest="command")

    # ── serve (MCP server) ────────────────────────────────────────────
    p_serve = sub.add_parser("serve", help="Start MCP server (stdio/SSE)")
    p_serve.add_argument("--namespace", default="hermes", help="Namespace name")
    p_serve.add_argument("--profile", default="default", help="Profile name")
    p_serve.add_argument("--transport", default="stdio", choices=["stdio", "sse"])

    # ── a2a (A2A agent server) ────────────────────────────────────────
    p_a2a = sub.add_parser("a2a", help="Start A2A agent server")
    p_a2a.add_argument("--port", type=int, default=9120, help="Listen port")
    p_a2a.add_argument("--host", default="127.0.0.1", help="Bind address (default localhost)")

    # ── test (quick connectivity check) ───────────────────────────────
    p_test = sub.add_parser("test", help="Test API connectivity")
    p_test.add_argument("--namespace", default="hermes")
    p_test.add_argument("--profile", default="default")

    # ── card (print agent card) ───────────────────────────────────────
    sub.add_parser("card", help="Print A2A agent card JSON")

    args = parser.parse_args()

    if args.command == "serve":
        from cloudflare_memory.server import serve
        serve(namespace=args.namespace, profile=args.profile, transport=args.transport)

    elif args.command == "a2a":
        from cloudflare_memory.a2a_server import serve_a2a
        serve_a2a(port=args.port, host=args.host)

    elif args.command == "test":
        asyncio.run(_test(args.namespace, args.profile))

    elif args.command == "card":
        from cloudflare_memory.a2a_card import AGENT_CARD
        print(json.dumps(AGENT_CARD, indent=2))

    else:
        parser.print_help()
        sys.exit(1)


async def _test(namespace: str, profile: str) -> None:
    from cloudflare_memory.client import CloudflareMemoryClient, MemoryAPIError

    from cloudflare_memory.credentials import CredentialsError, require_account_id, require_token

    try:
        token = require_token()
        account = require_account_id()
    except CredentialsError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    async with CloudflareMemoryClient(
        account_id=account,
        api_token=token,
        namespace=namespace,
        profile=profile,
    ) as client:
        # 1. list namespaces
        try:
            ns = await client.list_namespaces()
            print(f"✓ Namespaces: {len(ns)} found")
            for n in ns:
                print(f"  - {n.get('name', n)}")
        except MemoryAPIError as e:
            print(f"✗ List namespaces failed: {e}")
            sys.exit(1)

        # 2. list memories
        try:
            entries = await client.list_memories()
            print(f"✓ Memories in {namespace}/{profile}: {len(entries)}")
            for e in entries[:5]:
                print(f"  [{e.type}] {e.summary[:80]}")
        except MemoryAPIError as e:
            print(f"✗ List memories failed: {e}")

        # 3. summary
        try:
            s = await client.get_summary()
            print(f"✓ Summary: {len(s)} chars")
            if s:
                print(f"  {s[:200]}...")
        except MemoryAPIError as e:
            print(f"✗ Summary failed: {e}")

    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
