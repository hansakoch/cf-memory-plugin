"""Credential helper tests — no network."""

from __future__ import annotations

import pytest

from cloudflare_memory.credentials import (
    ACCOUNT_ENV,
    TOKEN_ENV,
    CredentialsError,
    require_account_id,
    require_token,
)


def test_require_token_missing(monkeypatch):
    monkeypatch.delenv(TOKEN_ENV, raising=False)
    with pytest.raises(CredentialsError, match=TOKEN_ENV):
        require_token()


def test_require_account_missing(monkeypatch):
    monkeypatch.delenv(ACCOUNT_ENV, raising=False)
    with pytest.raises(CredentialsError, match=ACCOUNT_ENV):
        require_account_id()


def test_require_both_ok(monkeypatch):
    monkeypatch.setenv(TOKEN_ENV, "tok")
    monkeypatch.setenv(ACCOUNT_ENV, "acct")
    assert require_token() == "tok"
    assert require_account_id() == "acct"
