---
Task: t848_2_label_renderer_and_board_pilot.md
Parent Task: aitasks/t848_customizable_shortcuts.md
Sibling Tasks: aitasks/t848/t848_1_*.md, aitasks/t848/t848_3_*.md, aitasks/t848/t848_4_*.md, aitasks/t848/t848_5_*.md, aitasks/t848/t848_6_*.md
Archived Sibling Plans: aiplans/archived/p848/p848_*_*.md
Worktree: (current directory — fast profile)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-28 17:32
---

# p848_2 — Label renderer + ShortcutsMixin + board pilot

## Goal

Build `(X)plore`-style label renderer + `ShortcutsMixin`, then migrate
the board TUI end-to-end as proof. After this child, picking the board
button labels reflect the active binding key from t848_1's registry,
including when the user has overridden the key.

## Files

**New:**

- `.aitask-scripts/lib/shortcut_labels.py`
- `.aitask-scripts/lib/shortcuts_mixin.py`
- `tests/test_shortcut_labels.sh`
- `tests/test_shortcut_labels_golden/*` (one expected-output file per case)

**Modified:**

- `.aitask-scripts/board/aitask_board.py`

## Step-by-step

### 1. `shortcut_labels.py`

Two rendering styles, callsite-selected, both ensure every label
exposes the active shortcut even when the user rebinds to a key whose
letter isn't part of the text.

```python
def render_label(text: str, key: str, *, style: str = "wrap") -> str:
    """
    style="wrap"  — used by button labels in TaskDetailScreen et al.
        - Empty key:        text
        - Single-char in text (case-insensitive, first match anywhere
          including mid-word): wrap and uppercase. `Pick` + `p`/`P`
          -> `(P)ick`.
        - Single-char NOT in text: prefix `(K) text`. `New Task` + `0`
          -> `(0) New Task`.
        - Multi-key (contains `+` or len > 1): prefix
          `(display_form(key)) text`. `Move Right` + `ctrl+r` ->
          `(Ctrl+R) Move Right`.

    style="leading" — used by inline filter labels in ViewSelector.
        - Empty key:        text
        - Single-char == first letter of text (case-insensitive):
          `k Text` (lowercase key + space + original-case text).
          `Locked` + `l`/`L` -> `l Locked`. Matches current filter
          rendering before t848.
        - Single-char ≠ first letter or not in text at all:
          fall back to `k · Text` (key + space + middle-dot +
          space + text). `Locked` + `o` -> `o · Locked`.
        - Multi-key: `display_form(key) · Text`. `Move Right` +
          `ctrl+r` -> `Ctrl+R · Move Right`.
    """

def display_form(key: str) -> str:
    """`ctrl+r` -> `Ctrl+R`, `a` -> `A`, `escape` -> `Escape`."""
```

Rule summary:
| Case | wrap | leading |
| --- | --- | --- |
| `Pick`,`p` | `(P)ick` | `p Pick` |
| `Pick`,`P` | `(P)ick` | `p Pick` |
| `Pick`,`o` | `(O) Pick` | `o · Pick` |
| `Locked`,`l` | `(L)ocked` | `l Locked` |
| `Locked`,`o` | `(O) Locked` | `o · Locked` |
| `Move Right`,`ctrl+r` | `(Ctrl+R) Move Right` | `Ctrl+R · Move Right` |
| `Foo`,`` | `Foo` | `Foo` |

### 2. `shortcuts_mixin.py`

