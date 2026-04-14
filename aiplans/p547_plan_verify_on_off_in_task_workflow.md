---
Task: t547_plan_verify_on_off_in_task_workflow.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Context

Recent Claude Code iterations have dramatically increased token spend during planning (better plans, higher cost). When the `fast` profile runs on a child task, the flow is: pick → plan (load code + generate) → automatic plan verification → implement. By the time implementation starts, context is often >80% and a compact mid-implementation breaks the workflow.

The existing `plan_preference`/`plan_preference_child` profile settings are binary — once a plan exists, the verify path re-runs verification every single pick, even if a fresh verification already exists. That is wasted work.

This task introduces plan verification tracking in the plan file metadata and extends execution profiles to skip verification when enough fresh verifications already exist. It also adds an "Approve and stop here" exit to the plan-approval checkpoint so the user can break between verification and implementation when their HUD shows context is getting hot.

This is a **planning-only** task at the parent level — it creates 3 child tasks and stops.

# Design decisions (confirmed with user)

1. **Context usage detection is NOT technically feasible.** Claude Code does not expose context usage to the running assistant. Instead, we merge the "stop before implementation" intent into the existing plan-approval checkpoint by adding a new option: **"Approve and stop here"**. User decides based on their HUD.
2. **Only explicit verify appends entries** to `plan_verified`. Fresh plan creation does NOT count as a verification. This means `plan_verification_required: 1` triggers one explicit verify pass on the next pick.
3. **Staleness stored as integer hours** (`plan_verification_stale_after_hours: 24`).

# Plan file metadata format

New field `plan_verified` as a YAML list of strings, one entry per explicit verification:

```yaml
---
Task: t547_plan_verify_on_off_in_task_workflow.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_6 @ 2026-04-14 15:30
  - claudecode/sonnet4_6 @ 2026-04-14 16:15
---
```

- Format per entry: `<agent_string> @ <YYYY-MM-DD HH:MM>`
- Agent string comes from the Model Self-Detection Sub-Procedure (`model-self-detection.md`), same format as commit attribution trailers (e.g., `claudecode/opus4_6`, `codex/gpt-5`)
- New plans are created with `plan_verified: []` (empty list). Existing plans that lack the field are treated as having zero verifications.

# Profile schema extension

Two new optional keys in profile YAML (canonical doc: `.claude/skills/task-workflow/profiles.md`). **Both keys apply uniformly to parent and child tasks** — no separate `_child` variants:

| Key | Type | Default | Description |
|---|---|---|---|
| `plan_verification_required` | int | `1` (when `plan_preference` is `verify`) | Number of fresh verifications needed to skip re-verification |
| `plan_verification_stale_after_hours` | int | `24` | Hours after which a `plan_verified` entry is considered stale |

The existing `plan_preference: verify` / `plan_preference_child: verify` remain the entry points — these keys only refine *how many* fresh verifications are needed and how fresh "fresh" means.

**Updated profile defaults:**
- `default.yaml`: no change (no verification keys set → defaults apply when verify path is chosen interactively)
- `fast.yaml`: add `plan_verification_required: 1`, `plan_verification_stale_after_hours: 24` (explicit for clarity — matches defaults)
- `remote.yaml`: no change (uses `use_current`, not `verify`)

# Workflow changes — `planning.md` §6.0 verify decision

To minimize logic in the skill markdown, the helper script owns the full decision. The workflow just calls one command and branches on the `DECISION:` output line.

When a plan exists AND the effective `plan_preference` (child/parent aware) is `verify`:

1. Call the helper: `./.aitask-scripts/aitask_plan_verified.sh decide <plan_file> <required> <stale_after_hours>`
2. The helper prints a structured report (one key per line):
   ```
   TOTAL:<N>
   FRESH:<M>
   STALE:<K>
   LAST:<agent @ timestamp>    (or LAST:NONE)
   REQUIRED:<R>
   STALE_AFTER_HOURS:<H>
   DISPLAY:<human-readable summary, e.g. "Plan has 2 verifications (1 fresh, 1 stale). Required: 1.">
   DECISION:<SKIP|ASK_STALE|VERIFY>
   ```
