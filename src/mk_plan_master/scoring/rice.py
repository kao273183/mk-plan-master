"""RICE scoring: (reach * impact * confidence) / max(effort, 1).

Inputs:
    reach       int   users/quarter affected
    impact      float one of 0.25 / 0.5 / 1 / 2 / 3 (minimal..massive)
    confidence  float 0..1 — how sure are we about the other three
    effort      int   person-weeks; clamped >= 1 to avoid div-by-zero

Tier thresholds from PRD section 15 Q2 (defaults, not yet configurable):
    P0  > 25
    P1  10..25
    P2  3..10
    P3  < 3
"""

RICE_DEFAULTS = {
    "reach": 0,
    "impact": 1.0,
    "confidence": 0.5,
    "effort": 1,
}

# Canonical impact scale per Intercom's original RICE post — kept here so a
# future score_initiative_tool can map "high" -> 2 etc. without re-deriving.
IMPACT_LEVELS = {
    "minimal": 0.25,
    "low": 0.5,
    "medium": 1.0,
    "high": 2.0,
    "massive": 3.0,
}


def rice_score(reach: float, impact: float, confidence: float, effort: float) -> float:
    """Compute the RICE score. Returns a float rounded to one decimal so
    the wire shape stays stable across runs."""
    safe_effort = max(float(effort), 1.0)
    score = (float(reach) * float(impact) * float(confidence)) / safe_effort
    return round(score, 1)


def rice_tier(score: float) -> str:
    if score > 25:
        return "P0"
    if score >= 10:
        return "P1"
    if score >= 3:
        return "P2"
    return "P3"


def rice_rationale(reach: float, impact: float, confidence: float, effort: float) -> str:
    """Terse one-liner explaining the score. <= 80 chars, no LLM call.
    Built from the breakdown so it stays deterministic across runs."""
    parts = []
    if reach >= 500:
        parts.append("broad reach")
    elif reach >= 100:
        parts.append("moderate reach")
    else:
        parts.append("narrow reach")

    if impact >= 2:
        parts.append("high impact")
    elif impact >= 1:
        parts.append("medium impact")
    else:
        parts.append("low impact")

    if confidence >= 0.8:
        parts.append("strong confidence")
    elif confidence >= 0.5:
        parts.append("medium confidence")
    else:
        parts.append("low confidence")

    if effort <= 2:
        parts.append("small effort")
    elif effort <= 8:
        parts.append("contained effort")
    else:
        parts.append("large effort")

    out = ", ".join(parts)
    return out[:80]
