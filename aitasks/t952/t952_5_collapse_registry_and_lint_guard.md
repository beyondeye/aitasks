---
priority: medium
effort: medium
depends: [t952_1, t952_2, t952_3, t952_4]
issue_type: refactor
status: Implementing
labels: [tmux, ait_bridge]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-10 12:49
updated_at: 2026-06-10 21:56
---

## Context

Stage 5 (capstone) of the t952 tmux-centralization decomposition (see
`aiplans/p952_*`). Two jobs: (a) collapse the duplicate `projects.yaml` registry
readers to one authority; (b) land the **anti-regression lint guard** that keeps
new raw `tmux` calls from creeping back in. Depends on t952_1..t952_4 because the
guard's allowlist is only complete once both gateways exist and all migrations
have landed.

**Separability note:** job (a) — registry collapse — is the only part of t952
that is NOT pure tmux-spawn routing (it is a data-layer dedup on the
registry-authority axis, scope item 4) and carries the highest behavior-change
risk. If a fast clean landing of the routing work is wanted, (a) can be split
into its own standalone follow-up task without blocking the guard. Decide at
plan time.

**Pick-time decision (2026-06-10):** job (a) was **split out to standalone
follow-up `t970`** (`aitasks/t970_collapse_projects_yaml_registry_reader.md`) —
a parity gap was found (Python authority returns 3 fields, bash emits 4 feeding
write ops). This task now covers only: (b1) migrate the Layer-A
`discover_aitasks_sessions` walk onto the gateway (t952_2's HARD BOUNDARY), and
(b2) the anti-regression lint guard. See `aiplans/p952/p952_5_*` for the
verified plan and the guard's Layer-A/B allowlist rationale.

## Key files to modify
### Job (a) — registry collapse
- `.aitask-scripts/lib/agent_launch_utils.py:266-368` — `_read_registry_index`,
  `_read_default_session`, `discover_aitasks_sessions` (the Python authority).
- `.aitask-scripts/aitask_project_resolve.sh:121-205` — `index_lookup_path`
  (awk parser to delete; becomes a thin shell-out).
- `.aitask-scripts/aitask_projects.sh:157-292` — `live_tmux_project_names` /
  registry-list readers (the bash duplicate).
### Job (b) — guard
- **NEW** `tests/test_no_raw_tmux.sh`.

## Reference facts
- Registry file: `~/.config/aitasks/projects.yaml` (override
  `AITASKS_PROJECTS_INDEX`). Schema: YAML list of `{name, path, git_remote,
  last_opened}`.
- The **live-scan** path is ALREADY single-authority — bash already shells out
  to Python `discover_aitasks_sessions` (`aitask_project_resolve.sh` heredoc
  ~138-143; `aitask_projects.sh` ~264). Only the **projects.yaml file reader**
  is genuinely duplicated. Scope is narrower than "registry/session-discovery".

## Implementation plan
### (a) Registry collapse
1. Make Python the single authority (it already is for live scan and has the
   more complete reader with STALE annotation). Expose a CLI surface
   (`--list-registry` / `--resolve <name>`).
2. Replace the bash awk parser with thin shell-outs to that CLI; honor
   `AITASKS_PROJECTS_INDEX` in the one Python place.
3. Keep the `RESOLVED:` / `STALE:` sentinel contract consumed by callers
   byte-identical.
### (b) Anti-regression guard
1. `tests/test_no_raw_tmux.sh` greps the tree for raw tmux spawns
   (`subprocess.run(["tmux"`, `Popen(["tmux"`, `create_subprocess_exec("tmux"`,
   shell `^\s*tmux ` / `$(tmux `) and FAILS unless the file is on an explicit
   allowlist.
2. Allowlist = the documented exceptions: `lib/tmux_exec.py`, `lib/tmux_exec.sh`,
   `monitor/tmux_monitor.py` raw fallback helpers, `monitor/tmux_control.py`
   attach, `aitask_companion_cleanup.sh` (minimal-env hook),
   `monitor_app.py` / `minimonitor_app.py` `_detect_tmux_session` pre-init probes.

## Risks
- awk-vs-Python parser parity: quoting, STALE detection, `AITASKS_PROJECTS_INDEX`
  override precedence — real behavior-change risk; golden-corpus test it.
- bash hot paths (`index_lookup_path`) now pay Python startup — measure; may
  justify keeping a fast bash reader. Do not regress resolve latency silently.

## Verification
- **Golden-corpus** `projects.yaml` fixture (quoted / unquoted / stale / comment
  / `AITASKS_PROJECTS_INDEX`-override cases) asserting the post-change unified
  reader matches the pre-change bash+Python baseline byte-for-byte.
- Run `tests/test_no_raw_tmux.sh` and confirm it passes with the complete
  allowlist (and fails when a raw `tmux` is deliberately introduced in a
  non-allowlisted file).
- Run the full tmux suite under `require_isolated_tmux`.
- This child gets its own Risk evaluation at pick time.