```python
from textual.binding import Binding
from keybinding_registry import register_app_bindings, resolve_key
from shortcut_labels import render_label

class ShortcutsMixin:
    """Apply shortcut overrides + provide `label()` for any Textual class
    (App, Screen, ModalScreen) that owns its own BINDINGS list.

    Usage:
      - Subclass MUST set `_shortcuts_scope` (string, e.g. "board" or
        "board.detail").
      - Apps should splice `*ShortcutsMixin.SHORTCUTS_MIXIN_BINDINGS`
        into their BINDINGS class attr to expose the `?` shortcut-editor
        binding. Modal/Screen subclasses MUST NOT splice — the `?`
        binding is owned at App level only.
    """

    _shortcuts_scope: str = ""

    SHORTCUTS_MIXIN_BINDINGS = [
        Binding("?", "open_shortcuts_editor", "Keys"),
    ]

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        if not self._shortcuts_scope:
            raise RuntimeError("ShortcutsMixin subclass must set _shortcuts_scope")
        # Apply overrides; record defaults in registry.
        self.BINDINGS = register_app_bindings(self._shortcuts_scope, self.BINDINGS)

    def label(self, action_id: str, text: str, *, style: str = "wrap") -> str:
        key = resolve_key(self._shortcuts_scope, action_id) or ""
        return render_label(text, key, style=style)

    def action_open_shortcuts_editor(self) -> None:
        raise NotImplementedError("Implemented in t848_4")


# Module-level helper for callsites that don't have a ShortcutsMixin
# instance (e.g. Static widgets like ViewSelector).
def get_label(scope: str, action_id: str, text: str, *, style: str = "wrap") -> str:
    key = resolve_key(scope, action_id) or ""
    return render_label(text, key, style=style)
```

Note: imports are top-level module names (`keybinding_registry`,
`shortcut_labels`), not package-relative — `.aitask-scripts/lib/` is
added to `sys.path` per t848_1's archived plan notes.

### 3. Board pilot — `aitask_board.py`

**Verification finding (2026-05-28):** The `(X)` button labels live inside
`TaskDetailScreen(ModalScreen)` (class at line 2098), not directly on
`KanbanApp`. The modal already owns its own `BINDINGS` block (lines
2101–2126) with action ids `pick`, `brainstorm`, `lock`, `unlock`, `close`,
`save`, `revert`, `edit`, `toggle_view`, `rename`, `delete`, plus
case-variant uppercase duplicates. All have matching `action_*` methods
(lines 2631–2683). The plan's earlier action ids (`pick_task`,
`view_plan`, `delete_archive`, `close_detail`, `save_changes`,
`brainstorm_task`) were App-level conventions that do NOT match the modal
that hosts these buttons.

**Scope organization model — sub-scopes per modal/screen.** Per
2026-05-28 design call, scopes are nested by Textual class: the App
itself uses `"board"`, each Modal/Screen with its own BINDINGS gets a
sub-scope like `"board.detail"`. This keeps overrides addressable and
groups bindings sensibly in the t848_4 editor (which can present
sub-scopes as indented sub-sections under the parent TUI). Override
paths become `shortcuts.board.detail.pick: o`.

Adjustments:

- `KanbanApp` gets `ShortcutsMixin` with `_shortcuts_scope = "board"`.
  The App's BINDINGS (line 3318) gain
  `*ShortcutsMixin.SHORTCUTS_MIXIN_BINDINGS` alongside
  `*TuiSwitcherMixin.SWITCHER_BINDINGS`.

- `TaskDetailScreen` ALSO mixes in `ShortcutsMixin` with
  `_shortcuts_scope = "board.detail"`. **Crucially, do NOT splice
  `SHORTCUTS_MIXIN_BINDINGS` into the modal's BINDINGS class attr** —
  the `?` shortcut-editor binding is owned at App level only. The
  modal still inherits `action_open_shortcuts_editor` (dormant on the
  modal; never invoked because no `?` binding fires there).

  ```python
  class TaskDetailScreen(ShortcutsMixin, ModalScreen):
      _shortcuts_scope = "board.detail"

      BINDINGS = [
          # ... existing bindings, no SHORTCUTS_MIXIN_BINDINGS splice ...
      ]

      def __init__(self, task, manager=None, read_only=False):
          # ShortcutsMixin.__init__ runs first via MRO, calls super(),
          # then mutates self.BINDINGS to apply user overrides.
          super().__init__()
          self.task_data = task
          self.manager = manager
          self.read_only = read_only
          ...
  ```

  Two-call registration: the App registers `board`-scope bindings at
  App construction; the modal registers `board.detail`-scope bindings
  at each modal push. Both registrations land in the registry's
  `_DEFAULTS` map and survive across modal pushes.

