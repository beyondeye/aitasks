---
Task: t1217_promote_task_yaml_to_lib.md
Base branch: main
plan_verified: []
---

# t1217 — Promote `task_yaml.py` from `board/` to `lib/`

## Context

`.aitask-scripts/task_yaml.py` is the framework's shared task-frontmatter
parser (`parse_frontmatter`, `serialize_frontmatter`, `BOARD_KEYS`,
`normalize_board_idx`, the `_TaskSafeLoader` / `_FlowListDumper` YAML
classes). It lives in `board/` for historical reasons only — its own docstring
says it was *"Extracted from aitask_board.py for reuse by aitask_merge.py and
other tools"*.

`lib/` is the shared base layer. Today **two `lib/` modules reach *up* into
`board/`** to import it (`work_report_gather.py`, `trail_gather.py`), and three
unrelated TUI packages (`codebrowser`, `diffviewer`, `monitor`) each
`sys.path.insert` `board/` purely to reach this one parser. Moving or renaming
`task_yaml.py` silently breaks all of them.

Outcome: the module's location matches its actual role, the layer direction is
restored (`lib/` depends on nothing above it for this parser), and a guard test
freezes the result.

### Audit drift since the task was filed

The task file lists 6 importers. Verified against current `main`, there are
now **7** — `lib/trail_gather.py:133` was added after filing (a second `lib/`
module with the same inversion). Three additional `board/` `sys.path` inserts
in `monitor/` also become dead once the module moves. Verified as **not**
needing changes: no references in `aidocs/`, `website/`, `seed/`, or any skill
tree (zero doc churn).

## The move

```bash
git mv .aitask-scripts/board/task_yaml.py .aitask-scripts/lib/task_yaml.py
```

Update its module docstring — it currently describes itself as a board
extraction; restate it as the base-layer frontmatter parser shared by the
board, the merge tool, the gatherers, and the TUIs.

After the move `board/` holds only `aitask_board.py` and `aitask_merge.py`.
**Nothing outside `board/` and `tests/` imports either of them** (verified by
grep), so every remaining `board/` `sys.path` insert in a shipped package is
dead and gets removed.

## Importer updates

### The one edit that is load-bearing, not mechanical

`board/aitask_merge.py` imports `task_yaml` at line 30 but only inserts `lib/`
on `sys.path` at line 34 (for `gate_ledger`). Post-move the line-30 import
resolves against nothing. **Move the `task_yaml` import below the `lib/`
insert**, joining `import gate_ledger`, with `# noqa: E402`, and fold it into
that block's existing comment.

This ordering is what keeps two callers working unchanged:
- `aitask_sync.sh:221` runs the merge tool with `PYTHONPATH="$SCRIPT_DIR/board"`
  only.
- `tests/test_aitask_merge.py:10` inserts only `board/` (its own comment
  already documents relying on `aitask_merge` to insert `lib/` itself).

### Mechanical: drop or swap the `board/` insert

Each of these inserted `board/` *solely* to reach `task_yaml`; `lib/` is
either already inserted or replaces it. Update the accompanying comment in
each case so it does not describe a path that no longer exists.

| File | Change |
|---|---|
| `lib/work_report_gather.py:47-51` | `for _sub in ("board", "stats")` → `("stats",)` — the inversion this task repays; the `stats` insert stays (see guard allowlist) |
| `lib/trail_gather.py:123-125` | loop over `(_LIB_DIR, …/"board")` → ensure `_LIB_DIR` only; keep `_SCRIPTS_DIR` (still used at line 249) |
| `codebrowser/history_data.py:17` | drop the `board` insert; the `lib` insert on line 18 already covers it |
| `diffviewer/plan_loader.py:7-9` | swap `board` → `lib` (it inserts *only* `board` today) |
| `monitor/monitor_core.py:35-39` | drop `board` from the two-dir tuple |
| `monitor/monitor_app.py:25`, `monitor/minimonitor_app.py:26`, `monitor/monitor_shared.py:16` | drop the now-dead `board` insert — `monitor_core` was the package's only `board/` consumer |

`board/aitask_board.py` needs no functional change (`lib/` is already inserted
at line 15, well above the line-53 import). Relocate its `from task_yaml
import (…)` block up next to the other `lib/` imports so the layering is
visible rather than implied.

### Stale prose to fix in the same commit

- `lib/shortcut_scopes.py:78` — the `_ensure_import_paths` docstring uses
  "``aitask_board`` → ``task_yaml`` in ``board/``" as its example of a
  bare-name sibling import. That becomes false. Replace with a still-true one:
  `codebrowser_app` → `history_data` in `codebrowser/`.
  *(This file has unrelated uncommitted edits from another session at lines
  ~63 and ~97 — the docstring is a separate hunk; stage this path
  deliberately, do not blanket-add.)*
