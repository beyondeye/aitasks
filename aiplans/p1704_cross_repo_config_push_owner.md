---
Task: t1704_cross_repo_config_push_owner.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1704 — Give the cross-repo config push an owner that commits in the target repo

## ⚠️ Re-verify before implementing — this plan was written against a moving base

Approved 2026-09-03 and **deliberately deferred**: at approval time **t1702** was
in flight, uncommitted, in the same working tree, holding edits to both files this
plan modifies most. t1704 now carries `depends: [1702]`.

`fast`'s `plan_preference` for a parent task is `use_current`, so a re-pick will
**skip verification and use this plan as-is**. Do not let it. Re-derive these two
points against the landed tree first:

1. **§2's anchor is stale as written.** It says the `--expect` comparison goes
   "just before `task_git_commit_scoped`". t1702 replaced that call site in
   `aitask_metadata_commit.sh` with `ait_commit_paths_staging_untracked`
   (a new `lib/task_utils.sh` function, with `ait_unstage_staged_by_us` and an
   `AIT_STAGED_BY_US` global unwound by an EXIT trap armed in the caller). The
   guard must sit before *that* call, and its interaction with the staging
   trap — a `REFUSED:changed` exit must leave nothing staged — has to be
   re-checked, not assumed.
2. **§1's edit site moved.** t1702 added ~74 lines to `lib/task_utils.sh` around
   the commit helpers. Re-locate the `AIT_GIT_INPROGRESS_STATES` extraction and
   re-confirm that `assert_data_worktree_clean` and `task_git_health` are still
   its only two call sites.

Also re-check whether t1702's new `lib/task_commit.py` overlaps
`lib/metadata_commit.py` in a way that changes where §3's `preflight_metadata` /
`expect` belong.

Everything else in this plan — the decision matrix, the concurrency guard, the
`clear_mask` failure policy, the test matrix — was derived from code t1702 does
not touch and should still hold.

## Context

t1677 gave every tracked `aitasks/metadata/*` write in **this** repo an owner that
commits it, via `.aitask-scripts/aitask_metadata_commit.sh` and its Python wrapper
`lib/metadata_commit.py::commit_metadata`. One writer was deliberately left out and
sits in the inventory guard's `KNOWN_UNCOMMITTED` allowlist:

`lib/cross_repo_settings.py::apply_push` — reached from the syncer's Settings-tab
push (`syncer_app.py::_push_apply_worker`) — writes **another repo's** tracked
`codeagent_config.json` through `import_all_configs` and returns `None`. The file
is left dirty in a repo the pushing session does not own. `ait sync` in that repo
then refuses to attribute it to any task (t1599_3), so it becomes a permanent
rebase deferral there — the exact ownerless state t1677 exists to end, relocated
into someone else's checkout.

Two facts found during exploration shape the design:

- `metadata_commit.commit_command(root=…)` **already** targets a foreign root
  (`<root>/.aitask-scripts/aitask_metadata_commit.sh`, `cwd=<root>`) and no caller
  uses it yet. It was built for this follow-up. Reuse it; do not fork it.
- The commit itself is the easy half. The hard half is deciding what is safe when
  the target repo is mid-work — and **reporting** whatever is decided, because a
  silent dirty file in someone else's repo is the defect, not the commit.

Two policy calls were settled with the user during planning:

- **Legacy-layout target (no `aitask-data` branch)** → **refuse before writing**.
  Committing there lands on whatever code branch that repo has checked out.
- **Where the check runs** → **apply time only**. `plan_push` and `PushOutcome`
  are untouched; no extra git subprocess per destination during the wizard.

## Decision matrix (the substance of this task)

Preflight is taken in the destination repo **immediately before** the write. Every
outcome is reported per destination on the results screen; none is silent.