- Button label replacements at `aitask_board.py:2302-2322` (line range
  shifted from plan's initial 2262-2282) — call `self.label(...)` from
  inside `compose()` (the modal carries its own `label` method via
  `ShortcutsMixin`, bound to `_shortcuts_scope = "board.detail"`):
  ```python
  yield Button(self.label("pick", "Pick"), variant="warning", id="btn_pick", ...)
  yield Button(self.label("brainstorm", "Brainstorm"), variant="primary", id="btn_brainstorm", ...)
  yield Button("\U0001f512 " + self.label("lock", "Lock"), variant="primary", id="btn_lock", ...)
  yield Button("\U0001f513 " + self.label("unlock", "Unlock"), variant="warning", id="btn_unlock", ...)
  yield Button(self.label("close", "Close"), variant="default", id="btn_close")
  yield Button(self.label("toggle_view", "View Plan"), variant="primary", id="btn_view", ...)
  yield Button(self.label("save", "Save Changes"), variant="success", id="btn_save", ...)
  yield Button(self.label("revert", "Revert"), variant="error", id="btn_revert", ...)
  yield Button(self.label("edit", "Edit"), variant="primary", id="btn_edit", ...)
  yield Button(self.label("rename", "Name"), variant="primary", id="btn_rename", ...)
  yield Button(self.label("delete", "Delete/Archive"), variant="error", id="btn_delete", ...)
  ```

- Audit the rest of `aitask_board.py` for `Button(` literals with
  `\([A-Za-z]\)` and migrate them too. **Verification finding:** `grep`
  shows the only `(X)` Button literals in the file are the 11 above
  inside `TaskDetailScreen.compose()`. No other audit work needed.

**ViewSelector filter labels — leading style.** The board's filter
bar (`ViewSelector` class at line 594, used to render
`[a All | l Locked | f Free]   g Git   t Type`) currently hardcodes
the key letters in `BASES`/`ADDONS` tuples and uses `f"{key} {label}"`
to render each segment (line 638, 655). After t848 the displayed key
must reflect any user override.

Replace the hardcoded `seg_text = f"{key} {label}"` with a
registry-aware call:

```python
from shortcuts_mixin import get_label

# ViewSelector.render(), inside the base/addon loops:
action_id = f"view_{base_id}"   # view_all / view_locked / view_free / view_git / view_type
seg_text = get_label("board", action_id, label, style="leading")
```

The BASES/ADDONS tuples can drop their hardcoded `key` field
(the registry is now the source of truth) — keep only
`(action_id_suffix, label, base_id/addon_id)`. The on-click hit-test
logic in `on_click()` is unaffected; it uses `target_id` (which is
the base_id / addon_id, not the key).

After this change, with a default `view_locked` binding of `l`, the
segment renders `l Locked`. After the user sets
`shortcuts.board.view_locked: o` in `userconfig.yaml`, it becomes
`o · Locked`. Default presentation is preserved; rebind cases stay
informative.

**Why case-variant bindings (e.g. `p` and `P` both → action `pick`) are
not a registry concern:** The registry records the last-seen
`(scope, action_id) -> (key, label)` entry. For the duplicate-action
case both default keys differ only in case, and `render_label` matches
case-insensitively, so the rendered output is identical regardless of
which variant wins. Override application iterates every binding, so a
user override of `pick` rewrites both lowercase and uppercase variants
together.

### 4. Tests

`tests/test_shortcut_labels.sh`:
- For each case, run a Python one-liner that imports `render_label` and
  compares output to a committed golden file under
  `tests/test_shortcut_labels_golden/<case>.txt`.

Golden cases — wrap style (default):
- `wrap_pick_p.txt`            -> `(P)ick`
- `wrap_pick_uppercase_P.txt`  -> `(P)ick`
- `wrap_pick_o.txt`            -> `(O) Pick`           (no-match prefix)
- `wrap_new_task_zero.txt`     -> `(0) New Task`       (digit key)
- `wrap_toggle_children_x.txt` -> first-match wrap (golden locks the exact
                                   output, including whether mid-word `x` is
                                   wrapped)
- `wrap_move_right_ctrl_r.txt` -> `(Ctrl+R) Move Right` (multi-key prefix)
- `wrap_empty_key.txt`         -> `Foo`

Golden cases — leading style (filter bar):
- `lead_locked_l.txt`          -> `l Locked`
- `lead_locked_uppercase_L.txt`-> `l Locked`           (key normalised lowercase)
- `lead_locked_o.txt`          -> `o · Locked`         (non-first letter)
- `lead_all_a.txt`             -> `a All`
- `lead_move_right_ctrl_r.txt` -> `Ctrl+R · Move Right`
- `lead_empty_key.txt`         -> `Foo`

## Verification

```bash
bash tests/test_shortcut_labels.sh
ait board                       # buttons render with default keys

# Override the detail-screen Pick to `o` (sub-scope path):
cat >> aitasks/metadata/userconfig.yaml <<'EOF'
shortcuts:
  board.detail:
    pick: o
EOF
ait board                       # open a task -> (P)ick now reads (O) Pick
# clean up
yq -i 'del(.shortcuts)' aitasks/metadata/userconfig.yaml
```

## Verification (for the t848_7 manual-verification sibling)

- `ait board` shows `(P)ick`-style labels driven by current bindings.
- Editing `userconfig.yaml` updates the labels on relaunch.
- All other board behavior unchanged (no regression in detail screen).

## Step 9 — Post-implementation

Standard archival.

## Post-Review Changes

### Change Request 1 (2026-05-29 06:34)
- **Requested by user:** Pressing `?` in `ait board` crashed the app
  (NotImplementedError surfaced as an unhandled exception).
- **Changes made:** Replaced the `NotImplementedError` raise in
  `ShortcutsMixin.action_open_shortcuts_editor` with a soft `self.notify(...)`
  that surfaces a "coming in t848_4" message via Textual's toast. Uses
  `getattr(self, 'notify', None)` so the stub is safe to call from classes
  that don't have `notify()` (e.g., bare unit-test instances).
- **Files affected:** `.aitask-scripts/lib/shortcuts_mixin.py`

## Final Implementation Notes

- **Actual work done:**
  - `lib/shortcut_labels.py` — pure-function renderer with two styles
    (`wrap`, `leading`) and `display_form` helper for multi-key combos.
  - `lib/shortcuts_mixin.py` — `ShortcutsMixin` (App-level + Modal-level
    use) plus module-level `get_label(scope, action_id, text, style)`
    free function for widgets that can't carry the mixin (e.g.
    `ViewSelector`).
  - `board/aitask_board.py`:
    - `KanbanApp(TuiSwitcherMixin, ShortcutsMixin, App)` with
      `_shortcuts_scope = "board"`. `BINDINGS` gains
      `*ShortcutsMixin.SHORTCUTS_MIXIN_BINDINGS` for the `?` editor
      stub binding.
    - `TaskDetailScreen(ShortcutsMixin, ModalScreen)` with
      `_shortcuts_scope = "board.detail"`. No mixin-binding splice —
      the `?` lives only at App level.
    - 11 button labels in the detail screen migrated to
      `self.label(action_id, text)` (style="wrap").
    - `ViewSelector.BASES`/`ADDONS` tuples reshaped to
      `(action_id, label, target_id)`; segment text rendered via
      `get_label("board", action_id, label, style="leading")`.
  - `tests/test_shortcut_labels.sh` + `tests/test_shortcut_labels_golden/`
    — 14 golden cases (7 wrap, 7 leading). All passing.