3. Print the `DISPLAY:` line to the user.
4. Branch on `DECISION:`:
   - **`SKIP`** (fresh_count ≥ required) → jump to Checkpoint (behaves like `use_current`)
   - **`ASK_STALE`** (fresh_count < required AND total > 0) → `AskUserQuestion`:
     - "Verify now" (enters verify mode; appends a fresh entry on exit)
     - "Skip verification" (proceed with existing plan as-is)
     - "Create plan from scratch" (discard and start fresh)
   - **`VERIFY`** (total == 0) → enter verification mode directly (matches current behavior for plans with no prior verification)

All counting/staleness math lives in bash. The skill only needs to parse 8 `KEY:value` lines and call one `AskUserQuestion`.

# Workflow changes — `planning.md` §6.1 verification tail

After `ExitPlanMode` on a verify path:
1. Run the **Model Self-Detection Sub-Procedure** (`model-self-detection.md`) to get the agent string
2. Append entry: `./.aitask-scripts/aitask_plan_verified.sh append <plan_file> "<agent_string>"`
3. Proceed to plan externalization (unchanged)

This is purely additive — fresh-create and use_current paths do NOT call the append helper.

# Workflow changes — §6 Checkpoint new option

Add a 4th option to the existing plan-approval `AskUserQuestion`:

- "Start implementation" (existing)
- "Revise plan" (existing)
- **"Approve and stop here"** (NEW) — approves the plan, commits it, releases the task lock, reverts task status to `Ready`, and ends the workflow. User will re-pick later in a fresh context. The already-appended `plan_verified` entry persists so the next pick will skip re-verification (when `required=1`).
- "Abort task" (existing)

**"Approve and stop here" cleanup sequence:**
1. Commit the plan file via `./ait git`
2. Run `./.aitask-scripts/aitask_lock.sh --unlock <task_num>`
3. Run `./.aitask-scripts/aitask_update.sh --batch <task_num> --status Ready --assigned-to ""`
4. `./ait git push`
5. Display: "Plan approved and committed. Task reverted to Ready — pick it up later with `/aitask-pick <N>` in a fresh context." End the workflow.

This option is always available (no profile gating) — the context-usage trigger the user originally wanted is replaced by "user can always choose to stop".

# Critical files to be modified

| File | Change |
|---|---|
| `.aitask-scripts/aitask_plan_verified.sh` | **NEW** helper script with `read`, `append`, **`decide`** subcommands (`decide` owns all counting + staleness + decision logic so the skill markdown stays trivial) |
| `.aitask-scripts/aitask_plan_externalize.sh` (`build_header()` ~line 248) | Emit `plan_verified: []` in new headers |
| `.claude/skills/task-workflow/planning.md` (§6.0, §6.1, §6 Checkpoint) | Workflow integration |
| `.claude/skills/task-workflow/profiles.md` | Document 4 new profile keys |
| `aitasks/metadata/profiles/fast.yaml` | Add `plan_verification_required_child: 1`, `plan_verification_stale_after_hours_child: 24` |
| `tests/test_plan_verified.sh` | **NEW** test for helper script |

**NOT modified** (per CLAUDE.md convention — Claude Code is source of truth; separate aitasks will be suggested for gemini/codex/opencode):
- `.gemini/skills/`, `.agents/skills/`, `.opencode/skills/`

# Existing functions and patterns to reuse

