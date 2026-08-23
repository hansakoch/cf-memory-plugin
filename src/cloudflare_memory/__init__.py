"""Cloudflare Agent Memory — client, MCP server, Hermes provider."""

from cloudflare_memory.client import CloudflareMemoryClient

__all__ = ["CloudflareMemoryClient"]
__version__ = "0.1.0"


def register(ctx) -> None:
    """Entry point for hermes_agent.memory_providers discovery."""
    from cloudflare_memory.provider import CloudflareMemoryProvider
    ctx.register_memory_provider(CloudflareMemoryProvider())
