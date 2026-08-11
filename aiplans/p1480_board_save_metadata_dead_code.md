---
Task: t1480_board_save_metadata_dead_code.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1480 — Retire two dead/misleading pieces of board save-path code

## Context

`.aitask-scripts/board/aitask_board.py` carries two pieces of code that read as
if they do something they cannot. Neither misbehaves today — this is a
correctness-of-intent fix, surfaced while implementing t1243_10 and recorded in
`aiplans/archived/p1243/p1243_10_group_collapse_and_filtering.md` under
"Upstream defects identified".

**Defect 1 — the `if not user_data: return` guard in `_write_user_layer`
(`:1375-1382`) is vacuous.** `_config_layers()` (`:1361-1373`) always builds
`data` with a `"settings"` key and `_USER_KEYS` is `{"settings"}`, so
`split_config` always returns a truthy `user_data`. Verified live against a real
`TaskManager`: with `manager.settings = {}`, `save_settings()` still writes
`{"settings": {}}` to `board_config.local.json`. The guard never skips, while
telling the reader the local file is written only sometimes.

**Defect 2 — the `auto_refresh_minutes` setter (`:1425-1427`) has zero
callers.** A repo-wide grep over `*.py` / `*.sh` / `*.md` finds no assignment
through it. `KanbanApp._handle_settings_result` (`:11558-11572`) writes through
`self.manager.settings.update(result)` instead, and it must: `SettingsScreen`
dismisses with **two** keys (`auto_refresh_minutes` *and* `sync_on_refresh`),
and `sync_on_refresh` has no property at all. The getter is live — three call
sites (`:6567`, `:7825`, `:7941`).

**Decided semantics (confirmed with the user):** drop the guard; delete the
setter and keep the getter.

**Scope note.** Dropping the guard changes no observable behaviour at any live
call site — that is precisely what makes it dead code. So the tests below pin
the *semantics the guard misrepresented* ("the user layer is always written"),
not the guard's absence. Nothing pins `_write_user_layer` called directly with
an empty payload: no caller can produce one, and asserting on it would convert
a cleanup into a supported — and destructive — private-method contract.

## Implementation

### Pre-phase (risk mitigations)

1. `[prove_the_unchanged_precondition]` In
   `test_an_unchanged_payload_still_writes_the_user_layer`, assert the
   precondition **first**: the on-disk local file parses equal to
   `{"settings": manager.settings}`. Verified to hold for the fixture tree. If
   it ever stops holding, the rejected Option-B body would write anyway and
   `test_negative_control_unchanged_skip_body_stops_the_write` would pass while
   proving nothing.

### 1. `.aitask-scripts/board/aitask_board.py` — drop the vacuous guard

Remove the `if not user_data: return` short-circuit from `_write_user_layer` and
state the contract it misrepresented. Keep the docstring to the durable claim —
no restatement of `_USER_KEYS` / `split_config` mechanics, which can drift:

```python
    def _write_user_layer(self, user_data: dict) -> None:
        """Write `board_config.local.json`; tag a failure `local`.

        Writes UNCONDITIONALLY — there is no "nothing to write" short-circuit.
        A guard on an empty payload used to sit here; it could never fire, and
        it read as "the local file is written only sometimes", which is false.
        """
        try:
            save_local_config(str(local_path_for(str(METADATA_FILE))), user_data)
        except OSError as exc:
            raise MetadataWriteError("local", exc) from exc
```

Behaviour at every live call site (`save_settings`, `save_metadata`) is
unchanged.

### 2. `.aitask-scripts/board/aitask_board.py` — delete the dead setter

Delete the `@auto_refresh_minutes.setter` block (`:1425-1427`) and record why
the property is read-only, so it is not re-added:

```python
    @property
    def auto_refresh_minutes(self) -> int:
        """Read-only view of `settings["auto_refresh_minutes"]`.

        Deliberately has no setter. Settings writes arrive as whole-payload
        updates into `self.settings` (the settings dialog dismisses with several
        keys at once, not all of which have properties), so a per-key setter
        would be a second, partial write path.
        """
        return self.settings.get("auto_refresh_minutes", 0)
```

