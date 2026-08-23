"""Resolve Cloudflare credentials from the environment. Never hardcode accounts."""

from __future__ import annotations

import os

TOKEN_ENV = "MCP_CLOUDFLARE_API_KEY"
ACCOUNT_ENV = "CF_ACCOUNT_ID"
NAMESPACE_ENV = "CF_MEMORY_NAMESPACE"
PROFILE_ENV = "CF_MEMORY_PROFILE"

DEFAULT_NAMESPACE = "hermes"
DEFAULT_PROFILE = "default"


class CredentialsError(RuntimeError):
    """Missing required Cloudflare credentials."""


def require_token() -> str:
    token = os.environ.get(TOKEN_ENV, "").strip()
    if not token:
        raise CredentialsError(
            f"{TOKEN_ENV} is not set. Create a scoped API token: "
            "https://dash.cloudflare.com/profile/api-tokens"
        )
    return token


def require_account_id() -> str:
    account = os.environ.get(ACCOUNT_ENV, "").strip()
    if not account:
        raise CredentialsError(
            f"{ACCOUNT_ENV} is not set. Find it in the Cloudflare dashboard sidebar: "
            "https://dash.cloudflare.com/"
        )
    return account


def namespace() -> str:
    return os.environ.get(NAMESPACE_ENV, DEFAULT_NAMESPACE).strip() or DEFAULT_NAMESPACE


def profile() -> str:
    return os.environ.get(PROFILE_ENV, DEFAULT_PROFILE).strip() or DEFAULT_PROFILE
