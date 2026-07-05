---
Task: t1123_fix_failed_verification_t1121_item1.md
Worktree: (none — current branch, profile 'fast')
Branch: (current)
Base branch: main
---

# t1123 — Fix picker forwarding the doc's placeholder concern block

## Context

t1121 manual-verification item #1 (verifying t1119) **failed**: launching a
completed task's agent + shadow, asking "review the implementation", then
pressing minimonitor's `c` picker forwarded the **doc's placeholder example**
concerns instead of the agent's real ones.

t1119 CR3 already root-caused this class of bug and fixed **4** shadow
sub-procedure docs (`impl-challenge.md`, `plan-challenge.md`,
`plan-assumptions.md`, `plan-diagnose-errors.md`) by presenting the concern
format *without* a contiguous `open → items → close` block, and added a guard
test `TestShadowDocsNotParserLive`. But it left **one** doc — `concern-format.md`
— with its contiguous example block intact, calling it "only *accidentally*
safe."

**Reproduced root cause (deterministic):**
- `concern-format.md` lines 17–22 still embed a full literal block:
  `===AITASK-CONCERNS===` → two `- [priority | region] body` items →
  `===END-CONCERNS===`.
- It is only "safe" because a **later** inline mention on line 27
  (`- Opening: \`===AITASK-CONCERNS===\` — Closing: \`===END-CONCERNS===\`.`)
  becomes the *last* fence, and the runtime parser scopes to the **last** fence
  only (`rfind` in `concern_parser._last_block_region`). That masking is a
  **fragile invariant**: a live shadow-pane capture is a bounded *window*
  (`aitask_shadow_capture.sh`, default 200 lines). If lines 17–22 are rendered
  or quoted into the pane while the masking line 27 falls outside that window,
  `parse_concerns` (the `c`-picker path, `minimonitor_app.py:1329`) isolates the
  block and forwards the two placeholder concerns.
- The existing guard test misses it because it calls `has_concern_block`
  (strict, last-fence-only) — the same last-block blind spot as the runtime.

Verified by scanning every `open → next-close` region (not just the last) for
item lines: **only `concern-format.md` flags** (line 17, 2 items). The other 4
CR3-fixed docs are clean.

## Fix (two structural parts + a negative-control-backed guard)

### 1. `concern-format.md` — remove the contiguous example block

Restructure the `## The format` section (lines 15–23) to present the format the
same safe way the 4 sibling docs already do: **name the sentinels inline in
prose**, then show the `- [priority | region] body` item lines in a code block
**without** the surrounding fences. No open→items→close region remains anywhere
in the file (the only other fence, line 27, already opens-and-closes on one
line). Content/meaning preserved — this is a presentation change.

Replacement for the fenced block currently at lines 16–23:

```
The block is bracketed by two sentinel lines — an opening `===AITASK-CONCERNS===`
line and a closing `===END-CONCERNS===` line (those two exact literals) — with one
concern per line between them. The concern lines themselves look like:

    ``` (real triple-backtick opening)
    - [high | Step 7 ownership guard] The guard re-runs aitask_pick_own.sh which
      double-commits when the lock was already held.
    - [medium | parser module] Multi-block accumulation is undefined when the
      shadow re-issues concerns.
    ``` (real triple-backtick closing)
```

(The `### Fences` section immediately below already documents the exact opening
and closing literals, so nothing is lost.)

### 2. `concern_parser.py` — add an authoring-safety helper (grammar reuse)

The runtime functions (`parse_concerns`, `has_concern_block`) deliberately scope
to the *last* fence. Add a small, additive helper that walks **every** block, so
the doc guard reuses the canonical fence/item grammar instead of reimplementing
the regex in the test:

- `_iter_block_regions(text)` — generator yielding the region after **each**
  opening fence up to its next close (or EOF).
- `contains_any_concern_block(text) -> bool` — `True` if *any* block (not just
  the newest) encloses ≥1 concern. Docstring cites t1123 and states this is the
  stricter *authoring* check (a partial pane capture can isolate any embedded
  block, not only the last).

No change to existing runtime behavior — these are new, unused-by-runtime
functions.

### 3. `tests/test_concern_parser.py` — strengthen the guard + negative control

In `TestShadowDocsNotParserLive`:
- Keep the existing `test_no_doc_is_parser_live` (documents the runtime
  last-block property).
- Add `test_no_doc_embeds_any_contiguous_block` — scans every
  `.claude/skills/aitask-shadow/*.md` with `contains_any_concern_block` and
  asserts none embeds a contiguous block anywhere. This is the check that
  actually catches the reproduced hazard (and would have caught
  `concern-format.md` pre-fix).
