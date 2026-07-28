---
Task: t1235_repay_lib_stats_inversion.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1235 — Repay the last `lib/` → TUI layer inversion (`stats_data`)

## Context

t1217 promoted `board/task_yaml.py` into the base layer (`lib/`) and added
`tests/test_no_lib_to_tui_import.sh`, which freezes the layer direction: **no
`lib/` module may put a sibling TUI package on `sys.path`**. One reach was
deliberately left standing and allowlisted with its reason:

```bash
"work_report_gather.py:stats" # KNOWN remaining inversion: reuses stats_data's
                              # collect_stats/DAY_NAMES. Out of scope for
                              # t1217; repaying it empties this allowlist.
```

`.aitask-scripts/lib/work_report_gather.py:50-54` inserts `.aitask-scripts/stats`
into `sys.path` solely to satisfy `from stats_data import DAY_NAMES, collect_stats`
(line 57). t1235 is the registered risk-mitigation follow-up that repays it, so the
allowlist holds only the `shortcut_scopes.py:*` reflection-loader entry.

**Outcome:** `lib/` depends on nothing above it; the guard's allowlist shrinks to
one entry; moving or renaming a stats TUI file can no longer break the
work-report helper.

## Approach — promote `stats_data.py` into `lib/` (wholesale move, no shim)

`stats/stats_data.py` is already a base-layer module misfiled in a TUI package:
its own docstring calls it *"Pure data extraction layer … No rendering, no
plotext"*, it imports **no** textual/plotext/rich, and its only non-stdlib
dependencies are three `lib/` modules (`archive_iter`, `config_utils`,
`gate_ledger`). It is exactly the t1217 shape — a strictly-downward module
sitting one layer too high for historical reasons.

Move it wholesale and rewrite every importer to the bare-name form, exactly as
t1217 did (`git mv`, docstring restated, nothing left behind).

**Rejected alternatives**

- *Extract only `DAY_NAMES` + `collect_stats` into a new `lib/` module.*
  `collect_stats`'s dependency closure is most of the file (`StatsData`,
  `TaskRecord`, `PhaseTimings`, `InflightData`, `_paths_for`,
  `resolve_completion_date`, `parse_frontmatter`, `parse_labels`,
  `normalize_implemented_with`, `is_child_task`, `week_*`, the ledger helpers,
  the archive-iteration path). Only the ~330-line model-ranking block
  (`:359-823`) and `merge_stats_data` are genuinely stats-only. Splitting there
  creates two seams where there is one and yields a *larger* diff than the move.
- *Move to `lib/` and leave a `stats/stats_data.py` re-export shim.* Smallest
  diff, but it gives one module two import identities (`stats.stats_data` and
  `stats_data`) — and `tests/test_stats_multistage.py` registers
  `sys.modules["stats_data"]` while `tests/test_aitask_stats_py.py` monkeypatches
  `TASK_DIR`/`ARCHIVE_DIR` on the module object. A dual identity silently splits
  those patches. t1217 set no shim precedent; its guard asserts the old path is
  *gone*.

### Import style

Bare (`from stats_data import …`), matching `task_yaml` after t1217 — not
`from lib.stats_data import …`. Bare keeps a single module object and matches
what every other `lib/` consumer already does.

## Changes

### 1. The move — `.aitask-scripts/stats/stats_data.py` → `.aitask-scripts/lib/stats_data.py`

```bash
git mv .aitask-scripts/stats/stats_data.py .aitask-scripts/lib/stats_data.py
```

- Replace the `lib/`-reaching bootstrap at `:19-23` with the lib-internal form
  used by `lib/trail_gather.py:121-125` (still needed: when the module is
  path-loaded by a test its own directory is not automatically on `sys.path`):

  ```python
  # Make lib/ importable however this module is loaded (path-loaded by a test,
  # or imported bare with lib/ on sys.path). Every module imported below now
  # lives beside this one — it reaches into no sibling package.
  _LIB_DIR = os.path.dirname(os.path.abspath(__file__))
  if _LIB_DIR not in sys.path:
      sys.path.insert(0, _LIB_DIR)
  ```

