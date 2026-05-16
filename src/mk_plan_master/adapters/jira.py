"""Adapter for JIRA Cloud (and best-effort JIRA Server) via REST API v3.

Env:
    PLAN_SOURCE=jira
    JIRA_BASE_URL=https://yourorg.atlassian.net   (no trailing slash)
    JIRA_EMAIL=you@example.com                     Cloud uses Basic auth
                                                    with email + API token
    JIRA_API_TOKEN=...                             From id.atlassian.com →
                                                    Security → API tokens
    PLAN_PROJECT_KEY=PROJ                          Project key (omit to list
                                                    across all projects the
                                                    API user can see).

Filter intent: this adapter is the *upstream* sibling to mk-spec-master's
jira adapter — pulls issues NOT-YET-shipped (statusCategory in "To Do" /
"Backlog") so rank_backlog only sees triageable work.

Mapping:
    issue.fields.customfield_10016 (story points)  → raw_metadata["effort"]
    issue.fields.labels                            → labels
    issue.fields.description (ADF)                 → body (flattened markdown)
    <BASE>/browse/<KEY-N>                          → url

Zero new deps — stdlib urllib + base64.
"""

import base64
import json
import urllib.error
import urllib.parse
import urllib.request

from .. import config
from . import register
from .base import Initiative, InitiativeSource, InitiativeSummary


class JiraUnavailable(RuntimeError):
    """Raised when the JIRA API call fails or env vars are missing.
    Message is shown to the AI client; keep it actionable."""


_TIMEOUT_S = 20
_API_PATH = "/rest/api/3"

# JIRA exposes story points via a customfield slot. 10016 is the default for
# Atlassian Cloud / next-gen projects; users with classic projects may need to
# override. We surface whichever slot is non-null and numeric.
_STORY_POINTS_FIELDS = ("customfield_10016", "customfield_10004", "customfield_10026")

# Upstream-half intent: NOT-YET-shipped work. JIRA's statusCategory keys are
# stable across language / workflow customisation, unlike status names.
_PLAN_STATUS_CATEGORIES = ("To Do",)


def _check_auth() -> tuple[str, str, str]:
    if not config.JIRA_BASE_URL:
        raise ValueError(
            "jira adapter requires JIRA_BASE_URL (e.g. https://yourorg.atlassian.net)"
        )
    if not config.JIRA_EMAIL:
        raise ValueError(
            "jira adapter requires JIRA_EMAIL (your Atlassian account email)"
        )
    if not config.JIRA_API_TOKEN:
        raise ValueError(
            "jira adapter requires JIRA_API_TOKEN. Create one at "
            "https://id.atlassian.com/manage-profile/security/api-tokens"
        )
    return config.JIRA_BASE_URL.rstrip("/"), config.JIRA_EMAIL, config.JIRA_API_TOKEN


def _request(path: str, params: dict | None = None) -> dict:
    """GET <base_url>/rest/api/3<path>?<params>. Tests monkeypatch this
    function to avoid live API calls."""
    base, email, token = _check_auth()
    creds = base64.b64encode(f"{email}:{token}".encode("utf-8")).decode("ascii")

    url = f"{base}{_API_PATH}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Basic {creds}",
            "Accept": "application/json",
            "User-Agent": "mk-plan-master/jira-adapter",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise JiraUnavailable(
            f"JIRA API HTTP {exc.code}: {exc.reason}. "
            f"Check JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN, and project access."
        ) from exc
    except urllib.error.URLError as exc:
        raise JiraUnavailable(f"JIRA API unreachable: {exc.reason}") from exc


def adf_to_markdown(adf) -> str:
    """Flatten an ADF document tree (or None / str) to markdown text.
    Handles the node types we see in 99% of JIRA descriptions; unknown
    nodes fall through with inner text preserved so we never drop data."""
    if adf is None:
        return ""
    if isinstance(adf, str):
        return adf

    def render(node) -> str:
        if isinstance(node, list):
            return "".join(render(n) for n in node)
        if not isinstance(node, dict):
            return ""

        typ = node.get("type", "")
        content = node.get("content") or []

        if typ == "text":
            return node.get("text", "")
        if typ == "doc":
            return "".join(render(c) for c in content)
        if typ == "heading":
            level = (node.get("attrs") or {}).get("level", 1)
            return f"\n{'#' * int(level)} {''.join(render(c) for c in content)}\n"
        if typ == "paragraph":
            return f"\n{''.join(render(c) for c in content)}\n"
        if typ == "bulletList":
            items = ["- " + render(c).strip() for c in content]
            return "\n".join(items) + "\n"
        if typ == "orderedList":
            items = [f"{i + 1}. " + render(c).strip() for i, c in enumerate(content)]
            return "\n".join(items) + "\n"
        if typ == "listItem":
            return "".join(render(c) for c in content)
        if typ == "codeBlock":
            return f"\n```\n{''.join(render(c) for c in content)}\n```\n"
        if typ == "hardBreak":
            return "\n"
        return "".join(render(c) for c in content)

    return render(adf).strip()


