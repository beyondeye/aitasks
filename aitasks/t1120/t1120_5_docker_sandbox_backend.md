---
priority: high
effort: high
depends: [t1120_4]
issue_type: feature
status: Ready
labels: [chat_surface, python, sanboxing]
gates: [risk_evaluated]
anchor: 1120
created_at: 2026-07-05 12:00
updated_at: 2026-07-05 12:00
---

## Context

Fifth child of t1120. The sandboxed launch backend: spawn the gateway's agent
in a Docker container without granting it extra permissions (the human in the
loop is on Discord, not at the terminal). **No Docker/sandbox support exists in
the repo today.** The seam must be shaped so t562's openshell modes slot in as
a drop-in second backend — this child also UPDATES t562's task definition (see
below). Parent plan: `aiplans/p1120_discord_bug_report_channel_integration.md`
(§PINNED contract 8 + "Crash ownership & startup reconciliation").

**Contracts: snapshot of parent plan §PINNED — provisional until t1120_1
freeze.** Consumes contracts 1 (session_id), 2 (spool), 6 (death→cancellation),
8 (launcher seam), 11 (ceilings), 13 (argv-only).

## Launcher seam (contract 8, consumed verbatim)

Lives in `lib/` (e.g. `.aitask-scripts/lib/sandbox_launch.py`) as a mode
registry mirroring `lib/launch_modes.py`'s `VALID_LAUNCH_MODES`/`LAUNCHERS`
pattern: `launch(spec) -> handle{wait(), kill(), alive()}` +
`reap_orphans(workspace_id)`, where `spec` bundles workspace-copy path, relay
dir, env allowlist, resource limits, session_id. Adopts t562's decided
semantics up front: workspace **delivery by copy/upload**, container **named
from session identity**, headless = non-interactive no-TTY, explicit cleanup
verb.

## Key deliverables

1. Docker backend for the seam: disposable **workspace copy** (clone/archive
   of committed HEAD — never a live-repo mount; uncommitted state must not
   leak), writable relay/output mounts only, env allowlist (**LLM API key
   only; no bot token, no git creds**), resource limits
   (`--memory/--cpus/--pids-limit` from t1120_2 ceilings), wall-clock
   supervision, exit/liveness detection, death→cancellation hook (contract 6).
   All process construction argv-list only (contract 13).
2. Container labels `ait.chatlink.session=<session_id>` and
   `ait.chatlink.workspace=<workspace_id>`; `reap_orphans(workspace_id)`
   enumerates labeled containers (`docker ps --filter label=…`) and
   kills/removes any past wall-clock cap or with terminal/absent session
   state (stateless discovery — gateway-death safe).
3. Dockerfile/image ownership: image contains `ait`, the agent CLI, and repo
   deps; document build/refresh.
4. **In-container relay smoke test** (before t1120_6's glue): spawn the real
   container with mounted relay dir; a stub agent script inside asks one
   question via `aitask_relay_ask.sh`; host writes the answer; assert
   continuation + `payload.json` lands. Proves bind mounts, env allowlist,
   workdir layout, and agent-CLI availability together. Skip-capable when
   `docker` is absent.
5. `docker` presence check wired into setup/doctor path (read
   `aidocs/framework/aitasks_extension_points.md` before touching setup).
6. **Update t562's task definition** (`aitasks/t562_openshell_launch_semantics.md`)
   to target the shared seam — scope alignment (openshell = second backend of
   `lib/sandbox_launch.py`, same `spec`/`handle` contract), not just a
   pointer. Commit via `./ait git` (bidirectional coordination convention).

## Reference files for patterns

- `.aitask-scripts/lib/launch_modes.py` (:26-29 registry,
  docstring :9-22 openshell semantics) and
  `.aitask-scripts/agentcrew/agentcrew_runner.py:410-424` (`_launch_headless`
  Popen reference), :489-514 (stub launchers + registry assert).
- `aitasks/t562_openshell_launch_semantics.md` — sandbox naming, `--upload`
  delivery, `--no-tty --no-keep`, heartbeat, cleanup design questions.
- `.aitask-scripts/applink/server.py:42-49` — ceilings style.

## Verification

- Unit tests with a fake docker CLI (recorded argv): spec→argv construction
  (argv-only, labels present, limits applied, env allowlist honored — bot
  token/git creds never in argv/env), reap_orphans filter logic, workspace
  copy excludes uncommitted state.
- In-container relay smoke test (skip-capable, see deliverable 4).
- Negative control: kill the container mid-question ⇒ death→cancellation hook
  fires (cancelled answers written, handle reports not-alive).