- Restate the docstring in the t1217 idiom: base-layer module, consumed by the
  stats CLI, the stats TUI **and** `work_report_gather`; it lived under `stats/`
  for historical reasons only; `tests/test_no_lib_to_tui_import.sh` freezes the
  direction (t1235).
- Add a one-line note on `parse_frontmatter` (`:242`) that it is the lightweight
  string-map parser and is **not** `task_yaml.parse_frontmatter` (the YAML-backed
  one) — the two are now co-located in `lib/`.

### 2. `.aitask-scripts/lib/work_report_gather.py` — drop the insert (the acceptance change)

Delete the whole bootstrap block at `:44-54` (`_SCRIPTS_DIR` becomes unused).
`from stats_data import DAY_NAMES, collect_stats` at `:57` stays as-is and now
resolves within `lib/`. Rewrite the surrounding comment to record that the
inversion is repaid.

### 3. Production importers — `from stats.stats_data import …` → `from stats_data import …`

| File | Note |
|---|---|
| `.aitask-scripts/aitask_stats.py:25-71` (47 symbols, re-exported via `__all__`) | also add `lib/` to its `sys.path` bootstrap at `:18` |
| `.aitask-scripts/stats/stats_app.py:54-59` | `lib/` is already on `sys.path` — `from lib.tui_switcher import …` at `:35` runs first |
| `.aitask-scripts/stats/panes/overview.py:9` | `DAY_NAMES, StatsData, build_chart_title` |
| `.aitask-scripts/stats/panes/labels.py:7` | `StatsData, build_chart_title, get_valid_task_types` |
| `.aitask-scripts/stats/panes/agents.py:7` | multi-line import block |
| `.aitask-scripts/stats/panes/velocity.py:8` | `StatsData, build_chart_title` |
| `.aitask-scripts/stats/panes/sessions.py:6` | `StatsData` |
| `.aitask-scripts/stats/panes/pipeline.py:14` | `StatsData, build_chart_title, format_duration` |
| `.aitask-scripts/stats/panes/base.py:17` | inside `if TYPE_CHECKING:` |

**All six pane modules must be migrated — none is optional.**
`stats/panes/__init__.py` does `from . import overview, labels, agents, velocity,
sessions, pipeline` at import time, so `stats_app.py`'s
`from stats.panes import PANE_DEFS` eagerly loads every one of them: a single
missed pane is a `ModuleNotFoundError` that stops the stats TUI from starting at
all.

**Make the `stats` package self-bootstrapping.** Today the panes' bare
`from stats_data import …` would resolve only because `stats_app.py:35` imports
`lib.tui_switcher` (which inserts `lib/`) *before* the pane import at `:53`. That
makes every pane's import silently dependent on the ordering inside a different
file, and it breaks any consumer that imports `stats.panes` directly. Add the
insert to `.aitask-scripts/stats/__init__.py` instead, so importing the package
in any order works:

```python
"""TUI package for ait stats. The data-extraction layer moved to
lib/stats_data.py in t1235; this package holds the TUI only."""
import os
import sys

# Downward dependency: every module in this package reads the base layer.
_LIB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)
```

Cross-check the list is exhaustive before and after the edit:

```bash
grep -rn "stats\.stats_data" --include=*.py --include=*.sh .aitask-scripts/ tests/   # must be empty afterwards
```


### 4. `tests/test_no_lib_to_tui_import.sh` — the acceptance criterion

- **Remove** the `work_report_gather.py:stats` ALLOWLIST entry (`:58-60`) so only
  `shortcut_scopes.py:*` remains, and rewrite the allowlist header prose
  (`:49-53`), which currently explains the stats holdout.
- **Re-point negative control (5)** (`:145-167`). It currently proves per-package
  allowlisting *using the entry being deleted* — its
  `assert_not_contains "allowlisted work_report_gather.py -> stats is not flagged"`
  becomes false the moment the entry goes. Rewrite it against a synthetic entry
  so the per-package semantics stay pinned and keep their discriminating power:
  make `is_allowed` consult an overridable array (default `"${ALLOWLIST[@]}"`),
  set it to a test-only `neg_perpkg.py:stats` for the fixture, and assert the
  same file reaching `board` **is** still flagged.
