---
Task: t708_warn_user_about_remote_changes_after_planning.md
Worktree: (none — profile fast: working on current branch)
Branch: main (current)
Base branch: main
---

# Plan: Warn user about remote changes after planning (t708)

## Context

`aitask-pick` Step 0c and `aitask_pick_own.sh` keep the **task-data branch** in sync (`task_sync()` in `lib/task_utils.sh:177` pulls `_AIT_DATA_WORKTREE` only). In branch-mode setups, the **code branch (`main`) is never fetched** by the workflow:

- Step 5 worktree creation uses local `<base-branch>` with no `git fetch` first.
- `planning.md` does no fetch/pull at any step.
- Step 9 merges into local `main` without pulling `origin/main`.

Net effect: locks prevent double-claiming the task, but two PCs can still build feature branches from each PC's stale local `main`. If `origin/main` advanced — especially on files the plan intends to change — the user implements against an out-of-date base, then either re-discovers the conflict at final-merge time or silently produces a redundant/incompatible change.

**Goal:** After plan approval and before implementation begins, warn the user if `origin/<base-branch>` is ahead of local `<base-branch>` — *strongly* if any remote-only commit touches a file referenced in the plan; *softly* otherwise. Offer the user a clean way to stop, pull, and re-verify before continuing.

## Approach

Encapsulate the drift detection in a single new helper script and add a thin wrapper sub-step in `planning.md`. Add an opt-out execution-profile key.

### Step 1 — New helper: `.aitask-scripts/aitask_remote_drift_check.sh`

**Signature:**
```
aitask_remote_drift_check.sh [--debug] [--timeout <sec>] <base-branch> <plan-file>
```

**Behavior (all best-effort; never fails the workflow):**

1. **Detect data-worktree mode** via `_ait_detect_data_worktree` (already in `lib/task_utils.sh`). If running in **legacy mode** (data on the same branch as code), emit `LEGACY_MODE_SKIP` and exit 0 — `task_sync()` already kept code current.
2. **Check remote exists** (mirror `has_remote` in `aitask_lock.sh:42`). If no `origin`, emit `NO_REMOTE` and exit 0.
3. **Fetch with timeout** (mirror `_git_with_timeout` from `aitask_sync.sh:84-115` — same `timeout` command + macOS background-process fallback, exit code 124 on timeout):
   ```bash
   timeout 10 git fetch --quiet origin "<base-branch>" || fetch_exit=$?
   ```
   If fetch fails: emit `FETCH_FAILED` and exit 0.
4. **Compute remote-ahead commits:**
   ```bash
   ahead=$(git rev-list --count "<base-branch>..origin/<base-branch>")
   ```
   If `ahead == 0`: emit `UP_TO_DATE` and exit 0.
5. **List remote-changed files:**
   ```bash
   git diff --name-only "<base-branch>..origin/<base-branch>"
   ```
6. **Extract plan-referenced paths.** No existing path extractor in the codebase (verified via Explore agent), so implement here. Use `grep -oE` with a union of patterns covering the project's directory roots and file extensions:
   ```
   (\.?/)?(\.?(aitask-scripts|aitasks|aiplans|claude/skills|opencode/skills|gemini/skills|agents/skills|website|seed|tests))/[A-Za-z0-9_./-]+\.(sh|py|md|yaml|yml|json|toml)
   ```
   Then `sort -u` and strip any leading `./`. Backticked paths (`` `aitasks/foo.md` ``) and markdown links (`[text](path)`) match naturally because the regex consumes only path characters.
7. **Intersect** remote-changed files with plan-referenced files (`comm -12` or `grep -Fx -f`).
8. **Emit structured output** (one item per line, batch protocol mirroring `aitask_sync.sh` / `aitask_query_files.sh`):
   ```
   AHEAD:<n>
   OVERLAP:<file>            # zero or more lines, one per overlapping path
   NO_OVERLAP                # mutually exclusive with OVERLAP: lines
   ```
