---
Task: t2004_artifact_create_refuse_archived_owner.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2004 — `ait artifact create` refuses an archived owner

## Context

`cmd_create` (`.aitask-scripts/aitask_artifact.sh:241`) resolves its owner with
`resolve_task_file` (`lib/task_utils.sh:2324`). That function falls through
three tiers: the active dir, then loose files in `aitasks/archived/`, then a
temp extraction from a numbered or legacy `.tar.zst` bundle. Neither
`cmd_create` nor `_artifact_create_txn` checks which tier answered. So
`ait artifact create <archived id> …` appends an `artifacts:` entry to a loose
archived task file and commits it. For a bundled id it writes into a temp file
outside the repo.

t1989 already makes the trail gatherer refuse an archived owner on create
(`archived_owner`, `lib/trail_gather.py:_owner_error`). The substrate itself
is not guarded, so any direct caller can still write into an archived record.
This plan puts the same rule ("a new artifact attaches to an active task") in
the substrate.

**Intentional flows checked (none create on an archived owner):**
- trail skill: the gatherer refuses archived owners for create, and refresh
  goes through `update`, which never resolves an owner;
- `aitask-backlog-roadmap` creates on t1718, an active holder task;
- `aitask_fold_mark.sh` moves `artifacts:` entries itself and never calls
  `create`;
- every test that calls `create` (`test_artifact_cli.sh`,
  `test_artifact_fold_transfer.sh`, `test_artifact_share_resolution.sh`,
  `test_trail_gather.py`, `test_trail_links.py`) uses an active owner.

`rm`, `ls` and `get` keep accepting archived owners, because trails outlive
their owners. Only `create` changes.

## Implementation

### 1. `.aitask-scripts/aitask_artifact.sh`

**a) New helper** in the "Shared helpers" section, next to `_artifact_records`:

```bash
# _artifact_owner_is_active <task_id> <task_file> -- true iff the file that
# resolve_task_file returned lives in the ACTIVE task tree: its directory is
# exactly $TASK_DIR (parent) or $TASK_DIR/t<parent> (child). Anything else is a
# loose file under $ARCHIVED_DIR or a temp extraction from a .tar.zst bundle.
# This is a positive match on the active location, so an unexpected path fails
# closed (it is refused, never written).
_artifact_owner_is_active() {
    local task_id="$1" task_file="$2" active_dir="${TASK_DIR%/}"
    [[ "$task_id" =~ ^([0-9]+)_[0-9]+$ ]] && active_dir="${active_dir}/t${BASH_REMATCH[1]}"
    [[ "$(dirname "$task_file")" == "$active_dir" ]]
}
```

**b) `cmd_create`.** Directly after
`local task_file; task_file="$(resolve_task_file "$task_id")"`, and before
`with_attach_lock` (so the refusal happens before any lock, blob, manifest or
commit):

```bash
    # A new artifact attaches to an ACTIVE task (t2004) -- the substrate half
    # of the trail gatherer's archived_owner rule (t1989). resolve_task_file
    # also answers with loose archived files and bundle extractions; writing
    # into either would commit into an archived record or a temp file. Only
    # create refuses: rm/ls/get still resolve archived owners.
    if ! _artifact_owner_is_active "$task_id" "$task_file"; then
        local where="a .tar.zst archive bundle"
        [[ "$task_file" == "${ARCHIVED_DIR%/}"/* ]] && where="$task_file"
        die "ait artifact create: t${task_id} is archived (${where}) — a new artifact must attach to an active task; rm, ls and get still accept archived owners"
    fi
```

**c) Help text** (`show_help`, the paragraph that begins `<task> accepts …`):
add one sentence: "`create` refuses an archived <task> (loose or bundled): a
new artifact must attach to an active task, while `rm`, `ls` and `get` still
accept archived owners."

### 2. `tests/test_artifact_cli.sh` — new section L (before the footer)

The test body runs at top level, not in subshells, so it needs no counter
opt-in. It uses fresh ids so earlier sections are not disturbed. Fixture
(committed before any create):
- `aitasks/archived/t20_loose.md` (loose archived parent);
- `aitasks/archived/t21/t21_1_child.md` (loose archived child);
- `aitasks/archived/_b0/old0.tar.zst` holding `./t22_bundled.md`, built with
  `tar -cf - -C <src> . | zstd -q -o <path>` (the same shape as
  `test_resolve_tar_zst.sh`). The id resolves through
  `_find_archive_for_task` → `archive_path_for_id`;
