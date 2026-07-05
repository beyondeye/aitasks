---
Task: t1120_5_docker_sandbox_backend.md
Parent Task: aitasks/t1120_discord_bug_report_channel_integration.md
Sibling Tasks: aitasks/t1120/t1120_1_*.md … t1120_7_*.md
Archived Sibling Plans: aiplans/archived/p1120/p1120_*_*.md
Worktree: aiwork/t1120_5_docker_sandbox_backend
Branch: aitask/t1120_5_docker_sandbox_backend
Base branch: main
---

Contracts: snapshot of parent plan §PINNED — provisional until t1120_1 freeze
(expected FROZEN — verify).

# Plan: t1120_5 — Docker sandbox backend

Deliverables (6 items incl. the t562 scope-alignment edit), the launcher-seam
contract 8 text, and verification list are in the task file
(`aitasks/t1120/t1120_5_docker_sandbox_backend.md`). Read
`aitasks/t562_openshell_launch_semantics.md` and t1120_3's archived plan
(spawn-seam protocol stub `chatlink/spawn_seam.py`) first.

## Step 1 — seam `lib/sandbox_launch.py`

Promote t1120_3's protocol stub into `.aitask-scripts/lib/sandbox_launch.py`:
`SandboxSpec` dataclass (workspace_copy_path, relay_dir, session_id,
env_allowlist: dict, limits: {memory,cpus,pids,wall_clock_s}, agent_argv),
`SandboxHandle` protocol (`wait(timeout)`, `kill()`, `alive()`),
`VALID_SANDBOX_BACKENDS = {"docker"}` + `BACKENDS` registry with sync assert
(mirror `lib/launch_modes.py:26-29,503-514`); `reap_orphans(workspace_id)`
dispatches per backend. chatlink imports this seam; `chatlink/spawn_seam.py`
becomes a re-export or is deleted (update t1120_3 tests accordingly).

## Step 2 — workspace copy

`make_workspace_copy(repo_root, dest)`: `git -C <repo_root> archive HEAD | tar
-x -C <dest>` — committed HEAD only (uncommitted state never leaks; test with
a dirty fixture repo). Cleanup verb removes it after session terminal state.

## Step 3 — docker backend

`_launch_docker(spec)` builds argv list (never shell string):
`docker run -d --name ait-chatlink-<session_id>
--label ait.chatlink.session=<session_id>
--label ait.chatlink.workspace=<workspace_id>
--memory <m> --cpus <c> --pids-limit <p>
-v <workspace_copy>:/work -v <relay_dir>:/relay
-e <allowlisted env only> --workdir /work <image> <agent_argv…>`.
Handle: `alive()` = `docker inspect -f {{.State.Running}}`; `wait(timeout)` =
poll + wall-clock enforcement (kill on breach); `kill()` = `docker rm -f`.
Death→cancellation: on non-alive with pending questions, invoke the relay-lib
cancel hook (write `cancelled` answers) — the callback is part of the spec
(supplied by the daemon).
`reap_orphans`: `docker ps -a --filter label=ait.chatlink.workspace=<id>
--format {{.ID}} {{.Label …session}}` → kill/remove those past wall-clock or
with terminal/absent session state.

## Step 4 — image

`docker/chatlink-agent/Dockerfile` (location per repo convention — decide with
a look at existing packaging; nothing exists today): base python+node, install
agent CLI + `ait` (copied from the workspace copy at runtime — prefer
installing only the CLI runtime in the image and using /work's own
`.aitask-scripts`), document build (`docker build -t ait-chatlink-agent …`)
and refresh policy in the Dockerfile header + aidocs note.

## Step 5 — setup/doctor + t562 alignment

- `docker` presence check in the setup/doctor path (read
  `aidocs/framework/aitasks_extension_points.md`; warn-not-block — sandbox is
  an opt-in feature tier like chat deps).
- Edit `aitasks/t562_openshell_launch_semantics.md`: scope it to implementing
  `openshell` as a second backend of `lib/sandbox_launch.py` (same
  `SandboxSpec`/`SandboxHandle`), note the shared semantics already adopted
  (upload-copy delivery, session naming, no-TTY headless, cleanup verb,
  reap_orphans). Commit via `./ait git`.

## Testing

Bash test script with a **fake docker CLI on PATH** (records argv): all
verification items in the task file — argv construction (labels, limits, env
allowlist; assert bot-token/git-cred names absent), reap filter logic
(table-driven), dirty-repo copy exclusion, death→cancellation negative
control. In-container smoke test as its own skip-capable script
(`command -v docker || SKIP`).

## Step 9 reference

Post-implementation follows task-workflow Step 9.