9. **Exit code:** always 0 unless invalid args. Workflow-relevant outcomes are conveyed via output keys.

**Boilerplate (mirror existing scripts):** `#!/usr/bin/env bash`, `set -euo pipefail`, `source lib/terminal_compat.sh`, `source lib/task_utils.sh`, `--help` block, `--debug` flag, `die "Usage: ..."` on missing args.

### Step 2 — New procedure file: `remote-drift-check.md`

The full procedure body lives in **a new file**, `.claude/skills/task-workflow/remote-drift-check.md`, mirroring the file-per-procedure pattern already used for `task-abort.md`, `lock-release.md`, `manual-verification-followup.md`, `upstream-followup.md`, etc. Call-sites in `planning.md` and `SKILL.md` only reference it — they do not inline its body.

**File contents (`.claude/skills/task-workflow/remote-drift-check.md`):**

```markdown
# Remote Drift Check Procedure

Detects whether `origin/<base-branch>` has commits the local `<base-branch>` is missing, with stronger emphasis when the missing commits touch files referenced in the plan. Invoked from `planning.md` Checkpoint after the user (or profile) chooses to start implementation, before control returns to `SKILL.md` Step 7.

## Input

| Variable | Type | Description |
|----------|------|-------------|
| `base_branch` | string | Base branch from the plan metadata header (e.g., `main`) |
| `plan_file` | string | Path to the externalized plan file (e.g., `aiplans/p708_*.md`) |
| `active_profile` | object/null | Loaded execution profile (or null) |

## Procedure

1. **Profile check:** If the active profile has `remote_drift_check: skip`, return immediately. No display.

2. **Run the helper:**
   \`\`\`bash
   ./.aitask-scripts/aitask_remote_drift_check.sh "<base_branch>" "<plan_file>"
   \`\`\`

3. **Parse stdout (line-oriented `KEY:value` protocol):**

   - `LEGACY_MODE_SKIP` / `NO_REMOTE` / `FETCH_FAILED` / `UP_TO_DATE` → return; no display.
   - `AHEAD:<n>` followed by `NO_OVERLAP`:
     - If profile is `strong-only`: return; no display.
     - Else: display "Remote `<base_branch>` is ahead by `<n>` commit(s); none touch files in your plan." Then proceed to AskUserQuestion below.
   - `AHEAD:<n>` followed by one or more `OVERLAP:<file>` lines (always treated as strong, regardless of profile `warn` or `strong-only`):
     - Display: "Remote `<base_branch>` is ahead by `<n>` commit(s) and changes `<m>` file(s) your plan also targets:" then list each overlapping file on its own line.
     - Proceed to AskUserQuestion below.

4. **AskUserQuestion:**
   - Question: "How would you like to proceed?"
   - Header: "Remote drift"
   - Options:
     - "Stop and re-verify plan" (description: "Release the lock, revert task to Ready, and end the workflow — pull `<base_branch>` then re-pick the task")
     - "Continue anyway" (description: "Proceed to implementation; you may need to handle conflicts at merge time")
     - "Abort task" (description: "Discard the task and revert status")

5. **Branches:**
   - "Stop and re-verify plan": Run the same release-and-revert sequence as the planning-checkpoint "Approve and stop here" branch (planning.md:312-330): commit any pending plan changes via `./ait git`, execute the **Lock Release Procedure** (`lock-release.md`), revert task status to `Ready` and clear `assigned_to` via `aitask_update.sh`, commit and `./ait git push`. Display "Pick it up later with `/aitask-pick <task_id>`." End the workflow.
   - "Continue anyway": Return so the caller can proceed to Step 7.
   - "Abort task": Execute the **Task Abort Procedure** (`task-abort.md`).

## Notes

- Always best-effort. Network failures, missing remotes, and legacy-mode setups all return silently without prompting.
- Idempotent: safe to call multiple times if the workflow re-enters the checkpoint via "Revise plan".
- Worktree mode: the helper runs from the repo root (`pwd` at workflow entry); the worktree directory is irrelevant for the drift comparison because we compare `<base-branch>..origin/<base-branch>`, not the worktree's `aitask/<task_name>` branch.
```

