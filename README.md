<p align="center">
  <img src="https://raw.githubusercontent.com/kao273183/mk-plan-master/main/assets/logo.png" alt="mk-plan-master logo" width="180" />
</p>

<h1 align="center">MK Plan Master</h1>

<p align="center">
  <em>AI 規劃大師 — ideas in, prioritized plans out. Spec drafts that hand straight to mk-spec-master.</em>
</p>

<p align="center">
  <strong>English</strong> · <a href="README.zh-TW.md">繁體中文</a>
</p>

<p align="center">
  <a href="https://pypi.org/project/mk-plan-master/"><img src="https://img.shields.io/pypi/v/mk-plan-master.svg?logo=pypi&logoColor=white&color=3775A9" alt="PyPI" /></a>
  <img src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-3776AB.svg?logo=python&logoColor=white" alt="Python 3.10-3.13" />
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" /></a>
  <img src="https://img.shields.io/badge/MCP-compatible-7C3AED.svg" alt="MCP compatible" />
  <img src="https://img.shields.io/badge/status-alpha-orange.svg" alt="Status: Alpha" />
</p>

> Idea triage + RICE scoring + quarterly roadmap + spec-draft bridge — over MCP. Reads from Linear / JIRA / Notion / Markdown, hands the generated spec draft directly to [`mk-spec-master.parse_spec`](https://github.com/kao273183/mk-spec-master), and remembers every decision so the same idea never bounces back unexplained.

> **🟢 Alpha — v0.1.** **15 tools** + **4 adapters** + 77 tests passing. Full design in [`docs/prd.md`](docs/prd.md). Walkthrough using a real dogfood case in [`docs/walkthrough.md`](docs/walkthrough.md).

---

## Why this exists

The AI-driven dev pipeline today looks like this:

```
???  →  Spec  →  Code  →  Test  →  Coverage  →  Coach
(gap)   mk-spec  IDE     mk-qa    mk-spec      both
```

The `mk-*` family already shipped two MCPs covering the right half:

- [`mk-spec-master`](https://github.com/kao273183/mk-spec-master) — specs in, scenarios out, coverage matrix
- [`mk-qa-master`](https://github.com/kao273183/mk-qa-master) — scenarios in, runnable tests out (pytest / Jest / Cypress / Go test / Maestro)

`mk-plan-master` closes the **upstream** gap. The piece nobody has built MCP-native yet: turn a pile of 30–200 ideas (chat snippets, customer calls, URLs, gut hunches) into a prioritized, RICE-scored quarterly roadmap, and **emit a spec draft that drops straight into `mk-spec-master.parse_spec(raw_text=...)`** — no manual reformatting, no copy-paste fragility.

It's the planning MCP that also **measures its own decision quality over time** — history snapshots, decision signatures (ghost initiatives / score whiplash / orphan OKRs), and tool-usage telemetry. The mk-spec-master v0.4 self-reinforcement layer, applied one step upstream.

---

## The family loop

```
   ┌─────────┐      ┌──────────┐      ┌─────────┐      ┌─────────┐      ┌──────────┐      ┌─────────┐
   │  Idea   │ ───> │   Plan   │ ───> │  Spec   │ ───> │  Code   │ ───> │   Test   │ ───> │ Coverage│
   │ (chat,  │      │ mk-plan- │      │ mk-spec-│      │ your IDE│      │ mk-qa-   │      │ mk-spec-│
   │ URL,    │      │ master   │      │ master  │      │ (Claude │      │ master   │      │ master  │
   │ call)   │      │          │      │         │      │ Code /  │      │          │      │         │
   │         │      │ RICE +   │      │ AC +    │      │ Cursor /│      │ runnable │      │ matrix  │
   │ AI      │      │ roadmap +│      │ scenarios│     │ Copilot)│      │ tests in │      │ + drift │
   │ summary │      │ spec     │      │ + drift │      │ writes  │      │ pytest / │      │ + coach │
   │         │      │ draft    │      │         │      │ impl    │      │ Jest / …│      │         │
   └─────────┘      └──────────┘      └─────────┘      └─────────┘      └──────────┘      └─────────┘
       ▲                  │                  │                  ▲                  ▲                  │
       │                  │                  │                  │                  │                  │
       │                  └──── spec_draft ──┘                  │                  │                  │
       │                                                        │                  │                  │
       │                                            red tests ──┘                  │                  │
       │                                                                           │                  │
       └─────────────────── decision history / chronic patterns ───────────────────┴──────────────────┘
```

**Important.** Code lives in your **IDE**, not in the family. Between spec and green tests, Claude Code / Cursor / Copilot writes the actual implementation. The MCP family wraps the *rails* — planning, spec, test, coverage, coach — and deliberately leaves the code-writing layer to whatever AI-pair-programming tool you already use. Tests generated by mk-qa-master are a runnable TODO list; the IDE loop flips them red → green.

---

## Install

```bash
uvx mk-plan-master    # or: pip install mk-plan-master
```

Add to your MCP client config:

```json
{
  "mcpServers": {
    "mk-plan-master": {
      "command": "uvx",
      "args": ["mk-plan-master"],
      "env": {
        "PLAN_SOURCE": "markdown_local",
        "PLAN_PROJECT_ROOT": "/path/to/your/project"
      }
    }
  }
}
```

Works in Claude Desktop, Claude Code, Cursor, Codex CLI, Gemini CLI — any MCP client.

Then in your AI session:

> "Use mk-plan-master to score every triage idea, pick the top one, run analyze_initiative on it, then generate a spec draft and hand it to mk-spec-master."

---

## Tool surface (15 tools)

Grouped by role in the idea → plan → spec → memory loop.

### Meta — orientation (1)

| Tool | Purpose |
|---|---|
| `get_plan_source_info` | Active adapter + all available + version. Call first so the AI knows whether to expect markdown / Linear / JIRA / Notion semantics |

### Discovery — find and load ideas (2)

| Tool | Purpose |
|---|---|
| `list_initiatives` | Enumerate initiatives from the active source (filter by status / label / limit). For Linear: triage / backlog / unstarted. For JIRA: statusCategory='To Do'. For Notion: status in (Triage / Backlog / Idea) |
| `fetch_initiative` | Pull a single initiative by id. Returns `{id, source, title, body, url, status, labels, raw_metadata}` — `raw_metadata` carries the RICE inputs (reach / impact / confidence / effort / okr) |

### Capture — chat / WebFetch handoff (1)

| Tool | Purpose |
|---|---|
| `add_initiative` | Persist an idea you (the AI client) already gathered via WebFetch / chat / call notes into `PLAN_PROJECT_ROOT/initiatives/<id>.md`. **The family does NOT crawl URLs** — you summarize, this tool writes. Auto-generates `IDEA-NNN` if id is omitted. markdown_local only; for Linear / JIRA / Notion, create the issue in that platform |

### Analysis — the senior-PM SOP (1)

| Tool | Purpose |
|---|---|
| `analyze_initiative` | Force a senior-PM analysis SOP **before** scoring. Returns a structured checklist (target users / competition / market signal / risks / MVP scope / out-of-scope / RICE rationale) the AI must fill in inline. Loads `plan-knowledge.md` context if present. **Does NOT call an LLM** — it scaffolds the prompt so the AI doesn't shortcut into a shallow read. Frameworks: `default` (7 sections), `lite` (4 sections), `lean_canvas` (9 blocks). Typical chain: `add_initiative` → `analyze_initiative` → `add_initiative(overwrite=true)` with the enriched body → `score_initiative` |

### Scoring — prioritize the backlog (2)

| Tool | Purpose |
|---|---|
| `score_initiative` | Score one initiative with RICE or Impact-Effort. Pass `initiative_id` (RICE inputs read from raw_metadata) or `raw_text + overrides` for ad-hoc. Tier thresholds: P0 > 25, P1 10..25, P2 3..10, P3 < 3. Appends a `scored` decision to `.mk-plan-master/index.json` |
| `rank_backlog` | Score the whole backlog and return the top-N descending. Pure arithmetic, deterministic rationale strings. **Auto-archives a snapshot** to `.mk-plan-master/history/<ts>.json` (debounced 5 min) so `get_planning_history` / `get_decision_signature` can compute trend deltas |

### Bridge — the family lock-in (1)

| Tool | Purpose |
|---|---|
| **`generate_spec_draft`** | **The family-bridge tool.** Produce a markdown spec draft shaped so `mk-spec-master.parse_spec(raw_text=...)` ingests it verbatim — no manual editing. Three templates: `default` (title / source / OKR / context / AC / out-of-scope), `lite` (title / context / AC), `detailed` (default + risks + dependencies + estimated effort). Appends a `spec_generated` decision to the index |

### Roadmap — quarterly planning (2)

| Tool | Purpose |
|---|---|
| `generate_roadmap` | Pack the ranked backlog into a quarterly markdown roadmap, respecting an engineering capacity envelope (engineer-months × 4 person-weeks) minus a buffer (default 20%). Greedy score-per-effort packer. Output split into P0 commitments / P1 commitments / P2 stretch / Deferred / Capacity summary |
| `analyze_roadmap_balance` | Classify top-N initiatives into feature / tech_debt / strategic / unlabeled buckets, surface ratio + score-share + heuristic advisory. Label vocabularies configurable. Answers "is the roadmap balanced?" / "are we starving tech debt?" |

### Knowledge — methodology layer (2)

| Tool | Purpose |
|---|---|
| `init_plan_knowledge` | Create `PLAN_PROJECT_ROOT/plan-knowledge.md` from a starter template — RICE / WSJF / Impact-Effort / OKR mapping / INVEST / personas + TODO sections for active OKRs / strategic bets / tech-debt zones / glossary. Idempotent |
| `get_plan_context` | Read `plan-knowledge.md` (with built-in fallback). Optional `section` filter pulls one heading. Call near the start of a planning session so the same methodology + glossary colours every score that follows |

### Self-reinforcement — long-running view (3)

| Tool | Purpose |
|---|---|
| `get_planning_history` | Trend deltas (current vs ~7d / ~30d) for top-10 RICE-ranked snapshots. Surfaces churn + average score. "Are we improving?" / "Is the same idea always at the top?" |
| `get_decision_signature` | Chronic patterns: **ghost initiatives** (top-10 in >50% of snapshots but never spec_generated), **score whiplash** (RICE swings >50% between snapshots → bad data quality), **orphan OKRs** (in index but zero initiatives in current top-10). "Which ideas keep getting punted?" |
| `get_telemetry` | Aggregate `.mk-plan-master/telemetry.jsonl` (name + duration + ok only — argument values **never** logged). Surfaces top tools, error rates, p50 / p95 / p99 latency, dead surface (declared but never called) |

---

## Adapter status

| `PLAN_SOURCE` | Source | Status | Auth |
|---|---|---|---|
| `markdown_local` | Local `initiatives/*.md` with YAML-ish frontmatter | Shipped in v0.1.0 | none |
| `linear` | Linear API (GraphQL), filtered to triage / backlog / unstarted state types | Shipped in v0.1.0 | `LINEAR_API_KEY` + `PLAN_PROJECT_KEY=<team-key>` (optional) |
| `jira` | JIRA Cloud (REST v3, ADF → markdown), filtered to `statusCategory='To Do'` | Shipped in v0.1.0 | `JIRA_BASE_URL` + `JIRA_EMAIL` + `JIRA_API_TOKEN` + `PLAN_PROJECT_KEY=<project-key>` (optional) |
| `notion` | Notion databases (REST v1, blocks → markdown), filtered to Status in (Triage / Backlog / Idea) | Shipped in v0.1.0 | `NOTION_TOKEN` + `PLAN_PROJECT_KEY=<database-id>` |

---

## Why `analyze_initiative` exists — a real case study

This is the differentiator. AI clients, by default, shortcut into a shallow read of any idea handed to them. They infer Reach / Impact / Confidence / Effort from a 2-paragraph blurb and produce a confident-looking RICE score that's mostly noise. The numbers below are from the actual dogfood corpus in `mk-plan-test/` — **same URL, same idea, two passes**.

**Pass 1 — without `analyze_initiative`** (the AI just reads the URL and guesses):

```
IDEA-001  ·  一鍵式 IP 授權平台（AI + 區塊鏈）
  reach        500
  impact         2
  confidence   0.5
  effort        12  person-weeks
  out_of_scope  []  (none)
  RICE         (500 × 2 × 0.5) / 12  =  41.7   →   P0
```

A confident P0. Looks like a no-brainer "ship it next quarter."

**Pass 2 — with `analyze_initiative`** (the AI is forced through the senior-PM SOP first):

```
IDEA-002  ·  RightClick — 一鍵式 IP 授權平台（AI + 區塊鏈）
  reach        250                    ←  scoped to "active users per quarter
                                          in initial regions (Singapore + US-west
                                          social), not raw addressable market"
  impact         2                    ←  same
  confidence   0.4                    ←  dropped: logo wall is unverifiable,
                                          AI-contract legal status untested,
                                          two-sided cold-start unproven, no GMV
  effort        18  person-weeks      ←  raised: wallet 3w + AI templates 4w
                                          + contracts/NFT 3w + marketplace 3w
                                          + lawyer review + security 3w
                                          + backoffice/observability 2w
  out_of_scope  8 explicit items      ←  fiat rails, cross-chain bridging,
                                          derivative auto-royalties (v2),
                                          multi-jurisdiction custom legal,
                                          DRM, PRO-style collective rights,
                                          video/animation, enterprise SSO
  RICE         (250 × 2 × 0.4) / 18  =  11.1   →   P1
```

**The delta** — same URL, same idea, an order of magnitude more honest:

| Field | Pass 1 (junior PM) | Pass 2 (senior PM SOP) | Delta |
|---|---:|---:|---|
| reach | 500 | 250 | scoped down |
| confidence | 0.5 | 0.4 | dropped — logo washing risk, AI-contract legal risk surfaced |
| effort | 12 pw | 18 pw | +6 pw for lawyer review + security |
| out_of_scope | 0 items | 8 items | explicit MVP fence |
| **RICE** | **41.7** | **11.1** | **3.8× drop** |
| **tier** | **P0** | **P1** | one tier down |

P0 → P1 is the difference between "ship next quarter" and "validate first." `analyze_initiative` is the SOP that gets you there without needing a senior PM in the room. Same idea, same source URL — different rigor.

Both initiatives are in [`mk-plan-test/initiatives/`](https://github.com/kao273183/mk-plan-test) verbatim. Both spec drafts are in `mk-plan-test/specs/`. The full decision trail is in `.mk-plan-master/index.json` — every `scored` and `spec_generated` event with timestamps. Walkthrough with prompts + tool chains in [`docs/walkthrough.md`](docs/walkthrough.md).

---

## 4 prompting workflows

Four natural-language prompts cover ~90% of real use. Each is one sentence to your AI client; the tools chain automatically.

### 1. Lock one idea — URL → spec_draft

> "I read https://rightclickip.xyz/ — capture it as an initiative, run analyze_initiative on it, score it, and produce a detailed spec draft I can hand to mk-spec-master."

Chains: `add_initiative` (from your chat summary, family does NOT crawl) → `analyze_initiative` → `add_initiative(overwrite=true)` (with the enriched body) → `score_initiative` → `generate_spec_draft(template="detailed")` → `mk-spec-master.parse_spec(raw_text=...)`.

### 2. Weekly backlog re-rank — trend over time

> "Every Monday, rank my Linear triage backlog with RICE and show me the trend vs last week and last month."

Chains: `rank_backlog(method="rice", limit=10)` → `get_planning_history(window_days=30)`. The first call auto-archives the snapshot; the second reads them all and computes deltas.

### 3. Senior-PM SOP on demand

> "Apply the senior-PM analysis SOP to IDEA-014 — I want target users, competition, market signal, risks, MVP scope, out-of-scope, and RICE rationale before I score it."

Chains: `get_plan_context` (loads methodology + glossary) → `fetch_initiative("IDEA-014")` → `analyze_initiative("IDEA-014", framework="default")` → AI fills checklist in response → `add_initiative(overwrite=true)` → `score_initiative`.

### 4. Quarterly roadmap from Notion triage

> "Pull every Notion idea in the Triage view, rank them with RICE, then pack a Q3 2026 roadmap assuming 4 engineers and 20% buffer. Tell me if the feature/tech-debt/strategic mix looks healthy."

Chains: `list_initiatives(status="triage")` → `rank_backlog` → `generate_roadmap(capacity_engineer_months=12, period="Q3 2026", buffer_pct=20)` → `analyze_roadmap_balance`.

---

## Self-reinforcement layer

`get_planning_history` + `get_decision_signature` + `get_telemetry` are the trio that makes mk-plan-master measure **its own decision quality** over time. The mk-spec-master v0.4 pattern, applied one step upstream.

| Layer | Question it answers | Storage |
|---|---|---|
| **History** | "Are we improving? Is the same idea always at the top?" | `.mk-plan-master/history/<ts>.json` — auto-archived per `rank_backlog` call, debounced 5 min |
| **Decision signature** | "Which ideas keep getting punted (ghost)? Which scores swing wildly (whiplash)? Which OKRs have zero execution (orphan)?" | Computed from history + `index.json` |
| **Telemetry** | "What's the AI actually using? Which tools are slow? Which are dead surface?" | `.mk-plan-master/telemetry.jsonl` — append-only, name + duration + ok only, payloads never logged |

Same shape as mk-spec-master's `get_spec_history` / `get_drift_signature` / `get_telemetry`, so if you already trust that pattern you know the layout.

The `decisions[]` audit trail on every initiative ("why did we deprioritize this last quarter?") is what kills the *bouncing back* problem. No more "didn't we discuss this in March?" — March's RICE breakdown is in the index with its `confidence` and `effort` values.

---

## Why this is missing from the ecosystem

| Tool | Lock-in | What we do differently |
|---|---|---|
| Productboard | $20-50/user/mo, walled garden | MCP-native: lives where the AI lives. Read existing Linear / JIRA / Notion, don't import to a new tool |
| Aha! | $59-149/user/mo, enterprise | Open-source baseline, SMB / indie / AI-native segment |
| Linear / JIRA | Backlog UI, no triage framework, no plan→spec bridge | We add the scoring + roadmap + spec-bridge layers on top of what you already have |
| Cursor / Claude "ask AI to plan" | Free-form chat, no persistence | Structured outputs, JSON index, traceable decisions, snapshot history |
| AWS Kiro plan phase | AWS IDE only, proprietary | MCP-native, multi-client |
| GitHub Spec Kit | Spec-first, doesn't reach upstream into idea triage | We're the missing pre-spec layer; complementary |

See [`docs/prd.md` §4](docs/prd.md) for the full positioning.

---

## Status

| Milestone | Scope | Status |
|---|---|---|
| **v0.1** (4 adapters, 15 tools, RICE + Impact-Effort, generate_spec_draft, plan-knowledge, self-reinforcement) | This release | Shipped |
| v0.2 (Productboard adapter, `cluster_feedback`, WSJF method) | +1 week | Planned |
| v0.3 (Intercom / Zendesk adapters, `compare_competitors`, `link_initiative_to_okr`) | +2 weeks | Planned |
| v1.0 (production-ready, docs, integration recipes, blog series) | Q3 2026 | Planned |

77 tests passing on Python 3.10 / 3.11 / 3.12 / 3.13.

---

## Family

- [`mk-spec-master`](https://github.com/kao273183/mk-spec-master) — AI 規格大師. Spec → scenarios → coverage matrix. `generate_spec_draft` output is shaped to drop into its `parse_spec(raw_text=...)` verbatim.
- [`mk-qa-master`](https://github.com/kao273183/mk-qa-master) — AI 測試大師. Scenarios → runnable tests in pytest / Jest / Cypress / Go test / Maestro.

The family loop: **mk-plan-master → mk-spec-master → your IDE → mk-qa-master → back into mk-spec-master coverage**.

---

## License

MIT © 2026 Jack Kao — see [`LICENSE`](LICENSE).

**Plain-English version:** personal use, commercial use, modification, redistribution — all allowed. The only requirement is that you keep the copyright and license notice in your copy. **No warranty**: if it breaks in production, you can't come after the author.

Built by [Jack Kao](https://github.com/kao273183) . Part of the `mk-*` family: `mk-qa-master` + `mk-spec-master` + `mk-plan-master`.

If this saved you time, [a coffee](https://www.buymeacoffee.com/minikao) goes a long way.
