---
priority: medium
effort: medium
depends: [t835_6]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [835_1, 835_2, 835_3, 835_4, 835_5, 835_6]
created_at: 2026-05-28 17:22
updated_at: 2026-05-28 17:22
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t835_1] bash tests/test_agent_string.sh tests/test_codeagent*.sh tests/test_resolve_detected_agent.sh — all pass
- [ ] [t835_1] ./.aitask-scripts/aitask_codeagent.sh list-agents — output includes agy
- [ ] [t835_1] ./.aitask-scripts/aitask_resolve_detected_agent.sh --agent agy --cli-id <known-id> — returns AGENT_STRING:agy/<name>
- [ ] [t835_1] Settings TUI launches; the agy mode tab is reachable and lists the stub model without error
- [ ] [t835_1] grep -rn geminicli .aitask-scripts/ — returns nothing new (no accidental t812 reversal)
- [ ] [t835_2] ./.aitask-scripts/aitask_skill_verify.sh passes
- [ ] [t835_2] aitask_skill_render.sh aitask-pick --profile fast --agent agy → .agents/skills/aitask-pick-fast-agy-/SKILL.md
- [ ] [t835_2] Same with --agent codex → .agents/skills/aitask-pick-fast-codex-/SKILL.md (agy variant intact)
- [ ] [t835_2] Rendered agy skill uses run_command / read_url_content tool names where applicable
- [ ] [t835_2] Rendered codex skill still uses codex-correct tool names (no accidental rewrite for codex)
- [ ] [t835_2] bash tests/test_skill_template.sh + render-suite tests pass
- [ ] [t835_3] bash tests/test_agy_setup.sh passes
- [ ] [t835_3] ./ait setup --reinstall in a clean test dir detects agy when binary is on PATH and runs setup_agy_cli() cleanly
- [ ] [t835_3] bash install.sh end-to-end in a throwaway dir succeeds
- [ ] [t835_3] After setup, ls ~/.agy/ shows the directory does NOT exist (agy uses global config)
- [ ] [t835_3] Release workflow dry-check (read workflow file; optional act run) shows no broken paths
- [ ] [t835_4] cd website && ./serve.sh — visually inspect each edited page renders correctly
- [ ] [t835_4] ./.aitask-scripts/aitask_skill_verify.sh passes
- [ ] [t835_4] bash tests/test_*goldens*.sh (or equivalent golden-diff suite) passes
- [ ] [t835_4] grep -rn agy website/content/docs/ shows agy consistently alongside codex where normative
- [ ] [t835_4] grep -rn geminicli website/content/docs/ returns nothing (t812_4 cleanup intact)
- [ ] [t835_5] aitasks/metadata/models_agy.json has >=1 real (non-stub) model
- [ ] [t835_5] An agy CLI session completes /aitask-pick end-to-end with correct implemented_with attribution
- [ ] [t835_5] aidocs/geminicli_to_agy.md no longer exists
- [ ] [t835_5] grep -rn geminicli .aitask-scripts/ seed/ install.sh returns empty
- [ ] [t835_6] Top-to-bottom walk of the reorganized doc maps every change in git log main..HEAD to exactly one section
- [ ] [t835_6] cd website && ./serve.sh — new development/adding-a-new-code-agent page renders and links resolve
- [ ] [t835_6] Fresh-context read-through of reorganized aidocs identifies no remaining clarity gaps
- [ ] [t835_6] grep -c '^## ' aidocs/adding_a_new_codeagent.md shows a reasonable section count (no content lost)
