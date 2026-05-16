"""Adapter for Notion (notion.so) databases.

Env:
    PLAN_SOURCE=notion
    NOTION_TOKEN=secret_XXX            Internal-integration token. Create one
                                        at https://www.notion.so/my-integrations
                                        then share the planning database with
                                        the integration via the database's
                                        "..." menu → Add connections.
    PLAN_PROJECT_KEY=<database-id>     The Notion database ID containing
                                        initiatives (32-char UUID, hyphens
                                        optional).

Initiative id format: the Notion page UUID. We mirror mk-spec-master's
approach — custom "Key" / "ID" properties surface in raw_metadata so the AI
client can show users their human identifier, but lookups use the UUID.

Property names are user-defined; we match case-insensitively against the
common shapes ("status", "state", "tags", "labels", "okr", plus any custom
fields that match RICE-scoring lanes). Anything we don't recognise is
preserved verbatim in raw_metadata so power users can override scoring with
score_initiative's `overrides`.

Filter intent: upstream-half — only triageable / not-yet-shipped pages.
Matches status property values in {Triage, Backlog, Idea} (case-insensitive).

Zero new deps — stdlib urllib.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

from .. import config
from . import register
from .base import Initiative, InitiativeSource, InitiativeSummary


class NotionUnavailable(RuntimeError):
    """Raised when the Notion API call fails or env vars are missing.
    Message is shown to the AI client; keep it actionable."""


_API_BASE = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"
_TIMEOUT_S = 20

# Upstream-half intent — accept any of these as a "still triageable" signal.
_PLAN_STATUSES = {"triage", "backlog", "idea"}

# Common alternative property names users name their RICE scoring lanes.
_SCORING_KEYS = {"reach", "impact", "confidence", "effort", "okr"}


def _check_auth() -> str:
    if not config.NOTION_TOKEN:
        raise ValueError(
            "notion adapter requires NOTION_TOKEN. Create an internal "
            "integration at https://www.notion.so/my-integrations, then "
            "share the planning database with that integration."
        )
    return config.NOTION_TOKEN


def _database_id() -> str:
    if not config.SOURCE_KEY:
        raise ValueError(
            "notion adapter requires PLAN_PROJECT_KEY=<database-id>. "
            "Open the Notion database in the browser; the 32-char UUID "
            "in the URL is the database id."
        )
    return config.SOURCE_KEY


def _request(method: str, path: str, body: dict | None = None) -> dict:
    """Call the Notion REST API. Tests monkeypatch this to skip the network."""
    token = _check_auth()
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        f"{_API_BASE}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": _NOTION_VERSION,
            "Content-Type": "application/json",
            "User-Agent": "mk-plan-master/notion-adapter",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise NotionUnavailable(
            f"Notion API HTTP {exc.code}: {exc.reason}. "
            f"Check NOTION_TOKEN, database ID, and integration sharing."
        ) from exc
    except urllib.error.URLError as exc:
        raise NotionUnavailable(f"Notion API unreachable: {exc.reason}") from exc


def _rich_text(rt_list: list) -> str:
    """Join Notion rich_text items' plain_text into a single string."""
    if not isinstance(rt_list, list):
        return ""
    return "".join(item.get("plain_text", "") for item in rt_list if isinstance(item, dict))


def blocks_to_markdown(blocks: list) -> str:
    """Flatten Notion blocks to markdown. Same dialect as the mk-spec-master
    sibling — supports paragraph / heading_{1..3} / bulleted / numbered /
    to_do / code / quote and falls through with inner text for unknown types."""
    if not isinstance(blocks, list):
        return ""

    lines: list[str] = []
    numbered_streak = 0
    for block in blocks:
        if not isinstance(block, dict):
            continue
        typ = block.get("type", "")
        data = block.get(typ) or {}
        text = _rich_text(data.get("rich_text") or [])

        if typ != "numbered_list_item":
            numbered_streak = 0

        if typ == "heading_1":
            lines.append(f"# {text}")
        elif typ == "heading_2":
            lines.append(f"## {text}")
        elif typ == "heading_3":
            lines.append(f"### {text}")
        elif typ == "paragraph":
            lines.append(text)
        elif typ == "bulleted_list_item":
            lines.append(f"- {text}")
        elif typ == "numbered_list_item":
            numbered_streak += 1
            lines.append(f"{numbered_streak}. {text}")
        elif typ == "to_do":
            checked = bool(data.get("checked"))
            mark = "[x]" if checked else "[ ]"
            lines.append(f"- {mark} {text}")
        elif typ == "code":
            lang = data.get("language") or ""
            lines.append(f"```{lang}\n{text}\n```")
        elif typ == "quote":
            lines.append(f"> {text}")
        else:
            if text:
                lines.append(text)

    return "\n\n".join(line for line in lines if line is not None)


