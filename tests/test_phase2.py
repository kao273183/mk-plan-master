"""Phase 2 tests: linear adapter, scoring, ranking, bridge.

Adapter tests monkeypatch _gql to avoid live API calls (mirrors
mk-spec-master's test_linear.py style). The autouse fixture in conftest.py
already swaps INDEX_PATH / INDEX_DIR onto a tmp directory, so every test
gets a fresh decision index.
"""

import asyncio
import json
from typing import Any

import pytest


# ---------- linear adapter helpers ------------------------------------


def _fake_gql_returning(responses: dict[str, Any]):
    """Stub _gql(query, variables=None) — picks a response by which Linear
    query identifier appears in the GraphQL text."""

    def _fake(query: str, variables=None):
        if "issueByIdentifier" in query:
            return responses.get("fetch", {})
        if "issues(" in query:
            return responses.get("list", {})
        return {}

    return _fake


def _node(identifier: str, title: str, state: str = "Triage", state_type: str = "triage",
          labels=None, estimate=None):
    node = {
        "id": f"uuid-{identifier}",
        "identifier": identifier,
        "title": title,
        "state": {"name": state, "type": state_type},
        "labels": {"nodes": [{"name": l} for l in (labels or [])]},
        "url": f"https://linear.app/team/issue/{identifier}",
    }
    if estimate is not None:
        node["estimate"] = estimate
    return node


# ---------- linear adapter --------------------------------------------


def test_linear_list_parses_nodes(monkeypatch):
    from mk_plan_master.adapters import linear

    monkeypatch.setattr(
        linear,
        "_gql",
        _fake_gql_returning(
            {
                "list": {
                    "issues": {
                        "nodes": [
                            _node("ENG-1", "Bulk-edit roles", labels=["admin"]),
                            _node("ENG-2", "Audit log export", state="Backlog",
                                  state_type="backlog"),
                        ]
                    }
                }
            }
        ),
    )

    adapter = linear.LinearAdapter()
    result = adapter.list_initiatives()

    assert [r.id for r in result] == ["ENG-1", "ENG-2"]
    assert result[0].source == "linear"
    assert result[0].labels == ["admin"]
    assert result[1].status == "Backlog"


def test_linear_list_respects_limit(monkeypatch):
    from mk_plan_master.adapters import linear

    monkeypatch.setattr(
        linear,
        "_gql",
        _fake_gql_returning(
            {"list": {"issues": {"nodes": [_node(f"ENG-{i}", f"T{i}") for i in range(10)]}}}
        ),
    )

    result = linear.LinearAdapter().list_initiatives(limit=3)
    assert len(result) == 3


def test_linear_list_default_filter_is_not_yet_shipped(monkeypatch):
    """When no explicit status filter is passed we constrain to state types
    triage / backlog / unstarted (the upstream-half intent)."""
    from mk_plan_master.adapters import linear

    captured: dict[str, Any] = {}

    def _capturing(query, variables=None):
        captured["variables"] = variables
        return {"issues": {"nodes": []}}

    monkeypatch.setattr(linear, "_gql", _capturing)

    linear.LinearAdapter().list_initiatives()
    state_filter = captured["variables"]["filter"]["state"]
    assert state_filter == {"type": {"in": ["triage", "backlog", "unstarted"]}}


def test_linear_fetch_maps_estimate_to_raw_metadata_effort(monkeypatch):
    from mk_plan_master.adapters import linear

    issue = _node("ENG-42", "Login feature", estimate=5)
    issue["description"] = "Body text"
    issue["createdAt"] = "2026-01-01T00:00:00Z"
    issue["updatedAt"] = "2026-01-02T00:00:00Z"

    monkeypatch.setattr(
        linear,
        "_gql",
        _fake_gql_returning({"fetch": {"issueByIdentifier": issue}}),
    )

    initiative = linear.LinearAdapter().fetch("ENG-42")

    assert initiative.id == "ENG-42"
    assert initiative.source == "linear"
    assert initiative.body == "Body text"
    assert initiative.raw_metadata["linear_id"] == "uuid-ENG-42"
    assert initiative.raw_metadata["effort"] == 5


def test_linear_fetch_missing_issue_raises(monkeypatch):
    from mk_plan_master.adapters import linear

    monkeypatch.setattr(
        linear,
        "_gql",
        _fake_gql_returning({"fetch": {"issueByIdentifier": None}}),
    )

    with pytest.raises(ValueError, match="not found"):
        linear.LinearAdapter().fetch("ENG-9999")


