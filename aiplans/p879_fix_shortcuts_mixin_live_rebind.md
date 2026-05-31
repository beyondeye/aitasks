---
Task: t879_fix_shortcuts_mixin_live_rebind.md
Worktree: (none — fast profile, current branch)
Branch: main
Base branch: main
---

# Plan: Fix `ShortcutsMixin` live key-rebind (t879)

## Context

A user shortcut override saved via the in-TUI `?` editor / Settings tab is
recorded in the registry and shown in the editor, but for **mixin-only scopes**
(`board`, `board.detail`, `shared.agent_cmd`, `monitor`, `codebrowser`,
`applink`, `stats`, `syncer`, `settings`, `brainstorm`, …) it never actually
rebinds the live key — even after the restart the editor instructs.

**Root cause (verified empirically, Textual 8.2.7):**
`ShortcutsMixin.__init__` (`.aitask-scripts/lib/shortcuts_mixin.py:89`) does
`self.BINDINGS = register_app_bindings(scope, self.BINDINGS)` *after*
`super().__init__()`. But Textual builds its live key-dispatch map
`self._bindings` (a `BindingsMap`, keyed `key → [Binding]`) from the
**class-level** merged map in `DOMNode.__init__` (`dom.py:218`), which the
class computed in `__init_subclass__`/`_merge_bindings` (`dom.py:591,671`) by
reading `base.__dict__["BINDINGS"]`. That all happens during `super().__init__()`
— *before* the mixin reassigns the instance attribute. So the reassignment
reaches `resolve_key()` and the editor but never reaches `key_to_bindings`.

Class-body-registered scopes (`brainstorm.dag`, `shared.tui_switcher`) are
unaffected because `register_app_bindings` runs in the class body, so the
override is baked into `BINDINGS` before Textual merges.

**Concurrent-work check (required by the task):** `shortcuts_mixin.py` is
clean in the working tree; the t877 "+69 lines" concurrent edit landed as
commit `afd5b4cb` and only touched the userconfig *reader* (TASK_DIR honoring),
**not** the live-rebind path. The defect at line 89-91 persists. Task is **not**
a no-op.

**Empirical reproduction (both real classes, under a temp userconfig override):**
- `AgentCommandScreen` (`shared.agent_cmd`, override `copy_command: z`):
  `resolve_key → z`, `self.BINDINGS → z`, but live `key_to_bindings`: `z → []`,
  `c → copy_command`, `C → copy_command` (defaults still active).
- `KanbanApp` (`board`, override `create_task: z`): same shape — `z → []`,
  `n → create_task`; shared `?`/`j` present and correct.

## STATUS: deferred (task aborted, priority → low) — 2026-05-31

Planning + empirical validation complete; **implementation not started**. The
task was reverted to `Ready` and deprioritized to `low` after the design
review below. This plan is the durable record for a future pickup. The
recommended approach (surgical `__init__` patch) is decided; the rejected
alternative and its rationale are documented so the decision isn't relitigated.

## Design analysis & approach decision

Two viable designs were evaluated against cleanliness AND safety-for-future-
edits (especially "someone modifies board/TUI code unaware of this mechanism").

### Chosen: surgical patch in `ShortcutsMixin.__init__` (~7/10 cleanliness)

Patch the **instance's** `self._bindings.key_to_bindings` after
`super().__init__()`, moving only the overridden actions off their default key
onto the resolved key. Sets `self.BINDINGS` (instance attr) but leaves the
**class** attr (`KanbanApp.BINDINGS`) as the literal defaults.

- **Pro — lowest blast radius / safest for unaware edits:** because `cls.BINDINGS`
  stays literal, the no-instantiation registration sweep (`shortcut_scopes.py`),
  `_merge_bindings`, and the editor's *default-key* recording all keep seeing
  true defaults — zero interaction with that infrastructure. A board dev who
  adds/renames a `Binding` in `BINDINGS` gets correct override behavior with no
  awareness of the mechanism.
- **Con — Textual-internal coupling:** writes Textual's private
  `_bindings.key_to_bindings`, so it's coupled to that dict's shape across
  Textual upgrades.
- **Narrow pitfalls (all assessed low-risk today):**
  1. If future code **rebuilds/replaces `self._bindings` after `__init__`** (or
     adds a dynamic binding refresh) the patch is dropped. *Verified absent
     today:* `_bindings` is built once in `DOMNode.__init__`; `refresh_bindings()`
     only updates footer/enabled-state (the editor modal's own comment confirms
     it does NOT rebuild); Textual keymaps are unused.
  2. A future mixin inserted **earlier in the MRO** that also mutates `_bindings`
     could violate the "default-key slot still holds this action" assumption.
  3. Textual version coupling (above).