- `lib/yaml_utils.sh:22` — comment says "via `task_yaml.py`"; make it
  `lib/task_yaml.py`.

## Test updates

| File | Change |
|---|---|
| `tests/test_update_multiline_yaml.sh:207` | `sys.path.insert(0, argv[1] + "/.aitask-scripts/board")` → `.../lib` |
| `tests/test_history_data.py:20` | drop the now-dead `board` insert |
| `tests/test_trail_gather.py:35` | drop the now-dead `board` insert |

Verified as needing **no** change: `tests/test_board_topic_group.py` (inserts
both dirs; line-472 import keeps resolving), `tests/lib/work_report_equiv.py`
(still needs `board/` for `aitask_board`), `tests/test_aitask_merge.py` (see
above), `tests/run_all_python_tests.sh` (exports both on `PYTHONPATH`), and the
two import-hygiene guards `tests/test_chat_no_aitasks_import.sh:52` /
`tests/test_chatlink_relay.sh:496` — their `FRAMEWORK_PREFIXES` tuples match on
*module name*, which the move does not change.

## New guard: `tests/test_no_lib_to_tui_import.sh`

Converts the task's two manual verification greps into a freeze, modeled on
`tests/test_no_raw_tmux.sh` (same allowlist-with-per-entry-reason idiom).

**Rule:** no module under `.aitask-scripts/lib/` may put a sibling TUI package
directory (`board`, `stats`, `monitor`, `codebrowser`, `diffviewer`,
`brainstorm`, `applink`, `chat`, `chatlink`, `syncer`, `settings`, `logview`,
`agentcrew`) on `sys.path`.

**Allowlist (scoped `file:dir`, each with its reason):**
- `lib/shortcut_scopes.py:*` — reflection loader; it deliberately imports every
  TUI module by path to sweep shortcut bindings.
- `lib/work_report_gather.py:stats` — **known remaining inversion**
  (`stats_data` reuse). Out of scope for this task; allowlisted so it is
  *surfaced* rather than silently ignored.

**Scope honesty:** the guard detects `sys.path` insertion of a sibling package
dir. It does not attempt to catch dynamic/`importlib` loading — stated in the
test header, matching `test_no_raw_tmux.sh`'s documented-boundary style.

**Negative control (the guard must be able to fail):** factor the scan into a
function taking a directory argument. Run it once against the real
`.aitask-scripts/lib/` (expect 0 violations) and once against a temp fixture
dir containing a synthetic `bad_module.py` that inserts `board/` (expect
exactly 1 violation, naming that file). Without the second run a
permanently-passing grep proves nothing.

The guard must also **exit non-zero** when a real violation is present — not
merely print one. Confirm by temporarily adding a `board/` insert to a `lib/`
module, running the guard, and checking `$?` is 1; then undo the edit by
reversing that one line (never `git checkout --`, which would discard the
concurrent uncommitted work in `lib/shortcut_scopes.py`).

No registration step: per `CLAUDE.md`, bash tests are self-contained and run
individually (`tests/run_all_python_tests.sh` covers only `test_*.py`). The new
guard follows `test_no_raw_tmux.sh` — same `tests/lib/asserts.sh` sourcing and
`PASS`/`FAIL`/`TOTAL` summary convention.

## Verification

**Interpreter:** every command below runs under the *framework* interpreter, not
bare `python3` — on a host whose system Python lacks PyYAML/Textual/Rich, bare
`python3` fails before it ever reaches the moved module, which would read as a
path regression that isn't one. Repo idiom (see
`tests/test_update_multiline_yaml.sh:23-27`, `tests/run_all_python_tests.sh:14-15`):

```bash
source .aitask-scripts/lib/python_resolve.sh
PY="$(require_ait_python)"        # venv CPython: yaml + textual + rich
PYF="$(require_ait_python_fast)"  # PyPy fast path — what `ait board` actually execs
```

`$PY`/`$PYF` are absolute interpreter paths, so `env -u PYTHONPATH "$PY" …`
isolates the import path without touching the dependency set.

Run from the repo root, in order:

```bash
bash tests/test_no_lib_to_tui_import.sh      # new guard + its negative control
bash tests/test_work_report_gather.sh        # includes the board-equivalence oracle
bash tests/test_update_multiline_yaml.sh
bash tests/run_all_python_tests.sh           # test_board_*.py (13), test_trail_gather,
                                             # test_history_data, test_aitask_merge, …
bash tests/test_stats_data.sh
bash tests/test_chatlink_relay.sh
bash tests/test_chat_no_aitasks_import.sh
```

