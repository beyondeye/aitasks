---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [agentcrew, ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-26 14:30
updated_at: 2026-04-26 16:40
---

## Context

Bug at Layer B in the t653 chain (see `aiplans/p653_brainstorm_import_proposal_hangs.md`).

Today the brainstorm TUI's `_poll_initializer()` (`brainstorm_app.py:3172`) is one-shot: it sets `_initializer_done = True` and stops the 2-second polling timer the first time it sees `Completed`, `Error`, or `Aborted`. On `Error` it surfaces a transient toast and never polls again. There is no detection on TUI reopen of "output file present + n000_init still placeholder" — `_load_existing_session()` re-reads `br_nodes/n000_init.yaml` (still the placeholder description "Imported proposal (awaiting reformat): …") and never re-attempts apply. Verified against session 635: `initializer_bootstrap_output.md` has been valid 794 lines on disk for hours, and the dashboard still shows the placeholder.

This child makes the TUI self-healing: on every session load (including re-open), if there is an output file and the node is still a placeholder, retry `apply_initializer_output()`. On Error, keep polling (at a longer interval) for the output to appear. Surface apply failures via a persistent banner widget — not a fading toast — pointing the user at `ait brainstorm apply-initializer <session>` (the retry CLI is added by sibling t653_2).

## Key Files to Modify

- `.aitask-scripts/brainstorm/brainstorm_app.py` — `_load_existing_session()` (find via grep), `_poll_initializer()` (line 3172), new method `_try_apply_initializer_if_needed()`, new key-binding handler `action_retry_initializer_apply()`, banner widget mount/update logic
- `.aitask-scripts/brainstorm/brainstorm_session.py` — new helper `n000_needs_apply(task_num: int | str) -> bool`

## Reference Files for Patterns

- `apply_initializer_output()` at `brainstorm_session.py:264` — the function we need to re-invoke
- `read_proposal()` and `read_node()` in `brainstorm_dag.py` — for inspecting node state
- `NodeDetailModal.on_mount()` at `brainstorm_app.py:343-379` — example of try/except wrapping a session-data read
- `_start_initializer_wait()` at `brainstorm_app.py:3162-3170` — where the polling timer is currently installed (we will hook the auto-apply call here too)
- For the persistent banner widget: any existing always-visible status widget in `brainstorm_app.py` (search for `mount` calls in the dashboard composition)

## Implementation Plan

1. **Add `n000_needs_apply()` helper** to `brainstorm_session.py`:
   ```python
   def n000_needs_apply(task_num: int | str) -> bool:
       wt = crew_worktree(task_num)
       node_path = wt / NODES_DIR / "n000_init.yaml"
       out_path = wt / "initializer_bootstrap_output.md"
       if not node_path.is_file() or not out_path.is_file():
           return False
       data = read_yaml(str(node_path))
       desc = (data or {}).get("description", "")
       return desc.startswith("Imported proposal (awaiting reformat):")
   ```

2. **Add `_try_apply_initializer_if_needed()`** to `BrainstormApp` (in `brainstorm_app.py`). Call once in `_start_initializer_wait()` (right before the polling timer is installed) and once at the end of `_load_existing_session()`. Inside the method:
   - Import `n000_needs_apply` and `apply_initializer_output` lazily
   - If not `n000_needs_apply(self.task_num)`: return
   - Try `apply_initializer_output(self.task_num)`. On success: `self.notify("Initial proposal imported.")`, clear any previous error, refresh the session display (`self._load_existing_session()` — careful with re-entrancy: guard with a flag).
   - On exception `e`: store `self._initializer_apply_error = str(e)`, update the persistent banner widget to show the error and the retry-CLI hint.

3. **Persistent banner widget.** Add a `Static` widget mounted near the top of the dashboard with id `"#initializer_apply_banner"` and CSS `display: none` by default. Provide setter/clearer methods `_set_apply_banner(msg)` / `_clear_apply_banner()` that toggle `display`.

4. **Soften the `Error`/`Aborted` branch in `_poll_initializer()`**:
   - Do NOT set `_initializer_done = True` permanently.
   - Increase the polling interval (use a fresh `set_interval(30, ...)` after stopping the 2 s one) and keep watching for `_output.md` to appear.
   - When `_output.md` appears at any point, call `_try_apply_initializer_if_needed()`.
   - The existing notify can stay but should advise `Run "ait brainstorm apply-initializer <session>" to retry.` (sibling t653_2 adds that CLI; the message is informative regardless).

5. **Re-entrancy guard.** Add `self._applying_initializer = False` initialized in `__init__`. Set it before the `apply_initializer_output()` call and clear it in a `finally` block. `_try_apply_initializer_if_needed()` returns immediately if it is already True.

6. **Key-binding for manual retry.** Bind `ctrl+r` → `action_retry_initializer_apply()` which calls `_try_apply_initializer_if_needed()` unconditionally and updates the banner. Wire the binding via Textual's `BINDINGS` list on the dashboard screen. (Verify by grep that `ctrl+r` is not already used.)

7. **CSS / layout.** Banner should sit above the DAG widget and span full width. One line of red-on-default text. No animation.

## Verification Steps

1. **Static check.** `grep -n "_initializer_done = True" brainstorm_app.py` should show only the `Completed` branch (the Error/Aborted branch no longer permanently flips the flag).

2. **Synthetic session reproduction.** Create a synthetic session under `.aitask-crews/crew-brainstorm-9999/` mimicking session 635:
   - `br_nodes/n000_init.yaml` with `description: 'Imported proposal (awaiting reformat): demo.md'`
   - `br_proposals/n000_init.md` with placeholder text
   - `initializer_bootstrap_output.md` with valid `--- NODE_YAML_START ---` / `--- PROPOSAL_START ---` blocks
   - `initializer_bootstrap_status.yaml` with `status: Completed`
   Run `ait brainstorm 9999`. The dashboard should auto-apply on load and show the real proposal — no manual retry needed. (Clean up: `rm -rf .aitask-crews/crew-brainstorm-9999/` afterwards.)

3. **Error-with-late-recovery.** Create the same synthetic session but with `status: Error` and `error_message: "Heartbeat timeout — agent presumed dead"` and **no `_output.md`**. Open the TUI; observe the banner. Then drop a valid `_output.md` into the session directory while the TUI is still open. The 30 s timer should pick it up and apply, clearing the banner. (Manual verification — TUI behavior.)

4. **Banner persistence.** Make the apply intentionally fail (e.g., write a malformed `_output.md`). The banner should stay visible until either `apply_initializer_output()` succeeds or the user dismisses (no dismissal needed for first cut — just verify it persists across user interactions like clicks/scrolls).

5. **Sibling tasks.** This child is independent of t653_2 and t653_3 (`depends: []`), but its persistent-banner message references `ait brainstorm apply-initializer <session>` which t653_2 wires up. Acceptable: when t653_2 has not yet landed, the message just points at a not-yet-existing command — it is still correct, the user just runs it once t653_2 lands.

## Out of scope (intentionally)

- No changes to `apply_initializer_output()` itself (Layer C — owned by t653_2).
- No new CLI helper (Layer C — owned by t653_2).
- No agent-crew status / transition changes (Layer D — owned by t653_3).
- No heartbeat fixes (Layer A — owned by parent t650).
