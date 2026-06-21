---
Task: t1018_2_operation_level_restart_running_tab.md
Parent Task: aitasks/t1018_brainstorm_op_restart_dblclick_footer_hygiene.md
Sibling Tasks: aitasks/t1018/t1018_*.md
Archived Sibling Plans: aiplans/archived/p1018/p1018_*_*.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-21 11:32
---

# p1018_2 — Operation/group-level restart on the Running tab

Depends on **t1018_1** (LANDED: per-screen binding model + the gated retry-apply
actions). Adds operation-level recovery on the Running tab using the per-row
`on_key` + render-hint pattern (NOT a footer Binding — user decision).

## Context

An `ait brainstorm` operation (e.g. `synthesize_001`) whose agents abort before
producing output is stuck: today's only recovery surfaces are `w`/`R` (reset/retry
a single *agent*) and the retry-apply actions (which only re-ingest output an
agent already produced). There is **no operation-level restart**. This child adds
two GroupRow actions on the Running tab — *re-run the whole operation fresh* and
*retry only the failed apply step* — and removes the dead `ctrl+shift+x`/`ctrl+shift+y`
chords that t1018_1 deliberately left intact for this re-home.

## Verified current state (re-verified 2026-06-21; brainstorm_app.py = 8848 lines)

All anchors below re-confirmed this pass; they shifted ~18 lines from the original
plan because t1018_1 edited the file. **Two assumptions in the prior draft were
wrong and are corrected below (wizard pre-population; need for a launch-helper
extraction).**

- **Operation/group model:** `GROUP_OPERATIONS` = explore/compare/synthesize/
  module_decompose/_merge/_sync (`brainstorm_schemas.py:78`). A `br_groups.yaml`
  group entry: `operation`, `agents`, `status` (**Waiting|Completed only**),
  `created_at`, `head_at_creation`, `nodes_created`, `subgraph`. Written by
  `record_operation()` (`brainstorm_session.py:232`), patched by
  `update_operation()` (`:282`).
- **Failure is agent-level, not operation-level:** `_TERMINAL_AGENT_STATES =
  {"Error","Aborted","Completed"}` (`brainstorm_app.py:199`);
  `_AGENT_FAILED_STATUSES = ("Error","Aborted")` (`brainstorm_session.py:640`).
  A group stays `Waiting` while its agents fail. "An aborted operation" = a
  `Waiting` group whose `AgentStatusRow`s are `Error`/`Aborted`.
- **Running tab:** `_refresh_status_tab()` (`:7453`) mounts `GroupRow` (`:3115`,
  `render()` `:3132-3150` — currently renders `arrow name op status agents:N
  progress created_at` and has **no focus-based hints**), expands to
  `AgentStatusRow`s via `_mount_group_agents()` (`:7779`). `AgentStatusRow.render()`
  (`:3183`) DOES append focus hints (`w: reset`, `R: retry`) — the pattern to mirror.
- **Focus dispatch / `on_key`** for Running rows lives in `App.on_key` (`:5767`):
  GroupRow `enter` = expand/collapse (`:5856`); AgentStatusRow `w` (`:5887`),
  `R` (`:5904`), `x` (`:5921`). New GroupRow keys slot in here, gated on
  `isinstance(focused, GroupRow)`.
