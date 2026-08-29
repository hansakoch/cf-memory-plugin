#!/usr/bin/env python3
"""Bulk ingest all Hermes sessions into CF Agent Memory.

Reads from Hermes state.db on Vultr, batches messages, and sends to
Cloudflare Agent Memory. Handles rate limits and timeouts.

Usage:
    source ~/.vault/cloudflare.env && export CLOUDFLARE_API_TOKEN CF_ACCOUNT_ID
    python3 bulk_ingest.py [--profile alfred] [--dry-run] [--limit 10]
"""

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────
VULTR_HOST = "vultr"
MAX_MESSAGES_PER_INGEST = 500
MAX_CONTENT_BYTES = 32000  # 32KB per message
RATE_LIMIT_DELAY = 2  # seconds between ingest calls
REMOTE_HERMES_HOME = "/home/fansfollow/.hermes"

# Read credentials once at import time
CF_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", "")
CF_ACCOUNT = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")

PROFILES = [
    "alfred",
    "ffm",
    "default",
]


def get_session_db_path(profile: str) -> str:
    """Return the remote path to a profile's state.db."""
    return f"{REMOTE_HERMES_HOME}/profiles/{profile}/state.db"


def query_remote_db(profile: str, query: str) -> list[dict]:
    """Run a query on the remote SQLite DB and return rows as dicts."""
    db_path = get_session_db_path(profile)
    cmd = [
        "ssh", "-i", os.path.expanduser("~/.ssh/id_ed25519_vultr"),
        VULTR_HOST,
        f'sqlite3 -json "{db_path}" "{query}"'
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return []
        if not result.stdout.strip():
            return []
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
        print(f"  Warning: query failed for {profile}: {e}", file=sys.stderr)
        return []


def get_sessions(profile: str, limit: int = 0) -> list[dict]:
    """Get all sessions for a profile."""
    query = "SELECT id, datetime(started_at, 'unixepoch') as started, title, message_count FROM sessions ORDER BY started_at DESC"
    if limit:
        query += f" LIMIT {limit}"
    return query_remote_db(profile, query)


def get_messages(profile: str, session_id: str) -> list[dict]:
    """Get user/assistant messages for a session."""
    # Escape single quotes in session_id
    safe_id = session_id.replace("'", "''")
    query = f"""
        SELECT role, content, timestamp
        FROM messages
        WHERE session_id = '{safe_id}'
          AND role IN ('user', 'assistant')
          AND content IS NOT NULL
          AND length(content) > 10
          AND tool_call_id IS NULL
        ORDER BY timestamp
    """
    return query_remote_db(profile, query)


def truncate_content(content: str, max_bytes: int = MAX_CONTENT_BYTES) -> str:
    """Truncate content to max bytes."""
    if not content:
        return ""
    encoded = content.encode("utf-8")
    if len(encoded) <= max_bytes:
        return content
    return encoded[:max_bytes].decode("utf-8", errors="ignore") + "..."


def batch_messages(messages: list[dict], batch_size: int = MAX_MESSAGES_PER_INGEST) -> list[list[dict]]:
    """Split messages into batches."""
    batches = []
    for i in range(0, len(messages), batch_size):
        batch = messages[i:i + batch_size]
        batches.append(batch)
    return batches


def ingest_batch(batch: list[dict], session_id: str, namespace: str = "hermes", profile: str = "default") -> bool:
    """Send a batch to CF Agent Memory via the API."""
    token = CF_TOKEN
    account = CF_ACCOUNT
    if not token or not account:
        print("ERROR: CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID must be set", file=sys.stderr)
        return False

    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/agent-memory/namespaces/{namespace}/profiles/{profile}/ingest"
    payload = {
        "messages": batch,
        "sessionId": session_id,
    }

    # Write payload to temp file to avoid arg list too long
    payload_json = json.dumps(payload)
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(payload_json)
            payload_file = f.name

        cmd = [
            "curl", "-s", "-X", "POST", url,
            "-H", f"Authorization: Bearer {token}",
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


def main():
    parser = argparse.ArgumentParser(description="Bulk ingest Hermes sessions into CF Agent Memory")
    parser.add_argument("--profile", choices=PROFILES + ["all"], default="all", help="Profile to ingest")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be ingested without doing it")
    parser.add_argument("--limit", type=int, default=0, help="Limit sessions per profile (0=all)")
    parser.add_argument("--namespace", default="hermes", help="CF Agent Memory namespace")
    parser.add_argument("--min-messages", type=int, default=5, help="Skip sessions with fewer than N messages")
    args = parser.parse_args()

    profiles = PROFILES if args.profile == "all" else [args.profile]
    total_sessions = 0
    total_messages = 0
    total_ingested = 0
    total_skipped = 0

    print("=" * 60)
    print("CF AGENT MEMORY — BULK INGEST")
    print("=" * 60)
    print(f"Profiles: {profiles}")
    print(f"Namespace: {args.namespace}")
    print(f"Dry run: {args.dry_run}")
    print(f"Min messages: {args.min_messages}")
    print()

    for profile in profiles:
        print(f"─── Profile: {profile} ───")
        sessions = get_sessions(profile, args.limit)
        print(f"  Found {len(sessions)} sessions")

        for session in sessions:
            session_id = session.get("id", "?")
            title = session.get("title", "")
            msg_count = session.get("message_count", 0)
            started = session.get("started", "?")

            if msg_count < args.min_messages:
                total_skipped += 1
                continue

            total_sessions += 1

            # Get messages
            messages = get_messages(profile, session_id)
            if not messages:
                total_skipped += 1
                continue

            total_messages += len(messages)

            # Format for ingest
            ingest_messages = []
            for m in messages:
                role = m.get("role", "user")
                content = truncate_content(m.get("content", ""))
                if content:
                    ingest_messages.append({"role": role, "content": content})

            if not ingest_messages:
                total_skipped += 1
                continue

            display_title = title or session_id[:30]
            print(f"  [{started[:10]}] {display_title[:40]:40s} ({len(ingest_messages)} msgs)")

            if args.dry_run:
                total_ingested += len(ingest_messages)
                continue

            # Batch and ingest
            batches = batch_messages(ingest_messages)
            for i, batch in enumerate(batches):
                sid = f"hermes/{profile}/{session_id}"
                if len(batches) > 1:
                    sid += f"/batch{i}"

                success = ingest_batch(batch, sid, args.namespace)
                if success:
                    total_ingested += len(batch)
                else:
                    print(f"    FAILED batch {i+1}/{len(batches)}")

                # Rate limit
                if i < len(batches) - 1:
                    time.sleep(RATE_LIMIT_DELAY)

            # Small delay between sessions
            time.sleep(1)

        print()

    print("=" * 60)
    print(f"SUMMARY")
    print(f"  Sessions processed: {total_sessions}")
    print(f"  Sessions skipped:   {total_skipped}")
    print(f"  Messages found:     {total_messages}")
    print(f"  Messages ingested:  {total_ingested}")
    print("=" * 60)


if __name__ == "__main__":
    main()
