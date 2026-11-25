---
Task: t2331_fix_concern_picker_resolved_color_assertions.md
Base branch: main
Output branch: main
---

# t2331 — Make the concern-picker resolved-colour tests hermetic against `NO_COLOR`

## Context

Two assertions in `tests/test_concern_picker_modal.py` (`ConcernMagnitudeRampTests`)
failed in t2295's full-suite run with `'#363636' != '#ff0000'`. The task asks
whether the styling or the test expectations are wrong.

**Diagnosis (reproduced):** it is neither. The test isn't sealed off from the
process environment.

- In isolation both tests pass: the class 13/13 and the whole file 224/224.
- With `NO_COLOR=1` exported, **exactly these two** fail with **exactly the
  reported values** (`2 failed, 11 passed`, lines 3704 and 3781):
  `NO_COLOR=1 python -m pytest tests/test_concern_picker_modal.py -k ConcernMagnitudeRampTests`.
- Mechanism: Textual 8.2.7's `App.__init__` (`textual/app.py:614`) reads
  `NO_COLOR` from `os.environ` at construction and adds the `Monochrome` line
  filter. Pure red's luminance is 0.2126 × 255 ≈ 54 = `0x36`, so `#ff0000` →
  `#363636`. The other 11 tests survive because they assert distinctness or
  structure, not literal hexes. Monochrome output still keeps the four
  magnitudes distinct.
- The product is correct. `NO_COLOR` is an explicit user request for
  monochrome, and Textual honours it. Nothing in this repo sets `NO_COLOR`
  (`git grep` finds nothing). The t2295 run was made by a Codex agent
  (`implemented_with: codex/gpt6_astra`), so the variable was most likely
  inherited from that agent's shell environment. This attribution is inferred,
  not proven: the `/tmp/t2295-evidence/` logs are gone. The fix does not depend
  on knowing the source.

So the test expectations are right for a colour terminal. The defect is that
the tests take their colour pipeline from whatever environment launched them.

## Implementation (single file: `tests/test_concern_picker_modal.py`)

1. **Pin the environment for the whole class.** Add a `setUp` to
   `ConcernMagnitudeRampTests` (around line 3625):
   ```python
   def setUp(self):
       # Textual reads NO_COLOR at App() construction and installs the
       # Monochrome filter (#ff0000 -> #363636). The hexes below pin the
       # colour pipeline, so they must not depend on the caller's env (t2331).
       patcher = unittest.mock.patch.dict(os.environ)
       patcher.start()
       self.addCleanup(patcher.stop)
       os.environ.pop("NO_COLOR", None)
   ```
   `patch.dict(os.environ)` with no values snapshots the environment and restores
   it on cleanup, so the inherited value comes back after each test. Add
   `import os` to the imports (lines 17–22). Every hex-reading test in the class
   builds its App inside the test method, after `setUp`, so a single hook covers
   `_arrow_styles` and the `_Host` sweep in
   `test_the_ramp_survives_every_row_state…`.

2. Add one sentence to the `RESOLVED` comment block (around line 3680): the
   literals assume no `NO_COLOR` filter, which `setUp` guarantees.

**No permanent `NO_COLOR` control test.** Textual has two valid ways to honour
`NO_COLOR` (`app.py:616`): `Monochrome` (grey) normally, and `NoColor` (resets
colours to `default`) in native-ANSI mode. A test that pinned "grey" could break
on a correct rendering-config or dependency change. The proof that the pin is
load-bearing is therefore the one-time pre-fix control below, recorded verbatim
in the Final Implementation Notes. Nothing in the suite asserts it.

**Out of scope (boundary noted, not fixed):** `TEXTUAL_FILTERS` and
`TEXTUAL_COLOR_SYSTEM` are read once, at `textual.constants` import time, so a
per-test patch cannot neutralise them. Neither was involved here, and no change
is proposed. `.aitask-scripts/` is unchanged: monochrome under `NO_COLOR` is
correct product behaviour.

## Verification

All runs use the existing picker tests unmodified, so the exact-colour and
row-state assertions are unchanged:

- Pre-fix control (already run, one-time): `NO_COLOR=1 ~/.aitask/venv/bin/python -m pytest -q
  tests/test_concern_picker_modal.py -k ConcernMagnitudeRampTests` → 2 failed
  (`'#363636' != '#ff0000'` at lines 3704 and 3781), 11 passed. Without
  `NO_COLOR` → 13 passed.
- Post-fix, the same command with `NO_COLOR=1` set → 13 passed.
- Post-fix, with `NO_COLOR` unset → 13 passed.
- Whole file, with `NO_COLOR=1` set and with it unset →
  224 passed each time.

## Step 9 (Post-Implementation)

Commit with `test: Pin NO_COLOR out of the concern-picker colour-ramp tests (t2331)`,
then archive per the shared workflow Step 9.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.
