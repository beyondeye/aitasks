---
Task: t943_harden_tmux_sessions_against_whole_server_teardown.md
Worktree: (none — working on current branch, profile 'fast')
Branch: main
Base branch: main
---

# t943 — Harden ait tmux server against whole-server teardown

## Context

All `ait`-managed project tmux sessions share **one tmux server**. The
2026-06-07 incident tore down every project's session at once. Investigation
into this plan **verified the root cause empirically on the live box**: the
tmux server runs inside a *transient systemd user scope*:

```
/user.slice/user-1000.slice/user@1000.service/app.slice/tmux-spawn-<uuid>.scope
```

A systemd **scope** exists to die as a unit. When the graphical session /
`app.slice` is torn down (compositor restart, logout, scope-level kill — all
Hyprland clients live in `app-*.scope` under `app.slice`), the scope dies and
takes the tmux server **and all its sessions** with it. That is the "9 scopes
torn down in the same second" the incident describes.

The framework itself does **not** create these scopes — it `Popen(["tmux",…])`
plainly. The scope comes from how the workspace is app-launched (uwsm/Omarchy).
But the framework **can** ensure that when *it* starts the server, the server
lands in a **persistent** unit that survives an `app.slice` teardown.

**Chosen direction (user-approved): "survive compositor teardown."** Start the
framework-created server in a persistent systemd-user service under
`session.slice`, escaping the transient `app.slice` scope. The server still
ends on full logout (no lingering). **The tmux socket is unchanged** (default
socket) — so this is a lifecycle/cgroup-only change and every other tmux call
site in the framework keeps working untouched. Rejected: dedicated-socket
isolation (wide blast radius across ~50 call sites, interacts with t936, and
only defends the default server); auto-respawn/notify (recovery-not-continuity
— a respawned session is fresh, not your old panes — which the user judged to
have no value vs. actually avoiding the crash).

**Empirically validated during planning** (live, on this Arch+Hyprland box):
`--slice=session.slice` is the load-bearing flag. Default `systemd-run --user`
placement (scope *or* service) inherits the caller's `app.slice` and is
useless; only `--slice=session.slice` lands the server outside `app.slice`,
where it survives `app.slice` teardown and dies only at `user@.service`
teardown (= logout). tmux double-forks; with `Type=forking` systemd records the
daemon as Main PID and supervises it independent of the launching client.

## Approach

A new capability-gated shell helper creates the brand-new detached session
inside a persistent systemd-user service when possible, with a graceful
fallback ladder. It is called from the **single server-creation chokepoint**,
`spawn_session_detached`. No socket plumbing, no Python changes (deferred).

### Recommended systemd-run invocation

```
systemd-run --user \
    --slice=session.slice \
    --unit="ait-tmux-<sanitized-session>-<unique>" \
    --property=Type=forking \
    --property=KillMode=none \
    --collect --quiet -- \
    tmux new-session -d -s "<session>" -c "<root>" -n monitor 'ait monitor'
```

- **`--slice=session.slice`** — the load-bearing change; escapes `app.slice`.
- **`Type=forking`** — matches tmux's double-fork; systemd tracks the daemon.
- **`KillMode=none`** — systemd must not signal the server cgroup when the
  launching transaction finishes; tmux owns its own lifecycle (`kill-server`).
- **`--collect`** — GC the unit if its launching client exits without leaving a
  tracked daemon (the benign TOCTOU loser case), so names don't linger.
- **No `RemainAfterExit`** — unit lifetime tracks the daemon, so `tmux
  kill-server` cleanly deactivates the unit.
- **Unit name**: `ait-tmux-$(systemd-escape -- "$session")-$$-$RANDOM` — unique
  and valid; sanitizes spaces/slashes.

### Step 1 — Add helpers to `.aitask-scripts/lib/terminal_compat.sh`

