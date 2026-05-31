---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [custom_shortcuts]
created_at: 2026-05-31 16:28
updated_at: 2026-05-31 16:28
boardidx: 70
---

## Origin

Spawned from t876 during Step 8b review.

## Upstream defect

`.aitask-scripts/lib/shortcuts_mixin.py:41` — the mixin's
`self.BINDINGS = register_app_bindings(self._shortcuts_scope, self.BINDINGS)`
reassignment runs in `ShortcutsMixin.__init__` **after** `super().__init__()`,
but Textual 8.2.7 builds the live key-dispatch map (`self._bindings`) from the
**class-level** merged map (`_merged_bindings`, computed in `__init_subclass__`
and copied at `DOMNode.__init__:218`) — which happens *before* the mixin
reassigns `self.BINDINGS`. As a result the reassignment never reaches
`key_to_bindings`, so a user override saved via the `?` editor / Settings tab is
recorded in the registry and shown in the editor but does **not** actually rebind
the live key for any mixin-only scope (e.g. `board`, `board.detail`,
`shared.agent_cmd`).

## Diagnostic context

Verified empirically in Textual 8.2.7 with two minimal cases while implementing
t876:
- `App`/`ModalScreen` + `ShortcutsMixin` with **literal** class `BINDINGS` and an
  override in `userconfig.yaml`: live `_bindings.key_to_bindings` kept the
  **default** key (`a`), not the override (`z`). Appending to `self.BINDINGS` in
  `__init__` was likewise ignored.
- A class-body `BINDINGS = register_app_bindings(scope, [...])` (the pattern used
  by `brainstorm_dag_display.py:450`, and adopted by t876 for the switcher
  overlay): the override **was** baked into the live map (`w`), because
  `_merge_bindings` reads `cls.__dict__["BINDINGS"]` at class-creation time.

So today only class-body-registered scopes (`brainstorm.dag`, `shared.tui_switcher`)
honor overrides at runtime; mixin-only scopes do not.

## Suggested fix

Make `ShortcutsMixin` apply overrides in a way Textual picks up — e.g. rebuild
`self._bindings` from the resolved `BINDINGS` at the end of `__init__` (or in
`on_mount`), or have the mixin write the resolved list to the class `BINDINGS`
before Textual merges. Verify against the real `KanbanApp`/`AgentCommandScreen`
(not just synthetic classes) and add a test that asserts a saved override changes
`key_to_bindings` for a mixin-based scope.

## IMPORTANT — check concurrent work first

While t876 was implemented, a concurrent session had uncommitted edits to
`.aitask-scripts/lib/shortcuts_mixin.py` (+69 lines). That work may already
address this defect — confirm the committed state of `shortcuts_mixin.py` before
starting; this task may be a no-op or need re-scoping.
