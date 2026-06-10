---
Task: t952_5_collapse_registry_and_lint_guard.md
Parent Task: aitasks/t952_centralize_tmux_invocations_shared_gateway.md
Sibling Tasks: aitasks/t952/t952_1_*.md, aitasks/t952/t952_2_*.md, aitasks/t952/t952_3_*.md, aitasks/t952/t952_4_*.md
Worktree: aiwork/t952_5_collapse_registry_and_lint_guard
Branch: aitask/t952_5_collapse_registry_and_lint_guard
Base branch: main
---

# t952_5 — Collapse registry + anti-regression lint guard (capstone)

Stage 5 — see parent plan `aiplans/p952_centralize_tmux_invocations_shared_gateway.md`.
Depends on **t952_1..t952_4** (the guard's allowlist needs both gateways +
all migrations landed).

**Separability:** job (a) registry collapse is the only non-routing part of
t952 and the highest behavior-change risk — if a fast clean landing of the
routing work is wanted, split (a) into its own follow-up and land (b) here
alone. Decide at pick time.

## Job (a) — Registry collapse
Only the **`projects.yaml` file reader** is duplicated; the live-scan path is
already single-authority Python (bash shells out to `discover_aitasks_sessions`).

1. Make Python the single authority — expose a CLI (`--list-registry` /
   `--resolve <name>`) on/near `agent_launch_utils.py` (`_read_registry_index`,
   `_read_default_session`, `discover_aitasks_sessions`, lines ~266-368).
2. Replace the bash awk parser in `aitask_project_resolve.sh:121-205`
   (`index_lookup_path`) and the `aitask_projects.sh:157-292` registry readers
   with thin shell-outs to that CLI. Honor `AITASKS_PROJECTS_INDEX` in the one
   Python place.
3. Keep the `RESOLVED:` / `STALE:` sentinel contract byte-identical.

**Risks:** awk-vs-Python parity (quoting, STALE detection, override
precedence); bash hot paths now pay Python startup — measure resolve latency,
may justify keeping a fast bash reader.

**Verification:** golden-corpus `projects.yaml` fixture (quoted / unquoted /
stale / comment / `AITASKS_PROJECTS_INDEX`-override) asserting the unified
reader matches the pre-change bash+Python baseline byte-for-byte.

## Job (b) — Anti-regression guard
1. **New `tests/test_no_raw_tmux.sh`**: grep the tree for raw tmux spawns
   (`subprocess.run(["tmux"`, `Popen(["tmux"`, `create_subprocess_exec("tmux"`,
   shell `^\s*tmux ` / `$(tmux `) and FAIL unless the file is on an explicit
   allowlist.
2. **Allowlist** (the documented exceptions): `lib/tmux_exec.py`,
   `lib/tmux_exec.sh`, `monitor/tmux_monitor.py` raw fallback helpers,
   `monitor/tmux_control.py` attach, `aitask_companion_cleanup.sh`,
   `monitor_app.py` / `minimonitor_app.py` `_detect_tmux_session` probes.

**Verification:** the guard passes with the complete allowlist, and fails when a
raw `tmux` is deliberately introduced in a non-allowlisted file. Run the full
tmux suite under `require_isolated_tmux`.

See **Step 9 (Post-Implementation)** for archival.
