---
Task: t952_centralize_tmux_invocations_shared_gateway.md
Worktree: (umbrella — implemented via children t952_1..t952_5)
Branch: (per-child)
Base branch: main
---

# t952 — Centralize tmux invocations behind a shared gateway (DECOMPOSITION PLAN)

## Context

tmux interaction is scattered across ~45–50 raw call sites with no single
chokepoint, spread over four parallel "hubs" plus inline stragglers — with
**no common substrate**. Because nothing owns the `tmux` spawn, three
cross-cutting policies are implicit and duplicated: **socket selection**
(nobody threads `-L`/`-S` — everyone assumes the default socket), **target
formatting** (`=session` exact-match is sometimes via a helper, sometimes
hardcoded), and **exec strategy** (per-tick `subprocess` vs. the persistent
control-mode client, currently tied to monitor).

This task introduces a single tmux command gateway **per language** that
becomes the only place a raw `tmux` process is spawned, and migrates the
existing call sites through it **without behavior change**. It is the
foundational substrate beneath t822_3's `monitor_core` extraction and the
precondition that turns a future dedicated-socket move into a one-knob change
instead of ~50 edits.

Because this is wide, cross-cutting, two-language, and effort:high, the task
body itself mandates staging ("gateway first, migrate incrementally"). Per
user decision (2026-06-10) it is **decomposed into 5 child tasks**, with the
persistent control-mode client absorption **deferred to stage 3** (not done in
the stage-1 gateway core).

## Key findings from exploration (ground truth for the children)

- **Target-format helpers already exist** but are "available, not mandatory":
  `tmux_session_target()` → `={session}`, `tmux_window_target()` → `={session}:{window}`
  (`.aitask-scripts/lib/agent_launch_utils.py:29-48`). The gateway makes them mandatory.
- **Monitor already has the exec-strategy dispatcher.** `TmuxMonitor.tmux_run()`
  (`monitor/tmux_monitor.py:266`) and `_tmux_async()` (`:255`) try `self._backend`
  (`TmuxControlBackend`) then fall back to module-level `_run_tmux_subprocess()` /
  `_run_tmux_async()` (`:103-152`) — the only raw spawn primitives in `monitor/`.
  All ~14 monitor runtime sites already route through these.
- **Persistence argv builder already exists** in both languages:
  Python `_new_session_tmux_argv` / `_persistent_new_session_prefix`
  (`agent_launch_utils.py:557-621`) mirrors shell
  `ait_tmux_new_session_persistent` (`lib/terminal_compat.sh:158-179`) — these
  are to be **moved/owned** by the gateway, not built from scratch.
- **No socket flag anywhere.** Threading it now, defaulting to none, is the
  whole point.
- **Test isolation harness** `tests/lib/tmux_isolation.sh` now exposes
  `require_isolated_tmux` (redirects `TMUX_TMPDIR` to a private per-user dir);
  it replaced the old `require_no_tmux` exit-2 refusal (t936). New tmux tests
  must source it. The gateway's default of **no `-L`/`-S` flag** must be
  preserved so `TMUX_TMPDIR` redirection keeps isolating tests.
- **Scaffold coupling:** `tests/lib/test_scaffold.sh::setup_fake_aitask_repo()`
  copies `lib/*.sh` into fake repos (terminal_compat.sh at line 17). A new
  `lib/tmux_exec.sh` added to `./ait`'s source chain MUST get a matching `cp`
  line **in the same commit** or every scaffolded test breaks.
- **Existing behavior-preservation oracles:** `tests/test_tmux_run_parity.sh`
  (control-client vs subprocess identical output), `test_tmux_control.sh`,
  `test_tmux_control_resilience.sh`, `test_tmux_exact_session_targeting.sh`,
  `test_tmux_persistent_scope.sh`, `test_launch_in_tmux_pane_pid.py`.

## The one design decision binding all children: the socket knob

