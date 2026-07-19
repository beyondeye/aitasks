---
Task: t1160_fix_shortcut_scopes_explore_pick_quick_jump.md
Worktree: (none — current branch, profile 'fast')
Branch: main
Base branch: main
---

# Plan: Fix `_QUICK_JUMPS` drift in test_shortcut_scopes.py (t1160)

## Context

`TuiSwitcherScopeTests` in `tests/test_shortcut_scopes.py` fails 2/6 on a clean
HEAD checkout. The test hand-maintains a `_QUICK_JUMPS` set (13 entries) and
asserts set-equality against the actions registered under `shared.tui_switcher`.
t1148 (commit `24eac8dc4`) added a 14th quick-jump — `shortcut_explore_pick`
("Explore (pick agent)", key `X`) — to the canonical `_QUICK_JUMP_BINDINGS`
table in `.aitask-scripts/lib/tui_switcher.py:369`, but did not update the test's
duplicated expectation set. Result:

```
AssertionError: Items in the first set but not the second: 'shortcut_explore_pick'
```
failing `test_quick_jumps_in_iter_all_bindings` and
`test_quick_jumps_in_scope_filtered_editor`.

The root cause is a **hand-maintained duplicate** of a list that already has a
canonical source. Rather than patch the duplicate (which will drift again on the
next quick-jump added), derive it — per the project's derive-don't-duplicate
convention, which the task explicitly asks to evaluate.

## Canonical source

`.aitask-scripts/lib/tui_switcher.py:369-384` — `_QUICK_JUMP_BINDINGS` is the
single source of truth: a list of `textual.binding.Binding` objects whose
`.action` is exactly the `shortcut_<name>` action id registered under
`shared.tui_switcher` (via `register_app_bindings(_TUI_SWITCHER_SCOPE,
_QUICK_JUMP_BINDINGS)` at line 460). Deriving `{b.action for b in
_QUICK_JUMP_BINDINGS}` yields the 14-element set (verified).

## Approach

Edit `tests/test_shortcut_scopes.py` only:

1. Add a top-level import next to the existing lib imports (after
   `import shortcut_scopes  # noqa: E402`, ~line 35):
   ```python
   import tui_switcher  # noqa: E402
   ```
   (Textual is already a hard dependency of this suite — the sweep imports
   every TUI module, so this adds no new dependency.)

2. Replace the hand-maintained `_QUICK_JUMPS` literal (lines 149-154) in
   `TuiSwitcherScopeTests` with a derivation from the canonical table:
   ```python
   # Derived from the switcher's canonical quick-jump table (t1160) so this
   # guard cannot drift when a quick-jump is added/removed. The equality
   # assertions below still verify the registration + sweep pipeline surfaces
   # exactly these actions under shared.tui_switcher, and that the fixed
   # structural keys (escape/enter/←/→/j) are left unregistered.
   _QUICK_JUMPS = {b.action for b in tui_switcher._QUICK_JUMP_BINDINGS}
   ```

3. **Guard (derive-with-guard):** add a sanity anchor at the start of
   `test_quick_jumps_in_iter_all_bindings` so a broken import/derivation
   (empty or shrunken set) fails loudly instead of making the equality
   assertion vacuous — mirroring the existing anchor pattern in
   `test_sweep_registers_every_source_scope` (lines 70-72):
   ```python
   # Sanity: the derived expectation must be non-empty and contain anchors.
   for anchor in ("shortcut_board", "shortcut_explore", "shortcut_explore_pick"):
       self.assertIn(anchor, self._QUICK_JUMPS)
   ```

No production code changes. `_STRUCTURAL` and the disjointness assertion are
unchanged.

## Verification

```bash
python3 tests/test_shortcut_scopes.py        # expect: Ran 6 tests ... OK
```

Also confirm no regression in the broader python suite touching this area is
not needed (single file), but a quick `shellcheck`/lint is N/A (Python test).

## Risk

### Code-health risk: low
- None identified. Test-only edit in a single file; replaces a hand-maintained
  duplicate with a derivation from the canonical `_QUICK_JUMP_BINDINGS` table,
  reducing future drift. No production code paths touched. · severity: low

### Goal-achievement risk: low
- None identified. The change directly resolves the two failing assertions and
  is verified by re-running the test to a green 6/6. · severity: low

## Post-Implementation

Follow task-workflow Step 8 (review + commit as `bug: ... (t1160)`) and Step 9
(archival). The `risk_evaluated` gate is recorded by the Step-9 orchestrator.

## Final Implementation Notes

- **Actual work done:** Edited `tests/test_shortcut_scopes.py` only, exactly as
  planned: (1) added `import tui_switcher  # noqa: E402` next to the existing lib
  imports; (2) replaced the 13-entry hand-maintained `_QUICK_JUMPS` literal in
  `TuiSwitcherScopeTests` with `{b.action for b in tui_switcher._QUICK_JUMP_BINDINGS}`
  (the canonical 14-entry table); (3) added a sanity anchor loop at the top of
  `test_quick_jumps_in_iter_all_bindings` asserting `shortcut_board`,
  `shortcut_explore`, and `shortcut_explore_pick` are present, so a broken
  import/derivation fails loudly rather than making the equality assertion vacuous.
- **Deviations from plan:** None.
- **Issues encountered:** None. `python3 tests/test_shortcut_scopes.py` went from
  2/6 failing (`shortcut_explore_pick` missing) to 6/6 passing.
- **Key decisions:** Chose derive-over-patch (derive-don't-duplicate convention,
  explicitly requested by the task) so this drift class cannot recur when a
  quick-jump is added. Retained an independent-ground-truth backstop via the
  anchor guard, per derive-with-guard. Used the private `_QUICK_JUMP_BINDINGS`
  symbol directly (the file already reaches into `keybinding_registry` internals);
  no public accessor exists and adding one was out of scope for a test-only fix.
  Verified `import tui_switcher` adds no new dependency — Textual is already a hard
  dependency of this suite (the sweep imports every TUI module).
- **Upstream defects identified:** None.
