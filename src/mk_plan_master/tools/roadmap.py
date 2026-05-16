"""Roadmap tools — generate_roadmap + analyze_roadmap_balance.

generate_roadmap_tool ranks the backlog via rank_backlog, packs it into a
capacity envelope (engineer-months × 4 - buffer), and emits a markdown
roadmap split by tier.

analyze_roadmap_balance_tool classifies the top-N by label into
feature / tech_debt / strategic / unlabeled buckets and emits a terse
advisory based on simple ratio heuristics. No LLM call — keeps the wire
shape deterministic for tests + clients.
"""

from typing import Any

from ..adapters import get_source
from ..adapters.base import Initiative
from ..config import SOURCE_NAME
from ..scoring.rice import RICE_DEFAULTS, rice_score, rice_tier
from .scoring import _score_with_method


def _error(message: str, *, retryable: bool, hint: str) -> dict[str, Any]:
    return {"error": message, "retryable": retryable, "hint": hint}


def _fetch_all_initiatives(status: str | None = None, label: str | None = None, limit: int = 200) -> list[Initiative]:
    """Resolve full Initiative records from the active adapter. rank_backlog
    does the same but only returns rankings; we need the metadata (effort,
    OKR, labels) for capacity packing."""
    source = get_source(SOURCE_NAME)
    summaries = source.list_initiatives(status=status, label=label, limit=limit)
    out: list[Initiative] = []
    for s in summaries:
        try:
            out.append(source.fetch(s.id))
        except Exception:
            continue
    return out


def _effort_pw(meta: dict) -> float:
    """Effort in person-weeks. Falls back to a small RICE default so an
    unestimated initiative doesn't free-ride the capacity pack."""
    raw = meta.get("effort")
    try:
        value = float(raw) if raw is not None else float(RICE_DEFAULTS["effort"])
    except (TypeError, ValueError):
        value = float(RICE_DEFAULTS["effort"])
    return max(value, 1.0)


def _commitment_tier(idx: int) -> str:
    """Crude tiering by position once the schedule is packed. Top item is
    always P0; next two are P1; rest are P2 stretch. Aligns with the markdown
    bucket labels generate_roadmap emits."""
    if idx == 0:
        return "P0"
    if idx <= 2:
        return "P1"
    return "P2"


