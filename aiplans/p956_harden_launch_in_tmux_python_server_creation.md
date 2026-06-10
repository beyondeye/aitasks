---
Task: t956_harden_launch_in_tmux_python_server_creation.md
Worktree: (none — working on current branch, profile 'fast')
Branch: main
Base branch: main
---

# t956 — Harden `launch_in_tmux()` Python server creation

## Context

t943 hardened the framework's tmux **server-creation chokepoint** so a
compositor / `app.slice` teardown can no longer reap the server and every
session with it. It did this by spawning the brand-new detached session inside
a persistent `systemd --user` service under `session.slice` (via
`ait_tmux_new_session_persistent` in `terminal_compat.sh`), called from the
bash chokepoint `spawn_session_detached` (`tmux_bootstrap.sh`). Socket
unchanged.

t943 deliberately left **one secondary server-creation site unhardened** to
keep that change surgical and shell-only: the Python `launch_in_tmux()`
`new_session` branch in `.aitask-scripts/lib/agent_launch_utils.py`. That
branch runs `tmux new-session -d -s <session>` — and when **no tmux server is
yet running**, that call *creates* the server, landing it in whatever
(possibly transient `app.slice`) scope the launching process sits in. This is
exactly the failure mode t943 fixed for the bash path. t956 (a risk-mitigation
"after" follow-up of t943) mirrors that hardening into the Python path.

This is the in-practice gap: TUIs (board, monitor, codebrowser, …) call
`launch_in_tmux(new_session=True)` to start an agent in a fresh tmux session.
When the TUI itself runs **inside** tmux, a server already exists → the call
just attaches a new session (no hardening needed). But when a TUI runs in a
plain terminal (not tmux) and launches the first session, **that** call creates
the server — and today it is unprotected.

## Approach

Mirror `ait_tmux_new_session_persistent` / `ait_systemd_user_available` (t943)
in Python, confined to the `new_session` branch of `launch_in_tmux()`. Replicate
the `systemd-run` invocation directly (the task sanctions "either shell out to
the bash helper or replicate the systemd-run invocation directly"); replication
keeps the file's existing idiom — every tmux interaction in
`agent_launch_utils.py` is already a direct `subprocess` call, never a bash
shell-out — preserves the exact `cwd=None` semantics, and stays cleanly
unit-testable in the existing `subprocess`-mock test style. The duplication is
acknowledged as temporary: **t952** (centralize tmux invocations behind a shared
gateway) is slated to absorb both copies.

### Precheck decision (deviation from literal task text — please confirm)

The task says: gate on *"a `tmux has-session` precheck (so it only wraps a
genuine SERVER creation, not an attach)"*. I plan to implement the **stated
goal** ("genuine SERVER creation, not an attach") with a **server-existence**
check rather than a literal `has-session -t <session>` on the target session,
because the literal form does **not** achieve the goal:

- A `has-session -t =<session>` precheck only tells you whether *that one
  session* exists. If a server is already running with *other* sessions (the
  common TUI-inside-tmux case) but not the target name, `has-session` fails —
  and you would wrap an **attach** in `systemd-run` anyway (pointless, and
  leaves a spurious — though `--collect`-GC'd — transient unit on every launch).
- "Genuine server creation" ⟺ **no tmux server is running at all**. A tmux
  server always has ≥1 session, so *"`tmux list-sessions` returns empty ⟺ no
  server"* is the precise, race-equivalent signal. I'll reuse the existing
  `get_tmux_sessions()` helper: `server_running = bool(get_tmux_sessions())`.

So: wrap in the persistent ladder **iff no server is running**; otherwise run
plain `tmux new-session` (today's behavior — and a duplicate-name attempt still
surfaces tmux's normal "duplicate session" error). The bash reference
(`spawn_session_detached`) uses a target `has-session` guard and accepts this
same imperfection; t956 implements the stricter, goal-faithful check. *(If you'd
rather match the bash reference literally, say so and I'll switch to
`has-session -t =<session>`.)*

### Changes — all in `.aitask-scripts/lib/agent_launch_utils.py`

**1. Two new module-private helpers** (mirroring the bash, placed near
`launch_in_tmux`):

```python
def _systemd_user_available() -> bool:
    """Mirror ait_systemd_user_available (t943): True iff a usable
    systemd --user manager is reachable for systemd-run."""
    if os.environ.get("AIT_NO_SYSTEMD_RUN"):      # test/escape hatch
        return False
    if shutil.which("systemd-run") is None or shutil.which("systemctl") is None:
        return False
    if not os.environ.get("XDG_RUNTIME_DIR"):
        return False
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-system-running"],
            capture_output=True, text=True, timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False
    return result.returncode == 0 or result.stdout.strip() == "degraded"


def _persistent_new_session_prefix(session: str) -> list[str] | None:
    """systemd-run prefix that lands the new tmux server in a persistent
    session.slice service (t943/t956), or None when systemd --user is
    unavailable. Mirrors the load-bearing flags from
    ait_tmux_new_session_persistent."""
    if not _systemd_user_available():
        return None
    safe = "session"
    try:
        esc = subprocess.run(["systemd-escape", "--", session],
                             capture_output=True, text=True, timeout=5)
        if esc.returncode == 0 and esc.stdout.strip():
            safe = esc.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    unit = f"ait-tmux-{safe}-{os.getpid()}-{os.urandom(3).hex()}"
    return ["systemd-run", "--user", "--slice=session.slice",
            f"--unit={unit}", "--property=Type=forking",
            "--property=KillMode=none", "--collect", "--quiet", "--"]
```

(`os.urandom(3).hex()` gives the `$$-$RANDOM`-style uniqueness without a new
`import random`; `os` / `shutil` / `subprocess` are already imported.)

**2. A small argv-builder for the new-session creation path** (keeps
`launch_in_tmux` readable and is the unit-test seam):

```python
def _new_session_tmux_argv(session: str, window: str, command: str,
                           cwd_args: list[str], cwd: str | None) -> list[str]:
    """Build the argv that creates a detached tmux session, wrapping a genuine
    SERVER creation in a persistent session.slice systemd-user service
    (t956, mirroring t943). Falls back setsid -> plain tmux. When a server is
    already running this is an attach, so today's plain invocation is used."""
    base = ["tmux", "new-session", "-d", "-s", session, "-n", window]
    if get_tmux_sessions():
        # Server already running -> new-session attaches; preserve today's
        # default-cwd behavior (no forced -c when cwd is None).
        return base + cwd_args + [command]
    # No server running -> this call creates it. The systemd-run / setsid rungs
    # sever the launcher relationship, so pass an explicit -c (default-cwd
    # inheritance is lost once detached); cwd or os.getcwd() reproduces today's
    # inherited-cwd behavior.
    created = base + ["-c", cwd or os.getcwd(), command]
    prefix = _persistent_new_session_prefix(session)
    if prefix is not None:
        return prefix + created
    if shutil.which("setsid"):
        return ["setsid"] + created
    return created
```

**3. Use it in the `new_session` branch of `launch_in_tmux()`** (lines ~544-565).
Replace only the construction of `tmux_cmd`; the `Popen` + `wait`, the
`returncode`/stderr error contract, the `_query_first_pane_pid` capture, and the
`TMUX` switch-client block are all unchanged:

```python
    if config.new_session:
        tmux_cmd = _new_session_tmux_argv(
            config.session, config.window, command, cwd_args, config.cwd)
        proc = subprocess.Popen(tmux_cmd, stderr=subprocess.PIPE)
        proc.wait()
        if proc.returncode != 0:
            stderr = proc.stderr.read().decode() if proc.stderr else ""
            return None, f"tmux new-session failed: {stderr}"
        pane_pid = _query_first_pane_pid(config.session, config.window)
        if os.environ.get("TMUX"):
            subprocess.Popen(
                ["tmux", "switch-client", "-t", tmux_session_target(config.session)]
            )
        return pane_pid, None
```

The `new_window` and `split-window` branches are **untouched** (they always
attach to an existing server — never a creation site).

### Tests — extend `tests/test_launch_in_tmux_pane_pid.py`

Add a `TestNewSessionPersistentSpawn` class (mock style consistent with the
file — `unittest.mock.patch`, `_FakeRunResult`). Test `_new_session_tmux_argv`
directly (the seam), patching `agent_launch_utils.get_tmux_sessions`,
`_systemd_user_available`, `shutil.which`, and `subprocess.run` (systemd-escape):

1. **Server running** (`get_tmux_sessions` → `["x"]`) → argv == plain
   `tmux new-session …` (no `systemd-run`, no `setsid`); with `cwd=None` no
   forced `-c`.
2. **No server + systemd available** → argv begins with `systemd-run --user
   --slice=session.slice`, includes `--property=Type=forking`,
   `--property=KillMode=none`, `--collect`, and the `tmux new-session … -c …`
   tail; `-c` present even when `cwd=None`.
3. **No server + systemd unavailable + setsid present** → argv begins with
   `setsid`, then `tmux new-session … -c …`.
4. **No server + neither** → plain `tmux new-session … -c …` (still `-c`).
5. `_systemd_user_available` returns False when `AIT_NO_SYSTEMD_RUN` is set
   (patch `os.environ`).

Existing `TestLaunchInTmuxNewSession` tests stay green: their blanket
`subprocess.run` mock returns a non-empty `list-sessions` result, so
`get_tmux_sessions()` reports a server running → the plain (today's) path is
taken. The live `TestLaunchInTmuxIntegration` also stays on the plain path on
any box that already has a tmux server.

## Verification

- `python3 -m pytest tests/test_launch_in_tmux_pane_pid.py -q` (or
  `python3 tests/test_launch_in_tmux_pane_pid.py`) — new + existing green.
- Behavior parity (any host): `AIT_NO_SYSTEMD_RUN=1` forces the fallback rung;
  confirm a no-server launch still creates the detached session with the right
  name / window / cwd / command (mirrors t943's Tier-1 assertions).
- Server escapes `app.slice` (systemd host, no server running): drive a
  `new_session` launch, then `cat /proc/<server-pid>/cgroup` → contains
  `/session.slice/ait-tmux-…service`, not `/app.slice/`.
- `python3 -c "import ast,sys; ast.parse(open('.aitask-scripts/lib/agent_launch_utils.py').read())"`
  (syntax) — repo has no Python linter configured for this module.
- Regression: existing tmux suite green
  (`bash tests/test_tmux_persistent_scope.sh`, the bash path is untouched).

See **Step 9 (Post-Implementation)** of the task-workflow for cleanup, archival,
and merge.

## Risk

### Code-health risk: low
- Change is confined to the `new_session` branch of one function plus three
  module-private helpers in a single file; signature, callers, and the
  `new_window`/`split` branches are untouched, and a graceful systemd-run →
  setsid → plain ladder preserves today's behavior · severity: low · →
  mitigation: TBD
- Duplicates t943's `systemd-run` flags in a second language/place, so a future
  change to those flags must be mirrored; also environment-sensitive and only
  partially CI-testable (user manager often absent — same property t943 noted) ·
  severity: low · → mitigation: t952 (centralize tmux invocations behind a
  shared gateway) is already slated to absorb both copies

### Goal-achievement risk: low
- Approach mirrors the validated t943 implementation and the precheck precisely
  targets genuine server creation; this closes the explicitly-deferred t943 gap
  in full · severity: low · → mitigation: TBD

### Planned mitigations
- None. t952 (pre-existing, already created) will later centralize the duplicated
  systemd-run logic; it is a planned refactor, not a risk-mitigation follow-up
  spawned by this task.
