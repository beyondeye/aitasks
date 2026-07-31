---
Task: t1353_monitor_shadow_spawn_live_smoke.md
Worktree: (none — current branch)
Branch: main
Base branch: main
Output branch: main
---

# p1353 — Live isolated-tmux smoke test for monitor shadow spawn

## Context

t1216_4 ported the shadow spawn keys `e` / `E` to the full monitor and, in doing
so, hardened four lifecycle contracts in code every agent launch flows through
(`agent_launch_utils.TmuxLaunchConfig.select_window`,
`attach_shadow_cleanup_hook`'s append-don't-overwrite rule,
`monitor_core.spawn_shadow`'s stamp verification and fail-closed duplicate
guard). Every one of those contracts is currently proven **only through mocks**
— `tests/test_monitor_shadow_pick.py` (45 tests) patches `launch_in_tmux`,
`resolve_pane_id_by_pid` and `attach_shadow_cleanup_hook` at the `monitor_core`
namespace and never issues a tmux call. The parts that cannot be mocked (real
pane placement, a real `pane-died` hook firing, real window-focus retention) are
covered only by the human walkthrough owned by t1216_5.

The most consequential of those contracts is **PINNED**: the monitor must pass
the newly created **shadow** pane as `aitask_companion_cleanup.sh`'s `companion`
argument, never its own `TMUX_PANE`. Job 2 of that script runs
`kill-pane -t "$companion"` with **no marker check**
(`.aitask-scripts/aitask_companion_cleanup.sh:57-59`), so a monitor pane passed
there would be killed on the followed agent's exit — arbitrarily later, long
after the session that armed it ended. A mock can only prove the *argument
string*; nothing today proves the *effect*.

This task adds the live leg: a `tmux_destructive` smoke test that really spawns
a shadow through `MonitorApp.action_launch_shadow` against a throwaway tmux
server, making the PINNED contract repeatable rather than human-checked.

### Pick-time safety gate — PASSED (measured)

`tui_conventions.md` "Tmux-stress tasks" requires implementing this from a shell
whose tmux server carries no code agents worth keeping. Measured at pick time:

```
$ tmux -L ait list-panes -a …   → no server running on /tmp/tmux-1000/ait
$ tmux list-panes -a …          → error connecting to /tmp/tmux-1000/default
$ echo $TMUX $TMUX_PANE         → both unset
```

No tmux server exists and this shell is not inside tmux. Implementation and live
verification may proceed.

## Acceptance criteria — one correction, one addition

**AC item 2 is split into 2a + 2b (user-confirmed).** The task file asks to arm
an agent with a cleanup hook naming companion A, spawn from the monitor, and
confirm "the hook still names A **and** the new entry was appended at the next
free `pane-died[N]` index". That conjunction is unreachable in the shipped code:
`attach_shadow_cleanup_hook` returns `"existing"` and appends **nothing** when a
`pane-died` hook already references `aitask_companion_cleanup.sh`
(`agent_launch_utils.py:1432-1434`). Appending at the next free index is the
*separate* case where the pre-existing hook is **unrelated**
(`agent_launch_utils.py:1439-1444`). The AC as written merges two distinct
branches of the same function. Both real contracts are asserted:

- **2a** — a pre-existing *cleanup* hook survives naming companion A, and **no
  second cleanup entry** is appended.
- **2b** — a pre-existing *unrelated* `pane-died[0]` hook survives, and the
  cleanup hook is appended at `pane-died[1]`.

The task file's AC text is updated to say this as part of the change.

**Addition beyond the AC (user-confirmed):** the smoke also **fires** the hook
for real — kills the agent process, watches `aitask_companion_cleanup.sh` run,
and asserts the shadow dies while a monitor stand-in pane in another window
survives — plus a bypass control proving that assertion discriminates.

## Approach

One new file plus one additive helper: **`tests/test_monitor_shadow_spawn_live.sh`** — a bash driver
(sources `tests/lib/tmux_isolation.sh`, builds the fixture server, tears it
down) wrapping a Python heredoc that drives the real app object. This is the
established shape for live-tmux tests in this repo; model on
`tests/test_kill_agent_pane_smart.sh`.

Bash tests are not part of `tests/run_all_python_tests.sh`, which is exactly
right for a `tmux_destructive` test — it stays opt-in and run individually.

