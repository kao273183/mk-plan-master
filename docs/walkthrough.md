# Walkthrough — one URL, two passes, two RICE scores

This is the end-to-end story of how `mk-plan-master` actually got used on a real idea — the same idea twice, once **without** `analyze_initiative` and once **with**. Same source URL, same product. Different rigor. The numbers below are pulled verbatim from the dogfood corpus at [`mk-plan-test/`](https://github.com/kao273183/mk-plan-test).

The point of the walkthrough isn't the tool surface — that's in the [README](../README.md). The point is **what `analyze_initiative` actually changes about the score**, in concrete pass-1 vs pass-2 numbers, and how the output then hands off to `mk-spec-master.parse_spec` and ultimately to `mk-qa-master.generate_test`.

---

## Setting

I was scrolling and saw a URL: `https://rightclickip.xyz/`. The pitch reads:

> "Instantly license your intellectual property. AI-powered, blockchain-secured, Web3-ready."

Interesting. IP licensing marketplace + AI contract drafting + on-chain receipts. Worth capturing as an initiative — but is it actually a P0 or am I just impressed by the marketing copy?

Two passes follow.

- **Pass 1** is the lazy path: I dump my impression into `add_initiative`, score it, generate a spec draft. The AI agrees with me. The score is high. Everyone is happy.
- **Pass 2** is the rigorous path: I run `analyze_initiative` first. The senior-PM SOP forces the AI to actually think about target users, competition, market signal, risks, MVP scope, and explicit out-of-scope. The score drops 3.8×.

Both passes are real and both initiatives are checked in side-by-side at `mk-plan-test/initiatives/IDEA-001.md` (pass 1) and `IDEA-002.md` (pass 2). The decision index records both, including timestamps.

---

## Pass 1 — without `analyze_initiative` (the lazy path)

### Step 1 · capture

```
Me: I just read https://rightclickip.xyz/. It's an IP licensing marketplace
    with AI contract drafting and blockchain receipts. Capture it as an
    initiative — I think reach is ~500, impact 2, confidence 0.5, effort
    around 12 person-weeks. Label it web3, ip-licensing, marketplace,
    ai-agent, blockchain.

AI (chains automatically):
    → mk-plan-master.add_initiative(
          title="一鍵式 IP 授權平台（AI + 區塊鏈）",
          body=<2-paragraph summary of the URL>,
          reach=500, impact=2, confidence=0.5, effort=12,
          labels=["web3","ip-licensing","marketplace","ai-agent","blockchain"],
          source_url="https://rightclickip.xyz/"
      )
    → {
        "id": "IDEA-001",
        "written_to": "/Users/.../mk-plan-test/initiatives/IDEA-001.md",
        "source": "markdown_local",
        "overwritten": false,
        "next_step_hint": "Score with mk-plan-master.score_initiative,
                           or analyze first with analyze_initiative."
      }
```

Note: I told the AI my impression and it summarized into a 2-paragraph body — concept source, core idea, target users, business model, differentiation. Thin but plausible. The family **does not** crawl `rightclickip.xyz/` itself; the AI client's WebFetch did that (or I narrated it from memory). `add_initiative` only persists what the AI summarized.

The resulting frontmatter on disk:

```yaml
---
id: IDEA-001
title: 一鍵式 IP 授權平台（AI + 區塊鏈）
status: triage
labels: [web3, ip-licensing, marketplace, ai-agent, blockchain]
reach: 500
impact: 2
confidence: 0.5
effort: 12
source_url: https://rightclickip.xyz/
created_at: 2026-05-16T09:15:26Z
---
```

No `out_of_scope`. No risk analysis. No competition table. Just the optimistic top-line.

### Step 2 · score

```
Me: Score it.

AI:
    → mk-plan-master.score_initiative(initiative_id="IDEA-001", method="rice")
    → {
        "initiative_id": "IDEA-001",
        "method": "rice",
        "score": 41.7,
        "breakdown": {
          "reach": 500.0, "impact": 2.0, "confidence": 0.5, "effort": 12.0
        },
        "tier": "P0",
        "rationale": "RICE = (500 × 2 × 0.5) / 12 = 41.7. Tier P0 (>25).",
        "stored": true
      }
```

**41.7. P0.** Tier P0 is "ship next quarter" in the default RICE thresholds (P0 > 25). The AI is now telling me this idea should be at the top of the roadmap. The index now has its first `scored` decision:

```json
{
  "ts": "2026-05-16T09:15:29.095075+00:00",
  "action": "scored",
  "details": {
    "method": "rice", "score": 41.7, "tier": "P0",
    "reach": 500.0, "impact": 2.0, "confidence": 0.5, "effort": 12.0
  }
}
```

### Step 3 · spec draft

```
Me: Generate a spec draft.

AI:
    → mk-plan-master.generate_spec_draft(
          initiative_id="IDEA-001",
          template="default"
      )
    → {
        "markdown": "# 一鍵式 IP 授權平台（AI + 區塊鏈）\n\n> Source: IDEA-001 ...",
        "suggested_filename": "IDEA-001.md",
        "template_used": "default",
        "ready_for_mk_spec_master": true,
        "next_step_hint": "Pass markdown to mk-spec-master.parse_spec(raw_text=...)"
      }
```

The draft (full file at `mk-plan-test/specs/IDEA-001.md`):

```markdown
# 一鍵式 IP 授權平台（AI + 區塊鏈）

> Source: IDEA-001 (markdown_local, triage)
> Priority: P0 (RICE score 41.7)
> Reference: https://rightclickip.xyz/

## Context
[concept source, pain point, solution, target users, business model, diff]

## Acceptance criteria
1. 創作者上架: 5 分鐘內完成 IP 上架
2. 即時授權成交: 60 秒內錢包付款 + 鏈上憑證
3. AI 合約代理: 自然語言 → 授權條款 + 合約草稿
4. 自動分潤: 鏈上結算、無人工介入
5. 可驗證證明: 第三方可在鏈上驗證授權真實性
6. 市場發現: 訪客免登入瀏覽、篩選分類

## Out of scope
- 跨司法管轄人工法律建議
- 法幣支付通道
- 衍生作品二次授權自動分潤
- 跨鏈橋接
- DRM / 線下執行
```

**6 ACs, 5 out-of-scope items inferred from the body.** Not bad — `generate_spec_draft` did its best with what was in the initiative.

But notice what's missing: **the AC for "AI 合約代理"** says the user describes use cases in **natural language**. The pass-1 body didn't surface that this is a hallucination risk — that an LLM might drop "non-sublicensable" from a templated contract clause. The spec is going to send 4 red tests to mk-qa-master that don't cover that failure mode.

### Step 4 · what's actually in the index after pass 1

```json
{
  "IDEA-001": {
    "decisions": [
      { "ts": "...09:15:29Z", "action": "scored",          "score": 41.7, "tier": "P0" },
      { "ts": "...09:15:32Z", "action": "spec_generated",  "template": "default" }
    ],
    "last_score": 41.7,
    "tier": "P0"
  }
}
```

**Total elapsed time: maybe 90 seconds.** Score, draft, done. The AI never pushed back on my numbers, never asked "what's `reach` actually counting?", never noticed the logo wall on the marketing site has no verifiable case studies.

---

## Pass 2 — with `analyze_initiative` (the rigorous path)

A few minutes later I came back to it. The 41.7 felt too good. Let me run it through the senior-PM SOP.

### Step 1 · capture (same URL, new id)

```
Me: Same URL, same idea, but this time run the senior-PM analysis SOP first.
    Use IDEA-002 so I can compare side by side.

AI:
    → mk-plan-master.add_initiative(
          title="RightClick — 一鍵式 IP 授權平台",
          body=<same 2-paragraph summary>,
          id="IDEA-002",
          reach=500, impact=2, confidence=0.5, effort=12,
          source_url="https://rightclickip.xyz/"
      )
    → { "id": "IDEA-002", ... }
```

Initial estimates same as pass 1. Now the analysis.

### Step 2 · `analyze_initiative` — the meta-tool

```
Me: Now run analyze_initiative on IDEA-002 with the default framework.

AI:
    → mk-plan-master.get_plan_context()   ← loads plan-knowledge.md
    → mk-plan-master.analyze_initiative(
          initiative_id="IDEA-002",
          framework="default"
      )
    → {
        "initiative": { ...IDEA-002 full record... },
        "framework": "default",
        "methodology_context": "<RICE thresholds + INVEST + personas...>",
        "analysis_checklist": {
          "1_target_users": "List 3 distinct personas with job-to-be-done...",
          "2_competition":  "Build a competition table with direct + indirect + do-nothing...",
          "3_market_signal":"Strong signals (evidence) vs weak/red flags...",
          "4_risks":        "Top 3 risks (regulatory / market / technical)...",
          "5_mvp_scope":    "What's IN — specific assets, chains, templates...",
          "6_out_of_scope": "What's OUT — explicit MVP fence (≥5 items)...",
          "7_rice_rationale": "Defend each input number with rationale..."
        },
        "instructions": "Fill in every section inline. After this completes,
                         call add_initiative(overwrite=true) with the enriched
                         body, then score_initiative.",
        "next_step_hint": "add_initiative(overwrite=true) -> score_initiative"
      }
```

`analyze_initiative` doesn't call an LLM. It just hands the AI a structured checklist and says **fill this in before you score**. The AI now has to actually research.

### Step 3 · the AI fills the checklist (this is where the work happens)

The AI's response (abbreviated — full version reaches `mk-plan-test/initiatives/IDEA-002.md`):

> **1. Target users (3 personas)** — independent digital creator (supply side), brand marketing lead (demand side), Web3 game/metaverse dev (dual-sided). Each with a concrete job-to-be-done and trigger event.
>
> **2. Competition + differentiation** —
>
> | Competitor | Strength | Weakness | Our diff |
> |---|---|---|---|
> | Story Protocol (a16z $140M+) | protocol layer, composable | infra-focused, creators must build UI | "ready-to-use marketplace" instead |
> | Getty / Shutterstock / Pond5 | stock + brand trust + legal | slow settlement, 30-50% commission, no AI contracts, no web3 IP | 60s settlement + crypto + AI terms |
> | DIY (Discord DM + Stripe + PDF) | zero learning cost, ~80% of what creators actually do today | no verifiable receipts, disputes unresolved, cross-border pain | on-chain receipt + template contract + crypto settle, one stack |
> | ASCAP / BMI / SOCAN | music performance rights done well | music-only, settlement delayed months, no commercial coverage | cross-category + instant settle |
>
> **Do-nothing (DIY) is the biggest threat, not Story Protocol.** This single line changes the threat-model.
>
> **3. Market signal** — strong macro signals (Story Protocol valuation $2.25B, gen-AI lawsuits, Adobe C2PA), but red flags on this specific product: logo wall has no verifiable case studies (logo washing risk), no published transaction volume / creator count / GMV, demo account public (`demo1234` — early launch stage).
>
> **4. Top 3 risks** — (a) jurisdictional non-enforceability (on-chain NFT receipts ≠ legal evidence in most courts) — fatal; (b) two-sided cold start — high probability; (c) AI contract hallucination dropping "non-sublicensable" clauses — high impact.
>
> **5. MVP scope (IN)** — single asset type first (digital illustration / character IP, not music — PRO regulation is more complex); single chain (Base or Polygon); 3 lawyer-reviewed templates; restricted AI term-builder (parameter selection from templates, **no free-text input**); USDC + ETH via WalletConnect; marketplace + creator dashboard; ERC-721 receipts with IPFS-pinned PDF.
>
> **6. Out of scope (explicit)** —
> 1. fiat payment rails (v1 crypto only)
> 2. cross-chain bridging
> 3. derivative auto-royalties (v2)
> 4. multi-jurisdiction custom legal advice (v1 templates only)
> 5. DRM / offline playback enforcement
> 6. collective-rights (PRO-style)
> 7. video / animated assets (v1 static images only)
> 8. enterprise SSO / SAML (v1 wallet-only)
>
> **7. RICE rationale** —
>
> | Input | Old (pass 1) | New | Why |
> |---|---:|---:|---|
> | reach | 500 | **250** | scope to "active users per quarter in initial regions (Singapore + US-west social communities)", not raw TAM |
> | impact | 2 | 2 | unchanged |
> | confidence | 0.5 | **0.4** | logo wall unverifiable + AI contract legal status untested + two-sided cold-start unproven + zero published GMV |
> | effort | 12 | **18** | wallet 3w + AI template system 4w + contracts/NFT 3w + marketplace 3w + lawyer-reviewed templates + security 3w + back-office / observability 2w |
>
> Expected RICE: (250 × 2 × 0.4) / 18 = **11.1 → P1**.

### Step 4 · write the enriched body back

```
AI (continuing automatically):
    → mk-plan-master.add_initiative(
          id="IDEA-002",
          title="RightClick — 一鍵式 IP 授權平台（AI + 區塊鏈）",
          body=<the full senior-PM analysis from above>,
          reach=250, impact=2, confidence=0.4, effort=18,
          out_of_scope=[
            "法幣支付通道（v1 純 crypto）",
            "跨鏈橋接",
            "衍生作品二次授權的自動分潤（v2）",
            "多司法管轄客製化法律建議（v1 只給範本）",
            "DRM / 線下播放執行",
            "集體管理權（PRO-style）",
            "影音 / 動態素材（v1 限靜態圖像）",
            "企業 SSO / SAML（v1 純錢包登入）"
          ],
          labels=["web3","ip-licensing","marketplace","ai-agent","blockchain",
                  "competitor-analysis"],
          overwrite=true
      )
    → { "id": "IDEA-002", "overwritten": true, ... }
```

The body is now ~80 lines of senior-PM analysis, not 2 paragraphs of marketing-copy paraphrase. The frontmatter carries 8 explicit out-of-scope items. Confidence dropped, effort raised.

### Step 5 · score

```
AI:
    → mk-plan-master.score_initiative(initiative_id="IDEA-002", method="rice")
    → {
        "initiative_id": "IDEA-002",
        "method": "rice",
        "score": 11.1,
        "breakdown": {
          "reach": 250.0, "impact": 2.0, "confidence": 0.4, "effort": 18.0
        },
        "tier": "P1",
        "rationale": "RICE = (250 × 2 × 0.4) / 18 = 11.1. Tier P1 (10-25).",
        "stored": true
      }
```

**11.1. P1.** Same idea. Same URL. 3.8× drop.

### Step 6 · spec draft, this time `detailed`

```
Me: Generate a detailed spec draft so mk-spec-master gets the risks +
    dependencies + estimated-effort sections too.

AI:
    → mk-plan-master.generate_spec_draft(
          initiative_id="IDEA-002",
          template="detailed"
      )
```

The full draft is at `mk-plan-test/specs/IDEA-002.md`. Key differences vs the pass-1 spec:

- **6 ACs but now concrete.** AC 2 in pass 2 says: "AI Term-Builder (restricted): user describes usage through a **restricted picker** (asset class / commercial / medium / duration / region); AI extracts parameters from templates; **free-text input is not permitted**." That single phrasing change kills the AI-contract-hallucination risk that pass-1 missed.
- **9 explicit Out-of-scope items** instead of 5 inferred. (Pass 1 missed: PRO-style collective rights, video/animation, enterprise SSO, music category itself.)
- **Risks section** — regulatory, market, technical/legal, each with mitigation
- **Dependencies section** — lawyer review, WalletConnect / Coinbase SDK, chain selection, IPFS pinning, Tokimi Pay alternatives
- **Estimated effort** — 18 person-weeks broken down by sub-system

This spec draft is now what `mk-spec-master.parse_spec(raw_text=...)` ingests.

---

## Side-by-side delta

The same URL, the same idea, two passes:

| Field | Pass 1 (no analyze) | Pass 2 (with analyze) | Delta |
|---|---:|---:|---|
| reach (per quarter) | 500 | 250 | scoped down to active users in initial geos |
| impact | 2 | 2 | unchanged |
| confidence | 0.5 | 0.4 | dropped — logo wall risk, untested AI-legal, cold-start, no GMV |
| effort (person-weeks) | 12 | 18 | +6 pw for lawyer review + security testing |
| out_of_scope items | 0 | 8 | explicit MVP fence |
| spec ACs | 6 (vague) | 6 (concrete + restricted free-text) | AI hallucination guarded against |
| **RICE** | **41.7** | **11.1** | **3.8× drop** |
| **tier** | **P0** | **P1** | one tier down |
| Time spent | ~90s | ~5-10 min | the cost of being rigorous |
| Decision trail entries | 2 | 2 | both recorded in `.mk-plan-master/index.json` |

P0 → P1 is **"ship next quarter"** → **"validate first"**. That's the difference between burning 18 person-weeks on something whose legal foundations might not hold, vs running 2 weeks of lawyer-review + 2 anchor-creator conversations before committing.

`analyze_initiative` is what bought that delta. The tool itself just hands the AI a checklist — but the checklist forces the AI not to shortcut, and the resulting analysis surfaces the risks the lazy path misses. **The difference between a junior PM and a senior PM.**

---

## Hand-off to the rest of the family

The pass-2 spec draft (markdown, ready) now leaves `mk-plan-master` and enters the family loop:

```
mk-spec-master.parse_spec(raw_text=<markdown from generate_spec_draft>)
    → 6 AC detected, each with ac_hash
mk-spec-master.extract_scenarios(spec_id="IDEA-002")
    → 6 happy + 4 error scenarios (negation-aware: "restricted picker"
      generates "reject free-text input" as an error scenario)

for scenario in scenarios:
    mk-qa-master.generate_test(business_context=scenario.gherkin)
    mk-spec-master.link_test_to_spec(spec_id="IDEA-002", test_node_id=..., ac_hash=...)
    # 10 tests RED, no implementation yet — this is the TODO list

──── boundary: family hands off to your IDE ────────────────────────────
your IDE (Claude Code / Cursor / Copilot):
    reads first failing test → writes app code → re-runs → repeat
    iterates until tests go green
──── boundary: family takes over again ────────────────────────────────

mk-qa-master.run_tests
    → 10 tests GREEN

mk-spec-master.get_coverage_matrix
    → "IDEA-002: 10/10 AC covered"

mk-spec-master.get_optimization_plan
    → "Coverage solid. Drift: 0 specs drifted. Next priority: ..."
```

The **tests are the executable form of the spec**. The IDE's job is to flip them red→green. The coverage matrix automatically reflects what's actually verified. This is the TDD framing the family was designed around — the `generate_spec_draft → parse_spec → extract_scenarios → generate_test` chain produces a runnable TODO list that the IDE consumes.

And here's the upstream value: because pass-2's spec had a **concrete restricted-picker AC** instead of pass-1's vague natural-language AC, mk-spec-master's scenario extractor produced an explicit `reject free-text input` error scenario. mk-qa-master generated a test for it. The IDE has to write the input-validation code to make it pass. **The hallucination risk gets engineered out at the test level**, not discovered post-launch in production.

That's the case for upstream rigor. `analyze_initiative` paid for itself before a single line of code got written.

---

## What the decision trail looks like at the end

```json
{
  "IDEA-001": {
    "decisions": [
      { "ts": "2026-05-16T09:15:29Z", "action": "scored",         "score": 41.7, "tier": "P0" },
      { "ts": "2026-05-16T09:15:32Z", "action": "spec_generated", "template": "default" },
      { "ts": "2026-05-16T09:18:39Z", "action": "scored",         "score": 41.7, "tier": "P0" },
      { "ts": "2026-05-16T09:18:40Z", "action": "spec_generated", "template": "default" }
    ],
    "last_score": 41.7,
    "tier": "P0"
  },
  "IDEA-002": {
    "decisions": [
      { "ts": "2026-05-16T09:37:20Z", "action": "scored",         "score": 11.1, "tier": "P1" },
      { "ts": "2026-05-16T09:39:02Z", "action": "spec_generated", "template": "detailed" }
    ],
    "last_score": 11.1,
    "tier": "P1"
  }
}
```

If anyone asks next quarter — **why didn't we ship the IP licensing thing?** — the answer is in the index. Pass 1 said P0 41.7 at 09:15. Pass 2 said P1 11.1 at 09:37. The audit trail records both, with the exact reach/impact/confidence/effort numbers that drove each tier. No more "didn't we discuss this in March?" No more bouncing-back ideas with no memory of why we passed last time.

This is the self-reinforcement layer doing its job. `get_decision_signature` will flag this as `score whiplash` (the 3.8× swing) — bad data quality on the pass-1 pass — and `get_planning_history` will pick it up in the trend report next time someone runs `rank_backlog`. **The MCP measures itself.**

---

## TL;DR

- `analyze_initiative` doesn't call an LLM. It scaffolds a senior-PM checklist that forces the AI to think.
- Same URL, same idea, two passes — RICE dropped from 41.7 (P0) to 11.1 (P1).
- The pass-2 spec draft has concrete-enough ACs that mk-qa-master can write tests that catch the AI-contract hallucination risk **before any code is written**.
- The IDE writes the implementation; the family wraps the rails on either side.
- Every decision is in `.mk-plan-master/index.json` with timestamps. Nothing bounces back unexplained next quarter.
- This is what shipping the upstream half of the AI dev pipeline looks like.
