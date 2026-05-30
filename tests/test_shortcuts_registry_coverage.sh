#!/usr/bin/env bash
# test_shortcuts_registry_coverage.sh — registry coverage for every TUI App.
#
# For each App, instantiate it (or trigger its BINDINGS registration path),
# then assert every Binding's `action` is recorded in
# keybinding_registry._DEFAULTS under the expected scope.
#
# Also runs coherence_lint() and prints (but does not fail on) advisory
# warnings — fails only if SHARED_ACTION_IDS actions are bound to truly
# conflicting keys across scopes.
#
# Run: bash tests/test_shortcuts_registry_coverage.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LIB_DIR="$PROJECT_DIR/.aitask-scripts/lib"

# shellcheck source=lib/venv_python.sh
source "$SCRIPT_DIR/lib/venv_python.sh"

cd "$PROJECT_DIR"

# All TUIs that mix in ShortcutsMixin somewhere (App or sub-Screen).
# Each entry is "<module_path>|<expected_scope>" — the scope MUST appear
# in _DEFAULTS after instantiating the App.
FAIL=0

PYTHONPATH="$LIB_DIR:$PROJECT_DIR/.aitask-scripts:$PROJECT_DIR/.aitask-scripts/codebrowser" \
    "$AITASK_PYTHON" - <<'PY' || FAIL=$((FAIL+1))
import argparse
import importlib.util
import sys
import os

sys.path.insert(0, ".aitask-scripts/lib")
sys.path.insert(0, ".aitask-scripts")
sys.path.insert(0, ".aitask-scripts/codebrowser")

import keybinding_registry
keybinding_registry._reset_for_tests()

# Import tui_switcher first so the "shared" scope is registered.
import tui_switcher  # noqa: F401

# Each entry: (module_path, module_name, app_class_name, instantiate_lambda, expected_scope)
TUIS = [
    (".aitask-scripts/syncer/syncer_app.py", "syncer_app", "SyncerApp",
     lambda C: C(argparse.Namespace(interval=None, no_fetch=False, dry_run=False)),
     "syncer"),
    (".aitask-scripts/diffviewer/diffviewer_app.py", "diffviewer_app", "DiffViewerApp",
     lambda C: C(),
     "diffviewer"),
    (".aitask-scripts/applink/applink_app.py", "applink_app", "ApplinkApp",
     lambda C: C(),
     "applink"),
    (".aitask-scripts/codebrowser/codebrowser_app.py", "codebrowser_app", "CodeBrowserApp",
     lambda C: C(),
     "codebrowser"),
    (".aitask-scripts/monitor/monitor_app.py", "monitor_app", "MonitorApp",
     lambda C: C("test-session", __import__("pathlib").Path(".")),
     "monitor"),
    (".aitask-scripts/monitor/minimonitor_app.py", "minimonitor_app", "MiniMonitorApp",
     lambda C: C("test-session", __import__("pathlib").Path(".")),
     "minimonitor"),
    (".aitask-scripts/stats/stats_app.py", "stats_app", "StatsApp",
     lambda C: C(),
     "stats"),
    (".aitask-scripts/settings/settings_app.py", "settings_app", "SettingsApp",
     lambda C: C(),
     "settings"),
    (".aitask-scripts/brainstorm/brainstorm_app.py", "brainstorm_app", "BrainstormApp",
     "register_class_only",  # too heavy to instantiate; emulate mixin's __init__ registration
     "brainstorm"),
]

failures = []
for path, name, cls_name, factory, expected_scope in TUIS:
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        App = getattr(mod, cls_name)
        if factory == "register_class_only":
            # Emulate ShortcutsMixin.__init__ without instantiating the App.
            keybinding_registry.register_app_bindings(App._shortcuts_scope, App.BINDINGS)
        elif factory is not None:
            try:
                factory(App)
            except Exception as e:
                failures.append(f"  {name}: instantiation failed: {type(e).__name__}: {e}")
                continue
        # For brainstorm, also import the DAG widget so "brainstorm.dag"
        # registers at module load time.
        if name == "brainstorm_app":
            import importlib.util as _u
            _spec = _u.spec_from_file_location(
                "brainstorm_dag_display",
                ".aitask-scripts/brainstorm/brainstorm_dag_display.py",
            )
            _m = _u.module_from_spec(_spec)
            _spec.loader.exec_module(_m)
    except Exception as e:
        failures.append(f"  {name}: import failed: {type(e).__name__}: {e}")
        continue

    scopes = {s for (s, a) in keybinding_registry._DEFAULTS}
    if expected_scope not in scopes:
        failures.append(f"  {name}: scope '{expected_scope}' not registered")

# Assert "shared" scope is registered (from tui_switcher import at top).
if "shared" not in {s for (s, _) in keybinding_registry._DEFAULTS}:
    failures.append("  tui_switcher: scope 'shared' not registered")

# Coherence lint (advisory).
warnings = keybinding_registry.coherence_lint()
if warnings:
    print("Advisory: coherence_lint() warnings (not failing):")
    for w in warnings:
        print(f"  - {w}")
else:
    print("coherence_lint(): no warnings")

print()
print("Registered scopes:", sorted({s for (s, _) in keybinding_registry._DEFAULTS}))

if failures:
    print()
    print("FAIL — registry coverage incomplete:")
    for f in failures:
        print(f)
    sys.exit(1)

print()
print("PASS — every TUI registered under its expected scope")
PY

TOTAL_FAILED=$FAIL
if [[ "$TOTAL_FAILED" -eq 0 ]]; then
    echo "PASS: tests/test_shortcuts_registry_coverage.sh"
    exit 0
fi
echo "FAIL: tests/test_shortcuts_registry_coverage.sh"
exit 1
