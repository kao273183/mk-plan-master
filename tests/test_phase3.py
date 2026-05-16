"""Phase 3 tests: jira / notion adapters, plan-knowledge, roadmap tools,
history snapshots, decision signature, telemetry.

Adapter tests monkeypatch _request to avoid live API calls. The autouse
fixture in conftest.py swaps PROJECT_ROOT / KNOWLEDGE_FILE / HISTORY_DIR /
TELEMETRY_PATH onto a tmp directory and disables the snapshot debounce so
every test gets a fresh world.
"""

import asyncio
import json
from typing import Any

import pytest


# ---------- jira adapter ----------------------------------------------


def _jira_issue(key: str, summary: str, status_name: str = "To Do",
                labels=None, story_points=None, description=None) -> dict:
    fields: dict[str, Any] = {
        "summary": summary,
        "status": {"name": status_name},
        "labels": labels or [],
    }
    if story_points is not None:
        fields["customfield_10016"] = story_points
    if description is not None:
        fields["description"] = description
    return {"id": f"id-{key}", "key": key, "fields": fields}


def test_jira_list_parses_issues(monkeypatch):
    from mk_plan_master import config
    from mk_plan_master.adapters import jira

    monkeypatch.setattr(config, "JIRA_BASE_URL", "https://example.atlassian.net")
    monkeypatch.setattr(config, "JIRA_EMAIL", "test@example.com")
    monkeypatch.setattr(config, "JIRA_API_TOKEN", "tok")
    monkeypatch.setattr(config, "SOURCE_KEY", "PROJ")

    monkeypatch.setattr(
        jira,
        "_request",
        lambda path, params=None: {
            "issues": [
                _jira_issue("PROJ-1", "Bulk-edit roles", labels=["admin"]),
                _jira_issue("PROJ-2", "Audit log", status_name="Backlog"),
            ]
        },
    )

    result = jira.JiraAdapter().list_initiatives()
    assert [r.id for r in result] == ["PROJ-1", "PROJ-2"]
    assert result[0].source == "jira"
    assert result[0].labels == ["admin"]
    assert result[0].url == "https://example.atlassian.net/browse/PROJ-1"


def test_jira_fetch_maps_story_points_to_effort(monkeypatch):
    from mk_plan_master import config
    from mk_plan_master.adapters import jira

    monkeypatch.setattr(config, "JIRA_BASE_URL", "https://example.atlassian.net")
    monkeypatch.setattr(config, "JIRA_EMAIL", "test@example.com")
    monkeypatch.setattr(config, "JIRA_API_TOKEN", "tok")

    description_adf = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Body text."}]},
        ],
    }
    issue = _jira_issue("PROJ-42", "Feature X", story_points=8, description=description_adf)
    monkeypatch.setattr(jira, "_request", lambda path, params=None: issue)

    initiative = jira.JiraAdapter().fetch("PROJ-42")
    assert initiative.id == "PROJ-42"
    assert initiative.source == "jira"
    assert "Body text." in initiative.body
    assert initiative.raw_metadata["effort"] == 8.0


def test_jira_check_auth_raises_without_env(monkeypatch):
    from mk_plan_master import config
    from mk_plan_master.adapters import jira

    monkeypatch.setattr(config, "JIRA_BASE_URL", "")
    with pytest.raises(ValueError, match="JIRA_BASE_URL"):
        jira._check_auth()

    monkeypatch.setattr(config, "JIRA_BASE_URL", "https://x")
    monkeypatch.setattr(config, "JIRA_EMAIL", "")
    with pytest.raises(ValueError, match="JIRA_EMAIL"):
        jira._check_auth()

    monkeypatch.setattr(config, "JIRA_EMAIL", "a@b.c")
    monkeypatch.setattr(config, "JIRA_API_TOKEN", "")
    with pytest.raises(ValueError, match="JIRA_API_TOKEN"):
        jira._check_auth()


def test_jira_registered_in_adapter_registry():
    from mk_plan_master.adapters import REGISTRY

    assert "jira" in REGISTRY


# ---------- notion adapter --------------------------------------------