### 3. `tests/test_board_persistence_seam.py` — pin both contracts

This module already boots a **real** `TaskManager` against a temp tree
(`CallSiteMappingTests._manager`, `:601-608`, patching the module globals
`TASKS_DIR` / `METADATA_FILE`) and owns the one-mutation negative-control idiom
(`NegativeControlTests._under`, `:451-461`). Reuse both.

- **Lift `_manager` from `CallSiteMappingTests` up into `_TreeCase`** (`:166`) —
  a method move, no signature change; `CallSiteMappingTests` inherits it
  unchanged.
- **Amend the module docstring** — it scopes itself to
  `Task.reload_and_save_board_fields`; widen it to the board's disk-write seams
  and name the t1480 addition.

#### `UserLayerWriteContractTests(_TreeCase)`

- `test_a_settings_empty_board_still_writes_the_user_layer` — set
  `manager.settings = {}`, call `save_settings()`, assert the on-disk file
  parses **exactly** `{"settings": {}}`. Direct content oracle, no spy needed
  (the content genuinely differs from the seeded file). This is the refutation
  of the reading the guard invited: *"a settings-empty board leaves
  `board_config.local.json` untouched."* Asserting the whole dict rather than a
  substring also catches a `collapsed_groups` leak from `_settings_for_save`.
- `test_an_unchanged_payload_still_writes_the_user_layer` — the discriminating
  test. Assert the precondition (pre-phase 1), then `save_settings()` with
  settings untouched must still issue the write. Content comparison is **not**
  an oracle here — a `settings`-only round trip re-serializes to identical bytes
  (the point `test_board_columns_seam.py` `:894-898` makes about its own mirror
  control) — so the oracle is a **call-through spy** on `B.save_local_config`
  (never a stub: a stub would disable the write and make the assertion vacuous),
  asserting exactly one call naming `board_config.local.json`.

#### The negative control

One control, in its own `UserLayerNegativeControlTests` class. `_under` turned
out to be hardwired to `B.Task.reload_and_save_board_fields`, so the control
follows its *discipline* (shared `_assert_*` helper on a base, `assertRaises`
pinned to the exact message) rather than calling it — which also avoids churning
the four existing controls:

- `test_negative_control_unchanged_skip_body_stops_the_write` — patches
  `B.TaskManager._write_user_layer` with the rejected Option B (read the local
  file, return when it equals `user_data`) and asserts
  `test_an_unchanged_payload_still_writes_the_user_layer`'s assertion fails.
  This is exactly the "negative control that fails under the other reading" the
  task's Verification section asks for.

#### `AutoRefreshMinutesIsReadOnlyTests(_TreeCase)`

Runtime pins, not a source grep:

- `test_the_getter_reflects_settings` — positive control: set
  `manager.settings["auto_refresh_minutes"] = 7` → the property reads `7`; with
  the key removed it reads the `0` default.
- `test_the_property_has_no_setter` — `type(m).auto_refresh_minutes.fset is
  None`, **and** `m.auto_refresh_minutes = 7` raises `AttributeError` while
  leaving `m.settings` unchanged (so the assertion is about the property, not
  an unrelated failure).

### 4. `tests/test_board_settings_dialog.py` — the surviving write path, live

*Added in review round 1.* Deleting the setter is only safe if the write path
that survives it is proven, and **nothing drove the settings dialog before**:
the tests above pin `save_settings()` at the manager layer, which says nothing
about whether the dialog reaches it. A one-off manual smoke against the user's
own config cannot close that — it leaves no coverage. So this new module drives
the real `KanbanApp` via Pilot over the fixture tree (no user state touched):

- `test_fixture_facts` — `O` opens the modal and the field seeds itself from the
  (surviving) getter at `0`.