### Step 3 — Wire references into the workflow

**A) `.claude/skills/task-workflow/planning.md` Checkpoint section — two insertion points:**

1. **Profile-driven `start_implementation` path** (planning.md:293-295). After the "Display: Profile '\<name\>': proceeding to implementation" line and **before** "Skip the AskUserQuestion below and proceed to Step 7", insert:
   ```
   - Execute the **Remote Drift Check Procedure** (see `remote-drift-check.md`) with `base_branch`, `plan_file`, and `active_profile` from context. If the procedure ends the workflow ("Stop and re-verify plan" or "Abort task"), do NOT proceed to Step 7.
   ```

2. **Interactive checkpoint "Start implementation" branch** (planning.md:308). Replace `If "Start implementation": Proceed to Step 7.` with:
   ```
   If "Start implementation": Execute the **Remote Drift Check Procedure** (see `remote-drift-check.md`) with `base_branch`, `plan_file`, and `active_profile` from context. If the procedure returns ("Continue anyway"), proceed to Step 7. If it ends the workflow, stop.
   ```

**B) `.claude/skills/task-workflow/SKILL.md` §Procedures bullet list (line ~551 onwards):**

Add one line:
```
- **Remote Drift Check Procedure** (`remote-drift-check.md`) — Warn before implementation if `origin/<base-branch>` is ahead, with strong emphasis on files the plan touches. Referenced from planning.md Checkpoint.
```

### Step 4 — Profile key

Edit **`.claude/skills/task-workflow/profiles.md`**:

Add a new row to the schema table (after `post_plan_action_for_child`):
```
| `remote_drift_check` | string | no | `"warn"` (default — soft if no overlap, strong if overlap), `"skip"` (do nothing), `"strong-only"` (only prompt when overlap exists) | Step 6 checkpoint (post-plan) |
```

No change required to `aitasks/metadata/profiles/default.yaml`, `fast.yaml`, or `remote.yaml` — omitting the key keeps the default `"warn"` behavior. (Optional: explicitly add `remote_drift_check: skip` to `remote.yaml` since Claude Code Web runs unattended and prompts are no-ops there.)

### Step 5 — Helper-script whitelisting (5 touchpoints, per CLAUDE.md)

| File | Entry to add |
|------|--------------|
| `.claude/settings.local.json` | `"Bash(./.aitask-scripts/aitask_remote_drift_check.sh:*)"` and `"Bash(/home/ddt/Work/aitasks/.aitask-scripts/aitask_remote_drift_check.sh:*)"` (mirror existing `aitask_lock.sh` / `aitask_pick_own.sh` pairs) |
| `.gemini/policies/aitasks-whitelist.toml` | Two `[[rule]]` blocks: one with `commandPrefix = "./.aitask-scripts/aitask_remote_drift_check.sh"`, one with `commandRegex = ".*/.aitask-scripts/aitask_remote_drift_check\\.sh.*"`, both `decision = "allow"`, `priority = 100` (mirror existing `aitask_lock.sh` rules) |
| `seed/claude_settings.local.json` | `"Bash(./.aitask-scripts/aitask_remote_drift_check.sh:*)"` |
| `seed/geminicli_policies/aitasks-whitelist.toml` | mirror of the runtime `.gemini/policies` rules |
| `seed/opencode_config.seed.json` | `"./.aitask-scripts/aitask_remote_drift_check.sh *": "allow"` |

Codex needs no entry (prompt-only permission model — see CLAUDE.md "Adding a New Helper Script").

### Step 6 — Test

New file `tests/test_remote_drift_check.sh` following the conventions in `tests/test_repo_fetch.sh`:

- Set up a scratch repo with two clones (`origin` repo + local clone) using `mktemp -d`.
- Plant a known plan file containing references to specific paths (e.g., `aitask-scripts/foo.sh`, `aiplans/bar.md`).
- Test cases:
  1. `UP_TO_DATE` when local matches `origin`.
  2. `AHEAD:N` + `NO_OVERLAP` when remote-only commit touches an unrelated file.
  3. `AHEAD:N` + `OVERLAP:<file>` when remote-only commit touches a path the plan references.
  4. `NO_REMOTE` when origin is unset.
  5. `LEGACY_MODE_SKIP` when `_ait_detect_data_worktree` resolves to `.`.
  6. `FETCH_FAILED` when origin URL is unreachable (e.g., `file:///nonexistent`).
- Use `assert_eq` / `assert_contains` helpers; gate the `FETCH_FAILED` test on a `SKIP_NETWORK`-style env (mirror `tests/test_repo_fetch.sh`).
- Run via `bash tests/test_remote_drift_check.sh`.

### Step 7 — Documentation note (out of scope; defer)

The website docs in `website/content/docs/workflows/` may need a paragraph mentioning the new check. Defer to a follow-up task — keep the user-facing docs change separate so this PR stays focused on workflow logic.

## Files touched

- **NEW** `.aitask-scripts/aitask_remote_drift_check.sh` — helper, all logic lives here
- **NEW** `.claude/skills/task-workflow/remote-drift-check.md` — procedure file (the source of truth for the procedure body — never inlined elsewhere)
- **NEW** `tests/test_remote_drift_check.sh`
- `.claude/skills/task-workflow/planning.md` — two thin "Execute the Remote Drift Check Procedure (see `remote-drift-check.md`)" references in the Checkpoint section. No procedure body inlined.
- `.claude/skills/task-workflow/SKILL.md` — one new bullet in the §Procedures list pointing to `remote-drift-check.md`.
- `.claude/skills/task-workflow/profiles.md` — one new row in the schema table for `remote_drift_check`.
- `.claude/settings.local.json` (whitelist)
- `.gemini/policies/aitasks-whitelist.toml` (whitelist)
- `seed/claude_settings.local.json` (whitelist)
- `seed/geminicli_policies/aitasks-whitelist.toml` (whitelist)
- `seed/opencode_config.seed.json` (whitelist)

## Out of scope (follow-up tasks to suggest at Step 8)

1. **Port to other code agents.** `.opencode/skills/` and `.agents/skills/` (Codex+Gemini shared) have *inlined* workflows for aitask-pick / aitask-explore / aitask-review (no shared `task-workflow` tree). Each will need a separate aitask to add an equivalent drift-check sub-step in its own SKILL.md. Per CLAUDE.md "WORKING ON SKILLS / CUSTOM COMMANDS" convention.
2. **Pre-merge drift check at Step 9.** Step 9 already does a `git merge` that will surface conflicts, so the value-add is smaller — defer.
3. **Structured `## Files Affected` plan section.** Plans currently embed paths in prose; a structured section would make extraction lossless. Larger doc-template change — defer.
4. **Auto-rebase option.** "Stop and re-verify plan" currently asks the user to pull manually. A future enhancement could offer to run `git pull --rebase` (and `git rebase origin/<base>` inside the worktree if applicable) automatically.

## Verification

Run after implementation:

1. **Unit tests:** `bash tests/test_remote_drift_check.sh` — must pass all cases.
2. **Lint:** `shellcheck .aitask-scripts/aitask_remote_drift_check.sh` — clean.
3. **Manual test 1 (no drift):** with `main` and `origin/main` aligned, run `/aitask-pick <some_task>`, approve a plan; expect no drift output between checkpoint and implementation.
4. **Manual test 2 (soft drift):** push an unrelated commit to `origin/main` from a second clone; pick a task whose plan does *not* reference that file; expect `AHEAD:1` + `NO_OVERLAP` and a soft warning.
5. **Manual test 3 (strong drift):** push a commit to `origin/main` touching `.aitask-scripts/aitask_archive.sh`; pick a task whose plan explicitly references `aitask_archive.sh`; expect `AHEAD:1` + `OVERLAP:.aitask-scripts/aitask_archive.sh` and a strong warning.
6. **Manual test 4 (no network):** `unshare -n` (or simply `git remote set-url origin file:///nonexistent`); expect silent `FETCH_FAILED` and proceed.
7. **Profile opt-out:** with `remote_drift_check: skip` set in a custom profile, drift check is silent regardless of state.