def _notion_page(page_id: str, title: str, status: str = "Triage",
                 labels=None, custom_key: str | None = None,
                 scoring: dict | None = None) -> dict:
    props: dict[str, Any] = {
        "Name": {"type": "title", "title": [{"plain_text": title}]},
        "Status": {"type": "status", "status": {"name": status}},
    }
    if labels is not None:
        props["Tags"] = {
            "type": "multi_select",
            "multi_select": [{"name": l} for l in labels],
        }
    if custom_key is not None:
        props["Key"] = {"type": "rich_text", "rich_text": [{"plain_text": custom_key}]}
    if scoring:
        for k, v in scoring.items():
            props[k.capitalize()] = (
                {"type": "number", "number": v}
                if isinstance(v, (int, float))
                else {"type": "rich_text", "rich_text": [{"plain_text": str(v)}]}
            )
    return {
        "object": "page",
        "id": page_id,
        "url": f"https://notion.so/{page_id}",
        "properties": props,
        "created_time": "2026-01-01T00:00:00Z",
        "last_edited_time": "2026-01-02T00:00:00Z",
    }


def test_notion_list_filters_to_triageable_statuses(monkeypatch):
    from mk_plan_master import config
    from mk_plan_master.adapters import notion

    monkeypatch.setattr(config, "NOTION_TOKEN", "secret_x")
    monkeypatch.setattr(config, "SOURCE_KEY", "db-uuid")

    monkeypatch.setattr(
        notion,
        "_request",
        lambda method, path, body=None: {
            "results": [
                _notion_page("p1", "Triage idea", status="Triage"),
                _notion_page("p2", "Idea idea", status="Idea"),
                _notion_page("p3", "Done — shouldn't appear", status="Done"),
            ]
        },
    )

    result = notion.NotionAdapter().list_initiatives()
    assert [r.id for r in result] == ["p1", "p2"]
    assert result[0].source == "notion"