The socket flag is sourced from a **process-global env var
`AITASKS_TMUX_SOCKET`** (empty → no flag), read **once at client
construction** (never per-call — the monitor fallback is a perf hot path).
Rationale: socket is a *server*-level concept, not project-level; an env var
is the one source Python (child 1/2/3) and bash (child 4) can both read
trivially, so all three clients + the shell mirror converge on the same value.
This is rejected-alternative-worthy: do **not** source it from
`load_tmux_defaults` / `project_config.yaml` (project-scoped, can't be shared
with bash, can't be read-once in the hot path).

---

## Decomposition: 5 children

Dependency graph: **1 → {2, 3, 4 in parallel} → 5**. Children 2/3/4 only depend
on child 1's *contract* (the `AITASKS_TMUX_SOCKET` env var name + "default
empty" + typed-method signatures), so once child 1 lands they can proceed
concurrently. Child 4 (shell) shares no files with 2/3. **Child 3 must be
rebased-after / coordinated-with t822_3** (both edit `monitor/`). Child 5 is
the only non-spawn-routing child and is independently shippable.

### Child 1 — Python gateway core (`lib/tmux_exec.py`)
- **Scope:** New module `TmuxClient`, pure addition + unit tests. Owns: sync
  spawn (`subprocess.run` capture), async spawn
  (`asyncio.create_subprocess_exec`), fire-and-forget (`subprocess.Popen`); the
  single `_socket_args()` source (reads `AITASKS_TMUX_SOCKET` once at
  construction); mandatory target formatting (absorb/re-export
  `tmux_session_target`/`tmux_window_target`); and the new-session
  persistence-argv builder (`new_session_argv` + `_persistent_new_session_prefix`,
  including its server-existence probe which must use the same `_socket_args()`).
  **No control-mode, no call-site migration.**
- **Surface:** `run(args, timeout)->(rc,str)` sync, `run_async(...)->(rc,str)`,
  `spawn(args)->Popen`. Preserve the exact `(-1, "")`-on-failure contract of
  the current `_run_tmux_subprocess`/`_run_tmux_async` verbatim.
- **Key files:** `.aitask-scripts/lib/tmux_exec.py` (new); read-only refs
  `agent_launch_utils.py:29-48,557-621`, `monitor/tmux_monitor.py:103-152`.
- **Risks:** persistence-probe split-brain (existence check must probe the same
  socket as the create); keep the systemd-run/setsid/plain degradation ladder
  byte-for-byte.
- **Verification:** new `tests/test_tmux_exec.py` — socket-args prepend with
  knob set/unset, target-format methods, persistence ladder (monkeypatch
  `shutil.which`), `(-1,"")` contract; one integration spawn under
  `require_isolated_tmux`.

### Child 2 — Migrate simple Python subprocess sites
- **Scope:** Re-point all **non-registry** sync sites to `TmuxClient`:
  `agent_launch_utils.py` (`get_tmux_sessions`, `get_tmux_windows`,
  `switch_to_pane_anywhere`, `_query_first_pane_pid`, `launch_in_tmux`,
  `maybe_spawn_minimonitor`, `launch_or_focus_codebrowser`), `lib/tui_switcher.py`
  (~7 sites), `agentcrew/agentcrew_runner.py` (pipe-pane ~447). Mechanical
  substitution; every `-t` session/window target through the mandatory helpers.
- **Hard boundary:** do **NOT** touch the two registry readers
  (`_read_registry_entry` show-environment; the `list-sessions`/`list-panes -s`
  walk in `discover_aitasks_sessions`) — those belong to child 5; touching them
  here collides.
- **Risks:** pane-scoped verbs (`set-option -p`/`set-hook -p`,
  `tui_switcher._launch_git_with_companion`) take pane ids, not session targets —
  pass through untouched; `agentcrew` pipe-pane argv order is sensitive.
- **Verification:** `test_launch_in_tmux_pane_pid.py` +
  `test_tmux_exact_session_targeting.sh` stay green; pure-routing, no new
  behavior tests.

### Child 3 — Absorb control-mode + re-point monitor (FUSED, coordinate w/ t822_3)
- **Scope:** Move `TmuxControlBackend`/`TmuxControlClient` ownership under the
  gateway so control-mode is reusable beyond monitor; re-point
  `TmuxMonitor.tmux_run`/`_tmux_async` to delegate to the gateway's
  exec-strategy dispatcher (kept as thin shims so all ~14 monitor sites are
  untouched); thread `_socket_args()` into the `tmux -C attach` spawn
  (`tmux_control.py:98-99`).
- **Why fused (not a 6th child):** `tmux_run`/`_tmux_async` *are* the
  dispatcher; once the backend moves into the gateway the "try backend else
  subprocess" logic moves with it and re-pointing the monitor is a 4-line
  delegation — inseparable.
- **Key files:** `monitor/tmux_control.py`, `monitor/tmux_monitor.py`,
  `lib/tmux_exec.py`.
- **Risks:** perf hot path — cache socket args at construction, no per-call
  config reads; keep the backend **session-bound** (don't gold-plate into a
  server-wide client); preserve the fallback-on-`-1` logic exactly.
  **t822_3 collision:** both edit `monitor/` — sequence after t822_3 or
  coordinate the rebase.
- **Verification:** `test_tmux_run_parity.sh` is the keystone oracle
  (backend-on vs backend-off identical); `test_tmux_control.sh`,
  `test_tmux_control_resilience.sh`; assert attach argv includes socket args
  when the knob is set.

### Child 4 — Shell gateway `lib/tmux_exec.sh` + migrate shell sites (parallel)
- **Scope:** New `lib/tmux_exec.sh` mirroring socket flag + exact-match
  targeting: a function `ait_tmux <args...>` prepending `tmux` +
  `AITASKS_TMUX_SOCKET` args, plus `ait_tmux_session_target` /
  `ait_tmux_window_target`, and a socket-args **emitter** form for `exec`/
  compound sites. Migrate `tmux_bootstrap.sh`, `terminal_compat.sh` new-session
  rungs, `aitask_ide.sh`, `aitask_minimonitor.sh`.
- **Constraints:** `#!/usr/bin/env bash`, `set -euo pipefail`, `die/warn/info`
  from terminal_compat.sh, `_AIT_TMUX_EXEC_LOADED` double-source guard. If it
  joins `./ait`'s source chain, add the matching `cp` to
  `test_scaffold.sh::setup_fake_aitask_repo()` **same commit**.
- **Decisions/risks:** `aitask_companion_cleanup.sh` is a **pane-died hook in a
  minimal env** that inherits the server socket via `$TMUX` — **leave it on raw
  tmux as a documented exception** (don't route it; whitelist it in child 5's
  guard). `aitask_ide.sh` uses `exec tmux attach ... \; select-window ...` —
  the wrapper must not mangle `\;`; use the socket-args-emitter form there, not
  the function form (a function can't be `exec`'d).
- **Verification (highest-blast-radius child):** `shellcheck` hard gate on all
  touched files; `test_tmux_exact_session_targeting.sh`,
  `test_tmux_persistent_scope.sh`, `test_tmux_control.sh`; full shell suite
  under `require_isolated_tmux`.

### Child 5 — Collapse duplicate registry / session-discovery (separable, last)
- **Scope:** Dedupe the Python (`_read_registry_index` + `discover_aitasks_sessions`)
  and bash (`aitask_project_resolve.sh::index_lookup_path` awk-parser,
  `aitask_projects.sh::live_tmux_project_names`) readers into one authority.
  **Narrower than it sounds:** the live-scan path is *already* single-authority
  (bash already shells out to Python `discover_aitasks_sessions`); only the
  `projects.yaml` *file reader* is duplicated.
- **Flagged separable/deferrable:** the only non-spawn-routing child (a
  data-layer dedup on registry-authority axis, scope item 4); highest
  behavior-change risk (awk vs Python edge cases). Can be split into a
  standalone follow-up without blocking 1–4 if a fast clean landing is wanted.
- **Design:** single authority = Python (already the live-scan authority and
  the more complete reader); bash readers become thin shell-outs to a Python
  `--list-registry`/`--resolve <name>` CLI, deleting the awk parser; honor
  `AITASKS_PROJECTS_INDEX` in one place.
- **Risks:** quoting/STALE-detection/override parity; bash hot paths now pay
  Python startup (measure — may justify keeping a fast bash reader); the
  `RESOLVED:`/`STALE:` sentinel contract must stay byte-identical.
- **Verification:** golden-corpus `projects.yaml` fixture (quoted/unquoted/
  stale/comment/override) asserting post-change reader matches the pre-change
  bash+Python baseline byte-for-byte.

---

## Blast-radius guards (the user scrutinizes "what if someone edits this unaware")

1. **Anti-regression lint test** (`tests/test_no_raw_tmux.sh`) — the centerpiece.
   Greps the tree for raw tmux spawns (`subprocess.run(["tmux"`,
   `Popen(["tmux"`, `create_subprocess_exec("tmux"`, shell `^\s*tmux `/`$(tmux `)
   and **fails** unless the file is on an explicit allowlist. Allowlist = the
   documented exceptions: `lib/tmux_exec.py`, `lib/tmux_exec.sh`,
   `monitor/tmux_monitor.py` raw helpers, `monitor/tmux_control.py` attach,
   `aitask_companion_cleanup.sh` (minimal-env hook),
   `monitor_app.py`/`minimonitor_app.py` `_detect_tmux_session` pre-init probes.
   **Land this in the final child** (allowlist only complete once both gateways
   exist) — landing early would force premature allowlisting of unmigrated sites.
2. **Socket-knob single-source assertion** — with `AITASKS_TMUX_SOCKET` set, all
   three Python spawn paths + the control attach + the shell wrapper emit the
   flag, proving the "one knob, future 1-line change" property.
3. **t822_3 coordination** — child 3 marked rebased-after/coordinated; children
   1/2/4 are independent of `monitor/`.
4. **Scaffold coupling checklist item** in child 4.

## Rejected alternatives
- Single-session / <5 children — rejected (user decision; language split +
  monitor perf-sensitivity are natural seams).
- Monitor re-point as a 6th child — rejected (4-line delegation inseparable
  from control-mode absorption).
- Persistence argv builder in child 2 — rejected (needs gateway-internal socket
  args + server-existence probe; belongs in child 1).
- Socket flag from `load_tmux_defaults`/`project_config.yaml` — rejected
  (server-level not project-level; unshareable with bash; can't read-once in
  hot path). Use `AITASKS_TMUX_SOCKET` env var.
- Migrating registry query-sites in child 2 — rejected (collides with child 5).
- Routing the companion-cleanup hook through the shell gateway — rejected
  (minimal hook env; inherits server socket via `$TMUX`; keep raw + whitelisted).

## Post-approval execution (these are WRITES — run after this plan is approved)

On approval, exiting plan mode:
1. Create children t952_1..t952_5 via `aitask_create.sh --batch` (mode child),
   each with full Context / Key Files / Reference Files / Implementation Plan /
   Verification sections per the per-child detail above. Wire `depends:` so
   2/3/4 depend on 1 and 5 depends on 1; note child 3's t822_3 coordination in
   its body.
2. Write child plans to `aiplans/p952/p952_<n>_<name>.md`; commit them.
3. Revert parent t952 to `Ready`, clear `assigned_to`, release the parent lock.
4. Offer the aggregate manual-verification sibling (TUI/live-tmux behavior the
   gateways touch — monitor refresh, `j` switcher teleport, companion despawn,
   session spawn persistence).
5. Child checkpoint: start first child (`/aitask-pick 952_1`) or stop here.

Each child re-verifies its anchors and gets its own Risk evaluation at pick
time. See **Step 9 (Post-Implementation)** of the task-workflow for archival
once children land.