### Entry point and the one mocked seam

The test drives **`MonitorApp.action_launch_shadow()`** on an app built with
`MonitorApp.__new__` (the `_mk_app` shape from
`tests/test_monitor_shadow_pick.py:140`), bound to a **real**
`TmuxMonitor(session=…)` whose `tmux_run` falls through to subprocess (no
control client started). Everything below the action is real: `_resolve_shadow_target`
→ `monitor_core.spawn_shadow` → `agent_launch_utils.launch_in_tmux` → tmux →
`resolve_pane_id_by_pid` → the `@aitask_shadow_target` stamp →
`attach_shadow_cleanup_hook`.

Exactly **one** seam is replaced: `monitor_app.resolve_dry_run_command` is
patched to return `tail -f /dev/null`. The real one resolves an actual code-agent
command line; the contracts under test are about pane placement, hook wiring and
window focus, not about what the shadow process is.

Binding→action wiring (`e` → `launch_shadow`, `E` → `launch_shadow_pick`) is
already pinned by `test_monitor_shadow_pick.py::BindingRegistrationTests`, so the
live leg starts at the action rather than driving a Textual `run_test()` event
loop — which would need `MonitorApp.__init__` + `on_mount` discovery and buy no
additional tmux-side coverage.

### Safety guard — refuse, don't just isolate

`require_isolated_tmux` only *isolates*; it never refuses. That was a deliberate
t936 decision (the old `tests/lib/require_no_tmux.sh`, t750 / commit
`36acc9011`, aborted with exit 2 whenever `$TMUX` was set or any default-socket
server was reachable, which made all 8 tmux tests unrunnable on a dev box
running tmux). Isolation alone is **not** sufficient here: cases E and F fire
`aitask_companion_cleanup.sh` for real, and that script runs raw `tmux` with no
socket flag by design — the task file calls this out explicitly.

Add a second function to `tests/lib/tmux_isolation.sh` (same file, same domain,
its header already narrates this history):

```bash
require_clean_ait_server   # exit 2 unless it is safe to run destructive live tests
```

It encodes the task's own documented pick-time preflight:

1. **`$TMUX` is set** → refuse. Message says to open a terminal outside tmux.
2. **The dedicated `-L ait` server is running and holds any pane that is an
   agent, a shadow (`@aitask_shadow_target` non-empty), or a framework TUI** →
   refuse, printing the offending panes. Probe is verbatim the preflight from
   `tui_conventions.md` / the task file:
   `tmux -L ait list-panes -a -F '#{pane_id} #{window_name} #{pane_current_command} [#{@aitask_shadow_target}]'`.
3. **Any other reachable server** (personal default socket) → **warn and
   continue**, listing sessions. Refusing there is the over-strictness t936
   removed, and the fixture never addresses that socket.
4. **Escape hatch** `AIT_LIVE_TMUX_TEST_FORCE=1` overrides 1–2, for a dedicated
   CI box. Documented in the function header and in the refusal message.

**Ordering is load-bearing:** `require_clean_ait_server` must run **before**
`require_isolated_tmux`. The latter unsets `TMUX` and repoints `TMUX_TMPDIR`, so
after it runs the guard could neither see `$TMUX` nor resolve `-L ait` to the
user's real socket (`/tmp/tmux-<uid>/ait`) — it would probe the empty isolated
dir and pass vacuously. This gets its own comment at the call site and in the
function header.

### Containment

Guard first, then `require_isolated_tmux` (unsets `TMUX`/`TMUX_PANE`, redirects
`TMUX_TMPDIR`, pins `AITASKS_TMUX_SOCKET=""`), then a per-run
`TMUX_TMPDIR=$FIXTURE_DIR`.
Because the Python process starts *after* the env is set, `agent_launch_utils`'s
import-time `_TMUX` singleton is built inside it — no rebuild needed (unlike the
mocked suite's `TmuxSocketContainmentMixin`, which exists for full-suite
discovery ordering). Containment is asserted two ways before any mutation:

1. Statically — `agent_launch_utils._TMUX.socket_args == []` (the `""` escape
   hatch, `lib/tmux_exec.py:87-91`).
2. Positively — a gateway round-trip
   `_TMUX.run(["display-message", "-p", "#{socket_path}"])` returns a path under
   `$FIXTURE_DIR`. This proves the gateway reaches the fixture server, rather
   than only proving it carries no `-L` flag.

