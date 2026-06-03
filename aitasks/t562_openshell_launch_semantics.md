---
priority: low
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [agentcrew]
created_at: 2026-04-15 12:39
updated_at: 2026-04-16 15:55
boardidx: 220
---

## Context

"OpenShell" refers to **NVIDIA OpenShell** (https://github.com/NVIDIA/OpenShell),
a sandboxed container runtime for autonomous AI agents. It provides Docker-based
execution environments with policy-enforced network, filesystem, and process
isolation. Key CLI:

```bash
openshell sandbox create [--name NAME] [--upload PATH:DEST] [--policy PATH] \
  [--provider NAME] [--no-keep] [--tty|--no-tty] [-- COMMAND...]
openshell sandbox connect <name>
openshell sandbox delete <name>
```

The sandbox comes with pre-installed agents (claude, codex, opencode, copilot)
and tools (python, node, git, gh). Credentials are injected via providers, not
mounted from the host.

Sibling task t461_9 registered both `openshell_headless` and
`openshell_interactive` in `VALID_LAUNCH_MODES` and added them to the
`LAUNCHERS` dispatch registry in
`.aitask-scripts/agentcrew/agentcrew_runner.py`. Both launchers
currently raise `LaunchError`:

- `_launch_openshell_headless`: "openshell_headless launch mode is
  not yet implemented — tracked in follow-up task"
- `_launch_openshell_interactive`: "openshell_interactive launch
  mode is not yet implemented — tracked in follow-up task"

The picker modals (`LaunchModePickerScreen`, `AgentModeEditModal`) and
the shell validators already accept both variants, so a user can
configure an agent to use them end-to-end — it just transitions to
`Error` on launch.

## Goal

Implement real launch semantics for both `openshell_headless` and
`openshell_interactive` so that configuring an agent with either mode
launches a code agent **inside an NVIDIA OpenShell sandbox**, attached
to the standard crew bookkeeping (pid, heartbeat, log file, status
transitions).

The sandbox provides isolation (network policy, filesystem restrictions,
process constraints) while the agentcrew runner provides orchestration
(lifecycle, scheduling, progress tracking).

## Design questions to resolve during planning

- **Sandbox naming:** Use `agent-<crew_id>-<agent_name>` as the
  `--name` for the sandbox? Must be unique and deterministic so the
  runner can manage (connect, delete) it.
- **Codebase delivery:** How to get the project repo into the sandbox?
  Options: `--upload <worktree>:/sandbox/workspace`, or mount the repo
  as a volume. Upload is safer (sandbox-isolated copy) but slower for
  large repos.
- **Prompt delivery:** Upload the assembled prompt file into the sandbox
  and pass its path to the agent command, e.g.:
  `openshell sandbox create --upload <prompt_file>:/sandbox/ -- claude -p "Read ..."`
- **Agent command mapping:** The sandbox has agents pre-installed. Map
  the `agent_string` (e.g., `claudecode/opus4_6`) to the sandbox agent
  binary (e.g., `claude --model claude-opus-4-6`). Decide whether to
  use `ait codeagent` resolution or direct binary invocation inside the
  sandbox.
- **Headless variant:** `openshell sandbox create --no-tty --no-keep`
  with stdout/stderr captured to the agent's `_log.txt`. The `--no-keep`
  flag auto-deletes the sandbox when the agent exits.
- **Interactive variant:** `openshell sandbox create --tty` launched
  inside a tmux window (same pattern as `_launch_interactive`). The
  user can also `openshell sandbox connect <name>` to attach additional
  terminals. Pipe-pane log mirroring and minimonitor integration apply.
- **Credentials/providers:** How to configure which OpenShell providers
  are available to sandboxed agents? Per-crew config? Global config?
  The `--provider <NAME>` flag can be repeated.
- **Policy:** Should a default sandbox policy be shipped with aitasks?
  Users can customize via `--policy <PATH>`. Consider a default that
  allows outbound to common API endpoints (Anthropic, OpenAI, etc.)
  but blocks everything else.
- **Lifecycle and heartbeat:** The agent runs inside a container. The
  runner cannot directly read the agent's `_alive.yaml` from outside.
  Options: (a) a supervisor wrapper that runs inside the sandbox and
  uploads heartbeat/status updates, (b) the runner polls
  `openshell sandbox get <name>` to check sandbox phase, (c) use
  `openshell sandbox exec` to read the alive file periodically.
- **Cleanup:** On crew shutdown or agent error, call
  `openshell sandbox delete <name>` to clean up containers.
- **OpenShell availability:** Require `openshell` binary in PATH. Raise
  `LaunchError` with a helpful message if not found.

## Files to modify

- `.aitask-scripts/agentcrew/agentcrew_runner.py` — replace the two
  stub functions with real implementations, add shared helpers
  (e.g., `_build_openshell_cmd`, `_resolve_sandbox_agent_cmd`).
- `.aitask-scripts/lib/launch_modes.py` — update docstring to describe
  the real OpenShell-based semantics (remove "not yet implemented").
- `tests/test_openshell_launch.py` — at least one test per variant,
  mocking the `openshell` CLI since tests cannot require Docker.

## Acceptance

- Both `openshell_headless` and `openshell_interactive` launch
  successfully when `openshell` is available (no `LaunchError`).
- Headless variant creates a sandbox, runs the agent, captures output
  to the agent's `_log.txt`, and auto-deletes the sandbox on exit.
- Interactive variant creates a sandbox inside a tmux window with
  pipe-pane log mirroring and minimonitor integration.
- Helpful `LaunchError` message when `openshell` binary is not found.
- `tests/test_openshell_launch.py` has at least one passing case per
  variant (mocked, no Docker dependency).
- Status transitions (`Running` → `Completed` / `Error`) and
  heartbeat files behave the same as existing modes.
- Sandbox cleanup on agent completion and crew shutdown.
