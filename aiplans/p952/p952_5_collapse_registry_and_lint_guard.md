---
Task: t952_5_collapse_registry_and_lint_guard.md
Parent Task: aitasks/t952_centralize_tmux_invocations_shared_gateway.md
Sibling Tasks: aitasks/t952/t952_1_*.md, aitasks/t952/t952_2_*.md, aitasks/t952/t952_3_*.md, aitasks/t952/t952_4_*.md
Archived Sibling Plans: aiplans/archived/p952/p952_*_*.md
Worktree: aiwork/t952_5_collapse_registry_and_lint_guard
Branch: aitask/t952_5_collapse_registry_and_lint_guard
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-11 08:19
---

# t952_5 — Anti-regression tmux guard + Layer-A discovery-walk migration (capstone)

Stage 5 (capstone) of the t952 tmux-centralization decomposition. Depends on
t952_1..t952_4 (the guard's allowlist is only meaningful once both gateways exist
and the routing migrations have landed).

## Pick-time scope decisions (2026-06-10)

Verified against the current tree at pick time; two decisions reshaped the plan:

1. **Job (a) — `projects.yaml` registry-reader collapse — SPLIT OUT to `t970`.**
   It is the only **non-routing** part of t952 (data-layer dedup, scope item 4)
   and the highest behavior-change risk, and a parity gap was found (below). It
   does not block the guard, so it was peeled into standalone follow-up
   **t970** (`aitasks/t970_collapse_projects_yaml_registry_reader.md`). **This
   task no longer does job (a).**

   > Parity gap that drove the split: bash `list_registry_entries`
   > (`aitask_projects.sh:157-206`) emits **4 fields**
   > (`name|path|git_remote|last_opened`) and feeds the registry **write** ops,
   > but Python `_read_registry_index` (`agent_launch_utils.py:261-320`) returns
   > only **(name, path, status)**. A naive shell-out would silently drop
   > `git_remote`/`last_opened` on every mutation. Resolved in t970, not here.

