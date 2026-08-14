---
Task: t1468_8_board_task_detail_followup_kind.md
Parent Task: aitasks/t1468_mark_followup_task_provenance_and_surface_on_board.md
Sibling Tasks: aitasks/t1468/t1468_8_*.md
Archived Sibling Plans: aiplans/archived/p1468/p1468_*_*.md
Worktree: (none — current-branch mode)
Branch: main
Base branch: main
Output branch: main
---

# p1468_8 — `followup_kind` in the board's task detail screen

Read `aidocs/framework/tui_conventions.md` before editing.

## Context

t1468 made auto-spawned follow-ups machine-readable (`followup_kind:`) and
painted a coloured glyph on **every board card surface** — `TaskCard`,
`InFlightTaskCard`, `TrailTaskCard`, and the collapsed-group roll-up — all
routed through the shared boundary `followup_kinds.marker_for`.

`TaskDetailScreen` shows **nothing**. Opening a task tells you nothing about
its provenance, and the card glyph is undecodable because the board has no
legend anywhere. Meanwhile `aitask_update.sh --followup-kind` can already set
and correct the field from the CLI — so the surface where a mis-classified
follow-up is actually *noticed* is the one surface that can neither show nor
change it. t1468_6 backfilled ~95 historical follow-ups by heuristic; spot-
correcting those from the board is the natural review loop and it does not
exist.

**Outcome:** a `Follow-up:` row in the detail screen's primary metadata block,
showing the glyph + human label, editable through a picker modal, where
choosing "(none)" *removes* the key.

## Corrections to the task file's premises

The task file was written against assumptions that current source no longer
matches. All four are load-bearing, so the plan below differs from it:

1. **`AnchorField` (`aitask_board.py:4813`) is the mandated pattern, and it is
   not the `save_changes` path.** Its docstring says so verbatim: persist by
   shelling out to `aitask_update.sh --batch <id> --<flag> <val> --silent`,
   notify on nonzero, then `_reload_detail_screen` — "**NOT** the CycleField
   `save_with_timestamp` path". Adopting it dissolves *both* "sharp hazards"
   the task file raises:
   - *"Clearing is not a value assignment"* — `save_changes` (`:6448`) can only
     ever assign, but we never touch it. `aitask_update.sh --followup-kind ""`
     already yields key **removal**: the emit is gated on
     `[[ -n "$followup_kind" ]]` (`aitask_update.sh:814-817`), with no
     `_present` tombstone companion.
   - *"The dirty-check trips on unset"* — only applies to keys seeded into
     `_original_values` (`:6164-6169`). The field stays out of that dict
     entirely, so the Save button cannot light up on open. Structural, not an
     invariant to maintain — but still tested.

   It also **inherits one defect**, addressed by step 4 below: see Concern A.
2. **`CycleField` is not merely awkward at 9 options — it does not fit.**
   `render()` (`:4389-4397`) emits *every* option inline on one row, and
   `.meta-ro`/`CycleField` rows are `height: 1`. `low | medium | high` fits;
   `manual verification | risk mitigation | upstream defect | …` cannot. A
   picker modal is required, not preferred.