- **Mitigations (part of this plan):** keep the `_bindings` write in ONE
  clearly-commented helper (`_apply_override_keys`) with a `getattr` guard; add a
  note to `aidocs/tui_conventions.md` (where the shortcut-scope rule already
  lives) so anyone touching bindings or `_bindings` is aware.

### Rejected: class-level `__init_subclass__` (cleaner in isolation, ~5/10 here)

Bake overrides into `cls.BINDINGS` *before* Textual's class-level merge (the
task's second suggestion), so Textual's own machinery builds the live map — no
private-internal access, single source of truth. **Confirmed it works at the
dispatch level** (PEP-487 ordering: the mixin's `__init_subclass__` mutates
`cls.BINDINGS` then `super().__init_subclass__()` runs `_merge_bindings`, which
reads the mutated class dict → `_merged_bindings` has the override key, not the
default).

- **Fatal interaction in THIS codebase:** the no-instantiation sweep
  (`shortcut_scopes._load_and_register`) re-registers every mixin class via
  `register_app_bindings(scope, cls.BINDINGS)`, and `register_app_bindings`
  records the editor's **default key** *unconditionally* from the key it's handed
  (`keybinding_registry.py:135`). If `cls.BINDINGS` has been mutated to the
  override keys, the sweep records **the override as the default** → the editor
  shows the wrong default and "reset to default" resets to the override.
- The class-body pattern (`brainstorm.dag`) avoids this only because those
  classes deliberately don't set `_shortcuts_scope`, so the sweep skips them — an
  option the mixin can't take. Fixing it would force changes to
  `shortcut_scopes.py` and/or `register_app_bindings` overwrite semantics —
  exactly the wider, surprising blast radius we want to avoid.

## Approach (recommended — implement on pickup)

Make `ShortcutsMixin.__init__` patch Textual's live dispatch map so the
resolved (override-applied) keys take effect, matching the behavior the
class-body pattern already gives. Surgical remap (not a full rebuild) so
inherited App/framework bindings and sibling bindings are untouched.

### File: `.aitask-scripts/lib/shortcuts_mixin.py`

1. Extend the existing import:
   `from textual.binding import Binding, BindingsMap`

2. Rework `ShortcutsMixin.__init__` to capture the defaults before reassigning,
   then call a new helper:

   ```python
   def __init__(self, *args, **kwargs) -> None:
       super().__init__(*args, **kwargs)
       if not self._shortcuts_scope:
           raise RuntimeError(
               "ShortcutsMixin subclass must set _shortcuts_scope"
           )
       default_bindings = self.BINDINGS
       resolved_bindings = register_app_bindings(
           self._shortcuts_scope, default_bindings
       )
       self.BINDINGS = resolved_bindings
       self._apply_override_keys(default_bindings, resolved_bindings)
   ```

3. Add the helper (key insight: Textual already built `self._bindings` from the
   class defaults; we move only the overridden actions off their default key
   onto the resolved key, matching on `action` so we never disturb a base or
   sibling binding that merely shares a key). `BindingsMap([b])` normalizes a
   single binding's key the same way Textual stores it (e.g. `"?"` →
   `"question_mark"`, compound `"j,down"` → two slots), so we look up the right
   `key_to_bindings` slots:

   ```python
   def _apply_override_keys(self, default_bindings, resolved_bindings) -> None:
       """Re-point Textual's live key-dispatch map at the override keys.

       Textual builds ``self._bindings`` (its live ``key_to_bindings`` map)
       from the class-level merged ``BINDINGS`` inside ``super().__init__()`` —
       before this mixin substitutes user overrides onto the instance — so
       reassigning ``self.BINDINGS`` alone never rebinds the live key (t879).
       Walk the default→resolved pairs and, for each whose key the user
       changed, move that action's binding(s) off the default-key slot onto
       the override-key slot. Class-body-registered scopes don't need this:
       their override is baked into BINDINGS before Textual merges.
       """
       bindings_map = getattr(self, "_bindings", None)
       if bindings_map is None:
           return  # non-DOMNode host: nothing to rebind
       ktb = bindings_map.key_to_bindings
       for default_binding, resolved_binding in zip(
           default_bindings, resolved_bindings
       ):
           default_key = getattr(default_binding, "key", None)
           resolved_key = getattr(resolved_binding, "key", None)
           action = getattr(resolved_binding, "action", None)
           if not action or default_key is None or resolved_key is None:
               continue
           if default_key == resolved_key:
               continue  # no override for this action
           # Drop this action from each (normalized) default-key slot.
           for old_key in BindingsMap([default_binding]).key_to_bindings:
               remaining = [
                   b for b in ktb.get(old_key, [])
                   if getattr(b, "action", None) != action
               ]
               if remaining:
                   ktb[old_key] = remaining
               else:
                   ktb.pop(old_key, None)
           # (Re)add it under each (normalized) override-key slot.
           for new_key, new_bindings in (
               BindingsMap([resolved_binding]).key_to_bindings.items()
           ):
               kept = [
                   b for b in ktb.get(new_key, [])
                   if getattr(b, "action", None) != action
               ]
               ktb[new_key] = kept + new_bindings
   ```

