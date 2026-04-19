---
Task: t584_reorder_keybinding_in_footer_of_codebrowser.md
Worktree: (none — working on current branch per profile `fast`)
Branch: main
Base branch: main
---

# t584 — Reorder keybindings in codebrowser footer (context-aware)

## Context

The codebrowser TUI has grown ~14 visible bindings. The default Textual
`Footer` renders them in the order they appear in `BINDINGS`, which is not
priority-driven. The user wants two improvements:

1. **New default order (least important):** `h, d, e, n, g, c, <rest>`.
2. **Context-aware reordering:** when a specific pane has focus, that pane's
   relevant bindings move to the front. The key set does **not** change —
   only display order.

This is viable because Textual's `Footer.compose()` iterates
`self.screen.active_bindings` in a fixed order; sorting that list before
it is grouped/yielded is enough to drive the display order.

## Approach

Add a `ContextualFooter` subclass of `textual.widgets.Footer` to
`codebrowser_app.py`. Override `compose()` to sort visible bindings by a
per-pane priority map (resolved from the currently focused widget), then
let the parent's grouping/rendering logic run unchanged (we replicate the
method body since Textual does not expose a hook in between).

Watch `Screen.focused` in `on_mount` so focus changes trigger
`self.recompose()` — the default Footer only recomposes when bindings
themselves change, which is not enough here.

Replace `yield Footer()` with `yield ContextualFooter()` in
`CodeBrowserApp.compose()`. No other files change.

## Files to Modify

- `.aitask-scripts/codebrowser/codebrowser_app.py` — add `ContextualFooter`
  class (near the top, after `CopyFilePathScreen`), add the necessary
  imports (`defaultdict`, `groupby`, and the private `FooterKey` /
  `FooterLabel` / `KeyGroup` from `textual.widgets._footer`), swap the
  `Footer()` call in `compose()` for the new class.

## Priority Maps

Key lists are matched against `Binding.key`. Keys not listed fall to the
end in their original `active_bindings` order. Only visible bindings
(i.e. `show=True`) are reordered; `escape`/`j`/`tab` (show=False) are
unaffected.

```python
DEFAULT_ORDER = ["h", "d", "e", "n", "g", "c"]

PANE_ORDERS = {
    "file_tree":    ["R", "r", "n", "h", "g", "d", "e", "c"],
    "recent_files": ["h", "H", "n", "d", "e", "c"],
    "file_search":  ["n", "g", "e", "h"],
    "code_viewer":  ["g", "w", "c", "e", "n", "h", "d", "t", "r"],
    "detail_pane":  ["d", "D", "H", "h", "n", "e"],
}
```

Pane resolution walks up from `self.screen.focused.parent` until it hits
a widget whose `id` is a key in `PANE_ORDERS`. If none matches,
`DEFAULT_ORDER` is used.

## Implementation Sketch

```python
# New imports at the top of codebrowser_app.py:
from collections import defaultdict
from itertools import groupby
from textual.widgets._footer import FooterKey, FooterLabel, KeyGroup
# (Footer is already imported via textual.widgets.)


class ContextualFooter(Footer):
    """Footer that reorders visible bindings based on the focused pane."""

    DEFAULT_ORDER = ["h", "d", "e", "n", "g", "c"]

    PANE_ORDERS = {
        "file_tree":    ["R", "r", "n", "h", "g", "d", "e", "c"],
        "recent_files": ["h", "H", "n", "d", "e", "c"],
        "file_search":  ["n", "g", "e", "h"],
        "code_viewer":  ["g", "w", "c", "e", "n", "h", "d", "t", "r"],
        "detail_pane":  ["d", "D", "H", "h", "n", "e"],
    }

    def _focused_pane_id(self) -> str | None:
        focused = self.screen.focused
        w = focused
        while w is not None:
            wid = getattr(w, "id", None)
            if wid in self.PANE_ORDERS:
                return wid
            w = w.parent
        return None

    def _ordering(self) -> list[str]:
        pane = self._focused_pane_id()
        return self.PANE_ORDERS.get(pane, self.DEFAULT_ORDER)

    def on_mount(self) -> None:
        super().on_mount()
        self.watch(self.screen, "focused", self._on_focus_change)

    def _on_focus_change(self, _focused) -> None:
        if self.is_attached:
            self.call_after_refresh(self.recompose)

    def compose(self):
        # Replicates Footer.compose() from textual 8.1.1, with the
        # `bindings` list re-sorted by our per-pane priority map before
        # it is grouped by action. Everything else is identical.
        if not self._bindings_ready:
            return
        active_bindings = self.screen.active_bindings

        ordering = self._ordering()
        priority = {k: i for i, k in enumerate(ordering)}
        def _sort_key(item):
            binding, _enabled, _tooltip = item
            return priority.get(binding.key, len(priority))

        bindings = [
            (binding, enabled, tooltip)
            for (_, binding, enabled, tooltip) in active_bindings.values()
            if binding.show
        ]
        bindings.sort(key=_sort_key)

        action_to_bindings = defaultdict(list)
        for binding, enabled, tooltip in bindings:
            action_to_bindings[binding.action].append((binding, enabled, tooltip))
        self.styles.grid_size_columns = len(action_to_bindings)

        for group, multi_bindings_iterable in groupby(
            action_to_bindings.values(),
            lambda mb: mb[0][0].group,
        ):
            multi_bindings = list(multi_bindings_iterable)
            if group is not None and len(multi_bindings) > 1:
                with KeyGroup(classes="-compact" if group.compact else ""):
                    for mb in multi_bindings:
                        binding, enabled, tooltip = mb[0]
                        yield FooterKey(
                            binding.key,
                            self.app.get_key_display(binding),
                            "",
                            binding.action,
                            disabled=not enabled,
                            tooltip=tooltip or binding.description,
                            classes="-grouped",
                        ).data_bind(compact=Footer.compact)
                yield FooterLabel(group.description)
            else:
                for mb in multi_bindings:
                    binding, enabled, tooltip = mb[0]
                    yield FooterKey(
                        binding.key,
                        self.app.get_key_display(binding),
                        binding.description,
                        binding.action,
                        disabled=not enabled,
                        tooltip=tooltip,
                    ).data_bind(compact=Footer.compact)

        if self.show_command_palette and self.app.ENABLE_COMMAND_PALETTE:
            try:
                _node, binding, enabled, tooltip = active_bindings[
                    self.app.COMMAND_PALETTE_BINDING
                ]
            except KeyError:
                pass
            else:
                yield FooterKey(
                    binding.key,
                    self.app.get_key_display(binding),
                    binding.description,
                    binding.action,
                    classes="-command-palette",
                    disabled=not enabled,
                    tooltip=binding.tooltip or binding.description,
                )
```