- **Add the t1235 postcondition** alongside Test 7, in the same shape:

  ```bash
  assert_file_exists "stats_data.py lives in lib/" \
    "$PROJECT_DIR/.aitask-scripts/lib/stats_data.py"
  assert_file_not_exists "stats_data.py no longer lives in stats/" \
    "$PROJECT_DIR/.aitask-scripts/stats/stats_data.py"
  ```

### 5. Test import sites

| File | Change |
|---|---|
| `tests/test_stats_data.sh:29-30, 53-54` | heredoc `sys.path.insert(0, ".aitask-scripts")` → `".aitask-scripts/lib"`; imports bare. Group 3 (`:65-74`) path-loads `aitask_stats.py` and is unaffected. Header comment at `:2` names `stats.stats_data`. |
| `tests/test_stats_verified_rankings.sh:33,61,77,116,140` | same insert + bare-import swap (5 heredocs) |
| `tests/test_aitask_stats_py.py:33-37` | `sys.modules["stats.stats_data"]` → `sys.modules["stats_data"]`; refresh the stale comment naming the dotted module |
| `tests/test_stats_multistage.py:19` | `".aitask-scripts" / "stats" / "stats_data.py"` → `… / "lib" / …` |
| `tests/test_stats_include_registered.py` | no change expected — it path-loads `stats_app.py`, which pulls `stats.panes` and therefore every pane module. This is the automated guard that catches a missed pane import site (incl. `velocity.py`); it must be run, not assumed. |
| `tests/test_work_report_gather.sh` | no change — black-box through the `.sh` wrapper; it is the end-to-end signal that the shipped bootstrap works |

Do **not** touch `tests/run_all_python_tests.sh` — its PYTHONPATH masking is
t1236's subject and that task is currently in flight.

### 6. Docs (current-state rule — paths go stale on the move)

- `website/content/docs/tuis/stats/_index.md:30`
- `aidocs/framework/adding_a_new_codeagent.md:318, 355, 403`
- `aidocs/gates/stats-multistage-completion.md:22, 43, 123, 125, 159`

## Verification

```bash
# Acceptance: the guard passes with the allowlist reduced to one entry
bash tests/test_no_lib_to_tui_import.sh

bash tests/test_work_report_gather.sh      # incl. the board-equivalence oracle
bash tests/test_stats_data.sh
bash tests/test_stats_verified_rankings.sh
bash tests/run_all_python_tests.sh          # covers test_stats_multistage,
                                            # test_stats_include_registered,
                                            # test_aitask_stats_py
```

Direct-invocation checks — the suite runner exports `lib/` on `PYTHONPATH` and
would mask a broken per-file bootstrap:

```bash
source .aitask-scripts/lib/python_resolve.sh; PY="$(require_ait_python)"
env -u PYTHONPATH "$PY" -c "import sys; sys.path.insert(0, '.aitask-scripts/lib'); import work_report_gather"
env -u PYTHONPATH "$PY" -c "import sys; sys.path.insert(0, '.aitask-scripts/lib'); import stats_data"
env -u PYTHONPATH "$PY" -c "import sys; sys.path.insert(0, '.aitask-scripts'); import stats.stats_app"

# Bounded assertion that EVERY pane module imports and registers — the
# non-interactive stand-in for launching the TUI. Both paths are inserted
# explicitly: this bypasses stats_app.py, so nothing else puts lib/ on sys.path.
env -u PYTHONPATH "$PY" -c "
import sys
sys.path.insert(0, '.aitask-scripts')
sys.path.insert(0, '.aitask-scripts/lib')
from stats.panes import PANE_DEFS
import stats.panes as p
mods = ('overview', 'labels', 'agents', 'velocity', 'sessions', 'pipeline')
missing = [m for m in mods if not hasattr(p, m)]
assert not missing, missing
assert PANE_DEFS, 'no panes registered'
print('panes ok:', len(PANE_DEFS))
"

# Proves the stats/__init__.py self-bootstrap: lib/ is deliberately NOT on the
# path here, so this fails unless the package puts it there itself.
env -u PYTHONPATH "$PY" -c "
import sys; sys.path.insert(0, '.aitask-scripts')
from stats.panes import PANE_DEFS
assert PANE_DEFS
"
```