Check `$?` after each — these scripts print a `PASS`/`FAIL` summary, and a
non-zero exit is the signal that matters. Do not read the summary text alone.

**Direct-invocation check (the suite runner masks path bugs).** `run_all_python_tests.sh`
exports *both* `board/` and `lib/` on `PYTHONPATH`, so it cannot detect a
broken per-file `sys.path` bootstrap. Re-run the touched Python tests standalone,
with no `PYTHONPATH`:

```bash
env -u PYTHONPATH "$PY" -m pytest tests/test_aitask_merge.py \
    tests/test_trail_gather.py tests/test_history_data.py \
    tests/test_board_topic_group.py -q
```

**TUI entry-module import assertion (replaces an interactive smoke-launch).**
The `codebrowser`, `diffviewer` and `monitor` packages import this parser but
have the thinnest coverage of the import path, and the `.sh` launchers add no
`PYTHONPATH` of their own — their *only* contribution is resolving the
interpreter. So importing each entry module under that same interpreter
exercises the identical import chain.

Verified precondition making this bounded and non-interactive: **all five entry
modules guard with `if __name__ == "__main__":` and every `.run()` sits inside
that guard** (`aitask_board.py:7381`, `codebrowser_app.py:1531`,
`monitor_app.py:2056`, `diffviewer_app.py:275`, plus `minimonitor_app.py`) — an
`import` therefore never starts Textual and never touches the terminal.

The loop must **fail loudly**: `cmd && echo ok || echo FAIL` would make the
failure branch itself succeed, leaving the block exit 0 with a broken consumer.
Accumulate a flag and exit on it, in a subshell so the status is the block's:

```bash
(
  rc=0
  for spec in "codebrowser:history_data"   "codebrowser:codebrowser_app" \
              "diffviewer:plan_loader"     "diffviewer:diffviewer_app" \
              ":monitor.monitor_core"      ":monitor.monitor_app" \
              ":monitor.minimonitor_app"   "board:aitask_board"; do
    d="${spec%%:*}"; m="${spec#*:}"
    if env -u PYTHONPATH "$PY" -c \
         "import sys; sys.path.insert(0, '.aitask-scripts/$d'); import $m"
    then echo "ok   $m"
    else echo "FAIL $m"; rc=1
    fi
  done
  exit "$rc"
)
status=$?
echo "entry-module import assertions exit=$status"
exit "$status"
```

The trailing `exit "$status"` is the load-bearing line. A bare
`echo "exit=$?"` as the last statement would itself succeed and hand the whole
sequence a 0 status — reinstating exactly the output-only failure it was meant
to report. Capture the subshell status into a variable *before* printing
anything, then exit on it (or drop the `echo` entirely and let the subshell be
the final command).

**Prove the assertion can fail** before trusting a green run — append a
deliberately bogus spec (`":does_not_exist_xyz"`) to the list, re-run, and
confirm the block prints `FAIL`, reports `exit=1`, **and** that `$?` of the
whole block is 1. Remove the bogus spec afterwards. A green assertion whose
exit path is broken pins nothing.

`ait board` execs the **PyPy** fast path, a different interpreter from the rest
— assert it separately (per `aidocs/framework/python_tui_performance.md`, board
is the only TUI on that path):

```bash
env -u PYTHONPATH "$PYF" -c \
  "import sys; sys.path.insert(0, '.aitask-scripts/board'); import aitask_board"
```

Every command above is bounded (exits on its own, no TTY, no cleanup needed).
**Manual check, optional:** launching `ait board` / `ait codebrowser` /
`ait monitor` by hand and confirming the TUI paints its first screen, then
quitting with `q`. This adds nothing the import assertions do not already cover
and is *not* required to close the task — do not run it from an automated agent.

**Merge tool under its production argv** — `aitask_sync.sh:221` passes only
`PYTHONPATH=board`, a path no existing test exercises:

```bash
env -u PYTHONPATH PYTHONPATH=.aitask-scripts/board "$PY" \
    .aitask-scripts/board/aitask_merge.py --help
```

**Residual greps** (now also enforced by the guard):

```bash
grep -rn "from task_yaml import\|import task_yaml" .aitask-scripts/ tests/
grep -rn "board" .aitask-scripts/*/[a-z]*.py | grep sys.path
```

Housekeeping: delete the stale `.aitask-scripts/board/__pycache__/task_yaml*.pyc`
(gitignored, not importable without its source, but removing it avoids
confusion while debugging).

