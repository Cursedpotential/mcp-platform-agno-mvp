"""Tests for gateway/ — content store paging + the five meta-operations (G4).

The load-bearing contracts: dedup by hash, correct page math at boundaries,
categories mirroring the live registry, search ranking, large-result ref
round-trip (execute -> ref -> pages reassemble byte-identically), and the
FastAPI surface returning proper status codes.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from server.tools.registry import FunctionTool, load_builtin_tools, registry
from server.tools.gateway.api import build_app
from server.tools.gateway.content_store import ContentStore, parse_ref
from server.tools.gateway.toolfinder import (
    describe_tool,
    execute_tool,
    get_ref,
    get_tool_categories,
    search_tools,
)


@pytest.fixture
def store(tmp_path):
    return ContentStore(tmp_path / "cs")


# ---- content store -----------------------------------------------------------


def test_put_dedup_and_ref_shape(store):
    r1 = store.put("hello world")
    r2 = store.put("hello world")
    assert r1["ref"] == r2["ref"] and r1["ref"].startswith("sha256:")
    assert r1["size"] == 11 and r1["total_pages"] == 1
    assert r1["preview"] == "hello world"


def test_page_math_at_boundaries(store):
    data = "x" * 10000  # 3 pages at 4096: 4096 + 4096 + 1808
    sha = parse_ref(store.put(data)["ref"])

    p0 = store.get_page(sha, 0)
    p2 = store.get_page(sha, 2)
    assert p0["total_pages"] == 3 and p0["has_more"] is True
    assert len(p0["content"]) == 4096
    assert len(p2["content"]) == 10000 - 2 * 4096 and p2["has_more"] is False

    with pytest.raises(IndexError):
        store.get_page(sha, 3)

    # custom page size changes the math
    assert store.get_page(sha, 0, page_size=10000)["has_more"] is False


def test_pages_reassemble_exactly(store):
    data = json.dumps({"records": [{"i": i, "text": "msg " * 50} for i in range(100)]})
    sha = parse_ref(store.put(data)["ref"])
    pages = []
    page = 0
    while True:
        p = store.get_page(sha, page)
        pages.append(p["content"])
        if not p["has_more"]:
            break
        page += 1
    assert "".join(pages) == data


def test_unknown_ref_and_bad_ref(store):
    with pytest.raises(KeyError):
        store.get("0" * 64)
    with pytest.raises(ValueError):
        parse_ref("not-a-ref")


# ---- meta-operations over the real registry -----------------------------------


def test_categories_mirror_registry():
    load_builtin_tools()
    cats = {c["category"]: c["tool_count"] for c in get_tool_categories()}
    assert cats["parse.transcript"] >= 13
    assert "parse.sms-xml" in cats
    total = sum(cats.values())
    assert total == len(registry.all())


def test_search_ranks_id_matches_first():
    results = search_tools("imessage")
    assert results and all("id" in r and "category" in r for r in results)
    assert results[0]["id"].startswith("messages.imessage") or "imessage" in results[0]["id"]
    # category filter narrows
    only_transcripts = search_tools("", category="parse.transcript", limit=100)
    assert {r["category"] for r in only_transcripts} == {"parse.transcript"}


def test_describe_includes_substitution_candidates():
    d = describe_tool("transcripts.chatgpt-official")
    assert d["category"] == "parse.transcript"
    assert "transcripts.claude-ai-export" in d["substitution_candidates"]
    with pytest.raises(KeyError):
        describe_tool("nope.nothing")


# ---- execute: inline vs ref --------------------------------------------------


@pytest.fixture
def fake_tools(monkeypatch):
    from server.tools import registry as registry_mod

    fresh = registry_mod.ToolRegistry()
    fresh.register(
        FunctionTool(
            id="test.small",
            capability="test.echo",
            description="small result",
            fn=lambda p: {"echo": p, "stats": {"record_count": 1}},
        )
    )
    fresh.register(
        FunctionTool(
            id="test.big",
            capability="test.echo",
            description="big result",
            fn=lambda p: {"records": [{"n": i, "body": "z" * 100} for i in range(200)], "stats": {"record_count": 200}},
        )
    )
    monkeypatch.setattr(registry_mod, "registry", fresh)
    monkeypatch.setattr("server.tools.gateway.toolfinder.registry", fresh)
    monkeypatch.setattr("server.tools.gateway.toolfinder._ensure_loaded", lambda: None)
    return fresh


def test_execute_small_inlines(fake_tools, store):
    out = execute_tool("test.small", {"a": 1}, store=store)
    assert out["inline"] is True and out["result"]["echo"] == {"a": 1}


def test_execute_large_returns_ref_and_pages_roundtrip(fake_tools, store):
    out = execute_tool("test.big", {}, store=store)
    assert out["inline"] is False
    assert out["stats"]["record_count"] == 200
    assert out["size"] > 4096

    # reassemble via get_ref and verify content integrity
    pages, page = [], 0
    while True:
        p = get_ref(out["ref"], page=page, store=store)
        pages.append(p["content"])
        if not p["has_more"]:
            break
        page += 1
    parsed = json.loads("".join(pages))
    assert len(parsed["records"]) == 200


# ---- FastAPI surface -----------------------------------------------------------


def test_api_endpoints(tmp_path):
    client = TestClient(build_app(store=ContentStore(tmp_path / "api-cs")))

    assert client.get("/health").json() == {"status": "ok"}

    cats = client.get("/categories").json()
    assert any(c["category"] == "parse.transcript" for c in cats)

    tools = client.get("/tools", params={"query": "chatgpt"}).json()
    assert any("chatgpt" in t["id"] for t in tools)

    assert client.get("/tools/transcripts.chatgpt-official").status_code == 200
    assert client.get("/tools/nope.nothing").status_code == 404

    # execute a real parser against a wrong-shape file -> structured 422 (hard-fail)
    bad = tmp_path / "x.json"
    bad.write_text("{}")
    r = client.post("/tools/transcripts.chatgpt-official/execute", json={"path": str(bad)})
    assert r.status_code == 422

    assert client.get("/refs/" + "0" * 64).status_code == 404
