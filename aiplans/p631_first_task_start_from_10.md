---
Task: t631_first_task_start_from_10.md
Base branch: main
plan_verified: []
---

## Context

Task **t631**: After `ait setup` bootstraps a brand-new project (no existing tasks), the first task created gets ID `t10`, not `t1`. This surprises users.

**Root cause:** `.aitask-scripts/aitask_claim_id.sh` computes the initial counter value as `next_id = max_id + ID_BUFFER`, where `ID_BUFFER=10`. `scan_max_task_id` returns `0` in an empty project, so the counter starts at `10`. The buffer was originally added as defensive margin against unscanned existing task IDs (`426f3300 Prevent duplicate task IDs with atomic counter and draft workflow (t108)`), but in practice `scan_max_task_id` already covers every task location (active, children, archived loose, numbered/legacy archives), so the buffer creates confusing UX without real safety.

**Decision:** Drop the `ID_BUFFER` entirely. Always start at `max_id + 1`. New projects begin at `t1`; existing projects continue sequentially from the highest scanned ID.

## Scope

One script change, two test file updates, one doc line update. No seed changes (the script lives only in `.aitask-scripts/`, which is installed from the framework, not seeded).

## Changes

### 1. `.aitask-scripts/aitask_claim_id.sh` — drop the buffer

- **Line 31**: Remove `ID_BUFFER=10`.
- **Line 76** (`init_counter_branch`): `local next_id=$((max_id + ID_BUFFER))` → `local next_id=$((max_id + 1))`.
- **Line 79**: Change info message from `"Initializing counter branch with next_id=$next_id (max + $ID_BUFFER buffer)"` → `"Initializing counter branch with next_id=$next_id (max + 1)"`.
- **Line 107** (`init_local_branch`): `local next_id=$((max_id + ID_BUFFER))` → `local next_id=$((max_id + 1))`.
- **Line 109**: Debug message `"Initializing local counter branch with next_id=$next_id (max=$max_id + buffer=$ID_BUFFER)"` → `"Initializing local counter branch with next_id=$next_id (max=$max_id + 1)"`.
- **Line 251** (`peek_counter`, no-remote + no-branch branch): `echo $((max_id + ID_BUFFER))` → `echo $((max_id + 1))`.

### 2. `tests/test_claim_id.sh` — update expected counter values

`setup_paired_repos` creates `t1..t5` (max=5). Old expected first-claim value was `5+10=15`; new is `5+1=6`.

- **Line 143**: comment `# Counter should be max(5) + 10 = 15` → `# Counter should be max(5) + 1 = 6`.
- **Line 145**: `assert_eq "Counter initialized to max+10" "15" "$counter_val"` → `assert_eq "Counter initialized to max+1" "6" "$counter_val"`.
- **Line 147**: `assert_contains "Output mentions counter value" "15" "$output"` → `"6"`.
- **Line 168**: `assert_eq "First claim returns 15" "15" "$claimed"` → `"First claim returns 6"` and `"6"`.
- **Line 180–182**: `"First sequential claim"/"15"`, `"Second…"/"16"`, `"Third…"/"17"` → `"6"`, `"7"`, `"8"`.
- **Line 195**: `assert_eq "Counter is 17 after 2 claims from 15" "17" "$counter_after"` → `"Counter is 8 after 2 claims from 6" "8"`.
- **Test 7 (Line 249–255)**: max=3 (t1..t3 created inline). Old: 13, 14. New: 4, 5. Update:
  - Line 249 comment: `# First claim: … max=3, buffer=10, counter starts at 13, claims 13` → `… max=3, counter starts at 4, claims 4`.
  - Line 251: `"No remote: first claim returns max+buffer" "13"` → `"No remote: first claim returns max+1" "4"`.
  - Line 255: `"14"` → `"5"`.
- **Test 8 (Line 279)**: max=50 (archived). `"Counter scans archived: max(50)+10=60" "60"` → `"Counter scans archived: max(50)+1=51" "51"`.
- **Test 9 (Line 297)**: max=100 (tar). `"Counter scans tar: max(100)+10=110" "110"` → `"Counter scans tar: max(100)+1=101" "101"`.
- **Test 12 (Line 345–352)**: max=10 (aitasks/t10_task.md existing).
  - Line 345 comment: `# Peek before any claim: no local branch yet, shows max+buffer` → `… shows max+1`.
  - Line 347: `"Peek with no remote (no branch): max+buffer=20" "20"` → `"Peek with no remote (no branch): max+1=11" "11"`.
  - Line 352: `"Peek with no remote (after claim): counter=21" "21"` → `"counter=12" "12"`.
- **Test 13 (Line 373–375)**: max=0. Old: 10. New: 1.
  - Line 373 comment: `# max=0, buffer=10, counter starts at 10, first claim returns 10` → `# max=0, counter starts at 1, first claim returns 1`.
  - Line 375: `"No remote, no tasks: returns buffer value" "10"` → `"No remote, no tasks: returns 1" "1"`.
- **Test 14 (Line 401–410)**: max=1 (t1_task.md). Old: 11, 12. New: 2, 3.
  - Line 401 comment: `# Claim locally (no remote) — should create local branch and return 11 (max=1, buffer=10)` → `… return 2 (max=1)`.
  - Line 403: `"Auto-upgrade: local claim returns 11" "11"` → `"Auto-upgrade: local claim returns 2" "2"`.
  - Line 410: `"Auto-upgrade: remote claim returns 12" "12"` → `"remote claim returns 3" "3"`.

