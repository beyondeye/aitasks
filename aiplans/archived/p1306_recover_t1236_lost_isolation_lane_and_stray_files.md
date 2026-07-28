---
Task: t1306_recover_t1236_lost_isolation_lane_and_stray_files.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1306 — Recover t1236's lost isolation lane and triage stray uncommitted files

## Context

An audit of the 8 uncommitted paths in this shared checkout found that four of
them are not in-flight work and not ordinary leftovers: they are the **only
surviving copy** of a task that is already archived as `Done`.

t1236 ("PYTHONPATH-isolated python test lane") shipped four files. Their content
was swept into commit `e22bdc582` by a concurrent session's index-wide commit;
commit `442dbc42c` was then landed as an empty traceability marker stating the
content lives in `e22bdc582` and deliberately leaving that commit unrewritten.
`e22bdc582` was rewritten anyway into `eb1a4f7ea` (t1235, currently on main)
with all four t1236 paths dropped. Verified: `git merge-base --is-ancestor
e22bdc582 HEAD` reports "not an ancestor", and the working-tree copies are
byte-identical to `e22bdc582`'s blobs.

Net effect on `main`: the PYTHONPATH masking t1236 was created to remove is
still in place, the three new test/helper files exist nowhere in history, and
the task + plan are archived as complete. The surviving copies are uncommitted
and one `git stash` away from being lost for good.

The remaining four uncommitted paths are unrelated strays that this task
disposes of so `git status` ends clean.

## Current state (verified in this session)

- `git status --porcelain` → `M .claude/settings.local.json`,
  `M tests/run_all_python_tests.sh`, `?? .antigravitycli/`,
  `?? .opencode/package-lock.json`, `?? aidocs/slack/`,
  `?? tests/lib/import_isolated.py`, `?? tests/test_python_bootstrap_isolation.sh`,
  `?? tests/test_runner_python_isolation.sh`.
- `bash tests/test_python_bootstrap_isolation.sh` → **PASSES** on the current
  tree (10 assertions; swept 156 test files in isolated interpreters).
- `bash tests/test_runner_python_isolation.sh` → **PASSES** (9 assertions).
- `git grep import_isolated HEAD` → empty; no committed file references the
  missing helpers, so HEAD is self-consistent — the lane is simply absent.
- `aitasks/t1179_python_test_runner_masks_failures.md` is status `Implementing`
  and its upstream defect is `tests/run_all_python_tests.sh:22-26` (the
  summary/exit-code masking — a *different* defect in the *same file*). The
  working-tree copy of that file currently matches `e22bdc582` exactly, so
  t1179 has not edited it yet.

## Approach

Restore forward with a new commit. Do **not** rewrite or revert `eb1a4f7ea` —
the history is shared and another session was active on it.

### 1. Re-verify before staging (concurrency guard)

The four files are already in the working tree with the correct content, so
"implementation" here is verification + staging, not editing.

```bash
# a. Prove the working tree still matches the orphaned blobs (no drift since audit)
for f in tests/lib/import_isolated.py tests/run_all_python_tests.sh \
         tests/test_python_bootstrap_isolation.sh tests/test_runner_python_isolation.sh; do
  diff <(git show e22bdc582:"$f") "$f" >/dev/null && echo "OK $f" || echo "DRIFT $f"
done

# b. No foreign staged hunks from a concurrent session
git diff --cached --stat
```

- Any `DRIFT` on `tests/run_all_python_tests.sh` means t1179's session has
  edited it. In that case do **not** restore the old blob wholesale — re-apply
  only t1236's change (`unset PYTHONPATH` plus its explanatory comment) on top
  of the current content, keeping t1179's edits intact.
- Any foreign staged content → stage this task's paths explicitly (never
  `git add -A`) and leave the rest alone.

### 2. Move the Slack notes into the canonical chat-docs directory

`aidocs/chat/` is where chat-platform docs live (`slack_app_setup.md`,
`discord_bot_setup.md`, `chatlink_runtime.md`, …). Per the user's decision:

```bash
mkdir -p aidocs/chat
git mv --force aidocs/slack/pros_and_cons.md aidocs/chat/claude_tag_pros_and_cons.md 2>/dev/null \
  || mv aidocs/slack/pros_and_cons.md aidocs/chat/claude_tag_pros_and_cons.md
rmdir aidocs/slack
```

