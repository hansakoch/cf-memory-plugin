"""A2A Agent Card for Cloudflare Memory.

Exposes cloudflare-memory as an A2A-compliant agent that other agents
can discover and call for memory operations.
"""

AGENT_CARD = {
    "name": "cloudflare-memory",
    "description": "CF Memory Plugin — persistent cross-session memory for AI agents via Cloudflare Agent Memory. Supports remember, recall, ingest, summary.",
    "url": "http://localhost:9120",
    "version": "0.1.0",
    "capabilities": {
        "streaming": False,
        "pushNotifications": False,
        "stateTransitionHistory": False,
    },
    "skills": [
        {
            "id": "remember",
            "name": "Remember",
            "description": "Store a single memory. Returns type + summary assigned by Cloudflare. Latency: 1.3–3.8s.",
            "tags": ["memory", "storage", "facts"],
        },
        {
            "id": "recall",
            "name": "Recall",
            "description": "Semantic search across stored memories. Returns synthesized answer + candidate memories. Latency: ~5s.",
            "tags": ["memory", "search", "recall"],
        },
        {
            "id": "ingest",
            "name": "Ingest",
            "description": "Ingest conversation messages for automatic fact/event/instruction extraction. Max 500 messages. Async — memories appear 3–8s later.",
            "tags": ["memory", "extraction", "conversation"],
        },
        {
            "id": "list",
            "name": "List Memories",
            "description": "List stored memories (omits content). Fast ~0.4s.",
            "tags": ["memory", "list"],
        },
        {
            "id": "get",
            "name": "Get Memory",
            "description": "Get a single memory by ID (includes full content). ~1.4s.",
            "tags": ["memory", "get"],
        },
        {
            "id": "summary",
            "name": "Profile Summary",
            "description": "Get a markdown summary of everything stored in a profile.",
            "tags": ["memory", "summary"],
        },
    ],
}
