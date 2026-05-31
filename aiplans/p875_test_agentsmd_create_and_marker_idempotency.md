---
Task: t875_test_agentsmd_create_and_marker_idempotency.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: AGENTS.md coverage for `tests/test_agent_instructions.sh` (t875)

## Context

`ait setup` installs `AGENTS.md` **unconditionally** as the cross-agent
convention (`setup_code_agents()` → `update_agentsmd()` in
`.aitask-scripts/aitask_setup.sh`). `update_agentsmd()` assembles the shared
**Layer-1** instructions (calls `assemble_aitasks_instructions "$project_dir"`
with *no* agent_type) and delegates to `insert_aitasks_instructions()` for
create/replace/append behavior.

The existing suite `tests/test_agent_instructions.sh` (17 tests) exercises the
shared injection machinery and the `CLAUDE.md` path
(`update_claudemd_git_section`, T10–T12), but has **zero cases asserting
`update_agentsmd` behavior**. This task adds that coverage. No production-code
changes — the behavior is already correct; this is purely added tests.

## Approach

Add a new test section `--- update_agentsmd() ---` with four cases (T18–T21)
after the last existing test (T17, ends at line 425) and before the
`Summary` block (line 427). Tests mirror the existing CLAUDE.md tests
(T10–T12) and the idempotency / preserve-surrounding patterns (T5, T4, T15),
reusing the in-file `setup_tmpdir` / `cleanup_tmpdir` helpers and the
`assert_*` helpers already defined.

Key fact that makes the Layer-1-only test meaningful: `setup_tmpdir` already
seeds **both** the shared seed and a **codex** Layer-2 seed
(`codex_instructions.seed.md`, containing `## Skills` → "Invoke skills with"
and `## Agent Identification` → "Identify as `codex/<model_name>`"). Because
`update_agentsmd` passes no agent_type, AGENTS.md must contain the shared
content but NONE of that codex Layer-2 content — even though the Layer-2 seed
is present on disk.

### File to modify

`tests/test_agent_instructions.sh` — two edits:

1. **Header comment** (lines 3–4): add `update_agentsmd()` to the `# Tests:`
   function list.

2. **New test section** inserted before the Summary (after line 425):

   - **T18 — Create-if-missing:** `setup_tmpdir`; call
     `update_agentsmd "$TMPDIR_TEST"` with no pre-existing AGENTS.md; assert
     the created `$TMPDIR_TEST/AGENTS.md` contains `>>>aitasks`, `<<<aitasks`,
     and `## Git Operations` (shared Layer-1). Use `assert_file_contains` to
     also prove the file was actually created.

   - **T19 — Layer-1-only:** `setup_tmpdir`; `update_agentsmd`; assert
     AGENTS.md `assert_contains` `## Git Operations` and
     `assert_not_contains` the codex Layer-2 markers: `Invoke skills with`,
     `## Agent Identification`, and `` Identify as `codex/ ``.

   - **T20 — Marker idempotency:** `setup_tmpdir`; run `update_agentsmd`
     twice; `assert_eq` the two `cat` results are identical; assert exactly
     one `>>>aitasks` marker via `grep -c ... || true` (mirrors T15).

   - **T21 — Preserve surrounding text:** `setup_tmpdir`; pre-create
     AGENTS.md with user prose and no markers; `update_agentsmd`; assert prose
     + header preserved and marked block appended; run a second time; assert
     prose still preserved and exactly one marker block remains (replace-only
     region, mirrors T4/T15).

All four use the existing `assert_eq`, `assert_contains`,
`assert_not_contains`, `assert_file_contains` helpers — no new helpers needed.
The `PASS/FAIL/TOTAL` counters and Summary block already tally any added
asserts automatically.

## Verification

```bash
bash tests/test_agent_instructions.sh
```

Expect: all tests pass (PASS count rises by the number of new asserts; "All
tests passed!"). Spot-check that T18–T21 appear in output under the new
`--- update_agentsmd() ---` heading.

Optional lint:
```bash
shellcheck tests/test_agent_instructions.sh   # if shellcheck is run on tests
```

## Step 9 (Post-Implementation)

Working on the current branch (profile `fast`), so no worktree/branch merge.
After review+commit: run `./.aitask-scripts/aitask_archive.sh 875`, then
`./ait git push`.
