"""Adapter for Linear (linear.app) — upstream/triage half of the pipeline.

Env:
    PLAN_SOURCE=linear
    LINEAR_API_KEY=lin_api_XXX        Personal API key — Settings -> API
    PLAN_PROJECT_KEY=ENG              Team key (optional). If unset, lists
                                       across every team the API key can see.

Auth: Linear personal API keys go in the Authorization header verbatim
— no `Bearer` prefix. (OAuth tokens do use `Bearer`; personal keys are
simpler for solo / small-team installs and this adapter targets that path.)

Initiative id format: Linear's human identifier ("ENG-123") is used as the
initiative_id. The internal UUID is kept in raw_metadata.linear_id for
debugging but isn't exposed elsewhere.

Filter intent: this adapter is the *upstream* sibling to mk-spec-master's
linear adapter. mk-spec-master pulls issues already in flight (In Progress);
mk-plan-master pulls ideas not-yet-shipped — Linear state types `triage`,
`backlog`, `unstarted`. The state filter is applied at the GraphQL layer so
the result set stays bounded even on large workspaces.

Networking: stdlib urllib only — keeps the package dep list to mcp>=1.0.0.
GraphQL POSTs are small JSON; 20s timeout matches the spec-master adapter.
"""

import json
import urllib.error
import urllib.request

from .. import config
from . import register
from .base import Initiative, InitiativeSource, InitiativeSummary


class LinearUnavailable(RuntimeError):
    """Raised when the Linear API call fails. Message is propagated to
    the AI client; keep it actionable."""


_API_URL = "https://api.linear.app/graphql"
_TIMEOUT_S = 20

# Linear state *types* (vs state *names*) — language-stable and consistent
# across workspaces. Maps to "not yet shipped, eligible for triage/ranking".
_PLAN_STATE_TYPES = ["triage", "backlog", "unstarted"]


def _check_auth() -> str:
    api_key = config.LINEAR_API_KEY
    if not api_key:
        raise ValueError(
            "LINEAR_API_KEY env var is required for the linear adapter. "
            "Generate a personal API key at https://linear.app/settings/api "
            "and set it as an env var on this MCP server."
        )
    return api_key


def _gql(query: str, variables: dict | None = None) -> dict:
    """POST a GraphQL query and return the `data` dict. Tests monkeypatch
    this function to skip the network."""
    api_key = _check_auth()
    payload = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    req = urllib.request.Request(
        _API_URL,
        data=payload,
        headers={
            "Authorization": api_key,
            "Content-Type": "application/json",
            "User-Agent": "mk-plan-master/linear-adapter",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
            response = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise LinearUnavailable(
            f"Linear API HTTP {exc.code}: {exc.reason}. "
            f"Check LINEAR_API_KEY and team access."
        ) from exc
    except urllib.error.URLError as exc:
        raise LinearUnavailable(f"Linear API unreachable: {exc.reason}") from exc

    if response.get("errors"):
        msg = "; ".join(e.get("message", "?") for e in response["errors"])
        raise LinearUnavailable(f"Linear API errors: {msg}")
    return response.get("data") or {}


_LIST_QUERY = """
query Issues($filter: IssueFilter, $first: Int!) {
  issues(filter: $filter, first: $first) {
    nodes {
      id
      identifier
      title
      estimate
      state { name type }
      labels { nodes { name } }
      url
    }
  }
}
"""

_FETCH_QUERY = """
query IssueByIdentifier($id: String!) {
  issueByIdentifier(id: $id) {
    id
    identifier
    title
    description
    estimate
    state { name type }
    labels { nodes { name } }
    url
    createdAt
    updatedAt
  }
}
"""


def _labels_from(node: dict) -> list[str]:
    return [
        lbl.get("name", "")
        for lbl in (node.get("labels") or {}).get("nodes", []) or []
        if isinstance(lbl, dict)
    ]


def _summary_from_node(node: dict) -> InitiativeSummary:
    return InitiativeSummary(
        id=node.get("identifier", ""),
        source="linear",
        title=node.get("title", ""),
        url=node.get("url", ""),
        status=(node.get("state") or {}).get("name", ""),
        labels=_labels_from(node),
    )


def _initiative_from_node(node: dict, fallback_id: str = "") -> Initiative:
    raw_metadata: dict = {
        "linear_id": node.get("id", ""),
        "created_at": node.get("createdAt", ""),
        "updated_at": node.get("updatedAt", ""),
        "state_type": (node.get("state") or {}).get("type", ""),
    }
    # Linear estimate (story points) is the most useful numeric signal we get
    # for free. Map to RICE's effort lane so score_initiative can consume it
    # without the AI client having to ask the user for a number.
    estimate = node.get("estimate")
    if estimate is not None:
        raw_metadata["effort"] = estimate

    return Initiative(
        id=node.get("identifier") or fallback_id,
        source="linear",
        title=node.get("title", ""),
        body=node.get("description") or "",
        url=node.get("url", ""),
        status=(node.get("state") or {}).get("name", ""),
        labels=_labels_from(node),
        raw_metadata=raw_metadata,
    )


@register("linear")
class LinearAdapter(InitiativeSource):
    name = "linear"

    def list_initiatives(
        self,
        status: str | None = None,
        label: str | None = None,
        limit: int = 50,
    ) -> list[InitiativeSummary]:
        gql_filter: dict = {}
        team_key = config.SOURCE_KEY
        if team_key:
            gql_filter["team"] = {"key": {"eq": team_key}}

        # If the caller passes a specific status name, honour it. Otherwise
        # filter to the "not yet shipped" state types so rank_backlog sees
        # only triageable work.
        if status:
            gql_filter["state"] = {"name": {"eq": status}}
        else:
            gql_filter["state"] = {"type": {"in": _PLAN_STATE_TYPES}}

        if label:
            gql_filter["labels"] = {"name": {"eq": label}}

        # `first` caps at 250 on Linear's side; we mirror that.
        data = _gql(_LIST_QUERY, {"filter": gql_filter, "first": min(limit, 250)})
        nodes = (data.get("issues") or {}).get("nodes") or []

        out: list[InitiativeSummary] = []
        for n in nodes:
            out.append(_summary_from_node(n))
            if len(out) >= limit:
                break
        return out

    def fetch(self, initiative_id: str) -> Initiative:
        data = _gql(_FETCH_QUERY, {"id": initiative_id})
        issue = data.get("issueByIdentifier")
        if not issue:
            raise ValueError(
                f"linear: issue {initiative_id!r} not found. Confirm the team "
                f"prefix matches PLAN_PROJECT_KEY and the API key has access."
            )
        return _initiative_from_node(issue, fallback_id=initiative_id)
