---
Task: t1071_1_shadow_diagnose_errors_subprocedure.md
Parent Task: aitasks/t1071_shadow_error_diagnosis_and_learn_skill_command.md
Sibling Tasks: aitasks/t1071/t1071_2_learn_skill_standalone_command.md
Archived Sibling Plans: aiplans/archived/p1071/p1071_*_*.md
Worktree: aiwork/t1071_1_shadow_diagnose_errors_subprocedure
Branch: aitask/t1071_1_shadow_diagnose_errors_subprocedure
Base branch: main
---

# Plan — Capability A: shadow error-diagnosis sub-procedure

Give the shadow agent a sub-procedure that detects workflow/helper **errors** in
the followed agent's captured screen, **marks** them as a forwardable concern
block, and **offers** to launch `/aitask-explore` scoped to the offending
skill/helper. Detect → mark → **offer** (user confirms; never auto-launch).
**Claude-only** — no cross-agent port (shadow `plan-*.md` sub-procedures live
only in the Claude tree; Codex/OpenCode shadow are thin wrappers redirecting
there).

## Exploration summary (already done — do not re-derive)

- `monitor/prompt_patterns.py` has **no** reusable error/retry detection — it
  matches only *awaiting-input* prompts, and `PaneSnapshot` carries no error
  field. So this flow performs its **own** text analysis of the captured screen.
- The concern-block machinery already exists (t1037): the
  `===AITASK-CONCERNS===` … `===END-CONCERNS===` format
  (`aidocs/framework/shadow_concern_format.md`) is emitted by `plan-challenge.md`,
  parsed by `.aitask-scripts/monitor/concern_parser.py`, and consumed by the
  minimonitor concern picker. **No minimonitor / parser changes needed** — this
  capability just emits the same block.
- Guardrail: read-only w.r.t. the *followed* pane. Running `/aitask-explore` is
  guardrail-safe because the shadow is a full code agent acting in *its own* pane.

## Files

| File | Change |
|------|--------|
| `.claude/skills/aitask-shadow/plan-diagnose-errors.md` | **NEW** sub-procedure |
| `.claude/skills/aitask-shadow/SKILL.md` | Add 1 Step 3 routing entry + 1 Step 1 proactive-trigger clause |
| `aidocs/framework/shadow_agent.md` | Add the new capability to the Step 3 list / sub-procedure bullets |

## Step-by-step

### 1. Author `plan-diagnose-errors.md`

Model the structure on `plan-challenge.md` (header + Inputs + advisory-only note +
numbered methodology + concern-block output rules). Sections:

- **Header + purpose:** "A sub-procedure of the shadow skill. Use it when the
  followed agent's captured screen shows tool-call errors or retries — signs of a
  bug in a workflow skill definition or a helper bash script it calls."
- **Inputs:** the captured screen (shadow Step 1); refetch if stale. No plan file
  needed (unlike the plan-* peers).
- **Advisory-only note:** never drive the followed pane; the offered explore runs
  in the shadow's OWN pane.
- **Methodology (numbered):**
  1. Read the captured screen (refetch via `aitask_shadow_capture.sh` if stale).
  2. Scan for error/retry signals:
     - `InputValidationError`
     - `Tool error:`
     - `Traceback (most recent call last):`
     - bash `error:` / stderr lines (e.g. `<script>.sh: line N:`, `command not found`)
     - **repeated identical commands** (retry loops — the same tool call / bash
       line appearing 2+ times in succession).
  3. Attribute each error cluster to the likely skill/helper: which workflow skill
     or `aitask_*.sh` helper the followed agent was running, and (where inferable)
     whether it's a wrong-parameter call vs a bug in the script itself.
  4. Emit the marked concern block — one concern per error cluster — following the
     `shadow_concern_format.md` rules **verbatim** (copy from `plan-challenge.md`):
     leading `- ` mandatory on every concern line; `- [priority | region] body`;
     `priority` ∈ {high, medium, low}; `region` names the offending skill/helper;
     `body` carries the full framing (the error, the likely cause, the file to
     look at); one logical line per concern (let the terminal soft-wrap, no literal
     mid-concern newline); order by severity; **always emit the closing
     `===END-CONCERNS===` fence**; emit the block only when ≥1 signal was found.
  5. **Offer** explore-to-fix (AskUserQuestion): "Launch `/aitask-explore`
     pre-seeded with `<skill/helper paths>` and the captured error excerpt to turn
     this into a fix-task?" Options: Yes (launch) / No (just keep the marked
     concerns). Only on explicit Yes do you run `/aitask-explore` (or batch task
     creation) in the shadow's own pane, seeding it with the buggy paths + error
     excerpt. Reinforce: this never touches the followed pane.

### 2. Wire `SKILL.md`

- **Step 3 — Structured analyses block:** add one bullet:
  > - **Diagnose skill/helper errors in the followed agent** (`InputValidationError`,
  >   tracebacks, bash stderr, retry loops) → read and follow `plan-diagnose-errors.md`.
- **Step 1 — proactive-surface trigger:** extend the existing "Proactively
  surface a relevant capability (after every capture)" paragraph with a clause:
  when a fresh capture shows error/retry signals, offer this capability unprompted
  (suggestion-only, never auto-run).
- **Do NOT** touch the Step 0 greeting — it derives from Step 3 automatically
  (single source of truth; the maintainer note in SKILL.md forbids a second copy).

### 3. Update `aidocs/framework/shadow_agent.md`

Add the new sub-procedure to the Step 3 capability list / `plan-*.md` bullet list
so the doc stays current with the skill source.

## Verification

- `./.aitask-scripts/aitask_skill_verify.sh` passes (static skill; confirms no
  surface breakage).
- Grep-confirm: greeting still has no hardcoded capability list; the new Step 3
  routing line + Step 1 trigger clause are present and well-formed.
- **Behavioral (manual — candidate for the aggregate manual-verification
  sibling):** feed `aitask_shadow_capture.sh -` a fixture screen containing an
  `InputValidationError` / traceback / retry loop; confirm the shadow emits a
  concern block that round-trips through `concern_parser.py` (≥1 parsed concern,
  closing fence present) and offers explore-to-fix without driving the followed
  pane.

## Notes for sibling tasks (t1071_2)

- Both A and B add a routing line to `aitask-shadow/SKILL.md` Step 3. This task
  (A) lands first; t1071_2 picks up the file with A's edit already present, so it
  appends its own line independently — no conflict expected.
- The greeting-derives-from-Step-3 invariant (no hardcoded capability list) must
  be preserved by both children.

## Post-implementation

Follow shared workflow **Step 9 (Post-Implementation)** for cleanup, gate
verification, archival, and merge.
