---
priority: medium
effort: low
depends: []
issue_type: test
status: Implementing
labels: [testing, agents_md, ait_setup]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-05-31 12:54
updated_at: 2026-05-31 16:59
boardidx: 60
---

Add AGENTS.md-specific coverage to `tests/test_agent_instructions.sh`. The suite
(16 tests) exercises the shared aitasks-instruction injection but has **no case
asserting AGENTS.md behavior**, even though `ait setup` installs AGENTS.md
unconditionally as the cross-agent convention.

## Background (verified during t869 exploration)

In `.aitask-scripts/aitask_setup.sh`:
- `setup_code_agents()` calls `update_agentsmd "$project_dir"` **unconditionally**
  (~`:1054`) — independent of whether any agent CLI is installed
  (comment ~`:1051`: "AGENTS.md is a cross-agent convention").
- `update_agentsmd()` (~`:1054`) assembles the **shared Layer-1** instructions
  (`assemble_aitasks_instructions` with no agent_type) and calls
  `insert_aitasks_instructions()`.
- `insert_aitasks_instructions()` (~`:1005`):
  - creates the file when absent: `if [[ ! -f "$target" ]]; then echo
    "$marked_block" > "$target"` (~`:1013-1015`);
  - when the `>>>aitasks` marker exists, replaces only the content between
    `>>>aitasks` / `<<<aitasks` (idempotent, via the awk block ~`:1018-1028`);
  - otherwise appends the marked block (~`:1030-1031`), preserving surrounding
    text.

## What to test

Add cases (mirroring the existing CLAUDE.md tests in the same file) asserting:

1. **Create-if-missing:** with no pre-existing `AGENTS.md`, `update_agentsmd`
   creates it containing the `>>>aitasks` / `<<<aitasks` block and the shared
   Layer-1 content.
2. **Layer-1-only:** AGENTS.md receives the shared content but NOT agent-specific
   Layer-2 (e.g. it must NOT contain the codex/opencode agent-identification
   blurb that `.codex/instructions.md` / `.opencode/instructions.md` get).
3. **Marker idempotency:** running `update_agentsmd` twice produces identical
   output (single marker block, no duplication).
4. **Preserve surrounding text:** a pre-existing `AGENTS.md` with user prose and
   no markers gets the block appended without clobbering the prose; a second run
   replaces only the marked region.

## Reference

Follow the existing CLAUDE.md test patterns in `tests/test_agent_instructions.sh`
(scaffold a temp project dir, call the function, grep the output). Use the
`assert_eq` / `assert_contains` helpers already in the suite. No production-code
changes are expected — this is purely added coverage for already-correct behavior.

## Verification

- `bash tests/test_agent_instructions.sh` passes with the new AGENTS.md cases.