In `CodeBrowserApp.compose()` replace:

```python
yield Footer()
```

with:

```python
yield ContextualFooter()
```

No changes to `BINDINGS` ordering itself — sorting happens at render
time, so the binding list remains authoritative for "what keys do what".

## Notes / Caveats

- `FooterKey`, `FooterLabel`, `KeyGroup` are imported from the private
  `textual.widgets._footer`. This is brittle across Textual versions —
  the pinned version at implementation time is **8.1.1**. If Textual
  changes Footer internals, this class needs to be refitted. Document
  this in a short inline comment.
- The `code_viewer` priority map includes `w` (wrap), `t` (annotations),
  `r` (refresh), because they are primarily useful while viewing code.
- The `detail_pane` map surfaces `D`, `H` because both only make sense
  with the detail pane in view (and typically focused).
- `escape`, `tab`, and the TUI switcher `j` all have `show=False` and
  are not affected by reordering.

## Verification

Manual smoke test (no automated tests for TUIs):

1. `./ait codebrowser` — open a file.
2. Observe default order: `h d e n g c …`.
3. Press `Tab` to cycle focus through panes; at each stop verify footer
   reorders to match that pane's map:
   - recent files → `h H n …`
   - file tree → `R r n h …`
   - file search → `n g e h …`
   - code viewer → `g w c e n …`
   - detail pane (enable with `d` first, then Tab to it) → `d D H h …`
4. Press bindings from any state and confirm they still work (e.g. `g`
   opens go-to-line regardless of footer position; `n` still launches
   task creation; `q` still quits).
5. Resize the terminal narrow and confirm no layout regressions.

## Step 9 reminder

After implementation & review, proceed to Step 9 (Post-Implementation):
archive via `./.aitask-scripts/aitask_archive.sh 584` and push.

## Final Implementation Notes

- **Actual work done:** Added `ContextualFooter(Footer)` subclass to
  `codebrowser_app.py` with `DEFAULT_ORDER` and per-pane `PANE_ORDERS` maps.
  `compose()` replicates Textual 8.1.1's `Footer.compose()` but sorts the
  visible-binding list by a priority computed from the currently focused
  pane (resolved by walking `self.screen.focused.parent` until a known pane
  id is hit). `on_mount()` additionally watches `self.screen.focused` so
  focus changes trigger `self.recompose()`. Swapped `Footer()` → 
  `ContextualFooter()` in `CodeBrowserApp.compose()`.
- **Deviations from plan:** The plan's compose-replica included
  `.data_bind(compact=Footer.compact)` on each yielded `FooterKey`. That
  call crashed on start with `ReactiveError: Unable to bind data; Footer
  is not defined on Screen.` because during `compose(self)` invoked from
  `recompose()`, `active_message_pump.get()` returns the Screen, not our
  `ContextualFooter` instance, and Textual's data-bind guard rejects the
  binding. Fix: dropped both `.data_bind` calls. FooterKey keeps its own
  `compact = reactive(True)` default, which is equivalent for codebrowser
  since we never toggle `Footer.compact` globally.
- **Issues encountered:** The first removal pass only stripped one of the
  two `.data_bind(...)` occurrences (grouped vs ungrouped branch); the
  ungrouped one still crashed until removed in a follow-up edit.
- **Key decisions:** Pane resolution is id-based (walks parents looking
  for an id in `PANE_ORDERS`) rather than class-based, so it naturally
  handles nested focusables like the `Input` inside `FileSearchWidget`
  (`id="file_search"`). Keys not listed in the active priority map fall
  to the end in their original `active_bindings` order via a stable
  `sort(key=…)`.
- **Verification performed:** `./ait codebrowser` launches without error;
  footer renders `h H n d …` on start (matches `recent_files` priority,
  which auto-focuses at mount). Full Tab-cycle verification is up to the
  user (see §Verification).