| Destination state | Decision |
|---|---|
| branch mode, target config tracked & clean | write, then path-scoped commit there. **Never pushes.** |
| target config absent (we create it) | write, commit with `--allow-new` |
| target config **tracked & dirty** (their session mid-edit) | **refuse before writing** — their edit is preserved byte-for-byte |
| target config **untracked but present** | **refuse before writing** — unclassified foreign content |
| target has other **staged** content | proceed; `commit -o -- <path>` never includes it (already guaranteed by `task_git_commit_scoped`) |
| data worktree mid rebase/merge/cherry-pick/revert/bisect | **refuse before writing** |
| data worktree on a detached HEAD | **refuse before writing** |
| **legacy layout** (no `.aitask-data`) | **refuse before writing** |
| target's own commit helper missing / too old / not a repo | **refuse before writing** |
| layer is `local` (gitignored there) | write; nothing to commit — reported as such |
| target's data branch behind its remote | irrelevant: the commit is local and the seam never pushes. Result line says "not pushed". |
| a concurrent writer in the target edits the file **during** the push | detected and **refused**, never published — see "Concurrency" below |

Target-repo *code* branch is irrelevant in branch mode — the commit lands on
`aitask-data` regardless — which is why legacy is the only branch-sensitive case
and is refused.

## Concurrency: the preflight verdict must survive until the commit

A preflight taken before `import_all_configs` is only a snapshot, and
`task_git_commit_scoped` commits with `git commit -o -- <path>`, which
`lib/task_utils.sh:322` documents as a **partial commit that takes the path's
WORKTREE content** at commit time. So a naive preflight→write→commit sequence has
two real defects, not one:

1. a racer who dirties the file after the clean verdict has their edit
   **overwritten** by our write;
2. a racer who edits after our write has their bytes **published under
   `ait: Update codeagent_config.json`** — the framework attributing content it
   never wrote, which is the precise failure t1599_3 built a quarantine to stop.

Both are closed by a **compare-and-commit guard**, and (2) — the damaging one —
is closed inside the helper, not across a process boundary:

- **Write side.** `apply_push` snapshots the destination file's bytes
  *immediately before* calling `preflight_metadata` and re-reads them
  *immediately after it returns*. A mismatch means a writer landed inside the
  preflight subprocess's window → `refused` / `dest_mid_work`, **nothing
  written**, their edit intact. This is the wide window (a subprocess, tens of
  ms); what remains is a same-process gap of a few statements.
- **Commit side.** After the write, `apply_push` reads back exactly what landed
  and hands those bytes to the commit helper as `--expect <path>=<file>`. The
  helper re-compares with `cmp -s` **immediately before** `task_git_commit_scoped`
  and answers `REFUSED:changed:<path>` (exit 2, nothing staged, nothing
  committed) if the worktree no longer holds them. The remaining window is
  helper-internal — between its own `cmp` and git's read — with no I/O in
  between.

**What this does not buy, stated plainly.** It is detect-and-refuse, not mutual
exclusion. A true mutex would have to be taken by *every* metadata writer in the
destination repo — including that repo's own Settings TUI, which is the writer
the race is actually against — so a lock taken only here would serialize
push-against-push while leaving push-against-local-edit exactly as it is, at the
cost of a lock lifecycle straddling a Python/shell boundary. The guard above
covers **every** concurrent writer for the outcome that matters: the framework
never publishes bytes it did not write, and never silently discards an edit it
found. Making all destination writers share `lib/stale_lock.sh` is a separate,
larger change; it is named as a follow-up below rather than half-done here.

## Changes

### Pre-phase (risk mitigations)