- **Agent string format**: `code-agent-commit-attribution.md` already defines the `<agent>/<model>` format (e.g., `claudecode/opus4_6`). Reuse the Model Self-Detection Sub-Procedure (`.claude/skills/task-workflow/model-self-detection.md`) — it returns exactly this format.
- **Plan header parsing**: `aitask_plan_externalize.sh` already strips/rebuilds the YAML header block. The `build_header()` function at lines 248-310 is the canonical place to emit the new field.
- **Lock release + status revert**: `aitask_lock.sh --unlock` and `aitask_update.sh --batch` are already used by the Task Abort Procedure (`task-abort.md`) — "Approve and stop here" reuses the same primitives but keeps the plan file and appended verification entry.
- **YAML list parsing in bash**: No awk/yq dependency needed — the header is a fixed-format block, so `sed`/`grep` with the line-range delimiters (`^---$`) is sufficient for the helper script. Follow the macOS-portable patterns in `aidocs/sed_macos_issues.md`.

# Child task split (this is a planning-only parent task)

The parent description explicitly states "this is a complex task that must be split in child tasks". After the plan below is approved, the parent workflow creates 3 children and stops. The children will be picked individually in fresh contexts.

**Child 1: Plan verification metadata infrastructure** (`t547_1_plan_verified_helper`)
- Create `.aitask-scripts/aitask_plan_verified.sh` with three subcommands:
  - `read <plan_file>` — prints one `<agent>|<timestamp>` line per entry (empty output if none)
  - `append <plan_file> <agent>` — appends a new entry to the YAML list with current timestamp
  - `decide <plan_file> <required> <stale_after_hours>` — prints the full structured decision report described in §6.0 (TOTAL/FRESH/STALE/LAST/REQUIRED/STALE_AFTER_HOURS/DISPLAY/DECISION)
- Update `aitask_plan_externalize.sh build_header()` to emit `plan_verified: []` in new headers
- Create `tests/test_plan_verified.sh` covering: read with no field, read with empty list, read with multiple entries, append into empty list, append into existing list, decide with 0 entries (expect VERIFY), decide with fresh-only (expect SKIP), decide with stale-only (expect ASK_STALE), decide with mix where fresh ≥ required (expect SKIP), decide with required=2 and only 1 fresh (expect ASK_STALE), malformed entry tolerance
- Depends on: nothing
- Acceptance: all helper subcommands pass tests; new plan files emitted by `build_header()` include `plan_verified: []`

**Child 2: Execution profile schema extension** (`t547_2_profile_verification_keys`)
- Add **2** new keys (uniform for parent and child — no `_child` variants) to `.claude/skills/task-workflow/profiles.md` schema table with types/defaults/descriptions: `plan_verification_required`, `plan_verification_stale_after_hours`
- Update `aitasks/metadata/profiles/fast.yaml` to set these explicitly (matches defaults, but explicit for clarity)
- Verify `default.yaml` and `remote.yaml` remain unchanged
- Sanity-check `aitask_scan_profiles.sh` still parses profiles (no code change expected since it only reads name/description)
- Depends on: nothing (can run in parallel with Child 1)
- Acceptance: `./.aitask-scripts/aitask_scan_profiles.sh` still lists all profiles; new keys documented

**Child 3: Workflow integration — verify path + checkpoint + stop-here flow** (`t547_3_workflow_verify_integration`)
- Update `.claude/skills/task-workflow/planning.md` §6.0 with the new verify decision tree
- Update §6.1 to call the append helper on the verify tail
- Update the §6 Checkpoint to add the "Approve and stop here" option and its cleanup sequence
- Depends on: Child 1 (needs helper), Child 2 (needs profile keys)
- Acceptance: planning.md reads correctly end-to-end; all profile-key references are consistent with Child 2's naming; all helper invocations match Child 1's interface

# Verification for the parent task

Since this is a planning-only parent, verification is that all 3 child task files exist under `aitasks/t547/`, all 3 child plan files exist under `aiplans/p547/`, and the parent task reverts to `Ready` status with `children_to_implement: [1, 2, 3]` after the child-task checkpoint chooses "Stop here".

# Reference to Step 9 (Post-Implementation)

For the parent task: Step 9 is not executed because the child-task checkpoint ends the workflow. Parent archival will happen automatically when the last child is archived (via `aitask_archive.sh`'s `PARENT_ARCHIVED:` output).

For each child task: Standard Step 9 applies — archive task/plan, handle any linked issue, push.