## Step 9 (post-implementation)

Standard archival via `aitask_archive.sh 708`, push via `./ait git push`. No special handling required.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned. New helper `.aitask-scripts/aitask_remote_drift_check.sh` (~180 lines) emits the structured `LEGACY_MODE_SKIP` / `NO_REMOTE` / `FETCH_FAILED` / `UP_TO_DATE` / `AHEAD:<n>` + (`OVERLAP:<f>`... | `NO_OVERLAP`) protocol. Procedure body lives in `.claude/skills/task-workflow/remote-drift-check.md`; `planning.md` and `SKILL.md` only reference it. `profiles.md` got the `remote_drift_check` row. All 5 whitelist touchpoints covered (`aitask_audit_wrappers.sh audit-helper-whitelist` reports zero MISSING).
- **Deviations from plan:** None of substance. The plan called for a `commandPrefix` whitelist entry plus a broad `commandRegex` for the `.gemini/` policy files — used the same two-rule pattern (prefix + regex) the existing `aitask_lock.sh` uses, in both runtime and seed Gemini whitelists.
- **Issues encountered:** Initial `shellcheck` run on the test file flagged SC2154 ("d is referenced but not assigned") for the loop variable inside the EXIT trap string — false positive, suppressed with a directive comment. SC1091 (info-level "not following sourced files") on the helper is unavoidable without `-x` and matches the `aitask_lock.sh` baseline.
- **Key decisions:**
  - Helper uses pure structured output (no `--batch` toggle), matching the simpler `aitask_query_files.sh` pattern rather than the dual-mode `aitask_sync.sh`. The procedure is only ever called by the workflow, so an interactive output mode would never run.
  - Path extraction in plans is a two-pass grep: first pull anything resembling `[A-Za-z0-9_./-]+\.(sh|py|md|yaml|yml|json|toml)`, then keep only paths rooted in known project directories. Since plans don't have a structured "Files Affected" section, this regex-based approach is best-effort but reliable for the project's directory conventions.
  - "Stop and re-verify plan" reuses the existing planning-checkpoint "Approve and stop here" sequence verbatim — same lock-release + status-revert + push flow — to avoid duplicating release logic.
  - Did NOT add `remote_drift_check: skip` to `remote.yaml` despite the plan suggesting it as optional. Defer that to `aitask-pickrem` / `aitask-pickweb` maintainers since those skills have their own profile semantics; the default `warn` is functionally identical to no-op when there's no human to prompt.
- **Upstream defects identified:** None.

## Verification (post-implementation)

- `bash tests/test_remote_drift_check.sh` → 11/11 passed (`UP_TO_DATE`, `LEGACY_MODE_SKIP`, `NO_REMOTE`, `FETCH_FAILED`, `AHEAD+NO_OVERLAP`, `AHEAD+OVERLAP`, missing-arg).
- `shellcheck .aitask-scripts/aitask_remote_drift_check.sh tests/test_remote_drift_check.sh` → only SC1091 info-level on the helper (same baseline as `aitask_lock.sh`); test file is clean.
- `./.aitask-scripts/aitask_audit_wrappers.sh audit-helper-whitelist aitask_remote_drift_check.sh` → exit 0 with no MISSING lines.
- Smoke test: `./.aitask-scripts/aitask_remote_drift_check.sh main <plan-file>` against the live repo → `UP_TO_DATE` (correct for the current repo state).
