---
Task: t1159_1_round_metadata_concern_block.md
Parent Task: aitasks/t1159_shadow_review_loop_automation.md
Sibling Tasks: aitasks/t1159/t1159_2_auto_recheck_loop.md, aitasks/t1159/t1159_3_spinoff_triage_arm.md, aitasks/t1159/t1159_4_docs_and_integration.md
Archived Sibling Plans: aiplans/archived/p1159/p1159_*_*.md
Worktree: . (current directory — profile 'fast', current branch)
Branch: main
Base branch: main
Output branch: main
---

# Plan — t1159_1: Round metadata in the concern block

Parent design: `aiplans/p1159_shadow_review_loop_automation.md` (pinned decisions restated below — do not reopen).

## Pinned decisions

- Header line **inside** the fences, immediately after the opening fence, before the first item: `Round: <N> @ <ISO-8601-UTC-with-seconds>Z` (e.g. `Round: 2 @ 2026-08-11T14:03:27Z`). Seconds resolution required.
- Never widen the `[priority | region]` marker bracket (t1167 hazard).
- Producers honor an externally supplied round ("recheck round N" in the request — sent by t1159_2's loop), self-count only for first review / manual free-text rechecks; timestamps shell-sourced (`date -u +%Y-%m-%dT%H:%M:%SZ`), never estimated.
- Clean reviews (zero concerns, or all suppressed) emit a **metadata-only block** (fences + round header only) so round numbering advances on clean rounds. `has_concern_block` stays False for it (no items ⇒ no auto-offer) — correct by design.
- Rejection suppression stays task-scoped (t1427 store untouched).

## Steps

1. **Parser accessor** — `.aitask-scripts/monitor/concern_parser.py`:
   ```python
   class BlockMeta(NamedTuple):
       round: int          # 1-based round the producer emitted
       reviewed_at: str    # verbatim timestamp after '@' ("" when omitted)

   _META_LINE = re.compile(r"^\s*Round:\s*(?P<round>\d+)(?:\s*@\s*(?P<at>.*\S))?\s*$")

   def parse_block_meta(capture_text: str) -> BlockMeta | None:
       ...
   ```
   - Use `_last_block_region(capture_text, require_close=False)` (line 235) — same forgiving region as `parse_concerns` (410-416), so meta and concerns always describe the same (newest) block.
   - Consult only the **first non-blank line** of the region; if it doesn't match `_META_LINE`, return `None` (a `Round:` line later is body text by the item grammar).
   - Fail-open, pure; `reviewed_at` verbatim, not validated.
   - Docstring carries the t1448 consumer contract: freshness key is the `(round, reviewed_at)` **pair** — round alone is not unique (a restarted shadow starts at 1 again).
   - Parser-safety basis (document in module docstring near the grammar notes): `_scan_items` line 352 drops a non-marker line before the first item (`items` empty ⇒ no continuation join), so `parse_concerns` / `has_concern_block` / `unrecovered_markers` are unaffected by the header. It **deliberately** changes `concern_block_signature` and `block_region`.

2. **Producers** — both rule sites in each of `.claude/skills/aitask-shadow/plan-challenge.md`, `impl-challenge.md`, `plan-assumptions.md`, `plan-diagnose-errors.md` (mirror the rejection-suppression inlining pattern, e.g. plan-challenge.md:61-67 + 106-117; adjust the 3-space step indentation of the three plan-* files):
   - **Site A (emit paragraph, near the fence-emission instruction):**
     > **Emit a round header as the first line inside the block.** Immediately after the opening fence — before the first concern line — emit exactly one line of the form `Round: <N> @ <timestamp>` (e.g. `Round: 2 @ 2026-08-11T14:03:27Z`). If the request that triggered this review names a round ("recheck round N"), use that N. Otherwise `<N>` starts at 1 for the first review you run in this conversation and increments by one each time you re-run a review in this same conversation (any review sub-procedure counts; a fresh shadow session starts again at 1 — the timestamp disambiguates). Obtain `<timestamp>` by running `date -u +%Y-%m-%dT%H:%M:%SZ` — do not estimate it. **If this review found no concerns (or suppression removed them all), still emit the block**: the fences with only the round header between them — this is the machine-readable record that the round completed clean.
   - **Site B (rules-list bullet):**
     > - **Round header.** The first line after the opening fence is `Round: <N> @ <timestamp>` and nothing else. It MUST come **before** the first `- [` marker — placed after any item it is absorbed into that item's body — and it must never itself begin with `- [`. A zero-concern review still emits the fences with only this header between them. Minimonitor reads it to show the round, to re-offer the picker on a repeat round, and to judge concern freshness.
   - Prepend `Round: 1 @ 2026-08-11T14:03:27Z` as the first line of each producer's example block. **Examples must never gain the fences** (t1123 `contains_any_concern_block` authoring guard).
   - Producers are plain shared `.md` — **no goldens regeneration**; do **not** touch `SKILL.md.j2`.

3. **Dedup lift** — `.aitask-scripts/monitor/minimonitor_app.py:2352-2355`:
   ```python
   meta = parse_block_meta(text)
   payload = build_clipboard_payload(concerns)
   dedup_key = (f"round={meta.round}@{meta.reviewed_at}\n{payload}"
                if meta else payload)
   ```
   No meta ⇒ byte-identical to today (back-compat with old blocks). Toast appends `(round {meta.round})` when meta present.

4. **Picker display** — `action_pick_concerns` (minimonitor_app.py:2199-2272) passes `block_meta=parse_block_meta(text)` to `ConcernPickerModal`; the modal (monitor_shared.py:2357-2660) gains optional `block_meta=None` keyword; `_context_line()` renders `· round 2, 14:03:27Z` (display-only — no `Concern.body` read, no AST-guard registration needed for this surface).

5. **`concern-format.md`** — new "Round header" section after "Fences": grammar, placement rule + hazard (after an item ⇒ body-joined), back-compat (absent ⇒ `parse_block_meta` → None, everything else unchanged), metadata-only clean-round block (and that `has_concern_block` stays False for it), the three consumer roles (display; dedup lift; t1448 freshness key = the pair), signature note. Update the parser-entry-points list to include `parse_block_meta` / `BlockMeta`.

## Verification

- `tests/test_concern_parser.py` (extend):
  - `parse_block_meta`: present / absent → None / no `@` timestamp → `reviewed_at == ""` / header after first item → None **and** the line body-joined into the prior concern (pin the corruption mode) / last-block-wins.
  - Metadata-only block: meta readable; `has_concern_block` False; `parse_concerns` `[]`; `unrecovered_markers` `[]`.
  - Byte-identical results of `parse_concerns` / `has_concern_block` / `unrecovered_markers` with and without the header on the same concerns.
  - `concern_block_signature` changes when only the round bumps.
  - New `TestProducerRoundHeaderRule` (mirror `TestProducerRejectionSuppressionRule`, ~line 950): each of the 4 producers carries both sites (grep both the emit paragraph marker and the rules bullet), each example block starts with a `Round:` line, and the zero-concern wording is present at both sites.
- `tests/test_minimonitor_concern_action.py` (extend): identical concerns round 1 → notify; round 2 → second notify (dedup lifted); identical round → single notify.
- `bash tests/run_all_python_tests.sh` — read only the final stderr verdict line.
- Reference **Step 9 (Post-Implementation)** of the task-workflow skill for cleanup, archival, and merge.