def generate_roadmap_tool(arguments: dict) -> dict[str, Any]:
    """Pack the backlog into a quarterly roadmap with capacity awareness.

    Args:
        capacity_engineer_months: float, required.
        period: str, required (e.g. "Q3 2026").
        okr: str, optional — pinned at top of the markdown.
        method: str, default "rice".
        buffer_pct: float, default 20 — uncommitted capacity reserved for
            unplanned work.
        status / label: pass-throughs to the active adapter's list filter.
    """
    if "capacity_engineer_months" not in arguments:
        return _error(
            "capacity_engineer_months is required",
            retryable=False,
            hint="Pass capacity in engineer-months for the roadmap period.",
        )
    if "period" not in arguments:
        return _error(
            "period is required",
            retryable=False,
            hint="Pass a label like 'Q3 2026' for the roadmap header.",
        )

    try:
        capacity_months = float(arguments["capacity_engineer_months"])
    except (TypeError, ValueError):
        return _error(
            "capacity_engineer_months must be numeric",
            retryable=False,
            hint="Pass a float — e.g. 4 for one engineer for a quarter.",
        )

    method = (arguments.get("method") or "rice").lower()
    buffer_pct = float(arguments.get("buffer_pct", 20))
    period = str(arguments["period"])
    okr = arguments.get("okr")
    status = arguments.get("status")
    label = arguments.get("label")

    try:
        initiatives = _fetch_all_initiatives(status=status, label=label, limit=200)
    except ValueError as exc:
        return _error(str(exc), retryable=False, hint="Set PLAN_SOURCE.")
    except Exception as exc:
        return _error(
            f"{type(exc).__name__}: {exc}",
            retryable=True,
            hint="Adapter call failed — check credentials / network.",
        )

    scored: list[dict] = []
    for ini in initiatives:
        result = _score_with_method(method, dict(ini.raw_metadata), {})
        scored.append(
            {
                "initiative": ini,
                "score": result["score"],
                "tier": result["tier"],
                "rationale": result["rationale"],
                "effort_pw": _effort_pw(ini.raw_metadata),
            }
        )

    # Greedy: rank by score-per-effort so capacity goes to the most efficient
    # initiatives first. Falls back to absolute score as the tiebreaker.
    scored.sort(
        key=lambda r: (
            -(r["score"] / max(r["effort_pw"], 1.0)),
            -r["score"],
        )
    )

    capacity_total_pw = capacity_months * 4.0
    buffer_pw = capacity_total_pw * (max(0.0, buffer_pct) / 100.0)
    capacity_for_planning = capacity_total_pw - buffer_pw

    scheduled: list[dict] = []
    deferred: list[dict] = []
    used = 0.0
    for r in scored:
        ini = r["initiative"]
        entry = {
            "initiative_id": ini.id,
            "title": ini.title,
            "score": r["score"],
            "estimated_effort_pw": r["effort_pw"],
            "okr": (ini.raw_metadata or {}).get("okr") or "",
            "labels": list(ini.labels or []),
            "rationale": r["rationale"],
        }
        if used + r["effort_pw"] <= capacity_for_planning:
            entry["tier"] = _commitment_tier(len(scheduled))
            scheduled.append(entry)
            used += r["effort_pw"]
        else:
            entry["tier"] = "deferred"
            deferred.append(entry)

    markdown = _render_roadmap_md(
        period=period,
        okr=okr,
        scheduled=scheduled,
        deferred=deferred,
        capacity_used_pw=round(used, 1),
        capacity_total_pw=round(capacity_total_pw, 1),
        buffer_pw=round(buffer_pw, 1),
        method=method,
    )

    return {
        "markdown": markdown,
        "scheduled": scheduled,
        "deferred": deferred,
        "capacity_used_pw": round(used, 1),
        "capacity_total_pw": round(capacity_total_pw, 1),
        "buffer_pw": round(buffer_pw, 1),
        "method": method,
        "period": period,
    }


def _render_roadmap_md(
    *,
    period: str,
    okr: str | None,
    scheduled: list[dict],
    deferred: list[dict],
    capacity_used_pw: float,
    capacity_total_pw: float,
    buffer_pw: float,
    method: str,
) -> str:
    lines: list[str] = [f"# Roadmap — {period}", ""]
    if okr:
        lines.append(f"> **Objective**: {okr}")
        lines.append("")

    for tier_label, tier_key in (("P0 commitments", "P0"), ("P1 commitments", "P1"), ("P2 stretch", "P2")):
        bucket = [e for e in scheduled if e.get("tier") == tier_key]
        lines.append(f"## {tier_label}")
        if not bucket:
            lines.append("- _none_")
        else:
            for e in bucket:
                lines.append(
                    f"- **{e['initiative_id']}** — {e['title']} "
                    f"(score {e['score']}, effort {e['estimated_effort_pw']:.1f} pw)"
                )
        lines.append("")

    lines.append("## Deferred")
    if not deferred:
        lines.append("- _none_")
    else:
        for e in deferred[:20]:
            lines.append(
                f"- {e['initiative_id']} — {e['title']} "
                f"(score {e['score']}, effort {e['estimated_effort_pw']:.1f} pw)"
            )
    lines.append("")

    lines.append("## Capacity summary")
    lines.append(f"- Method: {method}")
    lines.append(f"- Total capacity: {capacity_total_pw:.1f} person-weeks")
    lines.append(f"- Buffer reserved: {buffer_pw:.1f} pw")
    lines.append(f"- Committed: {capacity_used_pw:.1f} pw")
    lines.append("")
    return "\n".join(lines)


# ---------- analyze_roadmap_balance -----------------------------------


def _classify_labels(labels: list[str], feature: set[str], debt: set[str], strategic: set[str]) -> str:
    """Pick the first matching bucket — strategic > tech_debt > feature so a
    'strategic' label on a feature ticket gets the strategic credit."""
    lower = {l.lower() for l in (labels or [])}
    if lower & strategic:
        return "strategic"
    if lower & debt:
        return "tech_debt"
    if lower & feature:
        return "feature"
    return "unlabeled"


