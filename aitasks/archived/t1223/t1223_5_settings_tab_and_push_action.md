---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: medium
depends: [t1223_4]
issue_type: feature
status: Done
labels: [tui, ait_settings]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [1297, 1298, 1299]
assigned_to: dario-e@beyond-eye.com
anchor: 1223
implemented_with: claudecode/opus5
created_at: 2026-07-23 18:32
updated_at: 2026-07-28 17:30
completed_at: 2026-07-28 17:30
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
| `builtin` | value + `(default)` |
| `conflict` | `conflict` — **never** a guessed value |

> **Amended by t1223_4: there is no `seed` row.** The ground-truth resolver has
> no seed tier (`--agent-string` → local → project → `DEFAULT_AGENT_STRING`);
> `seed/` is a setup-time copy source. Rendering a `seed` marker would display a
> value the repo does not use. `read_operation_defaults` never returns it.

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

1. **Source value** — an explicit RadioSet step listing each repo with its
   effective value for the highlighted operation.

   > **AC deviation (user-confirmed, 2026-07-28): the source is chosen
   > explicitly, not taken from "the highlighted cell".** t1266 landed after
   > this task was written and binds `left`/`right` App-level with
   > `priority=True` to switch tabs "regardless of what holds focus"; and
   > `aidocs/framework/tui_conventions.md:182` instructs DataTables to use
   > `cursor_type="row"` precisely so they do not consume ←/→. A cell cursor
   > could therefore never be moved horizontally by keyboard, so "the
   > highlighted cell" is unreachable. The table uses `cursor_type="row"`
   > (rows = operations) and the picker preselects the **first eligible** repo.
   >
   > **Only eligible repos are offered.** A repo whose cell is `conflict` or
   > `unavailable` is excluded: `plan_push` matches against `value or ""`, so an
   > unusable source does not raise — it returns `malformed_agent_string` for
   > *every* destination, blaming the value the user picked rather than
   > reporting that none existed. When no repo has a usable value the push key
   > is dimmed and the action notifies instead of opening the flow.
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

   **Also handle `PushPartialError`** (added by t1223_4): `apply_push(...,
   clear_mask=True)` writes two files, and if the project write lands but the
   local clear fails it raises this instead of succeeding. The destination's
   *effective* value is unchanged (the mask still applies), so report it as
   "retry to finish", not as success and not as a plain failure — a retry
   converges because the project write is idempotent and `plan_push` still
   reports `masked`.
5. **Apply, then refresh** the affected rows. Report a per-destination summary
   (applied / skipped-noop / rejected-with-reason / cancelled) — a single
   "done" is not enough when destinations can diverge in outcome.

### 3. Failure handling

A write raising (fail-closed cases from contract E — invalid destination JSON,
type conflict) must be caught per destination, reported with the destination
name, and must not abort the remaining destinations.

## Verification steps

```bash
python3 tests/test_syncer_rows.py
```

Required tests (pure helpers where possible; `App.run_test()` only for render
assertions):

1. `build_settings_matrix` — marker per provenance (`local`/`project`/
   `builtin`), and **`conflict` renders the literal `conflict`, never a value**.
   (No `seed` case — amended by t1223_4.)
2. Divergence flag — all-equal row not flagged; one differing repo flagged;
   a `conflict` cell flags the row; an `unavailable` column is **excluded** from
   the comparison (one broken repo must not flag every row).
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
10. **Row-state gating** — with no selectable row (matrix not loaded, or empty)
    and on a row where no repo holds a usable value, the push key is **dimmed**
    (`None`, not `False`) and `action_push_setting()` **invoked directly**
    notifies without opening the flow. `check_action` gates the key binding, not
    the method, and this suite calls actions directly.
11. **Source/destination roles** — the picker offers only eligible source repos
    and preselects the first eligible one; the destination list excludes the
    chosen source and is **not** filtered by source-eligibility (a conflicted
    repo is a valid, and valuable, destination).
