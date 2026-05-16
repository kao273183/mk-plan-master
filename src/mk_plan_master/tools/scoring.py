"""Scoring tools: score_initiative + rank_backlog.

score_initiative computes RICE / Impact-Effort for one initiative (either
fetched from the active adapter via initiative_id or provided ad-hoc via
raw_text + overrides). Every successful call appends a `scored` decision
to the index.

rank_backlog scores every initiative the active adapter exposes and
returns the top-N descending. Pure arithmetic, no LLM call — the rationale
string is generated from the breakdown so the output is deterministic.
"""

from typing import Any

from ..adapters import get_source
from ..adapters.base import Initiative
from ..config import SOURCE_NAME
from ..index import decisions as decisions_index
from ..scoring.impact_effort import (
    impact_effort_quadrant,
    impact_effort_rationale,
    impact_effort_score,
)
from ..scoring.rice import (
    IMPACT_LEVELS,
    RICE_DEFAULTS,
    rice_rationale,
    rice_score,
    rice_tier,
)

_VALID_METHODS = {"rice", "impact_effort"}


def _error(message: str, *, retryable: bool, hint: str) -> dict[str, Any]:
    return {"error": message, "retryable": retryable, "hint": hint}


def _coerce_impact(value: Any) -> float:
    """Accept the verbal labels (low / medium / high / massive) as well as
    raw floats. Default to medium (1.0) when missing or unparseable."""
    if value is None or value == "":
        return RICE_DEFAULTS["impact"]
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().lower()
    if text in IMPACT_LEVELS:
        return IMPACT_LEVELS[text]
    try:
        return float(text)
    except ValueError:
        return RICE_DEFAULTS["impact"]