1. `[characterize_inprogress_state_guard]` Before touching `lib/task_utils.sh`,
   add a characterization test that plants each of the six in-progress git states
   (`rebase-merge`, `rebase-apply`, `MERGE_HEAD`, `CHERRY_PICK_HEAD`,
   `REVERT_HEAD`, `BISECT_LOG`) in a branch-mode data worktree and asserts
   `assert_data_worktree_clean` refuses a mutating `task_git` call on **every**
   one. Add it to `tests/test_task_git.sh` (already the home of `task_git`'s
   topology tests). Today only `rebase-merge` is exercised anywhere in the suite
   (`tests/test_task_push.sh:505`, `tests/test_sync_deferral_and_quarantine.sh:349`),
   so an extraction that silently dropped one of the other five would pass green.
   Run it and see it pass **before** the constant extraction in step 1 below, and
   again after — that before/after pair is what makes the refactor provably
   behaviour-preserving rather than merely plausible.

### 1. `.aitask-scripts/lib/task_utils.sh` — one named constant, two accessors

The six in-progress git state names are currently spelled out twice
(`assert_data_worktree_clean`, `task_git_health`). A third copy is not acceptable.

- Add `AIT_GIT_INPROGRESS_STATES=(rebase-merge rebase-apply MERGE_HEAD
  CHERRY_PICK_HEAD REVERT_HEAD BISECT_LOG)` and use it at both existing sites.
- Add `ait_data_mode()` → prints `branch` or `legacy` (wraps
  `_ait_detect_data_worktree`; avoids reaching into `_AIT_DATA_WORKTREE` from
  another script).
- Add `ait_data_inprogress_state()` → prints the first in-progress state found in
  `task_git rev-parse --absolute-git-dir`, or nothing. Works in both modes.

### 2. `.aitask-scripts/aitask_metadata_commit.sh` — a `--preflight` mode

New mode; the commit path is unchanged. Same path scope-check (fail-closed
`REFUSED:out_of_scope`), same `_is_ignored` / `_is_tracked` helpers, so there is
one resolution ladder rather than a parallel one in Python.

```
aitask_metadata_commit.sh --preflight <path>...
```

stdout (a data channel, as the rest of the script already documents):

```
MODE:branch|legacy
BRANCH:<name>|DETACHED
MIDOP:<state>                       # emitted only when stuck
STATE:<path>:clean|dirty|untracked|ignored|absent
```

Exit `0` inspected, `2` scope refusal, `1` git could not be inspected (prints
`FAILED:<detail>`). `dirty` is `task_git status --porcelain -- <path>` being
non-empty. `--preflight` and a commit are mutually exclusive; it writes nothing.

**Also new, on the commit path: `--expect <path>=<file>`** (repeatable). Just
before `task_git_commit_scoped`, the helper runs `cmp -s "<file>" "<path>"` for
each entry and, on any mismatch or a vanished path, prints
`REFUSED:changed:<path>` and returns 2 having staged and committed nothing.
`cmp -s` rather than a hash: it needs no new library (and therefore no
`tests/lib/test_scaffold.sh` baseline entry — see `shell_conventions.md`), is
exact for binary content, and `aitask_note.sh:602` already establishes it here.

Fail-closed contract: **if `--expect` is passed at all, every path that survives
the scope/ignore/tracked filters must have an entry**, else
`REFUSED:expect_incomplete` — a partially-guarded commit is the shape that looks
safe and is not. Omitting `--expect` entirely keeps today's behaviour, so the
three existing callers (`settings_app`, `aitask_board`, `chatlink/wizard`) are
untouched.

### 3. `.aitask-scripts/lib/metadata_commit.py`

- New `PreflightResult = namedtuple("PreflightResult", "status mode branch midop states detail")`;
  `status` ∈ `ok | refused | failed`, `states` a `dict[path -> state]`.
- New `preflight_metadata(paths, *, root=None, env=None, timeout=…)` — same
  subprocess shape and same never-raises contract as `commit_metadata`; an
  unparseable/old/missing helper returns `failed`, never `ok`.
- Add an `expect=None` parameter to `commit_metadata` — a
  `{repo_relative_path: local_file_holding_expected_bytes}` mapping, forwarded as
  `--expect` pairs. New status `raced` for `REFUSED:changed:<path>`, distinct
  from `refused`; `REFUSED:expect_incomplete` maps to `failed` (a programmer
  error, not a race).
