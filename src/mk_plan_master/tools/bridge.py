"""generate_spec_draft tool — the bridge from mk-plan-master to mk-spec-master.

Output is markdown shaped so `mk-spec-master.parse_spec(raw_text=...)` can
ingest it verbatim with no manual cleanup. Every successful call appends a
`spec_generated` decision to the index so the audit trail captures the
hand-off moment.
"""

from typing import Any

from ..adapters import get_source
from ..bridge.spec_draft import TEMPLATES, render_spec_draft
from ..config import SOURCE_NAME
from ..index import decisions as decisions_index


def _error(message: str, *, retryable: bool, hint: str) -> dict[str, Any]:
    return {"error": message, "retryable": retryable, "hint": hint}


def generate_spec_draft_tool(arguments: dict) -> dict[str, Any]:
    initiative_id = arguments.get("initiative_id") or arguments.get("id")
    if not initiative_id:
        return _error(
            "initiative_id is required",
            retryable=False,
            hint="Pass initiative_id — typically the top result from rank_backlog.",
        )

    template = (arguments.get("template") or "default").lower()
    if template not in TEMPLATES:
        return _error(
            f"unknown template {template!r}",
            retryable=False,
            hint=f"Use one of {list(TEMPLATES)}.",
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
            hint="Run list_initiatives first to confirm the id.",
        )
    except Exception as exc:
        return _error(
            f"{type(exc).__name__}: {exc}",
            retryable=True,
            hint="Transient adapter error — retry, then check credentials / network.",
        )

    # If the initiative has already been scored, surface that priority in
    # the metadata block. We don't trigger scoring here on purpose — that's
    # score_initiative's job; this tool is purely a renderer.
    score_summary = _last_score_for(str(initiative_id))

    markdown = render_spec_draft(initiative, template, score_summary=score_summary)
    suggested_filename = f"{initiative.id}.md"

    try:
        decisions_index.record_spec_generated(
            str(initiative_id),
            template=template,
            suggested_filename=suggested_filename,
            source=initiative.source,
            title=initiative.title,
            url=initiative.url,
        )
    except OSError as exc:
        return _error(
            f"index write failed: {exc}",
            retryable=True,
            hint="Confirm PLAN_PROJECT_ROOT is writable.",
        )

    return {
        "markdown": markdown,
        "suggested_filename": suggested_filename,
        "template_used": template,
        "ready_for_mk_spec_master": True,
        "next_step_hint": (
            "Pass markdown into mk-spec-master.parse_spec(raw_text=...) to "
            "extract acceptance criteria."
        ),
    }


def _last_score_for(initiative_id: str) -> dict[str, Any] | None:
    """Pull tier/score/method from the index if a prior score_initiative
    call recorded them. Best-effort — any I/O hiccup returns None."""
    try:
        index = decisions_index.load_index()
    except (OSError, ValueError):
        return None
    record = (index.get("initiatives") or {}).get(initiative_id)
    if not record:
        return None
    if "last_score" not in record:
        return None
    return {
        "score": record.get("last_score"),
        "tier": record.get("tier"),
        "method": record.get("method"),
    }