def test_notion_fetch_maps_scoring_properties(monkeypatch):
    from mk_plan_master import config
    from mk_plan_master.adapters import notion

    monkeypatch.setattr(config, "NOTION_TOKEN", "secret_x")
    monkeypatch.setattr(config, "SOURCE_KEY", "db-uuid")

    page = _notion_page(
        "p42",
        "Test page",
        custom_key="EX-42",
        scoring={"reach": 1000, "impact": 2, "confidence": 0.7, "effort": 4, "okr": "Q3-growth"},
    )
    blocks = {
        "results": [
            {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Hello body"}]}},
        ]
    }

    def fake_request(method, path, body=None):
        if path.startswith("/pages/"):
            return page
        if path.startswith("/blocks/"):
            return blocks
        return {}

    monkeypatch.setattr(notion, "_request", fake_request)

    initiative = notion.NotionAdapter().fetch("p42")
    assert initiative.title == "Test page"
    assert "Hello body" in initiative.body
    assert initiative.raw_metadata["custom_key"] == "EX-42"
    assert initiative.raw_metadata["reach"] == 1000
    assert initiative.raw_metadata["effort"] == 4
    assert initiative.raw_metadata["okr"] == "Q3-growth"


def test_notion_check_auth_raises_without_token(monkeypatch):
    from mk_plan_master import config
    from mk_plan_master.adapters import notion

    monkeypatch.setattr(config, "NOTION_TOKEN", "")
    with pytest.raises(ValueError, match="NOTION_TOKEN"):
        notion._check_auth()


def test_notion_registered_in_adapter_registry():
    from mk_plan_master.adapters import REGISTRY

    assert "notion" in REGISTRY


# ---------- plan_knowledge --------------------------------------------


def test_init_plan_knowledge_writes_methodology_keywords():
    from mk_plan_master import config
    from mk_plan_master.tools.plan_knowledge import init_plan_knowledge_tool

    result = init_plan_knowledge_tool({"project_name": "alpha"})
    assert result["created"] is True
    body = config.KNOWLEDGE_FILE.read_text(encoding="utf-8")
    for needle in ("RICE", "WSJF", "OKR", "INVEST"):
        assert needle in body, f"missing methodology keyword: {needle}"


def test_init_plan_knowledge_is_idempotent():
    from mk_plan_master.tools.plan_knowledge import init_plan_knowledge_tool

    init_plan_knowledge_tool({})
    second = init_plan_knowledge_tool({})
    assert second["created"] is False
    assert "already exists" in second["reason"]


def test_get_plan_context_section_filter_returns_only_target_block():
    from mk_plan_master.tools.plan_knowledge import (
        get_plan_context_tool,
        init_plan_knowledge_tool,
    )

    init_plan_knowledge_tool({})
    result = get_plan_context_tool({"section": "RICE"})
    assert result["found"] is True
    content = result["content"]
    # The section starts at the matched heading.
    assert "RICE" in content
    # And does not bleed into a later sibling section.
    assert "WSJF" not in content


def test_get_plan_context_builtin_when_no_file():
    from mk_plan_master.tools.plan_knowledge import get_plan_context_tool

    result = get_plan_context_tool({})
    assert result["source"] == "builtin"
    assert "RICE" in result["content"]


# ---------- generate_roadmap ------------------------------------------


def test_generate_roadmap_packs_initiatives_respecting_capacity():
    from mk_plan_master.tools.roadmap import generate_roadmap_tool

    # Sample fixtures total 5 + 3 + 1 = 9 pw effort. Capacity 0.5 engineer-
    # months = 2 pw of total capacity; with default 20% buffer => 1.6 pw
    # available — only LIN-003 (effort 1) fits.
    result = generate_roadmap_tool(
        {"capacity_engineer_months": 0.5, "period": "Q3 2026", "buffer_pct": 20}
    )

    assert result["capacity_total_pw"] == 2.0
    assert result["capacity_used_pw"] <= 1.6
    scheduled_ids = [e["initiative_id"] for e in result["scheduled"]]
    deferred_ids = [e["initiative_id"] for e in result["deferred"]]
    assert "LIN-003" in scheduled_ids  # effort 1 fits inside buffer-adjusted capacity
    assert "LIN-001" in deferred_ids or "LIN-002" in deferred_ids
    assert "# Roadmap — Q3 2026" in result["markdown"]


def test_generate_roadmap_buffer_pct_reserves_capacity():
    from mk_plan_master.tools.roadmap import generate_roadmap_tool

    # 4 engineer-months = 16 pw total. 50% buffer => 8 pw planning envelope.
    # Initiatives total 9 pw so at least one must be deferred.
    result = generate_roadmap_tool(
        {"capacity_engineer_months": 4, "period": "Q3 2026", "buffer_pct": 50}
    )
    assert result["buffer_pw"] == 8.0
    assert result["capacity_used_pw"] <= 8.0
    assert len(result["deferred"]) >= 1


def test_generate_roadmap_requires_capacity_and_period():
    from mk_plan_master.tools.roadmap import generate_roadmap_tool

    assert "error" in generate_roadmap_tool({})
    assert "error" in generate_roadmap_tool({"capacity_engineer_months": 1})
    assert "error" in generate_roadmap_tool({"period": "Q3"})


# ---------- analyze_roadmap_balance -----------------------------------


def test_analyze_roadmap_balance_ratios_sum_to_100():
    from mk_plan_master.tools.roadmap import analyze_roadmap_balance_tool

    result = analyze_roadmap_balance_tool({"limit": 30})
    pct = result["ratio_pct"]
    assert sum(pct.values()) == 100
    assert set(pct.keys()) == {"feature", "tech_debt", "strategic", "unlabeled"}
    assert isinstance(result["advisory"], str) and result["advisory"]


def test_analyze_roadmap_balance_respects_custom_label_vocab():
    from mk_plan_master.tools.roadmap import analyze_roadmap_balance_tool

    # The samples use 'growth', 'billing', 'api'. Map all three into the
    # feature bucket so every initiative is classified as feature.
    result = analyze_roadmap_balance_tool(
        {
            "feature_labels": ["growth", "billing", "api"],
            "tech_debt_labels": ["nothing-1"],
            "strategic_labels": ["nothing-2"],
        }
    )
    totals = result["totals"]
    assert totals["feature"] == totals["scored"]
    assert totals["unlabeled"] == 0


# ---------- history + archive_snapshot --------------------------------


def test_archive_snapshot_writes_file():
    from mk_plan_master import config
    from mk_plan_master.tools.history import archive_snapshot

    path = archive_snapshot({"method": "rice", "count": 1, "top10": [], "all_scores": []})
    assert path
    assert config.HISTORY_DIR.exists()
    files = list(config.HISTORY_DIR.glob("*.json"))
    assert len(files) == 1


def test_archive_snapshot_debounces_within_window(monkeypatch):
    from mk_plan_master import config
    from mk_plan_master.tools.history import archive_snapshot

    monkeypatch.setattr(config, "HISTORY_DEBOUNCE_SECONDS", 300)
    first = archive_snapshot({"method": "rice", "count": 1, "top10": [], "all_scores": []})
    second = archive_snapshot({"method": "rice", "count": 1, "top10": [], "all_scores": []})
    assert first
    assert second == ""  # debounced

    monkeypatch.setattr(config, "HISTORY_DEBOUNCE_SECONDS", 0)
    third = archive_snapshot({"method": "rice", "count": 1, "top10": [], "all_scores": []})
    assert third


def test_get_planning_history_empty_when_no_snapshots():
    from mk_plan_master.tools.history import get_planning_history_tool

    result = get_planning_history_tool({})
    assert result["snapshots_count"] == 0
    assert result["trend_7d"] == {
        "avg_top10_score": 0.0,
        "new_top10_entries": [],
        "churned_top10_entries": [],
    }
    assert "No snapshots" in result["summary"]


def test_get_planning_history_after_rank_backlog_call():
    from mk_plan_master.tools.history import get_planning_history_tool
    from mk_plan_master.tools.scoring import rank_backlog_tool

    rank_backlog_tool({"method": "rice", "limit": 5})
    history = get_planning_history_tool({})
    assert history["snapshots_count"] >= 1
    # Average score should be positive for the sample corpus.
    assert history["trend_7d"]["avg_top10_score"] > 0


def test_get_decision_signature_empty_when_no_history():
    from mk_plan_master.tools.history import get_decision_signature_tool

    result = get_decision_signature_tool({})
    assert result["ghost_initiatives"] == []
    assert result["score_whiplash"] == []
    assert result["orphan_okrs"] == []


def test_get_decision_signature_detects_orphan_okrs():
    """LIN-001 has okr=Q3-growth. After rank_backlog without spec_generated,
    the OKR should appear in top-10 (so not orphan). Verify the wiring works."""
    from mk_plan_master.tools.history import get_decision_signature_tool
    from mk_plan_master.tools.scoring import rank_backlog_tool

    rank_backlog_tool({"method": "rice", "limit": 10})
    result = get_decision_signature_tool({})
    # No spec_generated yet, but only one snapshot — so ghost detection
    # threshold (>50%) is not met from a single snapshot; check shape.
    assert isinstance(result["ghost_initiatives"], list)
    assert isinstance(result["score_whiplash"], list)
    assert isinstance(result["orphan_okrs"], list)


# ---------- telemetry --------------------------------------------------


def test_get_telemetry_empty_when_no_records():
    from mk_plan_master.tools.telemetry import get_telemetry_tool

    result = get_telemetry_tool({})
    assert result["calls_total"] == 0
    assert result["calls_by_tool"] == {}
    assert result["top_tools"] == []


def test_telemetry_records_calls_via_server_dispatch():
    """call_tool should write one JSONL record per dispatch."""
    from mk_plan_master.server import call_tool
    from mk_plan_master.tools.telemetry import get_telemetry_tool

    asyncio.run(call_tool("get_plan_source_info", {}))
    asyncio.run(call_tool("list_initiatives", {}))

    result = get_telemetry_tool({})
    assert result["calls_total"] >= 2
    assert "get_plan_source_info" in result["calls_by_tool"]
    assert "list_initiatives" in result["calls_by_tool"]


def test_get_telemetry_aggregates_p50_p95():
    from mk_plan_master import config
    from mk_plan_master.tools.telemetry import get_telemetry_tool, log_tool_call

    for ms in (1, 5, 10, 20, 50, 100, 200, 500, 1000):
        log_tool_call("synthetic", ms)

    result = get_telemetry_tool({"window_days": 30})
    assert result["calls_total"] >= 9
    assert result["p50_ms"] > 0
    assert result["p95_ms"] >= result["p50_ms"]


def test_get_telemetry_lists_dead_tools():
    from mk_plan_master.server import call_tool
    from mk_plan_master.tools.telemetry import get_telemetry_tool

    asyncio.run(call_tool("get_plan_source_info", {}))

    result = get_telemetry_tool({})
    # Tools we didn't touch should be in dead_tools.
    assert "generate_roadmap" in result["dead_tools"]
    assert "get_plan_source_info" not in result["dead_tools"]