- **Launch path (REUSED WHOLESALE — see correction #2):** `_execute_design_op(result)`
  (`:8372`) seeds worker-handoff attrs and calls the `@work(thread=True)` worker
  `_run_design_op()` (`:8389`), whose per-op `if/elif` chain (`:8418-8535`) calls
  `register_explorer/comparator/synthesizer/...` (`brainstorm_crew.py:579/629/670/…`)
  → `_run_addwork()` (`:125`, subprocess `ait crew addwork`) → `record_operation()`
  (`:8537`). `_run_design_op` mints a **fresh** group name via `_next_group_name(op)`
  (`:8394`), so a re-run produces a *new* group (e.g. `synthesize_002`); the old
  failed group survives until cleaned up.
- **Retry-apply actions (gated by t1018_1, methods + bindings retained):**
  `action_retry_explorer_apply` (`:7255`), `action_retry_synthesizer_apply`
  (`:7405`) — both `_try_apply_*_if_needed(agent, force=True)`;
  `action_retry_initializer_apply` (`:6745`). Their App bindings are still present:
  `ctrl+shift+x` (`:5552`), `ctrl+shift+y` (`:5554`), with the explanatory comment
  at `:5568` ("…bindings stay intact — t1018_2 re-homes…"). t1018_1 added all three
  retry actions to `_TAB_SCOPED_ACTIONS` (`:5561`, consumed by `check_action` `:5674`)
  so they are gated to `tab_running`.

### CORRECTION #1 — the wizard has NO config pre-population (changes Step 3 framing)
`ActionsWizardScreen.__init__(*, op_key, node_id="", marked=None)` (`:3292`) seeds
**only** the operation type, a contextual node, and a marked node-selection. Its
`on_mount` (`:3315-3351`) routes per op-type and then runs the op's config steps
**from scratch** — there is no parameter to pre-fill the explore mandate / compare
dimensions / synthesize merge-rules. It is opened via `push_screen(ActionsWizardScreen(
op_key=op, node_id=node, marked=marked), self._on_wizard_result)` (`:6380`), and
`_on_wizard_result` (`:6385`) calls `_execute_design_op`.

**Consequence:** "re-run fresh" can uniformly re-open the wizard seeded with
`op_key = group_info["operation"]` and `node_id = head_at_creation` for **every**
op-type — that *is* the wizard's existing seed contract, so **no per-op-type
special-casing and no "unsupported types" confirm-modal branch is needed** (the
prior draft's Step 3 hedge is removed). The trade-off: the user **re-enters** the
operation config (it is genuinely re-confirmed, not pre-filled from the old run).
For compare/synthesize the original input-node list is **not** stored in
`br_groups.yaml`, so `marked` starts empty and the user re-selects inputs. This is
acceptable and avoids the fragile alternative (parsing `<agent>_input.md` to silently
reconstruct config — explicitly rejected). The wizard itself is the destructive-action
confirm.

### CORRECTION #2 — no launch-helper extraction needed (drops prior Step 1)
The prior draft's Step 1 extracted the agent-registration loop out of the
`@work(thread=True)` worker to "avoid duplicating launch logic." With the wizard
approach, **neither new action launches agents directly**: "re-run fresh"
dispatches through the *existing* `_execute_design_op` → `_run_design_op` path, and
"retry failed step" calls the *existing* `_try_apply_*` helpers. So there is nothing
to duplicate and nothing to extract. Dropping the extraction also removes the
worker-thread-parity risk the prior draft carried (lowering code-health risk).

## Implementation steps

### Step 1 — GroupRow `on_key` actions + render hints
In `App.on_key` (`:5767`, near the existing GroupRow `enter` handler `:5856` and the
`w`/`R`/`x` AgentStatusRow handlers), add two keys handled when
`isinstance(focused, GroupRow)`:
- **`f`** → re-run whole operation fresh (Step 2).
- **`s`** → retry only the failed apply step (Step 3).

Proposed keys `f`/`s` are plain letters (deliverable per t1018_1; the Running tab has
no focused TextArea). **Confirm during implementation** that neither collides with an
existing Running-tab `on_key` letter — current set is `b`/`w`/`R`/`x`/`enter` plus
nav keys; read the full `App.on_key` body (`:5767`-end) and the app `BINDINGS`
(`:5516`+) before finalizing. Gate the handlers on a *failed* group where sensible
(at least one agent in `_AGENT_FAILED_STATUSES`); otherwise `notify` why the action
is unavailable, mirroring the `w`/`R` "Can only … in Error state" guards.

Add focus-time hints to `GroupRow.render()` (`:3132`), mirroring `AgentStatusRow.render()`
(`:3183`): when `self.has_focus`, append `f: re-run  s: retry-apply` (only when the
group actually has failed agents).

### Step 2 — "Re-run whole operation fresh" (pre-seeded wizard)
On the focused GroupRow, `push_screen(ActionsWizardScreen(op_key=group_info["operation"],
node_id=group_info.get("head_at_creation") or get_head(...), marked=[]), self._on_wizard_result)`.
This reuses ALL launch + validation logic and is itself the destructive confirm.
`_run_design_op` mints a new group name, so this creates a *new* group; then **offer
to clean up the old failed group** by reusing the existing `x` cleanup /
`CleanupAgentModal` pattern (`:867`). Document the rejected alternative (parse
`<agent>_input.md` to silently re-register — fragile reverse-engineering). Per
Correction #1 this path is uniform across all op-types — no special-casing.

### Step 3 — "Retry only the failed apply step" (re-home retry-apply)
From the GroupRow `on_key` action, call the retained `_try_apply_explorer_if_needed`
/ `_try_apply_synthesizer_if_needed` (`force=True`) for the focused group's
relevant agent(s), selecting by the group's `operation` (explore→explorer,
synthesize→synthesizer). Then **remove the now-dead global bindings**
`ctrl+shift+x` (`:5552`) and `ctrl+shift+y` (`:5554`) and update the explanatory
comment (`:5568`); **keep the underlying `action_retry_*`/`_try_apply_*` methods**
(they now back the GroupRow action). Also drop the two action names from
`_TAB_SCOPED_ACTIONS` (`:5561`) since the bindings they gated are gone (leave the
`retry_initializer_apply`/`ctrl+r` entry — see below). **Decide initializer-retry
(`ctrl+r`):** leave it gated as-is (t1018_1) — it targets the session initializer,
not an operation group, so it does not belong on the GroupRow surface. Note the
rationale in the Final Implementation Notes.

### Step 4 — State transition
Key purely off agent states — **no `brainstorm_schemas.py` change**. "Re-run fresh"
creates a new group (Step 2) and the old one is cleaned up on demand, so no
in-place group reset / `update_operation` transition is required. Document this
decision (and that no group-level "failed" badge was added).

### Step 5 — Tests (this child owns them)
- `pilot.press(...)` on a fixture session: a `br_groups.yaml` group whose
  `<agent>_status.yaml` fixtures are in `Error` →
  - `s` calls the apply path (assert via a spy/patch on `_try_apply_*_if_needed`),
  - `f` opens the pre-seeded `ActionsWizardScreen` with the right `op_key`/`node_id`
    (assert the pushed screen's seed, not a live launch).
  - assert the focus hints render on a failed GroupRow and are absent on a clean one.
- Structural/grep assertion: **no `ctrl+shift+x`/`ctrl+shift+y` binding survives**
  anywhere in `brainstorm_app.py`.
- Full brainstorm suite green: `python -m pytest tests/test_brainstorm*.py`.
- Fixtures are ephemeral (artificial `br_groups.yaml` + `<agent>_status.yaml`).

## Risk

### Code-health risk: low
- Both actions reuse existing, exercised paths (the wizard → `_execute_design_op`
  launch path and the `_try_apply_*` helpers); the new code is GroupRow key
  dispatch + render hints + an old-group cleanup offer. No worker-thread extraction
  (Correction #2), no schema change (Step 4). Blast radius is confined to the
  Running-tab dispatch and `GroupRow.render`. · severity: low · → mitigation: TBD
- Removing the `ctrl+shift+x`/`ctrl+shift+y` bindings while keeping their methods
  could leave a dangling `_TAB_SCOPED_ACTIONS` entry or footer label. · severity: low
  · → mitigation: grep assertion in Step 5 + the structural no-chord test.

### Goal-achievement risk: low
- The prior draft's medium goal risk ("wizard may not support pre-population for all
  op-types") is **resolved**: the wizard's seed contract (op-type + node) is uniform
  across all op-types (Correction #1), so re-run fresh works everywhere. The only
  residual is UX — the user re-enters config rather than it being pre-filled — which
  is an accepted, documented trade-off, not a delivery blocker. · severity: low
  · → mitigation: TBD
- Live behavioral proof (real failed agent → re-run actually relaunches & produces
  output; retry-step re-applies) cannot be shown by the headless pilot. · severity:
  low · → covered by the **t1018_4** aggregate manual-verification sibling.

## Verification
- `pilot.press` GroupRow restart tests on failed-operation fixtures green.
- No global retry-apply chord survives (structural assertion).
- Full brainstorm suite green.
- Live: real session, real failed agent → re-run fresh relaunches and produces
  output; retry-step re-applies — covered by **t1018_4**.

## Notes for sibling tasks
- **No launch-helper extraction was done** and **no operation-level failed state was
  added to schemas** — recovery keys off agent states. t1018_3 (double-click) and
  t1018_4 (manual verification) should assume the GroupRow gained `n` (re-run
  fresh) / `i` (retry-apply) actions and that the `ctrl+shift+x`/`ctrl+shift+y`
  chords are gone.
- The wizard's seed contract (op-type + node, no config pre-fill) is the reuse
  surface for any future "relaunch an operation" feature.

## Post-Review Changes

### Change Request 1 (2026-06-21 11:42)
- **Requested by user:** `F`/`S` are a poor choice because `f`/`s` are already
  App-bound (`toggle_deferred` / `tab_session`); using their shift-pairs is a
  muscle-memory hazard.
- **Changes made:** Re-keyed both GroupRow recovery actions to keys whose
  **both cases** are unbound: `n` (re-run fresh) and `i` (retry-apply). Updated
  the `on_key` handlers, the `GroupRow.render()` focus hints, all docstrings/
  comments, and the test presses/assertions/method-names.
- **Files affected:** `.aitask-scripts/brainstorm/brainstorm_app.py`,
  `tests/test_brainstorm_group_recovery.py`. Full brainstorm suite (629) green.

## Step 9 — Post-implementation
Archive via `./.aitask-scripts/aitask_archive.sh 1018_2` (Step 9 of the shared
workflow handles merge + archival). Parent stays active until t1018_3 + t1018_4 land.

## Final Implementation Notes
- **Actual work done:**
  - `brainstorm_session.delete_group(task_num, group_name) -> list[str]` —
    encapsulated one-call cleanup that drops the group entry from
    `br_groups.yaml` *and* removes each agent's `_status`/`_alive`/`_output`/
    `_log` artifacts (same suffix set as the per-agent `x` cleanup), returning
    the agent names actually removed.
  - `GroupRow` gained `has_failed_agent`/`has_completed_agent` flags (computed
    once in `_refresh_status_tab` via `_group_recovery_flags`), focus-time
    render hints (`n: re-run fresh` / `i: retry-apply`), and `on_focus`/`on_blur`
    refresh.
  - Two Running-tab `on_key` actions on a focused `GroupRow`: `n`
    (`_rerun_group_fresh` → pre-seeded `ActionsWizardScreen(op_key, node_id)` →
    existing `_on_wizard_result`/`_execute_design_op`, then `_confirm_cleanup_group`
    offers old-group cleanup) and `i` (`_retry_group_apply` → group-scoped
    `_try_apply_explorer/synthesizer_if_needed(force=True)`).
  - Removed the undeliverable `ctrl+shift+x`/`ctrl+shift+y` bindings and trimmed
    `_TAB_SCOPED_ACTIONS` to just `retry_initializer_apply`.
  - `CleanupAgentModal` generalized with optional `title`/`body` (backward
    compatible) so it confirms the group-level cleanup too.
  - Tests: new `tests/test_brainstorm_group_recovery.py` (pure-unit `delete_group`
    + pilot `n`/`i` dispatch, gating, focus hints, cleanup-modal push, and a
    structural no-chord guard); updated `tests/test_brainstorm_binding_scope.py`.
- **Deviations from plan:**
  - **Keys `n`/`i`, not `F`/`S`** (post-review CR1): `f`/`s` are App-bound, so
    their shift-pairs are a muscle-memory hazard; `n`/`i` are unbound in both
    cases.
  - **Removed** the now-dead global `action_retry_explorer_apply` /
    `action_retry_synthesizer_apply` and their sole helper
    `_pick_completed_agent_for_retry` — the plan said "keep the action methods",
    but the GroupRow retry-apply is *group-scoped* and calls `_try_apply_*`
    directly, so those globals back nothing. Deleting dead code is cleaner than
    leaving it. The `_try_apply_*_if_needed` helpers (used by the pollers and the
    new action) are retained.
  - No launch-helper extraction (Correction #2) and no schema change (Step 4) —
    both decided in the verified plan; the wizard/launch path is reused wholesale.
- **Issues encountered:** the t1018_1 `test_brainstorm_binding_scope.py` asserted
  all three retry actions are gated to `tab_running`; removing two of them made
  `check_action` fall through to its default `True` for the now-unbound names, so
  the Browse/Session `assertIsNone` would fail. Updated that test to assert only
  `retry_initializer_apply` (the GroupRow `i` action is covered by the new file).
- **Key decisions:** keys chosen so both cases are free (no shift-pair hazard);
  `delete_group` added as an encapsulated model method with a rich return value;
  `CleanupAgentModal` reused via optional overrides rather than a duplicate modal.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - Final keys are **`n`** (re-run fresh) / **`i`** (retry-apply) on the Running-tab
    GroupRow. The `ctrl+shift+x`/`ctrl+shift+y` chords are gone.
  - `brainstorm_session.delete_group()` is the canonical group-teardown helper for
    any future "remove an operation group" need.
  - The wizard seed contract (`op_key` + `node_id` only, no config pre-fill) is
    the reuse surface for relaunching an operation.