The file is a short hand-written note whose "Disadvantages of claude tag:"
heading has no bullets under it. Commit it as-is (it is scratch/thinking
material, not a spec); do not invent content for the empty section.

### 3. Ignore the two tool-generated artifacts

- `.opencode/package-lock.json` — `.opencode/.gitignore` already ignores
  `node_modules`, `package.json`, `bun.lock`, `.gitignore`, but not the npm
  lockfile. Add `package-lock.json` to **`.opencode/.gitignore`** (the local
  precedent), not the root file.
- `.antigravitycli/` — Antigravity CLI per-machine workspace state (records an
  absolute repo path and a write-permission grant). Add `.antigravitycli/` to
  the **root `.gitignore`**, next to the other local-state dirs
  (`.aitask-crews/`, `.aitask-gates/`, `.aitask-history/`), with a one-line
  comment following the existing style.

Verify both with `git check-ignore -v <path>`.

### 4. Verify the restored lane against the *current* tree

Already confirmed passing this session, but re-run after staging (and record
results in the plan's Final Implementation Notes):

```bash
bash tests/test_runner_python_isolation.sh        # 9 assertions
bash tests/test_python_bootstrap_isolation.sh     # 10 assertions, sweeps 156 files
bash tests/run_all_python_tests.sh                # full suite with unset PYTHONPATH
```

`tests/test_runner_python_isolation.sh` already carries its own negative
controls (Test 2 re-adds the export, Test 3 strips the `unset`, Test 4 pins a
commented-out export as benign), and
`tests/test_python_bootstrap_isolation.sh` carries a positive control, two
negative controls, and a flat-layout tripwire. No new negative control needs to
be written — the AC's "prove the guard discriminates" is satisfied by running
these and confirming Tests 2–4 / 3–4 respectively still fail-on-broken.

If `run_all_python_tests.sh` surfaces failures **unrelated** to this task
(t1179's diagnosis recorded pre-existing failures that the runner's exit code
masks), do not fix them here — log them in the Final Implementation Notes and
leave them to t1179, which owns that defect.

### 5. Commit

One code commit, tagged so the changelog / `aitask_issue_update.sh` can find it:

```
test: Restore t1236 python isolation lane dropped by history rewrite (t1306)
```

Body records: the four paths, that they were dropped by the
`e22bdc582` → `eb1a4f7ea` rewrite, and that `442dbc42c`'s claim is thereby
made true. Staged paths (explicit, no `-A`):

- `tests/run_all_python_tests.sh`
- `tests/lib/import_isolated.py`
- `tests/test_python_bootstrap_isolation.sh`
- `tests/test_runner_python_isolation.sh`
- `.gitignore`, `.opencode/.gitignore`
- `aidocs/chat/claude_tag_pros_and_cons.md` (+ removal of `aidocs/slack/`)
- `.claude/settings.local.json` (per the user's decision; matches how this file
  has historically ridden along in feature commits)

`aitasks/` and `aiplans/` are never mixed into this commit — they go through
`./ait git` separately.

## Files touched

| Path | Change |
|------|--------|
| `tests/run_all_python_tests.sh` | commit existing working-tree change (`unset PYTHONPATH`) |
| `tests/lib/import_isolated.py` | commit (new file) |
| `tests/test_python_bootstrap_isolation.sh` | commit (new file) |
| `tests/test_runner_python_isolation.sh` | commit (new file) |
| `.gitignore` | add `.antigravitycli/` |
| `.opencode/.gitignore` | add `package-lock.json` |
| `aidocs/slack/pros_and_cons.md` | → `aidocs/chat/claude_tag_pros_and_cons.md` |
| `.claude/settings.local.json` | commit accumulated allowlist entries |

## Verification

- `git show HEAD --stat` lists all four t1236 paths.
- `git status --porcelain` is empty (or contains only paths this task
  deliberately left alone).
- `git check-ignore -v .antigravitycli/x .opencode/package-lock.json` reports
  the new rules.
- The three test commands in §4 pass (or their failures are attributed and
  logged).
- `git log --oneline -1` subject matches `test: … (t1306)`.

## Step 9 (Post-Implementation)

Current-branch profile — no worktree/branch to merge. Step 9 runs the gate
orchestrator (`./ait gates run 1306`, which owns `risk_evaluated`) and then
`./.aitask-scripts/aitask_archive.sh 1306`.

## Risk

### Code-health risk: medium
- The restored `unset PYTHONPATH` changes how the whole Python suite resolves
  imports, so any test file with a wrong `sys.path` bootstrap starts failing
  where it previously passed. The tree has moved since t1236 was written
  (`eb1a4f7ea` promoted `stats_data.py` from `stats/` to `lib/`), so the lane is
  being reintroduced against code it never ran against · severity: medium ·
  mitigated in-task: both isolation tests were re-run against the current tree
  this session and pass (156 files swept, 0 broken) · → mitigation: none needed
- Concurrent-session collision: t1179 is `Implementing` against the same
  `tests/run_all_python_tests.sh`. Staging a stale blob could silently revert
  its in-flight edits · severity: medium · → mitigation: the §1 drift check +
  explicit-path staging, both mandatory pre-commit steps in this plan
- Committing `.claude/settings.local.json` alongside test changes mixes
  unrelated local config into a `(t1306)` commit · severity: low · → mitigation:
  none — this matches the file's existing commit history and was the user's
  explicit decision

### Goal-achievement risk: low
- None identified. The goal is fully specified (four known paths, verified
  byte-identical to a known-good blob), every step is directly verifiable, and
  the disposition of each stray file was decided by the user before planning.

## Final Implementation Notes

- **Actual work done:** All four t1236 paths restored to `main` in one commit.
  The §1 concurrency guard passed clean — all four working-tree files still
  diffed empty against `git show e22bdc582:<path>`, and `git diff --cached`
  was empty (no foreign staged hunks), so no re-application on top of drifted
  content was needed. `aidocs/slack/pros_and_cons.md` was moved to
  `aidocs/chat/claude_tag_pros_and_cons.md` and the emptied `aidocs/slack/`
  removed. Two ignore rules added. `.claude/settings.local.json`'s six
  accumulated allowlist entries were re-diffed immediately before staging and
  were byte-identical to what the audit saw, then committed.

- **Deviations from plan:** The plan put the `package-lock.json` rule in
  `.opencode/.gitignore`, following that file's existing sibling rules
  (`node_modules`, `package.json`, `bun.lock`). During implementation
  `git ls-files --error-unmatch .opencode/.gitignore` showed the file is
  **untracked** — its own last line is `.gitignore`, so it ignores itself. A
  rule there is local-only and would leave `package-lock.json` visible in every
  other checkout, which is exactly the drift this task exists to clean up. The
  edit was reverted and the rule placed in the tracked root `.gitignore`
  instead, with a comment recording why it is separated from its siblings.
  Verified by `git check-ignore -v`, which cites `.gitignore:27` (root), not
  `.opencode/.gitignore`.

- **Issues encountered:** None blocking. The plan's contingency for t1179
  (`Implementing` against the same `tests/run_all_python_tests.sh`) never
  fired — that session had not touched the file.

- **Key decisions:** Restore forward with a new commit rather than rewriting or
  reverting `eb1a4f7ea`. The history is shared and a concurrent session was
  active on it; `442dbc42c`'s own message had already made that call for the
  same reason, and repeating the rewrite is the more damaging failure mode.

- **Verification results:**
  - `bash tests/test_runner_python_isolation.sh` → 9 passed, 0 failed
    (includes its own negative controls: a re-added `PYTHONPATH` export and a
    stripped `unset` are both flagged; a commented-out export is not).
  - `bash tests/test_python_bootstrap_isolation.sh` → 10 passed, 0 failed;
    swept 156 test files in isolated interpreters, 0 broken bootstraps
    (includes a positive control, a broken-bootstrap negative control, and a
    poisoned-`PYTHONPATH` negative control).
  - `bash tests/run_all_python_tests.sh` → `Ran 2544 tests in 707.746s`,
    `OK (skipped=1)`, exit 0. The full suite passes with `PYTHONPATH` unset, so
    no test was relying on the removed seeding. This retires the code-health
    risk above: the lane was reintroduced against the post-`eb1a4f7ea` tree and
    found nothing broken.
  - `git check-ignore -v` → `.gitignore:22` for `.antigravitycli/…`,
    `.gitignore:27` for `.opencode/package-lock.json`; negative control
    `.opencode/instructions.md` is correctly not ignored.

- **Upstream defects identified:** None. (The `442dbc42c` / `e22bdc582` /
  `eb1a4f7ea` sequence that caused this task is a process/history-rewrite
  incident, not a defect in a script or module. The pre-existing runner
  exit-code masking is already owned by t1179.)
