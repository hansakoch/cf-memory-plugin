"""Cloudflare Memory config schema — rendered by the generic desktop panel."""

from __future__ import annotations

import sys
from pathlib import Path

# When loaded by Hermes's config_schema loader, the parent plugins/memory
# package is on sys.path.  When loaded standalone (tests, pip), fall back
# to a relative import stub.
try:
    from plugins.memory.config_schema import (
        KIND_SECRET,
        KIND_SELECT,
        KIND_TEXT,
        STORAGE_FLAT_JSON,
        ProviderConfigSchema,
        ProviderField,
        ProviderFieldOption,
    )
except ImportError:
    # Minimal stubs so the module is importable outside Hermes
    KIND_TEXT = "text"
    KIND_SECRET = "secret"
    KIND_SELECT = "select"
    STORAGE_FLAT_JSON = "flat_json"

    class ProviderFieldOption:
        def __init__(self, value, label, description=""):
            self.value = value
            self.label = label
            self.description = description

    class ProviderField:
        def __init__(self, key, label, kind=KIND_TEXT, default="", description="",
                     placeholder="", options=(), env_key=None, inline=False, group=""):
            self.key = key
            self.label = label
            self.kind = kind
            self.default = default
            self.description = description
            self.placeholder = placeholder
            self.options = options
            self.env_key = env_key
            self.inline = inline
            self.group = group

    class ProviderConfigSchema:
        def __init__(self, name, label, storage, docs_url="", fields=()):
            self.name = name
            self.label = label
            self.storage = storage
            self.docs_url = docs_url
            self.fields = fields


CONFIG_SCHEMA = ProviderConfigSchema(
    name="cloudflare-memory",
    label="Cloudflare Memory",
    storage=STORAGE_FLAT_JSON,
    docs_url="https://developers.cloudflare.com/agent-memory/",
    fields=(
        # — Connection —
        ProviderField(
            key="api_key",
            label="API Token",
            kind=KIND_SECRET,
            env_key="MCP_CLOUDFLARE_API_KEY",
            description="Cloudflare API token with Agent Memory permission.",
            placeholder="Enter Cloudflare API token",
            inline=True,
            group="Connection",
        ),
        ProviderField(
            key="account_id",
            label="Account ID",
            kind=KIND_TEXT,
            env_key="CF_ACCOUNT_ID",
            default="0870b0bdbc14bcd31f43fe5e82c3ee8e",
            description="Cloudflare Account ID.",
            inline=True,
            group="Connection",
        ),
        # — Scoping —
        ProviderField(
            key="namespace",
            label="Namespace",
            kind=KIND_TEXT,
            default="hermes",
            description="Agent Memory namespace (≤32 chars). Created on first write if missing.",
            inline=True,
            group="Scoping",
        ),
        ProviderField(
            key="profile",
            label="Profile",
            kind=KIND_TEXT,
            default="default",
            description="Agent Memory profile name (≤100 chars). Created on first write.",
            inline=True,
            group="Scoping",
        ),
    ),
)
