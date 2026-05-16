"""Read/write the decision index. Shape documented in docs/prd.md section 9.

Module attributes on `config` are looked up at call time (not bound at
import time) so tests can monkeypatch INDEX_PATH / INDEX_DIR cleanly.
"""

import json
from datetime import datetime, timezone
from typing import Any

from .. import config


def _empty_index() -> dict:
    """Fresh empty index each call. Was kept as a module-level dict in the
    spec-master sibling and the comment-of-why is: shallow-copying it leaks
    the nested `initiatives` reference across callers."""
    return {"version": 1, "initiatives": {}, "rejected": [], "shipped": []}


EMPTY_INDEX: dict = _empty_index()


def load_index() -> dict:
    if not config.INDEX_PATH.exists():
        return _empty_index()
    return json.loads(config.INDEX_PATH.read_text(encoding="utf-8"))


def save_index(index: dict) -> None:
    config.INDEX_DIR.mkdir(parents=True, exist_ok=True)
    config.INDEX_PATH.write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_initiative(
    index: dict, initiative_id: str, *, source: str = "", title: str = "", url: str = ""
) -> dict:
    """Return the (creating if necessary) per-initiative record under
    index['initiatives'][initiative_id]. Identity-preserving — caller can
    mutate the returned dict and the index reflects it."""
    initiatives = index.setdefault("initiatives", {})
    record = initiatives.get(initiative_id)
    if record is None:
        record = {
            "source": source,
            "title": title,
            "url": url,
            "decisions": [],
        }
        initiatives[initiative_id] = record
    else:
        # Backfill identity fields if the original write didn't have them
        # (e.g. a manual `raw_text` score followed later by a real fetch).
        if source and not record.get("source"):
            record["source"] = source
        if title and not record.get("title"):
            record["title"] = title
        if url and not record.get("url"):
            record["url"] = url
        record.setdefault("decisions", [])
    return record


def record_score(
    initiative_id: str,
    *,
    method: str,
    score: float,
    tier: str,
    breakdown: dict[str, Any],
    source: str = "",
    title: str = "",
    url: str = "",
) -> None:
    """Append a scoring decision and update the top-level summary fields
    (last_score / last_scored / method / tier) for quick read-back."""
    index = load_index()
    record = _ensure_initiative(
        index, initiative_id, source=source, title=title, url=url
    )

    ts = _now()
    record["last_scored"] = ts
    record["last_score"] = score
    record["method"] = method
    record["tier"] = tier
    record["decisions"].append(
        {
            "ts": ts,
            "action": "scored",
            "details": {"method": method, "score": score, "tier": tier, **breakdown},
        }
    )
    save_index(index)


def record_spec_generated(
    initiative_id: str,
    *,
    template: str,
    suggested_filename: str,
    source: str = "",
    title: str = "",
    url: str = "",
) -> None:
    """Append a `spec_generated` decision. Does NOT update tier/score —
    those stay owned by record_score."""
    index = load_index()
    record = _ensure_initiative(
        index, initiative_id, source=source, title=title, url=url
    )
    record["decisions"].append(
        {
            "ts": _now(),
            "action": "spec_generated",
            "details": {
                "template": template,
                "suggested_filename": suggested_filename,
            },
        }
    )
    save_index(index)
