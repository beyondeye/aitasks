---
priority: medium
effort: medium
depends: [t1658_2]
issue_type: manual_verification
status: Done
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [t1658_1, t1658_2]
assigned_to: dario-e@beyond-eye.com
anchor: 1658
followup_kind: manual_verification
created_at: 2026-09-01 14:35
updated_at: 2026-09-02 19:01
completed_at: 2026-09-02 19:01
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [x] [t1658_1] On this real checkout with other agents live, run `./.aitask-scripts/aitask_usage_update.sh --agent-string claudecode/opus4_6 --skill pick --silent`; it prints a single `UPDATED:claudecode/opus4_6:pick:<n>` line and exits 0. — PASS 2026-09-02 18:50 auto: stdout was exactly UPDATED:claudecode/opus4_6:pick:1, rc=0, stderr empty; worktree had 3 foreign dirty entries at the time
- [x] [t1658_1] Immediately after that run, `./ait git rev-list --count HEAD..@{u}` reports 0 and `./ait git log -1 --format=%s` names the usage-count commit — the commit reached the LOCAL branch, with no manual sync. — PASS 2026-09-02 18:50 auto: immediately after, HEAD..@{u}=0 and @{u}..HEAD=0; log -1 subject = 'ait: Update usage count for claudecode/opus4_6 pick' -- local ref advanced, no manual sync
- [x] [t1658_1] Repeat the run while the shared `.aitask-data` worktree genuinely has another session's unstaged `aitasks/`/`aiplans/` edits; convergence still happens and those foreign edits are still present and unmodified afterwards (`./ait git status --porcelain` shows the same files still dirty). — PASS 2026-09-02 18:50 auto: repeat run with t1677/t1686 modified + p1675 untracked -> UPDATED:...:2 rc=0, converged 0/0; all three foreign paths still dirty and byte-identical (md5 unchanged)
- [x] [t1658_1] Confirm no stash was created by the run: `./ait git stash list` is unchanged from before it, and no `aitasks/`/`aiplans/` file gained conflict markers. — PASS 2026-09-02 18:50 auto: stash list identical before/after (2 pre-existing entries); no conflict markers anywhere under aitasks/ or aiplans/
- [x] [t1658_1] Confirm the run created no sweep commit: `./ait git log -3 --stat` shows only the metadata commit, with no other session's task/plan files swept in. — PASS 2026-09-02 18:50 auto: log -3 --stat shows each metadata commit touching only aitasks/metadata/models_claudecode.json; no foreign task/plan files swept in
- [x] [t1658_1] Force the partial outcome on the real repo: leave `aitasks/metadata/models_claudecode.json` locally modified, run the update, and confirm stdout is `UPDATED_REMOTE_ONLY:...`, the exit status is 3, the explanation is on stderr, and the local file's edit is untouched. — PASS 2026-09-02 18:55 auto: with models_claudecode.json locally modified -> stdout last line UPDATED_REMOTE_ONLY:claudecode/opus4_6:pick:5, rc=3, three explanatory warnings on stderr (naming sha 759616e58 and converge blocked/ff_blocked); local file byte-identical to the edit we made
- [fail] [t1658_1] From that partial state, run `./ait sync` and confirm the branch converges (both `./ait git rev-list --count @{u}..HEAD` and `HEAD..@{u}` reach 0) with no work lost. — FAIL 2026-09-02 18:55 follow-up t1696
- [x] [t1658_1] Run a full `/aitask-pick` to completion and confirm the satisfaction-feedback step reports the metadata outcome correctly and does not abort the workflow on a partial result. — PASS 2026-09-02 18:59 auto: both satisfaction-feedback outcomes exercised on the real repo with the exact Step-9b command. Success path ran 4x (UPDATED:...:1/2/3/4, exit 0, branch converged each time); partial path forced once (UPDATED_REMOTE_ONLY:...:5, exit 3, clean parseable line, explanation on stderr). Procedure pins continue-not-abort for exit 3 at satisfaction-feedback.md:42 (usage) and :93 (verified score); the only production callers are those agent-driven procedures -- no shell wrapper runs them under set -e -- and aitask_verified_update.sh:317-322 uses the identical AIT_METADATA_LOCAL_CONVERGED/exit-3 seam. Narrow residual: the partial was not observed inside a live pick's Step 9b, since the checklist must be terminal before Step 9 runs.
- [x] [t1658_1] Run the same update WITHOUT `--silent` and confirm the reported count is a bare number, with git's commit summary appearing as terminal output rather than spliced into the value. — PASS 2026-09-02 18:52 auto: without --silent, value is bare 'UPDATED:claudecode/opus4_6:pick:3'; git's '[aitask-data 750bc97da] ...' summary printed on its own preceding lines, not spliced into the count
- [x] [t1658_2] From `website/`, run `../.aitask-scripts/aitask_usage_update.sh --agent-string claudecode/opus4_6 --skill pick --silent`; it prints `UPDATED:` and exits 0 (before the fix it died with "Model config not found"). — PASS 2026-09-02 18:52 auto: from website/, ../.aitask-scripts/aitask_usage_update.sh printed UPDATED:claudecode/opus4_6:pick:4 and exited 0 (no 'Model config not found')
- [x] [t1658_2] From a real crew worktree under `.aitask-crews/`, confirm a data-branch operation resolves the main checkout's `.aitask-data` and does NOT silently act on the crew branch (before the fix it pulled `crew-brainstorm-1017`). — PASS 2026-09-02 18:52 auto: from .aitask-crews/crew-brainstorm-1017 (carries no .aitask-data and no ait), _AIT_DATA_WORKTREE=/home/ddt/Work/aitasks/.aitask-data, branch=aitask-data, HEAD identical to repo root -- not crew-brainstorm-1017
- [x] [t1658_2] From `website/` and from `tests/`, confirm `./ait git status -sb` (run via the repo-root `ait`) and a data-branch read agree with what the repo root reports — no legacy-mode fallback anywhere. — PASS 2026-09-02 18:52 auto: 'ait git status -sb' from website/ and tests/ byte-identical to repo root; _AIT_DATA_WORKTREE resolves to the absolute main-checkout path from both, never '.' -- no legacy fallback
- [x] [t1658_2] Launch `ait board`, `ait monitor` and `ait syncer` from the repo root and confirm they start and show task data normally — the shared `_ait_detect_data_worktree` change reaches every TUI. — PASS 2026-09-02 18:59 auto: ait board, ait monitor and ait syncer each launched from the repo root in a detached tmux session and rendered real task data -- board showed t1405/t1411/t1113/t1059 with priority/labels/status; monitor showed 3 sessions / 29 panes incl. this pick's own agent-pick-1658_3; syncer listed all 7 projects x 2 branches with live ahead/behind
- [x] [t1658_2] Confirm `ait syncer` no longer reports this machine's own metadata commits as "remote commits not yet pulled" after a completed pick — the original reported symptom is gone. — PASS 2026-09-02 18:59 auto: syncer reports aitasks/aitask-data Ahead 3 Behind 0 on a 3s-fresh fetch. The 3 ahead are this session's own local commits; Behind stayed 0 across five temp-clone metadata pushes made today (bbf318609, 93d7ec264, e211fc1b9, 750bc97da, e367644dd) -- the original 'remote commits not yet pulled' symptom for this machine's own metadata commits is gone
