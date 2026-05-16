"""add_initiative_tool — covers the WebFetch -> capture-as-markdown handoff
that the family relies on when an idea originates outside an existing
issue tracker.
"""

import pytest

from mk_plan_master.tools import initiatives as init_tools


def test_add_initiative_creates_file_with_auto_id(tmp_path):
    result = init_tools.add_initiative_tool(
        {"title": "Bulk-edit roles", "body": "Admins want to mass-assign roles."}
    )
    assert "error" not in result
    assert result["id"] == "IDEA-001"
    assert result["source"] == "markdown_local"
    assert result["overwritten"] is False

    target_path = init_tools._cfg.INITIATIVES_DIR / "IDEA-001.md"
    assert target_path.exists()
    content = target_path.read_text(encoding="utf-8")
    assert "title: Bulk-edit roles" in content
    assert "Admins want to mass-assign roles." in content


def test_add_initiative_explicit_id_and_full_frontmatter():
    result = init_tools.add_initiative_tool(
        {
            "id": "IDEA-042",
            "title": "Onboarding wizard like competitor X",
            "body": "Inspired by https://competitor.com/onboarding.",
            "status": "triage",
            "labels": ["growth", "activation"],
            "reach": 1200,
            "impact": 2,
            "confidence": 0.6,
            "effort": 5,
            "okr": "Q3-growth",
            "source_url": "https://competitor.com/onboarding",
        }
    )
    assert result["id"] == "IDEA-042"
    content = (init_tools._cfg.INITIATIVES_DIR / "IDEA-042.md").read_text(
        encoding="utf-8"
    )
    assert "labels: [growth, activation]" in content
    assert "reach: 1200" in content
    assert "confidence: 0.6" in content
    assert "source_url: https://competitor.com/onboarding" in content


def test_add_initiative_round_trips_through_markdown_local():
    """Written initiative must be discoverable + readable by the same
    adapter — otherwise the bridge to score / generate_spec_draft breaks."""
    init_tools.add_initiative_tool(
        {
            "id": "IDEA-100",
            "title": "Inline payment failure recovery",
            "body": "When checkout fails, surface retry inline.",
            "labels": ["growth"],
            "reach": 800,
            "impact": 1.5,
            "confidence": 0.7,
            "effort": 3,
        }
    )

    listing = init_tools.list_initiatives_tool({"limit": 100})
    ids = {i["id"] for i in listing["initiatives"]}
    assert "IDEA-100" in ids

    fetched = init_tools.fetch_initiative_tool({"initiative_id": "IDEA-100"})
    assert fetched["title"] == "Inline payment failure recovery"
    assert "retry inline" in fetched["body"]
    assert fetched["raw_metadata"]["reach"] == 800
    assert fetched["raw_metadata"]["impact"] == 1.5


def test_add_initiative_missing_title_returns_error():
    result = init_tools.add_initiative_tool({"body": "no title here"})
    assert result["error"] == "title is required"
    assert result["retryable"] is False


def test_add_initiative_duplicate_id_without_overwrite_errors():
    init_tools.add_initiative_tool({"id": "IDEA-200", "title": "First"})
    second = init_tools.add_initiative_tool({"id": "IDEA-200", "title": "Second"})
    assert "already exists" in second["error"]
    assert second["retryable"] is False


def test_add_initiative_overwrite_replaces():
    init_tools.add_initiative_tool(
        {"id": "IDEA-300", "title": "First version", "body": "v1"}
    )
    result = init_tools.add_initiative_tool(
        {
            "id": "IDEA-300",
            "title": "Second version",
            "body": "v2",
            "overwrite": True,
        }
    )
    assert result["overwritten"] is True
    content = (init_tools._cfg.INITIATIVES_DIR / "IDEA-300.md").read_text(
        encoding="utf-8"
    )
    assert "title: Second version" in content
    assert "v2" in content
    assert "v1" not in content


def test_add_initiative_non_markdown_source_returns_error(monkeypatch):
    monkeypatch.setattr(init_tools, "SOURCE_NAME", "linear")
    result = init_tools.add_initiative_tool({"title": "won't write"})
    assert "only supports markdown_local" in result["error"]
    assert result["retryable"] is False
    assert "Linear" in result["hint"] or "linear" in result["hint"]


def test_add_initiative_auto_id_increments_past_existing(tmp_path):
    init_tools.add_initiative_tool({"title": "First"})
    init_tools.add_initiative_tool({"title": "Second"})
    third = init_tools.add_initiative_tool({"title": "Third"})
    assert third["id"] == "IDEA-003"
