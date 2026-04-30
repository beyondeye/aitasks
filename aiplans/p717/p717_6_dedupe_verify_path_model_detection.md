---
Task: t717_6_dedupe_verify_path_model_detection.md
Parent Task: aitasks/t717_codeagent_usage_stats_improvements.md
Sibling Tasks: aitasks/t717/t717_5_manual_verification_codeagent_usage_stats.md
Archived Sibling Plans: aiplans/archived/p717/p717_1_*.md, aiplans/archived/p717/p717_2_*.md, aiplans/archived/p717/p717_3_*.md, aiplans/archived/p717/p717_4_*.md
Worktree: (none — current branch)
Branch: main
Base branch: main
---

## Context

In a verify-mode pick (e.g. `plan_preference_child: verify` resolves to `DECISION:VERIFY` or `ASK_STALE → Verify now`), the Model Self-Detection sub-procedure currently runs **twice** during a single workflow:

1. `planning.md` line 90 (Step 6.1, "After `ExitPlanMode` on the verify path") detects to obtain an `agent_string` for the `plan_verified` append entry.
2. `agent-attribution.md` line 9 (Step 7) detects again to set `detected_agent_string` for downstream reuse.

The two call sites do not share state: the verify-append path obtains `agent_string` locally and discards it. By Step 7 the value is gone, so attribution must redetect.

This is independent of t717_2's usagestats hook, which already correctly reuses `detected_agent_string` via the satisfaction-feedback Step 9b fast path. The pattern is the same: detect once, reuse via context variable. We just need to extend it to cover the verify-append → attribution path.

The cost is small (a system-message read + a script invocation, ~tens of ms) but real, and the cleanup is mostly about correctness/clarity. The fix is a docs-only refactor — three skill instruction files in `.claude/skills/task-workflow/`.

## Files to Modify

1. `.claude/skills/task-workflow/planning.md`
2. `.claude/skills/task-workflow/agent-attribution.md`
3. `.claude/skills/task-workflow/SKILL.md`

## Edits

### 1. `.claude/skills/task-workflow/planning.md` — verify-path append

Currently lines 88–97 of the "After `ExitPlanMode` on the verify path" sequence read:

```
Sequence (runs inside the **Save Plan to External File** section, after the externalize helper emits `EXTERNALIZED:` / `OVERWRITTEN:` but before the `./ait git add`):

1. Execute the **Model Self-Detection Sub-Procedure** (see `model-self-detection.md`) to obtain `agent_string` (e.g., `claudecode/opus4_6`).
2. Run:
   ```bash
   ./.aitask-scripts/aitask_plan_verified.sh append <external_plan_path> "<agent_string>"
   ```
3. The append modifies the plan file in place. ...
```

**Change:** Insert a new step `1b` between current steps 1 and 2 that stores the resolved value into the workflow's `detected_agent_string` context variable so downstream procedures can reuse it.

Resulting steps:

```
1. Execute the **Model Self-Detection Sub-Procedure** (see `model-self-detection.md`) to obtain `agent_string` (e.g., `claudecode/opus4_6`).
1b. Set `detected_agent_string` = `agent_string` so downstream procedures (Step 7 Agent Attribution, Step 9b Satisfaction Feedback) can reuse the resolved value instead of re-detecting.
2. Run:
   ```bash
   ./.aitask-scripts/aitask_plan_verified.sh append <external_plan_path> "<agent_string>"
   ```
3. The append modifies the plan file in place. ...
```

The `1b` numbering (rather than renumbering 2→3, 3→4) keeps the diff localized and matches the user's preferred numbering in the task description.

### 2. `.claude/skills/task-workflow/agent-attribution.md` — fast-path guard

Currently line 9 reads:

```
1. Execute the **Model Self-Detection Sub-Procedure** (see `model-self-detection.md`) to get `agent_string`.
```

**Change:** Replace this line with a fast-path guard that mirrors the existing Step 9b satisfaction-feedback pattern (`satisfaction-feedback.md` line 18 and lines 40–49):

