---
Task: t2178_harden_setup_store_gitignore_writes.md
Base branch: main
Output branch: main
---

# t2178 — Harden setup's `.gitignore` store writers

## Context

`ait setup`'s `.gitignore` helpers in `.aitask-scripts/aitask_setup.sh` —
`setup_draft_directory`, `setup_python_cache_gitignore`,
`setup_gate_logs_gitignore`, `setup_testmap_gitignore`,
`setup_shadow_store_gitignore`, `setup_scratchpad_gitignore`,
`setup_sitrep_store_gitignore` (added by t2175_1 after this task was filed) and
`setup_worktree_dirs_gitignore` — test with `[[ -f ]]` and write with unchecked
`echo … >> "$gitignore"` / `{ … } > "$gitignore"`. `main()` runs them under
`set -euo pipefail`, so a read-only or non-regular `.gitignore` either **aborts
`ait setup`** (failed redirection under errexit) or — when errexit is suspended,
as in the test shell — prints "rule added" for a write that never happened.

t2173_1 hardened `setup_cache_gitignore`, and t2177 extracted the hardened
writer `_ait_add_gitignore_rules` (rc 0 added / 1 already / 2 cannot inspect or
write, read-back verified, each rule guarded separately) plus
`_ait_warn_gitignore_rules_failed`, and built the upgrade route
`upgrade_store_gitignore_rules` on them with its **own copy** of each group's
comment and rule strings. This task moves every setup helper onto that writer
and puts the comment/rule strings in **one table** both routes read, so they
cannot drift (27h pins byte-identical output today; the table makes it
structural).

Behaviour preserved verbatim: every helper's "already" line, its final success
line, and its commit subject; upgrade's per-group labels and failure "what"
lines; `upgrade_cache_gitignore`'s messages; the bytes written. **Two
deliberate changes:**
1. The pre-write `info "Adding <rule> to .gitignore (<note>)..."` line becomes the
   post-write `info "Added <rule> to .gitignore (<note>)"` (same `<note>`), the
   `setup_cache_gitignore` shape the task prescribes — the check and write are
   now one call, so nothing can be printed between them, and "Adding…" before a
   failed write would be the dishonest claim this task removes.
2. A `.gitignore` that exists but is not a readable regular file now warns and
   is left alone instead of aborting setup, being written through, or **hanging
   it**. Today `_ait_add_gitignore_rules` checks only `-e || -L` before
   `grep -qxF … "$gitignore"`: a directory, dangling symlink or unreadable file
   already fails grep (rc 2), but a **FIFO blocks grep's `open(O_RDONLY)` until a
   writer appears** (the user's probe: exit 124 after a 2s bound), and a symlink
   to a character device such as `/dev/zero` streams forever. The old setup
   helpers hang the same way on a FIFO (`{ … } > fifo` blocks on open for write).
   Step 2 makes the writer open **only** a regular file (or a symlink to one).

Out of scope: `setup_draft_directory`'s `mkdir -p aitasks/new` stays as is
(not a `.gitignore` write; if `aitasks/` is unwritable, `setup_data_branch` has
already failed earlier in `main()`).

## Implementation

All shell edits in `.aitask-scripts/aitask_setup.sh`; tests in
`tests/test_setup_git.sh`. Tests are written first so the red proof runs
against the unchanged helpers.

### Pre-phase (risk mitigations)

1. [pin_gitignore_writer_outputs] Add **Test 27k** to `tests/test_setup_git.sh`
   (after 27i): an independent literal oracle for every string the refactor
   moves, because once both routes read one table 27h compares the table with
   itself and can no longer catch a mis-copied comment or rule.
   - A heredoc `helper|group-block|note|commit|success|already` for all nine
     setup helpers, values copied from the **current** code (the table in step 3
     below). Per row, on a fresh `new_gitignore_repo` with an armed clean
     baseline (`snapshot_pre_setup_dirty`):
     - first run: `.gitignore` equals exactly `base-rule` + `\n# <comment>\n<rules…>\n`
       (`assert_eq` on `cat`, built with `printf`); `git log -1 --format=%s` equals
       `<commit>`; output contains `<success>` and `<rules> to .gitignore (<note>)`
       (the substring both today's "Adding … (note)..." and the new "Added … (note)"
       carry);
     - second run: output contains `<already>`, and no new commit.
   - `upgrade_store_gitignore_rules` on a fresh fixture: output contains each
     `Added <rules> to .gitignore (<label>)` line for the six groups; on the
     27f directory fault, output contains each `<what> will show as untracked`
     line.
   - `upgrade_cache_gitignore`: full lines `Added .aitask-cache/ to .gitignore
     (discovery caches)` then, on re-run, `Discovery-cache rule already in
     .gitignore`.
   - **Run it green against the unchanged `aitask_setup.sh` before any edit
     there** (the pre-refactor proof), and keep it green through step 3–4.

### 1. Extend 27f to every setup helper, plus an errexit check (red first)

In `tests/test_setup_git.sh` Test 27(f):

- Rename the heredoc's second field `first_rule` → `reported` (what the failure
  line names: `_ait_warn_gitignore_rules_failed` prints `Could not add $* to
  .gitignore`, so the two-rule group reports `aiwork/ .aitask-crews/`). Add rows:
  ```
  setup_draft_directory|aitasks/new/
  setup_python_cache_gitignore|__pycache__/
  setup_gate_logs_gitignore|.aitask-gates/
  setup_testmap_gitignore|.aitask-testmap/
  setup_shadow_store_gitignore|.aitask-shadow/
  setup_scratchpad_gitignore|.aitask-scratchpad/
  setup_sitrep_store_gitignore|.aitask-sitrep/
  setup_worktree_dirs_gitignore|aiwork/ .aitask-crews/
  ```