Notes / safety:
- `register_app_bindings` returns exactly one entry per input binding in order
  and never mutates its input, so `zip(default, resolved)` is correctly
  aligned and `default_bindings` stays the unmodified class defaults.
- Shared bindings (`?`, `j`) spliced into an App's BINDINGS resolve their
  override from the `shared` scope via the existing de-dup in
  `register_app_bindings`; with no shared override `default_key == resolved_key`
  → skipped → untouched. A real shared override is remapped live too (desirable).
- `_bindings.copy()` (per-instance, made in `DOMNode.__init__`) shallow-copies
  the dict; the helper only assigns **new** lists / pops keys, never mutates a
  shared list in place — no cross-instance contamination.
- No change to registry `_DEFAULTS` population or `self.BINDINGS` semantics, so
  the editor, `iter_scope_bindings`, and existing tests are unaffected.

### New test: `tests/test_shortcut_live_rebind.py`

Follows the temp-workspace + `keybinding_registry._reset_for_tests()` pattern
from `tests/test_shortcut_editor_modal.py` and `tests/test_shortcut_scopes.py`.
Uses a temp `userconfig.yaml` (via `TASK_DIR` or chdir) so live config is never
touched; constructs the **real** classes (no async pilot needed — `_bindings`
is populated in `__init__`).

- `test_agent_command_screen_override_rebinds_live` — override
  `shared.agent_cmd.copy_command: z`; instantiate `AgentCommandScreen`; assert
  `"z"` slot maps to `copy_command` and the default `"c"`/`"C"` slots no longer
  do.
- `test_kanban_board_override_rebinds_live` — override `board.create_task: z`
  under a temp `TASK_DIR`; instantiate `KanbanApp`; assert `"z" → create_task`,
  `"n"` no longer maps to `create_task`, and shared `question_mark` /`j` slots
  remain intact (regression guard for the splice path).
- `test_no_override_is_noop` — no overrides; assert the default keys are
  unchanged (guards against the helper disturbing the map when nothing changed).

Register fresh shared bindings in `setUp` after `_reset_for_tests()`
(`shortcuts_mixin.register_shared_bindings()`) as the editor-modal test does.

### Doc note: `aidocs/tui_conventions.md`

Add a short note under the existing shortcut-scope rule: mixin-scope overrides
are applied to the live `_bindings` map in `ShortcutsMixin.__init__`
(`_apply_override_keys`). Anyone adding bindings to a `ShortcutsMixin` class
gets this for free; anyone who rebuilds/replaces a host's `self._bindings`
after construction must re-run that step or the override is lost. This is the
discoverability mitigation for the surgical approach's narrow pitfalls.

## Verification

1. New test: `bash tests/run_all_python_tests.sh` (or
   `python3 tests/test_shortcut_live_rebind.py`) — all pass.
2. Regression — related suites must still pass:
   `python3 tests/test_shortcut_editor_modal.py`,
   `python3 tests/test_shortcut_scopes.py`,
   `bash tests/test_keybinding_registry.sh`,
   `python3 tests/test_board_view_filter.py`.
3. End-to-end (gold standard): with a `board.create_task: z` override in
   `aitasks/metadata/userconfig.yaml`, drive `KanbanApp` via
   `app.run_test()` and confirm pressing `z` triggers New-Task while `n` does
   not — confirms no late `_bindings` rebuild clobbers the `__init__` patch.

## Step 9 (Post-Implementation)

Standard task-workflow archival/merge per `task-workflow-fast-/SKILL.md` Step 9.

## Cross-agent follow-up

This fixes only the Claude Code source tree's Python lib (`.aitask-scripts/lib/`),
which is shared by all agents (not a skill/`.md.j2`), so no per-agent skill port
is needed. No goldens, no `.md.j2`, no sourced-bash-lib change → no
`test_scaffold.sh` / `aitask_skill_verify.sh` impact.
