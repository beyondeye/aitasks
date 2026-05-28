---
Task: t832_7_cross_repo_task_update.md
Parent Task: aitasks/t832_brainstorm_cross_repo_skills_retrieval_xdeps_parallel_planni.md
Sibling Tasks: aitasks/t832/t832_5_parallel_cross_repo_planning_procedure.md, aitasks/t832/t832_6_retrospective_dogfooding_evaluation.md, aitasks/t832/t832_8_ait_board_cross_repo_support.md, aitasks/t832/t832_9_manual_verification_cross_repo.md
Archived Sibling Plans: aiplans/archived/p832/p832_1_cross_repo_retrieval_reexec_trio.md, aiplans/archived/p832/p832_2_explain_context_cross_repo.md, aiplans/archived/p832/p832_3_xdeps_parser_and_validation.md, aiplans/archived/p832/p832_4_xdeps_blocking_logic.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-28 08:46
---

# Plan: t832_7 — cross-repo `aitask_update.sh --project` (verify-mode update)

Verifies and updates `aiplans/p832/p832_7_cross_repo_task_update.md`.
Task: `aitasks/t832/t832_7_cross_repo_task_update.md`.
Parent: `t832` (cross-repo skills / retrieval / xdeps / parallel planning).

## Context

t832 is decomposing cross-repo task coordination into shippable children.
t832_1, t832_3, t832_4 are archived. The next sibling that downstream
work depends on is `t832_7` — it adds `aitask_update.sh --project <name>`,
the mirror of `aitask_create.sh --project` shipped by t826_1. The
parallel-planning procedure (t832_5) cannot wire **symmetric** cross-edges
(both repos' children carry `xdeps:` pointing at the other) without it,
because the second `xdeps:` write only becomes possible after both sides'
IDs exist — i.e., we need to *update* the local children once the
cross-repo IDs are known.

Verification of the existing plan against the current codebase found:

- **Stale line ref.** Plan cites `aitask_create.sh:1693-1753` for the
  re-exec pattern. The pattern is now at **lines 1778-1838** (start of
  `main()`). The 1693-1753 range now contains `cmd_batch_create` body.
- **`owner:` → `locked_by:`.** Plan says `aitask_lock.sh --check` emits
  `owner:` lines. It actually emits `locked_by:` (alongside `hostname:`
  and `locked_at:`). See `aitask_lock.sh:315 check_lock()`.
- **Missing scope item: local `--xdeps` / `--xdeprepo` flags.**
  `aitask_update.sh` has every administrative flag in the cross-repo
  allowlist *except* `--xdeps` and `--xdeprepo`. The archived t832_3
  plan (lines 225-231) explicitly defers adding those flags to t832_7
  ("t832_7 also owns the local-only `aitask_update.sh --xdeps` /
  `--xdeprepo` flag work"). The current p832_7 plan only lists them in
  the cross-repo allowlist — without the underlying local flag work,
  the cross-repo `--xdeps` invocation is hollow.

All other plan claims hold:

- `aitask_create.sh main()` re-exec pattern (lines 1778-1838) is the
  canonical reference to mirror.
- `aitask_update.sh main()` (line 1555) dispatches `parse_args` →
  `run_batch_mode` / `run_interactive_mode`. The `--project` argv-prefix
  parse goes at the **top of `main()`** before `parse_args`, exactly as
  in `aitask_create.sh`.
- `aitask_project_resolve.sh` protocol (`RESOLVED:`/`STALE:`/`NOT_FOUND:`)
  is stable.
- `aitask_lock.sh --check <id>` reads the lock file YAML from
  `origin/<lock-branch>` and prints it to stdout (lines 332-333); exit
  0 = locked, 1 = free. Parser needs to read `hostname:` and `locked_by:`.
- Test scaffolding pattern lives in `tests/test_create_project_flag.sh`
  (stub sibling project + sentinel logfile + isolated `AITASKS_PROJECTS_INDEX`).

## Implementation steps

### 1. Local `--xdeps` / `--xdeprepo` flag work in `aitask_update.sh`

Mirror the `BATCH_XDEPS` / `BATCH_XDEPREPO` pattern from
`aitask_create.sh:36-37, 78-82, 150-151, 410+`.

- Add globals: `BATCH_XDEPS=""`, `BATCH_XDEPREPO=""`,
  `BATCH_XDEPS_SET=false`.
- Add `parse_args` cases: `--xdeps`, `--xdeprepo` (alongside existing
  `--deps`).
- Add `show_help` lines describing both flags and the both-or-neither
  rule on update (reuse the validator pattern from `create.sh`).
- In `run_batch_mode`'s YAML write path, write `xdeps:` and `xdeprepo:`
  fields when set. Replaces-all semantics, matching `--deps`.
- Reuse `validate_xdeps_pair` from `lib/task_utils.sh` (the validator
  added by t832_3) — same both-or-neither rule and cross-repo ID
  existence check as `aitask_create.sh`.
- Allow clearing: `--xdeps ""` + `--xdeprepo ""` removes both fields.

Keep this strictly local — no `--project` interaction yet.

### 2. Cross-repo dispatch in `aitask_update.sh main()`

Copy the cross-repo pre-dispatch block verbatim from
`aitask_create.sh:1778-1838` with these substitutions:

- Target script: `"$root/.aitask-scripts/aitask_update.sh"`.
- Drop the `--parent`/`-P` branch (update has no `--parent`); keep
  `--project` + `--batch` parsing and the forwarded-argv loop.
- Enforce `--project requires --batch` (same `die` message).
- Status-transition allowlist enforced **before** `cd` + `exec`. Scan
  the forwarded argv for `--status <val>`/`-s <val>` and refuse:
  - `Implementing` → die: "cross-repo status transition to
    `Implementing` must go through `<name>`'s own `/aitask-pick`
    workflow (lock acquisition + plan externalization happen there)".
  - `Done` → die with the same hint pointing at `/aitask-pick`.
  - `Folded` → die: "folding requires reading both task bodies and is
    not supported cross-repo".
  - Allowed cross-repo: `Ready`, `Editing`, `Postponed`.
- Refuse `--name` cross-repo (rename touches the filename and the
  child's parent's `children_to_implement` — risky across a remote).

### 3. Lock-check inside the re-exec'd target

Add at the top of `run_batch_mode` (after `parse_args` validation but
before any file mutation):

- Probe via `"$SCRIPT_DIR/aitask_lock.sh" --check "$TASK_ID"`.
- If exit 0 (locked), parse `hostname:` and `locked_by:` from the
  captured stdout.
- Compare against local `hostname` (the command, not the YAML field)
  and the user's email (read via existing helper or
  `aitasks/metadata/userconfig.yaml`).
- If a different host **or** a different owner holds the lock, die:
  "cross-repo task t<N> is locked by `<locked_by>@<hostname>` (since
  `<locked_at>`); cannot update from this host. Pick the task there
  to release, or wait."
