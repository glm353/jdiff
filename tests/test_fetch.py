"""Unit tests for the fetch layer (HTTP stubbed — no network calls)."""
from __future__ import annotations

import json

import pytest

from jdiff import fetch
from jdiff.fetch import fetch_schema, parse_target, resolve_url


def test_parse_target_happy():
    assert parse_target("npe:aplus") == ("npe", "aplus")
    assert parse_target("prd:suite") == ("prd", "suite")


@pytest.mark.parametrize(
    "bad",
    ["", "npe", "foo.json", "npe:bogus", "bogus:aplus", "npe:", ":aplus"],
)
def test_parse_target_rejects(bad):
    assert parse_target(bad) is None


def test_resolve_url_all_four():
    assert resolve_url("npe", "aplus") == "https://uon-api.npe.allocate.plus/npe/plus/graphql/aplus"
    assert resolve_url("npe", "suite") == "https://uon-api.npe.allocate.plus/npe/plus/graphql/suite"
    assert resolve_url("prd", "aplus") == "https://uon-api.prd.allocate.plus/prd/plus/graphql/aplus"
    assert resolve_url("prd", "suite") == "https://uon-api.prd.allocate.plus/prd/plus/graphql/suite"


def test_resolve_url_rejects_unknown():
    with pytest.raises(ValueError):
        resolve_url("dev", "aplus")
    with pytest.raises(ValueError):
        resolve_url("npe", "other")


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        return self._payload


def test_fetch_schema_sends_correct_request(monkeypatch):
    captured = {}

    def fake_post(url, *, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["body"] = json
        captured["timeout"] = timeout
        return _FakeResponse(payload={"data": {"__schema": {"types": []}}})

    monkeypatch.setattr(fetch.requests, "post", fake_post)

    result = fetch_schema("npe", "aplus", api_key="KEY123", jwt_token="TOKEN456")

    assert captured["url"] == "https://uon-api.npe.allocate.plus/npe/plus/graphql/aplus"
    assert captured["headers"]["x-api-key"] == "KEY123"
    assert captured["headers"]["Authorization"] == "Bearer TOKEN456"
    assert captured["headers"]["Content-Type"] == "application/json"
    assert "query" in captured["body"]
    assert "IntrospectionQuery" in captured["body"]["query"]
    assert result == {"data": {"__schema": {"types": []}}}


def test_fetch_schema_raises_on_non_200(monkeypatch):
    def fake_post(url, *, headers, json, timeout):
        return _FakeResponse(status_code=401, text="unauthorized")

    monkeypatch.setattr(fetch.requests, "post", fake_post)

    with pytest.raises(RuntimeError, match="401"):
        fetch_schema("npe", "aplus", api_key="k", jwt_token="t")


def test_fetch_schema_raises_on_graphql_errors(monkeypatch):
    def fake_post(url, *, headers, json, timeout):
        return _FakeResponse(payload={"errors": [{"message": "nope"}]})

    monkeypatch.setattr(fetch.requests, "post", fake_post)

    with pytest.raises(RuntimeError, match="GraphQL errors"):
        fetch_schema("prd", "suite", api_key="k", jwt_token="t")