12. **Per-repo degradation** — one corrupt repo renders `unavailable` while the
    others still render; a repo that breaks between the probe and the retry
    costs only its own column; a failure that cannot be attributed marks **no**
    repo and terminates within the stated attempt bound.
13. **Planning-phase isolation** — a destination whose `plan_push` raises is
    reported and the remaining destinations are still planned and applied.

Manual: covered by t1223_7.

## Notes for sibling tasks

- All value/provenance logic lives in `cross_repo_settings.py` (t1223_4). This
  child renders and routes; if a value looks wrong, fix it there, not here.
- The layer prompt is deliberately unskippable — do not add a "remember my
  choice" shortcut without revisiting the parent's scope decision.

### Landed with t1223_4 — read before wiring the tab

- **Index by `sess.key` directly.** `diff_across_repos` keys on
  `os.path.realpath` with the same `OSError` fallback as
  `AitasksSession.key`, and a test pins the two together — no mapping layer.
- **Never call `resolve_agent_string` on a foreign root yourself.**
  `lib/agent_string.sh` documents `METADATA_DIR` / `TASK_DIR` /
  `DEFAULT_AGENT_STRING` as caller overrides; they are inherited by the
  subprocess and outrank `cwd`, so an unscrubbed call makes every repo resolve
  against the same config. Go through `cross_repo_settings`, which scrubs them.
- **`diff_across_repos` / `read_operation_defaults` raise
  `DestConfigUnreadable`** when a repo's config layer exists but is corrupt (the
  shell resolver silently falls through to the builtin default for a malformed
  file, so this is the only way it surfaces). Catch it **per repo** in the matrix
  worker — letting it propagate would blank the whole tab because one repo is
  broken. Rendering that repo's column as unavailable is this child's call; the
  seam deliberately does not invent a provenance value for it.

  > **AC deviation (user-confirmed, 2026-07-28): "catch it per repo" is not
  > achievable by calling `diff_across_repos`.** It reads every root's layers in
  > one unguarded loop (`cross_repo_settings.py:294-295`), so **one corrupt repo
  > aborts the entire call** and no matrix is returned at all — its own docstring
  > says callers wanting per-repo degradation must loop `read_operation_defaults`
  > themselves. Implemented syncer-side as a **bounded shrink-and-retry loop**
  > (`_read_settings_matrix`): the happy path costs exactly one call; on a raise
  > a probe sweep names the offender(s), their columns render `unavailable`, and
  > the call is retried with the rest. Each round either removes ≥1 attributable
  > offender or spends a single non-attributable retry, bounding it at
  > `len(sessions) + 2` attempts. A repo that breaks *between* the sweep and the
  > retry costs only its own column, and a failure the sweep cannot attribute
  > marks **no** repo — it surfaces as a tab-level notice instead of invented
  > blame. Moving this into the seam as
  > `diff_across_repos(roots, *, skip_unreadable=True)` is the confirmed "after"
  > mitigation `cross_repo_settings_skip_unreadable`.

## Coordination — t1267

`t1267_syncer_settings_tab_nav_coordination` is t1266's "after" mitigation and
names this task directly: *"If t1223_5 has already landed by the time this task
is picked, replace step 1 with the actual fix: extend `TAB_LIST_IDS` / the
fall-through conditions and add a test asserting the Settings pane's focusable
widgets still receive their arrow keys."*

This task did both: `TAB_LIST_IDS` gained `"tab_settings": "settings"`, and
`test_arrows_in_a_settings_modal_do_not_switch_tabs` pins the modals' arrows. No
fall-through change was needed — the settings modals are *pushed screens*, and
`check_action`'s blanket `len(self.screen_stack) <= 1` gate already disables
every nav action there. **t1267's substantive scope is therefore satisfied**;
it is left open for the user to verify and dispose of.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-28T09:29:34Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-28T12:46:05Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-07-28T14:30:06Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:6e48705521ef3f52

> **✅ gate:risk_evaluated** run=2026-07-28T14:30:06Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1223_5/risk_evaluated_2026-07-28T14:30:06Z-risk_evaluated-a1.log`