- Add an `env=None` parameter to `commit_metadata` (forwarded to
  `subprocess.run`). Default `None` = inherit → existing three callers unchanged.
  Needed because the helper's `METADATA_PREFIX` reads `${TASK_DIR:-aitasks}`, and
  `TASK_DIR`/`METADATA_DIR` leaking from the pushing session would point it at the
  wrong tree — the same hazard `cross_repo_settings.resolver_env()` already exists
  to close.
- `commit_command` (pure resolution seam) gains nothing.

### 4. `.aitask-scripts/lib/cross_repo_settings.py` — `apply_push` gains an owner

New reason constants, alongside the existing `REASON_*`:
`dest_mid_work`, `dest_untracked_config`, `dest_mid_operation`,
`dest_detached_head`, `dest_legacy_layout`, `dest_commit_unavailable`.

New typed return (the module's existing "never a bare bool" rule):

```python
@dataclass(frozen=True)
class ApplyOutcome:
    kind: str            # committed | nothing_to_commit | user_layer_only
                         # | refused | commit_failed | commit_raced
    wrote: bool          # whether any config file reached disk
    mask_kept: bool      # a requested clear_mask was deliberately NOT performed
    reason: str | None   # a REASON_* for refused / commit_failed / commit_raced
    detail: str | None   # human detail: branch, git message, remedy command
```

`apply_push` becomes, in order:

1. Compute the repo-relative paths this call will touch —
   `aitasks/metadata/codeagent_config.json` for `project`, the `.local.json` for
   `local`, plus the `.local.json` when `clear_mask` is set. Constant strings from
   `PROJECT_CONFIG_NAME` / `LOCAL_CONFIG_NAME`; they must agree with the literal
   `dest_metadata_dir()` already returns.
2. `existed = {p: (dest_root / p).is_file() for p in paths}` and
   `before = {p: read_bytes_or_None(p)}` — both taken **before** anything else.
   `existed` is the only honest way to derive `allow_new`; `before` opens the
   write-side compare-and-commit bracket.
3. `preflight_metadata(paths, root=dest_root, env=resolver_env())` and apply the
   matrix above. Any refusal returns `ApplyOutcome(kind="refused", wrote=False, …)`
   **without calling `import_all_configs`**, so a mid-work target keeps its bytes.
4. Re-read the same paths and compare against `before`. Any difference → a writer
   landed inside the preflight window → `refused` / `dest_mid_work`, still
   nothing written.
5. The existing `import_all_configs(...)` write, unchanged.
6. Read back what actually landed, spill each path's bytes to a
   `tempfile.NamedTemporaryFile` (cleaned up in a `finally`), and call
   `commit_metadata(committable_paths, allow_new=…, root=dest_root,
   env=resolver_env(), expect={path: tmpfile})` where `committable_paths` excludes
   the `ignored` ones. Map its `CommitResult.status`: `committed`→`committed`,
   `nochange`→`nothing_to_commit`, `skipped`/empty set→`user_layer_only`,
   `raced`→`commit_raced`, `refused`/`failed`→`commit_failed`. The last two carry
   `remedy_command(...)` prefixed with `cd <shlex.quote(root)> && ` (the seam
   builds the command body; only the `cd` is added, so the advertised command
   cannot drift).
7. **Then, and only on a durable outcome, the `clear_mask` block.** This is the
   part the ordering exists for. Clear the local override **only** when the
   commit status was `committed` or `nochange` (`nochange` = git verified the
   destination already has that content committed — equally durable). On
   `commit_failed` or `commit_raced`, **skip the clear entirely**, set
   `mask_kept=True`, and report a retryable partial.

   Why: clearing the mask changes the destination's *effective* value. Doing that
   while the project file sits uncommitted (or, worse, holds a racer's bytes)
   produces a state that is neither the promised committed outcome nor the
   existing safe partial — the repo would start using a value that only exists as
   a dirty file. Keeping the mask preserves the module's standing guarantee that
   a failure leaves the effective value *exactly as it was*, and a re-run
   converges: `plan_push` still reports `masked` and the project write is
   idempotent.

`PushPartialError` (raised when the clear itself fails, after a successful
commit) gains a `commit_kind` attribute so the partial path still reports what
happened to the commit. The docstring's `project first, then clear local`
contract is preserved and extended: **write project → verify → commit project →
clear local only if the project write is durably owned.**

### 5. Syncer rendering

- `syncer_app.py::_push_apply_worker` — capture the `ApplyOutcome` and render one
  line per kind, e.g. `applied to the project layer and committed there (not
  pushed)`, `not applied: that repo has uncommitted changes to
  codeagent_config.json`, `applied but the commit failed there: … — clear it with:
  cd … && …`.
- `syncer/settings_screens.py:459` — the results screen's footer currently reads
  *"Nothing was committed — review and commit the changed config in each
  destination repo."* That becomes false with this change and must be replaced
  with wording that points at the per-destination lines and notes nothing is
  pushed.

### 6. Tests

**`tests/test_metadata_writer_inventory.py`** — move
`.aitask-scripts/lib/cross_repo_settings.py::apply_push` out of
`KNOWN_UNCOMMITTED` and into `WIRED` with seam token `"commit_metadata("`
(the token that must appear in that file). Required by the task.

**`tests/test_cross_repo_push_commit.py` (new)** — real git fixtures in the
production branch-mode topology (`.aitask-data` + an `aitasks` symlink + a
`.aitask-scripts/` carrying only `aitask_metadata_commit.sh` and a `lib` symlink),
built the way `tests/test_settings_commit_on_save.py` builds its own. They are
deliberately **not** shared: that fixture `chdir`s into the repo under test, and
the whole point here is that cwd stays elsewhere while the seam targets a foreign
root. One case per matrix row, each written to fail against today's
write-without-commit:

1. clean branch-mode target → `kind == "committed"`; `git show --name-only HEAD`
   is exactly the one config path; subject is `ait: Update codeagent_config.json`;
   the data worktree is clean afterwards. *(Negative control: today returns `None`
   and leaves the file dirty — both assertions fail.)*
2. foreign **staged** content in the data worktree → it is absent from the commit
   and still staged and uncommitted afterwards.
3. target config **dirty** → `refused` / `dest_mid_work`; the target's bytes are
   unchanged; no new commit on the data branch. *(Control: today the bytes are
   overwritten.)*
4. mid-merge (`MERGE_HEAD` planted in the data worktree's real gitdir) →
   `dest_mid_operation`, nothing written.
5. detached data-worktree HEAD → `dest_detached_head`, nothing written.
6. legacy-layout target → `dest_legacy_layout`, nothing written.
7. target with no commit helper at all → `dest_commit_unavailable`, nothing
   written (pins fail-closed against version skew).
8. `layer="local"` → written, `user_layer_only`, no new commit on the data branch.
9. project config **absent** → created and committed (the `--allow-new` path).
10. project config present but **untracked** → `dest_untracked_config`.
11. `clear_mask` whose local clear fails **after a successful commit** →
    `PushPartialError` with `commit_kind == "committed"` **and** the project write
    already on the data branch (pins the step-7 ordering).
12. commit fails (pre-commit hook exits 1, the documented seam this repo's tests
    already use) → `commit_failed`, the write survives on disk, and `detail`
    carries a runnable `cd … && …` remedy.

**Concurrency cases (fault injected through documented seams — deterministic, no
sleeps or thread races):**

13. **Write-side race.** Wrap `metadata_commit.preflight_metadata` so it returns
    the real clean verdict *and* rewrites the destination config as a side effect
    — a racer landing inside the preflight window. Assert `refused` /
    `dest_mid_work`, `wrote is False`, and the racer's bytes survive byte-for-byte.
    *Negative control:* with the step-4 re-read removed, the same injection
    clobbers the racer — so the assertion can fail.
14. **Commit-side race — the damaging one.** Wrap
    `metadata_commit.commit_metadata` so it mutates the destination file and then
    **calls through to the real function**, which drives the real helper with the
    real `--expect` value. Assert `commit_raced`, no new commit on the data
    branch, and the racer's bytes still on disk. *Negative control:* the same
    injection with `expect=None` commits, and `git show HEAD:<path>` returns the
    racer's bytes under `ait: Update codeagent_config.json` — i.e. the control
    reproduces exactly the misattribution the guard exists to prevent.
15. **A raced commit keeps the mask.** Case 14 with `clear_mask=True`: assert the
    local override is still present, `mask_kept is True`, and the destination's
    effective value is unchanged. Same assertion for case 12
    (`commit_failed` + `clear_mask`). *Negative control:* with the step-7 gate
    removed, the override is gone while the project file is dirty.

**`tests/test_metadata_commit_seam.sh`** also gains direct `--expect` coverage:
a matching file commits; a stale file answers `REFUSED:changed:<path>` with exit
2, no new commit and nothing left staged; `--expect` naming only some of the
committable paths answers `REFUSED:expect_incomplete`; and a control without
`--expect` commits the same mismatched state (proving the flag is what refuses).

**`tests/test_metadata_commit_seam.sh`** — extend with `--preflight` cases over
the existing `sync_fixture.sh` repo: clean / dirty / ignored / untracked / absent
states, `MODE:branch` and `BRANCH:aitask-data`, `MIDOP:` while mid-merge,
`MODE:legacy` in a legacy fixture, and an out-of-scope path still refused. Plus
the `--expect` cases listed under the concurrency block above.

### 7. Documentation

- `website/content/docs/tuis/syncer/_index.md` — replace the section
  **"The push writes files but commits nothing"** (currently ~line 269) with a
  section describing the new ownership: the push commits in the destination,
  path-scoped, under `ait: Update codeagent_config.json`, and **never pushes**;
  the refusal cases and what each means; the local layer committing nothing. The
  existing note about `aitasks/metadata/` being invisible from the destination's
  main checkout stays — it is still how you go look at the commit.
- `aidocs/framework/tui_conventions.md` §metadata ownership — record the
  foreign-root form of the seam (`commit_metadata(root=…)` + the mandatory
  env scrub + the preflight refusal set), so the next cross-repo writer inherits
  the rule instead of re-deriving it.

## Out of scope (stated, not silently dropped)

- **Plan-time preflight.** `plan_push` and `PushOutcome` are unchanged; a mid-work
  destination is reported on the results screen, not in the wizard preview. Settled
  with the user.
- **Pushing the destination's data branch.** The seam never pushes
  (`aitask_metadata_commit.sh`'s stated contract, and these are Textual event
  handlers). A target whose data branch is behind its remote gets a local commit
  and reconciles on its own next `ait sync`.
- **Version skew repair.** A target repo without a recent enough
  `aitask_metadata_commit.sh` is refused with `dest_commit_unavailable`, not
  upgraded. The syncer's Versions tab is the surface for that.
- **A true cross-writer mutex in the destination repo.** The compare-and-commit
  guard detects and refuses; it does not exclude. Real mutual exclusion requires
  every destination-repo metadata writer — that repo's own Settings TUI, board
  column CRUD, chatlink wizard — to take a shared `lib/stale_lock.sh` lock
  around its write-and-commit, which is a framework-wide change with its own
  lock-lifecycle design. Confirmed as the spawned "after" mitigation
  `shared_metadata_write_mutex`, created at Step 8d — so the residual window is
  a recorded decision with a named artifact, not an oversight.

## Verification

```bash
python3 tests/test_cross_repo_push_commit.py          # new
python3 tests/test_cross_repo_settings.py             # unchanged behaviour of the module
python3 tests/test_metadata_writer_inventory.py       # apply_push now WIRED
python3 tests/test_settings_commit_on_save.py         # metadata_commit.py signature change
bash    tests/test_metadata_commit_seam.sh            # --preflight
bash    tests/test_task_git.sh                        # task_utils.sh constant extraction
shellcheck .aitask-scripts/aitask_metadata_commit.sh .aitask-scripts/lib/task_utils.sh
bash tests/run_all_python_tests.sh                    # full suite, read the LAST line
cd website && python3 check_links.py --build          # after the docs edit
```

Manual end-to-end (optional, needs two discovered repos): `ait syncer` → Settings
tab → `p` → push an operation into a sibling repo → the results screen names the
commit; `ait git log -1` in that repo shows `ait: Update codeagent_config.json`
touching only that path, and its data worktree is clean.

Step 9 (Post-Implementation) then handles merge, `ait gates run 1704` for the
declared `risk_evaluated` gate, and archival.

## Risk

### Code-health risk: medium
- Extracting `AIT_GIT_INPROGRESS_STATES` rewrites two existing loops in
  `lib/task_utils.sh`, the library every framework script sources; only one of
  the six state names is exercised by any current test, so a dropped name would
  land silently · severity: medium · → mitigation: inline pre-phase characterize_inprogress_state_guard
- `apply_push` changes from "always writes" to "may refuse before writing", so a
  wrong preflight verdict disables the syncer's push rather than corrupting
  anything · severity: medium · → mitigation: covered by this plan's own 15-case
  test matrix (§6), each case carrying a negative control against today's
  write-without-commit
- `--expect` adds a fail-closed mode to a helper with three existing production
  callers; a mis-scoped `expect_incomplete` check could refuse commits those
  callers make today · severity: low · → mitigation: covered by §6 — `--expect`
  is opt-in, the three callers pass nothing, and `test_settings_commit_on_save.py`
  plus `test_metadata_commit_seam.sh` exercise the no-`--expect` path unchanged

### Goal-achievement risk: medium
- The seam runs the **destination's** copy of `aitask_metadata_commit.sh`
  (`commit_command(root=…)`), so every sibling repo not yet upgraded past t1677
  is refused with `dest_commit_unavailable` — fail-closed and correct, but
  indistinguishable to a user from "the push broke" · severity: medium ·
  → mitigation: skew_refusal_names_the_version
- `--preflight` is a new mode on that same destination-resolved helper, so its
  contract can only ever be exercised against fixtures, never against a real
  older target · severity: low · → mitigation: TBD (accepted — the refusal is
  fail-closed either way)
- The compare-and-commit guard detects and refuses but does not exclude: the
  destination's own writers take no lock, so a residual same-process window
  remains in which a concurrent edit is neither published nor overwritten but
  the push simply fails · severity: medium · → mitigation: shared_metadata_write_mutex

### Planned mitigations
- timing: pre-phase | name: characterize_inprogress_state_guard | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — the AIT_GIT_INPROGRESS_STATES extraction rewrites two loops in the repo's most central shell library | desc: pin all six in-progress git states against assert_data_worktree_clean before and after the constant extraction
- timing: after | name: skew_refusal_names_the_version | type: enhancement | priority: medium | effort: low | inline_risk: low | added_complexity: medium | addresses: goal-achievement — an un-upgraded destination is refused with dest_commit_unavailable and reads as a broken push | desc: name the destination's installed framework version in the dest_commit_unavailable result line and point at the syncer's Versions tab
- timing: after | name: shared_metadata_write_mutex | type: enhancement | priority: medium | effort: high | inline_risk: high | added_complexity: high | addresses: goal-achievement — the compare-and-commit guard detects and refuses but does not exclude, so a concurrent edit in the target makes the push fail rather than succeed | desc: make every destination-repo metadata writer take a shared lib/stale_lock.sh lock around write-and-commit, upgrading cross-repo push from detect-and-refuse to real mutual exclusion
