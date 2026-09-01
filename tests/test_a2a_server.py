"""A2A JSON-RPC method aliases — no network."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from cloudflare_memory.a2a_server import create_app


@pytest.fixture
def client():
    from starlette.testclient import TestClient

    return TestClient(create_app())


def _payload(method: str, text: str = "ping-a2a-probe") -> dict:
    return {
        "jsonrpc": "2.0",
        "id": "probe-1",
        "method": method,
        "params": {
            "message": {
                "messageId": "m1",
                "role": "ROLE_USER",
                "parts": [{"text": text}],
            }
        },
    }


@pytest.mark.parametrize("path", ["/", "/rpc"])
@pytest.mark.parametrize("method", ["SendMessage", "message/send", "tasks/send"])
def test_send_methods_accepted(client, path, method):
    fake = {"answer": "pong", "candidates": []}
    with patch("cloudflare_memory.a2a_server._handle_skill", new=AsyncMock(return_value=fake)):
        res = client.post(path, json=_payload(method))
    assert res.status_code == 200
    body = res.json()
    assert "error" not in body
    assert body["jsonrpc"] == "2.0"
    if method == "tasks/send":
        assert body["result"]["status"]["state"] == "completed"
        assert body["result"]["task"]["id"]
    else:
        assert body["result"]["task"]["status"]["state"] == "TASK_STATE_COMPLETED"
        assert body["result"]["task"]["id"]


def test_unknown_method_is_32601(client):
    res = client.post("/rpc", json={"jsonrpc": "2.0", "id": 1, "method": "Nope", "params": {}})
    assert res.status_code == 200
    assert res.json()["error"]["code"] == -32601
