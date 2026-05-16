"""Test config — set env vars before mk_plan_master imports anywhere.

Points PLAN_PROJECT_ROOT at a temp directory seeded with three sample
initiatives (LIN-001 / LIN-002 / LIN-003) so the markdown_local adapter
has a known corpus. Done as an autouse fixture so tests don't have to
opt in.
"""

import importlib
import os
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLES = REPO_ROOT / "examples" / "sample_initiatives"

os.environ.setdefault("PLAN_SOURCE", "markdown_local")

# Make src/ importable without `pip install -e .` for local quick runs.
sys.path.insert(0, str(REPO_ROOT / "src"))


@pytest.fixture(autouse=True)
def _temp_project_root(tmp_path, monkeypatch):
    """Copy the sample initiatives into a fresh tmp dir per test and point
    PLAN_PROJECT_ROOT + the already-imported config module at it.

    Reload of config + markdown_local module-level paths matters because
    INITIATIVES_DIR is evaluated at import time.
    """

    initiatives_dir = tmp_path / "initiatives"
    initiatives_dir.mkdir()
    for src_file in SAMPLES.glob("*.md"):
        shutil.copy(src_file, initiatives_dir / src_file.name)

    monkeypatch.setenv("PLAN_PROJECT_ROOT", str(tmp_path))

    from mk_plan_master import config as cfg

    index_dir = (tmp_path / ".mk-plan-master").resolve()
    monkeypatch.setattr(cfg, "PROJECT_ROOT", tmp_path.resolve())
    monkeypatch.setattr(cfg, "INITIATIVES_DIR", initiatives_dir.resolve())
    monkeypatch.setattr(cfg, "INDEX_DIR", index_dir)
    monkeypatch.setattr(cfg, "INDEX_PATH", index_dir / "index.json")
    monkeypatch.setattr(cfg, "HISTORY_DIR", index_dir / "history")
    monkeypatch.setattr(cfg, "TELEMETRY_PATH", index_dir / "telemetry.jsonl")
    monkeypatch.setattr(cfg, "KNOWLEDGE_FILE", (tmp_path / "plan-knowledge.md").resolve())
    # Disable the 5-minute snapshot debounce so multiple rank_backlog calls in
    # the same test actually persist history.
    monkeypatch.setattr(cfg, "HISTORY_DEBOUNCE_SECONDS", 0)

    # markdown_local captured INITIATIVES_DIR at import — patch the reference
    # there too so the adapter sees the new path.
    from mk_plan_master.adapters import markdown_local as ml

    monkeypatch.setattr(ml, "INITIATIVES_DIR", initiatives_dir.resolve())

    yield
