#!/usr/bin/env python3
"""Characterization capture of every model-stats reader (t1912_2).

Prints, deterministically, what each reader of `usagestats` / `verifiedstats`
displays for the project at ROOT, with "today" pinned to 2026-11-04:

  1. stats_data rankings  - load_verified_rankings / load_usage_rankings
  2. model picker         - _build_top_all_ops / _build_top_usage /
                            _build_options_for_agent
  3. settings TUI         - _get_verified_label / _get_all_providers_label /
                            _collect_non_default_skill_stats / _populate_models_tab
  4. aitask_codeagent.sh list-models

Run it in a fresh process with cwd = ROOT. Several readers resolve their files
cwd-relatively (MODEL_FILES, METADATA_DIR), and the TASK_DIR / METADATA_DIR
overrides must be unset; tests/test_stats_readers_golden.py does both.

Usage:
  stats_reader_capture.py ROOT                    print the capture
  stats_reader_capture.py ROOT --write PATH       (re)write a golden file
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / ".aitask-scripts"
for sub in ("", "lib", "settings"):
    path = str(SCRIPTS / sub) if sub else str(SCRIPTS)
    if path not in sys.path:
        sys.path.insert(0, path)

TODAY = _dt.date(2026, 11, 4)
AGENTS = ("claudecode", "codex", "opencode")
PICKER_OPS = ("pick", "explore", "batch-review")
LABEL_OPS = ("pick", "explore", "batch-review", "review", "wrap")


class _FixedDate(_dt.date):
    @classmethod
    def today(cls):  # noqa: D401 - matches date.today
        return TODAY


def _pin_today() -> None:
    import model_stats_windows
    model_stats_windows.date = _FixedDate


def _section(out: list, title: str) -> None:
    out.append(f"== {title}")


def _rankings(out: list, root: Path) -> None:
    from stats_data import WINDOW_KEYS, load_usage_rankings, load_verified_rankings

    _section(out, "stats_data.load_verified_rankings")
    data = load_verified_rankings(root, today=TODAY)
    out.append(f"operations={data.operations}")
    for op in sorted(data.by_window):
        for provider in sorted(data.by_window[op]):
            for win in WINDOW_KEYS:
                for e in data.by_window[op][provider].get(win, []):
                    out.append(f"{op}|{provider}|{win}|{e.cli_id}|{e.display_name}"
                               f"|score={e.score}|runs={e.runs}")

    _section(out, "stats_data.load_usage_rankings")
    data = load_usage_rankings(root, today=TODAY)
    out.append(f"operations={data.operations}")
    for op in sorted(data.by_window):
        for provider in sorted(data.by_window[op]):
            for win in WINDOW_KEYS:
                for e in data.by_window[op][provider].get(win, []):
                    out.append(f"{op}|{provider}|{win}|{e.cli_id}|{e.display_name}"
                               f"|runs={e.runs}")


def _picker(out: list, root: Path) -> None:
    from agent_model_picker import AgentModelPickerScreen
    from config_utils import load_all_models

    all_models = load_all_models(root)
    for op in PICKER_OPS:
        screen = AgentModelPickerScreen(op, all_models=all_models, today=TODAY)
        _section(out, f"picker[{op}]._build_top_all_ops")
        for c in screen._build_top_all_ops():
            out.append(json.dumps(c, sort_keys=True))
        _section(out, f"picker[{op}]._build_top_usage")
        for c in screen._build_top_usage():
            out.append(json.dumps(c, sort_keys=True))
        for agent in AGENTS:
            _section(out, f"picker[{op}]._build_options_for_agent({agent})")
            for o in screen._build_options_for_agent(agent):
                out.append(json.dumps(o, sort_keys=True))


class _Rec:
    """Stand-in for Textual's Label / Static: records the text it was given."""

    def __init__(self, text="", classes=None, **_kw):
        self.text = str(text)
        self.classes = classes


class _Container:
    def __init__(self):
        self.mounted: list = []

    def remove_children(self):
        self.mounted.clear()

    def mount(self, widget):
        self.mounted.append(widget)


def _settings(out: list) -> None:
    import settings_app
    from settings_app import ConfigManager, SettingsApp

    mgr = ConfigManager()
    fake = SimpleNamespace(config_mgr=mgr)

    _section(out, "settings._get_verified_label / _get_all_providers_label")
    for agent in sorted(mgr.models):
        for m in mgr.models[agent].get("models", []):
            agent_model = f"{agent}/{m.get('name')}"
            for op in LABEL_OPS:
                v = SettingsApp._get_verified_label(fake, op, agent_model)
                a = SettingsApp._get_all_providers_label(fake, op, agent_model)
                if v or a:
                    out.append(f"{op}|{agent_model}|verified={v!r}|all={a!r}")

    _section(out, "settings._collect_non_default_skill_stats")
    stats = SettingsApp._collect_non_default_skill_stats(fake)
    out.append(json.dumps(stats, sort_keys=True, default=str))

    _section(out, "settings._populate_models_tab")
    container = _Container()
    tab = SimpleNamespace(
        config_mgr=mgr,
        query_one=lambda *_a, **_k: container,
        _tab_switch_hint=lambda: "HINT",
    )
    saved = (settings_app.Static, settings_app.Label)
    settings_app.Static, settings_app.Label = _Rec, _Rec
    try:
        SettingsApp._populate_models_tab(tab)
    finally:
        settings_app.Static, settings_app.Label = saved
    for w in container.mounted:
        out.append(f"[{w.classes}] {w.text}")


def _list_models(out: list, root: Path) -> None:
    script = SCRIPTS / "aitask_codeagent.sh"
    runs = [[agent] for agent in AGENTS] + [["--active-only", "claudecode"]]
    for args in runs:
        _section(out, f"list-models {' '.join(args)}")
        proc = subprocess.run(["bash", str(script), "list-models", *args],
                              cwd=root, capture_output=True, text=True)
        out.append(proc.stdout.rstrip("\n"))
        if proc.returncode != 0 or proc.stderr.strip():
            out.append(f"exit={proc.returncode} stderr={proc.stderr.strip()!r}")


def capture(root) -> str:
    root = Path(root).resolve()
    if Path.cwd().resolve() != root:
        raise SystemExit(f"run with cwd = ROOT ({root}), not {Path.cwd()}")
    for var in ("TASK_DIR", "METADATA_DIR"):
        if var in os.environ:
            raise SystemExit(f"{var} must be unset for a capture")
    _pin_today()
    out: list = []
    _rankings(out, root)
    _picker(out, root)
    _settings(out)
    _list_models(out, root)
    return "\n".join(out) + "\n"


def main(argv) -> int:
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    text = capture(argv[0])
    if len(argv) == 3 and argv[1] == "--write":
        Path(argv[2]).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