### 3. `tests/test_draft_finalize.sh` — update expected IDs

`setup_draft_project` creates `t1` and `t2` (max=2). Old first-claim: `2+10=12`. New: `2+1=3`.

- **Line 245 comment**: `# Counter should be at 12 (max(2) + 10 = 12)` → `# Counter should be at 3 (max(2) + 1 = 3)`.
- **Line 251 comment**: `# The finalized file should be t12_claim_test.md (first claim from counter starting at 12)` → `… t3_claim_test.md (first claim from counter starting at 3)`.
- **Line 252**: `assert_file_exists "Finalized as t12" ".../aitasks/t12_claim_test.md"` → `"Finalized as t3"` and `.../aitasks/t3_claim_test.md`.
- **Line 267**: `assert_contains "Commit message has task ID" "t12" "$last_commit6"` → `"t3"`.
- **Line 293 comment**: `# 3 new task files should exist (t12, t13, t14)` → `… (t3, t4, t5)`.
- **Line 294**: `ls ".../aitasks"/t1[234]_*.md` → `ls ".../aitasks"/t[345]_*.md`.

### 4. `website/content/docs/development/_index.md` — update doc

- **Line 104**: `- Initialized via \`ait setup\` with a buffer of 10 above the highest existing task ID` → `- Initialized via \`ait setup\` to one above the highest existing task ID (so new projects start at t1)`.

## Files to modify

- `/home/ddt/Work/aitasks/.aitask-scripts/aitask_claim_id.sh`
- `/home/ddt/Work/aitasks/tests/test_claim_id.sh`
- `/home/ddt/Work/aitasks/tests/test_draft_finalize.sh`
- `/home/ddt/Work/aitasks/website/content/docs/development/_index.md`

## Verification

1. **Run the claim-id test suite** — must pass:
   ```bash
   bash tests/test_claim_id.sh
   ```
2. **Run the draft-finalize test suite** — must pass:
   ```bash
   bash tests/test_draft_finalize.sh
   ```
3. **Shellcheck** the modified script:
   ```bash
   shellcheck .aitask-scripts/aitask_claim_id.sh
   ```
4. **Manual smoke test** — bootstrap a throwaway project and confirm first task gets `t1`:
   ```bash
   tmp=$(mktemp -d) && cd "$tmp" && git init --quiet && git config user.email t@t.com && git config user.name T
   mkdir -p aitasks/archived .aitask-scripts/lib
   cp /home/ddt/Work/aitasks/.aitask-scripts/aitask_claim_id.sh .aitask-scripts/
   cp /home/ddt/Work/aitasks/.aitask-scripts/lib/terminal_compat.sh .aitask-scripts/lib/
   cp /home/ddt/Work/aitasks/.aitask-scripts/lib/archive_utils.sh .aitask-scripts/lib/
   cp /home/ddt/Work/aitasks/.aitask-scripts/lib/archive_scan.sh .aitask-scripts/lib/
   chmod +x .aitask-scripts/aitask_claim_id.sh
   echo init > x && git add -A && git commit -m init --quiet
   ./.aitask-scripts/aitask_claim_id.sh --peek    # expect: 1
   ./.aitask-scripts/aitask_claim_id.sh --claim   # expect: 1
   ./.aitask-scripts/aitask_claim_id.sh --claim   # expect: 2
   ```

## Follow-up (Step 9)

- Ask user to approve merging changes (no separate branch since `create_worktree: false`).
- Verify build via `project_config.yaml` (if configured).
- Run `./.aitask-scripts/aitask_archive.sh 631` to archive.
- Push via `./ait git push`.

## Final Implementation Notes

- **Actual work done:** All four changes implemented exactly as planned. Removed `ID_BUFFER=10` constant and changed three `max_id + ID_BUFFER` sites to `max_id + 1` (init_counter_branch, init_local_branch, peek_counter) in `.aitask-scripts/aitask_claim_id.sh`. Updated info/debug messages accordingly. Updated 14 test assertions across `tests/test_claim_id.sh` (Tests 1, 3, 4, 5, 7, 8, 9, 12, 13, 14) and 3 assertions in `tests/test_draft_finalize.sh` (Tests 5, 6, 7). Updated the doc line in `website/content/docs/development/_index.md`.
- **Deviations from plan:** None. Plan exactly matched the implementation.
- **Issues encountered:**
  - Noticed an unrelated modified file `.aitask-scripts/lib/agent_launch_utils.py` in `git status` — pre-existing from another workflow, explicitly excluded from this commit.
  - Manual smoke test's final `rm -rf "$tmp"` deleted the current working directory causing a spurious non-zero exit; output showed correct results (peek=1, first claim=1, second=2).
- **Key decisions:** User directive "drop the buffer entirely" over the originally-suggested "special-case max_id == 0" — simpler and relies on the fact that `scan_max_task_id` already covers every task location comprehensively, making the buffer redundant.
- **Verification results:**
  - `bash tests/test_claim_id.sh` → 23/23 passed.
  - `bash tests/test_draft_finalize.sh` → 35/35 passed.
  - `shellcheck` on the script → only pre-existing SC1091 info warnings (source paths), no errors.
  - Smoke test in empty fresh repo → `--peek` returns 1, first `--claim` returns 1, second `--claim` returns 2.