- `test_saving_the_dialog_persists_and_notifies` — cycle `0` → `1`, click Save;
  asserts all three effects independently: in-memory `auto_refresh_minutes`, the
  bytes in `board_config.local.json`, and the `Auto-refresh: 1min` notification
  (captured with a call-*through* spy on `app.notify`).
- `test_the_other_dialog_key_rides_along` — `sync_on_refresh` persists too. This
  is the key a per-key setter could not have carried, i.e. the reason the setter
  was deleted rather than wired up.
- `test_cancel_writes_nothing` — without it, the above could pass on a board
  that persists on *any* dismissal rather than on Save.

Uses `PristineTreeMixin`: these tests persist settings, and a leaked
`board_config.local.json` would make the next one boot with the previous test's
value and assert vacuously.

**Proven non-vacuous** by an out-of-tree mutation: with `save_settings` stubbed
to a no-op, `test_saving_the_dialog_persists_and_notifies` fails on the *disk*
assertion (`0 != 1`) while the in-memory one still passes.

## Risk

### Code-health risk: low
- Dropping the guard leaves `_write_user_layer` willing to write whatever
  payload it is handed, including an empty one. No caller can produce that
  today, and the guard was not protection either — an empty payload against a
  non-empty disk file is a *difference*, so even the rejected unchanged-skip
  reading would have written. Deliberately left undocumented and untested rather
  than promoted to a contract. · severity: low · → mitigation: none planned
- Lifting `_manager` into `_TreeCase` touches a helper five existing tests reach
  through. Pure move, no signature change. · severity: low · → mitigation: none
  planned — covered by the full-suite run in Verification.

### Goal-achievement risk: low
- The unchanged-payload control is only discriminating if the in-memory user
  payload really equals the on-disk local file for the fixture tree; if it did
  not, the rejected Option-B body would write anyway and the control would pass
  while proving nothing. · severity: medium · → mitigation: inline pre-phase
  `prove_the_unchanged_precondition`

### Planned mitigations
- timing: pre-phase | name: prove_the_unchanged_precondition | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — the unchanged-payload negative control could pass vacuously | desc: assert the on-disk local file equals `{"settings": manager.settings}` before exercising the write

*A second candidate (`name_the_truncation_corollary` — document the empty-payload
truncation in the docstring) was proposed and then withdrawn on review: writing
it down would create the very private-method contract this task should be
retiring. The scope note above records the decision instead.*

*Reassessed after the inline pre-phase was folded in: it is one precondition
assertion, so the levels above are unchanged.*

## Verification

1. Targeted: `~/.aitask/venv/bin/python -m pytest tests/test_board_persistence_seam.py tests/test_board_settings_dialog.py -q`
   — the new classes and controls green, existing classes unaffected.
2. Dead-setter proof: `grep -rn "auto_refresh_minutes" --include=*.py --include=*.sh --include=*.md .`
   shows no assignment through the property.
3. Full suite: `bash tests/run_all_python_tests.sh` — read the **last** line
   (`PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)`); do not pipe to `tail`
   without `pipefail`.
4. Live smoke (**restores user state** — `aitasks/metadata/board_config.local.json`
   is the user's real local board config):
   a. Record the current value and `cp` the file to the scratchpad.
   b. `ait board` → settings dialog → change the auto-refresh interval; confirm
      the notification and the new value in the file (the `settings.update` +
      `save_settings` write path).
   c. Set it back to the recorded value through the same dialog, then `diff` the
      file against the scratchpad copy to confirm it is restored.

   **Ran (t1480 review round 1).** Driven in a real tmux pane against the real
   repo: modal opened seeded at `0`, cycled to `1`, Save → on-disk
   `auto_refresh_minutes: 1`, header subtitle *and* toast both read
   "Auto-refresh: 1min"; reverted through the same dialog and restored the file
   from the backup — `diff` identical. One observation, not a defect of this
   change: the save also pruned a stale `collapsed_columns` entry
   (`trail-w1`) via `_prune_orphan_collapsed_columns`, which is that helper's
   documented orphan healing — the current board cannot even create such an
   entry (`check_action` disables `toggle_column_collapsed` in the By-Trail
   view). The backup restore put it back.

Step 9 (Post-Implementation) handles archival and merge.

## Post-Review Changes

### Change Request 1 (2026-08-11 14:20)

- **Requested by user:** the plan's only end-to-end verification (the live
  `ait board` settings smoke) was still unrun. Run it, or explicitly accept the
  interactive verification gap.
