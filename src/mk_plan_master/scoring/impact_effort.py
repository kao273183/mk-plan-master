"""Impact-Effort 2x2 — the lightweight cousin of RICE.

Both axes 1..5. Score is `impact - effort` so the ranking still sorts
high-to-low and is comparable across initiatives. The quadrant string
is the human label PMs actually use in meetings.
"""

# Quadrant cutoff: 3 is the natural midpoint of a 1..5 scale.
_HIGH_CUTOFF = 3


def impact_effort_score(impact: float, effort: float) -> float:
    return round(float(impact) - float(effort), 1)


def impact_effort_quadrant(impact: float, effort: float) -> str:
    high_impact = float(impact) >= _HIGH_CUTOFF
    high_effort = float(effort) >= _HIGH_CUTOFF
    if high_impact and not high_effort:
        return "quick_win"
    if high_impact and high_effort:
        return "big_bet"
    if not high_impact and not high_effort:
        return "fill_in"
    return "time_sink"


def impact_effort_rationale(impact: float, effort: float) -> str:
    quadrant = impact_effort_quadrant(impact, effort)
    label = quadrant.replace("_", " ")
    return f"{label} (impact {impact}, effort {effort})"[:80]
