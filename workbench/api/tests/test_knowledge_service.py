# Byline: Codex · GPT-5 · 2026-08-15 (case/lane-safe multi-base coverage)
"""Unit coverage for the Workbench Knowledge anti-corruption adapter."""

from __future__ import annotations

import pytest

from app.service import knowledge


def test_knowledge_ids_match_registered_agentos_bases():
    assert knowledge._knowledge_id("platform") == "3dd8cc92-f149-25b9-f150-fb9c934c9010"
    assert knowledge._knowledge_id("legal") == "6efddf6c-a228-38fc-7d85-88fbce105752"
    assert knowledge._knowledge_id("evidence") == "3c4a8296-e60f-3374-38b8-e6e93ffb874e"
    assert knowledge._knowledge_id("personal_history") == "932491b5-6999-97e7-01a2-af2d17b61308"
    assert knowledge._knowledge_id("context") == "19c578b1-53e6-f6cd-0315-4954635d26fc"


def test_search_one_lane_uses_knowledge_id_and_case_prefilter(monkeypatch):
    captured = {}

    def fake_spine_json(method, path, **kwargs):
        captured.update(method=method, path=path, kwargs=kwargs)
        return {
            "data": [{"id": "h1", "content": "x", "reranking_score": 0.7}],
            "meta": {"total_count": 1},
        }

    monkeypatch.setattr(knowledge, "spine_json", fake_spine_json)
    result = knowledge.search("custody chain", case_id="matter-2", lane="legal", limit=5)

    assert captured["method"] == "POST"
    assert captured["path"] == "/knowledge/search"
    assert captured["kwargs"]["json"] == {
        "query": "custody chain",
        "knowledge_id": knowledge._knowledge_id("legal"),
        "max_results": 5,
        "filters": {"case_id": "matter-2"},
    }
    assert result["data"][0]["meta_data"]["knowledge_lane"] == "legal"


def test_search_all_lanes_merges_after_each_case_prefilter(monkeypatch):
    calls = []

    def fake_spine_json(method, path, **kwargs):
        body = kwargs["json"]
        calls.append(body)
        score = len(calls) / 10
        return {
            "data": [{"id": f"h{len(calls)}", "content": "x", "reranking_score": score}],
            "meta": {"total_count": 1},
        }

    monkeypatch.setattr(knowledge, "spine_json", fake_spine_json)
    result = knowledge.search("what happened", case_id="primary", limit=3)

    assert len(calls) == len(knowledge._KNOWLEDGE_TABLES)
    assert all(call["filters"] == {"case_id": "primary"} for call in calls)
    assert len({call["knowledge_id"] for call in calls}) == len(calls)
    assert [hit["reranking_score"] for hit in result["data"]] == [0.5, 0.4, 0.3]
    assert result["meta"]["total_count"] == 5


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"query": " ", "case_id": "primary"}, "query must be a non-empty string"),
        ({"query": "q", "case_id": " "}, "case_id must be a non-empty string"),
        ({"query": "q", "case_id": "primary", "lane": "unknown"}, "unsupported knowledge lane"),
        ({"query": "q", "case_id": "primary", "limit": 0}, "limit must be between"),
        ({"query": "q", "case_id": "primary", "limit": 101}, "limit must be between"),
    ],
)
def test_search_rejects_unsafe_inputs(kwargs, message):
    with pytest.raises(ValueError, match=message):
        knowledge.search(**kwargs)


def test_list_contents_scopes_lane_and_filters_case_before_return(monkeypatch):
    captured = []

    def fake_spine_json(method, path, **kwargs):
        captured.append((method, path, kwargs))
        return {
            "data": [
                {"id": "ours", "metadata": {"case_id": "primary"}},
                {"id": "foreign", "metadata": {"case_id": "other"}},
                {"id": "unscoped", "metadata": {}},
            ],
            "meta": {"page": 1, "total_pages": 1, "total_count": 3},
        }

    monkeypatch.setattr(knowledge, "spine_json", fake_spine_json)
    result = knowledge.list_contents(case_id="primary", lane="evidence", limit=20, offset=0)

    assert captured[0][0:2] == ("GET", "/knowledge/content")
    assert captured[0][2]["params"] == {
        "limit": 200,
        "page": 1,
        "knowledge_id": knowledge._knowledge_id("evidence"),
    }
    assert [row["id"] for row in result["data"]] == ["ours"]
    assert result["data"][0]["metadata"]["knowledge_lane"] == "evidence"
    assert result["meta"]["total_count"] == 1
    assert result["meta"]["truncated"] is False


def test_list_contents_scans_pages_then_paginates_visible_rows(monkeypatch):
    def fake_spine_json(method, path, **kwargs):
        page = kwargs["params"]["page"]
        rows = (
            [{"id": "a", "metadata": {"case_id": "primary"}}, {"id": "x", "metadata": {"case_id": "other"}}]
            if page == 1
            else [{"id": "b", "metadata": {"case_id": "primary"}}]
        )
        return {"data": rows, "meta": {"page": page, "total_pages": 2, "total_count": 3}}

    monkeypatch.setattr(knowledge, "spine_json", fake_spine_json)
    result = knowledge.list_contents(case_id="primary", lane="context", limit=1, offset=1)

    assert [row["id"] for row in result["data"]] == ["b"]
    assert result["meta"]["total_count"] == 2
    assert result["meta"]["page"] == 2


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"case_id": " ", "lane": "legal"}, "case_id must be a non-empty string"),
        ({"case_id": "primary", "lane": "unknown"}, "unsupported knowledge lane"),
        ({"case_id": "primary", "lane": "legal", "offset": -1}, "offset must be"),
    ],
)
def test_list_contents_rejects_unsafe_inputs(kwargs, message):
    with pytest.raises(ValueError, match=message):
        knowledge.list_contents(**kwargs)