- `aitasks/t23_live.md` (active; used for the control pair).

Assertions:
- **L1 loose parent, L2 loose child, L3 bundled.** For each, `create <id>
  tiny.txt --kind report`:
  - exits non-zero;
  - stderr contains `is archived`;
  - the commit count is unchanged;
  - no `artifacts/manifests/t<id…>-report.json` exists;
  - `git status --porcelain -- aitasks artifacts attachments` is empty;
  - for L1/L2, the archived file has no `artifacts:` key.
- **L4 control on the same id (guard-specific).** First, `create 23 … --kind
  report` succeeds while t23 is active. Then archive it (`git mv` to
  `aitasks/archived/` and commit). After that:
  - `ls 23` still lists `art:t23-report`;
  - `get art:t23-report --out` still works;
  - `create 23 … --kind mockup` is now refused with `is archived`;
  - `rm 23 art:t23-report` still succeeds, and the archived file loses the
    entry in a commit.

  This pins both directions: an active owner is accepted, and an archived
  owner is refused only on create.

### 3. `website/content/docs/development/task-format.md` (`artifacts` row)

Add one clause after "Written by `ait artifact create` / `rm`, never by hand":
"`create` also refuses an archived task, because a new artifact must attach to
an active one. `rm` and `ls` keep working on archived owners." Then run
`python3 check_links.py --build` (in `website/`).

### Out of scope (to record as an upstream defect)

`ait attach add` (`aitask_attach.sh:233`) has the same shape: it resolves its
owner with `resolve_task_file` and writes `attachments:` into whatever file it
gets back. This task covers `artifact create` only. The attach gap goes into
the Final Implementation Notes "Upstream defects identified" bullet, so that
Step 8b offers a follow-up.

## Verification

1. `bash tests/test_artifact_cli.sh` — all PASS, including section L.
2. **Red proof.** Copy `.aitask-scripts/` and `tests/` into a scratchpad dir,
   overwrite the copied `aitask_artifact.sh` with
   `git show HEAD:.aitask-scripts/aitask_artifact.sh`, and run the copied test.
   Expect the L1/L2/L3 refusal assertions and L4's "create now refused" to
   FAIL, and everything else to pass. Record what pre-fix code actually did
   for the bundled id, which t2004 marks as unverified. The live worktree is
   not touched (no stash, no restore).
3. Regression runs:
   - `bash tests/test_artifact_fold_transfer.sh`
   - `bash tests/test_artifact_share_resolution.sh`
   - `bash tests/test_attach_lock_callback_contract.sh`
   - `bash tests/test_task_filename_invariant.sh`
   - `bash tests/run_all_python_tests.sh tests/test_trail_gather.py tests/test_trail_links.py`
     (read the final verdict line).
4. `shellcheck .aitask-scripts/aitask_artifact.sh`.
5. `cd website && python3 check_links.py --build`.

## Step 9

Current-branch mode: no worktree or merge. After the Step 8 commit, Step 9
archives t2004 and its plan.

## Risk

### Code-health risk: low
- Behaviour change for any caller that creates an artifact on an archived
  owner. All in-repo callers were audited and none do. The refusal happens
  before the lock and before any mutation, so a refused call leaves no state.
  · severity: low · → mitigation: none (covered by plan step 2 tests: L1–L3
  no-mutation assertions, L4 active control)

### Goal-achievement risk: low
None identified.

