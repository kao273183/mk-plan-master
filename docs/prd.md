# mk-plan-master — PRD

**Status:** Draft v0.1 · **Author:** Jack Kao (kao273183) · **Last updated:** 2026-05-16

---

## 1. Vision

> **Ideas in, prioritized plans out — with auto-generated spec drafts that hand straight to mk-spec-master.**

The MCP that closes the **upstream** gap in the AI dev pipeline. Reads product
ideas from Linear / JIRA / Notion / Productboard / Intercom / Markdown; ranks
them with RICE / WSJF / Impact-Effort; produces a quarterly roadmap;
generates spec drafts ready for `mk-spec-master.parse_spec`.

Chinese brand: **AI 規劃大師** (third member of 「AI 大師」 series after
mk-qa-master + mk-spec-master).

---

## 2. Problem Statement

The AI-driven dev pipeline currently looks like:

```
                        ⬇
???  →  Spec  →  Test  →  Coverage  →  Coach
(gap)    mk-spec  mk-qa   mk-spec      both
```

Nobody is doing the **upstream** half. PMs / founders / tech leads have:

1. **A pile of 30–200 ideas** from customers, sales calls, Twitter, internal hunches
2. **No structured way to triage** — Productboard / Aha! exist but live in their own walled garden, not in the AI session where the rest of the work happens
3. **No bridge to spec** — picking "we'll build X next sprint" doesn't automatically produce a spec draft; that's still a separate manual step
4. **No memory of decisions** — why did we deprioritize feature Y last quarter? Nobody remembers; the same idea bounces back next planning cycle

AI is meant to compress all four of these. Today it doesn't because there's no
MCP-native tool that puts product planning into the AI session.

**Hypothesis:** the same SDD wave that justified mk-spec-master justifies
mk-plan-master, one step upstream. AI clients want to do planning + spec +
test in one flow; they need a tool surface for the planning third.

---

## 3. Why now

- **Idea-to-Production AI pipeline** narrative is becoming the new dev-tools
  vocabulary (Anthropic, AWS Kiro, GitHub Spec Kit). The upstream "idea
  triage + roadmap" piece is the part of that narrative without a tool yet.
- **mk-spec-master + mk-qa-master** already close the spec→test→coverage→coach
  half; mk-plan-master finishes the loop and makes the family story coherent.