```
1. **Resolve agent string:**

   **Fast path:** If `detected_agent_string` is already set (non-null, non-empty) from an earlier procedure (e.g., the verify-path append in `planning.md` Step 6.1), use it directly as `agent_string` and skip detection.

   **Otherwise:** Execute the **Model Self-Detection Sub-Procedure** (see `model-self-detection.md`) to get `agent_string`.
```

Step 3 of the same procedure already says "Set `detected_agent_string` to the resolved `agent_string` value" — that line is preserved unchanged so the variable is also set when the fallback fires.

### 3. `.claude/skills/task-workflow/SKILL.md` — Context Requirements row

Currently line 26 (the `detected_agent_string` row of the Context Requirements table) reads:

```
| `detected_agent_string` | string/null | Agent string from Agent Attribution (e.g., `claudecode/opus4_6`). Set by Agent Attribution in Step 7, consumed by Satisfaction Feedback in Step 9b to skip re-detection. Initialized to `null`. |
```

**Change:** Update the description to reflect both writers and both consumers:

```
| `detected_agent_string` | string/null | Agent string (e.g., `claudecode/opus4_6`). Set by either the verify-path append in `planning.md` Step 6.1 or by Agent Attribution in Step 7. Consumed by Agent Attribution (fast-path) and by Satisfaction Feedback in Step 9b to skip re-detection. Initialized to `null`. |
```

## Cross-agent mirroring (no-op for this task)

The task description's step 4 asks to mirror the same edits to `.opencode/skills/task-workflow/` and `.agents/skills/task-workflow/` (the consolidated Codex/Gemini wrapper). Verified during planning:

```
$ ls .opencode/skills/task-workflow/  → No such file or directory
$ ls .agents/skills/task-workflow/    → No such file or directory
```

Neither tree currently has a port of `task-workflow`, so there is nothing to mirror for this task. Per CLAUDE.md ("WORKING ON SKILLS / CUSTOM COMMANDS"), the standard practice when no port exists is to surface the cross-agent ports as a post-implementation suggestion for the user to file as separate aitasks if/when those wrapper trees gain a `task-workflow` skill. Will be flagged in the Step 8 review.

## Verification

This is a docs-only / skill-instructions refactor; no automated tests apply. Verify by:

1. **Re-read the three edited files end-to-end** and confirm:
   - `planning.md` verify-append section has step `1b` setting `detected_agent_string` immediately after the Model Self-Detection call.
   - `agent-attribution.md` step 1 explicitly mentions the fast-path checking `detected_agent_string` non-null/non-empty, then falls through to Model Self-Detection. Step 3 still sets `detected_agent_string` (so the fallback path also writes it).
   - `SKILL.md` Context Requirements row mentions both writers (`planning.md` Step 6.1 verify-append AND Agent Attribution Step 7) and both consumers (Agent Attribution fast-path AND Satisfaction Feedback Step 9b).

2. **Trace a verify-mode pick mentally** through the workflow:
   - Step 6.0 → `plan_preference_child: verify` → `DECISION:VERIFY` → enter verify mode.
   - Step 6.1 ExitPlanMode → externalize plan → verify-path append: Model Self-Detection fires once, `detected_agent_string` populated.
   - Step 7 Agent Attribution → fast-path hits → skips Model Self-Detection.
   - Step 9b Satisfaction Feedback → existing fast-path hits → skips Model Self-Detection.
   - Total: one detection per pick on the verify path. ✓

3. **Trace a non-verify pick** to confirm no regression:
   - Step 6.0 → `plan_preference: use_current` (or no existing plan) → no verify-append.
   - Step 7 Agent Attribution → `detected_agent_string` is null → fallback fires → Model Self-Detection runs once, sets `detected_agent_string`.
   - Step 9b Satisfaction Feedback → fast-path hits → skip.
   - Total: one detection per pick. ✓

4. **No shellcheck step** — no shell scripts are touched.