3. **`marker_for` was already promoted into `lib/followup_kinds.py`** by
   t1468_5 (the task file's "consider promoting" note is done).
   `_followup_marker` (`:3364`) is now a thin metadata-dict adapter over it.
4. **A cross-field invariant the task file does not mention:**
   `followup_kind: manual_verification` **requires** `issue_type:
   manual_verification` (`lib/followup_kinds_sh.sh:77-84`, checked on the
   *resulting* pair in `aitask_update.sh:2069`). The board cannot set that kind
   on an ordinary task.

## Two concerns raised at plan review — both verified against source

### Concern A — an immediate write on a screen with deferred writes

`TaskDetailScreen` has **two persistence models** and this field introduces the
second one into a screen that previously mixed them only via `AnchorField`:

- The four `CycleField`s are **deferred**: an edit lands in `_current_values`
  (`:6433`), lights `#btn_save` via `_update_save_button` (`:6437-6440`), and
  is written only when the user presses Save.
- `AnchorField` — and now this field — is **immediate**: it writes through the
  shell and then calls `_reload_detail_screen` (`:4662-4665`), which does
  `task.load()` and `app.replace_screen_with_detail(task)`. That constructs a
  **fresh** `TaskDetailScreen`, whose `__init__` re-seeds `_original_values`
  from the reloaded metadata (`:6164-6169`).

**Verified:** cycle Priority `high`→`low` (Save lights up), then set a
follow-up kind → the reload replaces the screen and the pending priority edit
is **silently discarded**, with `#btn_save` back to `disabled`. No warning, no
trace.

**Policy chosen: block the immediate write while the screen is dirty.**
Rejected alternatives:

- *Save first* — auto-committing the user's other pending edits as a side
  effect of touching a different field is a surprising write, and Step 8's
  "explicit acceptance" principle says the same thing about reviews: an
  unrelated action must not become consent.
- *Preserve the draft across the reload* — the most seamless, and the most
  wrong. The reload exists **to pick up external changes** (`save_changes`
  reloads for the same reason, `:6456-6459`); re-imposing a stale draft over
  freshly-read metadata would reintroduce exactly the values another writer
  changed. It also needs a new parameter threaded through
  `open_task_detail` → `replace_screen_with_detail` → `_reload_detail_screen`,
  and `open_task_detail` is the **only** sanctioned construction site —
  `test_board_detail_nested_actions.py:198-212` asserts exactly one
  `TaskDetailScreen(` instantiation exists in the board source.

Blocking makes the loss **impossible** rather than merely unlikely, is local,
and is fully testable. It is not silent: the row's hint changes and `Enter`
notifies with the remedy.

**`AnchorField` has the identical defect and is not fixed here** — it is a
different field, pre-existing, and outside this task's scope. It is recorded as
an upstream defect for Step 8b. The predicate this plan adds
(`TaskDetailScreen.has_unsaved_edits()`) is deliberately field-agnostic so that
follow-up can adopt it without redesign.

### Concern B — the picker's default focus destroys an unrecognised value

**Verified:** with `followup_kind: risk_mitgation` (a typo — exactly the case
the task requires to "degrade visibly"), no picker row is marked current: the
clear row's flag is `not self.current_kind` → `False`, and no vocabulary row
matches. So `on_mount` falls through to `items[0].focus()` — the **clear** row —
and one reflexive `Enter` deletes the value the user opened the screen to
diagnose.

**Fix:** when the current value is present but not in `FOLLOWUP_KINDS`, the
picker (a) names it in the dialog title and (b) focuses the **Cancel button**,
so the default keystroke is a no-op. Non-destructive by construction, and the
diagnostic is where the user is already looking.

## Decisions

| # | Decision | Rationale |
|---|---|---|
| 1 | **Editable**, not read-only | The t1468_6 backfill review loop is the justification the task file gives, and it is the whole reason the field is worth surfacing here. |
| 2 | **Picker modal**, not `CycleField` | Correction 2 — `CycleField` renders all options inline on a 1-cell-high row. Precedent: `GateChoiceScreen` (`:3715`) + `PickerItem` (`:3670`). |
| 3 | **Row 5 of `#meta_editable`**, always visible when editable *(user decision)* | Provenance must be legible the instant the screen opens; the "Tracking & provenance" `Collapsible` is `collapsed=True` by default, which would reproduce the exact complaint. Renders `(none)` when unset so the set-affordance is discoverable. |
| 4 | **Read-only screens show the row only when a kind is set** | A read-only screen offers no way to set one, so an always-shown `(none)` is pure noise. Mirrors `AnchorField`'s own read-only rule (`:6268-6272`) and `_build_risk_fields`' "absent means unset, show nothing". |
| 5 | **Persist via `aitask_update.sh`**, not `save_changes` | Correction 1. Also gets validation, the MV invariant, and `updated_at` for free. |
| 6 | **Offer all 9 options; surface the shell's rejection** *(user decision)* | The MV invariant stays declared in exactly one place. Its message already reads *"Set both together, or choose a different followup_kind."* Re-declaring it in `aitask_board.py` would be a second authority free to drift. |
| 7 | **No new key binding; `Enter` on the focused row** | Follows `AnchorField` exactly. `TaskDetailScreen`'s 24 `BINDINGS` are all screen-level `show=False`; adding a footer-visible key would, per `tui_conventions.md` §"TUI footer must surface every operation", oblige an audit-and-flip of all 24 — scope this task does not own. A widget-level `Enter` with an inline hint is the established affordance for detail fields and adds no binding. |
| 8 | **`render()` returns a Rich `Text`**, not a markup `str` | The glyph's colour must be a *literal* Rich style: it resolves in `render().spans` **and** in composited strips, which is what the colour verification reads (t1468_3). It also makes `render().plain` available, which verification item 6 of the task asks for. Reuses the already-tested `_followup_glyph_text` (`:3388`). |
| 9 | **The picker is blocked while the screen has unsaved `CycleField` edits** | Concern A. Structural prevention over a fragile invariant; the remedy is named in a notification rather than the loss being silent. |
| 10 | **An unrecognised current value focuses Cancel and is named in the title** | Concern B. The default keystroke must not destroy the value the screen exists to diagnose. |

## Files

- `.aitask-scripts/board/aitask_board.py` — the only production file.
- `tests/test_board_detail_followup_kind.py` — new.
- `website/content/docs/tuis/board/reference.md` — extend the existing
  "Follow-up Provenance Glyphs" section and the Task Detail row of the keys
  table (`:416`).

## Implementation steps

### 1. Widen the vocabulary import

`aitask_board.py:66` currently reads:

```python
from followup_kinds import FOLLOWUP_KINDS, UNKNOWN_GLYPH, marker_for
```

Add `label_for` and `normalize_followup_kind`. Do **not** copy the map, the
labels, or the normaliser into the board.

### 2. `FollowupKindPickerItem` + `FollowupKindPickerScreen`

Insert immediately **after `AnchorField` ends (`:4873`)**, so the precedent and
its sibling read together.

```python
class FollowupKindPickerItem(PickerItem):
    """Focusable row for one follow-up kind — or for clearing the field.

    ``kind`` is the value that will be persisted: a vocabulary key, or ``""``
    for the clear row. Dismisses the SCREEN, not itself (``GateChoiceItem``
    :3705) — a row that dismissed itself would leave the modal standing.

    Does NOT define ``on_focus`` / ``on_blur``: ``PickerItem`` owns the focus
    contract and Textual dispatches handlers down the MRO, so both would fire
    (see its docstring at :3670).
    """

    def __init__(self, kind: str, current: bool):
        super().__init__()
        self.kind = kind
        self.current = current

    def render(self) -> Text:
        out = Text("✓ " if self.current else "  ")
        if not self.kind:
            out.append("(none) — not a follow-up")
            return out
        out.append_text(_followup_glyph_text(marker_for(self.kind)))
        out.append(f" {label_for(self.kind)}  ")
        out.append(self.kind, style="dim")   # the raw key, for CLI correlation
        return out

    def on_key(self, event):
        if event.key == "enter":
            self.screen.dismiss(self.kind)
            event.prevent_default()
            event.stop()

    def on_click(self, event):
        self.screen.dismiss(self.kind)


class FollowupKindPickerScreen(ModalScreen):
    """Pick a task's follow-up kind, or clear it.

    Dismisses with the value to persist — a vocabulary key, or ``""`` to clear
    (key removal; there is no tombstone) — or ``None`` on cancel. ``""`` and
    ``None`` are therefore NOT interchangeable: the caller must test
    ``is None``, not falsiness, or a cancel would silently clear the field.

    **An unrecognised current value focuses Cancel, not a row.** A hand-edited
    or future-vocabulary kind matches no row, and the clear row would otherwise
    take default focus — making one reflexive `Enter` delete the very value the
    user opened this dialog to diagnose. The title names the value instead.
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, task_num: str, current_kind: str):
        super().__init__()
        self.task_num = task_num
        self.current_kind = current_kind
        # Present but not in the vocabulary. A direct membership test against
        # the canonical map — not a second copy of the rule.
        self.unrecognised = bool(current_kind) and current_kind not in FOLLOWUP_KINDS

    def compose(self):
        with Container(id="dep_picker_dialog", classes="picker-dialog"):
            # A `Text`, never a markup string: `current_kind` is hand-editable
            # frontmatter, so `followup_kind: "[bold]x"` would otherwise be
            # markup-parsed by Label (markup=True is the default) — silently
            # swallowed at best, `MarkupError` at worst.
            title = Text(f"Set follow-up kind for {self.task_num}:")
            if self.unrecognised:
                title.append("  current value ")
                title.append(self.current_kind, style="bold")
                title.append(" is not a recognised kind")
            yield Label(title, id="dep_picker_title")
            # Clear row first: the common correction after t1468_6's heuristic
            # backfill is "this isn't a follow-up at all".
            yield FollowupKindPickerItem("", not self.current_kind)
            for kind in FOLLOWUP_KINDS:          # canonical declaration order
                yield FollowupKindPickerItem(kind, kind == self.current_kind)
            yield Button("Cancel", id="btn_dep_cancel")

    def on_mount(self):
        if self.unrecognised:
            # Safe default: Enter presses Cancel -> dismiss(None) -> no write.
            self.query_one("#btn_dep_cancel", Button).focus()
            return
        items = list(self.query(FollowupKindPickerItem))
        current = [it for it in items if it.current]
        (current[0] if current else items[0]).focus()

    @on(Button.Pressed, "#btn_dep_cancel")
    def cancel_button(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)
```

`classes="picker-dialog"` is required, not cosmetic: it is what supplies
`overflow-y: auto` (`:7740`), and this dialog has 10 rows plus a title and a
button. Focusing the **current** row (rather than always the first, as
`GateChoiceScreen` does — it has no notion of a current value) means the picker
opens on what the task already is. For an unset task the current row *is* the
clear row, and `Enter` there is a no-op by the `new_kind == self.kind` guard in
step 3 — so every default-focus case is non-destructive.

### 3. `FollowupKindField`

```python
class FollowupKindField(Static):
    """Focusable follow-up-provenance field. Enter opens the kind picker.

    Persists by shelling out to
    ``aitask_update.sh --batch <id> --followup-kind <val> --silent`` — the
    mandated new-field board pattern (see ``AnchorField``), NOT the CycleField
    ``save_with_timestamp`` path. Three consequences, all load-bearing:

    * **Clearing is key removal.** ``--followup-kind ""`` makes the shell's
      emit skip the line (`aitask_update.sh:814-817`); there is no tombstone.
      ``save_changes`` can only ever *assign*, and an assigned ``""`` would
      round-trip back through ``normalize_followup_kind`` as a present-but-
      unrecognised kind, painting `·` on every task the user had just cleared.
    * **The screen cannot go dirty on open.** This field is deliberately absent
      from ``_original_values`` / ``_current_values`` (:6164), so opening a
      task that has no ``followup_kind`` cannot light up the Save button. A
      seeded default in that dict — the shape the other four editable fields
      use — would do exactly that, because the field is legitimately absent on
      most tasks.
    * **The write is immediate, so it is blocked while the screen is dirty.**
      Success reloads the screen (`_reload_detail_screen`), which replaces it
      with a fresh instance and therefore discards any pending CycleField edit.
      ``blocked`` is pushed in by ``TaskDetailScreen._update_save_button``; when
      set, the hint says so and ``Enter`` notifies the remedy instead of
      opening the picker. See the plan's Concern A for the rejected
      alternatives (save-first, draft-preservation).

    The ``manual_verification`` cross-field invariant (it requires
    ``issue_type: manual_verification``, ``lib/followup_kinds_sh.sh:77``) is
    enforced by the shell and its message surfaced verbatim. It is deliberately
    NOT re-declared here: a copy in the board would be a second authority over
    a rule the CLI already owns.
    """

    can_focus = True

    def __init__(self, kind, manager, owner_task, read_only=False, **kwargs):
        super().__init__(**kwargs)
        # Normalised once: frontmatter is type-honest, so a hand-edited list,
        # int or bool arrives here verbatim. "" means "not a follow-up".
        self.kind = normalize_followup_kind(kind)
        self.manager = manager
        self.owner_task = owner_task
        self.read_only = read_only
        self.blocked = False

    def set_blocked(self, blocked: bool) -> None:
        """Called by the screen when its unsaved-edit state changes."""
        if blocked != self.blocked:
            self.blocked = blocked
            self.refresh()

    def render(self) -> Text:
        out = Text("  ")
        out.append("Follow-up:", style="bold")
        out.append(" ")
        marker = marker_for(self.kind)
        if not marker:
            out.append("(none)", style="dim")
        else:
            out.append_text(_followup_glyph_text(marker))
            out.append(" ")
            # `label_for` answers "" for an unrecognised kind; show the raw
            # value then, so a typo is diagnosable from the screen that can fix
            # it. The glyph is already `·` — same degradation as the card.
            out.append(label_for(self.kind) or self.kind)
        if self.read_only:
            return out
        if self.blocked:
            out.append("  (save or revert pending edits first)", style="dim")
        else:
            out.append("  (enter to change)" if marker else "  (enter to set)",
                       style="dim")
        return out

    def on_key(self, event):
        if event.key != "enter" or self.read_only:
            return
        event.prevent_default()
        event.stop()
        if self.blocked:
            self.app.notify(
                "Save or revert your pending changes first — setting a "
                "follow-up kind writes immediately and reloads this screen.",
                severity="warning")
            return
        self._edit()

    def _edit(self):
        task_num, _ = TaskCard._parse_filename(self.owner_task.filename)

        def on_result(new_kind):
            # `is None` is cancel; `""` is an intentional clear. Testing
            # falsiness here would turn every Escape into a clear.
            if new_kind is None or new_kind == self.kind:
                return
            self._apply(task_num.lstrip("t"), new_kind)

        self.app.push_screen(
            FollowupKindPickerScreen(task_num, self.kind), on_result)

    def _apply(self, task_num_bare: str, new_kind: str):
        result = subprocess.run(
            ["./.aitask-scripts/aitask_update.sh", "--batch", task_num_bare,
             "--followup-kind", new_kind, "--silent"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            error = (result.stderr.strip() or result.stdout.strip()
                     or "followup_kind update failed")
            self.app.notify(error, severity="error")
            return
        _reload_detail_screen(self.app, self.owner_task, self.manager)

    def on_focus(self):
        self.add_class("ro-focused")

    def on_blur(self):
        self.remove_class("ro-focused")
```

`on_focus`/`on_blur` are correct **here** (a bare `Static`, exactly as
`AnchorField:4867`) and forbidden in step 2's `PickerItem` subclass. The two
rules are not in conflict — they apply to different base classes.

### 4. `TaskDetailScreen`: the dirty predicate and the push

Two small edits, both in `TaskDetailScreen`:

```python
    def has_unsaved_edits(self) -> bool:
        """True when a CycleField edit is pending an explicit Save.

        Named and field-agnostic on purpose: any field that persists
        IMMEDIATELY must consult it, because a reload replaces this screen and
        drops the pending values. `AnchorField` has the same exposure and
        should adopt this (tracked as an upstream defect, not fixed here).
        """
        return self._current_values != self._original_values

    def _update_save_button(self):
        is_dirty = self.has_unsaved_edits()
        btn_save = self.query_one("#btn_save", Button)
        btn_save.disabled = not is_dirty
        # Immediate-write fields must not fire while a deferred edit is
        # pending. `query`, not `query_one`: the field is absent on a read-only
        # screen with no kind set.
        for field in self.query(FollowupKindField):
            field.set_blocked(is_dirty)
```

`_update_save_button` is the single hook where dirtiness changes — it is called
from `on_cycle_changed` (`:6431-6435`) and from `save_changes` (`:6468`), so the
flag is pushed on the way **in and out** of the dirty state. `is_dirty` is now
derived from the named predicate rather than recomputed, so there is one
definition of "dirty" on the screen.

### 5. Mount it as row 5 of the primary block

In `TaskDetailScreen.compose`, inside `with Container(id="meta_editable")`
(`:6353`), **after** the existing `if is_done_or_ro: … else: …` split — one
yield covering all four combinations:

```python
            with Container(id="meta_editable"):
                if is_done_or_ro:
                    ...                     # 4 existing ReadOnlyFields
                else:
                    ...                     # 4 existing CycleFields
                # Follow-up provenance (t1468_8) — the 5th row of the primary
                # block in both modes, so a card's glyph is decodable the
                # moment the task is opened. Editable only on a live screen
                # with a manager (the reload path needs one); a read-only
                # screen shows the row ONLY when a kind is set, since it
                # offers no way to set one. Mirrors AnchorField (:6264-6272).
                fk_read_only = is_done_or_ro or self.manager is None
                if not fk_read_only or _followup_marker(meta):
                    yield FollowupKindField(
                        meta.get("followup_kind"), self.manager,
                        self.task_data, read_only=fk_read_only,
                        id="ff_followup_kind", classes="meta-ro")
```

Keeping it a single `FollowupKindField` in both modes — rather than a
`ReadOnlyField` for the read-only case — means **one render implementation**,
so the read-only line cannot drift from the editable one. `read_only=True`
suppresses the hint and makes `on_key` inert, which is what "no editable
control" means operationally.

`#meta_editable` sits outside every `Collapsible` and
`test_board_detail_collapsible.py:100` pins that — unchanged here.

### 6. CSS — nothing new

`.meta-ro { height: 1; width: 100%; padding: 0 2; color: $text-muted; }` and
`.meta-ro.ro-focused { … }` (`:7635-7636`) already supply the row layout and
the focus highlight. **No `color:` rule is added** — the glyph's colour is a
literal Rich style from `FOLLOWUP_KINDS`, for the same one-authority reason
`.task-followup-glyph` carries none (`:7649`).

Note `.meta-ro` *does* set `color: $text-muted` on the widget. The literal span
style must win over it — see Risk, and the strip-level probe in Verification 5.

### 7. Docs

`website/content/docs/tuis/board/reference.md`:
- In "Follow-up Provenance Glyphs" (`:150-156`), add bullets: the task detail
  screen carries a `Follow-up:` row using the same glyph and colour, editable
  there — including clearing it, which removes the field; `manual_verification`
  can only be set on a task whose `issue_type` is also `manual_verification`;
  and the row is inert while the screen has unsaved metadata edits, because the
  write is immediate.
- Update the **Task Detail** row of the keys table (`:416`) to name follow-up
  provenance among the editable metadata.

Current-state prose only — no version history, per
`aidocs/framework/documentation_conventions.md`.

## Verification

New module `tests/test_board_detail_followup_kind.py`. Harnesses are lifted,
not reinvented — named per source.

1. **Field render, per value** (`render().plain`; single-widget `CardApp`
   harness from `test_board_followup_glyph.py:309-330`):
   - each of the 8 kinds → its glyph + human label;
   - unset → `(none)` **and** the `(enter to set)` hint;
   - a set kind → the `(enter to change)` hint;
   - `read_only=True` → neither hint;
   - `blocked=True` → the `(save or revert pending edits first)` hint and
     **neither** of the other two;
   - unknown non-empty string → `· <raw value>` (raw value shown, uncoloured);
   - totality: `None`, `""`, `"   "`, `[]`, `{}`, `0`, `True` → all `(none)`,
     i.e. the same three-way rule `marker_for` gives the cards.
2. **Detail screen wiring** (booted `KanbanApp` + `push_screen`, per
   `test_board_detail_collapsible.py:176-207`):
   - `#ff_followup_kind` is inside `#meta_editable` and is the **last** child,
     after the `issue_type` `CycleField` (pins decision 3 and keeps the two
     rows distinct, per the task's design decision 3);
   - **`#btn_save` is disabled on open** for a task *with* a kind and for one
     *without* — the dirty-check regression, asserted rather than assumed;
   - `read_only=True` + kind set → the row renders with no hint, and `Enter`
     pushes **no** screen (`len(app.screen_stack)` unchanged);
   - `read_only=True` + no kind → the row is absent.
3. **The dirty guard** (Concern A — booted screen, both directions):
   - cycle a `CycleField` (e.g. Priority) → `#btn_save` enabled **and**
     `#ff_followup_kind.blocked` is `True` and its hint changed;
   - `Enter` on the field while blocked → **no screen pushed**
     (`len(app.screen_stack)` unchanged) and `app.notify` called with
     `severity="warning"`;
   - press Save → `_update_save_button` re-runs → `blocked` back to `False`
     and `Enter` now pushes the picker. Pins both edges of the toggle, so a
     guard that latched on could not pass;
   - a booted screen with `read_only=True` and no field present → cycling
     nothing and calling `_update_save_button` does not raise (the `query`
     vs `query_one` choice).
4. **Picker** (`FollowupKindPickerScreen`):
   - exactly 9 rows: the clear row first, then `FOLLOWUP_KINDS` in declaration
     order (drift guard — adding a kind to the module without it appearing
     here fails);
   - the row matching the current kind is focused on mount; the clear row is
     focused when the task has no kind;
   - **unrecognised current value (Concern B):** `on_mount` focuses
     `#btn_dep_cancel`, **not** a row; the title names the offending value;
     and — the interaction test — pressing `Enter` immediately after open
     dismisses with `None`, so `_apply` is **never** called and the bad value
     survives. Drive this with a real typo fixture (`risk_mitgation`), not a
     synthetic sentinel;
   - a hand-edited value containing Rich markup (`"[bold]x"`) renders in the
     title verbatim and raises nothing — the `Label(Text(...))` choice;
   - `Enter` on a kind row dismisses with that kind; on the clear row with
     `""`; `Escape` and the Cancel button dismiss with `None`;
   - **`""` vs `None` are not interchangeable** — assert `_apply` is not called
     after `Escape`, and *is* called with `""` after the clear row.
5. **Colour on the composited screen** — lift `_painted` and the probe-`Label`
   technique from `test_board_followup_glyph.py:508-647` (probe colours, not
   static hexes: Textual resolves ANSI names through the app theme). Assert the
   glyph in the detail row is painted in its kind's colour and **not** in
   `.meta-ro`'s `$text-muted` — i.e. the literal span style beats the widget
   CSS `color:`. Carries the in-test negative control (see Post-phase 1).
6. **Narrow width** — composited strips at a narrow terminal; the glyph is
   still painted and the row is not clipped to nothing. Precedent:
   `FollowupGlyphNarrowWidthTests` (`test_board_followup_glyph.py:650`) and
   `MarkNarrowWidthTests` — `render().plain` stays fully populated even when
   the parent clips it away, so a label-level assertion cannot see this.
7. **The subprocess seam** (`DialogSubprocessTestBase` shape,
   `test_board_dialog_subprocess_degrade.py:82-102`: `PropertyMock` for `app`,
   patched `ab.subprocess.run`, no board boot):
   - exact argv for a set: `["./.aitask-scripts/aitask_update.sh", "--batch",
     "9001", "--followup-kind", "risk_mitigation", "--silent"]`;
   - exact argv for a clear — the 5th element is `""`, **not** `"none"`, and
     the flag is present rather than omitted;
   - nonzero return → `app.notify(<stderr verbatim>, severity="error")` **and
     no reload**. Drive this with the real MV-invariant message text;
   - zero return → `_reload_detail_screen` called once.
8. **Live round-trip: set → repaint → clear → repaint.** One test that runs the
   *real* `aitask_update.sh` through `FollowupKindField._apply`, over a booted
   fixture board, asserting **four** things in sequence — the positive control
   first, so the flow cannot pass while the set silently no-ops:

   1. after `_apply(..., "risk_mitigation")`: the task file carries **exactly**
      `followup_kind: risk_mitigation` — the key is present with that value
      (not merely "not absent");
   2. after `manager.reload_task(...)` + a column refresh: the card's
      `.task-followup-glyph` label exists and renders `▲`;
   3. after `_apply(..., "")`: the `followup_kind:` **line is absent** — a
      key-presence probe, in the shape of `has_field` in
      `test_followup_kind_roundtrip.sh:58`, because a value probe cannot tell
      an absent key from an empty one;
   4. after a second reload + refresh: the `.task-followup-glyph` label is
      **gone**.

   Steps 1+3 are the task's verification items 2 and 3; steps 2+4 are its
   "the card glyph updates on the next render", proven in both directions off
   the same real write rather than off a hand-planted metadata value.

   *Setup:* a `board_fixture` tree (which already `git init`s and writes
   `metadata/`), plus `(tree / ".aitask-scripts").symlink_to(<repo>/.aitask-scripts)`
   so the board's relative `./.aitask-scripts/aitask_update.sh` resolves under
   the fixture cwd — the same "real script, temp tree, `TASK_DIR=aitasks`"
   shape as `test_followup_kind_roundtrip.sh:68-70`. Mix in
   `PristineTreeMixin`. **Fallback if `aitask_update.sh` needs more of a real
   repo than the fixture provides:** split into (a) the live set/clear
   round-trip in a plain temp tree (steps 1 and 3, keeping the positive
   control) and (b) the repaint pair driven by a direct file write (steps 2
   and 4). Record which shape shipped in Final Implementation Notes.

   The CLI-side semantics themselves — durability across an unrelated update,
   invalid-kind rejection, the MV invariant in both directions — are already
   pinned by `tests/test_followup_kind_roundtrip.sh` (t1468_1) and are **not**
   duplicated here.
9. `bash tests/run_all_python_tests.sh` — read the **LAST** line for the
   verdict (`set -o pipefail` if piping; an earlier `Results: N passed` line
   belongs to one module, not the suite).
10. **Live board** (`ait board`) in a real terminal: open a real follow-up task
    and confirm the row shows the same glyph and colour as its card; open an
    ordinary task and confirm `(none)`; set, change and clear a kind on a
    scratch task and confirm the card glyph tracks it; cycle a `CycleField`
    and confirm the row goes inert with the warning; attempt
    `manual_verification` on a non-MV task and confirm the shell's message
    appears as an error notification. Also at a narrow width.

**Fixture invariant.** `tests/lib/board_fixture.py` requires `TASK_DIR` to be
the relative literal `"aitasks"` with cwd inside the fixture tree. Seed
`followup_kind` via `FixtureTask(..., extra={"followup_kind": …})` — `extra` is
`dict.update`d over the base frontmatter. Under a fixture tree the board's
`./.aitask-scripts/…` helpers **do not exist**, so every test of `_apply`
except 8 must patch `subprocess.run`; 8 supplies the symlink instead.

Mix in `PristineTreeMixin` for any test that writes to a task file.

## Post-phase (risk mitigations)

Runs after the implementation steps above, before the plan is consolidated.

1. **[colour_over_widget_css_negative_control]** Verification 5 is the only
   thing separating "the glyph paints" from "the glyph paints *in its kind's
   colour*", and it asserts against a widget whose CSS sets a competing
   `color:` — a wrong extraction passes vacuously. Prove it can fail: change
   exactly one entry's colour in `FOLLOWUP_KINDS` (e.g. `risk_mitigation`
   `yellow` → `green`), re-run the colour test, confirm it goes **RED**, and
   record the failing test id and the exact assertion message in Final
   Implementation Notes. Restore the module **byte-identical** and confirm
   GREEN. One mutation, one named failing test — a control that stays green is
   itself the defect.

2. **[clear_path_negative_control]** The clear path is the one behaviour the
   task file calls out as easy to get silently wrong, and Verification 8 is its
   end-to-end proof. Prove that proof can fail, in **both** halves — the two
   failure modes are independent and one mutation cannot expose both:
   - change `_apply`'s clear value from `""` to `"none"` → Verification 8
     step 3 must go RED with the `followup_kind:` line **present**;
   - make `_apply` return early before `subprocess.run` on a *set* → step 1
     (the positive control) must go RED. Without this half, a set that never
     persisted would leave the clear assertion passing vacuously — the exact
     hole this mitigation exists to close.

   Record both failing test ids and messages; restore byte-identical and
   confirm GREEN.

3. **[dirty_guard_negative_control]** The Concern-A guard is the plan's answer
   to a silent data-loss defect, so its test must be falsifiable. Force
   `set_blocked` to a no-op (`return` immediately) and confirm Verification 3's
   blocked-`Enter` assertion goes RED — i.e. the picker opens and the pending
   edit would be lost. Record the failing test id; restore and confirm GREEN.

## Risk

### Code-health risk: low

- The screen now hosts two persistence models — four deferred `CycleField`s and
  one immediate shell-write — coupled only by a `blocked` flag pushed from
  `_update_save_button`. A future field added to `_original_values`, or a new
  path that mutates `_current_values` without going through
  `on_cycle_changed`, would bypass the guard · severity: medium (residual —
  addressed by inline post-phase dirty_guard_negative_control) · → mitigation:
  inline post-phase dirty_guard_negative_control
- The glyph's colour is a literal Rich span style on a widget whose class
  (`.meta-ro`) sets a competing `color: $text-muted`. If the CSS wins, the row
  renders in muted grey and the kind is distinguishable by shape only — which
  silently fails half the acceptance criterion while looking correct
  · severity: medium (residual — addressed by inline post-phase
  colour_over_widget_css_negative_control) · → mitigation: inline post-phase
  colour_over_widget_css_negative_control
- `render()` returns a Rich `Text` where every other `#meta_editable` row
  returns a markup `str`. t1468_3 hit `NoActiveAppError` returning a Rich
  `Text` through `Static.update()` and had to switch to `Content`; this uses
  `render()`, not `update()`, so the conversion path differs — but it is the
  one novel mechanism here · severity: low · → mitigation: none (Verification
  1 renders the widget in a booted app on every value, so the failure mode is
  an immediate hard error, not a silent one)
- One new production file touched, ~170 added lines, mostly in classes copied
  from an in-file precedent; the only changes to existing code are one added
  `yield` in `compose` and three lines in `_update_save_button` · severity: low
  · → mitigation: none

### Goal-achievement risk: low

- "Clearing removes the key" is the requirement most likely to be implemented
  as a plausible-looking near-miss (writing `""` as a value, or `"none"`), and
  both near-misses would then paint `·` on every cleared task — the exact
  defect the field exists to let users fix. The set half is equally
  vulnerable: a set that silently no-ops leaves the clear assertion passing
  · severity: medium (residual — addressed by inline post-phase
  clear_path_negative_control) · → mitigation: inline post-phase
  clear_path_negative_control
- The `manual_verification` kind is unreachable from the board for any task
  whose `issue_type` is not already `manual_verification`, so 1 of 9 picker
  options fails for most tasks by design (decision 6). The mitigation is a
  clear error message rather than prevention · severity: low · → mitigation:
  none (Verification 7 drives the real message; Verification 10 confirms it
  reaches the user as a notification)
- The dirty guard makes the field inert in a state the user can reach without
  understanding why, so a user who does not read the notification may conclude
  the field is broken · severity: low · → mitigation: none (the hint text
  itself states the remedy in the row, and Verification 10 exercises the path
  live)

### Planned mitigations
- timing: post-phase | name: colour_over_widget_css_negative_control | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: a vacuous colour assertion that cannot see the widget CSS colour winning over the literal span style | desc: mutate one FOLLOWUP_KINDS colour, confirm the detail-row colour test goes RED with a named failing assertion, restore byte-identical and confirm GREEN
- timing: post-phase | name: clear_path_negative_control | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: the clear path being implemented as a value assignment ("" or "none") that the end-to-end test cannot distinguish from key removal, and a set that never persists leaving the clear assertion vacuous | desc: mutate _apply's clear value to "none" and separately short-circuit the set, confirming Verification 8 step 3 and step 1 go RED respectively, then restore and confirm GREEN
- timing: post-phase | name: dirty_guard_negative_control | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: the unsaved-edit guard being untested, so a no-op set_blocked would silently reintroduce the pending-edit data loss | desc: make set_blocked a no-op, confirm the blocked-Enter assertion goes RED because the picker opens, then restore and confirm GREEN

## Upstream defect to record at Step 8b

`aitask_board.py:4854-4865` — `AnchorField._apply` calls
`_reload_detail_screen` on success, which replaces `TaskDetailScreen` with a
fresh instance and therefore **silently discards any pending `CycleField` edit**
(priority / effort / status / issue_type) the user had not yet saved. Identical
mechanism to the one this task guards against for `followup_kind`; pre-existing,
in a different field, and out of scope here. The fix is to consult the
`TaskDetailScreen.has_unsaved_edits()` predicate this task adds — no redesign
needed.

## Step 9 (Post-Implementation)

Merge target `main` (current-branch mode, no worktree). Cleanup, archival and
merge follow `task-workflow` Step 9.
