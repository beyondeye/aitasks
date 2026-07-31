---
Task: t1216_4_monitor_shadow_spawn.md
Parent Task: aitasks/t1216_monitor_shadow_pane_view_and_concern_picker.md
Sibling Tasks: aitasks/t1216/t1216_5_manual_verification_monitor_shadow_pane_view_and_concern_pic.md
Archived Sibling Plans: aiplans/archived/p1216/p1216_1_shared_shadow_seam.md, aiplans/archived/p1216/p1216_2_monitor_shadow_zone.md, aiplans/archived/p1216/p1216_3_monitor_concern_picker.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-07-30 15:32
---

# p1216_4 — Port shadow spawn (`e` / `E`) to the full monitor

> **THIS IS A PLAN-ONLY DELIVERABLE. Approving it does NOT authorise
> implementation in this session.** Step 0's preflight fails here (measured), so
> the actions that follow approval are exactly: externalise the plan → commit it
> → release the task lock → revert `t1216_4` to `Ready` → end. Implementation is
> re-picked later from a verified isolated tmux server. (S1)

> **Re-verified 2026-07-30** against `main` @ `1b9ed49d7`, after t1216_1/_2/_3
> landed. Nine review concerns were raised across two rounds; **all nine were
> verified valid** and are addressed below (C1–C6, S1–S3, tagged inline).

## Context

`ait monitor` is the TUI for switching between sessions and agents. t1216_1
lifted the shadow seam into `monitor_core`, t1216_2 gave the monitor a live
shadow preview column, t1216_3 gave it the concern badge / toast / picker. What
is still missing is the ability to **create** a shadow: `e` / `E` exist only in
`ait minimonitor`, so the user still bounces to minimonitor for the one action
that starts the whole flow — the friction t1216 exists to remove.
`monitor_app.py:2677-2679` names this task in a source comment as the one that
closes the gap.

This child lifts minimonitor's `_spawn_shadow` into the shared headless module,
adds `e` / `E` to `MonitorApp` acting on the **selected** agent, and hardens four
lifecycle contracts the lift exposes.

---

## Step 0 — Execution safety gate (C1) — **BLOCKS implementation**

The task file's own pick-time guard requires that implementation and verification
run from a shell whose tmux server carries no code agents worth keeping
(`aidocs/framework/tui_conventions.md:491-516`, "Tmux-stress tasks"). This is not
advisory here: Step 6 exists precisely because a missed mock retarget makes the
suite call the real `launch_in_tmux`, and `attach_shadow_cleanup_hook` installs
**persistent** `remain-on-exit` + `pane-died` state on whatever pane it is given.

**Preflight (run before any test invocation):**

```bash
tmux -L ait list-panes -a -F '#{pane_id} #{window_name} #{pane_current_command} [#{@aitask_shadow_target}]'
```

Pass criterion: no pane other than the implementing agent's own is an agent, a
shadow, or a framework TUI. **If it fails, do not implement** — per
`tui_conventions.md:512-514` the prescribed action is "abort + revert to Ready,
keep the plan".

**Current state — the preflight FAILS (measured, not assumed):**

| pane | what | note |
|---|---|---|
| `%0` | `ait monitor` | the TUI this task modifies |
| `%1` | `ait board` | |
| `%2` | this implementing agent | **armed**: `pane-died → aitask_companion_cleanup.sh %2 %3` |
| `%3` | minimonitor companion | the `companion` in `%2`'s hook |
| `%4` | a shadow, `@aitask_shadow_target=%2` | bound to this agent |

So this session **writes and commits the plan and does not implement it** (S1):
after approval, release the lock and revert `t1216_4` to `Ready`, then re-pick it
from a shell outside this tmux server.

**Structural containment for whoever does implement (S2).** The first draft
proposed setting `AITASKS_TMUX_SOCKET` / `TMUX_TMPDIR` at test-module import.
**That does not work, and the repository already documents why.**
`TmuxClient.__init__` caches `tmux_socket_args()` **once** — *"Cached once —
never recomputed per call"* (`lib/tmux_exec.py:148-152`) — and four modules build
a client at **import time**: `agent_launch_utils.py:34`, `monitor_app.py:65`,
`lib/tui_switcher.py:74`, `lib/tui_clipboard.py:29`. Under full-suite discovery
any earlier module can import `agent_launch_utils` first, leaving its `_TMUX`
pinned to `-L ait` no matter what a later module writes to the environment. The
proposed "call the real `launch_in_tmux` and see that it fails" control is also
wrong: it can only discover the leak *by performing the mutation*.