`aitask_companion_cleanup.sh`'s raw `tmux` is contained by construction: hook
jobs inherit `$TMUX` from the firing server (documented at that script's
header), and the server was started under `TMUX_TMPDIR=$FIXTURE_DIR`. Both
resolution paths land on the fixture socket.

### Fixture

`tmux new-session -d -x 200 -y 50 -s "ait_shadowlive_$$" -n home` — the wide
geometry matters because the split branch passes `-l 60`. A `monitor` stand-in
pane lives in the `home` window; each case gets its own agent window. The
session's current window is reset to `home` before each spawn, and asserted via
`list-windows -F '#{window_active} #{window_name}'` — the detached session's
current window *is* what `select-window` / `new-window` mutate and what an
attached client would follow.

## Test cases

Two project roots are built under the fixture dir: `proj_split/` (no
`project_config.yaml` → `{}` → same-window split, width 60) and `proj_window/`
with `aitasks/metadata/project_config.yaml` containing
`tmux:\n  shadow_same_window: false`. Both are read by the real
`monitor_core.load_project_tmux_config` (`monitor_core.py:2528`).

| # | Case | Asserts |
|---|---|---|
| A | split branch spawn | one new pane in the agent's window; exactly one pane carries `@aitask_shadow_target == <agent>`; active window still `home` (**AC3, split**); `remain-on-exit` is `on`; hook argv is `… aitask_companion_cleanup.sh <agent> <shadow>` and the monitor stand-in pane id appears **nowhere** in `show-hooks` output (**AC1**) |
| B | `shadow_same_window: false` | a new window `agent-shadow-<task_id>` exists; the shadow pane is in it and stamped; active window still `home` (**AC3, new-window**); hook names the shadow |
| C | pre-existing *cleanup* hook (**AC2a**) | pre-arm with the real `attach_shadow_cleanup_hook(agentC, companionA)`; after the monitor spawn, `show-hooks -p -t agentC` still holds **exactly one** cleanup entry and it still names `companionA`; the spawn still succeeded (shadow created + stamped, notification is "Launched shadow agent", not the "could not be wired" warning) |
| D | pre-existing *unrelated* hook (**AC2b**) | pre-set `pane-died[0] display-message ait-unrelated-sentinel`; after the spawn, `[0]` still carries the sentinel **and** `[1]` is the cleanup hook naming `<agentD> <shadowD>` — both entries asserted, since asserting only "our hook is present" would pass even if the unrelated one were destroyed |
| E | hook fires for real (**AC1, behavioral**) | `kill <agent_pane_pid>` on case A's agent → poll ≤10s: the shadow pane is gone, and the monitor stand-in pane in `home` is **alive** |
| F | bypass control for E | a throwaway agent pane armed via `attach_shadow_cleanup_hook(V, victim)` where `victim` is a disposable pane in another window; killing V's process **does** kill `victim` — proving E would catch a wrong companion rather than passing because tmux is inert |
| G | focus negative control (**AC3**) | call `monitor_core.spawn_shadow(..., companion_pane=None, select_window=True, ...)` — minimonitor's policy value — on a fresh agent, and assert the active window **does** move. Run for both placement branches. Proves A/B's "active window unchanged" discriminates on `select_window=False` rather than on the fixture being static |

Every case reports its own `OK <name>`; the script ends with
`PASS: tests/test_monitor_shadow_spawn_live.sh` and exits non-zero on the first
failure (`set -euo pipefail` + `sys.exit(msg)` in the Python body).

### Teardown

`trap` on EXIT: for every pane armed during the run, `set-hook -pu … pane-died`
and `set-option -pu … remain-on-exit`, then `tmux kill-server`, then
`rm -rf "$FIXTURE_DIR"`. Defusing before `kill-server` keeps teardown from
racing a hook job. Best-effort (`|| true`) so a mid-run failure still cleans up.

## Files

- **`tests/test_monitor_shadow_spawn_live.sh`** (new, ~450 lines) — the whole
  deliverable.
- **`tests/lib/tmux_isolation.sh`** — additive: new `require_clean_ait_server`
  function (see Safety guard). No existing caller changes; `require_isolated_tmux`
  is untouched, so the 8 existing tmux tests keep running alongside a live
  session exactly as t936 intended.
