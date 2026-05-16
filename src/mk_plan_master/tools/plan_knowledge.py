"""Plan-knowledge layer — methodology + domain glossary for planning.

Mirrors mk-spec-master's spec_knowledge pattern: a markdown file at
PLAN_PROJECT_ROOT/plan-knowledge.md carries methodology (RICE, WSJF,
Impact-Effort, OKR mapping, INVEST, personas / job-stories, decision-log
convention) plus the team's domain-specific glossary. score_initiative /
rank_backlog / generate_roadmap stay heuristic — they don't read this file
directly — but the AI client should call `get_plan_context` near the start
of a session so the same rules guide every scoring decision.

init_plan_knowledge_tool   writes a starter file (idempotent — never
                            overwrites unless overwrite=True).
get_plan_context_tool       reads the file (or built-in defaults), optionally
                            filtered by a section header for partial pulls.
"""

import re
from typing import Any

from .. import config


# Built-in starter content. Methodology block stays universal; the
# TODO blocks below are domain placeholders the project lead fills in.

_UNIVERSAL_METHODOLOGY = """\
## Universal planning methodology

### RICE — Reach × Impact × Confidence / Effort

The default scoring method. Each lane has a defined scale so two people scoring
the same initiative land within ~20% of each other.

- **Reach**: users (or events) affected per quarter. Integer.
- **Impact**: 0.25 (minimal) · 0.5 (low) · 1 (medium) · 2 (high) · 3 (massive).
  Massive means "this is the headline metric for the quarter". Resist the urge
  to score everything as high.
- **Confidence**: 0..1. Below 0.5 means the inputs themselves are guesses;
  consider running discovery before scoring.
- **Effort**: person-weeks. Honest estimate including review + ramp. Clamps to
  >= 1 to avoid division by zero.

Score = (reach × impact × confidence) / effort. Tiers: P0 > 25, P1 10..25,
P2 3..10, P3 < 3. The tier line is a heuristic — promote / demote one tier
with a single sentence of rationale rather than re-running the arithmetic.

### WSJF — Weighted Shortest Job First

The SAFe variant, surfaced for teams who prefer it to RICE. Compute Cost of
Delay = user_value + time_criticality + risk_reduction (each 1..10) and divide
by job_size (1..10). Higher number = do it first.

WSJF is best when there is a clear deadline pressure (regulatory, partnership
launch, seasonal demand). RICE is better when most work is open-ended.

### Impact-Effort 2×2

The lightweight method for early-stage triage. Plot each idea on a 1..5 impact
axis and 1..5 effort axis. Quadrants:

- **Quick win** (high impact, low effort) — ship first.
- **Big bet** (high impact, high effort) — needs a milestone plan.
- **Fill-in** (low impact, low effort) — fold into spare cycles.
- **Time sink** (low impact, high effort) — kill or revisit later.

### OKR mapping

Every committed initiative must reference one Objective. If an initiative
doesn't map to any active Objective, surface it in planning as "orphan" — it
either justifies a new Objective or shouldn't be on the roadmap.

Convention: store the OKR string in initiative `raw_metadata.okr`. The
`analyze_roadmap_balance` and `get_decision_signature` tools key off this
field to detect orphan / under-served OKRs.

### INVEST — initiative readiness

Before promoting an initiative from triage to "next sprint" tier, it should
pass INVEST:

- **Independent**  — ships without sequencing against another in-flight item
- **Negotiable**   — the *what* is fixed, the *how* is flexible
- **Valuable**     — observable to a user / customer / business
- **Estimable**    — engineering has enough detail to size effort
- **Small**        — fits one sprint / iteration; otherwise split
- **Testable**     — a clear pass/fail outcome exists per acceptance criterion

### Personas / Job-stories

Document the canonical personas alongside the methodology so AI-driven scoring
doesn't have to re-derive them. Job-stories follow:

> When <situation>, I want to <motivation>, so I can <expected outcome>.

Persona block lives in "Your personas" below. Empty until the project lead
fills it in.

### Decision-log convention

Every score / promotion / deferral / rejection should leave a one-line note in
the index. The `decisions[]` array under each initiative captures `scored`,
`spec_generated`, `deferred`, `rejected`, `shipped` actions with a timestamp.
Use `get_planning_history` to compare quarter-over-quarter; use
`get_decision_signature` to find ghost initiatives + score whiplash.

### Capacity & buffer

`generate_roadmap` expects engineering capacity in engineer-months. Multiply
by 4 to get person-weeks. Reserve a buffer (default 20%) for unplanned work —
production incidents, prod-pressure favours, ad-hoc support escalations. A
zero-buffer roadmap is a fiction.
"""

