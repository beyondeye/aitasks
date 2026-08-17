---
priority: medium
effort: medium
depends: [1536]
issue_type: manual_verification
status: Done
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [1536]
assigned_to: dario-e@beyond-eye.com
anchor: 1536
followup_kind: manual_verification
created_at: 2026-08-17 17:39
updated_at: 2026-08-17 23:09
completed_at: 2026-08-17 23:09
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1536

## Verification Checklist

- [defer] Run a real /aitask-pick under a create_worktree:true profile (no shipped profile sets it, so the scripted acceptance run in t1536 never exercised the live pick path). — DEFER 2026-08-17 18:58 auto: not automatable -- requires a real interactive /aitask-pick session (worktree mode is reachable under the default profile by answering Yes; no shipped profile sets create_worktree: true, only fast.yaml sets it false). Driving one would mean implementing a real task end to end and cutting real branches. Human run needed.
- [x] Step 5 creates nothing: after the base-branch decision, confirm no aiwork/ directory and no aitask/<task_name> branch exist yet. — PASS 2026-08-17 18:58 auto: source-structural -- Step 5 body contains zero 'git worktree add'/'mkdir -p' in all 9 rendered variants (claude/codex/opencode x default/fast/remote); the sole 'git worktree add -b aitask/<task_name>' sits in Step 7's Deferred worktree fork block. Step 6's externalize helper was run live and created no aiwork/ dir (see item 5). Live pick observation still owed via item 1.
- [x] Step 5 widget wording: the interactive base-branch question states, inside the widget itself, that the branch and worktree are cut after plan approval and the drift check — not in surrounding prose. — PASS 2026-08-17 18:58 auto: the deferral sentence is INSIDE the AskUserQuestion text ('The branch and worktree are not created now -- they are cut at the start of implementation, after you approve the plan and the remote drift check passes.') in all 9 rendered variants + the .j2 authoring template, not in surrounding prose.
- [x] Profile-driven display line: with base_branch set in the profile, the "using base branch <b>" line carries the same deferral sentence. — PASS 2026-08-17 18:58 auto: profile-driven line reads 'Profile <name>: using base branch <b> -- the branch and worktree are created after plan approval and the remote drift check, not now.' in all 9 rendered variants and in BOTH authoring branches (Jinja-baked profile.base_branch + runtime profile check).
- [x] Plan header at Step 6: the externalized plan records Worktree:, Base branch: and Output branch: while aiwork/<task_name> still does not exist on disk. — PASS 2026-08-17 18:58 auto: live run of aitask_plan_externalize.sh in a scratch git repo with --worktree aiwork/t77_add_widget --base-branch dev-base --output-branch dev-base emitted a header carrying Worktree:/Base branch:/Output branch: while 'ls -d aiwork' reported No such file or directory. tests/test_plan_externalize.sh: 255/255 pass.
- [defer] Fork timing: the worktree appears only after the plan is approved AND the Remote Drift Check returns "Continue anyway" — not before. — DEFER 2026-08-17 18:58 auto: blocked on item 1 -- fork TIMING relative to plan approval + the drift check's 'Continue anyway' can only be observed inside a live pick. Source ordering was verified (item 13); the live observation is the missing evidence.
- [defer] Drift stop leaves nothing: choose "Stop and re-verify plan" and confirm no worktree or aitask/ branch was created, then re-pick and confirm it cuts cleanly from the pulled base. — DEFER 2026-08-17 18:58 auto: blocked on item 1 -- the 'Stop and re-verify plan' exit and the subsequent re-pick are multi-turn interactive stop paths.
- [defer] Approve-and-stop leaves nothing: choose "Approve and stop here" and confirm the same, then re-pick without a "branch already exists" failure (the t1392 collision). — DEFER 2026-08-17 18:58 auto: blocked on item 1 -- 'Approve and stop here' + clean re-pick (the t1392 branch-already-exists collision) needs a live plan-approval checkpoint.
- [defer] Decomposed parent: let planning create child tasks and stop — confirm the parent stranded no worktree. — DEFER 2026-08-17 18:58 auto: blocked on item 1 -- requires live planning that decomposes a parent into children and then stops.
- [defer] Risk-mitigation "before" stop: confirm the worktree DOES exist on that path and that a re-pick reuses it rather than failing. — DEFER 2026-08-17 18:59 auto: blocked on item 1 -- needs a live risk-gated plan with a 'before' mitigation line so the Step 7 session-stop branch fires; the reuse-on-re-pick half is covered mechanically by item 11.
- [x] Reuse after a move: git worktree move the task worktree elsewhere, resume, and confirm the agent works in the moved directory (not aiwork/<task_name>). — PASS 2026-08-17 18:58 auto: behavioral -- real git worktree created, then 'git worktree move'd to a path outside aiwork/. The Step-7 reuse awk (record-aware porcelain scan) returned the MOVED path, and aiwork/<task_name> was gone. Skill instructs working in $reuse_dir, not the guessed path.
- [defer] Re-entry under a DIFFERENT profile: resume a worktree-mode task under fast and confirm the fork still runs (header-driven), then resume a current-branch task under a worktree profile and confirm no worktree appears. — DEFER 2026-08-17 18:59 auto: partially verified, live half owed. Verified: Re-entry Routing resolves worktree intent from the plan header's Worktree: field with an explicit prohibition on profile.create_worktree, and the block is byte-identical across default/fast/remote and claude/codex/opencode; the header-parse snippets were executed (present / empty / unsafe cases all behave). Not verified: an actual cross-profile resume.
- [x] Re-entry ordering: on the IMPLEMENT route confirm the drift check runs BEFORE the fork. — PASS 2026-08-17 18:58 auto: Re-entry Routing IMPLEMENT route reads 'first run the remote drift check, then resume at Step 7' and re-runs 'the Pre-implementation ownership guard, the Deferred worktree fork block, and the Agent Attribution Procedure, in that order'; the environment-setup step is explicitly read-only ('resolve here, fork later'). Block is byte-identical across all 3 profiles and all 3 agent trees.
- [x] POSTIMPL resume: confirm no fork is attempted and Step 9 proceeds from the repo root. — PASS 2026-08-17 18:58 auto: POSTIMPL route states the fork block 'does not run at all' (cutting would either fail on the existing aitask/<task_name> or produce an empty worktree Step 9 would merge) and 'Proceed to Step 9 from the repo root'. Profile- and agent-invariant.
- [x] Legacy plan: strip Base branch: from a plan header, resume, and confirm the agent asks to confirm the base instead of silently using main — then confirm the branch is cut from the answer given. — PASS 2026-08-17 18:58 auto: executed the Re-entry Routing parse against a crafted legacy header (no 'Base branch:') -- yields base=main with provenance 'legacy plan, no Base branch field', which is precisely the trigger for Step 7 check 2's AskUserQuestion confirmation. Source confirms the answer is adopted (base_branch="$confirmed_base") before the cut, which uses "$base_branch"; UNUSABLE_BASE re-asks. Live widget observation owed via item 1.
- [x] Abort before the fork: confirm the abort reports cleanly and removes nothing. — PASS 2026-08-17 18:58 auto: behavioral -- ran the three task-abort.md cleanup commands in a repo with no worktree/branch: exit 0, nothing removed, and the porcelain survey returned empty, so 'clean abort' is truthful pre-fork.
- [x] Abort after a worktree move: confirm the abort names the surviving worktree path instead of reporting a clean abort. — PASS 2026-08-17 18:58 auto: behavioral -- after 'git worktree move', the same cleanup commands silently missed the worktree, and the task-abort.md survey awk printed the surviving moved path. task-abort.md instructs: name that path, 'do not report a clean abort'.
- [x] Crash recovery: interrupt a task between plan approval and the fork, re-pick, and confirm the survey reads "(none — current branch, or fork not reached)" rather than implying current-branch mode. — PASS 2026-08-17 18:58 auto: the survey placeholder reads 'Worktree: <path, or "(none -- current branch, or fork not reached)">' in crash-recovery.md across all 9 rendered variants -- the disjunction no longer implies current-branch mode. Live interrupt/re-pick observation owed via item 1.
- [defer] Step 9 merge: complete a worktree-mode task end to end and confirm the merge and worktree cleanup still work. — DEFER 2026-08-17 18:59 auto: blocked on item 1 -- an end-to-end worktree-mode task through Step 9 merge + worktree cleanup requires a full live implementation cycle.