## Risk

### Code-health risk: medium

- A missed or wrong `sys.path` bootstrap surfaces only at TUI runtime, **not**
  under the test suite — `tests/run_all_python_tests.sh` exports both `board/`
  and `lib/` on `PYTHONPATH`, so it passes even with a broken per-file
  bootstrap. `diffviewer/plan_loader.py` and `codebrowser/history_data.py` are
  the thinnest-covered consumers · severity: medium · → mitigation: in-task —
  the `env -u PYTHONPATH` direct-invocation pytest run and the entry-module
  import assertions (CPython + PyPy) in Verification exist specifically to
  defeat this masking · → mitigation: pythonpath_isolated_python_test_lane
- `board/aitask_merge.py` breaks under its **production** argv if the import is
  not reordered below the `lib/` insert: `aitask_sync.sh:221` invokes it with
  `PYTHONPATH="$SCRIPT_DIR/board"` and nothing else, a path no existing test
  exercises · severity: medium · → mitigation: in-task — the explicit
  production-argv `aitask_merge.py --help` check in Verification
- Blast radius is wide (11 source files across 6 packages + 3 test files), though
  each edit is a one-to-three-line import/bootstrap change with a loud
  `ImportError` failure mode rather than silent misbehavior · severity: low ·
  → mitigation: none needed — every site is enumerated in this plan and frozen
  by the new guard test
- `lib/shortcut_scopes.py` carries uncommitted edits from a concurrent session;
  a blanket `git add` would sweep foreign hunks into this task's commit ·
  severity: low · → mitigation: in-task — stage explicit paths and verify
  `git diff --cached` content before committing

### Goal-achievement risk: low

- The goal is a literal file move with a fully enumerated importer list
  (re-audited against live source, which is how the 7th importer was found), so
  there is little room for a wrong-shaped approach or missed requirement.
- One deliberate exclusion: `lib/work_report_gather.py` keeps its `stats/`
  `sys.path` insert, so the `lib/` layer direction is repaid for `board/` but
  **not fully restored**. This is out of scope for t1217 and is surfaced (not
  hidden) via the guard's allowlist entry · severity: low · → mitigation:
  repay_lib_stats_inversion

### Planned mitigations
- timing: after | name: repay_lib_stats_inversion | type: refactor | priority: medium | effort: medium | addresses: goal-achievement — lib/work_report_gather.py keeps its stats/ sys.path insert, so the lib/ layer direction is only partly restored | desc: Relocate the shared stats_data surface (DAY_NAMES, collect_stats) to the base layer, drop the last sibling-package sys.path insert from lib/, and tighten tests/test_no_lib_to_tui_import.sh's allowlist to empty
- timing: after | name: pythonpath_isolated_python_test_lane | type: test | priority: medium | effort: low | addresses: code-health — run_all_python_tests.sh exports both board/ and lib/ on PYTHONPATH, so a broken per-file sys.path bootstrap passes the suite and fails only at TUI runtime | desc: Add an isolated-import lane to the Python test runner (or stop exporting sibling package dirs) so per-file sys.path bootstraps are exercised as shipped, making the masking structurally impossible instead of relying on a manual env -u PYTHONPATH check

## Post-Review Changes

### Change Request 1 (2026-07-24 11:30)

- **Requested by user:** `.aitask-scripts/board/aitask_board.py` had picked up
  the **t1225** `run_dialog_command` refactor from a concurrent session while
  t1217 was in flight (t1225 is still `Implementing` and its plan/tests own
  those callback and worker changes). Staging that path wholesale would
  contaminate the t1217 commit with another task's implementation. Requested a
  selective index containing only the import-relocation hunk, verified via
  `git diff --cached`. Verdict: CONFIRMED, blocking.
- **Changes made:** No source edits. Corrected the *staging* method:
  - Re-audited every candidate path by **diff content**, not by whether it was
    dirty at session start — that heuristic was what missed this, since
    `aitask_board.py` was clean at session start and became contaminated
    mid-session. The other 14 modified files were confirmed 1-hunk and
    entirely t1217.
  - Built a two-hunk patch from `git diff` (header + the import add/remove
    hunks only) and applied it with `git apply --cached`; staged the remaining
    paths explicitly by name.
  - Verified the **index**, not the worktree: `git diff --cached` on
    `aitask_board.py` shows only the import move; a token grep over the whole
    staged diff for `run_dialog_command` / `CODEAGENT_FAILURE_NOTICE` /
    `refocus_filename` / `error_notice` / the two removed helpers returns
    nothing; and the t1225 work remains intact and unstaged in the worktree
    (47 insertions / 49 deletions still pending for that task).
  - **Validated the commit content itself** rather than the worktree that had
    been tested up to that point: materialized the exact index tree with
    `git checkout-index -a --prefix=…` and re-ran all eight entry-module
    imports, the PyPy `aitask_board` import, the `PYTHONPATH=board`
    `aitask_merge --help` check, and the new guard against that tree — all
    green. The staged `aitask_board.py` blob compiles, contains exactly one
    `from task_yaml import`, and still carries the pre-t1225 helpers.