- Add an errexit assertion inside the same `(helper, fault)` loop, on the same
  fixture after the in-process call (nothing was written, so it is reusable).
  The test shell runs `set +euo pipefail` after sourcing, so 27f alone never
  sees the abort `main()` would hit. A child shell re-sources the script, which
  re-arms `set -euo pipefail` at its line 2:
  ```bash
  # Runs <helper> on project <dir> under the errexit `ait setup`'s main() has.
  errexit_helper_run() {
      HOME="$1/home-scratch" bash -c '
          source "$1" --source-only
          [[ $- == *e* ]] && echo ERREXIT_ON
          SCRIPT_DIR="$2/.aitask-scripts"
          "$3"
          echo SURVIVED' _ "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" "$1" "$2" </dev/null 2>&1
  }
  ...
  out="$(errexit_helper_run "$d" "$helper")" || true
  assert_contains "27f $helper $fault: child shell has errexit" "ERREXIT_ON" "$out"
  assert_contains "27f $helper $fault: survives setup's errexit" "SURVIVED" "$out"
  ```
  `ERREXIT_ON` is the control: without it a `SURVIVED` proves nothing.
  The child runs through **`run_bounded 15 <outfile> bash -c …`** from
  `tests/lib/proc_fixtures.sh` (source it next to `asserts.sh`; GNU `timeout`,
  `gtimeout`, or its process-group watchdog on bare macOS), and asserts its
  status is `0` — a `124` is a named FAIL ("did not return within 15s") instead
  of a wedged suite.
