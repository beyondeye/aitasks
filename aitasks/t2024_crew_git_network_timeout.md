---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [git, bash_scripts, robustness, syncer]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1599
followup_kind: risk_mitigation
created_at: 2026-10-16 00:29
updated_at: 2026-10-16 00:32
---

## Origin

Risk-mitigation ("after") follow-up for t2016, created at Step 8d after implementation landed.

## Risk addressed

code-health bullet 1 (crew writes now make real network round-trips with no time limit; brainstorm _run_addwork has no subprocess timeout)

- Crew writes now make real network round-trips: a pull plus a push in addwork/setmode, and a push in init and in every runner and status commit. Before, they failed instantly with no network access. `brainstorm_crew._run_addwork` runs `ait crew addwork` without a subprocess timeout, so an origin that is unreachable but routable (TCP timeout rather than DNS failure) can stall brainstorm agent registration and init. Users who set `push.autoSetupRemote` already have this behavior. · severity: medium · → mitigation: crew_git_network_timeout

## Goal

Time-limit the crew git network operations so an unreachable-but-routable origin cannot stall crew init or agent registration until the TCP timeout:

- Shell: `crew_push` in `.aitask-scripts/lib/agentcrew_utils.sh` (used by `aitask_crew_init.sh`, `aitask_crew_addwork.sh`, `aitask_crew_setmode.sh`), and the `git pull --rebase --no-autostash` lines in addwork/setmode.
- Python: `git_push` / `git_pull` in `.aitask-scripts/agentcrew/agentcrew_utils.py` (runner + `ait crew status set`) — `subprocess.run(timeout=…)`, treating a timeout like any other best-effort failure (warn when not batch).
- `brainstorm_crew._run_addwork` (`.aitask-scripts/brainstorm/brainstorm_crew.py`): add a subprocess timeout and surface it as a registration failure.

Constraints: portable — macOS has no `timeout` binary, so the shell side needs the framework's existing portable timeout helper if one exists (search `.aitask-scripts/lib/` before writing one) or a bounded alternative such as git's own transport timeouts. A timed-out push must leave the branch exactly as a failed push does (upstream set on the next success). Keep t2008's `--no-autostash` on the pulls, and coordinate with t2018 (runner pull ordering) if it is still in flight.

Tests: extend `tests/test_crew_publish_upstream.sh` (t2016) with a cell whose origin never answers (e.g. a `GIT_SSH_COMMAND`/`ext::` transport that sleeps) and assert init/addwork return within the bound and still print CREATED:/ADDED:.