- Skip the check when:
  - Exit 1 (no lock — single-user / no-remote mode).
  - Lock is held by the same `hostname` + same `locked_by` (local
    administrative update while picking is fine).
- Gate the check behind a sentinel env var
  (`AIT_CROSS_REPO_REEXEC=1`) set in step 2 just before `exec`. This
  keeps in-process local invocations (PWD-local update calls) from
  paying the lock-fetch cost. Plain local updates have no need for the
  check — they go through `aitask_pick_own.sh` which already owns the
  lock.

### 4. `show_help()` update

Document `--project` + the allowlist + the lock-check guardrail (per
the p832_7 plan section 3, verbatim — modulo the `Folded` addition).

### 5. Tests — `tests/test_update_cross_repo.sh`

Pattern after `tests/test_create_project_flag.sh`. Two fake projects
(A = PWD repo, B = sibling stub with sentinel-logging
`aitask_update.sh`). Isolated registry via `AITASKS_PROJECTS_INDEX`.

**Success cases:**

- `aitask_update.sh --batch --project b 1 --priority high` → sentinel
  shows `cwd=B`, forwarded argv has `--batch 1 --priority high` (no
  `--project`).
- `--project b 1 --xdeps "1,2" --xdeprepo a` → forwarded.
- `--project b 1 --status Postponed` → forwarded.
- `--project b 1 --status Ready` → forwarded.
- `--project b 1 --status Editing` → forwarded.
- `--project b 1 --add-label foo` → forwarded.
- `--project b 1 --boardcol now --boardidx 50` → forwarded.