def _to_float(value: Any, default: float) -> float:
    if value is None or value == "":
        return float(default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _rice_inputs(meta: dict, overrides: dict) -> dict:
    """Build the RICE input dict from initiative metadata, then apply any
    explicit overrides on top (AI / user wins over what's in the source)."""
    inputs = {
        "reach": _to_float(meta.get("reach"), RICE_DEFAULTS["reach"]),
        "impact": _coerce_impact(meta.get("impact")),
        "confidence": _to_float(meta.get("confidence"), RICE_DEFAULTS["confidence"]),
        "effort": _to_float(meta.get("effort"), RICE_DEFAULTS["effort"]),
    }
    if "reach" in overrides:
        inputs["reach"] = _to_float(overrides["reach"], inputs["reach"])
    if "impact" in overrides:
        inputs["impact"] = _coerce_impact(overrides["impact"])
    if "confidence" in overrides:
        inputs["confidence"] = _to_float(overrides["confidence"], inputs["confidence"])
    if "effort" in overrides:
        inputs["effort"] = _to_float(overrides["effort"], inputs["effort"])
    return inputs


def _impact_effort_inputs(meta: dict, overrides: dict) -> dict:
    """1..5 scale for both axes. If raw RICE-style values are present
    (impact 0.25..3), pass them through unchanged — the quadrant cutoff
    is independent of scale magnitude."""
    impact = _to_float(overrides.get("impact"), _coerce_impact(meta.get("impact")))
    effort = _to_float(overrides.get("effort"), _to_float(meta.get("effort"), 1))
    return {"impact": impact, "effort": effort}


def _score_with_method(method: str, meta: dict, overrides: dict) -> dict:
    """Returns {score, breakdown, tier, rationale}. Pure arithmetic — no
    side effects, no index writes; that's the caller's job."""
    if method == "rice":
        inputs = _rice_inputs(meta, overrides)
        score = rice_score(**inputs)
        return {
            "score": score,
            "breakdown": inputs,
            "tier": rice_tier(score),
            "rationale": rice_rationale(**inputs),
        }
    # impact_effort
    inputs = _impact_effort_inputs(meta, overrides)
    score = impact_effort_score(**inputs)
    return {
        "score": score,
        "breakdown": inputs,
        "tier": impact_effort_quadrant(**inputs),
        "rationale": impact_effort_rationale(**inputs),
    }


def _fetch_initiative(initiative_id: str) -> Initiative:
    source = get_source(SOURCE_NAME)
    return source.fetch(initiative_id)


def score_initiative_tool(arguments: dict) -> dict[str, Any]:
    method = (arguments.get("method") or "rice").lower()
    if method not in _VALID_METHODS:
        return _error(
            f"unknown scoring method: {method!r}",
            retryable=False,
            hint=f"Use one of {sorted(_VALID_METHODS)}.",
        )

    initiative_id = arguments.get("initiative_id")
    raw_text = arguments.get("raw_text")
    overrides = arguments.get("overrides") or {}

    if not initiative_id and not raw_text:
        return _error(
            "either initiative_id or raw_text is required",
            retryable=False,
            hint=(
                "Pass initiative_id (resolved via the active adapter) or "
                "raw_text + overrides for ad-hoc scoring without a source record."
            ),
        )

    initiative: Initiative | None = None
    meta: dict = {}
    title = ""
    url = ""
    source_name = ""

    if initiative_id:
        try:
            initiative = _fetch_initiative(str(initiative_id))
        except ValueError as exc:
            return _error(
                str(exc),
                retryable=False,
                hint="Confirm initiative_id via list_initiatives.",
            )
        except Exception as exc:
            return _error(
                f"{type(exc).__name__}: {exc}",
                retryable=True,
                hint="Transient adapter error — retry, then check credentials / network.",
            )
        meta = dict(initiative.raw_metadata)
        title = initiative.title
        url = initiative.url
        source_name = initiative.source

    result = _score_with_method(method, meta, overrides)
    used_id = str(initiative_id) if initiative_id else ""

    stored = False
    if used_id:
        try:
            decisions_index.record_score(
                used_id,
                method=method,
                score=result["score"],
                tier=result["tier"],
                breakdown=result["breakdown"],
                source=source_name,
                title=title,
                url=url,
            )
            stored = True
        except OSError as exc:
            return _error(
                f"index write failed: {exc}",
                retryable=True,
                hint="Confirm PLAN_PROJECT_ROOT is writable.",
            )

    return {
        "initiative_id": used_id,
        "method": method,
        "score": result["score"],
        "breakdown": result["breakdown"],
        "tier": result["tier"],
        "rationale": result["rationale"],
        "stored": stored,
    }


def rank_backlog_tool(arguments: dict) -> dict[str, Any]:
    method = (arguments.get("method") or "rice").lower()
    if method not in _VALID_METHODS:
        return _error(
            f"unknown scoring method: {method!r}",
            retryable=False,
            hint=f"Use one of {sorted(_VALID_METHODS)}.",
        )

    status = arguments.get("status")
    label = arguments.get("label")
    limit = int(arguments.get("limit") or 10)

    try:
        source = get_source(SOURCE_NAME)
    except ValueError as exc:
        return _error(
            str(exc),
            retryable=False,
            hint="Set PLAN_SOURCE to one of the available adapters.",
        )

    # We need full Initiative records (for raw_metadata) to score. Listing
    # is cheap, fetching is what costs network — but the markdown adapter
    # is free and Linear's GraphQL is fast enough. For Phase 2 the simple
    # fetch-per-listing is acceptable; v0.3 can add a batched query.
    try:
        summaries = source.list_initiatives(status=status, label=label, limit=limit * 4)
    except Exception as exc:
        return _error(
            f"{type(exc).__name__}: {exc}",
            retryable=True,
            hint="Adapter list call failed — check credentials / network.",
        )

    ranked: list[dict] = []
    okr_by_id: dict[str, str] = {}
    for summary in summaries:
        try:
            initiative = source.fetch(summary.id)
        except Exception:
            # One bad initiative shouldn't sink the whole ranking.
            continue
        scored = _score_with_method(method, dict(initiative.raw_metadata), {})
        okr_by_id[initiative.id] = (initiative.raw_metadata or {}).get("okr") or ""
        ranked.append(
            {
                "initiative_id": initiative.id,
                "title": initiative.title,
                "score": scored["score"],
                "tier": scored["tier"],
                "rationale": scored["rationale"],
            }
        )

    ranked.sort(key=lambda r: r["score"], reverse=True)
    all_scores = [
        {"id": r["initiative_id"], "score": r["score"], "tier": r["tier"]}
        for r in ranked
    ]
    ranked = ranked[:limit]

    # v0.1 self-reinforcement: archive a snapshot so get_planning_history can
    # render trend deltas. Local import keeps history out of the import cycle
    # (history imports config; we don't want server-load cost here).
    from .history import archive_snapshot

    top10 = [
        {
            "id": r["initiative_id"],
            "title": r["title"],
            "score": r["score"],
            "tier": r["tier"],
            "okr": okr_by_id.get(r["initiative_id"], ""),
        }
        for r in ranked[:10]
    ]
    archive_snapshot(
        {
            "method": method,
            "count": len(ranked),
            "top10": top10,
            "all_scores": all_scores,
        }
    )

    return {
        "method": method,
        "count": len(ranked),
        "ranking": ranked,
    }
