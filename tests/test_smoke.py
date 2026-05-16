"""Smoke tests — exercise every Phase 1 tool end-to-end against the
three sample initiatives in examples/sample_initiatives.

These don't go through the MCP transport; they call the tool functions
directly. That keeps the harness simple and the failures legible.
"""

import asyncio


# ---------- importable check ------------------------------------------


def test_package_importable():
    import mk_plan_master

    assert mk_plan_master.__version__


# ---------- get_plan_source_info --------------------------------------


def test_get_plan_source_info_reports_markdown_local():
    from mk_plan_master.tools.initiatives import get_plan_source_info_tool

    info = get_plan_source_info_tool({})

    assert info["active"] == "markdown_local"
    assert "markdown_local" in info["available"]
    assert info["version"]


# ---------- list_initiatives ------------------------------------------


def test_list_initiatives_returns_three_samples():
    from mk_plan_master.tools.initiatives import list_initiatives_tool

    result = list_initiatives_tool({})

    assert result["source"] == "markdown_local"
    assert result["count"] == 3
    ids = sorted(i["id"] for i in result["initiatives"])
    assert ids == ["LIN-001", "LIN-002", "LIN-003"]


def test_list_initiatives_status_filter_excludes_nonmatching():
    from mk_plan_master.tools.initiatives import list_initiatives_tool

    result = list_initiatives_tool({"status": "nonexistent-status-zzz"})
    assert result["count"] == 0


# ---------- fetch_initiative ------------------------------------------


def test_fetch_initiative_returns_full_record():
    from mk_plan_master.tools.initiatives import fetch_initiative_tool

    initiative = fetch_initiative_tool({"initiative_id": "LIN-001"})

    assert initiative["id"] == "LIN-001"
    assert initiative["source"] == "markdown_local"
    assert initiative["title"]
    assert len(initiative["body"]) > 0
    # raw_metadata should carry RICE inputs from the sample frontmatter.
    assert "reach" in initiative["raw_metadata"]
    assert "impact" in initiative["raw_metadata"]
    assert "confidence" in initiative["raw_metadata"]
    assert "effort" in initiative["raw_metadata"]


def test_fetch_initiative_missing_id_returns_error_shape():
    from mk_plan_master.tools.initiatives import fetch_initiative_tool

    result = fetch_initiative_tool({})
    assert "error" in result
    assert "retryable" in result
    assert "hint" in result
    assert result["retryable"] is False


def test_fetch_initiative_unknown_id_returns_error_shape():
    from mk_plan_master.tools.initiatives import fetch_initiative_tool

    result = fetch_initiative_tool({"initiative_id": "LIN-999-does-not-exist"})
    assert "error" in result
    assert "retryable" in result
    assert "hint" in result


# ---------- server tool dispatch (lightweight) ------------------------


def test_server_dispatch_table_matches_declared_tools():
    """If a tool name is added to the list_tools schema, dispatch must also
    have it. This catches the easy 'forgot to wire it up' mistake. Phase 2's
    test_server_dispatch_table_covers_all_six_tools pins the exact count."""
    from mk_plan_master.server import _DISPATCH, list_tools

    declared = {t.name for t in asyncio.run(list_tools())}
    dispatched = set(_DISPATCH.keys())

    assert declared == dispatched, (
        f"declared - dispatched = {declared - dispatched}; "
        f"dispatched - declared = {dispatched - declared}"
    )