- **`aitasks/t1353_monitor_shadow_spawn_live_smoke.md`** — AC item 2 rewritten as
  2a + 2b; the hook-firing addition (E/F) recorded.
- **`aidocs/framework/shadow_agent.md`** — one line under the companion-pane /
  hook-idempotence rules pointing at the live smoke as their executable proof
  (bidirectional doc↔test cross-reference; the doc already states both rules).
- **`aidocs/framework/tui_conventions.md`** — add the new script to the
  tmux-destructive test list if one is enumerated there; otherwise no change.

No production code changes. If a case fails, that is a real defect in
`monitor_app` / `monitor_core` / `agent_launch_utils` and is fixed there.

## Verification

```bash
bash tests/test_monitor_shadow_spawn_live.sh        # the new test (from a clean shell)
bash tests/test_no_raw_tmux.sh                      # tests/ is out of scope, but confirm
python3 tests/test_monitor_shadow_pick.py           # mocked leg still green
python3 tests/test_minimonitor_shadow_pick.py
bash tests/run_all_python_tests.sh                  # read ONLY the last line
```

The preflight is no longer a manual step — `require_clean_ait_server` runs it
inside the script and exits 2 with an actionable message when it fails.

**Guard negative controls** (prove the refusal actually fires, and that it is
not vacuous):

```bash
TMUX=fake bash tests/test_monitor_shadow_spawn_live.sh   # → exit 2, no server created
# with a throwaway `-L ait` server holding a pane stamped @aitask_shadow_target:
bash tests/test_monitor_shadow_spawn_live.sh             # → exit 2, names that pane
AIT_LIVE_TMUX_TEST_FORCE=1 bash tests/…                  # → runs
```

The second control matters most: it proves the `-L ait` probe runs *before*
`require_isolated_tmux` repoints `TMUX_TMPDIR`. Reversing the two lines makes
that control pass silently — the guard would probe an empty isolated dir.

**Harness-can-fail proof.** Each of the six live contracts is broken once, in
source, to confirm the smoke exits non-zero and names the right case:
`companion_pane=None` → `os.environ.get("TMUX_PANE")` in `monitor_app._spawn_shadow`
(E + A fail); `select_window=False` → `True` (A/B fail, G still passes);
the `has_cleanup` early return removed (C fails); `slot = max(indices) + 1` →
`0` (D fails); the `@aitask_shadow_target` stamp skipped (A fails). Baseline
restored after each.

## Risk

### Code-health risk: low
- `require_clean_ait_server` lands in `tests/lib/tmux_isolation.sh`, which all 8
  existing tmux tests source. The addition is a new function with no call sites
  outside the new test, so those tests are unaffected — but the file is now
  shared between an "isolate, never refuse" policy (t936) and an "refuse when
  unsafe" one, and the distinction must stay legible in the header ·
  severity: low
- The change is test-only and additive — one new file plus doc/AC text. It
  cannot regress runtime behaviour, and it is a bash test outside
  `run_all_python_tests.sh`, so it cannot destabilise the aggregate suite ·
  severity: low
- The test drives `MonitorApp.__new__` and sets private attributes
  (`_focused_pane_id`, `_snapshots`, `_task_cache`), so an internal rename in
  `monitor_app` breaks it. This is the same coupling every existing monitor test
  already carries, and a break is loud rather than silent · severity: low

### Goal-achievement risk: medium
- Cases E and F fire a real `pane-died` hook and poll for pane disappearance.
  Hook jobs are asynchronous, so a too-short poll would flake and a too-long one
  would mask a genuine failure. Bounded by a ≤10s poll with an explicit failure
  message naming which pane was still present · severity: medium
- "The client's active window does not change" is asserted on the **detached
  session's** current window, not on an attached client's view. That is the
  state `select-window` / `new-window` mutate and the state a client follows, so
  it is the right ground truth — but it is one step removed from the literal AC
  wording, and a bug that moved only an attached client's window would be
  invisible · severity: low
- The one mocked seam (`resolve_dry_run_command`) means the smoke never proves
  the real shadow command line resolves. That is deliberate — resolving it would
  launch a real code agent — and it is already covered by the mocked suite ·
  severity: low

Post-implementation this plan is consolidated with Final Implementation Notes,
then Step 9 (Post-Implementation) runs archival per the shared workflow.