def test_linear_check_auth_raises_without_api_key(monkeypatch):
    from mk_plan_master import config
    from mk_plan_master.adapters import linear

    monkeypatch.setattr(config, "LINEAR_API_KEY", "")

    with pytest.raises(ValueError, match="LINEAR_API_KEY"):
        linear._check_auth()


def test_linear_registered_in_adapter_registry():
    from mk_plan_master.adapters import REGISTRY, get_source

    assert "linear" in REGISTRY
    assert get_source("linear").name == "linear"


# ---------- RICE arithmetic -------------------------------------------


def test_rice_score_matches_expected():
    from mk_plan_master.scoring.rice import rice_score, rice_tier

    score = rice_score(reach=1200, impact=2, confidence=0.8, effort=5)
    assert score == 384.0
    assert rice_tier(score) == "P0"


def test_rice_tier_thresholds():
    from mk_plan_master.scoring.rice import rice_tier

    assert rice_tier(30.0) == "P0"
    assert rice_tier(25.0) == "P1"
    assert rice_tier(10.0) == "P1"
    assert rice_tier(9.9) == "P2"
    assert rice_tier(3.0) == "P2"
    assert rice_tier(2.9) == "P3"


def test_rice_handles_zero_effort_gracefully():
    """effort gets clamped to 1 so we never divide by zero."""
    from mk_plan_master.scoring.rice import rice_score

    assert rice_score(reach=10, impact=1, confidence=1, effort=0) == 10.0


# ---------- Impact-Effort quadrant ------------------------------------


def test_impact_effort_quadrants():
    from mk_plan_master.scoring.impact_effort import impact_effort_quadrant

    assert impact_effort_quadrant(impact=5, effort=1) == "quick_win"
    assert impact_effort_quadrant(impact=5, effort=5) == "big_bet"
    assert impact_effort_quadrant(impact=1, effort=1) == "fill_in"
    assert impact_effort_quadrant(impact=1, effort=5) == "time_sink"


# ---------- score_initiative_tool -------------------------------------


def test_score_initiative_tool_writes_index_and_reads_back():
    from mk_plan_master import config
    from mk_plan_master.index import decisions as didx
    from mk_plan_master.tools.scoring import score_initiative_tool

    result = score_initiative_tool({"initiative_id": "LIN-001", "method": "rice"})

    assert result["initiative_id"] == "LIN-001"
    assert result["method"] == "rice"
    assert result["stored"] is True
    # LIN-001 sample: reach=1200, impact=2, confidence=0.8, effort=5 -> 384.0
    assert result["score"] == 384.0
    assert result["tier"] == "P0"

    assert config.INDEX_PATH.exists()
    index = didx.load_index()
    record = index["initiatives"]["LIN-001"]
    assert record["last_score"] == 384.0
    assert record["tier"] == "P0"
    assert record["method"] == "rice"
    assert any(d["action"] == "scored" for d in record["decisions"])


def test_score_initiative_tool_overrides_take_precedence():
    from mk_plan_master.tools.scoring import score_initiative_tool

    result = score_initiative_tool(
        {
            "initiative_id": "LIN-001",
            "method": "rice",
            "overrides": {"reach": 100, "impact": 1, "confidence": 0.5, "effort": 10},
        }
    )
    # (100 * 1 * 0.5) / 10 = 5
    assert result["score"] == 5.0
    assert result["tier"] == "P2"


def test_score_initiative_tool_impact_effort_quadrant():
    from mk_plan_master.tools.scoring import score_initiative_tool

    result = score_initiative_tool(
        {
            "initiative_id": "LIN-003",
            "method": "impact_effort",
            "overrides": {"impact": 5, "effort": 1},
        }
    )
    assert result["tier"] == "quick_win"
    assert result["score"] == 4.0


def test_score_initiative_tool_requires_id_or_text():
    from mk_plan_master.tools.scoring import score_initiative_tool

    result = score_initiative_tool({})
    assert "error" in result
    assert result["retryable"] is False


# ---------- rank_backlog_tool -----------------------------------------


def test_rank_backlog_tool_sorts_descending_by_score():
    from mk_plan_master.tools.scoring import rank_backlog_tool

    result = rank_backlog_tool({"method": "rice", "limit": 5})

    assert result["method"] == "rice"
    assert result["count"] == 3  # three sample initiatives
    scores = [r["score"] for r in result["ranking"]]
    assert scores == sorted(scores, reverse=True)
    # LIN-001 (384) should dominate the sample corpus.
    assert result["ranking"][0]["initiative_id"] == "LIN-001"
    assert result["ranking"][0]["tier"] == "P0"
    assert "rationale" in result["ranking"][0]


