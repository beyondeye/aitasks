---
Task: t980_document_tmux_gateway_architecture.md
Worktree: (none — profile 'fast', current branch)
Branch: main (current)
Base branch: main
---

# Plan: Document tmux gateway architecture (t980)

## Context

The tmux interaction layer was refactored across **t952** (a single tmux command
gateway per language — the only sanctioned place a raw `tmux` process is spawned)
and **t953** (a dedicated `-L ait` socket isolating the ait backend from the
user's personal default tmux server). The design is articulated only in the
gateway source headers/docstrings and enforced by a lint test — there is **no
`aidocs/framework/` doc** that new tmux-touching code can be pointed at. CLAUDE.md
only references `tui_conventions.md` ("when spawning tmux panes/windows"), which
predates and does not describe the gateway. Without an on-demand reference, new
code risks drifting back to ad-hoc raw `tmux` calls (the ~45–50-call-site sprawl
t952 collapsed). This task adds a brief conventions doc, wires it into CLAUDE.md,
and reconciles existing docs that still describe the pre-gateway model.

## Deliverable 1 — new doc `aidocs/framework/tmux_gateway.md`

Brief, rule-oriented, current-state-only (per `documentation_conventions.md`).
Distill from the source headers — do **not** re-derive. Sections:

1. **The chokepoint rule** — one gateway per language is the only place a raw
   `tmux` process is spawned:
   - Python: `.aitask-scripts/lib/tmux_exec.py` — `TmuxClient` (`run` /
     `run_async` / `spawn` / `run_via_control` / `run_async_via_control` /
     `resize_pane` / `new_session_argv`) + module fns `tmux_socket_args`,
     `session_target`, `window_target`.
   - Shell: `.aitask-scripts/lib/tmux_exec.sh` — `ait_tmux` (function form),
     `ait_tmux_socket_args` (emitter for `exec`/compound `\;` sites),
     `ait_tmux_session_target` / `ait_tmux_window_target`, `ait_tmux_socket_name`,
     and `ait_tmux_legacy*` (migration-window probes of the user's default server).
2. **The three centralized policies** (were implicit/duplicated pre-t952):
   - **Socket selection** (t953): `AITASKS_TMUX_SOCKET` — unset → `-L ait`
     (dedicated socket); `default` → explicit opt-out to the user's server;
     set-but-empty → no flag (legacy escape hatch following `$TMUX`, used by the
     test isolation harness). Resolved **once** at client construction, never
     per-call (monitor hot path).
   - **Target formatting**: `=<session>` exact-match `-t` targets are
     **mandatory** via the helpers (tmux's default prefix match makes `aitasks`
     resolve to `aitasks_mob`). Cross-link `tui_conventions.md` for the
     multi-project "why"; this doc owns the "use the helper" mechanism.
   - **Exec strategy**: per-tick subprocess vs. persistent control-mode client
     (`run_via_control` — "control client when alive, subprocess fallback on
     `rc == -1`"), with the `(rc, stdout)` / `(-1, "")` contract.
3. **The enforcement guard**: `tests/test_no_raw_tmux.sh` freezes raw spawns to
   the two gateways + a documented per-entry allowlist (gateways, Layer-A
   backends like `monitor/tmux_control.py`, ambient `$TMUX` self-probes). State
   the boundary: it's a freeze, not an invitation to extend the allowlist.
4. **Writing new tmux code — checklist**: route through the gateway; never
   hand-format `-t` (use `session_target`/`window_target`); don't add to the
   allowlist; run `bash tests/test_no_raw_tmux.sh` before committing.

## Deliverable 2 — CLAUDE.md pointer

In the **TUI Development** section (CLAUDE.md:191–210), add a new on-demand
pointer after the `tui_conventions.md` block:

> **Read `aidocs/framework/tmux_gateway.md`** when writing or editing any code
> (shell or Python) that spawns or commands `tmux` — panes, windows, sessions,
> sockets, capture/send-keys — anywhere under `.aitask-scripts/`, not only TUIs.
> The two gateways (`lib/tmux_exec.py` / `lib/tmux_exec.sh`) are the only
> sanctioned raw-`tmux` call sites; `tests/test_no_raw_tmux.sh` enforces it.

Also tighten the existing `tui_conventions.md` pointer's trailing tmux clause
("or when spawning tmux panes / windows from framework code") to redirect to the
new doc, so the two pointers don't both claim the tmux-spawning trigger.

## Deliverable 3 — reconcile `aidocs/framework/python_tui_performance.md`

Descriptively stale: lines ~46 (bottleneck table), ~51, ~197 attribute the raw
`asyncio.create_subprocess_exec("tmux", …)` spawn to
`tmux_monitor.py::capture_all_async()`. Post-t952 that raw spawn lives in the
gateway (`TmuxClient.run_async` / `spawn` in `lib/tmux_exec.py`); `tmux_monitor.py`
imports `TmuxClient` and routes through `run_async_via_control`. **Fix only the
code-location attribution** — the performance conclusion (fork+exec dominates,
PyPy ~0%) is unchanged and stays. Add a short clause noting the spawn is now
gateway-routed. (Line ~169 already correctly describes the control-mode path.)

## Deliverable 4 — cross-link `aidocs/framework/tui_conventions.md`

The "Single tmux session per project" section (lines 212–233) already states the
exact-match `-t =<session>` rule with the multi-project rationale, and the
companion-pane + tmux-stress sections reference raw `tmux` verbs. Do **not**
duplicate. Add a one-line cross-link near the exact-match bullet (line ~228)
pointing to `tmux_gateway.md` for the mandatory `session_target`/
`ait_tmux_session_target` helpers, establishing: `tui_conventions.md` owns the
*why* (multi-project isolation); `tmux_gateway.md` owns the *mechanism* (the
gateway + helpers). Quick re-scan of `cross_repo_references.md`,
`monitor_idle_and_prompt_detection.md`, `sed_macos_issues.md` confirmed current
during scoping — no edits expected, but verify against the final doc.

## Files to modify

- **New:** `aidocs/framework/tmux_gateway.md`
- `CLAUDE.md` (TUI Development section, ~line 197)
- `aidocs/framework/python_tui_performance.md` (attribution fix, ~lines 46/51/197)
- `aidocs/framework/tui_conventions.md` (one cross-link, ~line 228)

No code, scripts, or skills change. No `.j2`/closure/golden regeneration needed
(no skill-surface change). Commit type: `documentation` (per task `issue_type`).

## Verification

- `grep -n "tmux_gateway.md" CLAUDE.md aidocs/framework/tui_conventions.md` →
  pointer + cross-link present.
- Spot-read `tmux_gateway.md` claims against source: `AIT_DEDICATED_SOCKET="ait"`
  in both `lib/tmux_exec.sh` and `lib/tmux_exec.py`; allowlist entries match
  `tests/test_no_raw_tmux.sh`; helper names exist (`grep -n` in both gateways).
- `bash tests/test_no_raw_tmux.sh` still passes (docs-only change — sanity that
  nothing references a renamed symbol).
- Confirm no remaining `aidocs/framework/` doc attributes a raw `tmux` spawn to
  `tmux_monitor.py`: `grep -rn "tmux_monitor.*tmux\|create_subprocess_exec.*tmux"
  aidocs/framework/`.

## Risk

- **Code-health risk: low.** Documentation-only; no code, script, skill, or
  config touched. The single behavioral-doc edit (`python_tui_performance.md`
  attribution) is corrective — it removes a stale claim, lowering drift risk. No
  blast radius beyond four markdown files.
- **Goal-achievement risk: low.** Scope is well-bounded and the source of truth
  (gateway docstrings) is unambiguous. The only judgment call is the doc-ownership
  split for the exact-match rule (gateway = mechanism, tui_conventions = why),
  resolved above via cross-links rather than duplication.

### Planned mitigations
None — both dimensions are low; no before/after mitigation tasks warranted.

## Post-implementation (Step 9)

Single parent task, current branch (no worktree/merge). After review + commit:
consolidate plan, then `./.aitask-scripts/aitask_archive.sh 980` and `./ait git
push`. No folded tasks, no linked issue/PR.