`terminal_compat.sh` is the established home for portable capability-gated
helpers, owns the `command -v` idioms and `die/warn`, **and is already on the
test-scaffold copy list** (so no new scaffold entry is needed — see
`aidocs/framework/shell_conventions.md`). It is guaranteed-sourced before
`spawn_session_detached` in *both* invocation paths (aitask_ide.sh sources it at
line 6 before tmux_bootstrap.sh; tmux_bootstrap.sh standalone sources it at
line ~183 before calling spawn_session_detached). Add:

```bash
# --- Persistent-scope tmux session spawn (t943) ---------------------------
# ait_systemd_user_available
# Returns 0 iff a usable systemd --user manager is reachable for systemd-run.
ait_systemd_user_available() {
    [[ -n "${AIT_NO_SYSTEMD_RUN:-}" ]] && return 1   # test/escape hatch
    command -v systemd-run >/dev/null 2>&1 || return 1
    command -v systemctl   >/dev/null 2>&1 || return 1
    [[ -n "${XDG_RUNTIME_DIR:-}" ]] || return 1
    systemctl --user is-system-running >/dev/null 2>&1 && return 0
    [[ "$(systemctl --user is-system-running 2>/dev/null)" == "degraded" ]]
}

# ait_tmux_new_session_persistent <session> <root> <window> <command>
# Create a brand-new DETACHED tmux session whose SERVER lands in a persistent
# systemd-user service under session.slice, so a compositor / app.slice
# teardown does not reach it. Socket unchanged (default). Falls back to setsid,
# then plain tmux. Precondition: caller has confirmed the server does NOT yet
# exist (otherwise wrapping is pointless — a plain new-session just attaches).
ait_tmux_new_session_persistent() {
    local session="$1" root="$2" window="$3" cmd="$4"
    if ait_systemd_user_available; then
        local safe unit
        safe="$(systemd-escape -- "$session" 2>/dev/null || echo session)"
        unit="ait-tmux-${safe}-$$-${RANDOM}"
        systemd-run --user --slice=session.slice --unit="$unit" \
            --property=Type=forking --property=KillMode=none \
            --collect --quiet -- \
            tmux new-session -d -s "$session" -c "$root" -n "$window" "$cmd"
        return $?
    fi
    if command -v setsid >/dev/null 2>&1; then
        setsid tmux new-session -d -s "$session" -c "$root" -n "$window" "$cmd"
        return $?
    fi
    tmux new-session -d -s "$session" -c "$root" -n "$window" "$cmd"
}
```

### Step 2 — Call from `spawn_session_detached` (`.aitask-scripts/lib/tmux_bootstrap.sh` ~156–163)

Replace only the inner `tmux new-session` invocation; preserve the
`has-session` guard, the `|| { … return 4; }` failure contract, and (untouched,
earlier) the `BOOTSTRAP_FAILED:stale_path` → `return 42` sentinel that
`tui_switcher._ensure_session_live` parses:

```bash
    if ! tmux has-session -t "$session_t" 2>/dev/null; then
        # First session => this call creates the tmux SERVER. Spawn it inside a
        # persistent systemd-user service (session.slice) so a compositor /
        # app.slice teardown no longer kills the server (t943). Socket
        # unchanged; only the new server's cgroup placement differs.
        # new-session -s takes a literal session name; do not prefix '='.
        ait_tmux_new_session_persistent "$session" "$root" monitor 'ait monitor' \
            || {
                echo "spawn_session_detached: tmux new-session failed for '$session'" >&2
                return 4
            }
    fi
```

No change to `aitask_ide.sh` (delegates to `spawn_session_detached`, line 100).
No change to `agent_launch_utils.py` (deferred — see Risk / mitigations).

### Step 3 — Add `tests/test_tmux_persistent_scope.sh`

Bash style consistent with the suite (`tests/lib/asserts.sh` →
`assert_eq`/`assert_contains`; `tests/lib/require_no_tmux.sh` → `require_no_tmux`
with `TMUX_TMPDIR` isolation):

1. **Always-on (fallback rung):** with `AIT_NO_SYSTEMD_RUN=1` + isolated
   `TMUX_TMPDIR`, source `terminal_compat.sh`, assert the helper is defined,
   call it, `assert_eq 0 $?`; then assert session exists, window name is
   `monitor`, and pane cwd matches `<root>` — proving the fallback preserves
   session name / cwd / window / command.
