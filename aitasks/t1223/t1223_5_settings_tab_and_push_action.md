---
priority: medium
effort: medium
depends: [t1223_4]
issue_type: feature
status: Ready
labels: [tui, ait_settings]
gates: [risk_evaluated]
anchor: 1223
created_at: 2026-07-23 18:32
updated_at: 2026-07-23 18:32
---

## Context

Fifth child of t1223. Adds the **Settings tab** to the syncer: a repo × operation
matrix of the default code agent, with divergence visible at a glance and a push
action to bring repos into agreement. It renders the model from **t1223_4** into
the tab shell from **t1223_1** — it must not re-derive any value itself.

Parent plan: `aiplans/p1223_expand_syncer_scope_version_and_settings_sync.md`.
**Contract D is binding** (effective value, provenance, masked writes).

Depends on t1223_1 (`tab_settings` pane id) and t1223_4
(`lib/cross_repo_settings.py`).

## Key files to modify

- `.aitask-scripts/syncer/syncer_app.py` — fill `TabPane(id="tab_settings")`,
  matrix model, push action + modals.
- `tests/test_syncer_rows.py` — extend.

## Reference files for patterns

- `.aitask-scripts/syncer/syncer_app.py:90-105` (`RowSpec`, **opaque positional
  row keys** recovered via a lookup map — mirror this), `:149-156`
  (`build_labels`), `:426-430` (`check_action`), `:240-260` (`coalesce_request`).
- The Versions tab from **t1223_3** — mirror its row-key scheme (`v0`, `v1`, …)
  and its "resolve shared data once per refresh" rule.
- `.aitask-scripts/settings/settings_app.py:1804-1820` (`LaunchModePickerScreen`)
  and its agent picker — precedent for a value-selection modal.
- `.aitask-scripts/lib/agent_model_picker.py` — model listing for a chosen agent.
- `.aitask-scripts/syncer/sync_failure_screen.py` — compact `ModalScreen`
  precedent.
- `aidocs/framework/tui_conventions.md` — required reading; note the
  render-level verification rule (assert `widget.render().plain`, prefer
  `markup=False`).

## Implementation plan

### 1. Matrix model (pure, unit-tested)

Rows = operations (from `read_operation_defaults`, `-launch-mode` keys already
excluded by t1223_4); columns = discovered repos, labelled with `build_labels()`.
Each cell shows the **effective value + a provenance marker**:

| provenance | marker |
|---|---|
| `local` | value + `(local)` |
| `project` | value (bare) |
| `seed` | value + `(seed)` |
| `builtin` | value + `(default)` |
| `conflict` | `conflict` — **never** a guessed value |

A row where the repos' effective values are not all equal is **highlighted as
divergent**. Build the matrix with a pure helper
(`build_settings_matrix(diff) -> list[SettingsRow]`) so the divergence and marker
logic is testable without a running app. Opaque positional row keys (`s0`, `s1`,
…) + a lookup map, as in `RowSpec`.

The matrix is read via `diff_across_repos(roots)` in a thread worker (it shells
`resolve_agent_string` per repo) — reuse the existing generation-guard /
coalescing pattern; do not add a second one, and do not read it on every keypress.

### 2. Push action

Bound to a key on the Settings tab, gated via `check_action` + `_active_tab()`
(t1223_1) and routed through `ShortcutsMixin` (scope `"syncer"`). Flow:

1. **Source value** — default to the highlighted cell's effective value; allow
   choosing another repo's value for that operation.
2. **Destinations** — multi-select over the other repos. (Multi-select is fine
   here: unlike upgrade, this writes one config key, not framework files.)
3. **Layer prompt (no default).** "Write to the project layer (git-tracked,
   shared) or the local layer (gitignored, personal)?" — always asked, per the
   parent's scope decision. Show what each means in the option description.
4. **`plan_push` per destination** and branch on the typed outcome:
   - `ok` → apply.
   - `noop` → report "already matches", apply nothing.
   - `rejected(reason)` → surface the destination **and its specific reason**;
     apply nothing for that destination. Other destinations still proceed.
   - `masked(masking_value)` → the **three-way prompt, with no default**:
     - *Cancel this destination* — nothing written.
     - *Write to the local layer instead* — `apply_push(..., layer='local')`.
     - *Clear the local override and write project* —
       `apply_push(..., layer='project', clear_mask=True)`.

     The prompt must state the masking value, i.e. "repo B's local layer sets
     `<masking_value>` for `<op>`; a project write would have no effect."
5. **Apply, then refresh** the affected rows. Report a per-destination summary
   (applied / skipped-noop / rejected-with-reason / cancelled) — a single
   "done" is not enough when destinations can diverge in outcome.

### 3. Failure handling

A write raising (fail-closed cases from contract E — invalid destination JSON,
type conflict) must be caught per destination, reported with the destination
name, and must not abort the remaining destinations.

## Verification steps

```bash
bash tests/test_syncer_rows.py
```

Required tests (pure helpers where possible; `App.run_test()` only for render
assertions):

1. `build_settings_matrix` — marker per provenance (`local`/`project`/`seed`/
   `builtin`), and **`conflict` renders the literal `conflict`, never a value**.
2. Divergence flag — all-equal row not flagged; one differing repo flagged;
   a `conflict` cell flags the row.
3. **Render-level** — the settings table's cell text for a known fixture matrix
   equals the expected strings (`widget.render().plain` / cell values), including
   the provenance suffixes.
4. Push wiring: `ok` → `apply_push` called once with the chosen layer;
   `noop` → **`apply_push` not called**.
5. **`masked` three-way routing** — each branch reaches the right call:
   *cancel* ⇒ no `apply_push`; *local* ⇒ `apply_push(layer='local', clear_mask=False)`;
   *clear+project* ⇒ `apply_push(layer='project', clear_mask=True)`. Spy-asserted.
6. `rejected` surfaces the **specific reason string**, and `apply_push` is not
   called for that destination while a sibling `ok` destination still applies.
7. A destination whose `apply_push` raises is reported and the remaining
   destinations still process.
8. Per-tab gating — the push key is inert on `tab_branches` and `tab_versions`.
9. Single-repo mode — with `<2` repos the Settings tab renders the single repo's
   values read-only and the push action is unavailable (nothing to push to).

Manual: covered by t1223_7.

## Notes for sibling tasks

- All value/provenance logic lives in `cross_repo_settings.py` (t1223_4). This
  child renders and routes; if a value looks wrong, fix it there, not here.
- The layer prompt is deliberately unskippable — do not add a "remember my
  choice" shortcut without revisiting the parent's scope decision.
