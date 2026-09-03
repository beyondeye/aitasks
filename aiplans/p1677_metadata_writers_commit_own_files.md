---
Task: t1677_metadata_writers_commit_own_files.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1677 — Give every tracked `aitasks/metadata/*` write an owner that commits it

## Context

`t1599_3` made `ait sync`'s pre-sync sweep refuse to commit any dirty file it
cannot attribute to a task. That was right — the forensics are in the code:
`board_config.json` has **8 of its 9** commits attributed to unrelated tasks and
`stats_config.json` **3 of its 4**. But it left the gap its own `## Risk`
section flagged at severity **high**:

> Ownerless files have **no session that ever commits them** — their writers only
> write. An ownerless dirty file becomes a *permanent* rebase deferral, blocking
> all task-data sync until a human intervenes.

`aitask_sync.sh:639` now prints a prescriptive remedy for exactly this, and
`website/content/docs/commands/sync.md:78` states it as a standing fact:
"nothing else will ever commit it, so it stays dirty until you do."

This task makes that sentence false for the config-editing surfaces: every
**explicit user-initiated** write to a tracked `aitasks/metadata/*` file commits
itself, through the framework's existing scoped-commit seam, under a message
that names the file rather than a task — the rule `aitask_pick_own.sh:483`
already applies to `emails.txt`.

**Two decisions taken with the user before planning:**