def test_rank_backlog_tool_status_filter():
    from mk_plan_master.tools.scoring import rank_backlog_tool

    result = rank_backlog_tool({"status": "nonexistent-status-zzz", "limit": 5})
    assert result["count"] == 0


# ---------- generate_spec_draft_tool ----------------------------------


def test_generate_spec_draft_default_template_has_required_headings():
    from mk_plan_master.tools.bridge import generate_spec_draft_tool

    result = generate_spec_draft_tool({"initiative_id": "LIN-001"})

    md = result["markdown"]
    assert result["template_used"] == "default"
    assert result["ready_for_mk_spec_master"] is True
    assert result["suggested_filename"] == "LIN-001.md"

    assert md.startswith("# ")  # H1 title
    assert "## Context" in md
    assert "## Acceptance criteria" in md
    assert "## Out of scope" in md
    # Should reference the OKR from frontmatter when present.
    assert "Q3-growth" in md


def test_generate_spec_draft_lite_template_excludes_okr_and_oos():
    from mk_plan_master.tools.bridge import generate_spec_draft_tool

    result = generate_spec_draft_tool(
        {"initiative_id": "LIN-001", "template": "lite"}
    )
    md = result["markdown"]
    assert result["template_used"] == "lite"

    assert "## Context" in md
    assert "## Acceptance criteria" in md
    assert "## Out of scope" not in md
    assert "Linked OKR" not in md
    # No blockquote metadata block at all in lite.
    assert "> Source:" not in md


def test_generate_spec_draft_detailed_template_has_risk_and_dependency_sections():
    from mk_plan_master.tools.bridge import generate_spec_draft_tool

    result = generate_spec_draft_tool(
        {"initiative_id": "LIN-001", "template": "detailed"}
    )
    md = result["markdown"]
    assert result["template_used"] == "detailed"
    assert "## Risks" in md
    assert "## Dependencies" in md
    assert "## Estimated effort" in md


def test_generate_spec_draft_writes_decision_to_index():
    from mk_plan_master.index import decisions as didx
    from mk_plan_master.tools.bridge import generate_spec_draft_tool

    generate_spec_draft_tool({"initiative_id": "LIN-002"})

    index = didx.load_index()
    record = index["initiatives"]["LIN-002"]
    actions = [d["action"] for d in record["decisions"]]
    assert "spec_generated" in actions
    spec_entry = next(d for d in record["decisions"] if d["action"] == "spec_generated")
    assert spec_entry["details"]["template"] == "default"
    assert spec_entry["details"]["suggested_filename"] == "LIN-002.md"


def test_generate_spec_draft_unknown_template_returns_error():
    from mk_plan_master.tools.bridge import generate_spec_draft_tool

    result = generate_spec_draft_tool(
        {"initiative_id": "LIN-001", "template": "garbage"}
    )
    assert "error" in result
    assert result["retryable"] is False


# ---------- server dispatch wiring ------------------------------------


def test_server_dispatch_table_covers_all_phase3_tools():
    from mk_plan_master.server import _DISPATCH, list_tools

    declared = {t.name for t in asyncio.run(list_tools())}
    dispatched = set(_DISPATCH.keys())

    assert declared == dispatched
    # Phase 3 + add_initiative + analyze_initiative: 15 tools total in v0.1.
    assert len(declared) == 15
    assert "score_initiative" in declared
    assert "rank_backlog" in declared
    assert "generate_spec_draft" in declared
    assert "add_initiative" in declared
    assert "analyze_initiative" in declared


# ---------- bridge formatting unit ------------------------------------


def test_spec_draft_acs_match_mk_spec_master_heading_regex():
    """The rendered markdown's `## Acceptance criteria` heading must be the
    exact form mk-spec-master.parse_spec looks for. We replicate the regex
    here (not import — the family deliberately doesn't take a runtime dep
    on its sibling) and assert the output matches."""
    import re

    from mk_plan_master.tools.bridge import generate_spec_draft_tool

    result = generate_spec_draft_tool({"initiative_id": "LIN-003"})
    md = result["markdown"]

    ac_re = re.compile(
        r"^\s*#{1,6}\s*(acceptance\s*criteria|acceptance|ac|requirements)\s*:?\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    assert ac_re.search(md) is not None

    # And the rendered output must include at least one numbered list item
    # under that heading.
    after = md.split("## Acceptance criteria", 1)[1]
    item_re = re.compile(r"^\s*\d+[.)]\s+\S", re.MULTILINE)
    assert item_re.search(after) is not None
