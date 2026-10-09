---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [install, install_scripts, framework]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5_5
created_at: 2026-10-08 23:35
updated_at: 2026-10-09 11:35
---

## Problem

`ait upgrade` / `install.sh` never removes `.aitask-scripts/` files that the
framework retired or moved. A leftover module can then **shadow** its moved
replacement and crash the TUI that imports it.

Observed 2026-10-08 in the registered project `thinking_app`, on framework
v0.36.1:

```
File ".../thinking_app/.aitask-scripts/board/aitask_board.py", line 65, in <module>
ImportError: cannot import name 'normalize_board_idx' from 'task_yaml'
  (/home/ddt/Work/thinking_app/.aitask-scripts/board/task_yaml.py)
```

- t1217 (`979b88968`, 2026-07-24) moved `task_yaml.py` from
  `.aitask-scripts/board/` to `.aitask-scripts/lib/`.
- thinking_app still has `.aitask-scripts/board/task_yaml.py`: 4616 bytes,
  mtime Jul 10, **tracked in thinking_app's git**. Its current
  `lib/task_yaml.py` (Oct 5) defines `normalize_board_idx`; the old board copy
  does not.
- `aitask_board.py` inserts `board/` **ahead of** `lib/` on `sys.path`
  (L13 inserts `lib`, then L17 inserts `board/` at index 0). The stale copy
  therefore wins the import.
- Since v0.36.1 the board imports `normalize_board_idx`, so every fresh
  `ait board` in thinking_app crashes at import. A board started before the
  upgrade keeps running until restarted. That is why the board in the
  `thinkingapp` tmux session still looked fine.
- The user hit this through the TUI switcher (`j` → board from the
  minimonitor in the `aitasks` session). The switcher only reached thinking_app
  because of the session-root mis-mapping in t1922. The crash itself is
  independent: any fresh thinking_app board fails.

## Cause

- `install.sh` extracts the release tarball over `$INSTALL_DIR`
  (`tar -xzf … -C "$INSTALL_DIR"`, ~L1503). Extraction is purely additive.
- The only retirement cleanup is `prune_retired_skills()`
  (`aitask_prune_retired_skills.sh`, invoked ~L967), and it covers **skill
  surfaces only**. Nothing prunes retired `.aitask-scripts/` files, so every
  project upgraded across a move or delete keeps the old file. It is also
  committed into the project's git, because `commit_framework_files` stages
  framework paths.

## Goal

- **Prune retired framework scripts on upgrade and setup**, following the
  existing retired-skills design:
  - a manifest of retired `.aitask-scripts/` paths;
  - ownership decided **by content hash**, so a user-modified file is kept and
    reported, never deleted;
  - deletions surfacing through the existing framework-commit staging.
- **Seed the manifest** with at least the t1217 move (`board/task_yaml.py`).
  Audit the git history for other deleted or moved paths under
  `.aitask-scripts/` (`git log --diff-filter=D --name-only -- .aitask-scripts/`)
  and add the hashes of every shipped version of each.
- **Consider defence in depth for the import shadowing.** The board puts its
  own directory ahead of `lib/`, so any future stale or user file in `board/`
  named like a `lib/` module shadows it again. Either assert at startup that
  shared modules resolve from `lib/`, or reorder the path, after checking the
  "board package" import contract in `aidocs/framework/tui_conventions.md`.
  Do the same check for the other TUIs that insert their own directory first.
- Read `aidocs/framework/aitasks_extension_points.md` first, since this edits
  the install flow.

## Tests

- **Fixture project upgrade:** it contains a pristine retired file (removed
  and staged), a user-modified retired file (kept with a warning), and an
  unrelated user file (untouched).
- **Regression for the shadowing:** with a `board/task_yaml.py` lacking
  `normalize_board_idx` present, the board's import of `task_yaml` must resolve
  to `lib/` or fail with a clear diagnostic, never an opaque ImportError.

## Acceptance check: real upgrade of an old project

Unit tests on the helper are not enough. Acceptance means the cleanup works
through the actual `ait upgrade` path:
1. `aitask_upgrade.sh` downloads the **target** tag's `install.sh`
   (`aitask_upgrade.sh:99`).
2. It runs that script with `--force --dir` (`:152`).
3. The prune therefore executes from the new release's code, even inside a
   project whose installed scripts predate it.

**Fixtures.** Build two throwaway git projects, each a framework install at a
fixed old version, committed:
- **v0.31.0** (aitasks_go shape): ships `board/task_yaml.py`,
  `stats/stats_data.py` and the attachment/codex-plan scripts as that release
  had them.
