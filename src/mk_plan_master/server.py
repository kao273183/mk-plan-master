"""MCP entrypoint. Registers + dispatches the v0.1 tool surface.

Tool descriptions read like operating manuals — they tell the AI client
when to call this vs another tool, what shape comes back, and which
downstream tool to hand off to. Phase 3 wires up:
- JIRA + Notion adapters
- plan-knowledge tools (init / get)
- roadmap tools (generate / analyze balance)
- self-reinforcement tools (history / decision signature / telemetry)

call_tool is wrapped in a telemetry timer so get_telemetry can surface
usage / error patterns. Only tool name + duration + ok flag are recorded —
argument values are never logged.
"""

import asyncio
import json
from typing import Any, Callable

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .tools import initiatives as initiatives_tools
from .tools import analysis as analysis_tools
from .tools import scoring as scoring_tools
from .tools import bridge as bridge_tools
from .tools import plan_knowledge as plan_knowledge_tools
from .tools import roadmap as roadmap_tools
from .tools import history as history_tools
from .tools import telemetry as telemetry_tools

app = Server("mk-plan-master")


_DISPATCH: dict[str, Callable[[dict], dict]] = {
    "get_plan_source_info": initiatives_tools.get_plan_source_info_tool,
    "list_initiatives": initiatives_tools.list_initiatives_tool,
    "fetch_initiative": initiatives_tools.fetch_initiative_tool,
    "add_initiative": initiatives_tools.add_initiative_tool,
    "analyze_initiative": analysis_tools.analyze_initiative_tool,
    "score_initiative": scoring_tools.score_initiative_tool,
    "rank_backlog": scoring_tools.rank_backlog_tool,
    "generate_spec_draft": bridge_tools.generate_spec_draft_tool,
    "generate_roadmap": roadmap_tools.generate_roadmap_tool,
    "analyze_roadmap_balance": roadmap_tools.analyze_roadmap_balance_tool,
    "init_plan_knowledge": plan_knowledge_tools.init_plan_knowledge_tool,
    "get_plan_context": plan_knowledge_tools.get_plan_context_tool,
    "get_planning_history": history_tools.get_planning_history_tool,
    "get_decision_signature": history_tools.get_decision_signature_tool,
    "get_telemetry": telemetry_tools.get_telemetry_tool,
}


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_plan_source_info",
            description=(
                "Return the active initiative source (selected via PLAN_SOURCE env var) "
                "plus all adapters built into this server. Call first in any "
                "session so the AI knows whether to expect markdown / Linear / "
                "JIRA / Notion semantics. "
                "Returns {active, available, version}."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="list_initiatives",
            description=(
                "Enumerate product initiatives from the active source. For "
                "markdown_local this globs PLAN_PROJECT_ROOT/initiatives/*.md and "
                "reads YAML-ish frontmatter; for linear it queries the GraphQL API "
                "for issues in triage / backlog / unstarted state types; for jira "
                "it runs JQL filtered to statusCategory='To Do'; for notion it "
                "queries the database and filters to status in (Triage / Backlog / "
                "Idea). Optional filters: status (string — adapter-specific), label "
                "(string — single label match), limit (int, default 50). "
                "Returns {source, count, initiatives[]}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "label": {"type": "string"},
                    "limit": {"type": "integer", "default": 50},
                },
            },
        ),
        Tool(
            name="fetch_initiative",
            description=(
                "Pull a single initiative by id from the active source. Returns "
                "the full Initiative record {id, source, title, body, url, status, "
                "labels, raw_metadata}. raw_metadata holds scoring inputs (reach / "
                "impact / confidence / effort / okr) plus any source-specific "
                "fields. Pair with score_initiative to get a RICE / Impact-Effort rank."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "initiative_id": {"type": "string"},
                },
                "required": ["initiative_id"],
            },
        ),
        Tool(
            name="add_initiative",
            description=(
                "Write a new markdown_local initiative into "
                "PLAN_PROJECT_ROOT/initiatives/<id>.md. Use this to capture an "
                "idea you (the AI client) already gathered via WebFetch / chat "
                "summary / customer-call notes — plan-master deliberately does "
                "NOT crawl URLs; you summarize, this tool persists. Only works "
                "when PLAN_SOURCE=markdown_local; for Linear / JIRA / Notion, "
                "create the issue in that platform instead. If id is omitted, "
                "auto-generates IDEA-NNN. Returns {id, written_to, source, "
                "overwritten, next_step_hint}. Typical chain: add_initiative "
                "-> score_initiative -> generate_spec_draft -> "
                "mk-spec-master.parse_spec."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "id": {"type": "string"},
                    "status": {"type": "string", "default": "triage"},
                    "labels": {"type": "array", "items": {"type": "string"}},
                    "reach": {"type": "number"},
                    "impact": {"type": "number"},
                    "confidence": {"type": "number"},
                    "effort": {"type": "number"},
                    "okr": {"type": "string"},
                    "out_of_scope": {"type": "array", "items": {"type": "string"}},
                    "source_url": {"type": "string"},
                    "overwrite": {"type": "boolean", "default": False},
                },
                "required": ["title"],
            },
        ),
        Tool(
            name="analyze_initiative",
            description=(
                "Force a senior-PM analysis SOP on one initiative BEFORE scoring. "
                "Returns the initiative body + a structured checklist (target users / "
                "competition / market signal / risks / MVP scope / out-of-scope / "
                "RICE rationale) the AI client must fill in inline as its response. "
                "Loads plan-knowledge.md context if present. The tool does NOT call "
                "an LLM — it scaffolds the prompt so the AI doesn't shortcut into a "
                "shallow read. Use this WHENEVER an idea originates from chat / "
                "WebFetch and lacks a thorough product analysis. After filling the "
                "checklist, call add_initiative(overwrite=true) with the enriched "
                "body, then score_initiative. Framework options: 'default' (7 "
                "sections), 'lite' (4 sections), 'lean_canvas' (9 blocks). "
                "Returns {initiative, framework, methodology_context, "
                "analysis_checklist, instructions, next_step_hint}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "initiative_id": {"type": "string"},
                    "framework": {
                        "type": "string",
                        "default": "default",
                    },
                },
                "required": ["initiative_id"],
            },
        ),
        Tool(
            name="score_initiative",
            description=(
                "Score one initiative with RICE or Impact-Effort. Pass "
                "initiative_id to score a source-resolved record (RICE inputs are "
                "read from raw_metadata) or raw_text + overrides for an ad-hoc "
                "score without a source record. method = 'rice' (default) or "
                "'impact_effort'. overrides = {reach, impact, confidence, effort} "
                "— any subset; takes precedence over what was in the source. "
                "RICE tier thresholds: P0 > 25, P1 10..25, P2 3..10, P3 < 3. "
                "Every call with initiative_id appends a `scored` decision to the "
                "index at PLAN_PROJECT_ROOT/.mk-plan-master/index.json. "
                "Returns {initiative_id, method, score, breakdown, tier, "
                "rationale, stored}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "initiative_id": {"type": "string"},
                    "raw_text": {"type": "string"},
                    "method": {"type": "string", "default": "rice"},
                    "overrides": {"type": "object"},
                },
            },
        ),
        Tool(
            name="rank_backlog",
            description=(
                "Score every initiative the active adapter exposes and return the "
                "top-N descending. Pure arithmetic, no LLM call — the rationale "
                "string is generated from the breakdown so the output stays "
                "deterministic. Optional filters mirror list_initiatives: status, "
                "label. method defaults to 'rice'; limit defaults to 10. "
                "Auto-archives a snapshot to .mk-plan-master/history/<ts>.json so "
                "get_planning_history / get_decision_signature can compute trend "
                "deltas across cycles (debounced to 5 minutes by default). "
                "Returns {method, count, ranking[]}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "method": {"type": "string", "default": "rice"},
                    "status": {"type": "string"},
                    "label": {"type": "string"},
                    "limit": {"type": "integer", "default": 10},
                },
            },
        ),
        Tool(
            name="generate_spec_draft",
            description=(
                "Produce a markdown spec draft for one initiative, shaped so "
                "mk-spec-master.parse_spec(raw_text=...) can ingest it verbatim. "
                "Three templates: 'default' (title / source / OKR / context / "
                "acceptance criteria / out-of-scope), 'lite' (title / context / "
                "acceptance criteria), 'detailed' (default + risks + dependencies "
                "+ estimated effort). Appends a `spec_generated` decision to the "
                "index. Returns {markdown, suggested_filename, template_used, "
                "ready_for_mk_spec_master, next_step_hint}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "initiative_id": {"type": "string"},
                    "template": {"type": "string", "default": "default"},
                },
                "required": ["initiative_id"],
            },
        ),
        Tool(
            name="generate_roadmap",
            description=(
                "Pack the ranked backlog into a quarterly roadmap markdown, "
                "respecting an engineering capacity envelope (in engineer-months "
                "× 4 person-weeks) minus a buffer (default 20%). Uses a greedy "
                "score-per-effort packer — items with the highest RICE-per-pw "
                "ratio land first. Output is split into P0 commitments / P1 "
                "commitments / P2 stretch / Deferred / Capacity summary. "
                "Required: capacity_engineer_months (float), period (str like "
                "'Q3 2026'). Optional: okr (str — pinned at top), method "
                "(default 'rice'), buffer_pct (default 20). "
                "Returns {markdown, scheduled[], deferred[], capacity_used_pw, "
                "capacity_total_pw, buffer_pw, method, period}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "capacity_engineer_months": {"type": "number"},
                    "period": {"type": "string"},
                    "okr": {"type": "string"},
                    "method": {"type": "string", "default": "rice"},
                    "buffer_pct": {"type": "number", "default": 20},
                    "status": {"type": "string"},
                    "label": {"type": "string"},
                },
                "required": ["capacity_engineer_months", "period"],
            },
        ),
        Tool(
            name="analyze_roadmap_balance",
            description=(
                "Classify the top-N ranked initiatives into feature / tech_debt / "
                "strategic / unlabeled buckets by label, then surface ratio + "
                "score-share + a terse heuristic advisory. Use when a user asks "
                "'is the roadmap balanced' / 'are we starving tech debt' / 'do we "
                "have any strategic bets'. Label vocabularies are configurable: "
                "feature_labels (default ['feature', 'product']), tech_debt_labels "
                "(default ['tech-debt', 'refactor', 'infra']), strategic_labels "
                "(default ['strategic', 'bet', 'moonshot']). "
                "Returns {method, totals, ratio_pct, score_share_pct, advisory}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "method": {"type": "string", "default": "rice"},
                    "limit": {"type": "integer", "default": 30},
                    "feature_labels": {"type": "array", "items": {"type": "string"}},
                    "tech_debt_labels": {"type": "array", "items": {"type": "string"}},
                    "strategic_labels": {"type": "array", "items": {"type": "string"}},
                },
            },
        ),
        Tool(
            name="init_plan_knowledge",
            description=(
                "Create PLAN_PROJECT_ROOT/plan-knowledge.md from a starter "
                "template. The file carries methodology (RICE, WSJF, Impact-"
                "Effort, OKR mapping, INVEST, personas / job-stories, decision-"
                "log convention) plus TODO sections for active OKRs / personas "
                "/ strategic bets / tech-debt zones / glossary / roadmap rhythm. "
                "Other mk-plan-master tools lean on this indirectly via "
                "get_plan_context. Idempotent — refuses to overwrite an existing "
                "file unless overwrite=true. Optional project_name labels the file. "
                "Override location via the PLAN_KNOWLEDGE_FILE env var."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {"type": "string"},
                    "overwrite": {"type": "boolean", "default": False},
                },
            },
        ),
        Tool(
            name="get_plan_context",
            description=(
                "Read PLAN_PROJECT_ROOT/plan-knowledge.md (or fall back to built-in "
                "defaults if missing). Call near the start of a planning session "
                "so the same methodology + domain glossary colours every scoring "
                "decision that follows. Optional `section` filters to a single "
                "heading (partial-match, case-insensitive) — e.g. section='RICE' "
                "returns just the RICE block. "
                "Returns {source: 'file'|'builtin', content, ...}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "description": "Optional heading filter (partial match, case-insensitive).",
                    },
                },
            },
        ),
        Tool(
            name="get_planning_history",
            description=(
                "Return trend deltas (current vs ~7 days ago / vs window_days ago) "
                "for the top-10 RICE-ranked backlog snapshots archived by "
                "rank_backlog. Surfaces churn (entries added/dropped) plus the "
                "average score of the current top-10. Use when a user asks 'are we "
                "improving' / 'show me the trend' / 'is the same idea always at "
                "the top'. Returns {snapshots_count, trend_7d, trend_30d, summary}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "window_days": {"type": "integer", "default": 30},
                },
            },
        ),
        Tool(
            name="get_decision_signature",
            description=(
                "Scan history + index for chronic patterns: ghost initiatives "
                "(appear in top-10 in >50% of snapshots but never spec_generated), "
                "score whiplash (RICE swings >50% between snapshots → bad data "
                "quality), orphan OKRs (OKRs in the index with zero initiatives in "
                "the current top-10). "
                "Use when a user asks 'which ideas keep getting punted' / 'why "
                "does this score keep moving' / 'which OKR has no execution'. "
                "Args: window_days (default 30). "
                "Returns {ghost_initiatives, score_whiplash, orphan_okrs, summary}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "window_days": {"type": "integer", "default": 30},
                },
            },
        ),
        Tool(
            name="get_telemetry",
            description=(
                "Aggregate the tool-usage log written by this server. Surfaces: "
                "which tools are called most, which fail most (error rate), p50 / "
                "p95 / p99 latency, and which declared tools have never been "
                "called in the window (dead surface). Records contain only tool "
                "name + timing + ok flag — argument values are never logged. "
                "Use when a user asks 'what's the AI actually using' / 'which "
                "tools are slow' / 'which tools are unused'. "
                "Args: window_days (default 7). "
                "Returns {calls_total, calls_by_tool, error_rate_pct, p50_ms, "
                "p95_ms, p99_ms, top_tools[], dead_tools[]}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "window_days": {"type": "integer", "default": 7},
                },
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    handler = _DISPATCH.get(name)
    if handler is None:
        return [
            _text(
                {
                    "error": f"unknown tool: {name}",
                    "available": sorted(_DISPATCH),
                }
            )
        ]

    # v0.1 self-reinforcement: wrap dispatch in a telemetry timer. Records
    # {ts, tool, ok, duration_ms} to telemetry.jsonl — argument values never.
    with telemetry_tools._Timer(name):
        try:
            result = handler(arguments or {})
        except Exception as exc:
            result = {
                "error": str(exc),
                "error_type": type(exc).__name__,
                "tool": name,
            }
    return [_text(result)]


def _text(payload: dict) -> TextContent:
    return TextContent(
        type="text", text=json.dumps(payload, ensure_ascii=False, indent=2)
    )


async def main():
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())


def run():
    asyncio.run(main())


if __name__ == "__main__":
    run()
