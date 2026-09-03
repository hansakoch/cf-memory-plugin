"""CLI commands for Cloudflare Memory plugin.

Handles: hermes cloudflare-memory status | test | namespaces | create-ns | delete-ns
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path


def _get_client():
    """Lazy-create a client from env + config."""
    from cloudflare_memory.client import CloudflareMemoryClient

    from cloudflare_memory.credentials import CredentialsError, require_account_id, require_token

    try:
        token = require_token()
        account = require_account_id()
    except CredentialsError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # Try reading config
    from hermes_constants import get_hermes_home
    config_path = get_hermes_home() / "cloudflare-memory.json"
    namespace = "hermes"
    profile = "default"
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text())
            namespace = cfg.get("namespace", namespace)
            profile = cfg.get("profile", profile)
        except Exception:
            pass

    return CloudflareMemoryClient(
        account_id=account,
        api_token=token,
        namespace=namespace,
        profile=profile,
    ), namespace, profile


def cmd_status(args):
    """Show provider status."""
    client, ns, prof = _get_client()

    async def _run():
        async with client:
            namespaces = await client.list_namespaces()
            ns_names = [n.get("name", "?") for n in namespaces]
            ns_exists = ns in ns_names

            print(f"Namespace: {ns} ({'exists' if ns_exists else 'MISSING — will be created on first write'})")
            print(f"Profile:   {prof}")
            print(f"Account:   {client.account_id}")

            if ns_exists:
                try:
                    entries = await client.list_memories()
                    print(f"Memories:  {len(entries)}")
                except Exception as e:
                    print(f"Memories:  error — {e}")

            print(f"\nAll namespaces: {', '.join(ns_names) if ns_names else '(none)'}")

    asyncio.run(_run())


def cmd_test(args):
    """Run connectivity + write/read test."""
    client, ns, prof = _get_client()

    async def _run():
        import time
        async with client:
            # List namespaces
            t0 = time.monotonic()
            nss = await client.list_namespaces()
            print(f"✓ Namespaces ({time.monotonic()-t0:.1f}s): {len(nss)} found")

            # Remember
            t0 = time.monotonic()
            entry = await client.remember(
                "Cloudflare Memory provider connectivity test.",
                session_id="cli-test",
            )
            print(f"✓ Remember ({time.monotonic()-t0:.1f}s): [{entry.type}] {entry.summary}")

            # List
            t0 = time.monotonic()
            entries = await client.list_memories()
            print(f"✓ List ({time.monotonic()-t0:.1f}s): {len(entries)} memories")

            # Recall
            t0 = time.monotonic()
            result = await client.recall("connectivity test")
            print(f"✓ Recall ({time.monotonic()-t0:.1f}s): {result.answer[:80]}")

            # Summary
            t0 = time.monotonic()
            s = await client.get_summary()
            print(f"✓ Summary ({time.monotonic()-t0:.1f}s): {len(s)} chars")

            # Cleanup
            await client.delete_memory(entry.id)
            print(f"✓ Cleaned up test memory")

    asyncio.run(_run())


def cmd_namespaces(args):
    """List all namespaces."""
    client, _, _ = _get_client()

    async def _run():
        async with client:
            nss = await client.list_namespaces()
            for n in nss:
                print(f"  {n.get('name', '?')}  (id: {n.get('id', '?')})")
            if not nss:
                print("  (no namespaces)")

    asyncio.run(_run())


def cmd_create_ns(args):
    """Create a namespace."""
    client, _, _ = _get_client()
    name = args.name

    async def _run():
        async with client:
            result = await client.create_namespace(name)
            print(f"Created: {result.get('name', name)} (id: {result.get('id', '?')})")

    asyncio.run(_run())


def cmd_delete_ns(args):
    """Delete a namespace."""
    client, _, _ = _get_client()
    name = args.name

    async def _run():
        async with client:
            await client.delete_namespace(name)
            print(f"Deleted: {name}")

    asyncio.run(_run())


def cmd_export(args):
    """Export all memories to file."""
    client, ns, prof = _get_client()
    fmt = args.format
    output = args.output
    type_filter = args.type
    session_filter = args.session

    async def _run():
        async with client:
            all_memories = []
            page = 1
            while True:
                entries = await client.list_memories(page=page, per_page=100)
                if not entries:
                    break
                # Get content for each memory
                for entry in entries:
                    if type_filter and entry.type != type_filter:
                        continue
                    if session_filter and entry.session_id != session_filter:
                        continue
                    full = await client.get_memory(entry.id)
                    all_memories.append(full)
                page += 1

            if fmt == "json":
                data = [
                    {
                        "id": m.id,
                        "type": m.type,
                        "summary": m.summary,
                        "content": m.content,
                        "session_id": m.session_id,
                        "created_at": m.created_at,
                        "updated_at": m.updated_at,
                    }
                    for m in all_memories
                ]
                out = json.dumps(data, indent=2, ensure_ascii=False)
            elif fmt == "jsonl":
                lines = []
                for m in all_memories:
                    lines.append(json.dumps({
                        "id": m.id,
                        "type": m.type,
                        "summary": m.summary,
                        "content": m.content,
                        "session_id": m.session_id,
                        "created_at": m.created_at,
                    }, ensure_ascii=False))
                out = "\n".join(lines)
            elif fmt == "markdown":
                lines = [f"# Memory Export — {ns}/{prof}", f"\nExported: {len(all_memories)} memories\n"]
                for m in all_memories:
                    lines.append(f"## [{m.type}] {m.summary}")
                    lines.append(f"- **ID**: `{m.id}`")
                    if m.session_id:
                        lines.append(f"- **Session**: `{m.session_id}`")
                    if m.created_at:
                        lines.append(f"- **Created**: {m.created_at}")
                    if m.content:
                        lines.append(f"\n{m.content}\n")
                    lines.append("---\n")
                out = "\n".join(lines)
            else:
                out = json.dumps([{"error": f"Unknown format: {fmt}"}], indent=2)

            if output:
                Path(output).write_text(out, encoding="utf-8")
                print(f"Exported {len(all_memories)} memories to {output} ({fmt})")
            else:
                print(out)

    asyncio.run(_run())


def cmd_list(args):
    """List memories with optional filtering."""
    client, ns, prof = _get_client()
    type_filter = args.type
    session_filter = args.session
    limit = args.limit

    async def _run():
        async with client:
            all_entries = []
            page = 1
            while len(all_entries) < limit:
                entries = await client.list_memories(page=page, per_page=min(100, limit - len(all_entries)))
                if not entries:
                    break
                for entry in entries:
                    if type_filter and entry.type != type_filter:
                        continue
                    if session_filter and entry.session_id != session_filter:
                        continue
                    all_entries.append(entry)
                    if len(all_entries) >= limit:
                        break
                page += 1

            for m in all_entries[:limit]:
                sid = f" [{m.session_id}]" if m.session_id else ""
                ts = f" ({m.created_at[:10]})" if m.created_at else ""
                print(f"  {m.id}  {m.type:10}  {m.summary[:60]}{sid}{ts}")

            if not all_entries:
                print("  (no memories)")

    asyncio.run(_run())


def register_cli(subparser) -> None:
    """Build the hermes cloudflare-memory argparse tree."""
    subs = subparser.add_subparsers(dest="cf_memory_cmd")

    subs.add_parser("status", help="Show provider status and connection info")
    subs.add_parser("test", help="Run connectivity + write/read test")

    p_list = subs.add_parser("list", help="List memories with filtering")
    p_list.add_argument("--type", help="Filter by type (fact, instruction, event, etc.)")
    p_list.add_argument("--session", help="Filter by session ID")
    p_list.add_argument("--limit", type=int, default=50, help="Max results (default 50)")

    p_export = subs.add_parser("export", help="Export all memories to file")
    p_export.add_argument("--format", choices=["json", "jsonl", "markdown"], default="json", help="Output format")
    p_export.add_argument("--output", "-o", help="Output file path (stdout if omitted)")
    p_export.add_argument("--type", help="Filter by type")
    p_export.add_argument("--session", help="Filter by session ID")

    p_ns = subs.add_parser("namespaces", help="List all namespaces")

    p_create = subs.add_parser("create-ns", help="Create a namespace")
    p_create.add_argument("name", help="Namespace name (≤32 chars)")

    p_delete = subs.add_parser("delete-ns", help="Delete a namespace")
    p_delete.add_argument("name", help="Namespace name")

    subs.add_parser("card", help="Print A2A agent card JSON")

    def _dispatch(args):
        cmd = getattr(args, "cf_memory_cmd", None)
        if cmd == "status":
            cmd_status(args)
        elif cmd == "test":
            cmd_test(args)
        elif cmd == "list":
            cmd_list(args)
        elif cmd == "export":
            cmd_export(args)
        elif cmd == "namespaces":
            cmd_namespaces(args)
        elif cmd == "create-ns":
            cmd_create_ns(args)
        elif cmd == "delete-ns":
            cmd_delete_ns(args)
        elif cmd == "card":
            from cloudflare_memory.a2a_card import AGENT_CARD
            print(json.dumps(AGENT_CARD, indent=2))
        else:
            subparser.print_help()

    subparser.set_defaults(func=_dispatch)