- **Add a third fault, `fifo`**, for every row (setup and upgrade alike):
  `rm "$d/.gitignore"; mkfifo "$d/.gitignore"`. A FIFO must never be touched by
  an unbounded call, so for this fault:
  - skip the in-process call **and** `snapshot_pre_setup_dirty` — its
    `git ls-files --others --exclude-standard` reads `.gitignore` and could
    itself block outside any bound. An unarmed baseline is the direct-call
    default, and the failure path never reaches `_ait_commit_gitignore_rule`;
  - run only the bounded errexit child, then assert on its output the same
    four message checks the other faults make ("Could not add <reported> to
    .gitignore"; no "Added ", "rule added", "already in .gitignore"), `rc` 0,
    `SURVIVED`, no new commit (`git rev-list` does not read `.gitignore`), and
    **the path is unchanged**: `[[ -p "$d/.gitignore" ]]` → `yes`.
- Update the 27f comment to say it now covers every setup helper, setup's
  errexit, and a FIFO in place of `.gitignore`.
- **Red proof:** run `bash tests/test_setup_git.sh` and record that the new
  setup rows fail (no "Could not add" line / a "rule added" claim / missing
  `SURVIVED`), and that the `fifo` rows fail with `124` for **every** helper —
  setup and upgrade, since the shared writer hangs too — while every
  pre-existing row stays green. Expect this run to take ~11 × 15s for the
  timeouts. Keep the exact failing assertion names for the plan's Final
  Implementation Notes.

### 2. Writer: open only a regular file; then the table and setup mechanic

**2a. `_ait_add_gitignore_rules` rejects existing non-regular paths before
reading them.** First statement inside the existing-path branch:

```bash
    if [[ -e "$gitignore" || -L "$gitignore" ]]; then
        # Open only a regular file (or a symlink to one): grep blocks on a FIFO
        # until a writer appears and can read a device forever (t2178). Any
        # other existing path is the same "cannot inspect" as an unreadable one.
        [[ -f "$gitignore" ]] || return 2
        for rule in "$@"; do
```
The warning-and-return contract is unchanged: rc 2 → the caller's
`_ait_warn_gitignore_rules_failed`, setup returns 0, nothing written. A symlink
to a regular file stays writable through, as the old `[[ -f ]]` helpers and the
current writer both allow. Extend the function's header comment: rc 2 also
covers "an existing path that is not a regular file". Residual window, accepted:
a regular file swapped for a FIFO between `-f` and `grep` — only a local actor
in the user's own checkout can do that.

**2b.** Next to `_ait_add_gitignore_rules` (the "Discovery-cache gitignore rule"
block, ~line 3160), add:

```bash
# --- .gitignore rule groups: the one table setup and upgrade read (t2178) ---
# _ait_gitignore_group <group> sets, for one group:
#   _ait_gi_comment  the "# ..." line written above the rules
#   _ait_gi_rules    the rules (array), each guarded on its own
#   _ait_gi_what     what a failed write leaves showing as untracked
#   _ait_gi_label    the group's name in upgrade's "Added ... (<label>)" line
# Both routes write a group from here, which is what keeps setup's and
# upgrade's .gitignore byte-identical (tests/test_setup_git.sh 27h). An unknown
# group is a framework bug: die rather than reuse the previous lookup's values.
_ait_gi_comment="" _ait_gi_what="" _ait_gi_label=""
_ait_gi_rules=()
_ait_gitignore_group() {
    case "$1" in
        drafts)     _ait_gi_comment="Draft tasks (local, not committed)"
                    _ait_gi_rules=("aitasks/new/")
                    _ait_gi_what="Draft tasks"; _ait_gi_label="draft tasks" ;;
        pycache)    _ait_gi_comment="Python cache artifacts (generated by aitasks Python TUIs)"
                    _ait_gi_rules=("__pycache__/")
                    _ait_gi_what="Python cache directories"; _ait_gi_label="Python cache artifacts" ;;
        gates)      ...Gate sidecar logs (per-task verifier output; in-body summary is committed)
                    .aitask-gates/ | what "Gate sidecar logs" | label "gate sidecar logs"
        testmap)    ...Test map runs, ledger and onboarding scratch (per-checkout)
                    .aitask-testmap/ | "Test map runs" | "test map scratch"
        shadow)     ...Shadow concern-rejection store (per-task, local-only; pruned at archive)
                    .aitask-shadow/ | "The shadow rejection store" | "shadow rejection store"
        scratchpad) ...Scratchpad notes (per-task, local-only; pruned at archive)
                    .aitask-scratchpad/ | "Scratchpad notes" | "scratchpad notes"
        sitrep)     ...Sitrep todo store (per-repo, local-only; not rebuildable)
                    .aitask-sitrep/ | "The sitrep todo store" | "sitrep store"
        cache)      ...Discovery caches (per-checkout, content-keyed, safe to delete)
                    .aitask-cache/ | "The discovery cache" | "discovery caches"
        worktrees)  ...Framework worktrees (local, per-task and per-crew branches)
                    aiwork/ .aitask-crews/ | "Task and crew worktrees" | "framework worktree directories"
        *) die "unknown .gitignore rule group: $1" ;;
    esac
}
```
(Comment, rule, `what` and `label` strings are copied verbatim from today's
setup helpers and `upgrade_store_gitignore_rules` / `setup_cache_gitignore`.)

```bash
# _ait_setup_gitignore_group <group> <already-line> <added-note>
#   -> 0 rules were written (the caller commits and reports them),
#      1 nothing was written: already present (reported with <already-line>)
#        or not writable (warned via _ait_warn_gitignore_rules_failed).
# Never fatal: callers run it as `|| return 0`.
_ait_setup_gitignore_group() {
    local already="$2" note="$3" rc=0
    _ait_gitignore_group "$1"
    _ait_add_gitignore_rules "$SCRIPT_DIR/../.gitignore" \
        "$_ait_gi_comment" "${_ait_gi_rules[@]}" || rc=$?
    case "$rc" in
        0) info "Added $_ait_gitignore_added to .gitignore ($note)"; return 0 ;;
        1) success "$already" ;;
        *) _ait_warn_gitignore_rules_failed "$_ait_gi_what" "${_ait_gi_rules[@]}" ;;
    esac
    return 1
}
```

### 3. Rebuild the nine setup helpers as wrappers

Each keeps its header comment (t-number rationale) and its own labels; e.g.:

```bash
setup_gate_logs_gitignore() {
    _ait_setup_gitignore_group gates \
        "Gate sidecar-log rule already in .gitignore" "gate sidecar logs" || return 0
    _ait_commit_gitignore_rule "$SCRIPT_DIR/.." "ait: Add .aitask-gates/ to .gitignore (gate sidecar logs)"
    success "Gate sidecar-log rule added to .gitignore"
}
```

Per-helper strings (already / note / commit subject / success), all verbatim
from the current code:

| helper | group | already | note | commit | success |
|---|---|---|---|---|---|
| `setup_draft_directory` (keeps `mkdir -p` first) | drafts | Draft directory already in .gitignore | draft tasks are local-only | ait: Add aitasks/new/ to .gitignore (draft tasks) | Draft directory configured (aitasks/new/ in .gitignore) |
| `setup_python_cache_gitignore` | pycache | Python cache rule already in .gitignore | Python cache artifacts | ait: Add \_\_pycache\_\_/ to .gitignore (Python cache artifacts) | Python cache rule added to .gitignore |
| `setup_gate_logs_gitignore` | gates | Gate sidecar-log rule already in .gitignore | gate sidecar logs | ait: Add .aitask-gates/ to .gitignore (gate sidecar logs) | Gate sidecar-log rule added to .gitignore |
| `setup_testmap_gitignore` | testmap | Test map scratch rule already in .gitignore | test map runs and ledger | ait: Add .aitask-testmap/ to .gitignore (test map scratch) | Test map scratch rule added to .gitignore |
| `setup_shadow_store_gitignore` | shadow | Shadow rejection-store rule already in .gitignore | shadow concern-rejection store | ait: Add .aitask-shadow/ to .gitignore (shadow rejection store) | Shadow rejection-store rule added to .gitignore |
| `setup_scratchpad_gitignore` | scratchpad | Scratchpad notes rule already in .gitignore | scratchpad notes store | ait: Add .aitask-scratchpad/ to .gitignore (scratchpad notes) | Scratchpad notes rule added to .gitignore |
| `setup_sitrep_store_gitignore` | sitrep | Sitrep store rule already in .gitignore | sitrep todo store | ait: Add .aitask-sitrep/ to .gitignore (sitrep todo store) | Sitrep store rule added to .gitignore |
| `setup_cache_gitignore` | cache | Discovery-cache rule already in .gitignore | discovery caches | ait: Add .aitask-cache/ to .gitignore (discovery caches) | Discovery-cache rule added to .gitignore |
| `setup_worktree_dirs_gitignore` | worktrees | Worktree directory rules already in .gitignore | framework worktree directories | ait: Add worktree directories to .gitignore | Worktree directory rules added to .gitignore ($added) |

`setup_worktree_dirs_gitignore` captures `local added="$_ait_gitignore_added"`
right after the group call, so its success line still names only the rules
actually added (13b: a pre-existing `.aitask-crews/` yields `(aiwork/)`).

### 4. Upgrade route reads the same table

- `upgrade_store_gitignore_rules`: replace the six literal calls with
  ```bash
  local group
  for group in gates testmap shadow scratchpad sitrep worktrees; do  # setup's main() order
      _ait_gitignore_group "$group"
      _ait_upgrade_gitignore_rules "$_ait_gi_label" "$_ait_gi_what" \
          "$_ait_gi_comment" "${_ait_gi_rules[@]}"
  done
  return 0
  ```
  Update its header comment (strings now come from the table; order still
  setup's; 27h still pins the bytes).
- `upgrade_cache_gitignore`: keep its own case/messages; take comment and rule
  from `_ait_gitignore_group cache`. Remove `_AIT_CACHE_GITIGNORE_COMMENT` (only
  these two functions used it — verified by grep).
- Refresh the "Discovery-cache gitignore rule (t2173_1)" block comment so it
  points at the table rather than describing the cache as the only hardened
  setup helper.

### 5. Post-step checks

- `shellcheck .aitask-scripts/aitask_setup.sh` — no new warnings vs. HEAD (diff
  the two outputs; the globals assigned in `_ait_gitignore_group` and read
  elsewhere must not raise SC2034).
- `grep -n '>> "\$gitignore"\|> "\$gitignore"' .aitask-scripts/aitask_setup.sh`
  → no hits outside `_ait_add_gitignore_rules` (the data-branch
  `$data_gitignore` writers in `setup_data_branch` are a different file and out
  of scope).

## Verification

- `bash tests/test_setup_git.sh` — all green, including the new 27f rows, the
  bounded errexit assertions and the `fifo` fault for all eleven helpers (each
  returns in well under the 15s bound, FIFO still in place), 27a/27b (dirty baseline / path-scoped commit) for all nine
  helpers, 27g/g2/g3, 27h byte-identical parity, 27i drift guard, Tests 7/8
  (draft dir), 18/19 (pycache commit message + idempotence).
- Other suites that drive these helpers:
  `bash tests/test_data_branch_setup.sh` (13/13b worktree rules, 34/35),
  `bash tests/test_install_engine_binary.sh` (G: testmap rule),
  `bash tests/test_t167_integration.sh`, `bash tests/test_setup_failopen_probes.sh`
  (6 / 6-n: draft helper under an unverified baseline + its mutant),
  `bash tests/test_install_upgrade_dirty_baseline.sh` (upgrade route).
- Red proof recorded from step 1 (new rows red on the old helpers).
- Pre-refactor proof: 27k green on the unchanged helpers (pre-phase), still
  green after steps 3–4.

## Risk

### Code-health risk: low
- Once setup and upgrade both read one table, 27h's byte-parity compares the table with itself, so a mis-copied comment or rule (or a changed already / success / commit string, none pinned today) would pass unnoticed · severity: medium · → mitigation: inline pre-phase pin_gitignore_writer_outputs
- Table lookups communicate through `_ait_gi_*` globals (implicit coupling); a skipped lookup would reuse stale values · severity: low · → mitigation: none (each reader calls `_ait_gitignore_group` immediately before use; an unknown group dies)
- The writer's new `-f` gate changes the shared writer the upgrade route also uses · severity: low · → mitigation: none beyond the plan (27f's `fifo` rows run every upgrade helper too; 27g/g2/g3/h stay green)
- Residual TOCTOU between the `-f` check and the read (regular file swapped for a FIFO) · severity: low · → mitigation: none (accepted: requires a local actor in the user's own checkout)

### Goal-achievement risk: low
None identified.

### Planned mitigations
- timing: pre-phase | name: pin_gitignore_writer_outputs | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — table self-parity hides string drift | desc: Test 27k pins every setup/upgrade .gitignore block, commit subject and message line against literals, green before the refactor

## Post-implementation

Step 9 of the task workflow: commit (`bug: … (t2178)`), archive the task and
plan.
