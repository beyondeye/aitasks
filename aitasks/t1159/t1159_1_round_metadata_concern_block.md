---
priority: high
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [shadow, aitask_monitormini]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1159
implemented_with: claudecode/fable5
created_at: 2026-08-11 15:32
updated_at: 2026-08-11 17:09
---

Add round metadata to the shadow concern block: grammar, parser accessor, producer wording, auto-offer dedup lift, and picker display. First child of t1159 (shadow review-loop automation); the full parent design is in `aiplans/p1159_shadow_review_loop_automation.md` and the child plan is `aiplans/p1159/p1159_1_round_metadata_concern_block.md`.

## Context

The concern block (`===AITASK-CONCERNS===` … `===END-CONCERNS===`) carries no round number or review time. Consequences: minimonitor's auto-offer dedups on the parsed payload (`build_clipboard_payload`), so a round-2 review with identical concerns produces no new hint; the picker cannot show which round produced the block; and t1448 (`depends: [1159, 1420]`) has no freshness key. This child adds the metadata end-to-end. The auto-recheck loop (t1159_2) and spin-off arm (t1159_3) both consume it.

## Key decisions (user-confirmed at parent planning, 2026-08-11 — do not reopen)

- Header line INSIDE the fences, immediately after the opening fence: `Round: <N> @ <ISO-8601-UTC-with-seconds>Z` (e.g. `Round: 2 @ 2026-08-11T14:03:27Z`). Seconds resolution required (same-minute shadow restart must not reproduce a `(round, reviewed_at)` pair).
- NEVER widen the `[priority | region]` marker bracket (t1167 split-marker drop hazard).
- Round is mechanically anchored where possible: producers honor an externally supplied round number when the recheck request names one ("recheck round N", sent by t1159_2), self-count only for the first review / manual free-text rechecks; timestamp sourced via `date -u +%Y-%m-%dT%H:%M:%SZ` (shell), never estimated.
- Clean reviews (zero concerns, or all suppressed) emit a METADATA-ONLY block — fences with only the round header between them — so round numbering advances on clean rounds too. `has_concern_block` stays False for such a block (no items ⇒ no auto-offer), which is correct.
- Rejection suppression stays task-scoped (t1427 store untouched).

## Key files to modify

- `.aitask-scripts/monitor/concern_parser.py` — new `BlockMeta(round: int, reviewed_at: str)` NamedTuple + `parse_block_meta(text) -> BlockMeta | None`. Use `_last_block_region(text, require_close=False)` (line 235; same forgiving region as `parse_concerns` at 410-416, so meta and concerns always describe the same block). Only the FIRST non-blank line of the region is consulted; a `Round:` line anywhere later is body text by the item grammar. `reviewed_at` verbatim, fail-open (parser stays pure). Docstring must carry the t1448 consumer contract: the freshness key is the `(round, reviewed_at)` PAIR — round alone is not unique (restarted shadow starts at 1 again).
- `.claude/skills/aitask-shadow/plan-challenge.md`, `impl-challenge.md`, `plan-assumptions.md`, `plan-diagnose-errors.md` — each gets the round-header rule at BOTH rule sites (bolded emit paragraph near the fence-emission instruction + rules-list bullet), mirroring how the rejection-suppression rule is inlined twice per producer (see plan-challenge.md:61-67 and 106-117 for the pattern). Both sites must state: header first line after opening fence, BEFORE the first `- [` marker (after any item it is body-joined — corruption), never itself beginning `- [`; honor an externally-named round; shell-sourced UTC timestamp; zero-concern reviews emit the metadata-only block. Prepend `Round: 1 @ …` to each producer's example block. Examples must NEVER gain the fences (t1123 `contains_any_concern_block` authoring guard).
- `.aitask-scripts/monitor/minimonitor_app.py:2352-2355` — dedup key becomes `f"round={meta.round}@{meta.reviewed_at}\n{payload}"` when meta present, bare payload otherwise (byte-identical back-compat for old blocks). Toast text gains `(round N)` when meta present. `action_pick_concerns` (line 2199-2272) passes `block_meta=parse_block_meta(text)` into `ConcernPickerModal`.
- `.aitask-scripts/monitor/monitor_shared.py` — `ConcernPickerModal` gains optional `block_meta=None` keyword; `_context_line()` renders `· round 2, 14:03:27Z` (display-only).
- `.claude/skills/aitask-shadow/concern-format.md` — new "Round header" section after "Fences": grammar, placement hazard, back-compat (absent ⇒ `parse_block_meta` returns None, all else unchanged), metadata-only clean-round block, the three consumer roles (display; dedup lift; t1448 freshness key = the pair), and the note that the header intentionally changes `concern_block_signature` (round bump re-hashes the monitor's freshness badge).

## Reference files for patterns

- `concern_parser.py:91-92` fences; `:104-106` `_ITEM`; `:175-196` `Concern`; `:352` the non-marker-line-before-first-item drop (the parser-safety basis for the header slot); `:453` `has_concern_block` strictness; `:493` `concern_block_signature`.
- The disposition trailer (concern-format.md "derived fields", parser `_TRAILER_SPAN` at 157-167) is the precedent for backward-compatible metadata addition.
- `tests/test_concern_parser.py::TestProducerRejectionSuppressionRule` (~line 950) — the pattern for producer-text drift guards.

## Implementation plan

1. Parser: add `BlockMeta` + `parse_block_meta` + module docstring updates.
2. Producers: both sites x 4 files + example headers.
3. Dedup lift + toast + picker display.
4. concern-format.md section.
5. Tests (below).

Producers are plain shared `.md` files — NO goldens regeneration, do NOT touch `SKILL.md.j2`. If any `.j2` IS touched, run `./.aitask-scripts/aitask_skill_verify.sh` and regenerate goldens in the same commit.

## Verification

- `tests/test_concern_parser.py` (extend): parse_block_meta present/absent/no-timestamp; header-after-item → meta None AND line body-joined (pin the corruption mode); last-block-wins; metadata-only block (meta readable, `has_concern_block` False, `parse_concerns` empty); byte-identical entry-point results with/without header; `concern_block_signature` changes on round bump alone; new `TestProducerRoundHeaderRule` (both sites x 4 producers + example headers + zero-concern wording present).
- `tests/test_minimonitor_concern_action.py` (extend): round 1 then round 2 with identical concerns → two notifies; identical round → one.
- Run: `bash tests/run_all_python_tests.sh` — read only the final stderr verdict line.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-11T14:09:59Z status=pass attempt=1 type=human
