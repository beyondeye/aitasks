---
priority: medium
effort: medium
depends: [t573_4]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [t573_1, t573_2, t573_3, t573_4]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-23 11:05
updated_at: 2026-06-02 12:07
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [x] [t573_1] bash tests/test_apply_initializer_output.sh passes (fixture-driven). — PASS 2026-06-02 12:07 auto: bash tests/test_apply_initializer_output.sh -> 8/8 PASS
- [x] [t573_1] apply_initializer_output with a malformed output file raises ValueError and leaves existing n000_init.yaml/n000_init.md untouched. — PASS 2026-06-02 12:07 auto: malformed _output.md raises ValueError (missing PROPOSAL delimiter); pre-existing n000_init.yaml/.md md5 unchanged
- [x] [t573_1] init_session(..., initial_proposal_file=None) is byte-for-byte identical to the pre-change behaviour for a new session. — PASS 2026-06-02 12:07 auto: test_backward_compat_no_flag PASS; init_session(None) adds no initial_proposal_file key, uses legacy else-branch (proposal_body=initial_spec), bootstrap status Completed
- [x] [t573_2] ait brainstorm init <N> --proposal-file /nonexistent exits non-zero with clear error; no crew directory created. — PASS 2026-06-02 12:07 auto: init 999999 --proposal-file /nonexistent -> exit 1, 'Proposal file not found', no crew dir; test_brainstorm_init_proposal_file.sh 3/3 PASS
- [x] [t573_2] ait brainstorm init <N> --proposal-file real.md stdout contains SESSION_PATH: and INITIALIZER_AGENT:initializer_bootstrap; br_session.yaml has initial_proposal_file set; crew runner auto-started (or a clear warn if the runner helper name differs). — PASS 2026-06-02 12:07 auto: TestInitWithProposalFile.test_happy_path PASS - stdout SESSION_PATH + INITIALIZER_AGENT:initializer_bootstrap, br_session.yaml initial_proposal_file set, start_runner invoked
- [x] [t573_2] ait brainstorm init <N> with no flag behaves identically to pre-change (stdout is just SESSION_PATH:, no initializer agent, no runner auto-start). — PASS 2026-06-02 12:07 auto: test_backward_compat_no_flag PASS - no flag emits only SESSION_PATH, no initializer agent, no runner, no initial_proposal_file key
- [x] [t573_3] ait brainstorm <fresh> modal shows three buttons: Initialize Blank / Import Proposal… / Cancel. — PASS 2026-06-02 12:07 auto: Textual pilot - InitSessionModal renders 3 buttons: Initialize Blank / Import Proposal / Cancel
- [x] [t573_3] Initialize Blank path behaves exactly as before (n000_init body = task file). — PASS 2026-06-02 12:07 auto: pilot - Initialize Blank dismisses 'blank' -> unchanged _run_init; init_session blank path proposal_body=initial_spec (task file body)
- [x] [t573_3] Import Proposal… opens a DirectoryTree modal limited to .md/.markdown files + directories; escape returns to the main modal without exiting the TUI. — PASS 2026-06-02 12:07 auto: pilot - Import Proposal pushes ImportProposalFilePicker (markdown-only DirectoryTree subclass); escape returns to InitSessionModal, TUI stays running
- [ ] [t573_3] After selecting a valid .md, the TUI shows a waiting notification and polls until the initializer agent reaches Completed; on completion the DAG pane shows a properly sectioned n000_init with visible dimensions.
- [ ] [t573_3] Imported source file mtime and md5 are unchanged after the full flow.
- [ ] [t573_3] Simulated initializer failure (malformed _output.md) surfaces as an error-severity notification; the placeholder n000_init is retained and the TUI remains usable.
- [ ] [t573_3] Running outside tmux (unset TMUX) still reaches Completed via the headless fallback.
- [x] [t573_4] grep "initializer" aidocs/brainstorming/brainstorm_engine_architecture.md returns §5 and §7 additions plus the ASCII block update. — PASS 2026-06-02 12:07 auto: grep initializer in brainstorm_engine_architecture.md -> S5 (577-589), S7.1a (935-941), ASCII (63), layout table (162,164)
- [ ] [t573_4] defaults.brainstorm-initializer is present and identical in both aitasks/metadata/codeagent_config.json and seed/codeagent_config.seed.json.
- [x] [t573_4] No "previously" / "now" / "used to be" phrasing in the user-facing doc diff. — PASS 2026-06-02 12:07 auto: t573_4 commit b7d9c994 doc diff added-lines contain no previously/now/used-to-be phrasing