def _advisory(totals: dict, ratio_pct: dict) -> str:
    issues: list[str] = []
    f = ratio_pct.get("feature", 0)
    d = ratio_pct.get("tech_debt", 0)
    s = ratio_pct.get("strategic", 0)
    u = ratio_pct.get("unlabeled", 0)

    if totals.get("scored", 0) == 0:
        return "No labelled initiatives in the top window — call rank_backlog first or label your backlog."

    if f > 80:
        issues.append("Balance is feature-heavy")
    if d < 10:
        issues.append("tech-debt under-served")
    if s == 0:
        issues.append("no strategic bets")
    if u > 30:
        issues.append("many unlabeled items (cannot judge balance)")

    if not issues:
        return "Balance looks healthy across feature / debt / strategic."

    prefix = ", ".join(issues).capitalize() + "."
    return (
        prefix + " Aim for 60/30/10 (feature / debt / strategic) over a quarter; "
        "consider promoting any P0 tech-debt items."
    )


def analyze_roadmap_balance_tool(arguments: dict) -> dict[str, Any]:
    """Compute feature vs tech-debt vs strategic ratios across the top-N
    ranked initiatives.

    Args:
        method: default "rice".
        limit: default 30 — how many top-ranked initiatives to inspect.
        feature_labels: default ["feature", "product"].
        tech_debt_labels: default ["tech-debt", "refactor", "infra"].
        strategic_labels: default ["strategic", "bet", "moonshot"].
    """
    method = (arguments.get("method") or "rice").lower()
    limit = int(arguments.get("limit", 30))
    feature_labels = {l.lower() for l in (arguments.get("feature_labels") or ["feature", "product"])}
    debt_labels = {l.lower() for l in (arguments.get("tech_debt_labels") or ["tech-debt", "refactor", "infra"])}
    strategic_labels = {l.lower() for l in (arguments.get("strategic_labels") or ["strategic", "bet", "moonshot"])}

    try:
        initiatives = _fetch_all_initiatives(limit=limit * 2)
    except ValueError as exc:
        return _error(str(exc), retryable=False, hint="Set PLAN_SOURCE.")
    except Exception as exc:
        return _error(
            f"{type(exc).__name__}: {exc}",
            retryable=True,
            hint="Adapter call failed — check credentials / network.",
        )

    scored: list[dict] = []
    for ini in initiatives:
        result = _score_with_method(method, dict(ini.raw_metadata), {})
        scored.append({"initiative": ini, "score": float(result["score"])})

    scored.sort(key=lambda r: -r["score"])
    top = scored[:limit]

    totals = {"feature": 0, "tech_debt": 0, "strategic": 0, "unlabeled": 0, "scored": len(top)}
    score_sum = {"feature": 0.0, "tech_debt": 0.0, "strategic": 0.0, "unlabeled": 0.0}
    for entry in top:
        ini: Initiative = entry["initiative"]
        bucket = _classify_labels(list(ini.labels or []), feature_labels, debt_labels, strategic_labels)
        totals[bucket] += 1
        score_sum[bucket] += entry["score"]

    n = max(totals["scored"], 1)
    # Round to integers and balance any rounding drift so the four buckets sum
    # to exactly 100 (downstream tests assert this).
    raw_ratios = {k: totals[k] / n * 100.0 for k in ("feature", "tech_debt", "strategic", "unlabeled")}
    ratio_pct: dict[str, float] = {k: round(v, 0) for k, v in raw_ratios.items()}
    total_round = sum(ratio_pct.values())
    if total_round != 100 and totals["scored"]:
        drift = 100 - total_round
        # Apply the drift to the bucket with the largest fractional remainder
        # so the integers add up cleanly.
        max_key = max(raw_ratios.keys(), key=lambda k: raw_ratios[k] - int(raw_ratios[k]))
        ratio_pct[max_key] = ratio_pct[max_key] + drift

    total_score = sum(score_sum.values()) or 1.0
    score_share_pct = {k: round(v / total_score * 100, 1) for k, v in score_sum.items()}

    advisory = _advisory(totals, ratio_pct)

    return {
        "method": method,
        "totals": totals,
        "ratio_pct": ratio_pct,
        "score_share_pct": score_share_pct,
        "advisory": advisory,
    }
