<p align="center">
  <img src="https://raw.githubusercontent.com/kao273183/mk-plan-master/main/assets/logo.png" alt="AI 規劃大師 logo" width="180" />
</p>

<h1 align="center">AI 規劃大師 ｜ MK Plan Master</h1>

<p align="center">
  <em>想法進、計畫出。spec 草稿一鍵接給 mk-spec-master，不用手抄。</em>
</p>

<p align="center">
  <a href="README.md">English</a> · <strong>繁體中文</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/mk-plan-master/"><img src="https://img.shields.io/pypi/v/mk-plan-master.svg?logo=pypi&logoColor=white&color=3775A9" alt="PyPI" /></a>
  <img src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-3776AB.svg?logo=python&logoColor=white" alt="Python 3.10-3.13" />
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" /></a>
  <img src="https://img.shields.io/badge/MCP-compatible-7C3AED.svg" alt="MCP compatible" />
  <img src="https://img.shields.io/badge/status-alpha-orange.svg" alt="Status: Alpha" />
</p>

> 把堆積在 Linear / JIRA / Notion / Markdown 的想法用 RICE 排序、產出季度 roadmap、產生可直接餵給 [`mk-spec-master.parse_spec`](https://github.com/kao273183/mk-spec-master) 的 spec 草稿。每一個決策都記下來，同一個 idea 不會下一季再原封不動跳回 top 10。

> **🟢 Alpha — v0.1。** **15 個 tool** + **4 個 adapter** + 77 個測試通過。完整設計見 [`docs/prd.md`](docs/prd.md)，用真實 dogfood 跑完整流程見 [`docs/walkthrough.md`](docs/walkthrough.md)。

---

## 為什麼會有這個

目前 AI 開發流水線長這樣：

```
???  →  Spec  →  Code  →  Test  →  Coverage  →  Coach
(空)    mk-spec  IDE     mk-qa    mk-spec      兩邊都管
```

`mk-*` 家族已經出了兩個負責下半段的 MCP：

- [`mk-spec-master`](https://github.com/kao273183/mk-spec-master) — 規格進、場景出、覆蓋矩陣
- [`mk-qa-master`](https://github.com/kao273183/mk-qa-master) — 場景進、可跑測試出（pytest / Jest / Cypress / Go test / Maestro）

`mk-plan-master` 補的是**上游**那一塊——沒人用 MCP 做的那一段：把 30–200 個來自客戶 call、業務聊天、Twitter、自己腦子裡的想法，變成依 RICE 排好序、配好季度 capacity 的 roadmap，然後**直接吐出 mk-spec-master.parse_spec 能吃的 spec 草稿**，零手抄、零 copy-paste 漏字風險。

更狠的是，這個 MCP 還會**記錄自己的決策品質**：history 快照、決策簽章（ghost initiative / score whiplash / orphan OKR）、tool-usage telemetry。把 mk-spec-master v0.4 的自我強化模式，套到上游一段。

---

## 家族流水線

```
   ┌─────────┐      ┌──────────┐      ┌─────────┐      ┌─────────┐      ┌──────────┐      ┌─────────┐
   │  Idea   │ ───> │   Plan   │ ───> │  Spec   │ ───> │  Code   │ ───> │   Test   │ ───> │ Coverage│
   │ 聊天 /  │      │ mk-plan- │      │ mk-spec-│      │ 你的 IDE│      │ mk-qa-   │      │ mk-spec-│
   │ URL /   │      │ master   │      │ master  │      │ (Claude │      │ master   │      │ master  │
   │ 客戶 call│     │          │      │         │      │ Code /  │      │          │      │         │
   │         │      │ RICE +   │      │ AC +    │      │ Cursor /│      │ 可跑測試 │      │ 矩陣 +  │
   │ AI 摘要 │      │ roadmap +│      │ 場景 +  │      │ Copilot)│      │ pytest / │      │ drift + │
   │ 後丟進來│      │ spec 草稿│      │ drift   │      │ 寫實作  │      │ Jest / …│      │ coach   │
   │         │      │          │      │         │      │         │      │          │      │         │
   └─────────┘      └──────────┘      └─────────┘      └─────────┘      └──────────┘      └─────────┘
       ▲                  │                  │                  ▲                  ▲                  │
       │                  │                  │                  │                  │                  │
       │                  └──── spec_draft ──┘                  │                  │                  │
       │                                                        │                  │                  │
       │                                          紅色 test ──┘                    │                  │
       │                                                                           │                  │
       └───────────────────── 決策歷史 / 慢性模式 ─────────────────────────────────┴──────────────────┘
```

**重點：** code 寫在你的 **IDE**，不在家族裡。spec 跟綠燈 test 之間那段實作，是 Claude Code / Cursor / Copilot 負責。家族包的是**rails**——規劃、規格、測試、覆蓋、教練——故意把寫 code 那段留給你本來就在用的 AI 寫程式工具。mk-qa-master 產的 test 等於是一份**可執行的 TODO list**，IDE 自己迴圈把它從紅變綠。

---

## 安裝

```bash
uvx mk-plan-master    # 或：pip install mk-plan-master
```

MCP client config 加上：

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

Claude Desktop、Claude Code、Cursor、Codex CLI、Gemini CLI 通通可以。

Claude Desktop config 路徑：

- **macOS**：`~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**：`%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**：`~/.config/Claude/claude_desktop_config.json`

然後在 AI session 直接說：

> 「用 mk-plan-master 把所有 triage 的 idea 都算 RICE、挑最高的那個跑 analyze_initiative，再生 spec 草稿丟 mk-spec-master。」

---

## Tool 表（15 個）

依在「想法 → 計畫 → 規格 → 記憶」迴圈裡的角色分組。

### Meta — 暖機（1）

| Tool | 用途 |
|---|---|
| `get_plan_source_info` | 看目前 adapter、有哪些可用、版本——session 第一個叫，AI 才知道後面該預期 markdown / Linear / JIRA / Notion 哪一套語意 |

### Discovery — 找想法、讀想法（2）

| Tool | 用途 |
|---|---|
| `list_initiatives` | 列目前 source 內的 initiative（可按 status / label / limit 過濾）。Linear → triage / backlog / unstarted；JIRA → `statusCategory='To Do'`；Notion → status in (Triage / Backlog / Idea） |
| `fetch_initiative` | 依 id 拉單一 initiative 完整內容，回傳 `{id, source, title, body, url, status, labels, raw_metadata}`。`raw_metadata` 裡放 RICE 輸入（reach / impact / confidence / effort / okr） |

### Capture — 把 chat / WebFetch 抓回來的想法存進來（1）

| Tool | 用途 |
|---|---|
| `add_initiative` | 把你（AI client）剛剛從 WebFetch / 聊天 / 客戶 call 摘要好的想法寫進 `PLAN_PROJECT_ROOT/initiatives/<id>.md`。**家族故意不爬 URL**——你摘要，這個 tool 落地。id 省略時自動 `IDEA-NNN`。只支援 markdown_local；Linear / JIRA / Notion 請在那邊原生 UI 開 issue |

### Analysis — 資深 PM 的 SOP（1）

| Tool | 用途 |
|---|---|
| `analyze_initiative` | **打分前**強制跑一輪資深 PM 分析 SOP。回傳一份結構化 checklist（target users / competition / market signal / risks / MVP scope / out-of-scope / RICE rationale）給 AI 在 response 裡填。會吃 `plan-knowledge.md` 上下文。**不會自己呼叫 LLM**——它只是把 prompt 鷹架做好，逼 AI 不要 shortcut。framework：`default`（7 段）、`lite`（4 段）、`lean_canvas`（9 格）。常見鏈：`add_initiative` → `analyze_initiative` → `add_initiative(overwrite=true)` 寫回充實版 body → `score_initiative` |

### Scoring — 排序 backlog（2）

| Tool | 用途 |
|---|---|
| `score_initiative` | 對單一 initiative 跑 RICE 或 Impact-Effort。可以給 `initiative_id`（RICE 輸入從 raw_metadata 讀）或 `raw_text + overrides` 走 ad-hoc。tier 門檻：P0 > 25、P1 10..25、P2 3..10、P3 < 3。每次有 `initiative_id` 都會在 `.mk-plan-master/index.json` 寫一筆 `scored` 決策 |
| `rank_backlog` | 把整個 backlog 算分數、descend 排出 top-N。純算術、rationale 由 breakdown 推導，輸出 deterministic。**每次呼叫自動 archive snapshot** 到 `.mk-plan-master/history/<ts>.json`（5 分鐘 debounce），給 `get_planning_history` / `get_decision_signature` 算 trend delta |

### Bridge — 家族最關鍵的那塊（1）

| Tool | 用途 |
|---|---|
| **`generate_spec_draft`** | **家族橋接 tool。** 對單一 initiative 產 markdown spec 草稿，格式**故意對齊** `mk-spec-master.parse_spec(raw_text=...)` 的解析器，可直接餵、不用手改。三個模板：`default`（title / source / OKR / context / AC / out-of-scope）、`lite`（title / context / AC）、`detailed`（default + risks + dependencies + estimated effort）。會 append `spec_generated` 決策到 index |

### Roadmap — 季度規劃（2）

| Tool | 用途 |
|---|---|
| `generate_roadmap` | 拿排好序的 backlog、配上 engineering capacity 信封（engineer-months × 4 person-weeks 再扣 buffer，預設 20%），用 score-per-effort 貪婪打包成季度 markdown roadmap。輸出分 P0 commitments / P1 commitments / P2 stretch / Deferred / Capacity summary |
| `analyze_roadmap_balance` | 把 top-N initiative 依 label 分 feature / tech_debt / strategic / unlabeled 桶，秀比例 + 分數佔比 + 啟發式建議。Label 詞彙表可自訂。回答「roadmap 平衡嗎？」「是不是把 tech debt 餓死了？」 |

### Knowledge — 方法論層（2）

| Tool | 用途 |
|---|---|
| `init_plan_knowledge` | 在 `PLAN_PROJECT_ROOT/plan-knowledge.md` 寫一份起始模板——RICE / WSJF / Impact-Effort / OKR mapping / INVEST / personas + 你自己團隊的 OKR / 策略 bet / tech-debt 區 / glossary TODO 段。冪等，不會覆蓋 |
| `get_plan_context` | 讀 `plan-knowledge.md`（沒有就走 built-in 預設）。可帶 `section` 抓單一段落。session 開頭叫，把方法論 + 詞彙表帶進每個後續打分決定 |

### Self-reinforcement — 長期視角（3）

| Tool | 用途 |
|---|---|
| `get_planning_history` | 過去 N 筆 top-10 RICE 快照的 trend delta（現在 vs ~7d / vs ~30d），秀進出榜的 churn + 平均分數。「我們有沒有在進步？」「是不是同一個 idea 一直卡 top？」 |
| `get_decision_signature` | 慢性模式偵測：**ghost initiative**（>50% snapshot 都在 top-10 但從沒 spec_generated）、**score whiplash**（RICE 在兩次 snapshot 之間擺幅 >50%，資料品質差）、**orphan OKR**（index 有掛的 OKR 但目前 top-10 沒人對應）。「哪些 idea 一直被打飛？」 |
| `get_telemetry` | 彙整 `.mk-plan-master/telemetry.jsonl`（只記 tool 名 + 耗時 + ok flag，**參數值永遠不記**）。秀最常被叫的 tool、error rate、p50 / p95 / p99 latency、dead surface（宣告了但沒被叫過） |

---

## Adapter 狀態

| `PLAN_SOURCE` | 來源 | 狀態 | 認證 |
|---|---|---|---|
| `markdown_local` | 本地 `initiatives/*.md`，frontmatter 帶 metadata | v0.1.0 ship | 不用 |
| `linear` | Linear API（GraphQL），過 triage / backlog / unstarted | v0.1.0 ship | `LINEAR_API_KEY` + `PLAN_PROJECT_KEY=<團隊代碼>`（選填） |
| `jira` | JIRA Cloud（REST v3、ADF → markdown），過 `statusCategory='To Do'` | v0.1.0 ship | `JIRA_BASE_URL` + `JIRA_EMAIL` + `JIRA_API_TOKEN` + `PLAN_PROJECT_KEY=<專案 key>`（選填） |
| `notion` | Notion database（REST v1、blocks → markdown），過 Status in (Triage / Backlog / Idea) | v0.1.0 ship | `NOTION_TOKEN` + `PLAN_PROJECT_KEY=<database-id>` |

---

## 為什麼要有 `analyze_initiative`——一個真實案例

這就是差異點。AI client 預設會 shortcut——拿到一個 idea 就掃個兩段、隨手填出 Reach / Impact / Confidence / Effort，輸出一個看起來信心滿滿但其實是雜訊的 RICE 分數。下面的數字都是 `mk-plan-test/` 真實 dogfood——**同一個 URL、同一個 idea、跑兩次**。

**Pass 1 — 沒跑 `analyze_initiative`**（AI 直接讀 URL 隨便填）：

```
IDEA-001  ·  一鍵式 IP 授權平台（AI + 區塊鏈）
  reach        500
  impact         2
  confidence   0.5
  effort        12  person-weeks
  out_of_scope  []  （無）
  RICE         (500 × 2 × 0.5) / 12  =  41.7   →   P0
```

信心滿滿的 P0。看起來「下一季直接做」。

**Pass 2 — 跑了 `analyze_initiative`**（AI 被逼跑完資深 PM SOP）：

```
IDEA-002  ·  RightClick — 一鍵式 IP 授權平台（AI + 區塊鏈）
  reach        250                    ←  scope 縮到「初期地區（新加坡 + 美西
                                          社群）每季活躍上架/詢價用戶」，
                                          不是 raw addressable market
  impact         2                    ←  不變
  confidence   0.4                    ←  下調：logo 牆無法驗證、AI 合約法律
                                          未驗、雙邊冷啟動未證明、無 GMV
  effort        18  person-weeks      ←  上調：錢包 3w + AI 模板 4w +
                                          合約/NFT 3w + 市場頁 3w +
                                          律師審查 + 安全 3w +
                                          後台/觀測 2w
  out_of_scope  8 項明確列出          ←  法幣支付、跨鏈、衍生作品自動分潤、
                                          多司法管轄客製化、DRM、PRO-style
                                          集管、影音動態、企業 SSO
  RICE         (250 × 2 × 0.4) / 18  =  11.1   →   P1
```

**差異** — 同一個 URL、同一個 idea，誠實程度差一個數量級：

| 欄位 | Pass 1（菜鳥 PM） | Pass 2（資深 PM SOP） | 變化 |
|---|---:|---:|---|
| reach | 500 | 250 | scope 收斂 |
| confidence | 0.5 | 0.4 | 下調——logo washing、AI 合約法律風險浮上來 |
| effort | 12 pw | 18 pw | +6 pw 把律師審查 + 安全測試補進去 |
| out_of_scope | 0 項 | 8 項 | MVP 邊界明確劃出來 |
| **RICE** | **41.7** | **11.1** | **3.8 倍下殺** |
| **tier** | **P0** | **P1** | 直接降一級 |

P0 → P1 就是「下一季 ship」跟「先驗證」的差別。`analyze_initiative` 是那套 SOP，沒資深 PM 在現場也能跑——同樣的 idea、同樣的 source URL，嚴謹度不一樣。

兩份 initiative 一字不改放在 [`mk-plan-test/initiatives/`](https://github.com/kao273183/mk-plan-test)，兩份 spec 草稿放在 `mk-plan-test/specs/`，完整決策軌跡在 `.mk-plan-master/index.json`——每一筆 `scored` / `spec_generated` 都有時戳。prompt + 工具鏈完整 walkthrough 見 [`docs/walkthrough.md`](docs/walkthrough.md)。

---

## 4 種常用 prompt

四個自然語句 pattern 涵蓋 ~90% 真實情境。每個都只是一句話交給 AI client，工具會自動串。

### 1. 鎖一個 idea — URL → spec_draft

> 「我剛看 https://rightclickip.xyz/，幫我用 mk-plan-master 抓下來、跑 analyze_initiative、算分數，最後生 detailed spec 草稿給 mk-spec-master。」

串：`add_initiative`（從你 chat 摘要寫進來，家族不爬 URL）→ `analyze_initiative` → `add_initiative(overwrite=true)`（寫回充實版 body）→ `score_initiative` → `generate_spec_draft(template="detailed")` → `mk-spec-master.parse_spec(raw_text=...)`。

### 2. 每週 Monday 重新排——看 trend

> 「每週一幫我把 Linear triage backlog 跑一次 RICE 排序，再對比上週、上個月的趨勢。」

串：`rank_backlog(method="rice", limit=10)` → `get_planning_history(window_days=30)`。前者自動 archive snapshot，後者讀全部 snapshot 算 delta。

### 3. 對指定 idea 套資深 PM SOP

> 「對 IDEA-014 套一輪資深 PM 分析 SOP——target users、competition、market signal、risks、MVP scope、out-of-scope、RICE rationale，全部跑完我才打分。」

串：`get_plan_context`（載方法論 + glossary）→ `fetch_initiative("IDEA-014")` → `analyze_initiative("IDEA-014", framework="default")` → AI 在 response 裡把 checklist 填完 → `add_initiative(overwrite=true)` → `score_initiative`。

### 4. 從 Notion 拉全部 triage、出季度 roadmap

> 「把 Notion 上 Triage view 全部拉出來、跑 RICE、再用 4 個工程師 + 20% buffer 包成 Q3 2026 roadmap。順便告訴我 feature / tech-debt / strategic 比例健不健康。」

串：`list_initiatives(status="triage")` → `rank_backlog` → `generate_roadmap(capacity_engineer_months=12, period="Q3 2026", buffer_pct=20)` → `analyze_roadmap_balance`。

---

## 自我強化層

`get_planning_history` + `get_decision_signature` + `get_telemetry` 三劍客，讓 mk-plan-master **量測自己的決策品質**。這套是 mk-spec-master v0.4 已經驗證過的 pattern，套到上游一段。

| 層 | 回答的問題 | 儲存位置 |
|---|---|---|
| **History** | 「有沒有在進步？」「是不是同一個 idea 一直卡頂端？」 | `.mk-plan-master/history/<ts>.json`——每次 `rank_backlog` 自動 archive，5 分鐘 debounce |
| **Decision signature** | 「哪些 idea 一直被打飛（ghost）？」「哪些分數一直在跳（whiplash）？」「哪些 OKR 沒人做（orphan）？」 | 從 history + `index.json` 算出來 |
| **Telemetry** | 「AI 實際在用哪些 tool？」「哪個 tool 慢？」「哪個 tool 從沒被叫（dead surface）？」 | `.mk-plan-master/telemetry.jsonl`——append-only，只記 name + duration + ok flag，**參數值永遠不記** |

shape 跟 mk-spec-master 的 `get_spec_history` / `get_drift_signature` / `get_telemetry` 一致，已經用過那套就不會卡。

每個 initiative 上 `decisions[]` 那一條 audit trail（「為什麼上一季我們不做這個？」），就是用來治**同樣的 idea 下季又跳回來**這個老問題的。不用再「我們三月不是討論過？」——三月的 RICE breakdown、confidence 多少、effort 多少，全部在 index 裡。

---

## 為什麼生態圈缺這一塊

| 既有方案 | 鎖住的點 | 我們不同 |
|---|---|---|
| Productboard | $20-50/user/月，walled garden | MCP-native、住在 AI session 裡，不另開後台。直接讀你既有的 Linear / JIRA / Notion，不用搬資料 |
| Aha! | $59-149/user/月，鎖大企業 | 開源 baseline，鎖定 SMB / 獨立開發者 / AI-native |
| Linear / JIRA | 只有 backlog UI，沒有 triage 框架、沒有 plan→spec 橋 | 我們在上面補打分 + roadmap + spec-bridge 三層 |
| Cursor / Claude「叫 AI 來 plan」 | free-form chat、零持久化 | 結構化輸出、JSON index、決策可追、snapshot 歷史 |
| AWS Kiro plan phase | 鎖 AWS IDE、閉源 | MCP-native、跨 client |
| GitHub Spec Kit | spec-first，不碰上游 idea 整理 | 我們補的是 pre-spec 那段，互補 |

完整定位表見 [`docs/prd.md` §4](docs/prd.md)。

---

## 開發進度

| 里程碑 | 範圍 | 狀態 |
|---|---|---|
| **v0.1**（4 adapter、15 tools、RICE + Impact-Effort、generate_spec_draft、plan-knowledge、自我強化） | 本次 release | Shipped |
| v0.2（Productboard adapter、`cluster_feedback`、WSJF method） | +1 週 | 規劃中 |
| v0.3（Intercom / Zendesk adapter、`compare_competitors`、`link_initiative_to_okr`） | +2 週 | 規劃中 |
| v1.0（production-ready、文件、整合範例、blog 系列） | 2026 Q3 | 規劃中 |

77 個測試在 Python 3.10 / 3.11 / 3.12 / 3.13 通過。

---

## 家族

- [`mk-spec-master`](https://github.com/kao273183/mk-spec-master) — AI 規格大師。spec → scenarios → 覆蓋矩陣。`generate_spec_draft` 輸出**故意**對齊它的 `parse_spec(raw_text=...)`，可直接餵。
- [`mk-qa-master`](https://github.com/kao273183/mk-qa-master) — AI 測試大師。scenarios → 可跑測試，pytest / Jest / Cypress / Go test / Maestro。

家族迴圈：**mk-plan-master → mk-spec-master → 你的 IDE → mk-qa-master → 回到 mk-spec-master 覆蓋矩陣**。

---

## License

MIT © 2026 Jack Kao — 英文原版（具法律效力）見 [`LICENSE`](LICENSE)。

**白話版：** 個人用、商用、改寫、再散布都可以，**唯一要求是保留 copyright 跟授權聲明在你的 copy 裡**。**不附保證**：上 production 出事自負，不能反過來告作者。

開發者 [Jack Kao](https://github.com/kao273183) @ 宸鈞數位。`mk-*` 家族成員：`mk-qa-master` + `mk-spec-master` + `mk-plan-master`。

如果這專案幫到你，[請我喝杯咖啡](https://www.buymeacoffee.com/minikao)。