- **v0.36.1** (thinking_app shape): carries the 8 leftovers from the registry
  scan above, with byte content exactly as shipped by the releases they came
  from.

To each fixture add:
- one leftover whose content was **modified locally**, e.g. an extra line in
  `lib/codex_plan_policy.sh`;
- one **user-authored** file under `.aitask-scripts/` that never existed in the
  framework.

**Run.** Upgrade each fixture to the release under test. Run `install.sh --force
--dir <fixture>` from this checkout, or via a local tag/tarball, so the test
needs no network; this is the same code path `ait upgrade` invokes.

**Must hold, per fixture:**
- Every pristine leftover the target release no longer ships is **gone** from
  the working tree. This includes `board/task_yaml.py`, a *rename* source.
- The removal is **committed** in the fixture's git: `git ls-files` no longer
  lists the file, and `git status --porcelain -- .aitask-scripts/` is clean for
  those paths. Check the commit `install.sh` creates, not just the working tree.
- The locally **modified** leftover is **kept**, and the run's output names it
  with a cleanup hint.
- The **user-authored** file is untouched.
- `./ait board` in the upgraded fixture starts without the `normalize_board_idx`
  ImportError. Boot it the way the existing board live tests do, or at minimum
  import `aitask_board` with `board/` first on `sys.path`.
- **Re-running** the upgrade or `ait setup` on the upgraded fixture is a no-op:
  nothing pruned, no new commit.

**Negative control.** Run the same fixture against a release built **without**
the prune step. `board/task_yaml.py` must survive and the board import must
fail. This proves the fixture really reproduces the defect, so the passing
result is not vacuous.

**Already-current projects.** `ait upgrade` stops with "Already up to date" when
the project is already on the target version. Cover that case by running
`ait setup` on a fixture that is on the new release but still carries
leftovers. Either the prune runs there, or the task documents explicitly that
such projects need `ait setup`.

## Registry scan (2026-10-08, read-only)

**Method.** For each registered project, a file counts as a leftover when it
meets all three conditions:
- it is tracked under `.aitask-scripts/` in that project;
- it is **absent from the project's own installed release tag** (`v<VERSION>`);
- it has existed somewhere in framework history.

Comparing against the project's own version matters. A project on an older
release legitimately carries files that later releases removed. For example,
aitasks_mobile is on v0.27, which predates t1217, so its `board/task_yaml.py` is
the correct copy for that version.

Renames count too. `git log --diff-filter=D` misses `git mv` sources such as
t1217's move, so the manifest audit must include `--diff-filter=R` sources.

| project | version | leftovers | board crashes? |
|---|---|---|---|
| thinking_app | 0.36.1 | 8, incl. `board/task_yaml.py`, `stats/stats_data.py` | **yes**: ImportError `normalize_board_idx` |
| thinking_backend | 0.36.1 | 8 (same set) | **yes**: same ImportError |
| aitasks_go | 0.31.0 | 13, incl. `board/task_yaml.py`, `stats/stats_data.py` | no, runs |
| aitasks_mobile | 0.27.0 | 6 (`aitask_install.sh`, brainstorm detailer/patcher, `_detailer_rules.md`) | n/a |
| timexchange, teamim | 0.31.0 | 0 | — |
| animeless | 0.36.0 | 0 | — |

The 0.36.1 leftover set:
- `aitask_codex_plan_invoke.py`
- `board/task_yaml.py`
- `lib/attachment_backend.sh`
- `lib/attachment_backends/local.sh`
- `lib/attachment_cache.sh`
- `lib/attachment_utils.sh` (renamed to `lib/artifact_utils.sh`)
- `lib/codex_plan_policy.sh`
- `stats/stats_data.py` (moved to `lib/stats_data.py`)

All of them are tracked in their project's git. The thinking_app stats TUI
currently starts fine: `stats_app.py` imports bare `stats_data`, and today that
resolves from `lib/`. Even so, `stats/stats_data.py` differs from
`lib/stats_data.py`, so it is a latent shadow of the same shape and belongs in
the manifest. Only Python modules that a TUI imports by bare name can shadow;
stale `.sh` files are inert unless sourced.

## Workaround for an affected project

In that project, delete `.aitask-scripts/board/task_yaml.py`
(`git rm .aitask-scripts/board/task_yaml.py`, then commit it by name). Other
projects upgraded from before t1217 likely carry the same file.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-09T08:35:39Z status=pass attempt=1 type=human
