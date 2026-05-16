"""Initiative-discovery tools.

list_initiatives_tool / fetch_initiative_tool are thin wrappers over the
active adapter. add_initiative_tool writes a new markdown_local initiative
so AI clients can capture web-research / chat ideas without leaving the
session — the family deliberately does not crawl the web; the AI client
(Claude / Cursor) already does that, and this tool is the structured
hand-off back into plan-master's pipeline.

Failures return the structured error shape {error, retryable, hint} so AI
clients can recover or surface the issue.
"""

import re
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from .. import __version__, config as _cfg
from ..adapters import REGISTRY, get_source
from ..config import SOURCE_NAME

_AUTO_ID_PATTERN = re.compile(r"^IDEA-(\d+)\.md$")


def _error(message: str, *, retryable: bool, hint: str) -> dict[str, Any]:
    return {"error": message, "retryable": retryable, "hint": hint}


def get_plan_source_info_tool(_: dict) -> dict[str, Any]:
    return {
        "active": SOURCE_NAME,
        "available": sorted(REGISTRY),
        "version": __version__,
    }


def list_initiatives_tool(arguments: dict) -> dict[str, Any]:
    status = arguments.get("status")
    label = arguments.get("label")
    limit = arguments.get("limit", 50)

    try:
        source = get_source(SOURCE_NAME)
    except ValueError as exc:
        return _error(
            str(exc),
            retryable=False,
            hint="Set PLAN_SOURCE to one of the available adapters.",
        )

    try:
        summaries = source.list_initiatives(status=status, label=label, limit=limit)
    except Exception as exc:
        return _error(
            f"{type(exc).__name__}: {exc}",
            retryable=True,
            hint="Check PLAN_PROJECT_ROOT exists and contains an initiatives/ folder.",
        )

    return {
        "source": SOURCE_NAME,
        "count": len(summaries),
        "initiatives": [asdict(s) for s in summaries],
    }


def fetch_initiative_tool(arguments: dict) -> dict[str, Any]:
    initiative_id = arguments.get("initiative_id") or arguments.get("id")
    if not initiative_id:
        return _error(
            "initiative_id is required",
            retryable=False,
            hint="Pass initiative_id (or id) — typically discovered via list_initiatives.",
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
            hint="Run list_initiatives first to confirm the id exists in the active source.",
        )
    except Exception as exc:
        return _error(
            f"{type(exc).__name__}: {exc}",
            retryable=True,
            hint="Transient adapter error — retry, then check adapter credentials / network.",
        )

    return asdict(initiative)


def _next_auto_id() -> str:
    if not _cfg.INITIATIVES_DIR.exists():
        return "IDEA-001"
    max_n = 0
    for path in _cfg.INITIATIVES_DIR.glob("IDEA-*.md"):
        m = _AUTO_ID_PATTERN.match(path.name)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"IDEA-{max_n + 1:03d}"


def _format_frontmatter_value(value: Any) -> str:
    """Inline-list + scalar formatter compatible with markdown_local._coerce."""
    if isinstance(value, list):
        if not value:
            return "[]"
        return "[" + ", ".join(str(x) for x in value) + "]"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def add_initiative_tool(arguments: dict) -> dict[str, Any]:
    if SOURCE_NAME != "markdown_local":
        return _error(
            f"add_initiative only supports markdown_local (active: {SOURCE_NAME})",
            retryable=False,
            hint=(
                "For linear / jira / notion, create the issue in that platform's "
                "UI (or its own MCP), then list_initiatives picks it up. "
                "add_initiative is for capturing chat / web-research ideas locally."
            ),
        )

    title = arguments.get("title")
    if not title:
        return _error(
            "title is required",
            retryable=False,
            hint="Pass a short human-readable title. Body + scoring inputs are optional.",
        )

    body = (arguments.get("body") or "").rstrip()
    initiative_id = str(arguments.get("id") or _next_auto_id())
    overwrite = bool(arguments.get("overwrite", False))

    _cfg.INITIATIVES_DIR.mkdir(parents=True, exist_ok=True)
    target = _cfg.INITIATIVES_DIR / f"{initiative_id}.md"
    already_existed = target.exists()
    if already_existed and not overwrite:
        return _error(
            f"initiative_id={initiative_id!r} already exists at {target}",
            retryable=False,
            hint="Pass overwrite=true to replace, or choose a different id.",
        )

    frontmatter: dict[str, Any] = {
        "id": initiative_id,
        "title": title,
        "status": arguments.get("status") or "triage",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    for key in (
        "labels",
        "reach",
        "impact",
        "confidence",
        "effort",
        "okr",
        "out_of_scope",
        "source_url",
    ):
        if arguments.get(key) is not None:
            frontmatter[key] = arguments[key]

    ordered_keys = [
        "id",
        "title",
        "status",
        "labels",
        "reach",
        "impact",
        "confidence",
        "effort",
        "okr",
        "out_of_scope",
        "source_url",
        "created_at",
    ]
    lines = ["---"]
    for key in ordered_keys:
        if key in frontmatter:
            lines.append(f"{key}: {_format_frontmatter_value(frontmatter[key])}")
    lines.append("---")
    lines.append("")
    lines.append(body)
    lines.append("")
    target.write_text("\n".join(lines), encoding="utf-8")

    return {
        "id": initiative_id,
        "written_to": str(target),
        "source": SOURCE_NAME,
        "overwritten": already_existed and overwrite,
        "next_step_hint": (
            f"Run score_initiative(initiative_id='{initiative_id}') or "
            f"list_initiatives to confirm pickup."
        ),
    }