2. **Guard surface — Option 2 (refined), keyed to the `wish`/SSH Layer A/B split**
   (`aidocs/applink/wish_ssh_evaluation.md`):
   - **Layer A** (tmux as agent/process *backend*) must reach a single
     well-known backend handle and honor the dedicated socket (the t952 raison
     d'être). → such calls route through the gateway.
   - **Layer B** (tmux as user-facing *window manager*) disappears when remote;
     navigation moves in-app. Ambient `$TMUX` self-probes belong to the user's
     **default** server, not the aitasks backend socket — routing them through
     the dedicated-socket gateway would query the *wrong* server. → allowlist.

   Concretely: **migrate** the one remaining Layer-A backend holdout
   (`discover_aitasks_sessions`); **allowlist** the ambient `_detect_*` probes
   and the existing pre-init / navigation raw calls, as a *documented* contract.

## Job (b1) — Migrate the Layer-A discovery walk onto the gateway

`agent_launch_utils.discover_aitasks_sessions` is the backend session
enumerator. t952_2 migrated every other Python call site but **left this walk
raw on purpose** ("HARD BOUNDARY for t952_5" — see
`aiplans/archived/p952/p952_2_migrate_python_subprocess_sites.md`). It is the
single Layer-A call a served backend depends on, so it must honor the socket.

- **File:** `.aitask-scripts/lib/agent_launch_utils.py`, inside
  `discover_aitasks_sessions` (~lines 393-411).
- **Change (mechanical, behavior-preserving — mirrors the existing pattern at
  `:181`/`:189`):**
  - `subprocess.run(["tmux", "list-sessions", "-F", "#{session_name}"], …)` →
    `rc, out = _TMUX.run(["list-sessions", "-F", "#{session_name}"])`, then
    `sessions = [s for s in out.splitlines() if s] if rc == 0 else []`.
  - `subprocess.run(["tmux", "list-panes", "-s", "-t", tmux_session_target(session), "-F", "#{pane_current_path}"], …)`
    → `rc, out = _TMUX.run(["list-panes", "-s", "-t", tmux_session_target(session), "-F", "#{pane_current_path}"])`,
    then iterate `out.splitlines()` when `rc == 0`.
  - The gateway folds `TimeoutExpired/FileNotFoundError/OSError` into `(-1, "")`,
    so the wrapping `try/except` collapses into the `rc != 0` branch (drop the
    now-dead `except` blocks). `_TMUX` is already imported and constructed at
    module scope (`:24`, `:31`) — no new wiring.
- **Why safe today:** `AITASKS_TMUX_SOCKET` is unset, so the gateway emits no
  `-L` flag — the spawned argv is byte-identical to the raw call. The only
  change is the chokepoint, which the socket-move follow-up will flip in one place.
- **Note:** the migrated call passes `["list-sessions", …]` (no `"tmux"` argv
  literal), so it does **not** trip the guard's grep — confirming the migration
  also clears it from the raw set.

## Job (b2) — Anti-regression lint guard

**New file: `tests/test_no_raw_tmux.sh`.** Greps the tree for raw tmux spawns and
**FAILS** unless every hit's file is on an explicit allowlist. This freezes the
current surface and blocks *new* raw calls from creeping back in (it is a
freeze, not a migration — existing sanctioned sites are allowlisted).

**Detection patterns (raw `tmux` as argv[0] / command):**
- Python: a `"tmux"` / `'tmux'` element as the first item of an argv list passed
  to subprocess —
  `subprocess.(run|Popen|call|check_output|check_call)(\s*\[\s*["']tmux["']`,
  `create_subprocess_exec(\s*["']tmux`, and the list-literal form
  `\[\s*["']tmux["']\s*,` (catches argv vars built before the call).
- Shell: a command-position `tmux` —
  `(^|[^_[:alnum:]"'])tmux[[:space:]]+[a-z-]` and `\$\(\s*tmux[[:space:]]`,
  excluding comments (`#`) and the `ait_tmux*` helper names.
- Restrict the scan to `.aitask-scripts/` `*.py`/`*.sh` plus `tests/` helpers.

**Allowlist — a documented contract (not just a path list).** Each entry carries
a one-line reason in the script so the rationale is visible at the failure site:

| File | Layer | Why sanctioned |
|------|-------|----------------|
| `lib/tmux_exec.py` | gateway | THE Python chokepoint — owns `["tmux", *socket_args, …]` |
| `lib/tmux_exec.sh` | gateway | THE shell chokepoint — `command tmux` + persistent rungs |
| `monitor/tmux_control.py` | A | control-mode `tmux -C attach` client |
| `monitor/tmux_monitor.py` | A | raw per-tick fallback helpers (control-mode primary) |
| `aitask_companion_cleanup.sh` | A | minimal-env cleanup hook, raw by design (t952_4 note) |
| `monitor/monitor_app.py` | B / ambient + A | `_detect_tmux_session`/`_detect_tmux_window` ambient probes (permanent); `rename-window`/`rename-session`/`has-session` are Layer-A pre-init, **deferred-migration** (flag for the socket-move task) |
| `monitor/minimonitor_app.py` | B / ambient | `_detect_tmux_session` probe + `display-message -t own_pane` self-query |
| `codebrowser/codebrowser_app.py` | B / ambient + A | `_detect_tmux_session`/`_detect_tmux_window` probes (permanent); `show-environment`/`set-environment` Layer-A, **deferred-migration** |
| `board/aitask_board.py` | B / ambient + B-nav | `_detect_tmux_session` probe (permanent); `select-window` is Layer-B navigation (local-only, does not port remote) |
| `stats/stats_app.py` | B / ambient | `_detect_tmux_session` probe (`display-message -p #{session_name}`) |

Mark the "deferred-migration" Layer-A rows with an inline `# TODO(socket-move):`
comment in the allowlist so the future dedicated-socket task has a worklist —
but they are sanctioned for **this** guard (migrating them is out of scope here;
the guard's purpose is to freeze, and they are behavior-touching).

**Allowlist mechanics:** keep the allowlist as a bash array of repo-relative
paths; a hit whose file is in the array is skipped, any other hit prints
`RAW TMUX: <file>:<line>` and sets a failure flag; exit non-zero if any
un-allowlisted hit remains. Print a clear PASS/FAIL summary (match the
`assert_*`/PASS-FAIL style of the existing `tests/*.sh`).

## Verification

- `bash tests/test_no_raw_tmux.sh` **passes** against the post-migration tree
  (discovery walk migrated; all remaining raw sites allowlisted).
- **Negative test:** temporarily introduce `subprocess.run(["tmux", "kill-server"])`
  in a non-allowlisted file (e.g. `aitask_create.sh`) and confirm the guard
  **fails** and names the file:line; revert.
- `shellcheck tests/test_no_raw_tmux.sh` clean.
- Re-run the tmux suite under `require_isolated_tmux` (the migrated
  `discover_aitasks_sessions` is exercised by the monitor/session-discovery
  tests) — confirm no regression. Set `AIT_NO_SYSTEMD_RUN=1` for the live
  integration tests (pre-existing condition documented in t952_1/t952_2).

## Risk

### Code-health risk: low
- Discovery-walk migration is a 2-call mechanical swap onto an already-imported
  gateway, byte-identical with the socket unset · severity: low · → mitigation: covered by the isolated tmux suite re-run
- The guard is additive (a new test file); it touches no runtime path · severity: low · → mitigation: none needed
- Allowlist drift risk: a future genuinely-bad raw call lands in an
  already-allowlisted file and is masked · severity: low · → mitigation: allowlist is per-file (coarse) by design; the per-row reasons + `TODO(socket-move)` markers keep it auditable

### Goal-achievement risk: low
- Guard pattern could miss an exotic raw-spawn form (e.g. `os.execvp`, a
  shell wrapper) and give false confidence · severity: medium · → mitigation: the negative test exercises the common forms; document the patterns' scope in the script header
- Splitting job (a) to t970 means the "single registry authority" goal of the
  parent (scope item 4) is deferred, not delivered here · severity: low · → mitigation: explicitly tracked in t970; intentional per pick-time decision

See **Step 9 (Post-Implementation)** for archival.

## Final Implementation Notes

- **Actual work done:**
  - **Job (b1) — Layer-A migration.** Routed `agent_launch_utils.py`'s
    remaining raw tmux calls onto the module-level `_TMUX` gateway:
    `discover_aitasks_sessions` (`list-sessions` + per-session `list-panes`) **and**
    `_read_registry_entry` (`show-environment -g`). Both were the t952_2
    "HARD BOUNDARY" holdouts. The `subprocess.run([...]) + try/except
    (TimeoutExpired/FileNotFoundError/OSError)` shape collapses into the gateway's
    `rc != 0` branch (the gateway folds spawn errors into `(-1, "")`).
  - **Job (b2) — guard.** New `tests/test_no_raw_tmux.sh`: scans `.aitask-scripts/`
    `*.py`/`*.sh`, fails on any raw tmux spawn outside a documented allowlist
    (per-entry reason + Layer-A/B classification + `TODO(socket-move)` markers).
    Self-tests: rogue py/sh flagged, allowlisted file not flagged,
    comment/prose/`ait_tmux` not flagged.
  - **Doc.** Added "The backend substrate: a single tmux gateway" to
    `aidocs/applink/wish_ssh_evaluation.md` — gateway as socket-policy chokepoint,
    the enforced Layer-A/B split, and the guard, all motivated by the served
    (`wish`/`applink`) deployment direction.
- **Deviations from plan:**
  - The plan named only `discover_aitasks_sessions` for the Layer-A migration; the
    guard surfaced a **second** HARD-BOUNDARY raw call (`_read_registry_entry`'s
    `show-environment`) — migrated it too (same rationale). This is exactly the
    drift the guard exists to catch, found on first run.
  - Guard detection patterns were tightened twice after first-run false positives:
    Python now requires a comma after `["tmux"` (excludes dict-subscripts like
    `settings_app.py`'s `data["tmux"]`); shell anchors `tmux` to command position
    (excludes in-string prose like `tmux_bootstrap.sh`'s `echo "… tmux
    new-session failed"`). Documented as the guard's known scope in its header.
  - **Job (a) (registry-file-reader collapse) was split out to standalone `t970`**
    at pick time (user decision) — parity gap: Python `_read_registry_index`
    returns 3 fields, bash `list_registry_entries` emits 4 feeding write ops. Not
    implemented here.
- **Issues encountered:** Live integration tests need `AIT_NO_SYSTEMD_RUN=1`
  (pre-existing `systemd-run --user` / `TMUX_TMPDIR` condition documented in
  t952_1/t952_2; not a regression). With it set, all suites pass.
- **Key decisions:** The guard is a **freeze, not a migration** — existing
  sanctioned raw sites (gateway internals, control-mode attach, ambient `$TMUX`
  self-probes, local-only Layer-B navigation) are allowlisted with reasons rather
  than rewritten. The `ait_tmux` shell helper is skipped for free (its `tmux` is
  preceded by `_`, not a command-position lead-in). Migrated `_TMUX.run([...])`
  calls carry no `"tmux"` argv literal, so they are invisible to the guard by
  construction.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - **t952_6 (manual verification):** the gateway routing is now complete for the
    Python side; a live check should confirm `ait monitor` / session discovery
    still enumerate sessions correctly (the migrated `discover_aitasks_sessions`).
  - **t970 (registry collapse):** when it lands and the bash awk readers shell out
    to a Python CLI, re-run `tests/test_no_raw_tmux.sh` (unaffected — registry
    readers are not tmux spawns) and ensure no new raw tmux is introduced.
  - **Future dedicated-socket task:** the allowlist rows tagged `TODO(socket-move)`
    (`monitor_app.py` rename/has-session, `codebrowser_app.py` show/set-environment)
    are the Layer-A worklist to route through the gateway when the socket flag goes
    live. Ambient `_detect_*` probes are intentionally NOT on that list.
