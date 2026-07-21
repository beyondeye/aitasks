---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: high
depends: [t1186_3]
issue_type: enhancement
status: Implementing
labels: [tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1149
implemented_with: claudecode/opus4_8
created_at: 2026-07-20 19:30
updated_at: 2026-07-21 12:32
---

## Context

Final slice of t1186 (chatlink wizard live allowlist pickers). Builds on t1186_1
(per-dimension authorization modes + `policy.effective_posture()`), t1186_2
(`allowlist_fetch.run_allowlist_fetch` + `dedupe_ids` / `invalid_snowflakes` helpers),
and t1186_3 (step reorder: token + live check now precede the allowlist; derived step
numbering; class-declared `needs_seams`). Rebuilds `AllowlistScreen` into the
authorization step: per-dimension mode selectors, live Discord-backed multi-select
pickers for members and roles, manual entry preserved as the always-available fallback,
and config-time ID validation.

## Key files to modify

- `.aitask-scripts/chatlink/wizard.py`:
  - `WizardSeams` (:68-79): add `allowlist_fetch_runner: Callable | None = None`;
    `resolve_seams()` (:82-94) defaults it to `allowlist_fetch.run_allowlist_fetch`.
  - `AllowlistScreen` (:255-287) rebuild (details below); `needs_seams = True`.
  - `initial_state()` (:97-122) and `build_edits()` (:125-144): round-trip the six new
    keys — `user_authorization_mode`, `role_authorization_mode`, `allowed_user_ids`,
    `denied_user_ids`, `allowed_role_ids`, `denied_role_ids` (a dimension's inactive
    list is preserved, never cleared).
  - `SummaryScreen._summary_text()` (:523-545, allowlist line :531/:536): replace the
    single concatenated allowlist line with per-dimension lines —
    `users: <mode>: <ids or (none)>` / `roles: <mode>: <ids or (none)>`.
- `.aitask-scripts/chatlink/chatlink_app.py` (:109-129, :167-175): accept/store/wire an
  `allowlist_fetch_runner` init param (test seam), passed into `WizardSeams` in
  `action_wizard`.

## Pinned screen state model (from planning review — implement exactly)

The screen owns four working lists (`allowed_user_ids`, `denied_user_ids`,
`allowed_role_ids`, `denied_role_ids`) plus the two modes. Each ID `Input` always
displays/edits exactly the active-mode list of its dimension and relabels with the mode
("allowed user ids" ↔ "denied user ids"; same for roles).

- **Mode toggle** (two `CycleField`s — precedent: the deny-mode field,
  `lib/profile_editor`, already imported at wizard.py:38-42 — one per dimension):
  parse the Input into the OUTGOING mode's working list, then load the Input from the
  INCOMING mode's list. Both lists survive round-trip toggling; nothing is cleared.
- **Fetched SelectionLists**: selected-state is recomputed from the newly active list on
  every toggle; the selection-change handler reads the dimension's mode at event time so
  a selection can never write to an inactive list (stale-event guard).
- **Filtering** only narrows visible rows; it never mutates selection or lists.
- `_accept()` parses both Inputs into their active lists and writes all four lists +
  both modes into wizard state (Back/Next retention via the shared state dict).

## Picker behavior

- "Fetch from Discord" `Button`, disabled unless `state["provider"] == "discord"`;
  token from `state["token"] or seams.token_reader()`.
- Thread worker + generation-token guard copied from the `LiveCheckScreen` pattern
  (wizard.py:409-453): pure `work()` (no widget access) calling the seam runner,
  `self.app.call_from_thread(self._apply_results, gen, results)`, `_apply_results`
  early-returns on stale generation or `not self.is_attached`.
- On results: two `SelectionList`s (members, roles; entry label `"{name} ({id})"`,
  value=id; follow the `aitask_board.py:3097-3143` Selection/SelectionList precedent)
  with a filter `Input` narrowing entries; entries whose id is already in that
  dimension's active-mode Input start selected. Selection changes rewrite that Input:
  (manually-typed ids not in the fetched set, preserved) ∪ (selected fetched ids).
  Show a truncation notice when `members_truncated`.
- Advisory failure: per-stage sanitized error line (`members_error` / `roles_error`);
  manual entry always works (offline / no token / non-Discord provider / fetch failure)
  and a failed fetch never blocks Next.

## Validation and warnings in `_accept()`

- Always `dedupe_ids` (from `allowlist_fetch`). When provider == discord and
  `invalid_snowflakes` is non-empty → inline error naming the bad tokens; DO NOT
  advance (hard block — a typo'd id would otherwise silently never match). Non-Discord
  providers: dedupe only.
- The one-shot empty-warning becomes posture-aware via `policy.effective_posture()`
  over the screen's working values (same helper preflight uses — no duplicated posture
  logic): `deny_all` → "nobody will be able to open a bug report" (wording names the
  degenerate mixed cases: "the empty <dimension> allowlist denies everyone");
  `open_members` → "any channel member will be able to open a bug report"; press Next
  again to accept (keep the `_warned_empty`-style one-shot flag). `restricted`
  advances silently.

## Reference files for patterns

- Thread worker + gen guard: `wizard.py:374-456` (`LiveCheckScreen`); its mid-run
  dismiss test: `tests/test_chatlink_tui.sh:514-562` (app4, Event-blocked runner).
- Fake runner spy seam: `tests/test_chatlink_tui.sh:253-275` (`wiz_spy_live`,
  `make_wizard_app`).
- SelectionList multi-select modal: `.aitask-scripts/board/aitask_board.py:3097-3143`.
- One-shot warning flag: `wizard.py:258-260, 276-287`.

## Implementation plan

1. Seam plumbing (`WizardSeams`, `resolve_seams`, `chatlink_app.py`).
2. State model: six-key round-trip in `initial_state`/`build_edits`.
3. Screen rebuild: mode CycleFields + relabeling Inputs + toggle semantics.
4. Fetch worker + SelectionLists + filter + write-back.
5. Validation + posture-aware one-shot warning.
6. Summary per-dimension lines.
7. TUI tests.

## Verification

`tests/test_chatlink_tui.sh` — injected fake fetch-runner spy: not called before Fetch;
called with entered token/channel ids; results populate SelectionLists; toggling a
selection rewrites the Input; manually-typed ids survive fetch+selection; fetch failure
degrades to manual entry and still advances; invalid snowflake blocks advance with
error; dedupe on accept; posture-aware warnings for deny_all (incl. one mixed
degenerate posture) and open_members; saved config round-trips both modes + all four
lists end-to-end. REQUIRED state-model tests (from review):
1. mode-toggle-after-selection — fetch, select entries, toggle the dimension's mode;
   assert the selection landed only in the previously active list and the Input now
   shows the other list;
2. filter-after-toggle — filter, toggle; assert no selection or list mutation from
   filtering;
3. toggle round-trip — allowed→denied→allowed preserves both lists exactly;
4. Back/Next retention — leave and re-enter the screen; assert all four lists + both
   modes are retained and re-displayed correctly.
All other chatlink test files stay green.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-21T09:32:31Z status=pass attempt=1 type=human
