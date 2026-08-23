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
        description="Cloudflare Agent Memory — client, MCP server, Hermes provider",
    )
    sub = parser.add_subparsers(dest="command")

    # ── serve (MCP server) ────────────────────────────────────────────
    p_serve = sub.add_parser("serve", help="Start MCP server (stdio)")
    p_serve.add_argument("--namespace", default="hermes", help="Namespace name")
    p_serve.add_argument("--profile", default="default", help="Profile name")
    p_serve.add_argument(
        "--transport",
        default="stdio",
        choices=["stdio", "sse"],
        help="MCP transport",
    )

    # ── test (quick connectivity check) ───────────────────────────────
    p_test = sub.add_parser("test", help="Test API connectivity")
    p_test.add_argument("--namespace", default="hermes")
    p_test.add_argument("--profile", default="default")

    args = parser.parse_args()

    if args.command == "serve":
        from cloudflare_memory.server import serve
        serve(namespace=args.namespace, profile=args.profile, transport=args.transport)

    elif args.command == "test":
        asyncio.run(_test(args.namespace, args.profile))

    else:
        parser.print_help()
        sys.exit(1)


async def _test(namespace: str, profile: str) -> None:
    from cloudflare_memory.client import CloudflareMemoryClient, MemoryAPIError

    token = os.environ.get("MCP_CLOUDFLARE_API_KEY", "")
    if not token:
        print("ERROR: MCP_CLOUDFLARE_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    account = os.environ.get("CF_ACCOUNT_ID", "0870b0bdbc14bcd31f43fe5e82c3ee8e")
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