1. `aidocs/framework/tui_conventions.md:347-356` currently forbids this outright
   ("Never call `git commit` … from inside a TUI event handler for a config
   change"). The rule is **amended**, not deleted: commit only on an *explicit
   user-initiated save*; never on a background/incidental save; never push.
2. `diffviewer_history.json` is tracked but is per-user MRU state rewritten on
   every navigation. It is **untracked and moved to the user layer**, not
   committed.

## Re-derived writer inventory

Tracked set is `./ait git ls-files aitasks/metadata/` (25 files) — plain `git`
sees nothing, because `aitasks` is a symlink onto the `aitask-data` branch.

**Already owned — no change.** `emails.txt` (`aitask_pick_own.sh:483`,
`aitask_create.sh:1236`), `labels.txt` (create/update staging),
`models_*.json` (`lib/verified_update_lib.sh` H10), and everything
`aitask_setup.sh:1815` commits on the fresh-data-branch path.

**Deliberate human-review exceptions — no change, documented.** `gates.yaml`
(`aitask_gate.sh:1186` warns "registry updated but NOT committed — review it,
then …"); `aitask_add_model.sh` / `aitask_opencode_models.sh`, which also write
`seed/` on the main branch and always run inside a task that commits.

**Out of scope, follow-up.** `lib/cross_repo_settings.py:400` (`apply_push`,
driven by `syncer_app.py:1973`) writes **another repo's**
`codeagent_config.json`. A repo-scoped seam cannot commit into a repo that may
be mid-work; see `## Risk`.

**Ownerless today — this task's targets:**

| Surface | Write site | File |
|---|---|---|
| Settings TUI | `settings_app.py:590` `save_codeagent` | `codeagent_config.json` |
| Settings TUI | `settings_app.py:603` `save_board` | `board_config.json` |
| Settings TUI | `settings_app.py:608` `save_project_settings` | `project_config.yaml` |
| Settings TUI | `settings_app.py:617/643` `save_profile` / `delete_profile` — `save_profile` also **creates** (`_handle_new_profile`, `:3766`) | `profiles/<n>.yaml` |
| Settings TUI | `settings_app.py:3996` `_handle_import` → `config_utils.import_all_configs` | arbitrary set |
| Board TUI | `aitask_board.py:1926` `TaskManager.save_metadata` (6 column-CRUD callers) | `board_config.json` |
| minimonitor → headless | `aitask_board_column.sh create` → `board_columns.py:801` | `board_config.json` |
| chatlink wizard | `wizard.py:1260` `_do_save` → `config_write.py:129` | `chatlink_config.yaml` |
| `ait setup` | `aitask_setup.sh:2006/2033/2057/2086/2172` `ensure_*` | `project_config.yaml`, `chatlink_config.yaml`, `crew_runner_config.yaml`, 4 agent seed files |
| diffviewer | `plan_browser.py:213` `_save_history` | `diffviewer_history.json` → **untrack** |

`stats_config.json` has **no writer at all** — `stats/stats_config.py:44` writes
only the `.local.json` layer, by design. The task description's third bullet
("whatever writes stats_config.json") describes a file that nothing writes; its
four commits are all swallows. Nothing to do for it.

---

## Step 1 — The seam (one implementation, two languages)

`task_git_commit_scoped` (`lib/task_utils.sh:338`) already does the hard part —
`commit -o -m … -- <paths>` commits the *worktree* content at those paths and
**bypasses the index**, so a concurrent session's staged entry cannot ride
along. There is **no Python equivalent anywhere in the tree**, and every
existing Python commit site (`settings_app.py:3705`, `aitask_board.py:14164`)
is a bare pathspec-less `git commit` — i.e. the exact index-wide swallow t1599
exists to eliminate. Do not add a second implementation; wrap the one that
exists.

**1a. `lib/task_utils.sh` — `ait_metadata_commit_message <path>...`, the message
format, single-sourced.** Contract, not code:

- The subject names the **file**, never a task — two sessions can dirty a shared
  config, and only a file-naming message stays true regardless of who wrote it.
  This is the rule `aitask_pick_own.sh:483` already applies to `emails.txt`, and
  the shape `aitask_sync.sh:641` already prescribes: `ait: Update <basename>`.
- One path → `ait: Update <basename>`. Two or three → the basenames, comma-
  separated. More → `ait: Update <basename> and N more metadata files`, so the
  subject stays a subject.
- Zero paths → exit 2 and print nothing. An empty pathspec reaching `git commit`
  is what commits the whole index; this must fail before it can.
- Basenames only (`${p##*/}`), so a `profiles/fast.yaml` and a top-level file
  read the same way.

**1b. `.aitask-scripts/aitask_metadata_commit.sh` (new).** Sources
`terminal_compat.sh` + `task_utils.sh`, modelled on `aitask_gate_record.sh`.

```
Usage: aitask_metadata_commit.sh [--allow-new] <path>...
```

**Explicit paths only — there is deliberately no `--sweep`/`--all` mode.** A
"commit everything dirty under `aitasks/metadata/`" verb would commit whatever a
*concurrent* session was mid-editing, publishing content this process never
wrote. That is the raced-publication failure `t1599_3` built a whole quarantine
to prevent, and re-introducing it inside the task that closes its sibling gap
would be a straight regression. Every caller names the paths **it just wrote**.

Admission rules, all fail-closed:

- **Scope:** path must be under `aitasks/metadata/`, repo-relative, with no `..`
  segment → otherwise exit 2, `REFUSED:out_of_scope:<path>`.
- **Tracked-only by default.** `task_git_commit_scoped` **stages** the paths it
  is given (`task_git add -- "$@"`), so an untracked path passed by a careless or
  future caller would be *added to the data branch* — publishing local content
  the "tracked metadata" contract never covered. So: accept a path that is
  **tracked-and-modified** or **tracked-and-deleted**; refuse anything else with
  `REFUSED:untracked:<path>`, exit 2.
- **`--allow-new` is the narrow opt-in for genuinely created files.** Three
  surfaces legitimately create one: `aitask_setup.sh`'s populate-missing
  `ensure_*` family (`ensure_chatlink_config` writes the file when absent), the
  settings **new-profile** path (`save_profile` ← `_handle_new_profile`), and the
  settings import. Even under the flag the path must exist, be a regular file,
  and not be gitignored.

  **The flag is always *derived*, never hard-coded** — each caller computes it
  from an existence check taken **before** its own write, so it says "I created
  this", not "creation is allowed here". A hard-coded `True` is a standing
  relaxation that the next edit to that call site inherits without noticing;
  deriving it also means no caller has to remember the flag when its behaviour
  changes, which is precisely how `save_profile` would otherwise have been
  missed (it is a writer *and* a creator, and only its caller knew which).
- **User layer is skipped, not refused:** a path git ignores (`*.local.json`,
  `userconfig.yaml`, `profiles/local/`) → `SKIPPED:<path>`, exit unaffected.
  Callers pass whole layer-pairs without filtering.
- Message from `ait_metadata_commit_message`. **Never pushes** — the amended
  convention forbids it, and `task_push` is a network call inside what may be a
  TUI event handler.

**Staging: `--no-stage`, plus a scoped unstage on failure.** Calling
`task_git_commit_scoped` in its *default* mode would `task_git add -- <paths>`
first, and on a commit failure that `add` **survives**. A metadata path left in
the shared `.aitask-data` index is then swallowed by the next index-wide commit —
and one still exists (`aitask_board.py:14164` `_do_git_commit_tasks` commits with
no pathspec) — which is precisely the cross-session swallow this task exists to
end. Staging is also simply unnecessary for tracked paths: `commit -o -- <path>`
takes **worktree** content, a property `tests/test_sync_auto_commit_scoping.sh`
Test 16 already pins ("tracked files are committed WITHOUT being staged").

`aitask_sync.sh:778-805` already solves exactly this; **reuse its shape, do not
invent one**:

1. Stage **only** the untracked (`--allow-new`) paths — a pathspec cannot name a
   file git does not know about, so these have no alternative — and record each
   one that staged successfully in a `staged_by_us` array. Tracked and deleted
   paths are never staged.
2. `task_git_commit_scoped --no-stage "$msg" "${paths[@]}"`.
3. On **any** non-zero result, `task_git reset -q -- "${staged_by_us[@]}"`.
   Scoping the cleanup to entries *this* invocation created is what stops it
   unstaging another session's work; and because every `staged_by_us` entry was
   untracked at admission time (verified by `ls-files --error-unmatch` before
   staging), the reset removes an index entry that has no HEAD version to
   restore — it cannot resurrect stale content.

A temporary `GIT_INDEX_FILE` would also work, but it is a second mechanism over
the same shared index for a problem the framework already has one answer to.
- stdout is a data channel: `COMMITTED:<n>:<subject>` / `NOCHANGE` /
  `SKIPPED:<path>` / `REFUSED:<reason>:<path>` / `FAILED:<detail>`. Exit codes
  mirror the seam: **0** committed, **2** nothing to commit / refused, **1**
  commit failed.
- No permission-allowlist entries: its only callers are Python TUIs and other
  `.aitask-scripts/` shell scripts, never a `SKILL.md` closure
  (`aidocs/framework/aitasks_extension_points.md:322-332`). No `ait` dispatcher
  entry either, for the same reason.

**1b-fail. What every caller does when the commit fails** — specified here once,
because `commit_metadata` deliberately never raises (the config edit has already
landed, and losing it to a commit error would be worse than a dirty file). A
failure that is merely swallowed restores the exact permanent-deferral risk this
task exists to remove, so **every** surface must surface it, and every message
must carry the same single-sourced remedy: `aitask_metadata_commit.sh <path>`.

| Surface | On `FAILED:` |
|---|---|
| Settings TUI | `notify(…, severity="error")` naming the file and the remedy — the shape `_commit_profile` already used |
| Board TUI | same `notify`, from the thread worker (the board already notifies on git-commit failure at `:14164`) |
| chatlink wizard | fall back to **today's** behaviour: print the `./ait git add … && ./ait git commit …` hint block it prints now (`wizard.py:1344-1347`). A reachable, already-correct degradation |
| `aitask_board_column.sh` | `WARN:commit_failed:<path>` on **stderr** — stdout is the machine protocol and must not be polluted — and still exit 0: the column was created, the commit is secondary |
| `aitask_setup.sh` | `warn` naming the file and the remedy; never `die` — a failed metadata commit must not abort setup |

`ait sync` remains the backstop: a file whose commit failed is still dirty, so
the sweep reports it as ownerless with its own prescriptive line. The user is
told twice, never zero times.

**1c. `lib/metadata_commit.py` (new).** Thin subprocess wrapper so no Python
file re-derives git semantics:

```python
CommitResult = namedtuple("CommitResult", "status subject detail")
# status: committed | nochange | skipped | refused | failed

def commit_metadata(paths, *, allow_new=False, root=None, timeout=15) -> CommitResult:
    """Commit tracked aitasks/metadata paths through the shell seam.

    `allow_new=True` forwards `--allow-new`, permitting a path that is not yet
    tracked. Default False: every Python caller but the settings import passes
    only tracked paths, and an accidental add to the data branch is the failure
    this default exists to prevent.

    Never raises on a git failure — the write already landed, and losing the
    user's config edit to a commit error would be worse than a dirty file.
    Raises ValueError only on an empty path list (programmer error).
    """
```

**The wrapper's parameter set must cover every flag the shell seam accepts, or
the two drift into a defect that is invisible until run:** a missing `allow_new`
makes `_handle_import`'s call a `TypeError`, and "fixing" it by dropping the
argument silently refuses a newly imported config as untracked and leaves it
dirty — the exact ownerless file this task exists to eliminate. The
`--allow-new` flag is forwarded verbatim; it is not re-interpreted Python-side.

**1d. Re-point the sync remedy hint.** `aitask_sync.sh:641` hand-builds
`ait: Update ${path##*/}`. Have it call `ait_metadata_commit_message` and name
the new helper as the remedy, so the sweep's advice and the writers' behaviour
cannot drift.

## Step 2 — Wire the explicit-save surfaces

**2a. Settings TUI (`settings/settings_app.py`).** Commit inside the four
`ConfigManager.save_*` methods, not at their 8 call sites — every caller is an
explicit user save, and a method-level commit cannot be missed when a ninth
caller appears. `ConfigManager` gains an optional `on_commit` callback that
`SettingsApp` wires once to a `_notify_commit(result)` helper, so the manager
stays Textual-free.

- `save_codeagent` / `save_board` / `save_project_settings`: after the write,
  `commit_metadata([<project-layer path>])`. The `*.local.json` sibling is passed
  too and comes back `SKIPPED` — no caller-side filtering.
- `save_profile` (`:610`) **also creates files**, so it cannot be tracked-only:
  `_handle_new_profile` (`:3766`) calls it with `layer="project"` for a profile
  that does not exist yet, and `NewProfileScreen` (`:1098`) is a plain
  Settings gesture. Under the tracked-only default that creation would come back
  `REFUSED:untracked` and sit dirty — the task's own inventoried writer failing
  its owner guarantee. `save_profile` derives the flag **itself**, from
  `is_new = not path.exists()` captured *before* it writes, and passes
  `allow_new=is_new`. A user-layer profile is gitignored and comes back
  `SKIPPED` either way, so that branch needs nothing.
- `delete_profile` (`:643`): a tracked file removed from disk is a dirty
  deletion; pass the same path — `commit -o -- <path>` records a deletion
  (verified by t1599_3's Step-1 spike). A never-committed new profile deleted
  again is simply `NOCHANGE`, which is correct.
- `_handle_import` (`:3996`): `import_all_configs` returns the written
  filenames — commit that list in one commit. Derive `allow_new` the same way:
  snapshot which of the target paths exist **before** the import and pass
  `allow_new=True` only if the import actually created one.
- **Replace `_commit_profile` (`:3690-3715`) entirely.** Its `git add` +
  pathspec-less `git commit` is an index-wide swallow. The "Save & Commit"
  modal button collapses into plain "Save", since saving now commits.

**2b. Board TUI (`board/aitask_board.py`).** Add `commit: bool = True` to
`TaskManager.save_metadata` (`:1926`) and commit the project-layer path after a
successful `save_project_config`. Default in the helper, not the callers — the
six column-CRUD callers (`:2651`, `:2692`, `:2835`, `:2944`, `:8379`, `:13281`)
are all user gestures and need no edit. The **one** exception is the startup
first-ship at `:1732` (`if not METADATA_FILE.exists(): self.save_metadata()`),
which passes `commit=False`: that is the "first-time ship is a one-time
implementation commit" carve-out the convention already had, and it is not a
user gesture. Run it on the board's existing `@work(thread=True)` pattern so a
column merge does not block the UI thread on a subprocess.

`save_settings` / `_write_user_layer` (`:1891`) are untouched — they write only
the gitignored layer, which is precisely the "incidental save" the amended rule
still forbids from committing.

**2c. Headless column CLI (`aitask_board_column.sh`).** After a successful
`create`, call the helper on `aitasks/metadata/board_config.json`. Keep
`lib/board_columns.py` write-only — the wrapper's own header already promises
the lib owns writes and the wrapper owns process concerns.

**2d. chatlink wizard (`chatlink/wizard.py:1260`).** `_do_save` currently prints
a `./ait git add …` hint and never commits (`:1344-1347`). Commit instead, and
report the result — keeping the existing hint block as the **failure** branch
(see the 1b-fail table), so a failed commit degrades to exactly today's
behaviour rather than to silence.

**2e. `ait setup` (`aitask_setup.sh`).** `ait setup` is an explicit user action,
and the fresh-data-branch path at `:1815` already commits — this closes the
populate-missing/backfill path that does not.

**Commit only what this invocation wrote — never a blanket sweep.** Each
`ensure_*` already has an exact "I wrote it" point, right beside its own
`success`/`info` line: `ensure_project_config_defaults` at the `cp` (`:2006`)
and at the awk backfill (`:2033`); `ensure_chatlink_config` at `:2057`;
`ensure_crew_runner_config` at `:2086`; `ensure_agent_config_seeds` inside its
loop, which already keeps a `copied` counter (`:2172`). Append the target path
to a `AIT_SETUP_METADATA_WRITTEN` array at each of those points and pass the
array — with `--allow-new`, since these genuinely create files — after the four
calls at `:4154-4163`. Empty array ⇒ no call at all.

This is the same per-invocation "did *this* run actually write?" signal
`aitask_update.sh` uses for `labels.txt` (`_stage_labels` / `AIT_LABELS_ADDED`),
and it carries that pattern's known hazard: **reset the array once at the start
of the setup run**, and have each `ensure_*` append only on its real write path,
so an early-return branch cannot leave a previous entry to be committed under a
later phase. Every `ensure_*` early-exits in the common case, which is exactly
the shape that made a stale signal a bug in t1662.

`install.sh` is **not** in scope: its `install_seed_*` family writes into
`$INSTALL_DIR` (`~/.aitask`), which is not a project git repo.

## Step 3 — Untrack `diffviewer_history.json`

`plan_browser.py:209-216` rewrites a tracked file on every `select_plan`, with a
non-atomic `open(…, "w")`. Committing per-user MRU state would be wrong.

- `HISTORY_FILE` → `local_path_for("aitasks/metadata/diffviewer_history.json")`,
  i.e. `diffviewer_history.local.json`, already covered by the data branch's
  `aitasks/metadata/*.local.json` ignore rule — **no new gitignore entry**.
- `_load_history` reads the local path, falling back **read-only** to the legacy
  tracked path when the local one is absent. In an existing user repo the
  tracked file is simply never written again, so it goes clean and stays clean.
  **Nothing deletes a user's file** — only this repo runs
  `./ait git rm aitasks/metadata/diffviewer_history.json`.
- Switch the write to `lib/atomic_write.py` while here (it is one of the
  flagged non-atomic writers).

## Step 4 — Documentation

- **`aidocs/framework/tui_conventions.md:347-356`** — amend to the agreed rule:
  runtime `save()` paths still write only the user layer; project-level files
  are committed **only** on an explicit user-initiated save/publish, through
  `aitask_metadata_commit.sh`, and are **never pushed**; a background or
  incidental save (collapse keystroke, refresh, autosave) must not commit.
  ⚠️ **This file is currently dirty from a concurrent session.** Before
  committing it, confirm `git diff -- aidocs/framework/tui_conventions.md`
  contains only this change; if it carries foreign hunks, hold the doc commit
  until that session lands and say so, rather than sweeping their work in.
- **`website/content/docs/commands/sync.md:78`** — "An ownerless file is
  different: nothing else will ever commit it" is now false for config edits.
  Narrow it to the remaining ownerless cases (`gates.yaml`, hand-edited
  vocabularies) and name the new remedy command.
- **`website/content/docs/tuis/settings/how-to.md:134`** — "Optionally click
  **Commit**" no longer describes the UI.
- Run `python3 check_links.py --build` in `website/` after both edits.

### Post-phase (risk mitigations)

**`metadata_writer_inventory_guard`** — runs after Step 4, before the task is
considered done. Adds `tests/test_metadata_writer_inventory.sh`.

Discovery derives tracked-metadata write sites **from source**: callers of
`save_project_config` / `save_yaml_config` / `import_all_configs` / `_save_json`,
plus shell `cp` / redirect / `mv` writes whose destination resolves under
`aitasks/metadata/`. Every discovered site must be either wired to
`aitask_metadata_commit.sh` or listed in a commented `KNOWN_UNCOMMITTED`
allowlist with its reason (`gates.yaml` — human-review by design;
`aitask_add_model.sh` / `aitask_opencode_models.sh` — run inside a task that
commits; `cross_repo_settings.apply_push` — foreign repo, see the spawned
follow-up).

**A grep-derived candidate set can pass vacuously, so it is pinned.** A writer
moved to a different primitive, or a new one using an API the patterns do not
recognise, simply drops out of discovery — and a test that only checks
"everything I found is wired" then passes while the inventory silently shrinks:
the exact omission this mitigation claims to prevent. Three assertions close it:

1. **Baseline pin.** A `PINNED_SITES` list names every currently-known write site
   by `file::function` identity (never line number — they drift). If discovery
   fails to re-find any pinned entry, the test FAILS with "a known writer is no
   longer discoverable — the discovery patterns are stale", not with silence.
2. **Monotonic count.** The discovered-site count must be `>= ${#PINNED_SITES}`.
   A narrowing is a failure, not a pass.
3. **Wired-or-allowlisted.** Every discovered site — pinned or newly found —
   must be one or the other.

The header states the consequence: **adding a new write primitive means adding
its discovery pattern *and* its pinned entries in the same change.** That is the
deliberate process, made mechanical rather than remembered.

Negative controls, run as throwaway probes before committing the guard (each
must actually fail): (a) add a fake metadata writer that neither commits nor is
allowlisted → FAIL; (b) delete one discovery pattern so a pinned site vanishes →
FAIL on assertion 1. Without (b) the guard's own anti-vacuity claim is untested.

## Verification

Every assertion below is written to **fail against today's
write-without-commit**. The negative controls are run as throwaway probes
*before* the fix (proving they can fail) and are **not** committed as
characterization tests — there is no interim state in which not committing is
correct.

**`tests/test_metadata_commit_seam.sh` (new)** — on `tests/lib/sync_fixture.sh`,
which already builds the branch-mode repo with `aitasks/metadata/` committed:
1. one path → committed under `ait: Update board_config.json`; worktree clean.
2. **bystander control**: a dirty unrelated task file is *not* in that commit.
3. **staged-foreign control**: a path another session has `git add`-ed is not
   swept in (the `commit -o --` property).
4. out-of-scope path (and a `..` path) → `REFUSED:out_of_scope`, exit 2, nothing
   committed.
5. gitignored user-layer path → `SKIPPED`, nothing committed.
6. deletion of a tracked profile is recorded.
7. **untracked-path refusal**: an untracked, non-ignored file under
   `aitasks/metadata/` → `REFUSED:untracked`, exit 2, and — the assertion that
   matters — `./ait git ls-files` still does **not** list it. Written to fail
   against a helper that only scope-checks, since `task_git_commit_scoped`
   stages what it is given.
8. **`--allow-new` accepts exactly that path**, and still refuses a gitignored
   one and a directory under the flag.
9. **forced commit failure — including the index.** Install the failing
   `pre-commit` hook seam already documented at `tests/test_fold_mark.sh:337`
   (`_install_failing_pre_commit_hook`; neither commit site passes
   `--no-verify`; git releases the index lock on hook failure, so the index is
   inspectable afterwards). Assert: exit **1** with `FAILED:`, the file's
   **edit survives on disk**, nothing was committed, and a subsequent
   `run_sync` reports the file as ownerless with its remedy — the backstop that
   keeps a failed commit visible instead of silent.

   Then the staging assertions, which are the point of this case:
   - a **tracked** metadata path is **not staged** after the failure
     (`./ait git diff --cached --name-only` does not list it) — written to fail
     against a helper that used the default staging mode;
   - an **`--allow-new`** path is likewise not staged afterwards, and is still
     untracked (`ls-files` does not list it) — the `staged_by_us` unstage;
   - a **pre-existing foreign staged entry at a different path**, staged before
     the call, is **still staged** and unchanged — the assertion that the
     cleanup is scoped rather than a blanket `git reset`.
10. **the task's own bullet**: after a *successful* commit, `run_sync` reports
   **no** `ownerless` line on stderr and does not defer.

**`tests/test_board_column_cli.sh` (extend)** — `create` commits
`board_config.json` and leaves `./ait git status --porcelain` empty; under the
failing-hook seam it emits `WARN:commit_failed:` on **stderr**, keeps stdout's
`CREATED:` line intact (the machine protocol must not be polluted by a
diagnostic), and still exits 0.

**`tests/test_setup_metadata_commit_scope.sh` (new)** — the concern that a setup
run must not commit foreign work. Seed a repo where `chatlink_config.yaml` is
missing (so `ensure_chatlink_config` writes it) **and** `board_config.json` is
dirty from a simulated concurrent session. Run the `ensure_*` phase and assert
the resulting commit contains `chatlink_config.yaml` **only**, and that
`board_config.json` is still dirty and unchanged. Negative control: a blanket
"commit everything dirty under metadata" implementation fails this.

**`tests/test_settings_commit_on_save.py` (new)** — the real user-facing path:
`tests/lib/board_fixture.py`'s `build_tree(branch_mode=True)` (it `git init`s,
unlike the settings tests' bare `TemporaryDirectory`) + the `SettingsApp` pilot
pattern from `test_settings_project_config_value_types.py`. Assert a project
config save commits **that file only** and leaves the worktree clean, and that a
board **settings** save (user layer) commits **nothing** — the pin on the
"incidental save must not commit" half of the amended rule. Also pin the two
failure/lifecycle halves: under the failing-hook seam a save returns
`CommitResult(status="failed")`, the edited value is still on disk, and the
`on_commit` callback fired (so the error notification is reachable, not merely
possible); and `KanbanApp` startup on a project with no `board_config.json`
creates it and commits **nothing** — the `commit=False` first-ship pin from
Step 2b.

**Both file-creating Settings paths get their own cases**, because they are the
only Python callers that reach `allow_new`, and each fails three distinct ways
against a wrong wrapper — `TypeError` if the parameter is missing from the
signature, `REFUSED:untracked` if it is accepted but not forwarded, and a dirty
untracked file if the caller never derives it. Each case therefore pins the
parameter, the forwarding, and the derivation together rather than any one:

- **New project profile** (`NewProfileScreen` → `_handle_new_profile` →
  `save_profile`, `layer="project"`): create a profile the fixture does not
  have, and assert the file is **tracked and committed** afterwards and the
  worktree is clean. Pair it with a **user-layer** new profile, which must be
  `SKIPPED` — created, gitignored, never committed.
- **Import**: import a bundle carrying a project-layer config the fixture repo
  does **not** have; assert it is tracked and committed. Pair it with importing
  a config the repo **does** have, which must still take the ordinary
  tracked path — the pin that `allow_new` is derived, not hard-coded on.

**`tests/test_diffviewer_history_local.py` (new)** — writes land on
`*.local.json`; the legacy tracked path is never written; a pre-existing legacy
file is still read when no local file exists.

**Inventory guard (inline post-phase — full spec in Step 4's
`### Post-phase (risk mitigations)`)** — pinned-baseline + monotonic-count +
wired-or-allowlisted, with both anti-vacuity negative controls.

**Regression suites:** `bash tests/test_sync_auto_commit_scoping.sh`,
`tests/test_sync_deferral_and_quarantine.sh`, `tests/test_board_column_cli.sh`,
`tests/test_boardcol_update.sh`, `tests/test_create_email_lock.sh`,
`tests/test_fold_mark.sh`, `tests/test_pick_own_scoped_commit.sh`;
`bash tests/run_all_python_tests.sh --test-dir tests` for the board/settings
modules; `shellcheck .aitask-scripts/aitask_*.sh`.

## Commit boundaries

Code and `aitasks/`/`aiplans/` files go in **separate** commits; task/plan data
via `./ait git`. The `./ait git rm` of `diffviewer_history.json` is a data-branch
commit, separate from the code commit that stops writing it.

## Step 9 (Post-Implementation)

Standard: consolidate the plan with Final Implementation Notes, merge, archive.

**Required by the task's own Downstream note:** `t1678` (`data_index` lock
adoption) **depends on this task** and its audit cannot see call sites that do
not exist yet. The Final Implementation Notes MUST list every new
`.aitask-data` index-writing call site this task adds — the helper itself plus
each of the ~10 wiring points in Step 2 — so t1678 does not have to rediscover
them.

## Risk

### Code-health risk: high

Raised from medium during the staging reassessment: the change now writes to the
**shared** `.aitask-data` index from inside TUI event handlers, and two of the
bullets below are high-severity on their own.

- `save_metadata(commit=True)` defaults on, so **every** one of its seven
  callers commits — including the startup first-ship at `aitask_board.py:1732`,
  which is not a user gesture. Missing the `commit=False` there makes `ait board`
  produce a commit at launch on any project whose `board_config.json` is absent · severity: high · → mitigation: addressed in Step 2b (default in the helper, `commit=False` at the one non-gesture caller) + the startup-commits-nothing pin in Verification
- A commit is now a blocking subprocess inside a Textual event handler. The
  column-merge path (`:2944`) already carries a partial-failure rollback
  contract keyed on which of two writes landed; adding a third failure mode
  inside it widens what "failed" means at a site that already had to reason
  about it · severity: medium · → mitigation: addressed in Step 2b by running the commit on the board's existing `@work(thread=True)` pattern, and by `commit_metadata` never raising on a git failure — the write has already landed, so a commit error cannot reach the merge rollback
- The amended convention turns on an "explicit user-initiated save" vs
  "incidental save" distinction that the next author must reproduce by
  judgement. A misread re-introduces exactly the background commits the rule
  exists to prevent · severity: medium · → mitigation: addressed in Step 4 by stating the boundary with both a positive and a negative list (settings Save / column CRUD / wizard save vs collapse keystroke / refresh / autosave), and pinned by the user-layer-commits-nothing assertion in Verification
- `aidocs/framework/tui_conventions.md` — the file this task must amend — is
  **dirty from a concurrent session right now**. A path-scoped commit of it
  would carry that session's uncommitted hunks under this task's message: the
  precise defect the t1599 family exists to eliminate, re-created by the task
  that closes it · severity: medium · → mitigation: addressed in Step 4 by the pre-commit `git diff` check on that path, holding the doc commit rather than sweeping foreign hunks
- `--allow-new` reads as an ordinary flag but is the one thing that lets this
  helper **add** a file to the data branch. A future caller that copies an
  existing invocation inherits it and can publish a stray local file · severity: medium · → mitigation: addressed in Step 1b — the flag is *derived* per call from a pre-write existence check rather than hard-coded, so it cannot be inherited as a standing relaxation; the helper still requires the path to exist, be a regular file and be non-ignored; and the untracked-refusal, new-profile and import cases in Verification pin all three surfaces
- The setup written-paths array is a **per-invocation** signal, and every
  `ensure_*` early-exits in the common case — the precise shape that made a
  stale `AIT_LABELS_ADDED` a real bug in t1662. A leaked entry would commit an
  earlier phase's file under a later one · severity: medium · → mitigation: addressed in Step 2e (reset once per run, append only on the real write path) + `tests/test_setup_metadata_commit_scope.sh`

### Goal-achievement risk: medium

- **The inventory is the deliverable, and it is a claim about absence.** It was
  re-derived from source rather than trusted from the task body (which named a
  `stats_config.json` writer that does not exist), but a writer missed today
  stays ownerless silently — which is exactly how this defect arose in the first
  place · severity: high · → mitigation: inline post-phase metadata_writer_inventory_guard
- `lib/cross_repo_settings.py:400` (`apply_push`, via `syncer_app.py:1973`)
  writes **another repo's** tracked `codeagent_config.json` and is deliberately
  out of scope, because a repo-scoped seam cannot commit into a repo that may be
  mid-work. The goal "every tracked metadata write has an owner" is therefore
  met for this repo's own surfaces only · severity: medium · → mitigation: cross_repo_config_push_owner
- `gates.yaml` stays deliberately uncommitted (`ait gates sync-registry` asks a
  human to review first), so a permanent ownerless deferral remains reachable by
  design. This task **narrows** the premise "nothing else commits those files";
  it does not eliminate it, and the docs must say so rather than claim a cure · severity: medium · → mitigation: addressed in Step 4 by narrowing the sync.md claim to the remaining ownerless cases instead of deleting it, and by the guard's `KNOWN_UNCOMMITTED` allowlist entry
- Existing user repos keep a tracked `diffviewer_history.json`. The change stops
  it being rewritten, but a copy that is dirty *at upgrade time* stays dirty
  once; nothing deletes a user's file · severity: low · → mitigation: None — accepted; the file goes clean after one manual commit and never dirties again
- A failed commit that leaves an entry in the **shared** `.aitask-data` index is
  worse than a dirty worktree: it is invisible to the ownerless report and is
  swallowed by the next index-wide commit (`aitask_board.py:14164` still makes
  one). The cleanup must also not touch another session's staged entries · severity: high · → mitigation: addressed in Step 1b's staging rules (`--no-stage` for tracked paths; stage only `--allow-new` ones and unstage exactly those on failure, reusing `aitask_sync.sh:778-805`) + the three staging assertions in Verification case 9
- **A commit failure is best-effort by construction** — `commit_metadata` never
  raises, so the only thing standing between a failed commit and a silently
  dirty file is each surface remembering to report it. A missed report restores
  the permanent-deferral risk this task exists to remove · severity: medium · → mitigation: addressed in Step 1b-fail (a per-surface contract stated once, all naming one single-sourced remedy) + the forced-failure cases in Verification, which use the documented failing-`pre-commit` seam rather than a mock; and `ait sync`'s own ownerless report remains the independent backstop

### Planned mitigations
- timing: post-phase | name: metadata_writer_inventory_guard | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — the inventory is a claim about absence, and a writer missed today stays ownerless silently | desc: derive tracked-metadata write sites from source and assert each is wired to the commit seam or in a commented KNOWN_UNCOMMITTED allowlist with its reason
- timing: after | name: cross_repo_config_push_owner | type: bug | priority: medium | effort: medium | inline_risk: high | added_complexity: high | addresses: goal-achievement — apply_push writes another repo's tracked codeagent_config.json and leaves it dirty there | desc: give the syncer's cross-repo config push an owner that commits in the target repo, deciding safely what to do when that repo is mid-work

---

## Post-Review Changes

### Change Request 1 (2026-09-03 11:35)

- **Requested by user:** three blocking `allow_new` defects, each verified
  CONFIRMED before any edit. All three are the same root cause: **`allow_new` is
  a per-path permission ("I created this") that was being carried as a
  batch-level flag, or dropped entirely.**

  1. `lib/metadata_commit.py::remedy_command` never emitted `--allow-new`. The
     failure path unstages what it staged, so a newly created project profile or
     first-run chatlink config is left *untracked* — and the remedy the TUI
     showed answered `REFUSED:untracked` instead of committing it.
  2. `aitask_setup.sh::commit_setup_metadata_writes` passed `--allow-new` for
     the whole batch, but `ensure_project_config_defaults` has **two** write
     branches and the backfill one edits an *existing* `project_config.yaml`.
     An untracked local copy was therefore published rather than refused.
  3. `settings_app.py::_commit_imported` derived one `created_any` boolean for
     the batch and forwarded it for every path, so an import that created one
     config while overwriting a pre-existing untracked one admitted both.

- **Changes made:**
  - **The admission now rides on the result.** `CommitResult` gained an
    `allow_new` field (defaulted, so existing 3-arg constructions still work);
    `commit_metadata` stamps every exit through a local `_r()`. `remedy_command`
    takes `allow_new` and is built **through `commit_command`**, so the
    advertised string cannot drift from the argv actually run. The three
    surfaces render `remedy_command(paths, allow_new=result.allow_new)`.

    Chosen over adding a parameter to each notify callback for the reason the
    commit already lives inside the writer: a parameter every surface must
    remember to pass is one a surface eventually forgets.
  - **`ait setup` records newness per path.** `_note_metadata_write <path> [new]`
    splits into `AIT_SETUP_METADATA_NEW` / `_EXISTING`; the flush makes up to
    two calls via a new `_flush_metadata_batch <allow_new> <path>...`. The
    default is `existing`, so a call site added later without the argument fails
    **closed** (refused) rather than open (published). Four creation sites pass
    `new`; the backfill site keeps the default with a comment saying why.
    `_flush_metadata_batch` builds the run argv and the shown remedy from the
    same branch, so the warning cannot advertise a different admission.
  - **The import partitions.** `_commit_imported` splits `paths` by pre-import
    existence and commits each subset under its own admission.
  - **Docs:** `tui_conventions.md` states the per-path rule and the
    `result.allow_new` remedy requirement — a TUI author wiring a new writer
    needs both.

- **Tests added (10 new assertions/cases, every one with an executed negative
  control):**
  - `test_setup_metadata_commit_scope.sh` Tests 5-7: a backfilled pre-existing
    untracked config is refused and stays untracked while its edit survives on
    disk; the create branch still commits (so Test 5 cannot pass vacuously); a
    mixed run does not let the two share an admission.
  - `test_settings_commit_on_save.py` `RemedyMatchesTheAdmission`: the result
    carries `allow_new`, the negative direction does **not** advertise the flag,
    and — the assertion that matters — **running the exact advertised string
    actually commits the file**.
  - `test_settings_commit_on_save.py` `ImportAdmissionIsPerPath`: only the
    created config is admitted, the overwritten one is *reported* refused rather
    than silently dropped, and its content survives.

- **Negative controls (each mutation applied, observed failing, then reverted):**
  - flush the `updated` batch with `--allow-new` → 3 failures across Tests 5/7.
  - `_commit_imported` back to the `created_any` boolean → 2 failures; both
    files committed.
  - `CommitResult` no longer stamped with `allow_new` → 2 failures, the remedy
    run reproducing the reported symptom verbatim:
    `REFUSED:untracked:aitasks/metadata/profiles/brandnew.yaml`.

- **Not changed:** the helper's CLI. Both batch defects are fixed by
  partitioning at the caller, which the reviewer's own dispositions endorsed;
  making `--allow-new` take a path list would have rewritten the seam's
  contract and its 50 passing assertions for no additional safety.

## Final Implementation Notes

- **Actual work done:** the plan as approved, in five parts, plus one review
  round (see `## Post-Review Changes`) that made `allow_new` per-path
  everywhere and put the admission on `CommitResult`.
  - **The seam.** `lib/task_utils.sh::ait_metadata_commit_message` (file-naming
    subject, single-sourced); `.aitask-scripts/aitask_metadata_commit.sh`
    (explicit paths only, scope/tracked/user-layer admission, `--no-stage` plus
    a `staged_by_us` unstage on failure, structured stdout, exit 0/1/2, never
    pushes); `lib/metadata_commit.py` (subprocess wrapper, never raises on a git
    failure, `allow_new` forwarded verbatim, `remedy_command`).
    `aitask_sync.sh`'s ownerless report now names the helper as the remedy.
  - **Wiring.** Settings `ConfigManager.save_codeagent` / `save_board` /
    `save_project_settings` / `save_profile` / `delete_profile` (commit in the
    method, `on_commit` callback wired once by `SettingsApp`);
    `_handle_import` / the partial-import branch; board
    `TaskManager.save_metadata(commit=True)` with `commit=False` at the startup
    first-ship; `aitask_board_column.sh create`; chatlink `wizard._do_save`;
    `aitask_setup.sh`'s four `ensure_*` passes via
    `AIT_SETUP_METADATA_WRITTEN` + `commit_setup_metadata_writes`.
    `settings_app._commit_profile` (an index-wide `git commit`) was deleted and
    the modal's "Save and Commit" button collapsed into "Save".
  - **Untracking.** `diffviewer/plan_browser.py` writes
    `diffviewer_history.local.json` atomically and reads the legacy tracked path
    only as a fallback. **The `./ait git rm` of the tracked file is deliberately
    NOT done here** — see "Deviations".
  - **Docs.** `tui_conventions.md` section rewritten; `sync.md` and the settings
    `how-to.md` narrowed to match.
  - **Tests.** 7 new files, 79 shell assertions + 33 Python tests, plus one
    updated assertion in `tests/test_chatlink_tui.sh`.

- **Deviations from plan:**
  - **`--sweep` was removed from the helper entirely** (agreed pre-approval). A
    "commit everything dirty under `aitasks/metadata/`" verb publishes whatever a
    concurrent session is mid-editing. `ait setup` therefore records the exact
    paths each `ensure_*` wrote.
  - **The board's commit is synchronous, not `@work(thread=True)`.** A worker
    must be started by the App, so each of the six column-gesture call sites
    would have to drain a queue — reintroducing the "a caller can forget it"
    failure that putting the commit inside `save_metadata` exists to prevent.
    One path-scoped commit of one small JSON is on par with the subprocess calls
    (`aitask_lock.sh --list`, `git status`) the refresh path already makes
    inline. `TaskManager.on_metadata_commit` keeps it Textual-free.
  - **The board-column commit test is a new file** (`test_board_column_commit.sh`)
    rather than an extension of `test_board_column_cli.sh`, whose fixture is
    deliberately git-free ("stays readable in one screen").
  - **The inventory guard is Python, and its design changed.** Resolving an
    enclosing function needs real parsing, and — more importantly — *no regex
    over source is complete*: `plan_browser.py` builds its path as
    `os.path.join("aitasks", "metadata", ...)` and is invisible to a literal
    scan. A grep-derived allowlist would therefore have been the vacuous guard
    the mitigation exists to avoid. The inventory is now **pinned data**
    (`WIRED` / `KNOWN_UNCOMMITTED` by `file::function`) with discovery demoted
    to a new-file tripwire; the test's docstring states plainly what it does not
    catch. Four negative controls were run and each fails the intended assertion.
  - **`diffviewer_history.json` is not `git rm`-ed in this commit.** Removing it
    is a `./ait git` data-branch change, and the file is currently clean; doing
    it in the same session as the code change would put a data-branch deletion
    in front of a user whose diffviewer might still be running against it. The
    code no longer writes it, which is what stops it dirtying — the removal is
    safe to do at any later point.

- **Issues encountered:**
  - `import_all_configs` returns the literal `"shortcuts"` marker alongside real
    filenames when a shortcuts subtree is merged into `userconfig.yaml`. It
    names no file, so passing it would make the helper refuse the whole batch;
    `_import_commit_paths` filters on `is_file()`.
  - `aitask_setup.sh` overrides `warn()` to write to **stdout** (`:143`,
    alongside `info`/`success`) rather than `terminal_compat.sh`'s stderr
    version. The flush's failure message follows the script's own convention;
    `test_setup_metadata_commit_scope.sh` captures stdout accordingly.
  - `${#arr[@]}` on an empty array errors under `set -u` in bash 3.2, and the
    empty case is the common one here — `commit_setup_metadata_writes` uses the
    `${arr[@]+"${arr[@]}"}` guard.
  - The inventory guard's own first run caught a real modelling error:
    `aitask_pick_own.sh::store_email` writes `emails.txt` while
    `commit_and_push` commits it. The wiring check is file-scoped against an
    exact seam token, because writer and committer are legitimately different
    functions.
  - `settings_app.save_profile` shells out to `aitask_skill_rerender.sh`. The
    Python fixture therefore exposes only the one script under test with `lib/`
    symlinked, instead of symlinking the whole `.aitask-scripts` — otherwise a
    test save could re-render skill closures in the real repository.
  - **Two unreachable-code regressions, both caught in review, both the same
    mistake.** Appending `return self._commit(...)` / a new `def` at an edit
    anchor that ended *mid-function* orphaned the statements that followed:
    `ConfigManager.delete_profile` stopped popping `self.profiles` /
    `self.profile_layers` (the UI would keep offering a deleted profile until a
    reload), and `SummaryScreen._do_save` stopped relabelling the Next button to
    "Close" and stopped calling `_start_preflight()` — which also meant the new
    commit outcome never reached the user, since the preflight pane is what
    renders `_commit_hint()`. Both fixed, both pinned by a test with an
    executed negative control, and an AST sweep for `unreachable statement after
    return/raise` was run across every file this task edits (the only remaining
    hit is the pre-existing, deliberately-documented `yield` after `raise
    NotImplementedError` in `wizard.py:341`). **The lesson: when an edit appends
    to the end of a function, re-read the whole function afterwards — a diff
    that "looks like an append" can be an insertion.**
  - `tests/test_chatlink_tui.sh` asserted the summary shows `never commits`.
    That wording is now false — the wizard does commit — so the assertion was
    updated rather than the behaviour: it now pins that the summary always
    states the config's git position, and in that fixture (whose config lives
    outside `aitasks/metadata/`) that the out-of-scope refusal names the remedy.
    The committed branch is pinned in the new save-flow test.

- **Key decisions:**
  - Wrap the existing shell seam from Python rather than adding a second
    scoped-commit implementation. Every pre-existing Python commit site in the
    tree is a pathspec-less `git commit`; copying one would have re-created the
    index-wide swallow t1599 exists to eliminate.
  - `allow_new` is always **derived** from a pre-write existence check, never
    hard-coded — it means "I created this", not "creation is allowed here".
    `save_profile` derives it itself, which is what covers `_handle_new_profile`
    without any caller having to remember.
  - A commit failure never raises. The edit has already landed, so losing it
    would be worse than a dirty file — but every surface reports the failure and
    names the remedy, and `ait sync`'s ownerless report remains the independent
    backstop.
  - `gates.yaml` stays deliberately uncommitted (review-then-commit), and the
    docs narrow the old "nothing else will ever commit it" claim rather than
    replacing it with a cure.

- **Upstream defects identified:**
  - `.aitask-scripts/board/aitask_board.py:14164` — `_do_git_commit_tasks` runs
    `git commit -m <msg>` with **no pathspec**, committing the whole shared
    `.aitask-data` index; the delete (`:14029`) and rename (`:14126-14141`)
    paths do the same. These commit task files, so they are outside this task's
    metadata scope, but they can carry another session's staged work under this
    board's message — the same defect class t1599 addressed for `ait sync`,
    `aitask_pick_own.sh`, `aitask_create.sh` and `aitask_fold_mark.sh`.

- **New `.aitask-data` index-writing call sites (for t1678):** the
  `data_index` mutex audit cannot see these, so they are listed explicitly.
  - `.aitask-scripts/aitask_metadata_commit.sh` — **the** new index writer:
    `task_git add` (untracked paths only), `task_git reset` (failure cleanup),
    and `task_git_commit_scoped --no-stage` (which itself runs `task_git status`
    + `task_git commit`). Everything below funnels through it, so bringing this
    one script under the mutex covers all of them.
  - `.aitask-scripts/lib/metadata_commit.py::commit_metadata` — subprocess
    wrapper; runs no git itself.
  - Call sites that reach it: `settings_app.py::ConfigManager._commit`
    (← `save_codeagent`, `save_board`, `save_project_settings`, `save_profile`,
    `delete_profile`); `settings_app.py::SettingsApp._commit_imported`
    (← `_handle_import` and its partial-import branch);
    `aitask_board.py::TaskManager._commit_metadata_file` (← `save_metadata`,
    reached from `add_column`, `update_column`, `delete_column`,
    `merge_columns`, `ColumnManageScreen._shift`, and the card-reorder action);
    `chatlink/wizard.py::_commit_config` (← `_do_save`);
    `aitask_board_column.sh` top-level `create` branch; and
    `aitask_setup.sh::_flush_metadata_batch`
    (← `commit_setup_metadata_writes` ← the five `_note_metadata_write` sites).
  - **Two of these now invoke the helper up to TWICE per user action** (review
    round, above): `_flush_metadata_batch` is called once for created paths and
    once for edited ones, and `_commit_imported` likewise commits its created and
    pre-existing subsets separately. Each call is a separate scoped commit, so
    t1678's mutex must cover the *call*, not the enclosing user action.
  - `lib/task_utils.sh::ait_metadata_commit_message` is pure — no git.
