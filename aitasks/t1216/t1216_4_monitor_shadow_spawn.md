---
priority: high
effort: medium
depends: [t1216_3]
issue_type: feature
status: Ready
labels: [aitask_monitor, shadow, tui, tmux_destructive]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
anchor: 1111
created_at: 2026-07-27 22:22
updated_at: 2026-07-30 15:33
---

## Pick-time safety guard — DO NOT pick from inside your working tmux

**Risk to running code agents: HIGH — this child can kill live agent panes,
and it can do so on a delay.**

**Safe to pick when:** you are in a shell whose tmux server carries **no code
agents you care about**. With `AITASKS_TMUX_SOCKET` unset, `ait` uses the
dedicated `-L ait` server (t953), so check with
`tmux -L ait list-sessions` / `tmux -L ait list-panes -a`. Writing the plan from
inside your normal session is fine; **implementing and verifying are not**
(`aidocs/framework/tui_conventions.md`, "Tmux-stress tasks").

### Why — the exact mechanism

`e` / `E` end in `attach_shadow_cleanup_hook(agent_pane, companion_pane)`
(`lib/agent_launch_utils.py:1348-1370`), which **mutates the followed agent's
own pane** — not the shadow's:

- `set-option -p -t <agent_pane> remain-on-exit on` — a persistent behavioural
  change; that pane stops closing on process exit.
- `set-hook -p -t <agent_pane> pane-died "run-shell '<cleanup> <agent> <companion>'"`
  — a **pane-scoped hook that persists** until the pane dies or is unset.

Both calls are fire-and-forget with stdout/stderr to `DEVNULL`, so a bad
registration is **silent**. The hook is installed even on agents this code did
not launch — pressing `e` on any running agent rewrites its pane options.

When the agent later dies, `aitask_companion_cleanup.sh` runs **raw `tmux` with
no socket flag by design** (header L18-21; allowlisted at
`tests/test_no_raw_tmux.sh:52`), so it reaches whichever server fired the hook.
`AITASKS_TMUX_SOCKET` **cannot sandbox it.** It then:

| line | action | gating |
|---|---|---|
| `:40` | `kill-pane` every pane in the **session** whose `@aitask_shadow_target` equals the dying agent | exact marker match — low risk |
| `:58` | `kill-pane -t "$companion"` when the agent's window has no non-shadow siblings | **no marker check, no class check, no confirmation** |
| `:60` | `kill-pane -t "$primary"` | unconditional |

Line 58 is the hazard. `$companion` is whatever was passed at spawn time — in
minimonitor that is `os.environ["TMUX_PANE"]` (`minimonitor_app.py:1229`),
i.e. "the pane I am running in". **If the monitor passes its own `TMUX_PANE`,
that is the pane of the agent implementing this task.** Because the hook fires
on the *agent's* death, arbitrarily later, a wrong pane id is a **latent trap**
that can detonate after your session ends — and tmux recycles pane ids.

Damage ceiling (verified): **panes only.** There is no `kill-session` or
`kill-server` anywhere in `.aitask-scripts/`, and `kill-window`
(`monitor_core.py:2265`) is not on this path.

### Working rules for this child

- Prefer **mocked** tests — `tests/test_minimonitor_shadow_pick.py` stubs
  `attach_shadow_cleanup_hook` rather than registering a real hook. Any test
  that registers a real one must run under `require_isolated_tmux()`.
- The PINNED contract below is the whole point: pass
  `companion_pane = shadow_pane`, never the monitor's `TMUX_PANE`.

### If you armed a pane by accident

Detect (commands verified on a throwaway socket):

```bash
tmux -L ait list-panes -a -F '#{pane_id}' | while read -r p; do
  h=$(tmux -L ait show-hooks -p -t "$p" 2>/dev/null | grep -F aitask_companion_cleanup.sh || true)
  [ -n "$h" ] && echo "ARMED $p -> $h"
done
```

Disarm:

```bash
tmux -L ait set-hook   -p -u -t <pane> pane-died
tmux -L ait set-option -p -u -t <pane> remain-on-exit
```

## Context

Fourth child of **t1216** (make `ait monitor` shadow-aware). Depends on
**t1216_1** (shared shadow seam).

Ports the shadow **spawn** keys `e` (launch) and `E` (launch, pick agent) from
minimonitor to the full monitor. Confirmed in scope with the user: without it
the monitor still cannot *create* a shadow, so the user would keep bouncing back
to minimonitor — exactly the workflow friction t1216 exists to remove.

Parent plan: `aiplans/p1216_monitor_shadow_pane_view_and_concern_picker.md`.

## Key files to modify

- `.aitask-scripts/monitor/minimonitor_app.py` — `_spawn_shadow` (L1191-1271),
  `action_launch_shadow` (L1085), `action_launch_shadow_pick` (L1127),
  `_load_project_tmux_config` (L1695) move out.
- `.aitask-scripts/monitor/monitor_core.py` or `monitor_shared.py` — receives
  the shared spawn helper and the deduped config loader.
- `.aitask-scripts/monitor/monitor_app.py` — the two new actions and bindings.
  Note it carries its **own verbatim copy** of `_load_project_tmux_config` at
  L1993; collapse both into the shared one.
- `website/content/docs/tuis/monitor/reference.md` + `how-to.md`.
- `website/content/docs/workflows/shadow-agent.md` and
  `aidocs/framework/shadow_agent.md` ("Spawn path and binding") — both currently
  state the shadow is launched from minimonitor; the monitor is now a second
  spawn surface.

## PINNED: the `TMUX_PANE` companion-pane coupling

