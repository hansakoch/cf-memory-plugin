#!/usr/bin/env python3
"""Ingest ALL session data into CF Agent Memory.

Sources:
1. Vultr Hermes sessions (alfred, ffm, default profiles) via SSH
2. Local Grok CLI sessions (JSONL chat_history files)
3. Local mimocode sessions (checkpoint.md, notes.md)

Usage:
    source ~/.vault/cloudflare.env && export CLOUDFLARE_API_TOKEN CLOUDFLARE_ACCOUNT_ID
    python3 ingest_all.py [--dry-run] [--source vultr|local|all]
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

MAX_CONTENT_BYTES = 32000
MAX_MESSAGES_PER_INGEST = 500
RATE_LIMIT_DELAY = 1.5
VULTR_HOST = "vultr"
REMOTE_HERMES_HOME = "/home/fansfollow/.hermes"
LOCAL_GROK_SESSIONS = Path.home() / ".grok" / "sessions"
LOCAL_MIMOCODE_MEMORY = Path.home() / ".local" / "share" / "mimocode" / "memory"

CF_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", "")
CF_ACCOUNT = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
CF_BASE = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT}/agent-memory"


def truncate(content: str, max_bytes: int = MAX_CONTENT_BYTES) -> str:
    if not content:
        return ""
    encoded = content.encode("utf-8")
    if len(encoded) <= max_bytes:
        return content
    return encoded[:max_bytes].decode("utf-8", errors="ignore") + "..."


def ingest_batch(batch: list[dict], session_id: str, namespace: str = "hermes", profile: str = "default") -> bool:
    if not CF_TOKEN or not CF_ACCOUNT:
        print("ERROR: CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID must be set", file=sys.stderr)
        return False

    url = f"{CF_BASE}/namespaces/{namespace}/profiles/{profile}/ingest"
    payload = {"messages": batch, "sessionId": session_id}
    payload_json = json.dumps(payload)

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(payload_json)
            payload_file = f.name

        cmd = [
            "curl", "-s", "-X", "POST", url,
            "-H", f"Authorization: Bearer {CF_TOKEN}",
            "-H", "Content-Type: application/json",
            "-d", f"@{payload_file}",
            "--max-time", "30",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
        os.unlink(payload_file)

        if result.returncode != 0:
            print(f"  WARNING: curl failed (exit {result.returncode})", file=sys.stderr)
            return False
        data = json.loads(result.stdout)
        if data.get("success"):
            return True
        else:
            errors = data.get("errors", [])
            print(f"  WARNING: API error: {errors}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"  WARNING: ingest failed: {e}", file=sys.stderr)
        return False


# ── Vultr Hermes Sessions ──────────────────────────────────────────

def query_remote_db(profile: str, query: str) -> list[dict]:
    db_path = f"{REMOTE_HERMES_HOME}/profiles/{profile}/state.db"
    cmd = ["ssh", VULTR_HOST, f'sqlite3 -json "{db_path}" "{query}"']
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0 or not result.stdout.strip():
            return []
        return json.loads(result.stdout)
    except Exception as e:
        print(f"  Warning: remote query failed for {profile}: {e}", file=sys.stderr)
        return []


def ingest_vultr_sessions(namespace: str, dry_run: bool, limit: int) -> int:
    profiles = ["alfred", "ffm", "default"]
    total = 0

    for profile in profiles:
        print(f"\n─── Vultr Profile: {profile} ───")
        query = "SELECT id, title, message_count FROM sessions ORDER BY last_activity_at DESC"
        if limit:
            query += f" LIMIT {limit}"
        sessions = query_remote_db(profile, query)
        print(f"  Found {len(sessions)} sessions")

        for session in sessions:
            sid = session.get("id", "?")
            title = session.get("title", "")
            msg_count = session.get("message_count", 0)

            if msg_count < 3:
                continue

            safe_id = sid.replace("'", "''")
            msg_query = f"""
                SELECT role, content, timestamp FROM messages
                WHERE session_id = '{safe_id}'
                  AND role IN ('user', 'assistant')
                  AND content IS NOT NULL
                  AND length(content) > 10
                  AND tool_call_id IS NULL
                ORDER BY timestamp
            """
            messages = query_remote_db(profile, msg_query)
            if not messages:
                continue

            ingest_msgs = []
            for m in messages:
                content = truncate(m.get("content", ""))
                if content:
                    ingest_msgs.append({"role": m["role"], "content": content})

            if not ingest_msgs:
                continue

            display = title or sid[:30]
            print(f"  [{display[:40]:40s}] {len(ingest_msgs)} msgs")

            if dry_run:
                total += len(ingest_msgs)
                continue

            for i in range(0, len(ingest_msgs), MAX_MESSAGES_PER_INGEST):
                batch = ingest_msgs[i:i + MAX_MESSAGES_PER_INGEST]
                session_id = f"vultr/{profile}/{sid}"
                if len(ingest_msgs) > MAX_MESSAGES_PER_INGEST:
                    session_id += f"/batch{i}"
                success = ingest_batch(batch, session_id, namespace, profile)
                if success:
                    total += len(batch)
                    print(f"    ✓ {len(batch)} msgs")
                else:
                    print(f"    ✗ FAILED")
                time.sleep(RATE_LIMIT_DELAY)

            time.sleep(0.5)

    return total


# ── Local Grok CLI Sessions ────────────────────────────────────────

def ingest_local_grok_sessions(namespace: str, dry_run: bool) -> int:
    total = 0
    session_dirs = []

    for session_file in LOCAL_GROK_SESSIONS.rglob("chat_history.jsonl"):
        session_dirs.append(session_file.parent)

    print(f"\n─── Local Grok Sessions: {len(session_dirs)} found ───")

    for session_dir in session_dirs:
        chat_file = session_dir / "chat_history.jsonl"
        if not chat_file.exists():
            continue

        session_id = session_dir.name
        title = ""
        summary_file = session_dir / "summary.json"
        if summary_file.exists():
            try:
                with open(summary_file) as f:
                    title = json.load(f).get("title", "")
            except:
                pass

        messages = []
        try:
            with open(chat_file) as f:
                for line in f:
                    try:
                        d = json.loads(line)
                        if d.get("type") in ("user", "assistant"):
                            content = d.get("content", "")
                            if isinstance(content, list):
                                texts = []
                                for c in content:
                                    if isinstance(c, dict) and c.get("type") == "text":
                                        texts.append(c["text"])
                                content = "\n".join(texts)
                            if isinstance(content, str) and len(content) > 20:
                                if not content.startswith("You are Grok"):
                                    truncated = truncate(content)
                                    if truncated:
                                        messages.append({"role": d["type"], "content": truncated})
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"  Warning: failed to read {chat_file}: {e}", file=sys.stderr)
            continue

        if len(messages) < 2:
            continue

        display = title or session_id[:30]
        print(f"  [{display[:40]:40s}] {len(messages)} msgs")

        if dry_run:
            total += len(messages)
            continue

        for i in range(0, len(messages), MAX_MESSAGES_PER_INGEST):
            batch = messages[i:i + MAX_MESSAGES_PER_INGEST]
            sid = f"grok-local/{session_id}"
            if len(messages) > MAX_MESSAGES_PER_INGEST:
                sid += f"/batch{i}"
            success = ingest_batch(batch, sid, namespace, "default")
            if success:
                total += len(batch)
                print(f"    ✓ {len(batch)} msgs")
            else:
                print(f"    ✗ FAILED")
            time.sleep(RATE_LIMIT_DELAY)

        time.sleep(0.5)

    return total


# ── Local Mimocode Sessions ────────────────────────────────────────

def ingest_local_mimocode_sessions(namespace: str, dry_run: bool) -> int:
    total = 0
    sessions_dir = LOCAL_MIMOCODE_MEMORY / "sessions"

    if not sessions_dir.exists():
        print("\n─── No mimocode sessions found ───")
        return 0

    session_dirs = [d for d in sessions_dir.iterdir() if d.is_dir()]
    print(f"\n─── Local Mimocode Sessions: {len(session_dirs)} found ───")

    for session_dir in session_dirs:
        session_id = session_dir.name
        content_parts = []

        checkpoint = session_dir / "checkpoint.md"
        if checkpoint.exists():
            try:
                content_parts.append(f"## Checkpoint\n{checkpoint.read_text()}")
            except:
                pass

        notes = session_dir / "notes.md"
        if notes.exists():
            try:
                notes_text = notes.read_text().strip()
                if notes_text and len(notes_text) > 50:
                    content_parts.append(f"## Notes\n{notes_text}")
            except:
                pass

        if not content_parts:
            continue

        full_content = "\n\n".join(content_parts)
        if len(full_content) < 50:
            continue

        truncated = truncate(full_content)
        messages = [{"role": "user", "content": f"Session context for {session_id}:\n{truncated}"}]

        print(f"  [{session_id[:40]:40s}] {len(full_content)} chars")

        if dry_run:
            total += 1
            continue

        success = ingest_batch(messages, f"mimocode/{session_id}", namespace, "default")
        if success:
            total += 1
            print(f"    ✓ ingested")
        else:
            print(f"    ✗ FAILED")
        time.sleep(RATE_LIMIT_DELAY)

    return total


def main():
    parser = argparse.ArgumentParser(description="Ingest ALL session data into CF Agent Memory")
    parser.add_argument("--source", choices=["vultr", "local", "all"], default="all")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="Limit sessions per source (0=all)")
    parser.add_argument("--namespace", default="hermes")
    args = parser.parse_args()

    print("=" * 60)
    print("CF AGENT MEMORY — FULL INGEST")
    print("=" * 60)
    print(f"Source: {args.source}")
    print(f"Namespace: {args.namespace}")
    print(f"Dry run: {args.dry_run}")
    print()

    total = 0

    if args.source in ("vultr", "all"):
        total += ingest_vultr_sessions(args.namespace, args.dry_run, args.limit)

    if args.source in ("local", "all"):
        total += ingest_local_grok_sessions(args.namespace, args.dry_run)
        total += ingest_local_mimocode_sessions(args.namespace, args.dry_run)

    print("\n" + "=" * 60)
    print(f"TOTAL MESSAGES {'(would be) ' if args.dry_run else ''}INGESTED: {total}")
    print("=" * 60)


if __name__ == "__main__":
    main()