2. **systemd-guarded:** `if ait_systemd_user_available; then` create a session on
   an isolated socket, read `/proc/<server-pid>/cgroup`, `assert_contains
   '/session.slice/'` and assert it does **not** contain `/app.slice/`; then
   clean up (`tmux kill-server`; `systemctl --user stop 'ait-tmux-*'`).
   `else echo "SKIP: systemd --user unavailable"; fi` (matches existing skip
   convention). CI runners typically have no reachable user manager, so the
   systemd assertions are skipped there and the fallback rung is exercised.

## Verification

- **Fallback works (any host):**
  `AIT_NO_SYSTEMD_RUN=1 bash .aitask-scripts/lib/tmux_bootstrap.sh <project>` →
  `tmux has-session -t '=aitasks'` succeeds; window `monitor` present.
- **Server escapes app.slice (systemd host):** `ait ide` in a fresh workspace,
  then find the server pid (`pgrep -x tmux` / parent of a `#{pane_pid}`) and
  `cat /proc/<pid>/cgroup` → contains `/session.slice/ait-tmux-…service`, **not**
  `/app.slice/`. `systemctl --user list-units 'ait-tmux-*'` shows it active.
- **Survives teardown (the real proof):** with the server in `session.slice`,
  restart the Hyprland compositor (or `systemctl --user stop` a sibling
  `app-Hyprland-*.scope`) → `tmux list-sessions` still works. Control: rerun with
  `AIT_NO_SYSTEMD_RUN=1` (server in `app.slice`) and confirm the same teardown
  kills it — demonstrating the contrast.
- **Regression:** run the existing tmux suite from a tmux-free terminal
  (`bash tests/test_tmux_control.sh`, `test_tmux_run_parity.sh`,
  `test_tmux_exact_session_targeting.sh`) — all green; run the new test.
- `shellcheck .aitask-scripts/lib/terminal_compat.sh .aitask-scripts/lib/tmux_bootstrap.sh`.

See **Step 9 (Post-Implementation)** of the task-workflow for cleanup, archival,
and merge.

## Risk

