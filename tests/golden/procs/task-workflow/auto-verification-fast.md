# Auto-Verification Procedure

Automated verification for `manual_verification` tasks. Invoked from
`manual-verification.md` Step 1.5 (whole checklist) and Step 2 (single item,
via the `auto` verb). Supports two strategies:

- **Impromptu** — execute each item inline, picking the verification
  approach on the fly. The plan file is written **at the end** as a
  retroactive record of what was actually run. This is the default the
  Step 1.5 prompt recommends.
- **Pre-built** — design a per-item execution plan up front, write it to
  the plan file, optionally request approval via `EnterPlanMode` /
  `ExitPlanMode`, then execute and append an Execution Log.

## Input context

| Variable | Type | Description |
|----------|------|-------------|
| `task_file` | string | path to the manual_verification task file |
| `task_id` | string | task identifier (e.g. `787` or `571_7`) |
| `is_child` | boolean | whether `task_id` is a child task |
| `parent_id` | string/null | parent number if `is_child`, else null |
| `strategy` | string | `"impromptu"` or `"prebuilt"` |
| `approval_required` | boolean | only meaningful when `strategy == "prebuilt"`; ignored otherwise. `true` → `EnterPlanMode` + `ExitPlanMode` |
| `single_item` | int/null | when set, restrict to that one item index (Step 2 per-item path); null = whole checklist. **Forces `strategy = "impromptu"`** regardless of the caller's value. |
| `active_profile` | object | loaded execution profile |

## Plan file path

- parent task: `aiplans/p<task_id>_manual_verification_auto.md`
- child task: `aiplans/p<parent_id>/p<task_id>_manual_verification_auto.md`

Metadata header mirrors the parent / child header templates from
`planning.md`'s **Save Plan to External File** section.

## Procedure

### 1. Enumerate target items

```bash
./.aitask-scripts/aitask_verification_parse.sh parse <task_file>
```

If `single_item` is set, filter to that one index. Otherwise keep every
item currently in state `pending` or `defer`.

If no target items remain, return to the caller immediately (no plan file
written).

### 2. Strategy branch

#### 2a. Impromptu (`strategy == "impromptu"`)

For each target item, in order:

1. **Pick a verification approach on the fly.** Heuristics:
   - **File inspection** — text/YAML/JSON the item references → `cat` /
     `grep` / `head` / a Python one-liner.
   - **CLI invocation** — the item names a script, subcommand, or `ait`
     verb → invoke via Bash and check exit code / output.
   - **TUI interaction** — TUIs like `ait brainstorm` / `ait monitor` →
     spawn a detached tmux session, drive it with `tmux send-keys`,
     capture pane content with `tmux capture-pane -p`. Reuse the
     session-creation pattern at
     `.aitask-scripts/lib/tmux_bootstrap.sh:158`;
     `.aitask-scripts/monitor/monitor_app.py:84,1388` shows the
     Textual-key → tmux-key mapping.
   - **Test data fabrication** — when a verification needs seeded state,
     create scratch files under
     `${TMPDIR:-/tmp}/auto_verify_<task_id>_<idx>/` (cleaned at end).
     Never mutate user-owned files in `aitasks/` / `aiplans/` other than
     the checklist itself.
   - **Not automatable** — UX judgement, visual rendering, multi-screen
     flows → mark `defer` with a reason. No execution attempted.

2. **Execute** and capture stdout / stderr / exit-code.

3. **Mark state** (same per-state helpers as the interactive loop):
   - Pass criterion met:
     ```bash
     ./.aitask-scripts/aitask_verification_parse.sh set <task_file> <idx> pass --note "auto: <one-line summary>"
     ```
   - Pass criterion violated:
     ```bash
     ./.aitask-scripts/aitask_verification_followup.sh --from <task_id> --item <idx>
     ```
     Parse `FOLLOWUP_CREATED` / `ORIGIN_AMBIGUOUS` / `ERROR` exactly as
     in `manual-verification.md` step 2 Fail branch.
   - Cannot decide / blocked:
     ```bash
     ./.aitask-scripts/aitask_verification_parse.sh set <task_file> <idx> defer --note "auto: <why blocked>"
     ```

4. **Append to an in-memory execution log** (the actual file write happens
   in step 3 below).

#### 2b. Pre-built (`strategy == "prebuilt"`)

1. Read all target items.
2. Design a per-item plan using the same heuristics as 2a step 1, but
   write nothing yet.
3. Write the plan file (Write tool) with sections:
   - `## Pre-built Auto-Execution Plan` — numbered list, one entry per
     target item: `<idx>. [<expected_state>] <item text>` with indented
     bullets:
     - `- Strategy: <classification>`
     - `- Action: <bash / tmux command>`
     - `- Pass criterion: <how the agent decides Pass>`
     - `- Fail / defer fallback: <what triggers each>`
   - `## Cleanup` — scratch files / tmux sessions to remove afterwards.
4. **Approval gate.** If `approval_required == true`:
   - `EnterPlanMode`.
   - `ExitPlanMode` for user approval (the plan file content is what the
     user reviews).
   - If user rejects → delete the just-written plan file, return to the
     caller without mutating any item state.
5. Execute each item per the approved plan, marking state via the same
   helpers as 2a step 3. After each item, append a `### Item <idx>` block
   under a `## Execution Log` H2 of the plan file (Edit tool, growing the
   file in place).

### 3. Write or finalise the plan file

- **Impromptu path:** Write the plan file (Write tool) now, with sections:
  - Frontmatter header per "Plan file path" above.
  - `## Execution Log` — for each item processed: `### Item <idx>` with:
    - `- Item text: <text>`
    - `- Approach: <classification>`
    - `- Action run: <bash / tmux>`
    - `- Output (trimmed): <captured>`
    - `- Verdict: pass | fail | defer`
  - `## Cleanup` — scratch files / tmux sessions removed (or to remove if
    the next step is interrupted).
- **Pre-built path:** plan file already exists from step 2b; ensure the
  Execution Log appended in step 2b step 5 is complete.

### 4. Cleanup

Remove scratch dirs and any tmux sessions created during execution. Match
the `## Cleanup` list in the plan file.

### 5. Commit plan file

```bash
./ait git add aiplans/<plan_path>
./ait git commit -m "ait: Add manual-verification auto-execution plan for t<task_id>"
```

### 6. Return

Return to `manual-verification.md`:
- Step 1.5 caller → fall through to step 2 (interactive loop); items
  still `pending` / `defer` are handled interactively.
- Step 2 single-item caller (the `auto` verb path) → return to step 2's
  loop top so the checklist re-renders with the new state.
