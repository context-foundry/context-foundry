#!/usr/bin/env python3
"""Render a Foundry headless json-stream into a Markdown PR/check report.

Usage:
    foundry-ci-report.py <stream.jsonl>

Reads the JSONL event stream produced by
`foundry run --no-tui --output-format json-stream`, extracts the terminal
SessionReport (the final object carrying both `session` and `tasks`), and writes
a Markdown summary to stdout. Used for the PR body and the GitHub step summary.
Degrades gracefully when the report is missing or the stream is truncated.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_STATUS_LABELS = {"pass": "PASS", "feat": "PASS", "wip": "WIP", "fail": "FAIL"}


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def find_report(lines: list[str]) -> dict[str, Any] | None:
    """Return the last JSONL line that looks like a terminal SessionReport."""
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "session" in obj and "tasks" in obj:
            return obj
    return None


def status_label(status: str) -> str:
    return _STATUS_LABELS.get(status.lower(), status or "?")


def outcome(report: dict[str, Any]) -> tuple[str, str]:
    """Return (display_status, GitHub check conclusion)."""
    session: dict[str, Any] = report.get("session", {})
    feat = _int(session.get("feat_commits"))
    wip = _int(session.get("wip_commits"))
    if report.get("typed_error"):
        return ("FAIL", "failure")
    if wip == 0 and feat > 0:
        return ("PASS", "success")
    return ("WIP", "neutral")


def render(report: dict[str, Any]) -> str:
    session: dict[str, Any] = report.get("session", {})
    tasks: list[dict[str, Any]] = report.get("tasks", [])
    cfg: dict[str, Any] = report.get("config", {})
    feat = _int(session.get("feat_commits"))
    wip = _int(session.get("wip_commits"))
    cost = _float(report.get("cost_usd"))
    duration = _float(session.get("total_duration_secs"))
    overall, _conclusion = outcome(report)

    out: list[str] = [
        f"## Foundry build: {overall}",
        "",
        f"- Tasks: {len(tasks)} (feat {feat} / wip {wip})",
        f"- Cost: ${cost:.2f} | Duration: {duration:.0f}s",
        f"- Run mode: {cfg.get('run_mode', '?')} | "
        f"builder {cfg.get('builder_provider', '?')}:{cfg.get('builder_model', '?')}",
    ]
    typed_error = report.get("typed_error")
    if typed_error:
        out.append(f"- Typed error: `{json.dumps(typed_error)}`")
    out.append("")

    if tasks:
        out.append("| Task | Status | H/M/L | Commit | Secs |")
        out.append("|------|--------|-------|--------|------|")
        for task in tasks:
            findings: dict[str, Any] = task.get("findings", {})
            sha = (task.get("commit_sha") or "")[:8] or "-"
            out.append(
                f"| {task.get('id', '?')} "
                f"| {status_label(task.get('status', ''))} "
                f"| {findings.get('high', 0)}/{findings.get('medium', 0)}/{findings.get('low', 0)} "
                f"| `{sha}` "
                f"| {_float(task.get('duration_secs')):.0f} |"
            )
        out.append("")

    out.append("_Automated by `foundry run` (ci profile)._")
    return "\n".join(out)


def load_report(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, "Stream file not found."
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    report = find_report(lines)
    if report is None:
        return None, "No terminal SessionReport found in the event stream."
    return report, None


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print(
            "usage: foundry-ci-report.py [--status|--conclusion|--title] <stream.jsonl>",
            file=sys.stderr,
        )
        return 2

    mode = "render"
    path_arg = sys.argv[1]
    if len(sys.argv) == 3:
        mode = sys.argv[1]
        path_arg = sys.argv[2]
        if mode not in {"--status", "--conclusion", "--title"}:
            print(f"unknown option: {mode}", file=sys.stderr)
            return 2

    path = Path(path_arg)
    report, missing_reason = load_report(path)
    if report is None:
        if mode == "--status":
            print("FAIL")
            return 0
        if mode == "--conclusion":
            print("failure")
            return 0
        if mode == "--title":
            print("Foundry build: incomplete")
            return 0
        print(
            "## Foundry build: incomplete\n\n"
            f"{missing_reason}"
        )
        return 0
    status, conclusion = outcome(report)
    if mode == "--status":
        print(status)
        return 0
    if mode == "--conclusion":
        print(conclusion)
        return 0
    if mode == "--title":
        print(f"Foundry build: {status}")
        return 0
    print(render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