Use the repository's existing integration-test pattern instead — spelled out at
`tests/test_launch_in_tmux_pane_pid.py:276-279` (*"`agent_launch_utils._TMUX`
caches its socket args at import, so the module-level singleton is rebuilt inside
the patched env and restored in tearDown — mirroring
`test_tmux_exec.py::TestGatewayIntegration`"*), i.e. per-fixture:

```python
def setUp(self):
    self._tmpdir = tempfile.mkdtemp(prefix="ait_t1216_4_tmux_")
    self._env = patch.dict(os.environ, {
        "TMUX_TMPDIR": self._tmpdir,
        "AITASKS_TMUX_SOCKET": self.SOCK,   # throwaway, per-process
        "AIT_NO_SYSTEMD_RUN": "1",
    }, clear=False)
    self._env.start()
    os.environ.pop("TMUX", None)
    os.environ.pop("TMUX_PANE", None)       # synthetic %1/%2 collision guard
    self._saved = {m: m._TMUX for m in (agent_launch_utils, monitor_app)}
    for m in self._saved:
        m._TMUX = agent_launch_utils.TmuxClient()

def tearDown(self):
    for m, c in self._saved.items():
        m._TMUX = c
    self._env.stop()
    shutil.rmtree(self._tmpdir, ignore_errors=True)
```

**Containment is asserted statically, never by attempting a launch:** in the
fixture, assert `agent_launch_utils._TMUX.socket_args == ["-L", self.SOCK]`
(`socket_args` is the public read-only property at `lib/tmux_exec.py:154-157`).
That proves the singleton was rebuilt under isolation without issuing a single
mutating tmux call. The mocks remain the primary protection; this is the belt.

---

## Verification pass — what changed since the plan was written

| Original plan said | Current reality |
|---|---|
| `_spawn_shadow` at `minimonitor_app.py:1191-1271` | **1382-1462** |
| `action_launch_shadow` L1085 / `..._pick` L1127 | **1276-1316 / 1318-1380** |
| `_load_project_tmux_config` at `monitor_app.py:1993` | **3111-3123** (+ `minimonitor_app.py:1849-1860`) |
| monitor `BINDINGS` L391-410 | **470-491** — `e` / `E` confirmed free |
| `_get_focused_pane_id` L1529 | **2494-2499** |
| "duplicate guard uses the sync shadow lookup" | Right, but the lookup **fails open** and runs only pre-dialog — see C3 |
| *(absent)* | Two minimonitor test files must be retargeted (Step 6) |
| *(absent)* | The monitor needs a `PaneCategory.AGENT` guard minimonitor does not (Step 4) |
| *(absent)* | `launch_in_tmux` steals window focus on **both** placement branches (C2) |
| *(absent)* | The live walkthrough is already owned by **t1216_5** (five `[t1216_4]` items) |

## Decisions

**D1 — the duplicate guard uses live tmux state, not `_current_shadow_pane_id()`.**
`_shadow_snapshots` has two writers, and the fast one
(`refresh_shadow_snapshot`, `monitor_core.py:1822`) opens with
`prev = self._shadow_snapshots.get(...); if prev is None: return None` — it can
never *create* a key; only the ~3 s `commit_snapshots` can. `monitor_core.py:2196-2204`
documents a further race where a shadow pane is discovered before
`@aitask_shadow_target` is stamped, so the real double-spawn window is **3–6 s**.
Record the division of labour as a docstring line on `_current_shadow_pane_id`:
it answers *"is there a shadow to **read**"* (preview, key-forwarding, picker —
lagging a tick is the intended cheapness); the live lookup answers *"may I
**create** one"*.

A sync tmux round-trip in a user action is fine:
`tests/test_monitor_refresh_no_sync_tmux.py` constrains the **refresh** path only,
and monitor_app already makes blocking calls from actions (`kill_agent_pane_smart`,
`launch_in_tmux` at 2985). *Rejected:* async actions using
`find_shadow_pane_async` — the spawn blocks far longer than the guard's
`list-panes`, so it buys nothing while forking the two apps' guard mechanism.

**D2 — the lift lands in `monitor_core.py`, re-exported through the
`tmux_monitor.py` shim.** It already imports `agent_launch_utils`, already hosts
every other lifted shadow helper over a duck-typed `monitor`, and already does
mutating tmux (`send_keys` 2287, `kill-pane` 2374, `kill_agent_pane_smart` 2392).
No circular import. `monitor_shared` is rejected: Textual-aware, and splitting the
shadow family across two modules is how the seam rots.
`load_project_tmux_config` joins it beside `load_monitor_config`.

**D3 — `companion_pane` is keyword-only, `str | None`, no default.** The helper
**must never read `TMUX_PANE`**; `None` means "bind to the newly created shadow
pane". Verified against `aitask_companion_cleanup.sh`: job 1 (L38-43) kills every
pane in the *session* whose `@aitask_shadow_target` matches the dying agent; job 2
(L49-58) counts real-agent siblings in the agent's *window* and, finding none,
runs `kill-pane -t "$companion"` with **no marker check**. The monitor's pane is
never in that window, so it can never be *counted* — only ever be the *target*.
Body uses `companion_pane or shadow_pane` so it also normalises the `""` that
`os.environ.get("TMUX_PANE", "")` can produce.

*Rejected: a sentinel type.* It does not stop a caller passing
`os.environ["TMUX_PANE"]`. What does is a source-level test plus a runtime
negative control (Step 7).

**D4 — `schedule_refresh` is a parameter**, so "no refresh on launch error" is
preserved verbatim, and both apps stop owning the notify strings.

**D5 — `_spawn_shadow` is kept in *both* apps as a per-app policy adapter.**
Deleting it would replicate the safety-critical `companion_pane` and
`select_window` decisions at four call sites instead of two. Its docstring must
say it is **not** a t1289 pass-through seam.

---

## Step 1 — `monitor_core.py`

Extend the `agent_launch_utils` import (L42-49) with `TmuxLaunchConfig`,
`attach_shadow_cleanup_hook`, `launch_in_tmux`, `resolve_pane_id_by_pid`; add
`Callable` to the `collections.abc` import.

**1a. `load_project_tmux_config(project_root) -> dict`** — body verbatim from
`minimonitor_app.py:1850-1860`; companion to `load_monitor_config`.

**1b. Fail-closed shadow lookup (C3b).** `find_shadow_pane` currently returns
`None` both when `rc != 0` and when there is no match, so a failed `list-panes`
reads as "no shadow" and the guard **fails open**. Add the discriminating
primitive and re-express the existing one on top of it (derive, don't duplicate —
the six existing readers are untouched):

```python
def find_shadow_pane_status(monitor, followed_pane_id: str) -> tuple[bool, str | None]:
    """(ok, pane). ``ok`` is False when the query itself failed."""

def find_shadow_pane(monitor, followed_pane_id: str) -> str | None:
    ok, pane = find_shadow_pane_status(monitor, followed_pane_id)
    return pane if ok else None
```

**1c. `spawn_shadow`**

```python
def spawn_shadow(
    monitor, *,
    full_cmd: str, followed_pane: str, followed_window: str, session: str,
    task_id: str | None, target_root: Path,
    companion_pane: str | None,      # D3 — no default, per-app policy
    select_window: bool,             # C2 — no default, per-app policy
    notify: Callable[..., None],
    schedule_refresh: Callable[[], None],
) -> str | None:
```

Taking `followed_window` + `session` rather than a `PaneSnapshot` keeps the helper
duck-typed. Lifted verbatim from `minimonitor_app._spawn_shadow` (1382-1462) —
`same_window` / `shadow_pane_width` (60 fallback on `TypeError`/`ValueError`) /
`default_split`, the split-targets-the-**agent**-pane geometry, the
`agent-shadow-{task_id or 'x'}` window name, the `"Shadow launch failed: …"` error
(returning `None` **without** `schedule_refresh`, per D4), the
`"Launched shadow agent"` and `"…could not be classified…"` notifies — with these
**deliberate, non-verbatim hardenings**:

- **Re-check immediately before spawning (C3a).** The pre-dialog guard cannot
  cover the seconds an `AgentCommandScreen` is open, nor two queued dialogs. Call
  `find_shadow_pane_status(monitor, followed_pane)` as the last thing before
  `launch_in_tmux`; refuse on a found shadow, and refuse **on `ok is False`**
  too — an unverifiable state must not spawn. Fixing it here, at the shared sink,
  closes the same latent gap in minimonitor. This is an intentional behaviour
  change to minimonitor, called out because everything else is verbatim.
- **Verify the classifier stamp (C4).** `monitor.tmux_run(["set-option", …])`
  returns `(rc, out)`; the current code discards it, then installs the cleanup
  hook and reports success. An unstamped shadow is indistinguishable from an
  agent *forever*: it appears in agent lists, is targeted by `k` / `n`, counts as
  a real sibling, evades the duplicate guard, and — because job 1 matches on the
  marker — is **not** cleaned up when its agent dies. So: check `rc`, retry once,
  and on persistent failure **kill the pane we just created** (we own it, it is
  milliseconds old, and leaving it is strictly worse), do **not** install the
  cleanup hook, `notify(..., severity="error")` naming the pane, and return
  `None`.

Docstring carries as contract: the duck-typed-gateway clause; **"This function
never reads `TMUX_PANE`"** and what passing a pane outside the followed agent's
window does; that `schedule_refresh` is not called on launch failure; and the
stamp-failure recovery.

## Step 2 — `tmux_monitor.py` shim

Re-export `load_project_tmux_config`, `find_shadow_pane_status`, `spawn_shadow`
in the existing "Shared shadow seam" group with a `(t1216_4)` note.

## Step 3 — `agent_launch_utils.py` — focus and hook contracts

**3a. Focus preservation (C2).** Verified: the split branch ends with
`_TMUX.spawn(["select-window", "-t", window_target])` (L1283-1284), **and** the
`new_window` branch runs `new-window` **without `-d`** (L1257-1265), which creates
*and selects*. So **both** placements yank the client out of `ait monitor` — the
precise window-bouncing t1216 exists to remove. Add to `TmuxLaunchConfig`
(L64-93):

```python
select_window: bool = True   # default preserves every existing caller
```

- split branch: skip the `select-window` spawn when `False`;
- `new_window` branch: append `-d` to the `new-window` argv when `False`.

`spawn_shadow` threads it through; **minimonitor passes `True`** (its client is
already on that window — behaviour unchanged) and **the monitor passes `False`**.

**3b. Hook idempotence (C5).** Confirmed live on this very session's agent pane:
`pane-died[0] run-shell ".../aitask_companion_cleanup.sh %2 %3"` with
`remain-on-exit on`, where `%3` is the minimonitor companion. `set-hook -p`
**overwrites** the pane's single `pane-died` hook, so a monitor-side spawn onto
that agent replaces `companion=%3` with `companion=<shadow>`. On agent exit job 1
kills the shadow, then job 2's `kill-pane -t <shadow>` is a no-op — and the
**minimonitor is orphaned**. That is a lifecycle-contract regression, not lost
tidiness.

Fix inside `attach_shadow_cleanup_hook` (both callers benefit). The first draft
said "install only if no `aitask_companion_cleanup.sh` hook exists", which left
two holes (S3): a transient probe failure fell through to the overwrite, and an
**unrelated** `pane-died` hook was still silently destroyed. Corrected
procedure — note that a bare `set-hook -p … pane-died` writes index **`[0]`** and
therefore replaces whatever sits there:

1. Always `set-option -p -t <agent> remain-on-exit on` (idempotent).
2. Probe `show-hooks -p -t <agent>`. **On `rc != 0`, fail closed:** install
   nothing and return `"unverified"`. We cannot distinguish "no hook" from
   "someone else's hook", and the two failure modes are not symmetric —
   overwriting is silent and persistent, whereas skipping merely leaves the
   shadow to be closed by hand, which is bounded and visible. `spawn_shadow`
   surfaces it as a warning ("shadow launched; auto-cleanup on agent exit could
   not be wired").
3. If any `pane-died[N]` already references `aitask_companion_cleanup.sh` →
   no-op, return `"existing"`. Correct and complete because job 1 is
   **marker-driven**: it kills every pane whose `@aitask_shadow_target` matches
   the dying agent, regardless of who armed the hook or what `companion` it
   names. The prior companion contract survives untouched.
4. Otherwise **append at the first free index** —
   `set-hook -p -t <agent> 'pane-died[<max+1>]' "run-shell '…'"` (or `[0]` when
   there are no `pane-died` hooks at all) — return `"installed"`. Verified on a
   throwaway socket that this preserves an unrelated hook:
   ```
   pane-died[0] display-message custom-user-hook          # survives
   pane-died[1] run-shell ".../aitask_companion_cleanup.sh %1 %2"
   ```

Return a status (`"installed"` / `"existing"` / `"unverified"`) rather than
`None`, so the caller can report the fail-closed case; the only current caller
ignores the return, so the change is safe.
(`lib/tui_switcher.py:1383-1388` wires its own git-pane hook inline and does not
call this function; untouched.)

## Step 4 — `minimonitor_app.py`

- `tmux_monitor` import: drop `SHADOW_TARGET_OPTION` (sole use was L1450 —
  removing it makes a missed test retarget fail loudly); add
  `load_project_tmux_config`, `spawn_shadow`.
- `agent_launch_utils` import: drop `resolve_pane_id_by_pid` and
  `attach_shadow_cleanup_hook` (sole uses 1446 / 1454). **Keep** `launch_in_tmux`
  (still used at L1138 by the pick path) and `TmuxLaunchConfig`.
- Replace `_spawn_shadow`'s body (1382-1462) with the policy adapter, keeping the
  `if self._monitor is None: return` head guard:

```python
    return spawn_shadow(
        self._monitor,
        full_cmd=full_cmd, followed_pane=followed_pane,
        followed_window=snap.pane.window_name,
        session=snap.pane.session_name or self._session,
        task_id=task_id, target_root=target_root,
        # This minimonitor IS the followed agent's companion and shares its
        # window, so the cleanup hook must despawn US, not the shadow.
        companion_pane=os.environ.get("TMUX_PANE") or None,
        select_window=True,          # already on that window; unchanged
        notify=self.notify,
        schedule_refresh=lambda: self.call_later(self._refresh_data),
    )
```

- Delete `_load_project_tmux_config` (1849-1860); point `main()` (1871) at the
  imported name.

## Step 5 — `monitor_app.py`

- Imports: add `find_shadow_pane_status`, `spawn_shadow`,
  `load_project_tmux_config`. `PaneCategory` is already imported;
  `SHADOW_TARGET_OPTION` is not needed (the stamp lives in `spawn_shadow`).
- `BINDINGS` (470-491), after the `c` binding per the uppercase-sibling ordering
  convention:
  ```python
  Binding("e", "launch_shadow", "Shadow"),
  Binding("E", "launch_shadow_pick", "Shadow (pick)"),
  ```
  Picked up automatically by `register_app_bindings("monitor", …)`;
  `monitor_app` is already in `KNOWN_BINDING_SOURCES` (`lib/shortcut_scopes.py:54`).
- **Footer audit** (`tui_conventions.md:387-407`): flip `M`
  (`toggle_multi_session`, L486) to `show=True` — a distinct operation surfaced
  nowhere else, and `tests/test_multi_session_monitor.sh:362` asserts only key
  presence. Keep `f5` (L475) hidden **with an inline justification comment**: it
  is an alias of `r`, already footer-visible with the same label and action, so
  showing both duplicates an entry rather than surfacing an operation. minimonitor
  needs no change (its own `#mini-key-hints` line already advertises `e/E`).
- Two new **sync** actions plus a `_spawn_shadow` adapter, next to
  `action_pick_concerns` (~2656). Shared prologue:
  1. `if self._monitor is None: return`
  2. `pane_id = self._focused_pane_id`; if falsy or not in `self._snapshots` →
     `notify("Focus an agent pane first", severity="warning")`. Use
     `_focused_pane_id`, **never** `_get_focused_pane_id()` (2494).
  3. **`if snap.pane.category != PaneCategory.AGENT` →
     `notify("Shadow only applies to agent panes", severity="warning")`.**
     Monitor-only: `_rebuild_pane_list` (1562-1570, 1611) renders
     `PaneCategory.OTHER` panes as focusable `PaneCard`s, so `_focused_pane_id`
     can be a shell or lazygit pane. minimonitor never needed this because
     `_find_own_agent_snapshot` filters on category (1536).
  4. `followed_pane = snap.pane.pane_id`; if empty → warn.
  5. **Duplicate guard (D1 + C3b), fail-closed:**
     `ok, existing = find_shadow_pane_status(self._monitor, followed_pane)`;
     if `not ok` → `notify("Could not verify whether a shadow is already running",
     severity="warning"); return`; if `existing` → `notify("A shadow is already
     running for this agent", severity="warning"); return`.
  6. `task_id` / `target_root` / `args` / `full_cmd` exactly as minimonitor
     (1309-1315).
- `e` → `self._spawn_shadow(...)`. `E` pushes
  `AgentCommandScreen("Shadow (pick agent)", full_cmd, "/aitask-shadow " +
  " ".join(args), project_root=target_root, operation="shadow",
  operation_args=args, default_agent_string=resolve_agent_string(target_root,
  "shadow"))` — **no `narrow=`** (the monitor is full-width; both existing call
  sites at 2973/3053 omit it). The callback launches only
  `if isinstance(result, TmuxLaunchConfig)`, consumes **`screen.full_command`**,
  and discards the dialog's own placement.
- `_spawn_shadow` adapter: as minimonitor's but `companion_pane=None` and
  `select_window=False`, commented *"the monitor is not the agent's companion and
  normally lives in another window — passing our own `TMUX_PANE` here would make
  `aitask_companion_cleanup.sh` kill the monitor; stealing focus would defeat the
  shadow column."*
- `action_pick_concerns` (2675-2680): replace the placeholder comment and message
  with `notify("No shadow agent bound to this agent — press 'e' to launch one",
  severity="warning")`.
- Delete `_load_project_tmux_config` (3111-3123); point `main()` (3151) at the
  imported name.

**Not fixed, deliberately:** pressing `E` twice stacks two dialogs. The C3a
re-check now makes the *second* confirm refuse instead of spawning a duplicate,
so the remaining behaviour is a redundant dialog, not a correctness bug. Adding a
latch to only one app would break parity.

## Step 6 — retarget the minimonitor tests (hazard)

Once the body lives in `monitor_core`, patches on the `minimonitor_app` namespace
intercept **nothing** and the tests call the real `launch_in_tmux`. Both files
need `from monitor import monitor_core as mc`, plus the Step 0 socket containment:

- `tests/test_minimonitor_shadow_pick.py` — `ConfirmPathTests` (173-178):
  `patch.object(mm, …)` → `patch.object(mc, …)` for `launch_in_tmux`,
  `resolve_pane_id_by_pid`, `attach_shadow_cleanup_hook`; and
  `mm._load_project_tmux_config` → `mc.load_project_tmux_config`. L190
  `mm.SHADOW_TARGET_OPTION` → `mc.SHADOW_TARGET_OPTION`. L204 → `mc.launch_in_tmux`.
- `tests/test_minimonitor_concern_action.py` —
  `LaunchShadowGuardTests.test_refuses_duplicate_shadow_via_sync_reader` (322-327)
  rebinds `mm.launch_in_tmux` by attribute assignment; retarget to
  `mc.launch_in_tmux`, keeping the `try/finally` restore.

**C6 — add a minimonitor policy test.** The existing confirm test asserts only
`mock_hook.call_args.args[0]`, so it would pass if the refactor silently switched
minimonitor to self-binding. Add, mirroring the monitor's negative control: with
`patch.dict(os.environ, {"TMUX_PANE": "%77"})`, assert the **complete** call
`mock_hook.assert_called_once_with("%1", "%77")` — the minimonitor keeps its
`TMUX_PANE`-derived companion. Also assert `select_window is True` on its
`TmuxLaunchConfig`.

Everything these tests already assert stays byte-identical — only patch targets
move. That is the regression net proving the lift is behaviour-preserving.

## Step 7 — new `tests/test_monitor_shadow_pick.py`

Model on `tests/test_monitor_concern_action.py:174 _mk_app`
(`MonitorApp.__new__`, `spy_notify` / `spy_pushed`), extended with `_session`,
`_task_cache`, `_root_for_snap` and a `call_later` spy; take the
`sync_calls`-recording `tmux_run` from `tests/test_minimonitor_shadow_pick.py:48`.
Patch `monitor_app.resolve_dry_run_command` / `resolve_agent_string` and
`monitor_core.launch_in_tmux` / `resolve_pane_id_by_pid` /
`attach_shadow_cleanup_hook` / `load_project_tmux_config`, restoring in `finally`.
Socket containment per Step 0 — rebuild the cached `_TMUX` singletons in `setUp`,
restore in `tearDown`, and assert `socket_args` statically (never by attempting a
launch).

*Bindings / footer* — exactly one `e`→`launch_shadow` and one
`E`→`launch_shadow_pick`, both `show is True`; `M` is now `show is True`; `f5`
stays `show is False` **and** its action equals `r`'s (encoding the
justification); negative control: `c`→`pick_concerns` untouched.

*Selection guards* — no focused pane, and focused pane absent from `_snapshots`,
both refuse; **a `PaneCategory.OTHER` focused pane refuses**;
`check_action("launch_shadow", ())` is falsy for `Zone.PREVIEW` / `Zone.SHADOW`
and truthy for `Zone.PANE_LIST` (same for `launch_shadow_pick`).

*Duplicate guard* — `sync_list="%5\t%1"` refuses and never calls
`launch_in_tmux`; `E` refuses **before** pushing (`spy_pushed == []`);
**cache-is-not-the-guard control:** a monitor whose `get_shadow_snapshot` returns
`None` while `tmux_run` reports a live shadow **still refuses** (this fails if
someone swaps in `_current_shadow_pane_id()`); **fail-closed control (C3b):**
`tmux_run` returning `rc != 0` refuses and launches nothing; **confirm-time
re-check (C3a):** a monitor that reports no shadow at guard time but a live one
by spawn time launches nothing.

*Focus preservation (C2)* — the monitor's `TmuxLaunchConfig` has
`select_window is False` on both the split and the `new_window` branch; and, at
the `agent_launch_utils` level, `select_window=False` emits no `select-window`
argv and adds `-d` to `new-window`, while the default `True` keeps today's argv
byte-for-byte (negative control for existing callers).

*Spawn / lifecycle* — `launch_in_tmux` called once with `full_cmd`; config has
`new_window is False`, `split_target_pane == "%1"`, `split_size == 60`,
`cwd == "/p1"`; `{"shadow_same_window": False}` → `new_window is True`,
`window == "agent-shadow-42"`; `{"shadow_pane_width": "wide"}` → 60; exactly one
`set-option` stamp targeting `"%9"` with value `"%1"`.

*Stamp verification (C4)* — a monitor whose `set-option` returns `rc != 0`
retries once, then kills the new pane, notifies at `severity="error"`, installs
**no** cleanup hook, and returns `None`; the success path installs the hook
exactly once.

*Hook idempotence (C5 + S3)* — four cases, using the live-verified output shape
`pane-died[0] run-shell "…/aitask_companion_cleanup.sh %2 %3"`:
(a) an existing `aitask_companion_cleanup.sh` hook → **no** `set-hook`, prior
companion survives, returns `"existing"`, `remain-on-exit` still ensured;
(b) no `pane-died` hook → installs at `[0]`, returns `"installed"`;
(c) an **unrelated** `pane-died[0]` hook → installs at `[1]` and the unrelated
hook is still present afterwards, returns `"installed"`;
(d) `show-hooks` returning `rc != 0` → **no** `set-hook` at all, returns
`"unverified"`, and `spawn_shadow` emits the auto-cleanup warning.
Negative control for (c): asserting only "our hook is present" passes even when
the unrelated one was destroyed, so the test must assert **both** entries.

*PINNED companion contract (D3)* — with `patch.dict(os.environ, {"TMUX_PANE":
"%77"})`, `attach_shadow_cleanup_hook` is called once with `("%1", "%9")` and
`"%77"` appears in **no** argument; plus the structural control
`assertNotIn("TMUX_PANE", inspect.getsource(mc.spawn_shadow))`.

*D4* — `launch_in_tmux` returning `(None, "boom")` notifies at `severity="error"`
and never fires `schedule_refresh`; the success and unclassifiable paths each fire
it exactly once, and the unclassifiable path warns while skipping stamp and hook.

*`E` dialog contract* — `operation == "shadow"`, `operation_args == ["%1", "42"]`
(and `["%1"]` with no task id), prompt `"/aitask-shadow %1 42"`, and
**`screen._narrow` falsy** (assert it, or a copy-paste of `narrow=True` goes
unnoticed); confirm launches `screen.full_command`; `callback(None)` and
`callback("run")` launch nothing.

## Step 8 — docs

- `website/content/docs/tuis/monitor/reference.md` — `e` / `E` rows; `M` joins
  the shown set.
- `website/content/docs/tuis/monitor/how-to.md` — a "How to Launch a Shadow
  Agent" section mirroring `minimonitor/how-to.md:126-134`; line 154 names `e`;
  **line 158 replaced** ("…Monitor reads and picks concerns but does not spawn
  shadows itself"), now false. State that spawning keeps focus in the monitor.
- `website/content/docs/workflows/shadow-agent.md` — lines 15/17/19: the monitor
  is a second spawn surface. Lines 91/93 still describe concern-picking as
  minimonitor-only, which t1216_3 already made false; fixed in the same pass.
- `aidocs/framework/shadow_agent.md` — rewrite "Spawn path and binding"
  (135-141); add the `companion_pane` contract and the hook-idempotence rule as
  called-out rules; cross-reference `tui_conventions.md`'s companion-pane section.

Per `documentation_conventions.md`, describe current state; do not narrate the
change.

## Verification

```bash
bash tests/run_all_python_tests.sh      # read ONLY the last line for the verdict
bash tests/test_no_raw_tmux.sh
bash tests/test_multi_session_monitor.sh
```

Targeted: `python3 tests/test_monitor_shadow_pick.py`,
`python3 tests/test_minimonitor_shadow_pick.py`,
`python3 tests/test_minimonitor_concern_action.py`. The runner has no pytest and
falls back to unittest discovery, so a `-k` filter silently runs nothing.

All of the above are mocked and, per Step 0, socket-contained. **The live tmux
walkthrough is owned by t1216_5** (five `[t1216_4]` items) and is not run here.

## Implementation notes

Implemented 2026-07-30 from a shell **outside** the `-L ait` tmux server, after
the user cleared that server (`tmux -L ait kill-server`). Step 0's preflight was
re-run and **passed** — `no server running on /tmp/tmux-1000/ait` — so the
plan-only constraint recorded above no longer applied.

All steps landed as written, with these deliberate deviations:

- **Step 7's structural control was strengthened, not weakened.** The plan
  specified `assertNotIn("TMUX_PANE", inspect.getsource(mc.spawn_shadow))`. That
  assertion false-positives against the function's own docstring, which names
  `TMUX_PANE` to document the contract ("This function never reads `TMUX_PANE`").
  The test instead asserts on the **compiled code object** — no `"TMUX_PANE"`
  string literal among `co_consts` (excluding the docstring) and no `environ` in
  `co_names`. Strictly stronger: it proves no *executable* reference exists while
  leaving the documentation intact. Verified to discriminate by mutation.
- **Socket containment was factored into `tests/lib/tmux_socket_containment.py`**
  rather than duplicated per-fixture across three test modules. Same mechanics the
  plan specified (throwaway `AITASKS_TMUX_SOCKET` + `TMUX_TMPDIR`, `_TMUX`
  singletons rebuilt inside the patched env, static `socket_args` assertion, never
  a trial launch). Only `agent_launch_utils` needs rebuilding — `monitor_core`
  holds no `_TMUX` of its own.
- **`_spawn_shadow` returns `str | None`** in both apps (the plan's snippet wrote
  `return spawn_shadow(...)` against a `-> None` annotation).
- **One unplanned test update.** `test_monitor_concern_action.py`'s
  `test_no_shadow_bound_warns_without_promising_a_key` asserted the monitor's "no
  shadow bound" message must **not** name `e` — true when t1216_3 wrote it,
  false once this task bound `e`. Inverted into a positive assertion that also
  guards that the key named in the message actually exists in `BINDINGS`, so the
  message can never drift back into offering a key that does nothing.

Verification beyond the plan's list:

- **Mutation discrimination.** Ten contracts were each broken in source, one at a
  time, to prove the suite fails: the PINNED companion pane, focus preservation,
  the fail-closed duplicate guard, hook append-vs-overwrite, hook fail-closed,
  stamp verification, `schedule_refresh` on error, the `TMUX_PANE` structural
  control, the `PaneCategory` guard, and `narrow`. All ten discriminated;
  baseline restored and passing after each.
- **Stale-patch negative control.** Reverting the Step 6 patch targets from `mc`
  back to `mm` makes the minimonitor tests fail loudly — confirming the Step 4
  import removals turn a missed retarget into an `AttributeError` rather than a
  silent no-op, and the C6 policy test catches the one name (`launch_in_tmux`)
  still present in both namespaces.
- **Live tmux confirmation of the indexed-hook syntax** (isolated socket + private
  `TMUX_TMPDIR`, torn down after): `set-hook -p -t <pane> 'pane-died[1]'` exits 0,
  an unrelated `pane-died[0]` survives, and `show-hooks -p` emits exactly the
  shape `_pane_died_hook_indices` parses. This is the one C5/S3 claim the mocked
  tests cannot establish on their own.

## Risk

### Code-health risk: medium
- The fixes for C2 and C5 change `agent_launch_utils` — a public dataclass field and the hook-install contract — which every agent launch in the framework goes through, not just the shadow path. Defaults preserve existing behaviour, but the blast radius is now framework-wide rather than monitor-local · severity: medium · → mitigation: monitor_shadow_spawn_live_smoke
- The monitor gains its first synchronous `self._monitor.tmux_run` call. Correct here (user action, off the refresh path), but it weakens the file's uniform async-only-gateway property and the existing guard test does not cover action paths · severity: medium · → mitigation: none
- Retargeting patch sites in two minimonitor test files moves the characterization net that was t1216_1's proof the lift changed no behaviour; a missed `launch_in_tmux` retarget fails **silently** · severity: medium · → mitigation: monitor_shadow_spawn_live_smoke
- `spawn_shadow` takes two callables to keep `monitor_core` Textual-free — an unusual shape that moves control flow out of the caller's sight · severity: low · → mitigation: none

### Goal-achievement risk: low
- Behaviour is specified by a working implementation and every acceptance item has a mocked unit test; the parts not provable in-task (live pane placement, real hook firing, focus retention) are covered manually by t1216_5 rather than automatically · severity: low · → mitigation: monitor_shadow_spawn_live_smoke

### Planned mitigations
- timing: after | name: monitor_shadow_spawn_live_smoke | type: test | priority: medium | effort: medium | addresses: mocked-only coverage of the spawn path, its cleanup-hook companion argument, hook idempotence and focus retention | desc: Isolated-tmux smoke test (require_isolated_tmux from tests/lib/tmux_isolation.sh) that really spawns a shadow from the monitor and asserts the pane-died hook's companion argument, that a pre-existing companion hook is not overwritten, and that the client's active window does not change — making the PINNED contract repeatable rather than human-checked.

## Final Implementation Notes

- **Actual work done:** All eight plan steps landed as written — `spawn_shadow`,
  `find_shadow_pane_status` and `load_project_tmux_config` lifted into
  `monitor_core.py` and re-exported through the `tmux_monitor.py` shim;
  `TmuxLaunchConfig.select_window` and the append-only / fail-closed
  `attach_shadow_cleanup_hook` in `agent_launch_utils.py`; `e` / `E` bound in
  `MonitorApp` over a shared `_resolve_shadow_target` prologue with the
  `PaneCategory.AGENT` guard and the fail-closed live duplicate guard; both apps
  reduced to per-app `_spawn_shadow` policy adapters; the two minimonitor test
  files retargeted to the `monitor_core` namespace; new
  `tests/test_monitor_shadow_pick.py` (45 tests) and the shared
  `tests/lib/tmux_socket_containment.py`; docs updated in
  `aidocs/framework/shadow_agent.md` and three website pages.

- **Deviations from plan:** The four recorded in "Implementation notes" above
  (code-object structural control instead of `inspect.getsource`; socket
  containment factored into `tests/lib/tmux_socket_containment.py`;
  `_spawn_shadow -> str | None`; the one unplanned
  `test_monitor_concern_action.py` update). Plus one made while resuming: the
  `select_window` field comment said "both placement branches", but
  `launch_in_tmux` has three — `new_session` issues its own `switch-client` and
  is deliberately **not** gated by the flag (suppressing it would leave a
  brand-new session with no attached client, and no caller combines the two).
  The comment now states that scope explicitly instead of implying the flag
  covers every branch.

- **Issues encountered:** The session implementing this task crashed before
  committing; the work was recovered by re-picking t1216_4, which resumed from
  the `plan_approved` ledger checkpoint with the working tree intact. Step 0's
  tmux preflight was re-run at resume and passed again (`no server running on
  /tmp/tmux-1000/ait`, shell outside tmux), so implementation and verification
  remained within the task's own safety gate.

- **Key decisions:** Unchanged from the plan — D1 (live lookup gates creation,
  cache gates reading), D2 (lift lands in `monitor_core`), D3 (`companion_pane`
  keyword-only with no default; monitor passes `None`, minimonitor passes its
  `TMUX_PANE`), D4 (`schedule_refresh` as a parameter), D5 (`_spawn_shadow` kept
  in both apps as a policy adapter).

- **Build verification:** `bash tests/run_all_python_tests.sh` → 2951 tests,
  **1 failure**, `PYTHON SUITE: FAILED`. The failure is
  `test_board_work_report.WorkReportFullColumnUnderSearchTests.test_hidden_cards_still_listed`
  (`150 != 151`) and is **pre-existing and unrelated to this task** — it lives
  entirely in `aitask_board.py`, which this task does not touch, and reproduces
  from live task data alone (verified with a standalone probe of
  `manager.get_column_tasks("unordered")` vs `TaskCard._parse_filename`). Cause
  recorded under "Upstream defects identified". All task-relevant suites pass:
  `test_monitor_shadow_pick.py` 45, `test_minimonitor_shadow_pick.py` 10,
  `test_minimonitor_concern_action.py` 37, `test_monitor_concern_action.py` 61,
  `tests/test_no_raw_tmux.sh` 5/5, `tests/test_multi_session_monitor.sh` 47/47.

- **Upstream defects identified:**
  - `tests/test_board_work_report.py:483 — test_hidden_cards_still_listed asserts sl.option_count == len(col_tasks) against the LIVE task tree, but action_work_report (aitask_board.py:7271) deliberately skips any task whose filename TaskCard._parse_filename cannot parse; a single malformed task file anywhere in the first populated column therefore fails the whole Python suite. Currently triggered by aitasks/t_refresh_codeagent_suite_default_model_expectations.md (created 2026-07-29), whose filename carries no task number.`

- **Notes for sibling tasks:** The live tmux walkthrough of this change is owned
  by **t1216_5** (five `[t1216_4]` checklist items) — pane placement, real hook
  firing and focus retention are deliberately *not* asserted here, because every
  test in this task is mocked and socket-contained. `tests/lib/tmux_socket_containment.py`
  is reusable by any future mocked-tmux test: list the modules holding an
  import-time `_TMUX` in `CONTAINED_MODULES` and call `assert_contained()`. Note
  that only `agent_launch_utils` needs rebuilding — `monitor_core` holds no
  `_TMUX` of its own. When patching anything on the shadow spawn path, patch the
  **`monitor_core`** namespace, not `minimonitor_app`: the Step 4 import removals
  turn a missed retarget into a loud `AttributeError`, except for
  `launch_in_tmux`, which still exists in both namespaces and is covered by the
  C6 policy test.
