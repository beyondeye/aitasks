---
Task: t1071_1_shadow_diagnose_errors_subprocedure.md
Parent Task: aitasks/t1071_shadow_error_diagnosis_and_learn_skill_command.md
Sibling Tasks: aitasks/t1071/t1071_2_learn_skill_standalone_command.md
Archived Sibling Plans: aiplans/archived/p1071/p1071_*_*.md
Worktree: aiwork/t1071_1_shadow_diagnose_errors_subprocedure
Branch: aitask/t1071_1_shadow_diagnose_errors_subprocedure
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-29 13:58
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
| `.claude/skills/aitask-shadow/SKILL.md` | Add 1 Step 3 routing entry (**on-request only — no Step 1 proactive trigger**) |
| `aidocs/framework/shadow_agent.md` | Add ONE capability-level bullet (no signal-list duplication) |

## Design decisions (revised after plan review)

- **On-request only — not proactive.** The capability is reached **only** when the
  user asks the shadow to diagnose what is going wrong (Step 3 routing). It is
  **deliberately not** added to Step 1's proactive-surface behavior, so the shadow
  never emits unsolicited concern blocks about errors on screen. (This supersedes
  the original task outline's "Step 1 proactive-surface trigger" — the t1071_1 AC
  was updated to match.)
- **User chooses which concerns to act on.** When triggered, the shadow presents
  the candidate concerns (concern-block format, like plan review) and the user
  selects which — if any — actually warrant a fix-task. The shadow does not decide
  for them.
- **One offer behavior (v1).** For a chosen concern, the shadow offers
  `/aitask-explore` seeded with a prompt only. The "or batch task creation" branch
  is dropped from v1 (a possible later enhancement) — fewer branches, easier
  verification.

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
  4. **Present the candidate concerns and emit the marked concern block** — one
     concern per error cluster. First show the user a short human-readable list
     (like plan review), then append the machine-parseable block following the
     `shadow_concern_format.md` rules **verbatim** (copy from `plan-challenge.md`):
     leading `- ` mandatory on every concern line; `- [priority | region] body`;
     `priority` ∈ {high, medium, low}; `region` names the offending skill/helper;
     `body` carries the full framing (the error, the likely cause, the file to
     look at); one logical line per concern (let the terminal soft-wrap, no literal
     mid-concern newline); order by severity; **always emit the closing
     `===END-CONCERNS===` fence**; emit the block only when ≥1 signal was found.
     If no signal is found, say so plainly and stop — do not manufacture concerns.
  5. **Let the user choose which concerns (if any) to act on, then offer ONE
     action.** Ask the user which of the presented concerns actually warrant a
     fix-task (AskUserQuestion, multiSelect; include a "none" path). For each
     chosen concern, **offer** to launch `/aitask-explore` seeded with a prompt
     naming that concern's skill/helper path(s) + the captured error excerpt. v1
     scope: **`/aitask-explore` with a seed prompt only** — no batch-task-creation
     branch. Only on explicit confirmation do you launch it, in the shadow's OWN
     pane. Never auto-launch; never drive the followed pane.

### 2. Wire `SKILL.md`

- **Step 3 — Structured analyses block:** add one bullet:
  > - **Diagnose skill/helper errors in the followed agent** (`InputValidationError`,
  >   tracebacks, bash stderr, retry loops) → read and follow `plan-diagnose-errors.md`.
- **Step 1 — leave unchanged.** Do **not** add an error/retry proactive trigger.
  The capability is on-request only (see Design decisions). Step 1's existing
  general proactive-surface behavior for other capabilities is untouched.
- **Do NOT** touch the Step 0 greeting — it derives from Step 3 automatically
  (single source of truth; the maintainer note in SKILL.md forbids a second copy).

### 3. Update `aidocs/framework/shadow_agent.md`

Add **one capability-level bullet** for the new sub-procedure to the Step 3
`plan-*.md` list (matching the one-line style of its peers, e.g.
"`plan-diagnose-errors.md` — diagnose skill/helper errors the followed agent hit
and offer to spin a fix-task"). **Do NOT** copy the detailed signal list into the
doc — it lives only in `plan-diagnose-errors.md`, so the doc cannot go stale when
the signals change.

## Verification

- `./.aitask-scripts/aitask_skill_verify.sh` passes (static skill; confirms no
  surface breakage).
- Grep-confirm: greeting still has no hardcoded capability list; the new Step 3
  routing line + Step 1 trigger clause are present and well-formed.
- **Behavioral — positive fixture (manual):** feed `aitask_shadow_capture.sh -` a
  fixture screen containing an `InputValidationError` / traceback / retry loop;
  confirm the shadow emits a concern block that round-trips through
  `concern_parser.py` (≥1 parsed concern, closing fence present), lets the user
  pick which concerns to act on, and offers `/aitask-explore` (seed prompt only)
  without driving the followed pane.
- **Behavioral — negative-control fixture (manual):** feed at least one fixture
  that contains benign error-shaped text that must **not** trigger a concern block
  — e.g. a passing test run that prints the word `error:` in narrative output, an
  *intentionally* failing test the agent is expected to see, or a pasted traceback
  excerpt being discussed (not a live crash). Confirm the shadow recognizes these
  as non-actionable and emits **no** concern block. This guards the false-positive
  surface that the positive-fixture/parser test cannot catch.

## Notes for sibling tasks (t1071_2)

- Both A and B add a routing line to `aitask-shadow/SKILL.md` Step 3. This task
  (A) lands first; t1071_2 picks up the file with A's edit already present, so it
  appends its own line independently — no conflict expected.
- The greeting-derives-from-Step-3 invariant (no hardcoded capability list) must
  be preserved by both children.

## Risk

### Code-health risk: low
- None identified. The change is markdown-only and additive (one new `plan-*.md`
  sub-procedure + two additive `SKILL.md` clauses + one doc update); it reuses the
  existing `===AITASK-CONCERNS===` format and `concern_parser.py` verbatim, so no
  code path or parser is touched. `aitask_skill_verify.sh` passes trivially.

### Goal-achievement risk: medium
- The error-signal detection and skill/helper attribution are heuristic
  agent-judgment at runtime, not deterministic code — false positives/negatives
  are possible (e.g. benign retries flagged, or a real error mis-attributed). ·
  severity: medium · → mitigation: on-request-only invocation + user picks which
  concerns to act on + the negative-control fixture in Verification.
  Bounded further: the capability is advisory-only and user-confirmed, never
  proactive, and the negative fixture directly exercises the false-positive case.

## Post-implementation

Follow shared workflow **Step 9 (Post-Implementation)** for cleanup, gate
verification, archival, and merge.
