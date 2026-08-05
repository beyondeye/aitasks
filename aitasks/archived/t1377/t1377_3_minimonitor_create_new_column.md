---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: [t1377_2]
issue_type: feature
status: Done
labels: [aitask_monitormini, aitask_board, board_columns, tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1243
implemented_with: claudecode/opus5
created_at: 2026-08-04 09:55
updated_at: 2026-08-06 00:29
completed_at: 2026-08-06 00:29
---

## Context

t1377_2 lets minimonitor move a task to an **existing** board column. This child
adds "create a new column". It is sequenced after deliberately: column creation
exists **only** inside the board TUI today, so it needs a headless config-writer
before any UI, and that writer softens a stance the framework currently advertises.

Parent acceptance criterion 3 is satisfied by this child (the alternative was an
explicit deferral; the user chose to build it).

## Key Files to Modify

- **`.aitask-scripts/lib/board_columns.py`** — add `generate_col_id`,
  `PALETTE_COLORS`, `create_column`, and the single definition of
  `_PROJECT_KEYS` / `_USER_KEYS`.
- **`.aitask-scripts/board/aitask_board.py`** — import `generate_col_id` /
  `PALETTE_COLORS` / the key sets back instead of defining them.
- **`.aitask-scripts/settings/settings_app.py`**, **`.aitask-scripts/stats/stats_config.py`**
  — import the shared key sets.
- **`.aitask-scripts/aitask_board_column.sh`** — add `create`.
- **`.aitask-scripts/monitor/monitor_shared.py`**, **`minimonitor_app.py`** — the
  "New column…" row and the title-entry modal.

## Reference Files for Patterns

- `aitask_board.py` `ColumnEditScreen._generate_col_id` — the slug generator to
  lift. It strips non-ASCII, maps `[^a-z0-9]+` -> `_`, trims, truncates to 20 and
  uniquifies with `_2`, `_3`. Because of that it can **never** emit `|`, CR or LF —
  the property the work-report protocol depends on. Preserve it.
- `aitask_board.py` `PALETTE_COLORS` — the 8-entry palette.
- `aitask_board.py` `TaskManager.save_metadata` — shows the project/user split via
  `split_config(..., project_keys=_PROJECT_KEYS, user_keys=_USER_KEYS)`. Note it
  writes **both** layers; `create_column` must not.
- `lib/config_utils.py` — `load_layered_config`, `split_config`,
  `save_project_config`, `local_path_for`.
- `monitor_shared.py` `TaskNumberInputModal` — the shape to copy for a title-entry
  modal (Input, OK/Cancel, `.narrow` block, `on_input_submitted`).
- `aitask_board.py` `ColumnEditScreen.save` — the empty-title behaviour to mirror:
  notify "Title is required" and **return without dismissing**.

## Implementation Plan

### 1. Headless config writer

Add to `lib/board_columns.py`:

```python
def generate_col_id(title, existing_ids) -> str
PALETTE_COLORS: list[tuple[str, str]]
def create_column(root, title, color=None) -> str   # returns the new col_id
```

**The write must not flatten the layers.** `load_layered_config` returns the
**merged** dict (project <- `.local`). Writing that merged dict back through
`save_project_config` would leak the user-level `settings` block into the tracked
`board_config.json`; and a careless mirror of `save_metadata()` would clobber
`board_config.local.json`. `create_column` touches `columns` + `column_order` only:
run `split_config(merged, project_keys=_PROJECT_KEYS, user_keys=_USER_KEYS)` and
write **only the project layer**, leaving the local file untouched on disk.

### 2. Single-source the key sets

`_PROJECT_KEYS` / `_USER_KEYS` are currently **triplicated**: `aitask_board.py`,
`settings_app.py` (as `_BOARD_PROJECT_KEYS` / `_BOARD_USER_KEYS`) and
`stats_config.py`. Define them once in `lib/board_columns.py` and have all three
import — derive, don't duplicate.

### 3. Board re-imports

`aitask_board.py` imports `generate_col_id` and `PALETTE_COLORS` back, the same way
it already re-imports `board_ordering` and `topic_semantics`. `ColumnEditScreen`
keeps its staticmethod as a thin delegate or drops it in favour of the import —
either is fine as long as there is one implementation.

**Add the first tests for the slug generator** — `_generate_col_id` has none today.

### 4. Wrapper + UI

- `aitask_board_column.sh create --root R --title T [--color C]`, emitting
  `CREATED:<col_id>|<title>` or `ERROR:<reason>`.
- `ColumnPickerModal` (from t1377_2) gains a trailing `+ New column…` row.
  Selecting it opens the title-entry modal, then creates and moves in one gesture.
- **Empty / whitespace-only title is rejected in place**: warn and keep the modal
  open, mirroring `ColumnEditScreen.save`. Never silently dismiss.
- Every new modal ships a `.narrow` variant (ctor kwarg -> `add_class("narrow")`
  first in `compose()` -> `ClassName.narrow` CSS block).

### 5. `ait settings` stance — record the decision, do not change it

`settings_app.py` labels the Columns section "read-only — edit via board TUI". A
headless writer now exists, so that label is no longer forced by capability.
**Flipping the settings TUI to editable is out of scope for this child** (the user
scoped it to minimonitor). Record the decision explicitly in the Final
Implementation Notes; if it should change, that lands as the separate
`settings_columns_editable` follow-up, not as scope creep here.

Note also `aidocs/framework/tui_conventions.md`: a runtime TUI may **write**
project-level config but must never `git commit` / `./ait git push` from an event
handler.

## Verification Steps

```bash
shellcheck .aitask-scripts/aitask_board_column.sh
bash tests/test_board_column_cli.sh
bash tests/run_all_python_tests.sh     # read ONLY the last line for the verdict
```

Tests:

- slug generation: emoji/non-ASCII stripped, collisions uniquified, 20-char cap,
  empty title -> `"column"`, and an explicit assertion that no output can contain
  `|`, CR or LF.
- **Layered round-trip fixture** — seed a tree whose `board_config.json` carries an
  extra unrelated project key and whose `board_config.local.json` carries a
  populated `settings` block (`collapsed_columns`, `auto_refresh_minutes`). After
  `create_column`, assert: (a) the new column is in the project layer; (b) the
  unrelated project key survives verbatim; (c) `settings` did **not** appear in the
  project file; (d) `board_config.local.json` is **byte-identical** to before. A
  happy-path creation test alone passes even when the split is wrong.
- **Narrow render of the title modal** at 40 columns on composited screen text, with
  the `.narrow`-removal negative control.
- **Empty-title path**: submitting blank keeps the modal mounted, emits the warning,
  and creates nothing.

## Coordination

Depends on t1377_2. Touches `aitask_board.py` only for imports — a small surface,
but that file is edited by other in-flight tasks: re-read before editing, stage
explicit paths, never `git stash` / `git add -A` in this shared checkout.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-05T20:45:11Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-05T21:26:50Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-08-05T21:28:41Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:95fbd9646c7ee6a5

> **✅ gate:risk_evaluated** run=2026-08-05T21:28:41Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1377_3/risk_evaluated_2026-08-05T21:28:41Z-risk_evaluated-a1.log`