- **Files affected:** none (staging-only change). Staged set: the 16 t1217
  paths plus the new `tests/test_no_lib_to_tui_import.sh`.

**Lesson for the Final Implementation Notes:** in a shared checkout, "this file
was clean when I started" is not evidence that a file is uncontaminated at
commit time. Concurrent sessions can dirty a path mid-task, so the pre-commit
audit must read the diff of every path being staged.

## Final Implementation Notes

- **Actual work done:** `git mv .aitask-scripts/board/task_yaml.py
  .aitask-scripts/lib/task_yaml.py`, then updated all **7** importers (the plan's
  re-audit found one more than the task file listed — `lib/trail_gather.py`,
  added after filing). Removed 4 now-dead `board/` `sys.path` inserts from
  `monitor/` (`monitor_core`, `monitor_app`, `minimonitor_app`,
  `monitor_shared`), swapped `board`→`lib` in `diffviewer/plan_loader.py`,
  dropped the `board` insert in `codebrowser/history_data.py`, narrowed
  `lib/work_report_gather.py`'s loop to `("stats",)` and `lib/trail_gather.py`'s
  to `_LIB_DIR` only. Relocated `board/aitask_board.py`'s `task_yaml` import up
  into its `lib/` import group. Fixed 3 test bootstraps and 2 stale comments
  (`lib/shortcut_scopes.py` docstring example, `lib/yaml_utils.sh` path).
  Added `tests/test_no_lib_to_tui_import.sh` (10 assertions) freezing the
  layering. Net: 17 files, +40/−36 plus the 189-line new guard.
- **Deviations from plan:** None in scope or approach. The only deviation was in
  *how* the commit was staged — see Post-Review Changes above.
- **Issues encountered:**
  1. `board/aitask_merge.py` imported `task_yaml` at line 30 but only inserted
     `lib/` at line 34. Post-move that import resolves against nothing. Moving it
     below the insert was the one non-mechanical edit; it is what keeps
     `aitask_sync.sh:221` (`PYTHONPATH=board` only) and `tests/test_aitask_merge.py`
     (inserts only `board/`) working unchanged. Verified explicitly by running
     the merge tool under that exact production argv.
  2. `tests/run_all_python_tests.sh` exports **both** `board/` and `lib/` on
     `PYTHONPATH`, so the suite cannot detect a broken per-file `sys.path`
     bootstrap. Defeated by re-running the touched tests under
     `env -u PYTHONPATH` (163 tests) plus entry-module import assertions on
     CPython and PyPy. Structural fix deferred to the
     `pythonpath_isolated_python_test_lane` mitigation.
  3. A concurrent session landed the t1225 `run_dialog_command` refactor into
     `aitask_board.py` mid-task, requiring a selective index (see Post-Review
     Changes). All prior verification had run against the worktree; it was
     re-run against the materialized index tree to validate the actual commit
     content.
- **Key decisions:**
  - Guard scope is **`sys.path` insertion of a sibling package dir**, documented
    as not covering dynamic/`importlib` loading — a documented boundary, matching
    `tests/test_no_raw_tmux.sh`'s style, rather than an overclaiming guard.
  - The remaining `lib/work_report_gather.py → stats/` inversion is
    **allowlisted with its reason**, not silently excluded, so it stays visible;
    repaying it empties the allowlist (tracked as `repay_lib_stats_inversion`).
  - Every assertion was proven able to fail before being trusted: the guard was
    run against a real injected violation (exit 1), and the import block against
    a bogus module (exit 1). Both mutations were undone by reversing the edit,
    never `git checkout --`, because the checkout would have discarded the
    concurrent session's uncommitted work.
- **Upstream defects identified:** None
- **Notes for sibling tasks:** n/a (not a child task).

## Step 9 (Post-Implementation)

Standard: merge approval, `ait gates run 1217` (this task declares
`risk_evaluated`), branch/worktree cleanup (n/a — working on the current
branch per profile `fast`), then `./.aitask-scripts/aitask_archive.sh 1217`.
