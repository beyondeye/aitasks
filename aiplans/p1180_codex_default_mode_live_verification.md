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

## Live Verification Result — FAILED

- **`ait codeagent invoke pick` (live tmux): PASS.** `codex/gpt5_6_terra` opened with the status line `default`, not plan mode; the pick stub ran `aitask_skill_render.sh aitask-pick --profile fast --agent codex`, read the rendered fast Codex variant, and displayed its default-mode `request_user_input` label-filter question. The rendered file mtime advanced to `2026-07-20 09:51:04 +0300` during this launch.
- **`ait skillrun pick` (live tmux): PASS.** The second surface opened in default mode, ran the same render-and-read path, and displayed the default-mode label-filter question. It was stopped before a task was selected.
- **Structural guard: PASS.** `bash tests/test_codex_no_plan_injection.sh` reported `PASS: 29 / 29`.
- **Clean `ait setup`: PARTIAL / BLOCKING FAILURE.** A disposable clone and home under `/tmp/t1180-setup-verify` completed setup offline using the existing framework venv; its dependency declarations contained no `pexpect`. But the resulting `.codex/config.toml` has no `[features]` section and no `default_mode_request_user_input = true`.
- **Cause:** `aitask_setup.sh:2067` looks for `aitasks/metadata/codex_config.seed.toml`, but a fresh initialized data branch contains `codex_instructions.seed.md` and lacks both `codex_config.seed.toml` and `codex_rules.default.rules`. The repository source has the missing files only under `seed/`; setup therefore leaves the pre-existing project `.codex/config.toml` unmerged. This violates t1171's load-bearing setup assumption.
- **Outcome:** do not archive t1180. t1171's setup-seed path needs correction (or an equivalent fallback) before the live verification can pass in a clean install.

## Final Implementation Notes

- **Actual work done:** Executed both live Codex launch surfaces in disposable tmux sessions, ran a clean-home setup in a disposable clone, and ran the structural guard. No production source files were changed.
- **Deviations from plan:** The first clean setup attempt lacked a Git identity and the second could not resolve PyPI. A repository-local temporary identity plus an offline, read-only existing framework venv allowed the setup logic to complete without changing the real home or repository.
- **Issues encountered:** The clean setup exposed the missing task-data Codex configuration/rules seed files described above.
- **Key decisions:** Used a non-existent task ID (`999999`) so both nested pick sessions reached `request_user_input` without claiming or modifying another task.
- **Upstream defects identified:**
  - `.aitask-scripts/aitask_setup.sh:2067 and :2081 — clean data-branch initialization does not seed codex_config.seed.toml or codex_rules.default.rules into aitasks/metadata, while setup reads only those paths; fresh `ait setup` therefore omits the default_mode_request_user_input feature required by t1171.`