- **Changes made:** ran it for real, and closed the gap permanently rather than
  accepting it. (a) Drove `ait board` in a tmux pane against the real repo with
  a backup/restore round-trip — result recorded under Verification step 4.
  (b) Added `tests/test_board_settings_dialog.py` (Implementation step 4), so
  the dialog→disk→notification path has standing coverage instead of a one-off
  manual check. Plan Verification step 1 now names both test modules.
- **Files affected:** `tests/test_board_settings_dialog.py` (new),
  `aiplans/p1480_board_save_metadata_dead_code.md`.

## Final Implementation Notes

- **Actual work done:** exactly the approved plan, plus the review-round
  addition above. `_write_user_layer` lost its vacuous `if not user_data:
  return` and gained a docstring stating the unconditional contract;
  `TaskManager.auto_refresh_minutes` lost its zero-caller setter and its getter
  now documents why the property is read-only.
  `tests/test_board_persistence_seam.py` gained `UserLayerWriteContractTests`,
  `UserLayerNegativeControlTests` and `AutoRefreshMinutesIsReadOnlyTests`, with
  `_manager` lifted from `CallSiteMappingTests` to `_TreeCase`.
  `tests/test_board_settings_dialog.py` is new.
- **Deviations from plan:** two. (1) The negative control could not reuse
  `NegativeControlTests._under` — that helper hardwires
  `mock.patch.object(B.Task, "reload_and_save_board_fields", body)`, so it can
  only mutate that one seam. The control follows its *discipline* (shared
  `_assert_*` helper so the real test and the control run identical code;
  `assertRaises` pinned to the exact message) in its own class, which also
  avoids churning the four existing controls. (2) Step 4 (the dialog module) was
  added during review and was not in the approved plan.
- **Issues encountered:** the first live-smoke attempt appeared to show the `O`
  Options binding not working — three presses, no modal. It was not a defect:
  keys were reaching the app (a `ctrl+p` positive control opened the command
  palette), and a clean re-boot with an `escape` first opened the modal on the
  first `O`. The initial session simply had the search input holding focus, so
  `O` was consumed as text. Worth recording because "the key does nothing" was
  the wrong conclusion and nearly became a spurious follow-up task.
- **Key decisions:**
  - **Chose "always write" over "skip when unchanged"** for the guard (user
    decision). The rejected reading survives as the negative control, which is
    what makes the semantics test discriminating rather than merely descriptive.
  - **Deleted the setter rather than routing the dialog through it.**
    `SettingsScreen` dismisses with `auto_refresh_minutes` *and*
    `sync_on_refresh`, and the latter has no property — a per-key setter cannot
    express that payload, so `settings.update()` stays the single write path.
  - **Deliberately did NOT test `_write_user_layer({})`.** An earlier plan
    revision did, on the reasoning that a direct call is the only way to observe
    the guard's absence. Withdrawn on review: no caller can produce an empty
    payload, so pinning it (and documenting the truncation it causes) would
    convert a dead-code cleanup into a supported, destructive private-method
    contract. The tests pin the semantics the guard *misrepresented* instead,
    through the public `save_settings()` seam.
  - **Verified non-vacuity by mutation, out of tree.** Stubbing `save_settings`
    to a no-op makes the dialog test fail on its disk assertion (`0 != 1`) while
    its in-memory assertion still passes — so the disk oracle is live.
- **Upstream defects identified:** None.
