"""Env-var-driven config. Mirrors mk-spec-master's pattern."""

from pathlib import Path
import os

PROJECT_ROOT = Path(os.getenv("PLAN_PROJECT_ROOT", "./plan_project")).resolve()

SOURCE_NAME = os.getenv("PLAN_SOURCE", "markdown_local").lower()

# Source-specific key. For Linear this is a team id; for JIRA a project key;
# for Notion a database id; for markdown_local it is ignored.
SOURCE_KEY = os.getenv("PLAN_PROJECT_KEY", "")

# Adapter auth tokens. Phase 1 only the markdown_local adapter uses none.
LINEAR_API_KEY = os.getenv("LINEAR_API_KEY", "")

# JIRA auth (Phase 3). Atlassian Cloud uses Basic auth with email + API token.
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "")
JIRA_EMAIL = os.getenv("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "")

# Notion auth (Phase 3). Internal-integration token from
# https://www.notion.so/my-integrations.
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")

# Local index for decisions / roadmap snapshots. One JSON file under
# PROJECT_ROOT keeps everything; data ownership stays with the user.
INDEX_DIR = PROJECT_ROOT / ".mk-plan-master"
INDEX_PATH = INDEX_DIR / "index.json"

# Self-reinforcement storage:
# - HISTORY_DIR holds one JSON snapshot per rank_backlog call so trend tools
#   can compare "now" vs "last quarter".
# - TELEMETRY_PATH is a JSONL append-only log of tool invocations so
#   get_telemetry can surface usage / error patterns.
HISTORY_DIR = INDEX_DIR / "history"
TELEMETRY_PATH = INDEX_DIR / "telemetry.jsonl"

# Knowledge file holding RICE / WSJF / OKR / INVEST methodology + project
# glossary. Default location keeps it visible at the project root; override
# for monorepos where the planning lives in a sub-folder.
KNOWLEDGE_FILE = Path(
    os.getenv("PLAN_KNOWLEDGE_FILE") or (PROJECT_ROOT / "plan-knowledge.md")
).resolve()

# Where local markdown initiatives live (markdown_local adapter only).
INITIATIVES_DIR = PROJECT_ROOT / "initiatives"

# archive_snapshot debounces to avoid hammering history/ during back-to-back
# rank_backlog calls. Tests override to 0 via the env var below.
HISTORY_DEBOUNCE_SECONDS = int(os.getenv("MK_PLAN_HISTORY_DEBOUNCE_SECONDS", "300"))