## Final Implementation Notes
- **Actual work done:** `cmd_create` in `.aitask-scripts/aitask_artifact.sh` now refuses an owner whose resolved file is not in the active task tree. It runs immediately after `resolve_task_file` and before `with_attach_lock`, so a refused call takes no lock and leaves no blob, manifest or commit. The check is a positive match, `_artifact_owner_is_active`: the dirname must be the same directory (`-ef`) as `$TASK_DIR` (parent) or `$TASK_DIR/t<parent>` (child). The error names the loose archived path, or says "a .tar.zst archive bundle". `show_help` and the `artifacts` row in `website/content/docs/development/task-format.md` each gained one sentence. `tests/test_artifact_cli.sh` has a new section L: L1 loose parent, L2 loose child, L3 bundled (with a fixture-shape precondition that t22 really resolves to a temp extraction outside `aitasks/`), and L4, a same-id pair. In L4, create is accepted while the owner is active and refused once it is archived, while `ls`, `get` and `rm` keep working on the archived owner.
- **Deviations from plan:** (1) `tests/test_attach_lock_callback_contract.sh` pins `aitask_artifact.sh` allowlist entries by line number, and its comment requires them to be re-checked whenever the file shifts. My insertions moved the four exempted sites by +17 or +27 lines (176→193, 350→377, 457→484, 673→700, after Change Request 1). Each new line was compared byte-for-byte with the HEAD line before its entry was renumbered. (2) Each L refusal case uses its own payload file. With a shared payload, the red run's L3 "no blob stored" check failed only because of the blob L1 had stored, which is not L3's own signal.
- **Issues encountered:** `bash tests/run_all_python_tests.sh <path> <path>` did not narrow the run. It started the whole suite serially, so I stopped it and ran `pytest tests/test_trail_gather.py tests/test_trail_links.py` directly.
- **Red proof (pre-fix `aitask_artifact.sh` from HEAD, run in a scratchpad copy of `.aitask-scripts/` + `tests/`; the live tree was untouched):** 198/218 passed, 20 failed, all in section L. Pre-fix, L1/L2/L4 created the artifact and committed an `artifacts:` entry into the loose archived task file, together with its manifest and blob. Pre-fix, L3 (bundled) died at `txn_require_clean` with `fatal: /tmp/.../t22_bundled.md: ... is outside repository`. That was before any blob, manifest or commit, which confirms the task's unverified expectation. With the fix: 218/218 (227/227 after Change Request 1 added L5).
- **Key decisions:** Only `create` refuses an archived owner. `rm`, `ls` and `get` are deliberately unchanged, because artifacts outlive their owners, and L4 pins this. The check sits in `cmd_create` and not in `resolve_task_file`, whose archive fallback the read verbs rely on. The callers audited were the trail skill (guarded by the gatherer, whose refresh uses `update`), `aitask-backlog-roadmap` (active t1718), `aitask_fold_mark.sh` (does not call create), and every test that calls create (all active owners).
- **Upstream defects identified:**
  - `.aitask-scripts/aitask_attach.sh:233 — cmd_add resolves its owner with resolve_task_file and writes attachments: into whatever file comes back, so 'ait attach add <archived id>' commits an attachment entry into a loose archived task file (and for a bundled id targets a temp extraction) — same shape as the cmd_create gap t2004 closed; not reproduced`

## Post-Review Changes

### Change Request 1 (2026-10-15 15:33)
- **Requested by user:** `_artifact_owner_is_active` stripped the trailing slash from `TASK_DIR`, but `resolve_task_file` keeps `TASK_DIR` exactly as written. With `TASK_DIR=aitasks/`, an active child resolves to `aitasks//t16/...` while the expected directory was `aitasks/t16`, so `create 16_2` was wrongly refused as "archived (a .tar.zst archive bundle)". Fix it, and add an active-child regression test with a trailing-slash `TASK_DIR`.
- **Changes made:** I reproduced the bug first: in a scratch repo, `TASK_DIR=aitasks/ ait artifact create 16_2` was refused, while the active parent `create 5` succeeded. The helper now compares directories by identity (`[[ "$(dirname "$task_file")" -ef "$active_dir" ]]`, same device and inode) using `TASK_DIR` as written, not by string. No single spelling fits both cases: `dirname` collapses a parent's `aitasks//t5_x.md` to `aitasks` but leaves a child's `aitasks//t16`. The match is still positive, and a missing directory makes `-ef` false, so the check still fails closed. New test section L5 sets `TASK_DIR=aitasks/ ARCHIVED_DIR=aitasks/archived/`: an active child (24_1) and an active parent (25) are accepted, and a loose archived child (21_1) and a bundled task (22) are still refused, with no commit. Red proof: with the earlier helper restored in a scratch copy, exactly the two active-child L5 assertions fail (225/227). With the fix, 227/227. Those 3 extra comment lines moved the four allowlisted sites in `test_attach_lock_callback_contract.sh` by another +3. Each was re-checked byte-for-byte against HEAD and renumbered (92/92).
- **Files affected:** `.aitask-scripts/aitask_artifact.sh`, `tests/test_artifact_cli.sh`, `tests/test_attach_lock_callback_contract.sh`