- **AI code velocity** compresses the cost of shipping a third MCP from 2
  months to ~2 weeks (validated by mk-spec-master's actual build time).
  Window to ship before competitors realize the upstream gap is shrinking.

---

## 4. Competitive Positioning

| Tool | Lock-in | What we do differently |
|---|---|---|
| **Productboard** | Full PM platform, $20-50/user/mo, walled garden | MCP-native: lives where the AI lives, not in its own UI. Multi-source (read your existing Linear/JIRA, don't import to a new tool) |
| **Aha!** | Enterprise roadmap, $59-149/user/mo | Open source baseline; SMB / indie friendly |
| **Linear / JIRA** | Backlog management, no triage / no prioritization framework / no plan→spec bridge | We add the missing scoring + roadmap + spec-bridge layers |
| **Cursor / Claude Code "ask AI to plan"** | Free-form chat, no persistence | Structured outputs, JSON index, traceable decisions |
| **AWS Kiro plan phase** | AWS IDE only, proprietary | MCP-native, multi-client |
| **GitHub Spec Kit** | Spec-first, doesn't reach upstream into idea triage | We're the missing pre-spec layer; complementary |
| **Notion / Confluence "product wiki"** | Storage only, no analysis | We *read* these and add the analysis layer |

**Defensible position:**

> The only **MCP-native, open-source, multi-source** product-planning MCP that
> **bridges directly to spec** (mk-spec-master) + **self-reinforces over time**
> (decision history, idea→ship rate).

Five differentiators no competitor combines:
1. MCP-native (not a SaaS UI)
2. Multi-source adapter pattern (8+ planned)
3. Bridges to mk-spec-master.parse_spec automatically (the family lock-in)
4. Self-reinforcement: tracks decision history, idea→ship conversion rate
5. Open source baseline; user owns the data

---

## 5. Target Users

**Primary:** Solo founders + product-minded engineers + small teams (1–10
people) running their planning out of Linear / Notion / "a markdown file
of ideas". They feel the gap because they're the ones doing both PM AND
engineering AND don't want to context-switch to Productboard.

**Secondary:** Mid-size product teams (1–3 PMs + 10–30 engineers) who want
planning to live in the AI flow alongside spec + test work.

**Tertiary:** Engineering managers running quarterly planning who want
data-backed prioritization (not vibes).

**Anti-personas:**
- Pure enterprise PMs already deep in Productboard / Aha! — they're not
  switching, and that's fine. mk-plan-master is for the "before they bought
  Productboard" segment.
- Pure no-code shops — they don't think in specs / tickets.

---

## 6. MVP Scope (v0.1) — Tier B

> **Decision 2026-05-16:** scope expanded from original 2-adapter / 6-tool draft
> to **4 adapters + 13 tools with self-reinforcement built in from Day 1**.
> Rationale: mk-spec-master already validated the self-reinforcement pattern;
> shipping it in v0.1 makes "the only planning MCP that measures its own
> decision quality" a Day-1 differentiator instead of waiting for v0.4.
>
> **Implementation status (2026-05-16):** Phase 1 (markdown_local + base
> tools), Phase 2 (Linear adapter + scoring + ranking + spec-draft bridge),
> Phase 3 (JIRA + Notion adapters + plan-knowledge + roadmap +
> self-reinforcement), `add_initiative` (chat / WebFetch capture handoff),
> and `analyze_initiative` (senior-PM analysis SOP meta-tool) are all
> complete. 4 adapters and **15 tools** registered; 77 tests passing.
> Remaining for v0.1 ship: Dockerfile / smithery.yaml + README polish +
> PyPI publish workflow.

**In scope:**
- **4 adapters**: `markdown_local` + `linear` + `jira` + `notion` (HTTP layer
  copied from mk-spec-master; only the GraphQL/REST query changes — filter to
  triage / backlog states instead of spec states)
- **13 core tools** (see §8 — flagged "MVP")
  - 6 base: get_plan_source_info / list_initiatives / fetch_initiative /
    score_initiative / rank_backlog / generate_spec_draft
  - 4 methodology + roadmap: generate_roadmap / init_plan_knowledge /
    get_plan_context / analyze_roadmap_balance
  - 3 self-reinforcement: get_planning_history / get_decision_signature /
    get_telemetry
- File-based decision index at `PLAN_PROJECT_ROOT/.mk-plan-master/index.json`
- History snapshots at `.mk-plan-master/history/*.json` (auto-archived on
  every `rank_backlog` call)
- Telemetry at `.mk-plan-master/telemetry.jsonl` (append-only, name +
  duration + ok only — no payload)
- Manual `score_initiative` (RICE arithmetic, AI fills in the inputs)
- `generate_spec_draft` — the family-bridge tool — produces markdown that
  `mk-spec-master.parse_spec` can ingest verbatim
- PyPI publish via Trusted Publishing (mirror mk-spec-master's `publish.yml`)
- CI matrix Python 3.10–3.13 from Day 1 (mirror mk-spec-master's `ci.yml`)
- README + README.zh-TW + this PRD + sample initiatives example

**Explicitly out of scope (deferred):**
- Productboard / Intercom / Zendesk adapters → v0.2 / v0.3
- `cluster_feedback` (clustering customer support tickets) → v0.2
- `compare_competitors` (fetching competitor changelogs) → v0.3
- `link_initiative_to_okr` (explicit OKR mapping tool) → v0.3
- WSJF method (RICE + impact-effort only in v0.1) → v0.2
- Web UI / dashboard → not planned (MCP + CLI only)

**MVP timeline target:** ship to PyPI within **~7 working days** of starting
(adapter HTTP reuse from mk-spec-master + self-reinforcement pattern reuse
keeps incremental cost low).

---

## 7. System Architecture

```
mk-plan-master/
├── pyproject.toml              # name: mk-plan-master, module: mk_plan_master
├── README.md
├── README.zh-TW.md
├── LICENSE / LICENSE.zh-TW.md
├── smithery.yaml               # stdio config
├── Dockerfile                  # Glama introspection
├── .github/
│   └── workflows/
│       ├── publish.yml         # mirror mk-spec-master's
│       └── ci.yml              # pytest matrix from day 1
├── docs/
│   ├── prd.md                  # this file
│   └── walkthrough.md          # end-to-end example
├── src/mk_plan_master/
│   ├── __init__.py
│   ├── server.py               # MCP entry, tool routing, telemetry wrap
│   ├── config.py               # env vars, paths
│   ├── adapters/
│   │   ├── base.py             # InitiativeSource ABC
│   │   ├── markdown_local.py   # MVP
│   │   └── linear.py           # MVP (copy from mk-spec-master)
│   ├── scoring/
│   │   ├── rice.py             # Reach × Impact × Confidence / Effort
│   │   ├── wsjf.py             # Weighted Shortest Job First (v0.2)
│   │   └── impact_effort.py    # 2x2 matrix
│   ├── index/
│   │   └── decisions.py        # JSON index (mirrors traceability.py)
│   ├── bridge/
│   │   └── spec_draft.py       # generate_spec_draft markdown formatter
│   └── tools/
│       ├── initiatives.py      # list / fetch / cluster
│       ├── scoring.py          # score / rank / compare
│       ├── roadmap.py          # generate_roadmap / analyze_balance
│       ├── bridge.py           # generate_spec_draft
│       └── meta.py             # get_plan_source_info
└── tests/
```

**Key env vars:**
- `PLAN_SOURCE=markdown_local | linear | jira | notion | productboard | intercom`
- `PLAN_PROJECT_ROOT=/path/to/project`
- `PLAN_PROJECT_KEY=<team-id>` (Linear), `<board-id>` (JIRA), etc.
- `LINEAR_API_KEY` / `JIRA_*` / `NOTION_TOKEN` / `PRODUCTBOARD_TOKEN` / `INTERCOM_TOKEN` — per adapter
- `PLAN_KNOWLEDGE_FILE` — optional override for plan-knowledge.md

---

## 8. Tool Surface

Target: ~18 tools at v0.3 maturity. **MVP ships with 15** (Tier B + add_initiative + analyze_initiative).

| Tool | MVP? | Purpose |
|---|---|---|
| `get_plan_source_info` | ✅ | Active adapter + all available; mirrors mk-spec-master's get_spec_source_info |
| `list_initiatives` | ✅ | List ideas (filter by status / label / priority) |
| `fetch_initiative` | ✅ | Pull one initiative's full content by id |
| `add_initiative` | ✅ | Write a new markdown_local initiative from AI-summarized chat / WebFetch content. The family does NOT crawl URLs; AI client summarizes, this persists. |
| `analyze_initiative` | ✅ | Force a senior-PM analysis SOP — returns target-users / competition / risks / MVP / RICE-rationale checklist the AI must fill before scoring. Loads plan-knowledge.md context. Frameworks: default / lite / lean_canvas. |
| `score_initiative` | ✅ | RICE / Impact-Effort scoring on one initiative; returns numeric + ranked tier |
| `rank_backlog` | ✅ | Score + sort the whole backlog; returns ordered list with rationale. **Auto-archives snapshot** to `history/` on every call. |
| **`generate_spec_draft`** | ✅ | **Key family-bridge tool.** Take top-scored initiative → produce markdown spec draft consumable by `mk-spec-master.parse_spec` |
| `generate_roadmap` | ✅ | Given capacity (engineer-months) + OKR, produce quarterly markdown roadmap |
| `analyze_roadmap_balance` | ✅ | Feature vs tech-debt vs strategic-bet ratio analysis on current top-N |
| `init_plan_knowledge` | ✅ | Bootstrap a `plan-knowledge.md` file with RICE / WSJF / OKR / INVEST methodology + project-specific glossary |
| `get_plan_context` | ✅ | Read `plan-knowledge.md` → return structured methodology context for AI to consume |
| `get_planning_history` | ✅ | Snapshot trends 7d / 30d — are we shipping what we plan? (mirrors mk-spec-master's get_spec_history) |
| `get_decision_signature` | ✅ | Chronic patterns: ghost initiatives, score whiplash, orphan OKRs |
| `get_telemetry` | ✅ | Tool usage log (privacy-safe: name + duration + ok only). Same JSONL wrap as mk-spec-master. |
| `cluster_feedback` | v0.2 | Group customer feedback (Intercom / Zendesk / raw text) into themes |
| `compare_competitors` | v0.3 | Fetch competitor changelog / blog → cross-reference with our roadmap |
| `link_initiative_to_okr` | v0.3 | Tag initiatives with org OKR mapping |

**Tool signatures (MVP only):**

```python
get_plan_source_info() -> { active: str, available: list[str], version: str }

list_initiatives(
    status: str | None = None,        # adapter-specific
    label: str | None = None,
    limit: int = 50
) -> list[InitiativeSummary]

fetch_initiative(id: str) -> Initiative

score_initiative(
    initiative_id: str | None = None,  # use fetched
    raw_text: str | None = None,        # ad-hoc
    method: str = "rice"                # rice / impact_effort / wsjf
) -> { score: float, breakdown: dict, tier: str }

rank_backlog(
    method: str = "rice",
    limit: int = 50,
    filters: dict = {}
) -> list[{ initiative_id: str, title: str, score: float, tier: str, rationale: str }]

generate_spec_draft(
    initiative_id: str,
    template: str = "default"           # default / lite / detailed
) -> { markdown: str, suggested_filename: str, ready_for_mk_spec_master: bool }
```

---

## 9. Data Model

**Decision index** stored at `PLAN_PROJECT_ROOT/.mk-plan-master/index.json`:

```json
{
  "version": 1,
  "initiatives": {
    "LIN-456": {
      "source": "linear",
      "title": "Bulk-edit user roles",
      "url": "https://linear.app/...",
      "last_scored": "2026-05-16T...",
      "last_score": 18.4,
      "method": "rice",
      "tier": "P1",
      "decisions": [
        {
          "ts": "2026-05-16T...",
          "action": "scored",
          "details": {"reach": 200, "impact": 1.5, "confidence": 0.7, "effort": 13}
        },
        {
          "ts": "2026-05-17T...",
          "action": "spec_generated",
          "details": {"path": "specs/LIN-456.md"}
        }
      ]
    }
  },
  "rejected": [],
  "shipped": []
}
```

**Why this shape:**
- `decisions[]` audit trail — answers "why did we deprioritize this last
  quarter" automatically
- `tier` (P0/P1/P2/P3) for human-readable roadmap categories
- `shipped` archive — measure idea→ship conversion rate over time (v0.4
  self-reinforcement signal)

---

## 10. Adapter Design

Mirrors mk-spec-master's `adapters/` abstraction.

```python
# src/mk_plan_master/adapters/base.py

class InitiativeSource(ABC):
    @abstractmethod
    def list_initiatives(self, **filters) -> list[InitiativeSummary]: ...

    @abstractmethod
    def fetch(self, initiative_id: str) -> Initiative: ...

    @property
    @abstractmethod
    def name(self) -> str: ...
```

**MVP adapters:**

| Adapter | `PLAN_SOURCE` | Auth | Notes |
|---|---|---|---|
| `markdown_local` | `markdown_local` | None | `ideas/*.md` with frontmatter (reach / impact / confidence / effort / OKR) |
| `linear` | `linear` | `LINEAR_API_KEY`, `PLAN_PROJECT_KEY=<team-key>` | Filter to state=Triage / Backlog (vs spec adapter which filters to In Progress) |

**v0.2 adapters:**
- `jira` (`JIRA_*` env vars, `PLAN_PROJECT_KEY=<board-id>`)
- `notion` (`NOTION_TOKEN`, `PLAN_PROJECT_KEY=<database-id>`)

**v0.3 adapters:**
- `productboard` (`PRODUCTBOARD_TOKEN`)
- `intercom` (`INTERCOM_TOKEN`) — feedback / conversation insights
- `zendesk` (`ZENDESK_*`)
- `csv_local` — for orgs with ad-hoc tracking

**Adapter code reuse:** the Linear, JIRA, Notion adapters' HTTP layers can
literally copy from mk-spec-master (same APIs, different query). Reduces
mk-plan-master adapter dev cost by ~50%.

---

## 11. Integration with mk-spec-master + mk-qa-master

**No MCP-to-MCP RPC** (same as the existing family). The AI client orchestrates
the chain.

**Important: the family does not write your app code.** Between spec and
green-light tests, the IDE (Claude Code / Cursor / Copilot) writes the actual
implementation. The MCP family wraps the *rails* — planning, spec, test,
coverage, coach — and deliberately leaves the code-writing layer to whatever
your AI-pair-programming tool already does well. Think TDD: tests are the
executable form of the spec, and code-writing is the loop that flips them red
→ green.

Canonical chain in a Claude / Cursor session (TDD framing):

```
1.  mk-plan-master.list_initiatives(status="triage")          → 50 ideas
2.  mk-plan-master.rank_backlog(method="rice", limit=10)      → top 10
3.  user picks LIN-456 → mk-plan-master.fetch_initiative("LIN-456")
4.  mk-plan-master.score_initiative("LIN-456")                → score 18.4, P1
5.  mk-plan-master.generate_spec_draft("LIN-456")             → markdown
    ↓ (AI client carries the markdown across the boundary)
6.  mk-spec-master.parse_spec(raw_text=<markdown>)            → AC list
7.  mk-spec-master.extract_scenarios(...)                     → scenarios
8.  mk-qa-master.generate_test(business_context=...)          → 4 tests (red)
                                                                 ↑ no impl yet
─── boundary: family hands off to your IDE ────────────────────────────────
9.  Your IDE (Claude Code / Cursor) writes app code           → impl emerges
    AI iterates: read failing test → write code → re-run → repeat
─── boundary: family takes over again ─────────────────────────────────────
10. mk-qa-master.run_tests                                    → tests green
11. mk-spec-master.link_test_to_spec(...)                     → trace
12. mk-spec-master.get_coverage_matrix                        → "4/4 AC ✓"
```

The TDD framing makes the "I have a spec but no code yet" gap into a
*feature*: the generated tests are a runnable TODO list. The AI codes against
red tests until they go green — at which point coverage automatically
reflects what's actually verified.

**Key bridge tool: `generate_spec_draft`**

The output format is *deliberately matched* to mk-spec-master's parse_spec
expected shape:

```markdown
# Bulk-edit user roles

> Source: LIN-456 (Linear, triage)
> Priority: P1 (RICE score 18.4)
> Linked OKR: Reduce admin overhead by 30%

## Context
[from initiative body]

## Acceptance criteria
1. Admin can select N users from the list and assign a single role
2. Role change is reflected in the next session login
3. ...

## Out of scope
[from initiative body if present]
```

This drops directly into `mk-spec-master.parse_spec(raw_text=...)`, no
manual editing required. The family becomes literally **one fluid chain**.

---

## 12. Self-reinforcement (MVP, mirrors mk-spec-master v0.4)

**Built into v0.1 (Tier B decision).** Three tools + two storage layers:

**`get_planning_history`** — snapshots archived per `rank_backlog` call.
Tracks:
- Top 10 priorities over time (week / month deltas)
- Idea→ship conversion rate (% of P0 initiatives that became shipped specs)
- Score stability (do RICE scores swing wildly or converge?)

**`get_decision_signature`** — chronic patterns:
- **"Ghost initiatives"**: appear in top 10 every cycle, never get spec_draft'd
- **"Score whiplash"**: RICE swings >50% between cycles → bad data quality
- **"Orphan OKRs"**: OKRs with zero linked initiatives → strategy/execution gap

**Tool-usage telemetry** — same JSONL wrap as mk-spec-master.

This makes mk-plan-master the **only** product-planning tool that measures
its own decision quality over time. Differentiator vs Productboard / Aha!.

---

## 13. Non-functional Requirements

| Concern | Requirement |
|---|---|
| **Privacy** | Initiative content stays local. No telemetry by default. All LLM calls go through the AI client (Claude/etc), not directly. `--local-only` disables any future external calls. |
| **Performance** | `list_initiatives` < 2s for 500 items cached. `rank_backlog` < 1s for 100 items (pure arithmetic). Network adapters bounded by 20s timeout. |
| **Storage** | Decision index JSON < 10MB for projects with <10k initiatives. |
| **Auth** | Adapter-specific. Tokens read from env vars only. Never logged. |
| **Errors** | All adapter failures return structured `{error, retryable, hint}` (mirror mk-spec-master). |
| **Compatibility** | Python 3.10+, MCP SDK >=1.0.0, mirror mk-spec-master's stack. Zero new runtime deps beyond `mcp`. |

---

## 14. Roadmap

| Milestone | Scope | Target |
|---|---|---|
| **v0.1 (MVP, Tier B)** | 4 adapters (markdown_local / linear / jira / notion), 13 tools (incl. self-reinforcement built-in), RICE + Impact-Effort scoring, generate_spec_draft bridge, plan-knowledge layer | ~7 working days |
| **v0.2** | + Productboard adapter, cluster_feedback, WSJF method, compare_competitors prep | +1 week |
| **v0.3** | + Intercom / Zendesk adapters, compare_competitors, link_initiative_to_okr | +2 weeks |
| **v1.0** | Production-ready: comprehensive docs, walkthrough videos, integration recipes for Claude/Cursor/Codex/Gemini, blog series complete | End of Q3 2026 |

**Realistic calendar** (assuming ~30 hrs/week side-project pace):
- v0.1 ship: ~2026-05-26 (target)
- v0.3 ship: ~2026-07-10
- v1.0: 2026-09-30

---

## 15. Open Questions / Risks

| # | Question | Mitigation |
|---|---|---|
| Q1 | RICE inputs (reach / impact / confidence / effort) — should the AI fill them in from initiative text, or require user to enter? | v0.1: AI fills in with explicit "estimated" flag; user overrides. Confidence drops if AI-only. |
| Q2 | What's a "P0 vs P1 vs P2" threshold for RICE? | v0.1: hard-coded (P0 >25, P1 10–25, P2 3–10, P3 <3). v0.2 expose as config. |
| Q3 | If `generate_spec_draft` is the bridge tool, should mk-spec-master have a corresponding `import_from_plan` tool that closes the loop officially? | Probably yes — small PR upstream in v0.2. |
| R1 | Productboard / Aha! release their own MCP first | Their MCP would be product-specific; ours is multi-source — orthogonal. Position as complementary. |
| R2 | LLM-driven RICE scoring produces garbage on poorly-described initiatives | First adapter is `markdown_local` (controlled corpus) → tune prompts → then noisy sources. |
| R3 | OKR linking is org-specific and hard to abstract | Make it explicit user-input ("paste your OKR doc"), don't try to auto-fetch from org systems in v0.x. |
| R4 | Solo dev maintaining 3 MCPs is a lot | Adapter code reuse cuts mk-plan-master dev to ~50% of mk-spec-master's effort. Same shape, same patterns. |

---

## 16. Success Metrics

**Adoption (3 months from v0.1):**
- 100 GitHub stars on the repo
- 1,000 PyPI downloads / month
- 5 unsolicited Issues / PRs from external users
- Mentioned in 1 PM / dev-tools blog post

**Quality (any time):**
- 60%+ of users surveyed report `rank_backlog` is "useful weekly"
- 0 critical bugs (data loss, index corruption) reported
- Glama quality grade ≥ B from day 1 (mirror mk-spec-master setup)

**Family effect (6 months):**
- 25%+ of mk-spec-master users also install mk-plan-master
- The "Idea-to-Production AI Pipeline" narrative gets traction in dev-tools
  discourse (proxy: shows up in 3+ external blog posts as a category)

---

## 17. Open Source Strategy

- License: MIT (mirror mk-spec-master + mk-qa-master)
- Repo: `github.com/kao273183/mk-plan-master`
- Branch protection on main, signed releases
- Trusted Publishing to PyPI (same setup as mk-spec-master)
- CI from day 1 (pytest matrix 3.10–3.13, mirror mk-spec-master's ci.yml)
- Smithery + Glama listed within 2 weeks of v0.1
- awesome-mcp-servers PR submitted on v0.1 release day
- Single blog post (positioning piece) on launch day: "The product-planning
  half of AI dev pipelines"
- Show HN within 1 week of stable v0.1

---

## 18. Naming

| Surface | Value |
|---|---|
| PyPI / npm | `mk-plan-master` |
| Python module | `mk_plan_master` |
| CLI command | `mk-plan-master` |
| MCP Server() id | `mk-plan-master` |
| Display name (EN) | MK Plan Master |
| Display name (中) | AI 規劃大師 |
| Tagline | Ideas in, prioritized plans out. Spec drafts ready for mk-spec-master. |
| Family slot | `mk-*` series (after `mk-spec-master`, before `mk-perf-master` / `mk-a11y-master`) |

---

## 19. Walkthrough Example

A solo founder has 80 ideas in their Linear backlog and wants to plan next month.

**Step 1 — In Claude / Cursor:**
> "List my top-priority Linear ideas for next month and turn the top one into
> a spec we can implement."

**Step 2 — AI orchestrates plan + spec + test generation:**

```
mk-plan-master.get_plan_source_info()
  → active: linear, version: 0.1.0

mk-plan-master.list_initiatives(status="triage", limit=80)
  → 80 initiatives

mk-plan-master.rank_backlog(method="rice", limit=10)
  → top 10:
    LIN-456 (Bulk-edit roles, 18.4, P1)
    LIN-289 (Audit log export, 14.2, P1)
    LIN-512 (Mobile app dark mode, 11.7, P2)
    ...

user: "Take the top one."

mk-plan-master.fetch_initiative("LIN-456")
mk-plan-master.score_initiative("LIN-456", method="rice")
  → score 18.4, tier P1
  → breakdown: reach=200, impact=1.5, confidence=0.7, effort=13

mk-plan-master.generate_spec_draft("LIN-456")
  → markdown ready for mk-spec-master

mk-spec-master.parse_spec(raw_text=<markdown>)
  → 4 ACs detected

mk-spec-master.extract_scenarios(...)
  → 1 happy + 3 error scenarios

for each scenario:
  mk-qa-master.generate_test(business_context=...)
  mk-spec-master.link_test_to_spec(spec_id, test_node_id, ac_hash=...)

mk-qa-master.run_tests
  → 4 tests RED (no implementation yet — this is intentional)
```

**Step 3 — Hand-off to the IDE (the family does *not* write app code):**

The 4 red tests are now the developer's TODO list. The user switches to
Claude Code / Cursor / Copilot and prompts:

> "Make these 4 tests pass."

The IDE iterates: read failing test → write app code → re-run tests → repeat.
Each loop is the AI client's primary job; the MCP family stays out of the way.

**Step 4 — Family takes over again, closes the loop:**

```
mk-qa-master.run_tests
  → 4 tests GREEN

mk-spec-master.get_coverage_matrix
  → "LIN-456: 4/4 AC covered"

mk-spec-master.get_optimization_plan
  → "Coverage solid. Next priority: LIN-289 (still 0 tests)."
```

**Step 5 — The user has, in one continuous flow:**
1. Triaged 80 ideas with RICE scoring
2. Picked top one with data-backed rationale
3. Generated a spec
4. Generated 4 tests (red — the TODO list)
5. Wrote implementation in IDE until tests went green
6. Tracked coverage automatically
7. Got the next priority from the coach

**Total time:** maybe 30–45 minutes (incl. the actual implementation work),
vs the usual half-day for the same workflow across 4 different tools.

**This is the demo video.** This is the Show HN screenshot. This is the
family's reason to exist — the MCPs own the *rails*, the IDE owns the *code*,
and TDD glues them together.

---

## 20. Decision Required Before Coding

1. **Confirm scope of v0.1 MVP** — 2 adapters + 6 tools, or even tighter?
2. **Spec draft template** — what fields go in? (Suggested: title, source, OKR, context, AC, out-of-scope.)
3. **RICE thresholds** — accept the default P0>25 / P1>10 / P2>3 / P3<3 or tune?
4. **First validating user** — who do you ask to try v0.1 before public launch?
5. **Public PRD?** — should this doc be public on day 1 (build-in-the-open)
   or kept private until v0.1 ships? mk-spec-master's PRD is public; mirror?

---

*End of PRD v0.1. Discussion in mk-plan-master Issues once the repo exists.*