### Code-health risk: medium
- Modifies the load-bearing server-creation path (`spawn_session_detached`,
  used by every `ait ide` / switcher bootstrap). Mitigated by the graceful
  fallback ladder (systemd-run → setsid → plain tmux = today's behavior), but a
  subtle `systemd-run` misbehavior could disrupt the primary startup path ·
  severity: medium · → mitigation: TBD
- Introduces a systemd interaction (`Type=forking` / `KillMode=none` / slice
  survival) that is environment-sensitive and only partially testable in CI
  (user-manager often absent) · severity: low · → mitigation: TBD

### Goal-achievement risk: medium
- **Partial coverage:** the fix only protects *framework-created* servers. The
  actual 2026-06-07 server was created by the user's own Hyprland `tmux-spawn`
  keybind (outside the repo), so the complete fix also needs that launcher
  hardened — a personal Omarchy-config change, separate from this task ·
  severity: medium · → mitigation: document_tmux_workspace_keybind_persistence
- Secondary framework server-creation site `launch_in_tmux()` (new_session
  branch) in `agent_launch_utils.py` is left unhardened (deferred to keep this
  change surgical and shell-only) · severity: low · → mitigation:
  harden_launch_in_tmux_python_server_creation

### Planned mitigations
- timing: after | name: harden_launch_in_tmux_python_server_creation | type: enhancement | priority: low | effort: low | addresses: secondary server-creation site in agent_launch_utils.py | desc: Mirror the persistent systemd-user-service (session.slice) server spawn in the Python launch_in_tmux() new_session branch, gated on systemd-run availability + a tmux has-session precheck, with the same setsid/plain fallback ladder.
- timing: after | name: document_tmux_workspace_keybind_persistence | type: documentation | priority: low | effort: low | addresses: user-launched workspace server not covered by framework hardening | desc: Add a troubleshooting/docs note (and cross-reference the omarchy guidance) explaining that a workspace launcher/keybind which starts the ait tmux server should place it in a persistent slice (e.g. systemd-run --user --slice=session.slice) so a user-created server also survives compositor/app.slice teardown.

## Final Implementation Notes

- **Actual work done:** Implemented all three plan steps.
  1. Added `ait_systemd_user_available()` and `ait_tmux_new_session_persistent()`
     to `.aitask-scripts/lib/terminal_compat.sh` (capability gate +
     `systemd-run --user --slice=session.slice` spawn with a
     setsid → plain-tmux fallback ladder; `AIT_NO_SYSTEMD_RUN` escape hatch).
  2. Replaced the inner `tmux new-session` in `spawn_session_detached`
     (`.aitask-scripts/lib/tmux_bootstrap.sh`) with a call to the new helper,
     preserving the `has-session` guard, the `return 4` failure contract, and
     the untouched `BOOTSTRAP_FAILED:stale_path` → `return 42` sentinel.
  3. Added `tests/test_tmux_persistent_scope.sh` (Tier 0 helper presence,
     Tier 1 always-on fallback rung, Tier 2 systemd-guarded session.slice
     placement that skips cleanly where no user manager is reachable).
- **Deviations from plan:**
  - The plan referenced `tests/lib/require_no_tmux.sh` / `require_no_tmux`; the
    current isolation helper is `tests/lib/tmux_isolation.sh` /
    `require_isolated_tmux` (renamed since the plan was written). Used the
    actual helper.
  - Tier 2 **reconstructs** the `systemd-run` invocation with
    `--setenv=TMUX_TMPDIR=<isolated>` instead of calling the helper directly:
    the production helper intentionally does NOT thread `TMUX_TMPDIR` (it must
    spawn on the default socket), so calling it in-test would create a server on
    the user's real default tmux server. The reconstruction uses the identical
    load-bearing flags (`--slice=session.slice`, `Type=forking`,
    `KillMode=none`, `--collect`), so it still verifies the session.slice
    placement property. Tier 1 exercises the real helper end-to-end.
- **Issues encountered:**
  - `tmux display-message -p -t '=<session>'` returns empty for pane/window
    formats (a session-only target has no pane context) → used
    `list-windows` / `list-panes -F` instead, the reliable scripting form.
  - The setsid fallback brings the server up asynchronously, so
    `pane_current_path` (derived from the pane process's `/proc` cwd) can
    momentarily read the launcher's cwd before settling into `-c <root>`. Fixed
    by polling the cwd in the test until it reflects the requested root (window
    name / start command are tmux metadata and need no poll).
- **Key decisions:** Socket left unchanged (default) — this is a cgroup/lifecycle
  change only, so every other tmux call site keeps working untouched. Verified
  empirically on the live Arch+Hyprland box that `--slice=session.slice` lands
  the server in `/user.slice/.../session.slice/ait-tmux-*.service` and **not**
  under `app.slice`.
- **Verification run:** new test 9/9 (stable over 3 runs, both tiers exercised);
  `shellcheck` clean on both production files; regression tests
  `test_tmux_control`, `test_tmux_run_parity`,
  `test_tmux_exact_session_targeting`, `test_tmux_control_resilience`,
  `test_kill_agent_pane_smart` all green. Pre-existing/unrelated:
  `test_multi_session_primitives.sh` (19/20) fails a stale `AitasksSession`
  field-list assertion in `agent_launch_utils.py` — untouched by this task; it
  is a test-vs-code drift (test gap), a candidate for `/aitask-qa`, not a code
  defect seeded here.
- **Upstream defects identified:** None.
- **Follow-up tasks created during planning discussion:** t952 (centralize tmux
  invocations behind a shared gateway) and t953 (dedicated persistent socket,
  depends on t952) — the broader tmux-refactoring groundwork for the
  wish/SSH + hosted directions in `aidocs/applink/wish_ssh_evaluation.md`.
  These are independent of t943's narrow scope.