def _quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _build_jql(project_key: str, status: str | None, label: str | None) -> str:
    parts: list[str] = []
    if project_key:
        parts.append(f"project = {_quote(project_key)}")
    if status:
        parts.append(f"status = {_quote(status)}")
    else:
        cat_list = ", ".join(_quote(c) for c in _PLAN_STATUS_CATEGORIES)
        parts.append(f"statusCategory in ({cat_list})")
    if label:
        parts.append(f"labels = {_quote(label)}")
    return " AND ".join(parts) + " ORDER BY updated DESC"


def _extract_story_points(fields: dict) -> float | None:
    for slot in _STORY_POINTS_FIELDS:
        value = fields.get(slot)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _browse_url(base: str, key: str) -> str:
    return f"{base.rstrip('/')}/browse/{key}" if key else ""


def _summary_from_issue(issue: dict, base_url: str) -> InitiativeSummary:
    fields = issue.get("fields") or {}
    labels = fields.get("labels") or []
    if not isinstance(labels, list):
        labels = []
    key = str(issue.get("key", ""))
    return InitiativeSummary(
        id=key,
        source="jira",
        title=str(fields.get("summary", "")),
        url=_browse_url(base_url, key),
        status=((fields.get("status") or {}).get("name", "")),
        labels=[str(l) for l in labels],
    )


def _initiative_from_issue(issue: dict, base_url: str, fallback_id: str = "") -> Initiative:
    fields = issue.get("fields") or {}
    body_md = adf_to_markdown(fields.get("description"))

    labels = fields.get("labels") or []
    if not isinstance(labels, list):
        labels = []

    raw_metadata: dict = {
        "jira_id": issue.get("id", ""),
        "created": fields.get("created", ""),
        "updated": fields.get("updated", ""),
        "issue_type": ((fields.get("issuetype") or {}).get("name", "")),
    }
    story_points = _extract_story_points(fields)
    if story_points is not None:
        raw_metadata["effort"] = story_points

    key = str(issue.get("key") or fallback_id)
    return Initiative(
        id=key,
        source="jira",
        title=str(fields.get("summary", "")),
        body=body_md,
        url=_browse_url(base_url, key),
        status=((fields.get("status") or {}).get("name", "")),
        labels=[str(l) for l in labels],
        raw_metadata=raw_metadata,
    )


@register("jira")
class JiraAdapter(InitiativeSource):
    name = "jira"

    def list_initiatives(
        self,
        status: str | None = None,
        label: str | None = None,
        limit: int = 50,
    ) -> list[InitiativeSummary]:
        base = (config.JIRA_BASE_URL or "").rstrip("/")
        jql = _build_jql(config.SOURCE_KEY, status, label)
        # Include the story-point custom fields so rank_backlog can read effort
        # without a separate fetch per issue.
        field_csv = ",".join(("summary", "status", "labels", *_STORY_POINTS_FIELDS))
        payload = _request(
            "/search",
            {"jql": jql, "fields": field_csv, "maxResults": min(limit, 100)},
        )
        issues = payload.get("issues") or []

        out: list[InitiativeSummary] = []
        for issue in issues:
            out.append(_summary_from_issue(issue, base))
            if len(out) >= limit:
                break
        return out

    def fetch(self, initiative_id: str) -> Initiative:
        base = (config.JIRA_BASE_URL or "").rstrip("/")
        field_csv = ",".join(
            ("summary", "description", "status", "labels", "created", "updated", "issuetype", *_STORY_POINTS_FIELDS)
        )
        payload = _request(
            f"/issue/{initiative_id}",
            {"fields": field_csv},
        )
        if not payload or "key" not in payload:
            raise ValueError(
                f"jira: issue {initiative_id!r} not found. Confirm the project "
                f"key prefix and API token access."
            )
        return _initiative_from_issue(payload, base, fallback_id=initiative_id)
