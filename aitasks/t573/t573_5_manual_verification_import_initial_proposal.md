---
priority: medium
effort: medium
depends: [t573_4]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [573_1, 573_2, 573_3, 573_4]
created_at: 2026-04-23 11:05
updated_at: 2026-04-23 11:05
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t573_1] bash tests/test_apply_initializer_output.sh passes (fixture-driven).
- [ ] [t573_1] apply_initializer_output with a malformed output file raises ValueError and leaves existing n000_init.yaml/n000_init.md untouched.
- [ ] [t573_1] init_session(..., initial_proposal_file=None) is byte-for-byte identical to the pre-change behaviour for a new session.
- [ ] [t573_2] ait brainstorm init <N> --proposal-file /nonexistent exits non-zero with clear error; no crew directory created.
- [ ] [t573_2] ait brainstorm init <N> --proposal-file real.md stdout contains SESSION_PATH: and INITIALIZER_AGENT:initializer_bootstrap; br_session.yaml has initial_proposal_file set; crew runner auto-started (or a clear warn if the runner helper name differs).
- [ ] [t573_2] ait brainstorm init <N> with no flag behaves identically to pre-change (stdout is just SESSION_PATH:, no initializer agent, no runner auto-start).
- [ ] [t573_3] ait brainstorm <fresh> modal shows three buttons: Initialize Blank / Import Proposal… / Cancel.
- [ ] [t573_3] Initialize Blank path behaves exactly as before (n000_init body = task file).
- [ ] [t573_3] Import Proposal… opens a DirectoryTree modal limited to .md/.markdown files + directories; escape returns to the main modal without exiting the TUI.
- [ ] [t573_3] After selecting a valid .md, the TUI shows a waiting notification and polls until the initializer agent reaches Completed; on completion the DAG pane shows a properly sectioned n000_init with visible dimensions.
- [ ] [t573_3] Imported source file mtime and md5 are unchanged after the full flow.
- [ ] [t573_3] Simulated initializer failure (malformed _output.md) surfaces as an error-severity notification; the placeholder n000_init is retained and the TUI remains usable.
- [ ] [t573_3] Running outside tmux (unset TMUX) still reaches Completed via the headless fallback.
- [ ] [t573_4] grep "initializer" aidocs/brainstorming/brainstorm_engine_architecture.md returns §5 and §7 additions plus the ASCII block update.
- [ ] [t573_4] defaults.brainstorm-initializer is present and identical in both aitasks/metadata/codeagent_config.json and seed/codeagent_config.seed.json.
- [ ] [t573_4] No "previously" / "now" / "used to be" phrasing in the user-facing doc diff.
