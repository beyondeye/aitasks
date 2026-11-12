---
Task: t2277_safe_unwind_of_owned_staged_paths_after_wedge.md
Base branch: main
Output branch: main
---

# t2277 — Staged entries of uncertain ownership: detect, guide, prove (no unwind)

## Context

`ait_unstage_staged_by_us` (`.aitask-scripts/lib/task_utils.sh:1066`) leaves the
paths a run staged in the shared `.aitask-data` index when the data worktree is
wedged. It names them on stderr (t2271). t2277 asked for a safe unwind. Planning
measured (git 2.56, scratch repos) that **the current ownership checks cannot
justify cleanup after arbitrary git operations**:

- With a new file of ours staged, plain `merge` / `rebase` / `pull` /
  `cherry-pick` / `revert` all refuse (no wedge). `--autostash` moves our entry
  into the stash, so a same-path index entry afterwards is the operation's.
  `am` refuses but leaves `rebase-apply/` behind, and `bisect` tolerates the
  entry. In both of those the entry is still ours.
- A merge that starts in the gap between the helper's in-loop guard and its
  `add` mixes its entries with ours. Two no-autostash merge states (one entry
  ours, one the merge's) gave **byte-identical** facts: `ls-files -s`, HEAD
  absence, no unmerged entry, MERGE_HEAD present, no MERGE_AUTOSTASH.
- In the `merge --autostash` counter-example, `git reset -- <path>` (what an
  unconditional cleanup runs) drops the incoming file from the merge commit.
- Recovery itself acts on uncertain entries. When an unrelated new file is
  staged into a stopped merge, resolving and committing the merge **commits**
  it, and `git merge --abort` **removes it from the index and the worktree**.
  (After `merge --autostash`, abort re-applies the stash and restores our
  entry.) So the guidance can never be "resolve or abort first". It must be:
  inspect, coordinate with the operation's owner, and copy aside what you want
  to keep, before either step.

This does **not** rule out preventing the interleaving among cooperating
framework operations. That is serialization, which belongs to **t1678**
(`data_index` lock adoption across task-data writers; user decision, not done
here). This task therefore:
1. keeps the name-and-leave behaviour unchanged;
2. makes leftover staged entries visible through `ait git-health`, described as
   **staged entries with uncertain ownership** (never "abandoned" or
   "ownerless"), with guidance that requires inspection before changing them;
3. adds real-operation tests that show why the cleanup must preserve ambiguous
   entries;
4. keeps the existing preservation assertions and corrects the stale references;
5. records the overlap and findings in an advisory note to t1678.

## Steps

### 1. `ait git-health`: staged-entry check — `.aitask-scripts/lib/task_utils.sh`

Add a private helper `_ait_git_health_staged <hits…>` and call it at the end of
`task_git_health` (branch mode only; legacy mode still returns early). The
helper:

- runs `git -C .aitask-data -c core.quotePath=true diff --cached --name-status --no-renames`.
  The exit status is captured explicitly with `|| rc=$?` (`ait` runs under
  `set -euo pipefail`). With quotePath, odd paths come back C-quoted and safe
  to print.
- **rc ≠ 0** → `warn "Staged entries: could not read the index (git diff --cached exited <rc>) — unknown, not none."`
  The "Clean" line is then not printed (no all-clear without positive evidence).
- **empty output** → no extra lines. The final success line becomes
  `Clean — no in-progress rebase/merge/cherry-pick/revert/bisect, and nothing staged.`
  It prints only when there are no hits, no detached HEAD and the staged read
  succeeded empty.
- **non-empty** →
  ```
  warn  "Staged entries in the shared .aitask-data index — ownership uncertain (<N>):"
        "    <status>  <path>"   (at most 20 lines, then "    … and <K> more")
  info  "  Every session on this machine shares this index. An entry may belong to a commit another session is making right now, to an in-progress git operation, or to a run whose cleanup left it in place and named it on stderr. This check cannot tell which."
  [only when <hits> non-empty]
  info  "  An operation is in progress (<hits>), and these entries are in its index. Before you continue OR abort it, inspect them (./ait git diff --cached --name-status) and check with whoever started the operation and with any session committing these paths. Continuing (--continue, or committing a resolved merge) commits every staged entry, including ones that are not the operation's. Aborting can discard them: a new file staged into a stopped merge is removed from the index AND the worktree by merge --abort. Copy aside any uncertain new file you want to keep before either step."
  [always]
  info  "  Inspect before changing anything: ./ait git diff --cached -- <path>. Re-run ./ait git-health in a moment: an entry another session was committing will be gone."
  info  "  Unstage only an entry you have confirmed is yours and unwanted, and only with no operation in progress: ./ait git reset -q -- <path>  (the file in the worktree is kept)."
  ```
  The check never suggests a guard bypass (`AIT_GIT_SKIP_STATE_CHECK`), and
  never unstages anything itself.
- returns 0 in every branch (`git-health` is informational, and its only
  caller is `ait git-health` at `ait:362`).

`task_git_health` passes its `hits` array so the in-progress line names the same
states it already reported.

### 2. Cleanup warning and comment — same file

- `ait_unstage_staged_by_us`: keep the first sentence verbatim (tests pin
  `were LEFT in the shared index`). Replace the second line ("Once the operation
  is resolved, … unstage …"). It prints right after the guard's own
  `--abort`/`--continue` recovery list, so it must qualify that list:
  `Before you continue or abort that operation, inspect the staged entries (./ait git-health lists them) and check with its owner: continuing commits these paths with the operation, and aborting can discard them from the index and the worktree. Copy aside any you want to keep first. Unstage one only after the operation is finished and you have confirmed it is yours: ./ait git reset -q -- <path>`
- Its header comment: replace `(t2271; a safe unwind needs ownership or
  serialization evidence — t2277)` with a short current-state statement.
  t2277 measured that no check over the index or the wedge markers separates
  these cases (`tests/test_staged_entry_ownership.sh`). Preventing the
  interleaving among cooperating framework writers is t1678's `data_index`
  adoption. `ait git-health` lists what is left.

### 3. New test file `tests/test_staged_entry_ownership.sh`

Self-contained. All assertions run in the main shell (no `( … )` test bodies).
It uses `tests/lib/asserts.sh` + `tests/lib/sync_fixture.sh` (`setup_repo`,
which gives branch mode with tracked `aitasks/t10_alpha.md` / `t20_beta.md`),
the same shape as `tests/test_task_commit_scoped.sh`. A private
`AITASKS_LOCK_DIR` keeps it off the real lock base. Fixture helper
`own_fixture <t>`: in the data repo it creates branch `incoming` from data HEAD,
which edits `t10_alpha.md` (conflict) and **adds `aitasks/t86_first.md` with
exactly the content the caller will write**. A second branch `incoming_noadd`
makes only the conflicting edit. Then a conflicting edit of `t10_alpha.md` is
committed on `aitask-data`.

A capability probe that does not run the code under test (`git merge -h`
mentions `--autostash`) gates R1 and C1 with a visible `SKIP:` line.

- **R1 — real `merge --autostash` after our add (the counter-example, through
  the real caller).** A PATH `git` shim runs the real `add` of
  `aitasks/t86_first.md`. It then runs the real
  `git -C .aitask-data merge --autostash incoming`, which stops on the
  conflict. Then run `aitask_task_commit.sh -m … aitasks/t86_first.md aitasks/t87_second.md`.
  The next iteration's guard dies, and the EXIT-trap cleanup runs. Assert:
  non-zero exit; `stuck mid-MERGE_HEAD`; `were LEFT in the shared index` +
  names `t86_first`; MERGE_HEAD **and** MERGE_AUTOSTASH exist (real-op
  provenance). The entry passes every check the t2271 review rejected: stage 0,
  blob == `hash-object` of our file, absent from HEAD, no `ls-files -u` entry.
  Yet the blob also equals `incoming:aitasks/t86_first.md`. `./ait git-health`
  lists `aitasks/t86_first.md` under `ownership uncertain`, prints the
  in-progress line, and contains none of `abandoned` / `ownerless` / `orphan`.
  Resolve the conflict, `add` it and commit the merge. The merge commit
  **contains** `t86_first.md` (the incoming addition survived).
- **R1-NC — negative control, same fixture.** After the same run, apply what an
  unconditional cleanup would do (`git reset -q -- aitasks/t86_first.md`),
  resolve and commit. The merge commit **lacks** `t86_first.md`. This asserts
  the harm positively, so R1 cannot pass by measuring nothing.
- **R2 — real merge started in the guard→add gap (the entry IS ours).** The shim
  runs the real `merge incoming_noadd` (clean index, no bystander) **before**
  the real `add` of t86. The add stages into the merging index, and the scoped
  commit's guard dies. Assert the cleanup names t86 and leaves it (the cost of
  the limitation, pinned so it is not mistaken for a bug), and `git-health`
  lists it. The output must carry the inspect-and-coordinate wording (it names
  `continue`, `abort`, the inspect command and "copy aside") and must **not**
  contain `resolve or abort it first`.
- **R2-continue / R2-abort — why the guidance says "inspect before continuing
  or aborting" (characterization through the R2 fixture, two fresh copies).**
  (a) Resolve `t10_alpha.md`, `add` it and commit the merge. The merge commit
  **contains** the unrelated `t86_first.md`. (b) Run `git merge --abort` (raw
  git; the test drives git, not the framework). `t86_first.md` is gone from
  the index **and** the worktree. Both were measured in scratch during
  planning; these assertions keep the guidance claims true across git
  versions.
- **C1 — characterization (raw git, no helper).** Build the not-ours twin of R2
  in raw git: `merge incoming` (clean index, no autostash) stops, then t86 is
  written and added. Compare a facts vector with R2's: `ls-files -s`, HEAD
  presence, `ls-files -u` count, which of MERGE_HEAD / MERGE_AUTOSTASH exist.
  Assert it is **identical** while ownership differs. This refutes a future
  "autostash marker or index state proves ownership" proposal with a test.
- **H1 — clean:** `git-health` prints the `… and nothing staged.` line and no
  `ownership uncertain`.
- **H2 — bystander staged, no wedge:** lists `t20_beta.md` with `M`, says
  `ownership uncertain`, contains the inspect command
  (`./ait git diff --cached --`), and the `reset` hint appears only after it.
  No in-progress line, no `Clean` line, none of `abandoned` / `ownerless` /
  `orphan`.
- **H3 — index unreadable:** a PATH shim fails `diff --cached`. Assert
  `unknown, not none` and no `Clean` line.
- **H4 — cap:** 22 staged new files give 20 listed lines and `… and 2 more`.

Header comment: the measured probe table above (op → refuses / autostash / tolerates),
the facts-vector result, and a mutation table **measured during
implementation**. Mutations, each in a copy of `task_utils.sh` loaded via an
override hook like `TC_LIB_OVERRIDE`:
- cleanup resets via `_ait_data_git` on a wedge → R1 fails
  (merge commit lacks t86);
- drop the `rc` check → H3 fails;
- drop the cap → H4 fails;
- drop the wedge line → R1's git-health assertion fails.

### 4. Existing tests — keep assertions, correct references

- `tests/test_task_commit_scoped.sh` Test 9e comment (lines 480-484). It keeps
  the "preserved" assertion. Replace "When t2277 lands a safe unwind, the
  'preserved' assertion is the one to flip" with: preservation is deliberate.
  `tests/test_staged_entry_ownership.sh` shows why with real operations, and
  serialization is t1678. Header mutation table unchanged (no test added here).
- `tests/test_issue_update_ledger.sh` (s2) comment (around line 598): replace
  `(safe unwind: t2277)` with the same pointer. The assertion at line 615
  stays.
- The task file names "case u", but the preserved assertion is **case (s2)**.
  Correct it in the task body (`aitask_update.sh --batch 2277 --desc-file`),
  and record it in Final Implementation Notes.

### 5. Docs — `website/content/docs/commands/sync.md` § `ait git-health`

Add a bullet to the "flags anything…" list: staged entries in the shared index
whose ownership the check cannot determine, with inspect-first guidance
(current-state prose, no history). Say that while an operation is in progress,
continuing commits these entries and aborting can discard them, so inspect and
coordinate before either step.

**Out of scope, offered as a follow-up at Step 8c (not done here).** The guard
messages in `assert_data_worktree_clean` / `assert_task_data_writable` say
`'--abort' … discards only the partially replayed remote commits`. That claim
is incomplete when the index holds staged entries the operation does not own:
measured, `merge --abort` removed such a new file from the index and the
worktree. This task qualifies the claim in the cleanup warning that follows the
message. Rewording the shared guard text (pinned verbatim by other tests) is a
separate change. Update "A clean worktree reports no
in-progress operations" to "…no in-progress operations and nothing staged". Run
`cd website && python3 check_links.py --build`.

### 6. Advisory note to t1678 (via the `/aitask-note` skill, `--from 2277`)

Content (hedged; tree-relative claims dated by the note's SHA):
- `ait_commit_paths_staging_untracked` (`lib/task_utils.sh`) is an index writer
  outside `data_index`. Its callers: `aitask_task_commit.sh`,
  `aitask_metadata_commit.sh`, `verified_update_lib.sh`,
  `release_issue_ledger.sh`, `aitask_create_manual_verification.sh`,
  `aitask_verification_followup.sh` (plus usage/verified-update through
  `verified_update_lib`). For the cleanup to stay sound, the lock must cover
  stage → commit → unstage-cleanup.
- Wedging writers: `_ait_owned_pull` (pick-time pull + `ait git pull`) holds
  only the pull mutex (`<gitdir>/aitask-pull.lock`). `aitask_sync.sh`
  `do_pull_rebase` / its `merge --ff-only` hold neither. An interleaving can
  stage into a stopped rebase's index, and the automerge `--continue` would
  then commit it.
- Constraints for adoption: `registry_lock_acquire` installs an EXIT trap,
  which would replace these callers' `trap ait_unstage_staged_by_us EXIT`
  (needs a no-trap adapter, like the pull mutex). Decide nesting vs. merging
  with the pull mutex.
- Critical-section boundary: only the network **fetch** may stay outside the
  lock. Acquire exclusion **before** pinning HEAD/@{u} and before validating
  any local state the operation then acts on. Hold it through the operation's
  completion **and** its cleanup (abort / unstage). Any evidence gathered
  before the acquire (a pin, a dirty scan, a wedge check) must be revalidated
  under the lock: a concurrent writer can invalidate it in between. This
  matches what t1984 (already in t1678's inbox, from t1792) requires: writer
  exclusion from pinning through rebase completion.
- Even after adoption, a raw git operation can still wedge mid-run, so
  name-and-leave stays for that residue. `tests/test_staged_entry_ownership.sh`
  pins why.
- t2277 is related to the `art:trail-parallel-git-and-sync` trail but is not a
  member. Membership changes are left to a separate trail refresh.

### 7. Verification

```bash
bash tests/test_staged_entry_ownership.sh
bash tests/test_task_commit_scoped.sh
bash tests/test_issue_update_ledger.sh
bash tests/test_task_git.sh
bash tests/test_task_push.sh
shellcheck .aitask-scripts/lib/task_utils.sh
(cd website && python3 check_links.py --build)
```
Run the mutation rows of Step 3 against a lib copy and record the measured
table.

## Risk

### Code-health risk: low
- The `git-health` "Clean" line changes wording, and a new `git diff --cached`
  call runs under `ait`'s `set -euo pipefail` · severity: low. The only
  consumer is `ait git-health`, and no test or script parses the line. The rc
  is captured explicitly (Step 1) · → mitigation: covered in-plan (Step 1, H3).
- The new real-operation tests depend on git's `merge --autostash` and on the
  untracked-overwrite refusal · severity: low · → mitigation: covered in-plan
  (Step 3 capability-probe SKIP, independent of the code under test).

### Goal-achievement risk: low
- The task title asks for a safe unwind. The user re-scoped it to
  detect-and-prove, with serialization in t1678 · severity: low · →
  mitigation: covered in-plan (Context + Step 6 note; Final Implementation
  Notes record the re-scope).
- `git-health` could list a transient entry from another session's in-flight
  commit · severity: low · → mitigation: covered in-plan (wording says
  "ownership uncertain", says to re-run in a moment and to inspect first).

### 8. Step 9 (Post-Implementation)

Commit code and tests with paths named (the main index holds another session's
staged files). Commit the plan via `aitask_task_commit.sh`, then archive per the
workflow.
