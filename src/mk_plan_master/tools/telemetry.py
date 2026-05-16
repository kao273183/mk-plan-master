"""Tool-usage telemetry for v0.1 self-reinforcement.

Every call_tool dispatch in server.py writes one JSONL line. get_telemetry
aggregates by tool to surface usage / error patterns: which tools get called
often, which fail often, which never get called.

Storage: <TELEMETRY_PATH> — append-only JSONL. One line = one tool call.
Schema: {ts, tool, ok, duration_ms, error?}.

Privacy: argument values are NEVER logged. Only the tool name + outcome.
"""

import datetime as _dt
import json
import time
from typing import Any

from .. import config


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log_tool_call(tool: str, duration_ms: int, error: str | None = None) -> None:
    """Append a single record. Swallows storage errors so telemetry can never
    crash a tool call."""
    try:
        config.INDEX_DIR.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": _now_iso(),
            "tool": tool,
            "ok": error is None,
            "duration_ms": duration_ms,
        }
        if error:
            record["error"] = error[:200]
        with config.TELEMETRY_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


class _Timer:
    """Tiny context manager so server.py can wrap dispatch cleanly."""

    def __init__(self, tool: str):
        self.tool = tool
        self.error: str | None = None
        self._start = 0.0

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb):
        duration_ms = int((time.perf_counter() - self._start) * 1000)
        if exc is not None:
            self.error = f"{exc_type.__name__}: {exc}"
        log_tool_call(self.tool, duration_ms, self.error)
        return False  # never swallow exceptions


def _percentile(sorted_values: list[int], pct: float) -> int:
    if not sorted_values:
        return 0
    n = len(sorted_values)
    idx = min(n - 1, int(n * pct))
    return sorted_values[idx]


def get_telemetry_tool(arguments: dict) -> dict[str, Any]:
    """Aggregate telemetry.jsonl by tool. Returns counts, error rate,
    p50 / p95 / p99 latency, plus tools that have never been called in
    the window.

    Args:
        window_days: int, default 7.
    """
    window_days = int(arguments.get("window_days", 7))

    if not config.TELEMETRY_PATH.exists():
        return {
            "calls_total": 0,
            "calls_by_tool": {},
            "error_rate_pct": 0.0,
            "p50_ms": 0,
            "p95_ms": 0,
            "p99_ms": 0,
            "top_tools": [],
            "dead_tools": [],
        }

    cutoff = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=window_days)
    records: list[dict] = []
    try:
        for line in config.TELEMETRY_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            try:
                ts = _dt.datetime.strptime(rec["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.timezone.utc)
            except (KeyError, ValueError):
                continue
            if ts >= cutoff:
                records.append(rec)
    except OSError:
        return {
            "calls_total": 0,
            "calls_by_tool": {},
            "error_rate_pct": 0.0,
            "p50_ms": 0,
            "p95_ms": 0,
            "p99_ms": 0,
            "top_tools": [],
            "dead_tools": [],
        }

    by_tool: dict[str, dict[str, Any]] = {}
    durations_all: list[int] = []
    error_count = 0
    for r in records:
        t = r.get("tool", "?")
        bucket = by_tool.setdefault(t, {"calls": 0, "errors": 0, "durations": []})
        bucket["calls"] += 1
        ok = r.get("ok", True)
        if not ok:
            bucket["errors"] += 1
            error_count += 1
        dur = int(r.get("duration_ms", 0))
        bucket["durations"].append(dur)
        durations_all.append(dur)

    calls_by_tool = {t: b["calls"] for t, b in by_tool.items()}

    top_tools = []
    for t, b in by_tool.items():
        err_rate = (b["errors"] / b["calls"] * 100) if b["calls"] else 0.0
        top_tools.append(
            {
                "name": t,
                "calls": b["calls"],
                "error_rate_pct": round(err_rate, 1),
            }
        )
    top_tools.sort(key=lambda r: -r["calls"])

    durations_all.sort()
    p50 = _percentile(durations_all, 0.50)
    p95 = _percentile(durations_all, 0.95)
    p99 = _percentile(durations_all, 0.99)

    error_rate = (error_count / len(records) * 100) if records else 0.0

    dead_tools: list[str] = []
    try:
        from ..server import _DISPATCH
        seen = set(by_tool)
        dead_tools = sorted(t for t in _DISPATCH if t not in seen)
    except Exception:
        dead_tools = []

    return {
        "calls_total": len(records),
        "calls_by_tool": calls_by_tool,
        "error_rate_pct": round(error_rate, 1),
        "p50_ms": p50,
        "p95_ms": p95,
        "p99_ms": p99,
        "top_tools": top_tools,
        "dead_tools": dead_tools,
        "window_days": window_days,
    }
