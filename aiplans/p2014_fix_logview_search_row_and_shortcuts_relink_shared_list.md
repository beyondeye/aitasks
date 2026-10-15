---
Task: t2014_fix_logview_search_row_and_shortcuts_relink_shared_list.md
Base branch: main
Output branch: main
---

# t2014 — logview search row + ShortcutsMixin shared-list leak

## Context

t2003's review found two upstream defects next to the frozenagent fixes:

1. **logview `/` box draws nothing.** `.aitask-scripts/logview/logview_app.py:48` gives the
   stock `Input` `height: 1`. Its 2-row `tall` border fills that completely, so the content area
   has 0 rows. Measured during planning (Textual 8.2.7, headless `run_test(size=(100,24))`):
   after `/`, the box is focused and `region.height == 2`, but `content_region.height == 0`.
   The placeholder is not on screen. Typing `qzx` sets `Input.value == "qzx"`, but the text is
   never drawn. This is the same defect t2003 fixed in frozenagent, whose CSS was copied from
   logview.
2. **`_relink_live_bindings` mutates class-level state.**
   `.aitask-scripts/lib/shortcuts_mixin.py:140` runs `mapping.setdefault(new_key, []).append(active_b)`.
   Textual builds `self._bindings` with `_merged_bindings.copy()`, and `BindingsMap.copy()` is
   `key_to_bindings.copy()`: a new dict that holds the class's per-key lists
   (`textual/binding.py:241-249`, `dom.py:218-221`). When an override moves a binding onto a key
   the class already binds, the moved binding is appended to the class-level list.
   Measured: for a demo class with `e→do_thing` and `y→other` and an override `do_thing→y`,
   `Demo._merged_bindings["y"]` goes from `['other']` to `['other','do_thing']`. A fresh instance
   built afterwards, with no override, inherits that list.
   Other paths are already safe. The old-key branch assigns a new list or deletes from the
   instance dict, and frozenagent's `_sync_copy_keys` already assigns new lists.
   A grep found no other in-place mutation of `key_to_bindings` or `self.bind(` under
   `.aitask-scripts/`.

**Where the leak shows.** Textual's `_check_bindings` tries each binding on a key in order and
falls through when an action raises `SkipAction` (`app.py:3984-3987`, `4273-4289`). So in a
later instance that has no override, the leaked binding becomes a hidden live binding: when the
key's own action declines, `y` fires `do_thing`.

## Implementation (test-first, so each new test is proven red before its fix)

### 1. Logview pilot test (new file `tests/test_logview_search_box.py`)

Model it on t2003's `SearchBoxTests` (`tests/test_frozenagent_app.py:596-642`), including the
`_screen_text` helper (export_screenshot, SVG tags stripped, html-unescaped, nbsp→space).
Setup: a temporary log file containing `alpha\nbravo\ncharlie\n`, and `LogViewApp(path, tail=False)`
so no poll thread runs. One test:

- Press `slash`, then `pilot.pause()`.
- Assert `app.focused is box` and `box.content_region.height >= 1`.
- Assert `"Search (Enter to confirm"` appears in `_screen_text(app)`.
- Type `qzx`, a term the log does not contain, so only the box can draw it, then assert `"qzx"`
  is in the screen text. Checking `Input.value` is not enough: that check passes today.
- Layout: `box.region.y >= header-info.region.bottom`, `log.region.y >= box.region.bottom`,
  and `log.region.height >= 1`.
- Clear the box, type `charlie`, press `enter`. Assert the box loses `visible`, focus returns to
  the `RichLog`, and `app._search_term == "charlie"`. This shows the compact box still submits.

Run it (`~/.aitask/venv/bin/python tests/test_logview_search_box.py`). It must FAIL on the
`content_region.height` assertion before the fix.

### 2. Logview fix (`.aitask-scripts/logview/logview_app.py:48`)

```css
/* `border: none` is what gives the box a text row: the stock Input's 2-row
   `tall` border filled `height: 1` entirely, leaving a 0-row content area,
   so typed text was received but never drawn (t2014; same fix as t2003). */
#search-box { display: none; height: 1; border: none; }
```
This is the same compact form frozenagent uses (`frozenagent_app.py:207-212`). The 1-row layout
stays the same, so the log keeps its height.

### 3. Shared-list regression test (append to `tests/test_shortcuts_mixin_live_remap.py`)

Add a dedicated class, so a red run cannot pollute the existing tests' `_DemoApp`:

```python
class _CollidingApp(ShortcutsMixin, App):
    """Two bindings, so an override can move one onto a key the class binds."""
    _shortcuts_scope = "demo_collide"
    BINDINGS = [Binding("e", "do_thing", "Thing"), Binding("y", "other", "Other")]
    def __init__(self): super().__init__(); self.fired = False
    def action_do_thing(self): self.fired = True
    def action_other(self):
        # Declines, so the key falls through to the next binding on it: the
        # path a leaked binding takes.
        raise SkipAction()
```

Add `SharedKeyRebindTests(_Fixture)` with a single test. It reuses the existing temp-workspace
fixture and registry reset:

- Snapshot `{k: list(v) for k, v in _CollidingApp._merged_bindings.key_to_bindings.items()}`.
- Call `save_override("demo_collide", "do_thing", "y")` and `refresh_all()`, then construct
  `app = _CollidingApp()`. Precondition: `[b.action for b in app._bindings.key_to_bindings["y"]] == ["other", "do_thing"]`.
  This proves the override really reached the shared key.
- Assert that the class-level map is unchanged against the snapshot.
- Call `clear_override(...)` and `refresh_all()`, then construct `later = _CollidingApp()`.
  Assert `later`'s live `"y"` bucket is `["other"]`.
- Behaviour: run `later.run_test()`. Pressing `y` must leave `later.fired` False, because the
  leaked `do_thing` must not fire. Pressing `e` must set it True, because the instance's own
  default still works.

Run the file. The new test must FAIL on the class-map assertion before the fix, and the existing
tests must stay green.

### 4. Mixin fix (`.aitask-scripts/lib/shortcuts_mixin.py:140`)

```python
            # A new list, never `setdefault(...).append`: `BindingsMap.copy()`
            # is shallow, so an existing per-key list here IS the class-level
            # `_merged_bindings` list, and appending to it would leak this
            # override into every later instance of the class (t2014).
            mapping[new_key] = [*mapping.get(new_key, []), active_b]
```
The resulting order and contents of the instance's own map are identical, so the only change is
that class-level state is no longer mutated.

## Verification

- Red, then green, for both new tests (steps 1→2 and 3→4 above).
- `~/.aitask/venv/bin/python tests/test_logview_search_box.py`
- `~/.aitask/venv/bin/python tests/test_shortcuts_mixin_live_remap.py`
- Neighbours: `tests/test_textual_markup_structure.py` (logview header and startup focus),
  `tests/test_frozenagent_app.py`, and `tests/test_settings_shortcuts_tab.py`.
- Blast radius: the mixin runs in every TUI, so run the full Python suite with
  `set -o pipefail; bash tests/run_all_python_tests.sh` and read only the final
  `PYTHON SUITE:` line. The worktree carries other sessions' uncommitted edits, so attribute any
  failure against this change's surface before acting on it.
- Commit only the four touched paths. Then Step 9 (Post-Implementation): archive on the current
  branch, with no merge.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.
