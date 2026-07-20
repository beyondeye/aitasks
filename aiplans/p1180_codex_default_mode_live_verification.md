---
Task: t1180_codex_default_mode_live_verification.md
Worktree: (none — profile 'fast', working on current branch)
Branch: main
Base branch: main
---

# t1180 — Codex default-mode live verification

## Plan

1. Establish the runtime baseline without changing product source: inspect the two Codex launch builders, the pick skill's three-step stub, the setup seed, and t1171's archived plan. Record the exact expected direct command shape and the expected rendered-skill target.
2. In a real tmux session, launch `ait codeagent --agent-string codex/<available-model> invoke pick <N>` against a harmless ready task. Observe that Codex opens in default mode (not read-only plan mode), then let the pick stub reach its render step. Verify the target `.agents/skills/aitask-pick-<profile>-codex-/SKILL.md` has a new mtime and is readable by step 3.
3. At the first interactive task/plan checkpoint, confirm `request_user_input` is rendered and usable in the default-mode Codex session. End the nested Codex session without selecting or altering a task beyond the live verification.
4. Repeat the live launch through `ait skillrun pick --agent-string codex/<available-model> -- <N>` in a separate tmux session. Confirm default mode, successful render/write, rendered-file read, and an interactive checkpoint.
5. Create a temporary clean project copy outside the repository state, run `ait setup` there, and verify setup succeeds, the generated Codex config contains `default_mode_request_user_input = true`, and its dependency declarations/install log contain no `pexpect` requirement.
6. Run the structural guard `bash tests/test_codex_no_plan_injection.sh` as supporting evidence. Record every live-check outcome, command/session evidence, and any environment limitation in this plan's final notes. Step 9 then archives this verification task only after the gate results are recorded.

## Verification

- Both non-dry-run launch surfaces start Codex in default mode and reach an interactive `request_user_input` checkpoint.
- Each pick-stub invocation writes and subsequently reads the corresponding rendered Codex skill variant.
- A clean `ait setup` completes with default-mode prompting enabled and without `pexpect` in its dependency set.
- `bash tests/test_codex_no_plan_injection.sh` passes.

## Risk

### Code-health risk: low
- This task changes no production source; its only persistent output is the task/plan evidence record. · severity: low · → mitigation: manual review before archival

### Goal-achievement risk: medium
- Terminal/TUI observations can be confounded by a pre-existing local configuration or an unavailable Codex model, so each launch surface is checked independently and setup is run in a clean copy. · severity: medium · → mitigation: the independent live sessions and clean-environment setup check in this plan
