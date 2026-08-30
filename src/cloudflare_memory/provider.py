"""Hermes MemoryProvider for Cloudflare Agent Memory.

Design constraints (from live retesting 2026-08-23):
  - remember 1.3–3.8s, recall ~5s → prefetch() must NEVER block on recall
  - sync_turn() MUST be non-blocking (ingest is async, writes 3–8s later)
  - list omits content; get includes it
  - POST /summary works; GET /summary 404s
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.memory_provider import MemoryProvider, RecallStatus

from cloudflare_memory.client import CloudflareMemoryClient, MemoryAPIError

logger = logging.getLogger(__name__)

# ── cache config ──────────────────────────────────────────────────────
_CACHE_TTL = 600  # 10 min — longer TTL reduces redundant CF calls
_CACHE_MAX = 128  # more entries for multi-profile setups


class _RecallCache:
    """Simple TTL cache for recall results."""

    def __init__(self, ttl: int = _CACHE_TTL, maxsize: int = _CACHE_MAX):
        self._cache: dict[str, tuple[float, str, int]] = {}
        self._ttl = ttl
        self._max = maxsize

    def get(self, key: str) -> tuple[str, int] | None:
        entry = self._cache.get(key)
        if entry and (time.monotonic() - entry[0]) < self._ttl:
            return entry[1], entry[2]
        return None

    def put(self, key: str, text: str, count: int) -> None:
        if len(self._cache) >= self._max:
            oldest = min(self._cache, key=lambda k: self._cache[k][0])
            del self._cache[oldest]
        self._cache[key] = (time.monotonic(), text, count)

    def invalidate(self) -> None:
        self._cache.clear()


class _AsyncRunner:
    """Persistent background event loop for running async code from sync.

    Avoids the 'Event loop is closed' problem where asyncio.run() creates
    and destroys a loop each call, orphaning httpx clients.
    """

    def __init__(self):
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._started = threading.Event()

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._started.set()
        self._loop.run_forever()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._started.wait(timeout=5)

    def run(self, coro):
        """Run an async coroutine on the background loop. Blocks until done."""
        if not self._loop or self._loop.is_closed():
            self.start()
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=60)

    def run_fire_and_forget(self, coro):
        """Fire an async coroutine without waiting for the result."""
        if not self._loop or self._loop.is_closed():
            self.start()
        asyncio.run_coroutine_threadsafe(coro, self._loop)

    def stop(self):
        if self._loop and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._loop.stop)
            if self._thread:
                self._thread.join(timeout=5)


def register(ctx) -> None:
    """Entry point for hermes_agent.memory_providers discovery."""
    ctx.register_memory_provider(CloudflareMemoryProvider())


class CloudflareMemoryProvider(MemoryProvider):
    """Cloudflare Agent Memory provider for Hermes."""

    def __init__(self):
        self._client: CloudflareMemoryClient | None = None
        self._session_id: str = ""
        self._hermes_home: str = ""
        self._cache = _RecallCache()
        self._bg_thread: threading.Thread | None = None
        self._pending_recall_query: str = ""
        self._last_recall_text: str = ""
        self._last_recall_count: int = 0
        self._namespace: str = "hermes"
        self._profile: str = "default"
        self._runner = _AsyncRunner()
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="cf-mem")

    # ── identity ──────────────────────────────────────────────────────
    @property
    def name(self) -> str:
        return "cloudflare-memory"

    # ── availability (no network) ─────────────────────────────────────
    def is_available(self) -> bool:
        return bool(os.environ.get("MCP_CLOUDFLARE_API_KEY"))

    def unavailable_reason(self) -> str:
        if not os.environ.get("MCP_CLOUDFLARE_API_KEY"):
            return "Set MCP_CLOUDFLARE_API_KEY in ~/.hermes/.env"
        return ""

    # ── lifecycle ─────────────────────────────────────────────────────
    def initialize(self, session_id: str, **kwargs) -> None:
        self._session_id = session_id
        self._hermes_home = kwargs.get("hermes_home", "")

        # Read optional config
        config_path = Path(self._hermes_home) / "cloudflare-memory.json"
        if config_path.exists():
            try:
                cfg = json.loads(config_path.read_text())
                self._namespace = cfg.get("namespace", self._namespace)
                self._profile = cfg.get("profile", self._profile)
            except Exception:
                pass

        # Start the persistent async runner
        self._runner.start()

        from cloudflare_memory.credentials import require_account_id, require_token

        self._client = CloudflareMemoryClient(
            account_id=require_account_id(),
            api_token=require_token(),
            namespace=self._namespace,
            profile=self._profile,
        )
        logger.info(
            "CloudflareMemoryProvider initialized: ns=%s profile=%s session=%s",
            self._namespace, self._profile, session_id,
        )

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False)
        if self._client:
            try:
                self._runner.run(self._client.close())
            except Exception:
                pass
            self._client = None
        self._runner.stop()

    # ── system prompt ─────────────────────────────────────────────────
    def system_prompt_block(self) -> str:
        return (
            f"[CF Memory: ns={self._namespace} profile={self._profile}. "
            f"cf_remember to store, cf_recall to search.]"
        )

    # ── prefetch (MUST be fast) ───────────────────────────────────────
    def prefetch(self, query: str, *, session_id: str = "") -> str:
        """Return cached recall context. Never blocks on live recall."""
        if not query or not self._client:
            return ""

        cache_key = query[:256]
        cached = self._cache.get(cache_key)
        if cached:
            self._last_recall_text, self._last_recall_count = cached
            return cached[0]

        # Cache miss — fire background recall, return empty this turn
        self._fire_background_recall(query, session_id)
        return ""

    def queue_prefetch(self, query: str, *, session_id: str = "") -> None:
        """Warm the cache for the next turn (background, non-blocking)."""
        if not query or not self._client:
            return
        self._fire_background_recall(query, session_id)

    def _fire_background_recall(self, query: str, session_id: str) -> None:
        """Fire recall in a daemon thread, cache the result. Deduplicates."""
        if self._bg_thread and self._bg_thread.is_alive():
            # Already running — just update the pending query for next turn
            self._pending_recall_query = query
            return

        def _do_recall():
            try:
                result = self._runner.run(self._client.recall(query))
                text = result.answer
                count = len(result.candidates)
                if text:
                    formatted = f"[CF Memory recall]: {text}"
                    self._cache.put(query[:256], formatted, count)
                    self._last_recall_text = formatted
                    self._last_recall_count = count
                # Process any pending query that arrived while we were working
                pending = self._pending_recall_query
                if pending and pending != query:
                    self._pending_recall_query = ""
                    try:
                        result2 = self._runner.run(self._client.recall(pending))
                        if result2.answer:
                            formatted2 = f"[CF Memory recall]: {result2.answer}"
                            self._cache.put(pending[:256], formatted2, len(result2.candidates))
                    except Exception:
                        pass
            except Exception as e:
                logger.debug("Background recall failed: %s", e)

        self._bg_thread = threading.Thread(target=_do_recall, daemon=True)
        self._bg_thread.start()

    def recall_status(self) -> Optional[RecallStatus]:
        if self._last_recall_text:
            return RecallStatus(
                provider_label="CF Memory",
                count=self._last_recall_count,
                glyph="☁️",
            )
        return None

    # ── sync_turn (MUST be non-blocking) ──────────────────────────────
    def sync_turn(
        self,
        user_content: str,
        assistant_content: str,
        *,
        session_id: str = "",
        messages: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Ingest turn to CF Agent Memory. Non-blocking (thread pool).

        ingest() returns immediately with result:null;
        memories appear 3–8s later.
        """
        if not self._client:
            return

        # Skip trivial prompts
        from agent.memory_provider import is_trivial_prompt
        if is_trivial_prompt(user_content):
            return

        def _do_ingest():
            try:
                msg_list = messages or [
                    {"role": "user", "content": user_content},
                    {"role": "assistant", "content": assistant_content},
                ]
                self._runner.run(self._client.ingest(
                    msg_list,
                    session_id=session_id or self._session_id,
                ))
                logger.debug("CF Memory ingest submitted")
            except Exception as e:
                logger.warning("CF Memory ingest failed: %s", e)

        self._executor.submit(_do_ingest)

    # ── tools ─────────────────────────────────────────────────────────
    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "cf_remember",
                "description": "Store one fact in CF Agent Memory (~2s).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string"},
                    },
                    "required": ["content"],
                },
            },
            {
                "name": "cf_recall",
                "description": "Semantic search in CF Agent Memory (~5s).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "cf_list",
                "description": "List memories (no content). ~0.4s.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "page": {"type": "integer", "default": 1},
                        "per_page": {"type": "integer", "default": 20},
                    },
                },
            },
            {
                "name": "cf_get",
                "description": "Get one memory by ID (with content). ~1.4s.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "memory_id": {"type": "string"},
                    },
                    "required": ["memory_id"],
                },
            },
            {
                "name": "cf_summary",
                "description": "Markdown summary of stored memories.",
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "name": "cf_delete",
                "description": "Delete a memory by ID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "memory_id": {"type": "string"},
                    },
                    "required": ["memory_id"],
                },
            },
        ]

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        if not self._client:
            return json.dumps({"error": "Provider not initialized"})

        try:
            if tool_name == "cf_remember":
                entry = self._runner.run(self._client.remember(args["content"]))
                return json.dumps({
                    "id": entry.id, "type": entry.type, "summary": entry.summary,
                })

            elif tool_name == "cf_recall":
                result = self._runner.run(self._client.recall(args["query"]))
                return json.dumps({
                    "answer": result.answer,
                    "candidates": [
                        {"id": c.id, "type": c.type, "summary": c.summary}
                        for c in result.candidates
                    ],
                })

            elif tool_name == "cf_list":
                entries = self._runner.run(self._client.list_memories(
                    page=args.get("page", 1),
                    per_page=args.get("per_page", 20),
                ))
                return json.dumps([
                    {"id": e.id, "type": e.type, "summary": e.summary}
                    for e in entries
                ])

            elif tool_name == "cf_get":
                entry = self._runner.run(self._client.get_memory(args["memory_id"]))
                return json.dumps({
                    "id": entry.id, "type": entry.type,
                    "summary": entry.summary, "content": entry.content,
                })

            elif tool_name == "cf_summary":
                text = self._runner.run(self._client.get_summary())
                return json.dumps({"summary": text})

            elif tool_name == "cf_delete":
                result = self._runner.run(self._client.delete_memory(args["memory_id"]))
                return json.dumps(result)

            else:
                return json.dumps({"error": f"Unknown tool: {tool_name}"})

        except MemoryAPIError as e:
            return json.dumps({"error": str(e), "status": e.status, "code": e.code})
        except Exception as e:
            logger.exception("CF Memory tool %s failed", tool_name)
            return json.dumps({"error": str(e)})

    # ── on_session_end ────────────────────────────────────────────────
    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        """Ingest the full session on end for fact extraction."""
        if not self._client or not messages:
            return

        def _do_end_ingest():
            try:
                # Convert to ingest format (role+content only)
                ingest_msgs = []
                for m in messages:
                    role = m.get("role", "")
                    content = m.get("content", "")
                    if role in ("user", "assistant") and content:
                        ingest_msgs.append({"role": role, "content": content})
                if ingest_msgs:
                    self._runner.run(self._client.ingest(
                        ingest_msgs[:500],  # CF limit
                        session_id=self._session_id,
                    ))
                    logger.info("CF Memory session-end ingest: %d messages", len(ingest_msgs))
            except Exception as e:
                logger.warning("CF Memory session-end ingest failed: %s", e)

        self._executor.submit(_do_end_ingest)

    # ── config schema ─────────────────────────────────────────────────
    def get_config_schema(self) -> List[Dict[str, Any]]:
        return [
            {
                "key": "api_key",
                "description": "Cloudflare API token with Agent Memory permission",
                "secret": True,
                "required": True,
                "env_var": "MCP_CLOUDFLARE_API_KEY",
                "url": "https://dash.cloudflare.com/profile/api-tokens",
            },
            {
                "key": "account_id",
                "description": "Cloudflare Account ID (from the dashboard sidebar)",
                "required": True,
                "env_var": "CF_ACCOUNT_ID",
                "url": "https://dash.cloudflare.com/",
            },
            {
                "key": "namespace",
                "description": "Agent Memory namespace name (≤32 chars)",
                "default": "hermes",
            },
            {
                "key": "profile",
                "description": "Agent Memory profile name (≤100 chars)",
                "default": "default",
            },
        ]

    def save_config(self, values: Dict[str, Any], hermes_home: str) -> None:
        config_path = Path(hermes_home) / "cloudflare-memory.json"
        config_path.write_text(json.dumps({
            "namespace": values.get("namespace", "hermes"),
            "profile": values.get("profile", "default"),
        }, indent=2))
