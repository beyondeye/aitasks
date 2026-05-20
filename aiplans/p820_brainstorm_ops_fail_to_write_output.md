---
Task: t820_brainstorm_ops_fail_to_write_output.md
Base branch: main
plan_verified: []
---

# Plan: Fix brainstorm/crew agents failing their first write to `_output.md` (t820)

## Context

While running `agent-detailer_001` in brainstorm-635, the code agent failed to
write its output **on the first attempt**, succeeding only on a retry. The same
symptom appeared on other operations in the same brainstorm — a systematic
issue, not a one-off.

**Root cause (confirmed by tracing the code path):**

1. `aitask_crew_addwork.sh` pre-creates `<agent>_output.md` on disk at agent
   registration time, with placeholder content (`.aitask-scripts/aitask_crew_addwork.sh:200-203`):
   ```
   # Output from agent: <name>

   This file is populated by the agent during/after execution.
   ```
2. Brainstorm agents run as **Claude Code** (`_runner_launch.log` shows
   `string=claudecode/sonnet4_6`). Claude Code's `Write` tool **refuses to
   overwrite a file that exists but has not been `Read` in the session**
   ("File has not been read yet").
3. The agent reads `_input.md` (the templates tell it to) but **never reads
   `_output.md`** — it only writes to it. So its first `Write` fails; it then
   reads the placeholder and the second `Write` succeeds.
4. This is systematic because `addwork` pre-creates `_output.md` for **every**
   agent type — explorer, comparator, synthesizer, detailer, patcher,
   initializer.

The pre-created placeholder is intentional (it is committed at registration
time and `_output.md` is part of the crew file contract), so the chosen fix
keeps it and instead tells the agent to read it once before writing.

**Approach chosen by the user:** instruct the agent to read the output file
first — a contained, agent-agnostic change to the generated `_instructions.md`.
The brainstorm `templates/*.md` are deliberately NOT touched: `_instructions.md`
is the canonical shared location every agent consults for the output path.

**Note on the working tree:** there are pre-existing uncommitted changes (an
in-flight `apply-detailer` feature touching `brainstorm_app.py`,
`brainstorm_session.py`, `templates/detailer.md`, `ait`, plus untracked
`aitask_brainstorm_apply_detailer.sh` and two test files). This fix touches
`aitask_crew_addwork.sh` only — no overlap. Step 8 will commit only the t820
files.

## Changes

### 1. `.aitask-scripts/aitask_crew_addwork.sh` — `_instructions.md` "Writing Output" section

The `_instructions.md` body is built as a double-quoted string argument to
`write_yaml_file` (lines 206-254). Amend the `## Writing Output` section
(currently lines 235-236):

```
## Writing Output
Write your results to: ${AGENT_NAME}_output.md
```

to:

```
## Writing Output
Write your results to: ${AGENT_NAME}_output.md

This file already exists with placeholder content. Some file-write tools
require reading a file before overwriting it — if so, read
${AGENT_NAME}_output.md once first, then write your results.
```

`${AGENT_NAME}` stays unescaped (it is substituted into the file, as elsewhere
in this string). The text has no backticks or double-quotes, so it is safe
inside the double-quoted argument. An em-dash is already used elsewhere in the
same string (line 226-227), so it is fine here.

### 2. New regression test — `tests/test_crew_addwork_output_instructions.sh`

A self-contained bash test mirroring the harness in `tests/test_crew_groups.sh`
(`setup_test_repo` / `cleanup_test_repo`, file-based `assert_*` helpers):

- `setup_test_repo` (copy `.aitask-scripts/`, `git init`).
- `ait crew init` a test crew, then `aitask_crew_addwork.sh` an agent.
- Assert the generated `<agent>_instructions.md`:
  - contains the `## Writing Output` header, and
  - contains the read-before-write note (e.g. grep for
    `require reading a file before overwriting`).

This locks in the fix; no existing test asserts the "Writing Output" section
(the string `Writing Output` appears only in `aitask_crew_addwork.sh`).

## Critical files

- `.aitask-scripts/aitask_crew_addwork.sh` — the only source change (lines 235-236).
- `tests/test_crew_addwork_output_instructions.sh` — new test.
- Reference for the test harness: `tests/test_crew_groups.sh` (lines 79-150).

## Verification

1. `bash tests/test_crew_addwork_output_instructions.sh` → all PASS.
2. `bash tests/test_crew_groups.sh` and `bash tests/test_crew_status.sh` → still
   PASS (both exercise `addwork`; sanity check the heredoc edit didn't break it).
3. `shellcheck .aitask-scripts/aitask_crew_addwork.sh` → clean.
4. Manual spot-check: run `addwork` in a scratch repo and confirm the generated
   `<agent>_instructions.md` shows the new note under `## Writing Output`.

## Post-implementation (Step 9)

Commit the code change (`bug: ... (t820)`) and the plan file separately, merge,
archive task t820.
