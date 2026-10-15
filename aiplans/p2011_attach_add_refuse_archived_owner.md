---
Task: t2011_attach_add_refuse_archived_owner.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2011 — `ait attach add` refuses an archived owner

## Context

`cmd_add` (`.aitask-scripts/aitask_attach.sh:233`) resolves its owner with
`resolve_task_file` (`lib/task_utils.sh:2342`). That function has three tiers:
the active dir, then loose files under `aitasks/archived/`, then a temp
extraction from a numbered or legacy `.tar.zst` bundle. `cmd_add` never checks
which tier answered. So `ait attach add <archived id> f` appends an
`attachments:` entry to a loose archived task file and commits it, together with
the blob and its ledger incref. For a bundled id it targets a temp file outside
the repo, and (by t2004's measurement of the same shape) dies at
`txn_require_clean` with a confusing "outside repository" error.

t2004 closed the same gap for `ait artifact create` with
`_artifact_owner_is_active` in `aitask_artifact.sh`.

**Decision: attaching to an archived task is not intended. `add` refuses it.**
- The attachments design treats an archived task as browsable history that
  keeps its existing references (`aidocs/task_attachments_design.md` §8
  "Archival"). It is a referrer, not a target for new work.
- Today the outcome depends on storage age: a loose archived task accepts the
  attachment, but once it is bundled the same command dies. A rule that flips
  when archives are packed is not a supported feature.
- This matches `artifact create` (t2004), so the two substrate writers agree.
- No in-repo caller adds to an archived owner. The only programmatic caller of
  `aitask_attach.sh` is the board's `decref-deleted`. Every test `add` targets
  an active task, and the regression runs below confirm that.

`ls` and `get` keep accepting archived owners. Only `add` changes behaviour.

**`rm` on an archived owner, scoped to what the code does (trace, to be
measured in step 0).** For a loose archived owner, `rm` works and commits the
edit into the archived file (t2004's L4 pins this for artifacts). For a
**bundled** owner, the trace goes like this:
- `resolve_task_file` runs inside `$( )`, so the archive EXIT trap does not
  fire and the extraction survives;
- `_attach_resolve_ref` therefore finds a real entry;
- `_attach_rm_txn` then calls `txn_require_clean` on the temp path;
- `task_git status -- /tmp/...` fails ("outside repository"), so it dies with
  "could not read the git status of …" **before any mutation**.

`_artifact_rm_txn` has the same shape (`aitask_artifact.sh:634`). So "rm still
accepts archived owners" holds only for an owner that has not been bundled.
Every message this task writes says exactly that. t2004's identical claim in
`aitask_artifact.sh` (its die text and help) and in the `task-format.md`
`artifacts` row is narrowed the same way. Its `if` block is edited in step 2
anyway, and leaving the two sibling messages disagreeing would recreate the
inconsistency. No bundle-editing support is added.

## Implementation

### 0. Probe first (scratchpad, before any edit)

In a scratch legacy-mode repo (the same fixture shape as the tests), run the
current code:
1. create active `t26_packed`;
2. `ait attach add 26 p.bin`, and `ait artifact create 26 p.txt --kind report`;
3. move `t26_packed.md` into `aitasks/archived/_b0/old0.tar.zst` and
   `git rm` the loose file;
4. confirm that `resolve_task_file 26` returns an extraction containing both
   the `attachments:` and the `artifacts:` entry;
5. run `ait attach ls/get/rm 26 …` and `ait artifact ls 26` /
   `ait artifact rm 26 art:t26-report`, recording exit status, output, commit
   count and `git status`.

**Expected:** `ls` and `get` succeed. Both `rm`s die with the "could not read
the git status" message, with no commit and no ledger or manifest change, and
**not** with "no attachment/artifact matching" (which would mean lookup failed
before the transaction). Also check whether the extraction temp dir is left
behind. The trace says yes, because `_AIT_ARCHIVE_TMPDIR` is set only inside
the `$( )` subshell.

If the probe contradicts the expectation (a bundled `rm` succeeds), the scoped
wording below reverts to the broad claim everywhere, and the L6 assertions in
steps 4/4b flip to pin success. Either way, the help, the die messages and the
website say the same thing, and L6 pins it.

### 1. Shared predicate — `.aitask-scripts/lib/task_utils.sh`

Both scripts need the check, so move t2004's helper next to
`resolve_task_file`, the function whose output it classifies. Insert it directly
after `resolve_task_file` (before the `# Resolve plan file from task number…`
comment), so no existing line before it shifts. The body is unchanged from
t2004; only the name and the comment change:

```bash
# task_file_is_active <task_id> <task_file> -- true iff the file that
# resolve_task_file returned lives in the ACTIVE task tree: its directory is
# exactly $TASK_DIR (parent) or $TASK_DIR/t<parent> (child). Anything else is a
# loose file under $ARCHIVED_DIR or a temp extraction from a .tar.zst bundle.
# A positive match on the active location, so an unexpected path fails closed.
# Compared by IDENTITY (-ef: same device + inode), never by spelling:
# resolve_task_file keeps $TASK_DIR verbatim, so a trailing slash yields
# `aitasks//t16/...` for a child while dirname collapses a parent's
# `aitasks//t5_x.md` to `aitasks` -- no one string form fits both (t2004).
task_file_is_active() {
    local task_id="$1" task_file="$2" active_dir="$TASK_DIR"
    [[ "$task_id" =~ ^([0-9]+)_[0-9]+$ ]] && active_dir="$TASK_DIR/t${BASH_REMATCH[1]}"
    [[ "$(dirname "$task_file")" -ef "$active_dir" ]]
}
```

Only the predicate is shared. Each caller keeps its own error message: the
shared code is the mechanics, and each verb keeps its own wording.

### 2. `.aitask-scripts/aitask_artifact.sh` — use the shared helper

- Delete the `_artifact_owner_is_active` definition and its comment block
  (currently lines 105–118).
- In `cmd_create`, change `_artifact_owner_is_active "$task_id" "$task_file"`
  to `task_file_is_active "$task_id" "$task_file"`.
- Narrow the claim to the measured scope (step 0), in three places:
  - the `die` tail becomes `… — a new artifact must attach to an active task;
    ls and get still accept any archived owner, rm only one not yet packed into
    a bundle`;
  - the code comment's "rm/ls/get still resolve archived owners" becomes
    "ls/get still resolve archived owners; rm too, until the owner is bundled
    (its extraction is outside the repo, so the transaction refuses it)";
  - `show_help`: "while `rm`, `ls` and `get` still accept archived owners"
    becomes "`ls` and `get` still accept any archived owner, and `rm` one whose
    file is still loose under aitasks/archived/ (not one packed into a .tar.zst
    bundle)".

### 3. `.aitask-scripts/aitask_attach.sh` — refuse in `cmd_add`

Directly after `local task_file; task_file="$(resolve_task_file "$task_id")"`,
before the `name` default and before `with_attach_lock`. This means a refused
call takes no lock and leaves no blob, ledger change or commit:

```bash
    # A new attachment goes on an ACTIVE task (t2011, mirroring t2004's
    # artifact create). resolve_task_file also answers with loose archived
    # files and bundle extractions; writing into either would commit into an
    # archived record or target a temp file. Only add refuses: ls/get still
    # resolve archived owners; rm too, until the owner is bundled (its
    # extraction is outside the repo, so the transaction refuses it).
    if ! task_file_is_active "$task_id" "$task_file"; then
        local where="a .tar.zst archive bundle"
        [[ "$task_file" == "${ARCHIVED_DIR%/}"/* ]] && where="$task_file"
        die "ait attach add: t${task_id} is archived (${where}) — a new attachment must go on an active task; ls and get still accept any archived owner, rm only one not yet packed into a bundle"
    fi
```

`show_help`: after the `<task> accepts a parent id…` paragraph, add:
"`add` refuses an archived <task> (loose or bundled): a new attachment must go
on an active task. `ls` and `get` still accept any archived <task>, and `rm`
one whose file is still loose under aitasks/archived/ (not one packed into a
.tar.zst bundle)."

### 4. `tests/test_attach_local_backend.sh` — new section L (before the footer)

The body runs at the top level, not in subshells, so no counter opt-in is
needed. It uses fresh ids, and the fixture is committed before any `add`. It
mirrors `tests/test_artifact_cli.sh` section L:
- `aitasks/archived/t20_loose.md` (a loose archived parent);
- `aitasks/archived/t21/t21_1_child.md` (a loose archived child);
- `aitasks/archived/_b0/old0.tar.zst` holding `./t22_bundled.md`, built with
  `tar -cf - -C <src> . | zstd -q -o <path>`;
- `aitasks/t23_live.md` (active, for the same-id control);
- `aitasks/t24/t24_1_kid.md` and `aitasks/t25_par.md` (active, for L5).

Precondition: `resolve_task_file 22` must resolve to a `t22_bundled.md` outside
`aitasks/`, so L3 really exercises the bundle tier.

`check_archived_refusal <label> <id> [archived-file]`. Each case gets its own
payload file, so a blob stored by one case cannot mask another case's
assertion. The checks:
- exit is non-zero;
- the output contains `is archived`;
- the commit count is unchanged;
- no blob exists at `attachments/blobs/<shard>`;
- no ledger file exists at `attachments/meta/<shard>.json` (path from
  `attach_meta_relpath`; source `lib/attachment_meta.sh` in the test);
- `git status --porcelain -- aitasks attachments` is unchanged;
- for L1/L2, the archived file gained no `attachments:` key.

Cases:
- **L1** loose parent `20`, plus: the error names `aitasks/archived/t20_loose.md`.
- **L2** loose child `21_1`.
- **L3** bundled `22`, plus: the error says `archive bundle`.
- **L4, same id in both directions.** `add 23 l4.bin` succeeds while t23 is
  active. Then `git mv` t23 into `aitasks/archived/` and commit. After that:
  - `ls 23` still lists `l4.bin`;
  - `get 23 l4.bin --out` returns the stored bytes;
  - `add 23 l4b.bin` is refused with `is archived`, makes no commit and leaves
    no ledger file;
  - `rm 23 l4.bin` still succeeds in one commit, and the archived file loses
    the entry.
- **L5, trailing slash.** With `TASK_DIR=aitasks/ ARCHIVED_DIR=aitasks/archived/`:
  - `add 24_1` (active child) and `add 25` (active parent) are accepted;
  - `add 21_1` (loose archived) and `add 22` (bundled) are still refused;
  - the two refusals make no commit.
- **L6, a bundled owner with a real attachment (pins the help's `rm` scope).**
  Fixture: active `t26_packed` gets `add 26 l6.bin`, committed. Its file
  (which now carries the entry) is then packed into the same `old0.tar.zst` as
  t22, building the bundle once from both files, and the loose file is
  `git rm`'d. Assertions:
  - precondition: `resolve_task_file 26` is an extraction outside `aitasks/`
    whose content lists the `l6.bin` hash (so `rm` reaches the transaction);
  - `ls 26` lists `l6.bin`;
  - `get 26 l6.bin --out` returns the bytes;
  - `rm 26 l6.bin` exits non-zero;
  - its output does **not** contain `no attachment matching` (the lookup
    succeeded);
  - no commit, and the ledger refs for the hash still contain `26`;
  - `git status --porcelain -- aitasks attachments` is unchanged.

  (Assertions follow the step-0 measurement. This is the expected shape.)

Update the file's header comment to mention section L (t2011).

### 4b. `tests/test_artifact_cli.sh` — new section L6 (after L5)

The same pin for the narrowed artifact wording:
- create `art:t26-report` on an active `t26_packed`;
- rebuild `aitasks/archived/_b0/old0.tar.zst` from `$TMP/bundle_src` (which
  still holds `t22_bundled.md`) plus the t26 file, `git rm` the loose file, and
  commit;
- precondition: the extraction lists `art:t26-report`;
- `ls 26` lists the handle, and `get art:t26-report --out` returns the bytes;
- `rm 26 art:t26-report` exits non-zero, its output is not the "no artifact
  matching" lookup error, it makes no commit, and the manifest is still
  present.

L3/L5's bundled refusals must still pass on the rebuilt bundle.

### 5. `tests/test_attach_lock_callback_contract.sh` — renumber ALLOWLIST pins

Steps 2–3 shift lines: `aitask_attach.sh` moves down (help line + refusal
block) and `aitask_artifact.sh` moves up (helper removed). Re-locate each pinned
site and renumber its entry. Before renumbering, compare each new line
byte-for-byte with the HEAD line:
- `aitask_attach.sh:335`, `:614`;
- `aitask_artifact.sh:193`, `:377`, `:484`, `:700`.

### 6. Docs (current-state wording)

All of these use the same step-0-measured scope as the help and die texts:
`ls`/`get` work on any archived task, and `rm` only on one not yet packed into
a bundle.
- `website/content/docs/commands/attach.md`:
  - `### add` "`add` refuses:" list: add a bullet for an archived task (loose
    under `aitasks/archived/` or packed into an archive bundle), because a new
    attachment must go on an active task;
  - `### rm`: add one sentence saying `rm` works on an archived task whose file
    is still under `aitasks/archived/`, but not on one already packed into an
    archive bundle, which it refuses without changing anything.
- `website/content/docs/development/task-format.md`:
  - `attachments` row: add "`add` also refuses an archived task, because a new
    attachment must go on an active one; `ls` keeps working on any archived
    task, `rm` on one not yet packed into an archive bundle";
  - `artifacts` row: narrow the existing "`rm` and `ls` keep working on
    archived owners" the same way.
- `website/content/docs/concepts/attachments.md`, the "**Archiving** changes
  nothing" bullet: add that an archived task cannot gain new attachments, while
  its existing ones stay listable and fetchable.
- Run `cd website && python3 check_links.py --build`.

## Verification

1. `bash tests/test_attach_local_backend.sh` and `bash tests/test_artifact_cli.sh`:
   all pass, including the new L sections and L6.
1b. Consistency check: grep the help texts, die texts and the three doc pages
   for "still accept" / "keep working". Every claim about archived `rm` must
   carry the bundle qualifier.
2. **Red proof** in the scratchpad. Copy `.aitask-scripts/` and `tests/`,
   overwrite the copied `aitask_attach.sh` with
   `git show HEAD:.aitask-scripts/aitask_attach.sh`, and run the copied test.
   Expect L1/L2/L3, L4's "add now refused" and L5's archived refusals to FAIL,
   and everything else to pass. Record what pre-fix code did for the loose and
   bundled ids. The live tree is not touched (no stash, no restore).
3. Regression runs (each prints its own summary):
   - `test_artifact_cli.sh`, because of the helper move; section L/L5 must
     still pass;
   - `test_attach_lock_callback_contract.sh`;
   - `test_attach_archive_gc.sh`, `test_attach_fold_rebind.sh`,
     `test_attach_task_delete_decref.sh`;
   - `test_attach_txn_worktree_isolation.sh`, `test_attach_scaffold.sh`;
   - `test_artifact_fold_transfer.sh`, `test_artifact_share_resolution.sh`;
   - `test_task_filename_invariant.sh`, `test_yaml_utils.sh`,
     `test_resolve_tar_zst.sh`.
4. `shellcheck .aitask-scripts/aitask_attach.sh .aitask-scripts/aitask_artifact.sh .aitask-scripts/lib/task_utils.sh`.
5. `cd website && python3 check_links.py --build`.

## Expected Final Implementation Notes entries (upstream defects, if measured)

- A bundled-owner `attach rm` / `artifact rm` refuses with a misleading
  "could not read the git status of /tmp/…" error, not one that names the
  bundle. A clearer refusal is a separate change. This task only documents the
  scope and pins it.
- A temp dir leaked by `resolve_task_file` inside `$( )`, if step 0 confirms
  that `_AIT_ARCHIVE_TMPDIR` cleanup never runs for a bundle extraction.

## Step 9

Current-branch mode, so there is no worktree and no merge. After the Step 8
commit, Step 9 archives t2011 and its plan.

## Risk

### Code-health risk: low
- Moving the helper into `lib/task_utils.sh` touches a widely sourced library
  and the artifact `create` path. The body is byte-identical, only its name
  changes, and `test_artifact_cli.sh` sections L/L5 pin the artifact behaviour.
  The line shifts are handled by the explicit allowlist re-check in step 5.
  · severity: low · → mitigation: none (covered by verification steps 3–4)

- Rebuilding `old0.tar.zst` in `test_artifact_cli.sh` L6 could disturb the
  existing L3/L5 bundled cases that read it. · severity: low · → mitigation:
  none (the rebuild keeps `t22_bundled.md`, and L3/L5 re-run green in
  verification step 1)

### Goal-achievement risk: low
- A user who attached files to a loose archived task (worked, though
  unsupported) is now refused. This is the intended behaviour change, and it is
  documented on the command, concept and task-format pages. · severity: low ·
  → mitigation: none (intended; pinned by section L4 in both directions)
- The bundled-`rm` scope rests on a code trace until step 0 measures it.
  · severity: low · → mitigation: none (step 0 runs before any edit; the
  wording and the L6 assertions follow the measured result, and step 1b checks
  that every surface agrees)