- Add `test_guard_catches_masked_embedded_block` — **negative control**:
  construct a doc that embeds a real block *followed by* a trailing inline
  sentinel mention (exactly the `concern-format.md` masking shape); assert the
  old `has_concern_block` returns `False` (reproduces the blind spot) while
  `contains_any_concern_block` returns `True` (proves the new guard closes it).

Update the class docstring to describe the two layers.

## Out of scope (considered)

- **`concern_parser.py`'s own docstring** (lines 19–23) also shows a contiguous
  block, but it is Python source the shadow never reads at runtime and the guard
  does not scan it — not a live surface. Left unchanged to keep scope tight.
- **Parser/minimonitor logic** unchanged — the runtime "last block wins" design
  is correct (the agent emits its real block last); the defect is doc content,
  fixed at the source per the structural approach CR3 established.
- **Cross-agent port:** none. Shadow sub-procedure docs live only in the Claude
  tree (`.agents/`/`.opencode/` are SKILL.md wrappers) — see memory
  *Shadow skill = wrapper, no cross-agent port*.

## Risk

### Code-health risk: low
- Doc-presentation change + two additive parser helpers + tests; no runtime
  logic path is modified · severity: low · → mitigation: TBD

### Goal-achievement risk: low
- The fix removes the exact reproduced hazard and the negative-control test
  proves the strengthened guard catches the masked-block shape the old guard
  missed · severity: low · → mitigation: TBD

`risk_mitigations_planned = false` (both dimensions low; no before/after
follow-up tasks warranted — covered by the in-task guard + negative-control
test).

## Verification

1. **Reproduce-then-confirm-fixed** — the scan that currently flags
   `concern-format.md` must return clean after the edit:
   ```bash
   python3 - <<'PY'
   import sys, glob, os
   sys.path.insert(0, '.aitask-scripts/monitor')
   from concern_parser import contains_any_concern_block
   bad = [os.path.basename(p) for p in glob.glob('.claude/skills/aitask-shadow/*.md')
          if contains_any_concern_block(open(p).read())]
   print('offenders:', bad)  # must be []
   PY
   ```
2. **Parser tests green (incl. new guard + negative control):**
   ```bash
   python3 tests/test_concern_parser.py
   ```
3. **Balanced code fences** in the edited `concern-format.md`:
   ```bash
   n=$(grep -cE '^```' .claude/skills/aitask-shadow/concern-format.md); echo $((n % 2))  # 0
   ```
4. **No sentinel regression** — exactly one self-closed inline mention pair
   remains, no contiguous block:
   ```bash
   grep -n 'AITASK-CONCERNS\|END-CONCERNS' .claude/skills/aitask-shadow/concern-format.md
   ```

## Post-Implementation

Follow **Step 9** of the shared task-workflow: user review → commit (code/doc
files via `git`; the plan via `./ait git`) → gate run (`risk_evaluated`) →
archive t1123. A fresh live manual re-verification of the t1121 item is the
real end-to-end proof but requires a live agent+shadow; offer it as a follow-up
manual-verification task at Step 8c.

## Final Implementation Notes

- **Actual work done:** Restructured `.claude/skills/aitask-shadow/concern-format.md`
  `## The format` section to present the format with **inline-named sentinels +
  a separate item-only code block** (no contiguous `open → items → close`
  block), matching the 4 sibling docs t1119 CR3 already fixed. Added
  `_iter_block_regions` + `contains_any_concern_block` to
  `.aitask-scripts/monitor/concern_parser.py` (walk *every* block, not just the
  last). Strengthened `tests/test_concern_parser.py`
  `TestShadowDocsNotParserLive` with `test_no_doc_embeds_any_contiguous_block`
  and a negative-control `test_guard_catches_masked_embedded_block`.
- **Deviations from plan:** None. Implemented exactly as planned.
- **Issues encountered:** None. The root cause was reproduced deterministically
  before coding (the every-block scan flagged only `concern-format.md`, line 17),
  and the same scan returns clean post-fix.
- **Key decisions:** Fixed at the doc source (structural), not the parser/picker
  — the runtime "last block wins" design is correct (the agent emits its real
  block last); the defect was doc content. Put the every-block detection in the
  parser module (grammar reuse) rather than reimplementing the fence/item regex
  in the test. The negative control encodes the exact masked-block shape that
  fooled the old last-fence guard, so a future regression of the guard itself is
  caught.
- **Upstream defects identified:** None. (`concern_parser.py`'s own module
  docstring also shows a contiguous example block, but it is Python source the
  shadow never reads at runtime and the guard does not scan it — not a live
  surface; deliberately left unchanged.)