**Refusal cases (must die before any sentinel write):**

- `--project b 1 --priority high` (no `--batch`) → die "--project
  requires --batch".
- `--project b 1 --status Implementing` → die with `/aitask-pick` hint.
- `--project b 1 --status Done` → die with `/aitask-pick` hint.
- `--project b 1 --status Folded` → die with cross-repo-fold hint.
- `--project b 1 --name foo` → die "rename not supported cross-repo".
- `--project not_registered 1 ...` → die with
  `cd && ait projects add` hint.

**Lock-check (requires real PWD-local repo, not a stub):**

- Stage a fake lock file in B's repo with a different hostname → die
  with the locked-by message.
- Stage a fake lock with the **same** hostname/owner → succeeds.

Use `tests/lib/test_scaffold.sh::setup_fake_aitask_repo` for B's repo
so the real `aitask_update.sh` runs end-to-end in the lock-check tests.

### 6. Local-flag tests

Add to `tests/test_aitask_update_xdeps.sh` (new file, mirroring the
existing `tests/test_aitask_update_*.sh` style):

- `--batch <id> --xdeps "1,2" --xdeprepo other_repo` writes both YAML
  fields.
- `--batch <id> --xdeps ""` (no `--xdeprepo`) → both-or-neither
  validator rejects.
- `--batch <id> --xdeps "" --xdeprepo ""` clears both fields.
- Round-trip with the t832_3 parser: write via update, read back via
  `aitask_ls.sh`'s parser, fields match.

## Files to modify

- `.aitask-scripts/aitask_update.sh` — steps 1, 2, 3, 4.
- `tests/test_update_cross_repo.sh` (new) — step 5.
- `tests/test_aitask_update_xdeps.sh` (new) — step 6.

## Reference patterns (do not modify)

- `.aitask-scripts/aitask_create.sh:1778-1838` — cross-repo dispatch.
- `.aitask-scripts/aitask_create.sh:36-37, 78-82, 150-151, 410+` —
  `--xdeps`/`--xdeprepo` flag parsing and write.
- `.aitask-scripts/aitask_lock.sh:315` `check_lock()` — output format.
- `.aitask-scripts/aitask_project_resolve.sh` — resolver protocol.
- `tests/test_create_project_flag.sh` — sentinel-stub test pattern.
- `tests/test_scaffold.sh::setup_fake_aitask_repo` — full fake-repo
  scaffold for lock-check tests.

## Verification

- `bash tests/test_update_cross_repo.sh` passes.
- `bash tests/test_aitask_update_xdeps.sh` passes.
- `shellcheck .aitask-scripts/aitask_update.sh` clean.
- Manual smoke test from `aitasks/`:
  ```
  ./.aitask-scripts/aitask_update.sh --batch --project aitasks_mobile <id> --add-label test
  ```
  Confirm the label lands in the cross-repo project; local PWD
  unchanged.
- Re-render skills (`./.aitask-scripts/aitask_skill_render.sh`) and
  verify via `./.aitask-scripts/aitask_skill_verify.sh` — only
  `show_help` text changed, so no template/golden churn expected.

## Final Implementation Notes

(To be filled by the implementing agent during/after execution.)
