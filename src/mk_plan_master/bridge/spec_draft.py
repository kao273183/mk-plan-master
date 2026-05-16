"""Markdown spec-draft formatter.

Output shape is matched to mk-spec-master.parse_spec's heading regex:
    - H1 for title
    - `## Context` before AC
    - `## Acceptance criteria` followed by a numbered list
    - `## Out of scope` after AC (default + detailed templates only)

Three templates:
    default  : title / source / OKR / context / AC / out-of-scope
    lite     : title / context / AC                (3 sections; no OKR, no OOS)
    detailed : default + risks + dependencies + estimated effort

Acceptance criteria detection: we look for a `## Acceptance criteria` (or
the zh-TW `## 驗收條件`) heading already in the initiative body and reuse
its numbered list verbatim. If none is present, we emit a placeholder list
so the downstream parser still has structure to anchor on.
"""

import re
from typing import Any, Iterable

from ..adapters.base import Initiative

TEMPLATES = ("default", "lite", "detailed")

_AC_HEADING_RE = re.compile(
    r"^\s*#{1,6}\s*(?:acceptance\s*criteria|驗收條件|驗收標準)\s*:?\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_LIST_ITEM_RE = re.compile(r"^\s*(?:\d+[.)]|-|\*)\s+(.+?)$", re.MULTILINE)

_PLACEHOLDER_ACS = [
    "TODO: state the first observable behaviour required for this initiative.",
    "TODO: state the second observable behaviour required for this initiative.",
    "TODO: state the third observable behaviour required for this initiative.",
]


def _extract_existing_acs(body: str) -> list[str]:
    """Return numbered/bulleted AC items from an existing `## Acceptance
    criteria` block in the body, or [] if none."""
    m = _AC_HEADING_RE.search(body)
    if not m:
        return []
    rest = body[m.end():]
    next_heading = re.search(r"^\s*#{1,6}\s+\S", rest, re.MULTILINE)
    block = rest[: next_heading.start()] if next_heading else rest
    return [item.group(1).strip() for item in _LIST_ITEM_RE.finditer(block)]


def _strip_existing_sections(body: str) -> str:
    """Remove an H1 line and any leading `## Acceptance criteria` block so
    the body we splice into `## Context` doesn't duplicate sections we're
    about to render ourselves. Conservative — we keep prose intact."""
    out_lines: list[str] = []
    skip_until_heading = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            # Drop the H1; it's already the markdown title.
            continue
        if _AC_HEADING_RE.match(line):
            skip_until_heading = True
            continue
        if skip_until_heading:
            if re.match(r"^\s*#{1,6}\s+\S", line):
                skip_until_heading = False
            else:
                continue
        out_lines.append(line)
    return "\n".join(out_lines).strip()


def _format_numbered(items: Iterable[str]) -> str:
    return "\n".join(f"{i}. {item}" for i, item in enumerate(items, start=1))


def _format_oos(items: Any) -> list[str]:
    if not items:
        return []
    if isinstance(items, str):
        return [items]
    return [str(x) for x in items]


def _metadata_block(initiative: Initiative, extras: dict[str, Any]) -> str:
    """Render the blockquote metadata header (Source / Priority / OKR).
    Empty fields are skipped so the block stays tight."""
    lines = []
    source = initiative.source or extras.get("source")
    status = initiative.status or extras.get("status")
    if source:
        suffix = f", {status}" if status else ""
        lines.append(f"> Source: {initiative.id} ({source}{suffix})")

    tier = extras.get("tier")
    score = extras.get("score")
    method = extras.get("method")
    if tier or score is not None:
        bits = []
        if tier:
            bits.append(f"{tier}")
        if score is not None and method:
            bits.append(f"({method.upper()} score {score})")
        elif score is not None:
            bits.append(f"(score {score})")
        lines.append(f"> Priority: {' '.join(bits)}")

    okr = initiative.raw_metadata.get("okr")
    if okr:
        lines.append(f"> Linked OKR: {okr}")
    return "\n".join(lines)


def render_spec_draft(
    initiative: Initiative,
    template: str = "default",
    *,
    score_summary: dict[str, Any] | None = None,
) -> str:
    """Produce the markdown spec draft. `score_summary` is optional and
    carries {score, tier, method} from a prior score_initiative call so
    the metadata block can quote the priority line. When absent, the
    metadata defaults to "(unscored)" rather than fabricating a number."""
    if template not in TEMPLATES:
        raise ValueError(
            f"unknown template {template!r}; choose one of {list(TEMPLATES)}"
        )

    extras: dict[str, Any] = dict(score_summary or {})

    title = initiative.title or initiative.id
    body = _strip_existing_sections(initiative.body or "")
    context = body if body else "TODO: describe the problem this initiative solves."

    existing_acs = _extract_existing_acs(initiative.body or "")
    acs = existing_acs or _PLACEHOLDER_ACS

    parts: list[str] = [f"# {title}"]

    if template != "lite":
        meta_block = _metadata_block(initiative, extras)
        if meta_block:
            parts.append(meta_block)

    parts.append(f"## Context\n\n{context}")
    parts.append(f"## Acceptance criteria\n\n{_format_numbered(acs)}")

    if template != "lite":
        oos = _format_oos(initiative.raw_metadata.get("out_of_scope"))
        oos_block = _format_numbered(oos) if oos else "- (none specified)"
        parts.append(f"## Out of scope\n\n{oos_block}")

    if template == "detailed":
        risks = initiative.raw_metadata.get("risks")
        deps = initiative.raw_metadata.get("dependencies")
        effort = initiative.raw_metadata.get("effort")
        parts.append(
            "## Risks\n\n"
            + (f"- {risks}" if isinstance(risks, str) else _bullet_list(risks))
        )
        parts.append(
            "## Dependencies\n\n"
            + (f"- {deps}" if isinstance(deps, str) else _bullet_list(deps))
        )
        parts.append(
            "## Estimated effort\n\n"
            + (
                f"{effort} person-weeks"
                if effort is not None
                else "TODO: estimate effort in person-weeks."
            )
        )

    return "\n\n".join(parts).rstrip() + "\n"


def _bullet_list(items: Any) -> str:
    if not items:
        return "- (none specified)"
    if isinstance(items, str):
        return f"- {items}"
    return "\n".join(f"- {x}" for x in items)
