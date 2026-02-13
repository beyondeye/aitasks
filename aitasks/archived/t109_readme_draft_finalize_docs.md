---
priority: medium
effort: medium
depends: []
issue_type: documentation
status: Done
labels: [aitasks, documentation]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-13 02:30
updated_at: 2026-02-13 11:52
completed_at: 2026-02-13 11:52
---

Update README.md to document the new atomic task ID allocation system and draft/finalize workflow introduced in t108. The README should cover the following behavioral changes:

## Areas to Document

### 1. `ait create` (Interactive Mode)
- Tasks are now created as **drafts** in `aitasks/new/` with timestamp-based filenames (e.g., `draft_20260213_1423_fix_login.md`)
- Drafts are local-only (gitignored) and do not have a real task number yet
- On startup, existing drafts are listed and can be edited, finalized, or deleted
- **Finalization** assigns a globally unique task ID from the atomic counter on the `aitask-ids` git branch, moves the file to `aitasks/`, and commits to git
- Users can choose to "Save as draft" and finalize later

### 2. `ait create` (Batch Mode / `aitask_create.sh`)
- Default behavior (without `--commit`): creates a draft in `aitasks/new/` (no network needed)
- `--commit` flag: auto-finalizes immediately (claims real ID from atomic counter, commits to git)
- New `--finalize <file>` flag: finalize a specific draft
- New `--finalize-all` flag: finalize all pending drafts
- Backward compatibility: `--commit` preserves existing behavior for scripts

### 3. `ait setup` (`aitask_setup.sh`)
- New step: initializes the `aitask-ids` counter branch on the remote (shared atomic counter)
- New step: creates `aitasks/new/` directory and adds it to `.gitignore`
- Both steps are idempotent (safe to re-run)

### 4. Atomic Task ID Counter (`aitask_claim_id.sh`)
- Internal script (not exposed via `ait` dispatcher) that manages a shared counter on a separate `aitask-ids` git branch
- Uses git plumbing commands for lock-free atomic compare-and-swap
- Prevents duplicate task IDs when multiple PCs create tasks against the same repo
- Fallback to local file scan when counter branch is unavailable

### 5. `aitask-create` Claude Code Skill
- Now creates drafts in `aitasks/new/` instead of directly in `aitasks/`
- Finalizes via `./aiscripts/aitask_create.sh --batch --finalize <draft>`
- No network needed during draft creation; network required for finalization

### 6. `aitask-pick` Claude Code Skill
- New Step 0c: `git pull --ff-only` (best-effort) before task selection to sync with remote

### 7. Duplicate ID Detection
- `aitask_ls.sh` now warns on stderr if duplicate task IDs are detected
- `aitask_update.sh` suggests running `ait setup` when multiple files found for same ID

## Reference Files
- aiscripts/aitask_claim_id.sh
- aiscripts/aitask_create.sh
- aiscripts/aitask_setup.sh
- .claude/skills/aitask-create/SKILL.md
- .claude/skills/aitask-pick/SKILL.md
- aiplans/archived/p108_force_git_pull_at_start_of_task_create.md