- **Deviations from plan:**
  - Renderer ended up supporting two callsite-selected styles (`wrap`
    and `leading`) rather than the single style in the initial plan.
    The leading style was requested mid-implementation to preserve
    the t850 filter-bar look (`l Locked`) while still surfacing
    overrides cleanly (`o · Locked`).
  - Sub-scope model (`board` for App, `board.detail` for modal) was
    chosen over the original flat-`board`-scope plan, again
    mid-implementation, so the t848_4 editor can group bindings by
    Textual class.
  - `action_open_shortcuts_editor` stub: original plan had it raise
    `NotImplementedError`. Initial implementation followed the plan,
    but pressing `?` in `ait board` crashed the app at user-test time.
    Replaced with a soft `self.notify(...)` toast ("coming in t848_4")
    that is safe to call from any class that mixes in `ShortcutsMixin`
    — including future unit tests on bare instances, where `notify`
    is absent (the `getattr` guard handles that).
  - `register_app_bindings` was called twice for the same key bindings
    in `TaskDetailScreen.__init__` (because the modal is constructed
    fresh on every push). `_DEFAULTS` is idempotent under
    same-`(scope, action_id)` writes; no defensive code needed.
- **Issues encountered:**
  - The verify path surfaced a major plan deviation: the original
    plan had button labels living on `KanbanApp`, but they actually
    live in `TaskDetailScreen`. The verify-mode plan-update prevented
    a wasted implementation pass.
  - The case-variant Binding pattern in `TaskDetailScreen` (each
    action bound to both lowercase and uppercase variants) means
    `register_app_bindings` records the uppercase variant last. This
    is rendering-neutral (both `(P)ick` from `p` and from `P` are
    identical under `render_label`), so no remediation was needed.