`_spawn_shadow` currently ends with (minimonitor L1262):

```python
companion_pane = os.environ.get("TMUX_PANE", "") or shadow_pane
attach_shadow_cleanup_hook(followed_pane, companion_pane)
```

Here `TMUX_PANE` means *"minimonitor's own pane"* — the companion that should be
despawned once no real agent sibling remains in the followed agent's window.

**The lifted helper MUST take `companion_pane` as an explicit parameter and must
never read `TMUX_PANE` itself.** If the monitor passed its own `TMUX_PANE`,
`aitask_companion_cleanup.sh` job 2 would **kill the monitor's own pane** when
the agent's window runs out of real agents.

**The monitor passes `companion_pane = shadow_pane`** — the fallback minimonitor
already uses when `TMUX_PANE` is unset. Verified safe against
`.aitask-scripts/aitask_companion_cleanup.sh`:

- Job 1 kills every pane whose `@aitask_shadow_target` matches the dying primary,
  scoped to the session — so the bound shadow dies with its agent regardless of
  what `companion` is, including in separate-window placement.
- Job 2 counts real-agent siblings in the **primary's window** (excluding the
  primary, the companion, and any pane carrying `@aitask_shadow_target`); if
  zero it runs `kill-pane -t "$companion"`, which on the already-dead shadow
  pane is a `|| true` no-op.

## Implementation

Lift `_spawn_shadow` with signature roughly:

```python
def spawn_shadow(monitor, *, full_cmd, followed_pane, task_id, target_root,
                 snap, companion_pane, session) -> str | None:
```

Preserve verbatim:

- `_load_project_tmux_config(target_root)` → `shadow_same_window` (default
  `True`) and `shadow_pane_width` (default `60`, `TypeError`/`ValueError` → 60).
- Same-window branch: `TmuxLaunchConfig(..., new_window=False,
  split_direction=tmux_cfg.get("default_split", "horizontal"),
  split_size=shadow_width, split_target_pane=followed_pane, cwd=str(target_root))`
  — the split targets the **agent pane**, not the window's active pane.
- Separate-window branch: `new_window=True`,
  `window=f"agent-shadow-{task_id or 'x'}"`.
- `launch_in_tmux` → `resolve_pane_id_by_pid` → stamp
  `set-option -p -t <shadow_pane> @aitask_shadow_target <followed_pane>` →
  `attach_shadow_cleanup_hook(followed_pane, companion_pane)`.
- The "launched, but its pane could not be classified" warning when the pane id
  cannot be resolved, and the trailing `call_later(refresh)`.

On `MonitorApp`:

- `action_launch_shadow` (`e`) and `action_launch_shadow_pick` (`E`), acting on
  the **selected** agent — resolve from `self._focused_pane_id` →
  `self._snapshots`, **not** `_get_focused_pane_id()` (L1529, returns `None`
  whenever focus is off a `PaneCard`).
- The duplicate guard (`"A shadow is already running for this agent"`) fires
  **before** the dialog opens, using the **sync** shadow lookup — no await trap.
- `E` builds `AgentCommandScreen("Shadow (pick agent)", full_cmd,
  "/aitask-shadow " + " ".join(args), project_root=target_root,
  operation="shadow", operation_args=args,
  default_agent_string=resolve_agent_string(target_root, "shadow"))`. The
  callback consumes **`screen.full_command`** (post-override) and deliberately
  **discards** the dialog's `TmuxLaunchConfig` placement — placement stays
  handler-controlled. Use `narrow=False` (the monitor is full-width).
- `e` and `E` are free in the monitor's `BINDINGS` (L391-410) and match
  minimonitor's keys, so muscle memory carries over. New bindings are picked up
  automatically by `register_app_bindings("monitor", …)`; no
  `KNOWN_BINDING_SOURCES` change is needed since `monitor_app` is already listed.

## Verification

New `tests/test_monitor_shadow_pick.py`, mirroring
`tests/test_minimonitor_shadow_pick.py` (`__new__` + spy-lambda harness,
`patch.object(mm, "resolve_dry_run_command"/"resolve_agent_string")`,
recorder swapped in for `launch_in_tmux`, restored in `finally`):

- Binding registration: exactly one `e` → `launch_shadow` and one `E` →
  `launch_shadow_pick`.
- Duplicate guard fires **before** the dialog opens (`spy_pushed == []`), uses
  the sync reader.
- `AgentCommandScreen` contract: `operation == "shadow"`, `operation_args ==
  ["%1", "42"]` (and `["%1"]` without a task id), prompt
  `"/aitask-shadow %1 42"`.
- Confirm path launches `screen.full_command` (post-override, not a stale
  capture); stamps `SHADOW_TARGET_OPTION` exactly once targeting the new pane
  with the followed pane's id; `callback(None)` and `callback("run")` launch
  nothing.
- **New assertion:** `attach_shadow_cleanup_hook` is called with the **shadow**
  pane as `companion_pane`, plus a **negative control** proving the monitor's own
  `TMUX_PANE` is never passed (set `TMUX_PANE` to a sentinel in the test env and
  assert it does not appear in the call).

```bash
bash tests/run_all_python_tests.sh
bash tests/test_no_raw_tmux.sh
```

Manual (from a shell **outside** the main aitasks tmux session — see
`aidocs/framework/tui_conventions.md`): press `e` in `ait monitor` on a selected
agent, confirm the shadow splits beside that agent, then kill the agent and
confirm the shadow dies **and the monitor survives**.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-30T12:33:39Z status=pass attempt=1 type=human
>
> Note: deferred