End-to-end, through the real entry points:

```bash
./.aitask-scripts/aitask_work_report_gather.sh --list-columns
./.aitask-scripts/aitask_work_report_gather.sh --columns now --project
./ait stats                     # text report
./ait stats --csv /tmp/s.csv    # CSV export
```

`./ait stats-tui` is **not** an enforceable signal — it blocks on a live
terminal and asserts nothing on its own. The enforceable signals are the test
suite (`tests/test_stats_include_registered.py` in particular) plus the two
import assertions above; actually *launching* the TUI and confirming the panes
draw is manual verification, offered at Step 8c.

**Negative control** (prove the guard still discriminates): temporarily
re-introduce the `for _sub in ("stats",)` insert in `lib/work_report_gather.py`
and confirm `tests/test_no_lib_to_tui_import.sh` **fails** naming
`work_report_gather.py:stats`; then undo the edit by hand (never
`git checkout --`, which would wipe the rest of the working tree).

Step 9 (Post-Implementation) handles merge, gates, and archival.

## Risk

### Code-health risk: medium
- Wide-but-shallow blast radius: one file move plus 9 production import sites
  (the stats CLI, `stats_app.py`, and all 7 files under `stats/panes/`), 4 test
  files and 3 doc files. Each edit is mechanical, but a missed pane is a
  `ModuleNotFoundError` that stops the TUI from starting — `stats/panes/__init__.py`
  imports every pane eagerly ·
  severity: medium · → mitigation: t1305
- After the move `lib/` holds two different functions named `parse_frontmatter`
  (`stats_data`'s lightweight string-map parser and `task_yaml`'s YAML-backed
  one) side by side in one flat, bare-name module directory. They are not
  interchangeable, and nothing prevents a future consumer importing the wrong one ·
  severity: medium · → mitigation: t1304
- `tests/run_all_python_tests.sh` exports `lib/` on `PYTHONPATH`, so a broken
  per-file bootstrap can still pass the suite; the explicit `env -u PYTHONPATH`
  checks above are the only counter-signal (the general fix is t1236, in flight) ·
  severity: low · → mitigation: none (covered by t1236)

### Goal-achievement risk: low
- Negative control (5) of the layering guard is built *on* the allowlist entry
  being deleted. Rewriting it carelessly (or simply dropping it) would leave the
  suite green while quietly removing the proof that allowlisting is per-package —
  the acceptance criterion would read as met with weaker coverage than before ·
  severity: medium · → mitigation: none (handled in-task — see Changes §4)
- The approach is prescribed by the task and precedented by t1217, and the
  acceptance criterion (allowlist reduced to one entry, guard green) is
  mechanically checkable · severity: low

