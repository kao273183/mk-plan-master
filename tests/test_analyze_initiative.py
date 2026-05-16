"""analyze_initiative_tool — the senior-PM-analysis meta-tool.

The tool packages framework + initiative + (optional) plan-knowledge.md
into a structured response the AI client treats as a fill-in template.
"""

from mk_plan_master.tools import analysis as analysis_tools


def test_analyze_initiative_returns_default_framework_with_seven_sections():
    result = analysis_tools.analyze_initiative_tool({"initiative_id": "LIN-001"})
    assert "error" not in result
    assert result["framework"] == "default"
    assert len(result["analysis_checklist"]) == 7
    section_names = [item["section"] for item in result["analysis_checklist"]]
    assert any("Target users" in s for s in section_names)
    assert any("RICE" in s for s in section_names)
    assert any("Out of scope" in s for s in section_names)


def test_analyze_initiative_embeds_full_initiative_record():
    result = analysis_tools.analyze_initiative_tool({"initiative_id": "LIN-001"})
    assert result["initiative"]["id"] == "LIN-001"
    assert "body" in result["initiative"]
    assert "raw_metadata" in result["initiative"]


def test_analyze_initiative_lite_framework_has_four_sections():
    result = analysis_tools.analyze_initiative_tool(
        {"initiative_id": "LIN-001", "framework": "lite"}
    )
    assert result["framework"] == "lite"
    assert len(result["analysis_checklist"]) == 4


def test_analyze_initiative_lean_canvas_has_nine_blocks():
    result = analysis_tools.analyze_initiative_tool(
        {"initiative_id": "LIN-001", "framework": "lean_canvas"}
    )
    assert result["framework"] == "lean_canvas"
    assert len(result["analysis_checklist"]) == 9
    names = [item["section"] for item in result["analysis_checklist"]]
    assert "Problem" in names
    assert "Unfair advantage" in names


def test_analyze_initiative_missing_id_returns_error():
    result = analysis_tools.analyze_initiative_tool({})
    assert result["error"] == "initiative_id is required"
    assert result["retryable"] is False


def test_analyze_initiative_unknown_framework_returns_error():
    result = analysis_tools.analyze_initiative_tool(
        {"initiative_id": "LIN-001", "framework": "not_a_framework"}
    )
    assert "unknown framework" in result["error"]
    assert result["retryable"] is False


def test_analyze_initiative_unknown_id_returns_error():
    result = analysis_tools.analyze_initiative_tool(
        {"initiative_id": "NOT-EXIST"}
    )
    assert result["retryable"] is False


def test_analyze_initiative_loads_methodology_when_knowledge_file_exists(tmp_path):
    knowledge = analysis_tools._cfg.KNOWLEDGE_FILE
    knowledge.write_text(
        "# Plan knowledge\n\n## RICE\nReach * Impact * Confidence / Effort.\n",
        encoding="utf-8",
    )
    result = analysis_tools.analyze_initiative_tool({"initiative_id": "LIN-001"})
    assert result["methodology_loaded"] is True
    assert "RICE" in result["methodology_context"]


def test_analyze_initiative_methodology_absent_when_no_knowledge_file():
    result = analysis_tools.analyze_initiative_tool({"initiative_id": "LIN-001"})
    assert result["methodology_loaded"] is False
    assert result["methodology_context"] is None


def test_analyze_initiative_instructions_mention_next_steps():
    result = analysis_tools.analyze_initiative_tool({"initiative_id": "LIN-001"})
    assert "add_initiative" in result["instructions"]
    assert "score_initiative" in result["instructions"]
