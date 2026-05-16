"""analyze_initiative — meta-tool that forces a senior-PM analysis SOP.

The tool itself doesn't call an LLM. It packages the initiative + methodology
context + a structured checklist so the AI client can't shortcut into a
shallow 'looks good, ship it' read. Output is JSON; the AI client treats
the checklist as the response template, fills each section inline, then
re-calls add_initiative(overwrite=true) + score_initiative with the
enriched body. This is the same pattern as the family bridge:
mk-plan-master holds the rails, the AI client does the thinking.
"""

from dataclasses import asdict
from typing import Any

from .. import config as _cfg
from ..adapters import get_source
from ..config import SOURCE_NAME


_FRAMEWORKS: dict[str, list[dict[str, str]]] = {
    "default": [
        {
            "section": "Target users (3 personas)",
            "guidance": (
                "For each persona: who they are, the job-to-be-done they're hiring "
                "this for, and the trigger event that makes them look for a solution. "
                "Avoid generic 'startups' / 'enterprises' labels."
            ),
        },
        {
            "section": "Competition + differentiation",
            "guidance": (
                "Top 3 alternatives (incl. status-quo 'do nothing' if relevant). "
                "For each: what they do well, where they fall short, how this initiative "
                "is differentiated. Cite source URLs when available."
            ),
        },
        {
            "section": "Market signal / demand evidence",
            "guidance": (
                "What evidence shows demand exists? Customer quotes, search-volume "
                "estimates, competitor traction, similar product launches. If signal "
                "is weak, say so explicitly — that flows into a low RICE confidence."
            ),
        },
        {
            "section": "Top 3 risks",
            "guidance": (
                "Cover technical, market, and execution risks. For each: probability "
                "(low/med/high) + impact + a one-line mitigation."
            ),
        },
        {
            "section": "MVP scope",
            "guidance": (
                "The smallest version that validates the core hypothesis. List what's "
                "IN (3-7 bullets). The next section captures what's OUT."
            ),
        },
        {
            "section": "Out of scope (explicit)",
            "guidance": (
                "Non-goals to prevent scope creep. List things a reader might assume "
                "are included but aren't (yet)."
            ),
        },
        {
            "section": "RICE inputs with rationale",
            "guidance": (
                "reach (users/quarter affected), impact (0.25 / 0.5 / 1 / 2 / 3 — "
                "minimal / low / medium / high / massive), confidence (0..1 — drop "
                "below 0.6 if signal is weak), effort (person-weeks). Justify each "
                "number in one line; numbers without rationale are worthless."
            ),
        },
    ],
    "lite": [
        {
            "section": "Target users",
            "guidance": "1-3 personas + the job-to-be-done.",
        },
        {
            "section": "MVP scope",
            "guidance": "Smallest shippable version. 3-7 bullets.",
        },
        {
            "section": "Top 3 risks",
            "guidance": "Technical / market / execution. One-line mitigations.",
        },
        {
            "section": "RICE inputs with rationale",
            "guidance": (
                "reach / impact / confidence / effort + a one-line justification "
                "for each."
            ),
        },
    ],
    "lean_canvas": [
        {"section": "Problem", "guidance": "Top 3 problems this addresses."},
        {"section": "Customer segments", "guidance": "Early adopters first."},
        {"section": "Unique value proposition", "guidance": "Single clear message."},
        {"section": "Solution", "guidance": "Top 3 features mapping to the problems."},
        {"section": "Channels", "guidance": "How customers find this."},
        {"section": "Revenue streams", "guidance": "Pricing model + key assumptions."},
        {"section": "Cost structure", "guidance": "Fixed + variable costs."},
        {"section": "Key metrics", "guidance": "1-3 metrics that show this is working."},
        {"section": "Unfair advantage", "guidance": "What competitors can't easily copy."},
    ],
}


def _error(message: str, *, retryable: bool, hint: str) -> dict[str, Any]:
    return {"error": message, "retryable": retryable, "hint": hint}


def _read_knowledge_excerpt() -> str | None:
    path = _cfg.KNOWLEDGE_FILE
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    # Cap at 4000 chars so we don't blow the context window on a giant doc;
    # AI client can still call get_plan_context for more.
    return text[:4000] + ("\n...[truncated]" if len(text) > 4000 else "")


def analyze_initiative_tool(arguments: dict) -> dict[str, Any]:
    initiative_id = arguments.get("initiative_id")
    if not initiative_id:
        return _error(
            "initiative_id is required",
            retryable=False,
            hint="Pass initiative_id (discovered via list_initiatives).",
        )

    framework = (arguments.get("framework") or "default").lower()
    if framework not in _FRAMEWORKS:
        return _error(
            f"unknown framework: {framework!r}",
            retryable=False,
            hint=f"Use one of: {sorted(_FRAMEWORKS)}",
        )

    try:
        source = get_source(SOURCE_NAME)
    except ValueError as exc:
        return _error(
            str(exc),
            retryable=False,
            hint="Set PLAN_SOURCE to one of the available adapters.",
        )

    try:
        initiative = source.fetch(str(initiative_id))
    except ValueError as exc:
        return _error(
            str(exc),
            retryable=False,
            hint="Run list_initiatives first to confirm the id exists.",
        )
    except Exception as exc:
        return _error(
            f"{type(exc).__name__}: {exc}",
            retryable=True,
            hint="Transient adapter error — retry, then check credentials / network.",
        )

    knowledge = _read_knowledge_excerpt()

    return {
        "initiative": asdict(initiative),
        "framework": framework,
        "methodology_context": knowledge,
        "methodology_loaded": knowledge is not None,
        "analysis_checklist": _FRAMEWORKS[framework],
        "instructions": (
            "Fill in every section of analysis_checklist as your response, in order. "
            "Cite source_url where relevant. Numbers without rationale are not accepted. "
            "When done, call add_initiative(id=<initiative_id>, overwrite=true) with "
            "the enriched body, then score_initiative(initiative_id=<initiative_id>) "
            "to lock in the RICE result."
        ),
        "next_step_hint": (
            f"After analysis, run: add_initiative(id='{initiative_id}', overwrite=true, "
            f"body=<your filled-in analysis>) -> score_initiative -> "
            f"generate_spec_draft -> mk-spec-master.parse_spec."
        ),
    }