### Planned mitigations
- timing: after | name: t1304 (consolidate_lib_frontmatter_parsers) | type: refactor | priority: medium | effort: low | addresses: code-health — two `parse_frontmatter` functions co-located in lib/ | desc: Rename or consolidate `stats_data.parse_frontmatter` (string-map) vs `task_yaml.parse_frontmatter` (YAML-backed) so the flat lib/ namespace exposes one unambiguous frontmatter parser
- timing: after | name: t1305 (stats_pane_import_regression_test) | type: test | priority: medium | effort: low | addresses: code-health — blast radius across TUI import sites | desc: Add an import-level regression test that path-loads every stats/panes/*.py and stats_app.py with only .aitask-scripts + lib on sys.path, so a missed import site fails a test instead of only at TUI runtime

## Final Implementation Notes

- **Actual work done:** Implemented as planned. `git mv
  .aitask-scripts/stats/stats_data.py .aitask-scripts/lib/stats_data.py` (pure
  rename, no shim), its `lib/`-reaching bootstrap replaced with the self-dir
  form, docstring restated as a base-layer module. `lib/work_report_gather.py`
  lost the whole `for _sub in ("stats",)` `sys.path` block — the acceptance
  change. Nine importers rewritten to bare `from stats_data import …`
  (`aitask_stats.py` + a `lib/` insert, `stats_app.py`, and all 7 files under
  `stats/panes/`). `tests/test_no_lib_to_tui_import.sh`: allowlist reduced to
  `shortcut_scopes.py:*`, negative control (5) re-pointed at a synthetic entry,
  new control (5b), Test 7 extended. Four test files and four doc references
  updated.

- **Deviations from plan:** Two, both from user review of the plan before
  approval and folded into it before implementation:
  1. The first draft's importer table omitted `stats/panes/velocity.py`.
     `stats/panes/__init__.py` imports every pane eagerly, so that omission
     would have been a `ModuleNotFoundError` at TUI startup. The table now names
     all seven pane files explicitly.
  2. The verification section originally listed `./ait stats-tui` as a "smoke"
     signal. It blocks on a live terminal and asserts nothing, so it was
     demoted to manual verification and replaced with two bounded
     `env -u PYTHONPATH` assertions over `stats.panes`.

  A third correction came from the same review: the bounded pane-import command
  initially inserted only `.aitask-scripts`, which cannot resolve the panes' new
  bare `from stats_data import …`. That surfaced a real design weakness rather
  than just a bad test command — the panes were relying on `stats_app.py:35`
  importing `lib.tui_switcher` *before* the pane import at `:53`, i.e. on the
  line ordering inside a different file. Fixed structurally by giving
  `stats/__init__.py` its own `lib/` bootstrap, so `import stats.panes` works
  standalone. A dedicated check (only `.aitask-scripts` on `sys.path`) proves
  the package, not the caller, is what puts `lib/` there.

- **Issues encountered:**
  - A blanket `.aitask-scripts` → `.aitask-scripts/lib` rewrite of the test
    heredocs broke `tests/test_stats_verified_rankings.sh`, whose heredocs also
    import `stats.panes.agents`. Those five heredocs now insert **both** paths;
    `.aitask-scripts/lib` is still required explicitly because the bare
    `from stats_data import` line precedes the first `stats.*` import that would
    trigger the package bootstrap.
  - The first full-suite run reported 4 failures + 4 errors, but the output was
    piped through `tail -30` so the detail was lost. A clean re-run gave
    **2541 tests, 0 failures (1 skipped)**. The earlier failures came from a
    concurrent session's mid-edit working tree (codebrowser / monitor /
    `tui_layout.py`), not from this change.
  - t1236 landed mid-task in the same checkout, replacing the runner's
    `export PYTHONPATH=…board:…lib` with `unset PYTHONPATH`. Every stats test was
    re-run with `PYTHONPATH` unset and passes; the new
    `tests/test_python_bootstrap_isolation.sh` (8/8, sweeping 156 files in
    isolated interpreters) and `tests/test_runner_python_isolation.sh` (9/9) also
    pass with the moved module. `tests/run_all_python_tests.sh` was deliberately
    left untouched — it is t1236's file.

- **Key decisions:**
  - **Wholesale move, not extraction.** `collect_stats`'s dependency closure is
    most of `stats_data.py`; only the ~330-line model-ranking block and
    `merge_stats_data` are stats-only. Splitting there would have produced a
    larger diff and two seams.
  - **No re-export shim at `stats/stats_data.py`.** A shim gives one module two
    import identities; `test_stats_multistage.py` registers
    `sys.modules["stats_data"]` and `test_aitask_stats_py.py` monkeypatches
    module globals, so a dual identity would silently split those patches.
    t1217 set the no-shim precedent and its guard asserts the old path is gone.
  - **Bare imports, not `from lib.stats_data import …`**, matching `task_yaml`
    after t1217 and keeping a single module object.
  - **Negative control (5) rewritten rather than deleted.** It proved
    per-package allowlisting *using the entry being removed*. `is_allowed` now
    reads an overridable `ACTIVE_ALLOWLIST`, so the semantics are pinned against
    a synthetic `neg_perpkg.py:stats` entry, and a new control (5b) asserts the
    old real reach is flagged again. Verified by injecting the removed
    `sys.path` block back into `lib/work_report_gather.py`: the guard failed and
    named `work_report_gather.py:stats:51`, then the file was restored by hand
    (not `git checkout --`, which would have wiped concurrent work).

- **Upstream defects identified:** None

- **Manual verification not performed:** `./ait stats-tui` was never launched —
  the panes are proven to import and register, but nobody has watched them draw.
