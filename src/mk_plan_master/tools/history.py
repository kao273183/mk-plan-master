"""History archive + trend tools for v0.1 self-reinforcement.

Every rank_backlog call writes a snapshot here (debounced to 5 minutes by
default — override via MK_PLAN_HISTORY_DEBOUNCE_SECONDS for tests). Other
tools read the archive to compute trend deltas and detect chronic patterns
(ghost initiatives, score whiplash, orphan OKRs).

Storage: <HISTORY_DIR>/<UTC-ISO-timestamp>.json — one file per snapshot.
Append-only. Old snapshots can be safely deleted by the user; tools degrade
gracefully (just less trend granularity).
"""

import datetime as _dt
import json
from typing import Any

from .. import config
from ..index import decisions as decisions_index


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _now_dt() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def _parse_ts(ts: str) -> _dt.datetime | None:
    try:
        return _dt.datetime.strptime(ts, "%Y-%m-%dT%H-%M-%SZ").replace(tzinfo=_dt.timezone.utc)
    except (TypeError, ValueError):
        return None


def archive_snapshot(snapshot: dict) -> str:
    """Write one snapshot JSON. Returns the path on success, "" on debounce or
    error. Failures are swallowed — history persistence must never break the
    live tool output."""
    try:
        config.HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        debounce = max(0, int(getattr(config, "HISTORY_DEBOUNCE_SECONDS", 300)))
        if debounce > 0:
            now = _now_dt()
            for existing in sorted(config.HISTORY_DIR.glob("*.json")):
                ts = _parse_ts(existing.stem)
                if ts is None:
                    continue
                if (now - ts).total_seconds() < debounce:
                    return ""
        stamped = dict(snapshot)
        stamped["timestamp"] = _now_iso()
        path = config.HISTORY_DIR / f"{stamped['timestamp']}.json"
        path.write_text(json.dumps(stamped, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return str(path)
    except (OSError, TypeError):
        return ""


def _read_snapshots(window_days: int | None = None) -> list[dict]:
    """Return snapshots in chronological order (oldest first). If
    window_days is set, filter to snapshots whose timestamp is within that
    window from now."""
    if not config.HISTORY_DIR.exists():
        return []
    files = sorted(config.HISTORY_DIR.glob("*.json"))
    out: list[dict] = []
    cutoff: _dt.datetime | None = None
    if window_days is not None:
        cutoff = _now_dt() - _dt.timedelta(days=window_days)
    for f in files:
        try:
            snap = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        ts = _parse_ts(snap.get("timestamp") or "")
        if cutoff is not None and ts is not None and ts < cutoff:
            continue
        out.append(snap)
    return out


def _top10_ids(snapshot: dict) -> set[str]:
    return {entry.get("id") for entry in snapshot.get("top10", []) if entry.get("id")}


def _avg_top10_score(snapshot: dict) -> float:
    entries = snapshot.get("top10", []) or []
    scores = [float(e.get("score", 0) or 0) for e in entries]
    if not scores:
        return 0.0
    return round(sum(scores) / len(scores), 2)


def _trend_block(snapshots: list[dict]) -> dict:
    if not snapshots:
        return {"avg_top10_score": 0.0, "new_top10_entries": [], "churned_top10_entries": []}
    latest = snapshots[-1]
    earliest = snapshots[0]
    latest_ids = _top10_ids(latest)
    earliest_ids = _top10_ids(earliest)
    return {
        "avg_top10_score": _avg_top10_score(latest),
        "new_top10_entries": sorted(latest_ids - earliest_ids),
        "churned_top10_entries": sorted(earliest_ids - latest_ids),
        "snapshots_in_window": len(snapshots),
    }


def get_planning_history_tool(arguments: dict) -> dict[str, Any]:
    """Return trend deltas (current vs ~7 days ago / vs ~30 days ago) for the
    top-10 RICE-ranked backlog. Surfaces churn (entries added/dropped) plus
    the average score of the current top-10.

    Args:
        window_days: int, default 30 — outer trend window. The 7d window is
        always computed in addition to window_days regardless of the value.
    """
    window_days = int(arguments.get("window_days", 30))
    all_snapshots = _read_snapshots()
    if not all_snapshots:
        return {
            "snapshots_count": 0,
            "trend_7d": {"avg_top10_score": 0.0, "new_top10_entries": [], "churned_top10_entries": []},
            "trend_30d": {"avg_top10_score": 0.0, "new_top10_entries": [], "churned_top10_entries": []},
            "summary": "No snapshots yet — call rank_backlog to start tracking.",
        }

    snaps_7d = _read_snapshots(window_days=7)
    snaps_window = _read_snapshots(window_days=window_days)

    trend_7d = _trend_block(snaps_7d or all_snapshots[-1:])
    trend_window = _trend_block(snaps_window or all_snapshots[-1:])

    latest = all_snapshots[-1]
    churn = len(trend_7d.get("new_top10_entries") or []) + len(trend_7d.get("churned_top10_entries") or [])
    parts = [
        f"{len(all_snapshots)} snapshot(s) archived; latest {latest.get('timestamp', '?')}.",
        f"Top-10 list churned by {churn} entries in last 7 days.",
    ]
    new_entries = trend_7d.get("new_top10_entries") or []
    if new_entries:
        parts.append(f"New into top-10 (7d): {', '.join(new_entries[:3])}.")

    return {
        "snapshots_count": len(all_snapshots),
        "window_days": window_days,
        "trend_7d": trend_7d,
        "trend_30d": trend_window,
        "summary": " ".join(parts),
    }


def get_decision_signature_tool(arguments: dict) -> dict[str, Any]:
    """Chronic patterns surfaced by cross-referencing the live decision index
    with history snapshots.

    - **ghost_initiatives**: appeared in top-10 in > 50% of snapshots in the
      last `window_days` but never had `spec_generated` recorded in the index.
    - **score_whiplash**: RICE score swung > 50% between two adjacent
      snapshots — usually means data quality is shaky.
    - **orphan_okrs**: OKR strings recorded in the live index but absent from
      the current top-10.

    Args:
        window_days: int, default 30.
    """
    window_days = int(arguments.get("window_days", 30))
    snapshots = _read_snapshots(window_days=window_days)
    index = decisions_index.load_index()
    initiatives = (index.get("initiatives") or {})

    # Empty-history path returns the canonical empty shape so the AI client
    # always sees the same keys.
    if not snapshots:
        return {
            "ghost_initiatives": [],
            "score_whiplash": [],
            "orphan_okrs": [],
            "summary": "Not enough history to detect patterns yet. Run rank_backlog over time.",
        }

    # ---- ghost initiatives ----
    appearance_counts: dict[str, int] = {}
    for snap in snapshots:
        for entry in snap.get("top10", []) or []:
            sid = entry.get("id")
            if sid:
                appearance_counts[sid] = appearance_counts.get(sid, 0) + 1

    half = max(1, len(snapshots) // 2)
    ghosts: list[dict] = []
    for sid, count in appearance_counts.items():
        if count <= half:
            continue
        record = initiatives.get(sid) or {}
        decisions = record.get("decisions") or []
        if any(d.get("action") == "spec_generated" for d in decisions):
            continue
        ghosts.append({"id": sid, "appearances": count, "snapshots": len(snapshots)})
    ghosts.sort(key=lambda r: -r["appearances"])

    # ---- score whiplash ----
    score_history: dict[str, list[tuple[str, float]]] = {}
    for snap in snapshots:
        ts = snap.get("timestamp", "")
        for entry in snap.get("all_scores", []) or []:
            sid = entry.get("id")
            score = entry.get("score")
            if sid is None or score is None:
                continue
            score_history.setdefault(sid, []).append((ts, float(score)))

    whiplash: list[dict] = []
    for sid, points in score_history.items():
        if len(points) < 2:
            continue
        worst = 0.0
        worst_from = 0.0
        worst_to = 0.0
        prev_score = points[0][1]
        for _, score in points[1:]:
            base = max(abs(prev_score), 0.1)
            delta_pct = abs(score - prev_score) / base
            if delta_pct > worst:
                worst = delta_pct
                worst_from = prev_score
                worst_to = score
            prev_score = score
        if worst > 0.5:
            whiplash.append(
                {
                    "id": sid,
                    "max_swing_pct": round(worst * 100, 1),
                    "from_score": worst_from,
                    "to_score": worst_to,
                }
            )
    whiplash.sort(key=lambda r: -r["max_swing_pct"])

    # ---- orphan OKRs ----
    # An OKR is orphan if it was mentioned by some snapshot's top-10 in the
    # window but is absent from the current top-10 — i.e. nothing in flight
    # against it. We also pull any OKR strings recorded on indexed initiatives
    # (future-proofing once raw_metadata is mirrored into the index).
    all_seen_okrs: set[str] = set()
    for snap in snapshots:
        for entry in snap.get("top10", []) or []:
            okr = entry.get("okr")
            if isinstance(okr, str) and okr:
                all_seen_okrs.add(okr)
    for record in initiatives.values():
        okr = (record.get("raw_metadata") or {}).get("okr")
        if isinstance(okr, str) and okr:
            all_seen_okrs.add(okr)

    latest_top10 = snapshots[-1].get("top10", []) or []
    top10_okrs: set[str] = set()
    for entry in latest_top10:
        okr = entry.get("okr")
        if isinstance(okr, str) and okr:
            top10_okrs.add(okr)

    orphan_okrs = sorted(all_seen_okrs - top10_okrs)

    summary_parts = [
        f"Scanned {len(snapshots)} snapshot(s) over {window_days} days.",
        f"{len(ghosts)} ghost initiative(s).",
        f"{len(whiplash)} score-whiplash case(s).",
        f"{len(orphan_okrs)} orphan OKR(s).",
    ]

    return {
        "ghost_initiatives": ghosts,
        "score_whiplash": whiplash,
        "orphan_okrs": orphan_okrs,
        "summary": " ".join(summary_parts),
    }
