"""HTTP client for Cloudflare Agent Memory REST API.

All methods are async.  Sync wrappers provided for convenience.
Latency reality (Vultr SIN → CF):
  remember  1.3–3.8 s   recall ~5 s   ingest return ~2 s (write 3–8 s later)
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any

import httpx

_BASE = "https://api.cloudflare.com/client/v4/accounts"

# ── limits (from official docs) ──────────────────────────────────────
MAX_NAMESPACE_NAME = 32
MAX_PROFILE_NAME = 100
MAX_SESSION_ID = 64
MAX_RECALL_QUERY = 1024  # 1 KB UTF-8
MAX_CONTENT_BYTES = 32_768  # 32 KB UTF-8
MAX_INGEST_MESSAGES = 500
LIST_PAGE_MAX = 1000


class MemoryAPIError(Exception):
    """Cloudflare Agent Memory API error."""

    def __init__(self, status: int, code: int, message: str, raw: Any = None):
        self.status = status
        self.code = code
        self.message = message
        self.raw = raw
        super().__init__(f"HTTP {status} [{code}]: {message}")


@dataclass
class MemoryEntry:
    id: str
    type: str
    summary: str
    content: str | None = None
    session_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @classmethod
    def from_dict(cls, d: dict) -> MemoryEntry:
        return cls(
            id=d["id"],
            type=d.get("type", ""),
            summary=d.get("summary", ""),
            content=d.get("content"),
            session_id=d.get("sessionId"),
            created_at=d.get("createdAt"),
            updated_at=d.get("updatedAt"),
        )


@dataclass
class RecallResult:
    answer: str
    candidates: list[MemoryEntry]

    @classmethod
    def from_dict(cls, d: dict) -> RecallResult:
        return cls(
            answer=d.get("answer", ""),
            candidates=[MemoryEntry.from_dict(c) for c in d.get("candidates", [])],
        )


@dataclass
class CloudflareMemoryClient:
    """Async client for Cloudflare Agent Memory HTTP API.

    Parameters
    ----------
    account_id : str
        Cloudflare account ID (not secret).
    api_token : str
        Bearer token with Agent Memory permission.
    namespace : str
        Namespace name (≤32 chars).  Created on first write if missing.
    profile : str
        Profile name (≤100 chars).  Created on first write if missing.
    timeout : float
        Per-request timeout in seconds.  Default 30 (recall can be slow).
    """

    account_id: str
    api_token: str
    namespace: str = "hermes"
    profile: str = "default"
    timeout: float = 30.0
    _client: httpx.AsyncClient = field(default=None, repr=False)  # type: ignore[assignment]

    # ── lifecycle ─────────────────────────────────────────────────────
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=f"{_BASE}/{self.account_id}/agent-memory",
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "User-Agent": "cf-memory-plugin/0.1.0",
                },
                timeout=httpx.Timeout(self.timeout),
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()

    # ── helpers ───────────────────────────────────────────────────────
    def _ns_path(self, *parts: str) -> str:
        return f"/namespaces/{self.namespace}/" + "/".join(parts)

    def _profile_path(self, *parts: str) -> str:
        return f"/namespaces/{self.namespace}/profiles/{self.profile}/" + "/".join(parts)

    @staticmethod
    def _check(resp: httpx.Response) -> dict:
        """Raise MemoryAPIError on non-success."""
        data = resp.json()
        if not data.get("success"):
            errors = data.get("errors", [])
            err = errors[0] if errors else {"code": 0, "message": "unknown"}
            raise MemoryAPIError(resp.status_code, err["code"], err["message"], data)
        return data

    # ── namespace management ──────────────────────────────────────────
    async def list_namespaces(self) -> list[dict]:
        c = await self._get_client()
        r = await c.get("/namespaces")
        return self._check(r).get("result", [])

    async def create_namespace(self, name: str | None = None) -> dict:
        c = await self._get_client()
        r = await c.post("/namespaces", json={"name": name or self.namespace})
        return self._check(r).get("result", {})

    async def delete_namespace(self, name: str | None = None) -> dict:
        c = await self._get_client()
        r = await c.delete(f"/namespaces/{name or self.namespace}")
        return self._check(r).get("result", {})

    # ── remember (single memory, 1.3–3.8s) ───────────────────────────
    async def remember(
        self,
        content: str,
        session_id: str | None = None,
    ) -> MemoryEntry:
        """Store one memory.  Returns type+summary assigned by CF.

        Latency: 1.3–3.8s.  Do NOT call in a tight loop.
        """
        body: dict[str, Any] = {"content": content}
        if session_id:
            body["sessionId"] = session_id
        c = await self._get_client()
        r = await c.post(self._profile_path("remember"), json=body)
        data = self._check(r)
        return MemoryEntry.from_dict(data["result"])

    # ── list (no content, fast ~0.4s) ─────────────────────────────────
    async def list_memories(
        self,
        page: int = 1,
        per_page: int = 20,
    ) -> list[MemoryEntry]:
        """List memories (omits content field)."""
        c = await self._get_client()
        r = await c.get(
            self._profile_path("memories"),
            params={"page": page, "perPage": min(per_page, LIST_PAGE_MAX)},
        )
        data = self._check(r)
        return [MemoryEntry.from_dict(m) for m in data.get("result", [])]

    # ── get (includes content, ~1.4s) ─────────────────────────────────
    async def get_memory(self, memory_id: str) -> MemoryEntry:
        """Get one memory by ID (includes content)."""
        c = await self._get_client()
        r = await c.get(self._profile_path("memories", memory_id))
        data = self._check(r)
        return MemoryEntry.from_dict(data["result"])

    # ── delete ────────────────────────────────────────────────────────
    async def delete_memory(self, memory_id: str) -> dict:
        c = await self._get_client()
        r = await c.delete(self._profile_path("memories", memory_id))
        return self._check(r).get("result", {})

    # ── recall (~5s, synthesized answer + candidates) ─────────────────
    async def recall(
        self,
        query: str,
        thinking_level: str = "low",
        response_length: str = "short",
    ) -> RecallResult:
        """Semantic recall.  Returns synthesized answer + candidates.

        Latency: ~5s.  Never block prefetch() on this.
        """
        if len(query.encode()) > MAX_RECALL_QUERY:
            raise ValueError(f"Query exceeds {MAX_RECALL_QUERY} bytes")
        c = await self._get_client()
        r = await c.post(
            self._profile_path("recall"),
            json={
                "query": query,
                "thinkingLevel": thinking_level,
                "responseLength": response_length,
            },
        )
        data = self._check(r)
        return RecallResult.from_dict(data["result"])

    # ── ingest (async, returns null, writes 3–8s later) ───────────────
    async def ingest(
        self,
        messages: list[dict[str, str]],
        session_id: str | None = None,
    ) -> dict:
        """Ingest conversation messages.  Extraction is async.

        Returns immediately with result:null.
        Memories appear in list 3–8s later.
        Max 500 messages, each ≤32KB.
        """
        if len(messages) > MAX_INGEST_MESSAGES:
            raise ValueError(f"Max {MAX_INGEST_MESSAGES} messages per ingest")
        body: dict[str, Any] = {"messages": messages}
        if session_id:
            body["sessionId"] = session_id
        c = await self._get_client()
        r = await c.post(self._profile_path("ingest"), json=body)
        return self._check(r)

    # ── summary (POST only — GET 404s) ────────────────────────────────
    async def get_summary(self) -> str:
        """POST /summary returns markdown summary.  GET does NOT work."""
        c = await self._get_client()
        r = await c.post(self._profile_path("summary"), json={})
        data = self._check(r)
        return data.get("result", {}).get("summary", "")

    # ── sync convenience ──────────────────────────────────────────────
    def remember_sync(self, content: str, session_id: str | None = None) -> MemoryEntry:
        return asyncio.get_event_loop().run_until_complete(
            self.remember(content, session_id)
        )

    def recall_sync(self, query: str, **kw) -> RecallResult:
        return asyncio.get_event_loop().run_until_complete(self.recall(query, **kw))