- **Key decisions:**
  - **Two-style renderer.** A single style would have forced
    button-style on filter labels (regression of t850's look). Two
    callsite-selected styles let each call-site pick. `get_label`
    free function gives non-mixin widgets the same access.
  - **Sub-scope `board.detail`.** Lets the t848_4 editor present
    modal bindings as a sub-section under "board". Override paths
    become `shortcuts.board.detail.<action>`, which is addressable
    and never collides with the App-level scope.
  - **ShortcutsMixin on modal too.** Lets the modal carry its own
    `self.label(...)` against its own scope. Without the mixin we'd
    need `get_label("board.detail", ...)` inside the modal, which is
    error-prone to keep in sync with the scope literal.
  - **`?` binding owned only at App level.** The mixin defines
    `SHORTCUTS_MIXIN_BINDINGS` as a class attribute that subclasses
    splice into BINDINGS explicitly. Modal/Screen subclasses skip
    the splice to avoid double-stub triggers.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - **t848_3 (TUI sweep):** mirror the board pilot pattern. Pick a
    consistent App scope per TUI (`monitor`, `codebrowser`,
    `brainstorm`, `settings`, `syncer`, `stats-tui`, `diffviewer`).
    For any modal/screen with its own BINDINGS, use `<tui>.<modal>`
    sub-scope and `ShortcutsMixin` (no SHORTCUTS_MIXIN_BINDINGS
    splice on the modal). For Static widgets that render shortcut
    text outside a mixin instance, call `get_label(...)` directly.
  - **t848_4 (editor modal):** the editor should iterate
    `keybinding_registry._DEFAULTS` to populate its scope tree.
    Sub-scopes use `.` as the separator (e.g. `board.detail`); the
    editor can split on `.` to render hierarchy. The mixin's
    `action_open_shortcuts_editor` currently just toasts — replace
    its body with `self.push_screen(...)` to launch the modal. The
    toast `getattr` guard can be removed when the action is no
    longer optional.
  - **t848_5 (settings tab + export/import):** the userconfig
    `shortcuts:` subtree uses nested dot-paths as YAML keys
    (`shortcuts.board.detail.pick`). Round-tripping must preserve
    the dot structure verbatim; treat the scope string as the literal
    YAML key rather than splitting it.
  - **t848_6 (docs):** document the two render styles and the
    sub-scope convention. Reference the golden test directory as the
    source of truth for rendered output.