_DOMAIN_TODO_SECTIONS = """\
## Your active OKRs
- TODO: list the 3–5 Objectives you are committing to this quarter. Each line
  is one Objective. Initiatives reference these in `raw_metadata.okr`.

## Your personas
- TODO: who you build for (e.g., "Workspace owner — sets up the org, invites
  team, pays the bill"; "API consumer — integrates programmatically, cares
  about latency + error semantics"). Skip generic "user" — be specific.

## Your strategic bets
- TODO: the 1–2 multi-quarter bets you're committed to even at the expense of
  short-term metrics. These get top-of-roadmap pin treatment regardless of
  RICE score.

## Your tech-debt zones
- TODO: areas where debt is biting you (e.g., "search index rebuild",
  "billing reconciliation"). Initiatives touching these get a confidence
  boost when scoring because the team already knows the territory.

## Your glossary
- TODO: domain terms with one-line definitions. The canonical "Workspace",
  "Account", "Plan", "Cycle" — whatever your business calls them.

## Your roadmap rhythm
- TODO: planning cadence (weekly triage / monthly roadmap / quarterly OKR
  reset?) plus the calendar dates. Helps AI suggest realistic dates when
  generating roadmap markdown.
"""


_HEADING_RE = re.compile(r"^\s*#{1,6}\s*(.+?)\s*$", re.MULTILINE)


def _knowledge_path():
    return config.KNOWLEDGE_FILE


def _starter_content(project_name: str) -> str:
    return (
        f"# Plan knowledge — {project_name}\n\n"
        "> Methodology + domain glossary that mk-plan-master tools "
        "(`score_initiative`, `rank_backlog`, `generate_roadmap`, "
        "`analyze_roadmap_balance`) lean on indirectly. The AI client should "
        "call `get_plan_context` near the start of each session so the same "
        "rules colour every prioritisation decision that follows.\n\n"
        + _UNIVERSAL_METHODOLOGY
        + "\n"
        + _DOMAIN_TODO_SECTIONS
    )


def init_plan_knowledge_tool(arguments: dict) -> dict[str, Any]:
    """Create PLAN_PROJECT_ROOT/plan-knowledge.md from a starter template.

    Idempotent: refuses to clobber an existing file unless overwrite=True.
    """
    project_name = str(arguments.get("project_name") or config.PROJECT_ROOT.name)
    overwrite = bool(arguments.get("overwrite"))

    path = _knowledge_path()
    if path.exists() and not overwrite:
        return {
            "created": False,
            "path": str(path),
            "reason": "file already exists; pass overwrite=true to replace",
        }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_starter_content(project_name), encoding="utf-8")
    return {
        "created": True,
        "path": str(path),
        "bytes": path.stat().st_size,
    }


def _select_section(content: str, header: str) -> str:
    """Return the substring starting at a heading whose text matches
    `header` (case-insensitive, partial match) until the next heading
    of equal-or-greater depth. Empty string if no match."""
    header_norm = header.strip().lower()
    matches = list(_HEADING_RE.finditer(content))
    for i, m in enumerate(matches):
        text = m.group(1).strip().lower()
        if header_norm in text:
            start = m.start()
            hashes = re.match(r"^\s*(#+)", content[start:])
            this_depth = len(hashes.group(1)) if hashes else 1
            for nxt in matches[i + 1:]:
                next_hashes = re.match(r"^\s*(#+)", content[nxt.start():])
                next_depth = len(next_hashes.group(1)) if next_hashes else 1
                if next_depth <= this_depth:
                    return content[start:nxt.start()].rstrip() + "\n"
            return content[start:].rstrip() + "\n"
    return ""


def get_plan_context_tool(arguments: dict) -> dict[str, Any]:
    """Read PLAN_PROJECT_ROOT/plan-knowledge.md (or fall back to built-in
    defaults if missing). Optional `section` filters to a single block
    (partial-match, case-insensitive).
    """
    section = arguments.get("section")

    path = _knowledge_path()
    if path.exists():
        content = path.read_text(encoding="utf-8")
        source = "file"
    else:
        content = (
            "# Plan knowledge — (built-in defaults; run init_plan_knowledge to customise)\n\n"
            + _UNIVERSAL_METHODOLOGY
            + "\n"
            + _DOMAIN_TODO_SECTIONS
        )
        source = "builtin"

    if section:
        slice_ = _select_section(content, section)
        if not slice_:
            return {
                "source": source,
                "section": section,
                "found": False,
                "content": "",
                "available_sections": [m.group(1).strip() for m in _HEADING_RE.finditer(content)],
            }
        return {
            "source": source,
            "section": section,
            "found": True,
            "content": slice_,
        }

    return {
        "source": source,
        "content": content,
        "byte_count": len(content.encode("utf-8")),
    }
