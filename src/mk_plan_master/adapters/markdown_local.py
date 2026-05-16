"""Adapter for local Markdown initiative files. PLAN_PROJECT_ROOT/initiatives/*.md.

Frontmatter (YAML-ish) drives metadata:

    ---
    id: LIN-001
    title: Self-serve onboarding wizard
    status: triage
    labels: [growth, activation]
    reach: 1200
    impact: 2
    confidence: 0.8
    effort: 5
    okr: Q3-growth
    out_of_scope: [enterprise SSO]
    ---

    Customers drop off at signup because they have to email us for a demo...

Why hand-rolled instead of pyyaml: keeps the dep list to mcp>=1.0.0 only.
The frontmatter shape is constrained (scalars + inline lists), so a tiny
parser is enough. If users need nested dicts, we add pyyaml in a later phase.
"""

import re
from pathlib import Path

from ..config import INITIATIVES_DIR
from . import register
from .base import Initiative, InitiativeSource, InitiativeSummary

_FRONTMATTER_RE = re.compile(
    r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z",
    re.DOTALL,
)

_SCORING_KEYS = {"reach", "impact", "confidence", "effort"}
_RESERVED_KEYS = {"id", "title", "status", "labels"}


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Returns (metadata_dict, body). If no frontmatter, returns ({}, full_text)."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text

    meta_block, body = m.group(1), m.group(2)
    meta: dict = {}
    for raw_line in meta_block.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        meta[key] = _coerce(value)
    return meta, body


def _coerce(value: str):
    """Parse scalars + inline lists. Bool / null / int / float kept simple."""
    if value == "" or value.lower() == "null":
        return None
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip("\"'") for item in inner.split(",")]
    # int
    if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
        return int(value)
    # float (RICE confidence is often 0.8 / 0.5)
    try:
        if "." in value:
            return float(value)
    except ValueError:
        pass
    return value.strip("\"'")


def _initiative_files() -> list[Path]:
    if not INITIATIVES_DIR.exists():
        return []
    return sorted(INITIATIVES_DIR.glob("*.md"))


def _initiative_id_from(meta: dict, fallback_path: Path) -> str:
    """Prefer explicit `id` in frontmatter; else derive from filename stem."""
    return str(meta.get("id") or fallback_path.stem)


@register("markdown_local")
class MarkdownLocalAdapter(InitiativeSource):
    name = "markdown_local"

    def list_initiatives(
        self,
        status: str | None = None,
        label: str | None = None,
        limit: int = 50,
    ) -> list[InitiativeSummary]:
        out: list[InitiativeSummary] = []
        for path in _initiative_files():
            try:
                meta, _ = _parse_frontmatter(path.read_text(encoding="utf-8"))
            except OSError:
                continue

            initiative_id = _initiative_id_from(meta, path)
            title = str(meta.get("title") or initiative_id)
            cur_status = str(meta.get("status") or "")
            labels = meta.get("labels") or []
            if isinstance(labels, str):
                labels = [labels]

            if status and cur_status != status:
                continue
            if label and label not in labels:
                continue

            out.append(
                InitiativeSummary(
                    id=initiative_id,
                    source=self.name,
                    title=title,
                    url=str(path),
                    status=cur_status,
                    labels=list(labels),
                )
            )
            if len(out) >= limit:
                break
        return out

    def fetch(self, initiative_id: str) -> Initiative:
        for path in _initiative_files():
            meta, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
            if _initiative_id_from(meta, path) != initiative_id:
                continue

            labels = meta.get("labels") or []
            if isinstance(labels, str):
                labels = [labels]

            raw_metadata = {
                k: v for k, v in meta.items() if k not in _RESERVED_KEYS
            }

            return Initiative(
                id=initiative_id,
                source=self.name,
                title=str(meta.get("title") or initiative_id),
                body=body.strip(),
                url=str(path),
                status=str(meta.get("status") or ""),
                labels=list(labels),
                raw_metadata=raw_metadata,
            )

        raise ValueError(
            f"initiative_id={initiative_id!r} not found under {INITIATIVES_DIR}"
        )