## Step 9 reference

Standard task-workflow Step 9 archival applies (no worktree to clean up since `create_worktree: false`). The plan file will be archived to `aiplans/archived/p717/p717_6_dedupe_verify_path_model_detection.md` and serve as the primary reference for any future sibling tasks that touch model-self-detection call sites.

## Notes for sibling tasks

- The convention established here — "if you call Model Self-Detection in a new place, check `detected_agent_string` first and store the result on the fallback path" — is now uniform across `planning.md` (verify-append, write-only), `agent-attribution.md` (fast-path read + fallback write), and `satisfaction-feedback.md` (fast-path read + fallback write).
- t717_2's `usage_collected` Step 0 already inherits `detected_agent_string` correctly; this refactor does not alter that. Land order does not matter — t717_2 (already archived) and t717_6 are independent.
- Future sibling skills that add new model-self-detection call sites must follow this pattern: check `detected_agent_string` first, detect only on null, and store the result back to `detected_agent_string` on the fallback path.
- If/when `.opencode/skills/task-workflow/` or `.agents/skills/task-workflow/` (consolidated Codex/Gemini) gains a port of `task-workflow`, the same three edits must be mirrored there. This is filed as a post-implementation follow-up suggestion at Step 8.

## Final Implementation Notes

- **Actual work done:** Three docs-only edits to `.claude/skills/task-workflow/` exactly as planned:
  1. `planning.md` (verify-path append, line 91): inserted new step `1b` setting `detected_agent_string = agent_string` after the Model Self-Detection call.
  2. `agent-attribution.md` (Step 1): replaced the unconditional Model Self-Detection call with a Fast path / Otherwise structure that checks `detected_agent_string` first and falls through to detection on null/empty. Step 3's "Set `detected_agent_string`" remains unchanged so the fallback path still writes the variable.
  3. `SKILL.md` (Context Requirements row line 26): updated `detected_agent_string` description to list both writers (`planning.md` Step 6.1 verify-append + Agent Attribution Step 7) and both consumers (Agent Attribution fast-path + Satisfaction Feedback Step 9b).
- **Deviations from plan:** None. The plan was followed verbatim.
- **Issues encountered:** None. Each edit was a single small targeted Edit-tool replacement; no redos required.
- **Key decisions:**
  - Used `1b` numbering rather than renumbering 2→3, 3→4 in `planning.md`. This preserves identifier stability for any external references and matches the user's task description verbatim.
  - In `agent-attribution.md`, kept Step 3's `detected_agent_string` write-back even though the fast path already has the value — necessary because the fallback path must still write the variable so a hypothetical third downstream consumer also benefits, and avoids needing to add a guard inside Step 3.
  - In the `SKILL.md` row, dropped the leading "from Agent Attribution" qualifier since attribution is no longer the only writer; replaced with the neutral "Agent string (e.g., `claudecode/opus4_6`)".
- **Upstream defects identified:** None
- **Notes for sibling tasks:**
  - The convention established here — "if you call Model Self-Detection in a new place, check `detected_agent_string` first and store the result on the fallback path" — is now uniform across `planning.md` (verify-append, write-only), `agent-attribution.md` (fast-path read + fallback write), and `satisfaction-feedback.md` (fast-path read + fallback write). Sibling skills adding new self-detection call sites should follow the same pattern.
  - Cross-agent mirroring (`.opencode/skills/task-workflow/`, `.agents/skills/task-workflow/`): verified during implementation that neither tree currently contains a `task-workflow` port (`ls` returned "No such file or directory" for both). Mirroring is therefore a no-op for this task. If/when those wrapper trees gain a `task-workflow` port, the same three edits must be applied there — flagged for the user as an optional follow-up.
  - Verification (manual trace) reconfirmed: verify-mode pick now fires Model Self-Detection exactly once (in the verify-append step); non-verify pick still fires it exactly once (in Step 7 Agent Attribution via the fallback). No regression.
