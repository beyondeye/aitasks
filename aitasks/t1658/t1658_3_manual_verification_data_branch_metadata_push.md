---
priority: medium
effort: medium
depends: [t1658_2]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [t1658_1, t1658_2]
assigned_to: dario-e@beyond-eye.com
anchor: 1658
followup_kind: manual_verification
created_at: 2026-09-01 14:35
updated_at: 2026-09-02 18:07
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t1658_1] On this real checkout with other agents live, run `./.aitask-scripts/aitask_usage_update.sh --agent-string claudecode/opus4_6 --skill pick --silent`; it prints a single `UPDATED:claudecode/opus4_6:pick:<n>` line and exits 0.
- [ ] [t1658_1] Immediately after that run, `./ait git rev-list --count HEAD..@{u}` reports 0 and `./ait git log -1 --format=%s` names the usage-count commit — the commit reached the LOCAL branch, with no manual sync.
- [ ] [t1658_1] Repeat the run while the shared `.aitask-data` worktree genuinely has another session's unstaged `aitasks/`/`aiplans/` edits; convergence still happens and those foreign edits are still present and unmodified afterwards (`./ait git status --porcelain` shows the same files still dirty).
- [ ] [t1658_1] Confirm no stash was created by the run: `./ait git stash list` is unchanged from before it, and no `aitasks/`/`aiplans/` file gained conflict markers.
- [ ] [t1658_1] Confirm the run created no sweep commit: `./ait git log -3 --stat` shows only the metadata commit, with no other session's task/plan files swept in.
- [ ] [t1658_1] Force the partial outcome on the real repo: leave `aitasks/metadata/models_claudecode.json` locally modified, run the update, and confirm stdout is `UPDATED_REMOTE_ONLY:...`, the exit status is 3, the explanation is on stderr, and the local file's edit is untouched.
- [ ] [t1658_1] From that partial state, run `./ait sync` and confirm the branch converges (both `./ait git rev-list --count @{u}..HEAD` and `HEAD..@{u}` reach 0) with no work lost.
- [ ] [t1658_1] Run a full `/aitask-pick` to completion and confirm the satisfaction-feedback step reports the metadata outcome correctly and does not abort the workflow on a partial result.
- [ ] [t1658_1] Run the same update WITHOUT `--silent` and confirm the reported count is a bare number, with git's commit summary appearing as terminal output rather than spliced into the value.
- [ ] [t1658_2] From `website/`, run `../.aitask-scripts/aitask_usage_update.sh --agent-string claudecode/opus4_6 --skill pick --silent`; it prints `UPDATED:` and exits 0 (before the fix it died with "Model config not found").
- [ ] [t1658_2] From a real crew worktree under `.aitask-crews/`, confirm a data-branch operation resolves the main checkout's `.aitask-data` and does NOT silently act on the crew branch (before the fix it pulled `crew-brainstorm-1017`).
- [ ] [t1658_2] From `website/` and from `tests/`, confirm `./ait git status -sb` (run via the repo-root `ait`) and a data-branch read agree with what the repo root reports — no legacy-mode fallback anywhere.
- [ ] [t1658_2] Launch `ait board`, `ait monitor` and `ait syncer` from the repo root and confirm they start and show task data normally — the shared `_ait_detect_data_worktree` change reaches every TUI.
- [ ] [t1658_2] Confirm `ait syncer` no longer reports this machine's own metadata commits as "remote commits not yet pulled" after a completed pick — the original reported symptom is gone.
