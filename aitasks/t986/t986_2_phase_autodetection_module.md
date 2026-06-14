---
priority: medium
effort: medium
depends: [t986_1]
issue_type: feature
status: Implementing
labels: [gates, python, aitask_monitormini]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-14 16:03
updated_at: 2026-06-14 17:25
---

## Context

Child of t986 (shadow agent). The shadow must know **which workflow phase** the
shadowed agent is in (planning / risk-eval / implementation / review / done /
archived / awaiting-AskUserQuestion) so it can tailor its help. Decision:
**ledger-first, text fallback.**

**True deps:** none — this is a pure headless module and can be implemented in
parallel with t986_1 (the sequential sibling dependency on t986_1 only orders it;
nothing in the code requires the substrate). **Coordinates t635_8 / t635_1**:
the gate ledger parser is the source of truth; import it, do not fork it.

## Key Files to Modify / Create

- **Create** `.aitask-scripts/monitor/phase_detect.py` (pure, no Textual import).
  Public fn e.g. `detect_phase(task_file: str | None, captured_text: str) -> str`
  (plus a small enum/constants for phase names).
- **Reuse (import, don't fork)** `.aitask-scripts/lib/gate_ledger.py`:
  `derive_status(text)` / `parse_gate_runs(text)`. Per the module docstring,
  t635_8 (shared TUI gate-ledger parser) EXTENDS `gate_ledger.py` — TUIs must
  import from there. Coordinate with t635_8 so both consume the same API.

## Reference Files for Patterns

- Gate names recorded by the workflow (see `task-workflow/gate-recording.md` and
  SKILL.md Steps 7/8/9): `plan_approved`, `risk_evaluated`, `review_approved`,
  `build_verified`, `merge_approved`. The ledger lives as a `## Gate Runs`
  section **in the task file**.
- Terminal markers for the text fallback (from `task-workflow/SKILL.md`):
  - Step 8 review: "Implementation complete. Please review and test the changes."
  - Step 5: "Which branch should the new task branch be based on?"
  - Step 9: "Proceed with merge of code changes to main branch?"
  - AskUserQuestion shape: a question line + a header + enumerated options (see
    `monitor/prompt_patterns.py` for existing prompt-detection patterns to reuse).
- `monitor/prompt_patterns.py` — existing awaiting-input detection; reuse/extend
  for the AskUserQuestion shape rather than writing a new scanner.

## Implementation Plan

1. **Ledger-first:** given the source task file, read its `## Gate Runs` via
   `gate_ledger.derive_status()`; map the set of passed gates → phase
   (e.g. no gates → planning; `plan_approved` only → implementing;
   `review_approved` → review; `merge_approved`/archived → done).
2. **Text fallback:** when the ledger is absent/insufficient (or no task file is
   resolvable), scan `captured_text` for the phase markers above and the
   AskUserQuestion shape; return the most specific phase. An on-screen
   AskUserQuestion should win (it is the live, actionable state).
3. Keep the module importable headless (used by the shadow skill helpers and,
   potentially, by monitor). Define precedence clearly: live-prompt > ledger >
   text-history.

## Verification Steps

- `bash tests/test_phase_detect.sh` (or a Python unittest) with fixtures:
  - task files at various gate states → expected phase (ledger path).
  - captured-transcript fixtures (review prompt, merge prompt, AskUserQuestion,
    plain planning) → expected phase (text path).
  - ledger-vs-text precedence (live AskUserQuestion overrides ledger phase).
- Confirm no fork of gate-ledger logic: the module imports
  `derive_status`/`parse_gate_runs` from `gate_ledger.py`.