def _prop_value(prop: dict):
    """Best-effort scalar extraction from any property type we know."""
    if not isinstance(prop, dict):
        return None
    typ = prop.get("type")
    if typ == "title":
        return _rich_text(prop.get("title") or [])
    if typ == "rich_text":
        return _rich_text(prop.get("rich_text") or [])
    if typ == "number":
        return prop.get("number")
    if typ == "select":
        return ((prop.get("select") or {}).get("name") or "")
    if typ == "status":
        return ((prop.get("status") or {}).get("name") or "")
    if typ == "multi_select":
        return [opt.get("name", "") for opt in (prop.get("multi_select") or []) if isinstance(opt, dict)]
    if typ == "checkbox":
        return bool(prop.get("checkbox"))
    if typ == "url":
        return prop.get("url") or ""
    if typ == "email":
        return prop.get("email") or ""
    if typ == "unique_id":
        uid = prop.get("unique_id") or {}
        prefix = uid.get("prefix") or ""
        num = uid.get("number")
        if prefix and num is not None:
            return f"{prefix}-{num}"
        return str(num) if num is not None else ""
    return None


def _find_prop(page: dict, candidates: set[str]) -> tuple[str, dict] | None:
    """Locate a property whose name matches any candidate (case-insensitive).
    Returns (actual_name, prop_dict) or None."""
    props = page.get("properties") or {}
    for name, prop in props.items():
        if isinstance(prop, dict) and name.lower() in candidates:
            return name, prop
    return None


def _extract_title(page: dict) -> str:
    props = page.get("properties") or {}
    for _, prop in props.items():
        if isinstance(prop, dict) and prop.get("type") == "title":
            return _rich_text(prop.get("title") or [])
    return ""


def _extract_status(page: dict) -> str:
    hit = _find_prop(page, {"status", "state"})
    if not hit:
        return ""
    value = _prop_value(hit[1])
    return value if isinstance(value, str) else ""


def _extract_labels(page: dict) -> list[str]:
    hit = _find_prop(page, {"tags", "labels"})
    if not hit:
        return []
    value = _prop_value(hit[1])
    if isinstance(value, list):
        return [str(v) for v in value]
    return []


def _extract_custom_key(page: dict) -> str:
    """Surface user's human identifier — they're free to name the property
    Key / ID / Spec ID / Initiative ID."""
    hit = _find_prop(page, {"key", "id", "spec id", "spec_id", "initiative id", "initiative_id"})
    if not hit:
        return ""
    value = _prop_value(hit[1])
    return str(value) if value is not None else ""


def _extract_scoring(page: dict) -> dict:
    """Pull number / text properties that match RICE-style scoring lanes."""
    props = page.get("properties") or {}
    out: dict = {}
    for name, prop in props.items():
        if not isinstance(prop, dict):
            continue
        key = name.lower()
        if key not in _SCORING_KEYS:
            continue
        value = _prop_value(prop)
        if value is None or value == "":
            continue
        out[key] = value
    return out


def _summary_from_page(page: dict) -> InitiativeSummary:
    return InitiativeSummary(
        id=str(page.get("id", "")),
        source="notion",
        title=_extract_title(page),
        url=str(page.get("url") or ""),
        status=_extract_status(page),
        labels=_extract_labels(page),
    )


def _initiative_from_page(page: dict, body_md: str, fallback_id: str = "") -> Initiative:
    raw_metadata: dict = {
        "notion_id": str(page.get("id", "")),
        "custom_key": _extract_custom_key(page),
        "created_time": page.get("created_time", ""),
        "last_edited_time": page.get("last_edited_time", ""),
    }
    raw_metadata.update(_extract_scoring(page))

    return Initiative(
        id=str(page.get("id") or fallback_id),
        source="notion",
        title=_extract_title(page),
        body=body_md,
        url=str(page.get("url") or ""),
        status=_extract_status(page),
        labels=_extract_labels(page),
        raw_metadata=raw_metadata,
    )


@register("notion")
class NotionAdapter(InitiativeSource):
    name = "notion"

    def list_initiatives(
        self,
        status: str | None = None,
        label: str | None = None,
        limit: int = 50,
    ) -> list[InitiativeSummary]:
        db_id = _database_id()
        # We don't pass a server-side filter — Notion needs the property
        # name + type per database and users name them anything. Pull a
        # generous page, then filter client-side on status / label below.
        body: dict = {"page_size": min(max(limit * 4, 25), 100)}
        payload = _request("POST", f"/databases/{db_id}/query", body)
        results = payload.get("results") or []

        explicit_status = status.lower() if status else None

        out: list[InitiativeSummary] = []
        for page in results:
            if not isinstance(page, dict):
                continue
            summary = _summary_from_page(page)
            cur_status = (summary.status or "").lower()

            if explicit_status is not None:
                if cur_status != explicit_status:
                    continue
            else:
                # Upstream-half default: triage / backlog / idea.
                if cur_status and cur_status not in _PLAN_STATUSES:
                    continue

            if label and label not in summary.labels:
                continue
            out.append(summary)
            if len(out) >= limit:
                break
        return out

    def fetch(self, initiative_id: str) -> Initiative:
        page = _request("GET", f"/pages/{initiative_id}")
        if not page or page.get("object") != "page":
            raise ValueError(
                f"notion: page {initiative_id!r} not found or not shared with "
                f"the integration."
            )

        # Notion paginates blocks at 100 per page; for v0.1 a single batch is
        # plenty for initiative-sized pages (a real spec is usually well under
        # 100 blocks). Larger pages truncate; v0.2 can paginate.
        children = _request("GET", f"/blocks/{initiative_id}/children?page_size=100")
        blocks = children.get("results") or []
        body_md = blocks_to_markdown(blocks)
        return _initiative_from_page(page, body_md, fallback_id=initiative_id)
