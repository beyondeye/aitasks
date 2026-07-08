---
Task: t1120_5_docker_sandbox_backend.md
Parent Task: aitasks/t1120_discord_bug_report_channel_integration.md
Sibling Tasks: aitasks/t1120/t1120_6_*.md, t1120_7_*.md, t1120_8_*.md
Archived Sibling Plans: aiplans/archived/p1120/p1120_1_*.md … p1120_4_*.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/fable5 @ 2026-07-08 08:57
---

Contracts: snapshot of parent plan §PINNED — **FROZEN as of t1120_1** (verified
2026-07-07 against `aiplans/p1120_discord_bug_report_channel_integration.md`
contract 0).

# Plan: t1120_5 — Docker sandbox backend

## Context

Fifth child of t1120 (Discord bug-report channel integration). Builds the
sandboxed launch backend: the gateway daemon (t1120_3, landed) spawns its
explore agent (t1120_4, landed) in a Docker container with no extra
permissions. The launcher seam must be shaped so t562's openshell modes slot
in as a drop-in second backend; this child also edits t562's task definition
(scope alignment). No Docker/sandbox support exists in the repo today
(verified — zero Dockerfiles/docker dirs).

## Verification notes (2026-07-07, pre-implementation verify pass)

Re-checked the original plan against current source; all assumptions hold,
with these refinements folded into the steps below:

- Contracts **FROZEN** (parent plan contract 0; t1120_1 archived).
- `chatlink/spawn_seam.py` stub exists exactly as referenced — names to keep
  stable: `SandboxSpec` (:29), `SandboxHandle` (:47), `Launcher` (:59),
  `NullLauncher` (:69), `LaunchError` (:25), test doubles `FakeHandle`/
  `FakeLauncher` (:91/:115). Importers: `daemon.py:42`
  (`Launcher, NullLauncher`), `intake.py:58`
  (`Launcher, LaunchError, SandboxSpec`), `tests/test_chatlink_daemon.sh:58`
  (`FakeLauncher, LaunchError, NullLauncher`). **Re-export, don't delete** —
  cheaper than rewriting t1120_3 imports/tests.
- `intake.py:223-236` already constructs `SandboxSpec` (limits from clamped
  config ceilings) and **drops the returned handle** — nothing polls liveness
  mid-life today. `workspace_copy_path` and `env_allowlist` are not wired
  (None/{}). t1120_3 sibling notes direct t1120_5 to swap
  `serve()`'s `NullLauncher()` (`daemon.py:553`) for the real backend, so the
  daemon-side wiring (workspace copy + death hook) belongs here.
- `reap_orphans(workspace_id)` must return the **LIVE session_id list** —
  `daemon.py:297` feeds it to `reconcile.plan_startup_actions`, which
  fail-closes every non-terminal record not in the live set
  (`reconcile.py:146-158`). Cancel primitive: `SessionDir.write_answer(a,
  overwrite=False)` (`relay.py:523`, race-free `os.link` never-clobber) +
  `pending_questions()` (`relay.py:557`); `Answer(status="cancelled")`.
- Agent argv/env contract (t1120_4 final notes): full argv comes from
  `ait codeagent invoke explore-relay --headless --dry-run` shape —
  `env BASH_DEFAULT_TIMEOUT_MS=630000 BASH_MAX_TIMEOUT_MS=630000 claude
  --model <id> --print /aitask-explorechat --allowedTools
  Bash,Read,Write,Glob,Grep` (`aitask_codeagent.sh:47-48,490-495`). The relay
  dir and bug report travel via **env, not argv**: `CHATLINK_RELAY_DIR`
  (must be an existing dir, :477) + `CHATLINK_BUG_REPORT_FILE` (existing
  file, :481). The backend owns host→container path translation for both.
- Ceilings (config.py:28-39, contract 11): `sandbox_memory` (str "2g",
  regex `^[0-9]+[kmg]$`), `sandbox_cpus` (int), `sandbox_pids` (int),
  `sandbox_wall_clock_s` (int, default 1800, clamp 60–14400) — map directly
  to `--memory/--cpus/--pids-limit` + watchdog deadline.
- `lib/` is a namespace package; `from lib.sandbox_launch import …` works
  from chatlink (precedent: `agentcrew_runner.py:53` imports
  `lib.launch_modes`). Registry pattern to mirror: `VALID_LAUNCH_MODES`
  (`lib/launch_modes.py:26-29`) + `LAUNCHERS` dict + sync `assert`
  (`agentcrew/agentcrew_runner.py:503-514`).
- `aitask_relay_ask.sh` needs only bash + python3/stdlib in-container (its
  header pins this); the workspace copy carries `.aitask-scripts/` and the
  committed `.claude/skills/aitask-explorechat/` — skill discovery is
  cwd-based (proven by t1120_4's live smoke).
- Setup precedent: warn-not-block optional tiers (`aitask_setup.sh` —
  `setup_chat_deps()` :687 "never block the core setup"; CLI tools via
  `command -v` in `install_cli_tools()` :174). No separate doctor script.
- Fake-CLI-on-PATH test precedent: `tests/test_setup_find_modern_python.sh`
  (`make_stub` into `$SCRATCH/bin`, PATH override); scripted fake-agent
  relay conformance precedent: `tests/test_chatlink_relay.sh:656-734`.
- t562 task file unchanged since April — the scope-alignment edit is valid.

## Design decisions (resolved this pass)

1. **Death→cancellation: the watchdog only SIGNALS; all durable mutations
   run daemon-side through the sequential dispatch + executor phase
   discipline.** The spec gains `on_death: Callable[[str], None] | None =
   None` (additive; invoked **at most once** by the backend watchdog thread
   with the session_id, wrapped in try/except — a failing/closed-loop
   callback is swallowed; startup reconciliation is the backstop). The
   callback chatlink supplies does **no I/O**: it is
   `loop.call_soon_threadsafe(death_q.put_nowait, sid)` — a thread-safe
   enqueue onto a daemon-owned `asyncio.Queue`. `run_daemon`'s dispatch loop
   consumes a **merged stream** (small unit-testable helper
   `_merged_events(stream, death_q)` yielding tagged
   `("event", ev)` / `("death", sid)` items via `asyncio.wait`
   FIRST_COMPLETED, pending-task preserved across yields) so there is still
   **exactly one sequential consumer** (`daemon.py:443-447` binding
   invariant preserved — no concurrent handler tasks). A death item is
   handled like startup's non-terminal-not-live branch: new **pure**
   `reconcile.plan_agent_death_actions(record, scan)` (reuses
   `_cancel_and_disable` + `MARK_FAILED` + `REACT_FAILED` +
   `REMOVE_RELAY_DIR`; returns `[]` when the record is terminal/absent —
   idempotent supersession guard) executed by the existing `ActionExecutor`
   (terminal persistence → best-effort platform → dir removal). Cancelled
   answers therefore never appear outside the loop's sequential dispatch,
   and mid-life death gets the full record-failure + component-disable +
   reaction path immediately, not at next restart. Death signals arriving
   while disconnected stay queued and are drained when the merged loop
   resumes (bounded by the reconnect backoff; documented).
2. **Wall-clock enforcement lives in the backend watchdog**, with a
   stateless twin for crash recovery: each container carries label
   `ait.chatlink.deadline=<epoch>` (computed at launch from
   `limits["wall_clock_s"]`) so `reap_orphans` can kill past-cap containers
   after a gateway death without any local state.
3. **Reap semantics (bounded leak documented) + repo-scoped ownership:**
   `reap_orphans` removes exited containers, kills+removes running ones past
   their deadline label, and returns the remaining running session_ids as
   live. A running container whose session record is already terminal is
   *not* reaped (reap is stateless by design) — it dies at its deadline at
   the latest; t1120_6's pump kills promptly on payload completion via the
   stored handle. **Ownership is repo-scoped, not just chat-workspace-
   scoped:** the chat `workspace_id` (Discord guild) can be shared by two
   repos' gateways, so every container also carries
   `ait.chatlink.repo=<sha256(resolved repo root)[:12]>` (lib helper
   `repo_identity(path)`); `DockerLauncher(repo_id=…)` filters reap on
   **both** labels (seam signature `reap_orphans(workspace_id)` unchanged —
   repo identity is constructor state, injected by `serve()` from
   `paths.project_root()`). A foreign-repo container is never enumerated,
   killed, or counted live.
4. **Seam pins the container layout as contract:** workspace copy mounted at
   `/work` (workdir), relay dir at `/relay`; backend exports
   `CHATLINK_RELAY_DIR=/relay` and `CHATLINK_BUG_REPORT_FILE=/relay/bug_report.md`
   (convention: the gateway writes the report into the session spool dir;
   extra non-`question-*`/`answer-*`/`payload.json` files there are tolerated
   per t1120_4 notes). `spec.env_allowlist` is merged on top (LLM key only —
   never bot token / git creds). Documented in the module docstring; t562's
   openshell backend implements the same exports.
5. **Backend selection hardcoded** (`DEFAULT_SANDBOX_BACKEND = "docker"`) —
   a config knob is speculative with one backend; noted in the t562 edit as
   the follow-up surface.
6. **Env-allowlist sourcing is an explicit handoff:** intake keeps
   `env_allowlist={}` — contract 10 forbids inventing env-var names here;
   LLM-key config wiring belongs to t1120_6 (noted there via plan). The
   in-container smoke test uses a stub bash agent (no key, no billing).

## Step 1 — seam `lib/sandbox_launch.py` (promote the stub)

Create `.aitask-scripts/lib/sandbox_launch.py`: move `LaunchError`,
`SandboxSpec` (+ new `on_death` field, default None), `SandboxHandle`,
`Launcher`, `NullLauncher`, `FakeHandle`, `FakeLauncher` verbatim from
`chatlink/spawn_seam.py`; add
`VALID_SANDBOX_BACKENDS = frozenset({"docker"})`, `DEFAULT_SANDBOX_BACKEND`,
`BACKENDS` registry (name → launcher factory) + sync assert (mirror
`launch_modes.py:26-29` / `agentcrew_runner.py:503-514`), and
`get_launcher(backend)`. `chatlink/spawn_seam.py` becomes an explicit-name
re-export shim (docstring updated; t1120_3 imports/tests untouched and must
stay green).

## Step 2 — workspace copy

`make_workspace_copy(repo_root, dest)` in `lib/sandbox_launch.py`:
`git -C <repo_root> archive HEAD | tar -x -C <dest>` via `subprocess`
argv-lists piped (no shell string) — committed HEAD only; uncommitted and
untracked state never leaks (dirty-fixture test); no `.git` in the copy.

## Step 3 — Docker backend

`DockerLauncher` in `lib/sandbox_launch.py` (argv-list only, contract 13):

- `launch(spec)`: refuse with `LaunchError` when docker is absent
  (`shutil.which`) or `spec.workspace_copy_path` is None. Argv:
  `docker run -d --name ait-chatlink-<session_id>
  --label ait.chatlink.session=<sid> --label ait.chatlink.workspace=<wid>
  --label ait.chatlink.repo=<repo_id>
  --label ait.chatlink.deadline=<epoch+wall_clock_s>
  --memory <m> --cpus <c> --pids-limit <p>
  -v <workspace_copy>:/work -v <relay_dir>:/relay
  -e CHATLINK_RELAY_DIR=/relay -e CHATLINK_BUG_REPORT_FILE=/relay/bug_report.md
  -e <allowlisted k=v>… --workdir /work <image> <agent_argv…>`.
  Image constant `DEFAULT_SANDBOX_IMAGE = "ait-chatlink-agent"`.
  Add `workspace_id: str = ""` to the spec (additive, default keeps t1120_3
  tests valid); `repo_id` is `DockerLauncher` constructor state (decision 3).
- `DockerHandle`: `alive()` = `docker inspect -f {{.State.Running}}`;
  `wait(timeout)` = poll loop; `kill()` = `docker rm -f`.
- Watchdog: per-launch `threading.Thread(daemon=True)` polling every ~2 s;
  kills at deadline; invokes `spec.on_death(session_id)` **at-most-once**
  on observed death (flag-guarded), wrapped in try/except (a raising
  callback — e.g. closed loop — is swallowed; reconciliation is the
  backstop). The thread performs no spool/store I/O and never touches
  asyncio directly (decision 1).
- `reap_orphans(workspace_id)`:
  `docker ps -a --filter label=ait.chatlink.workspace=<wid>
  --filter label=ait.chatlink.repo=<repo_id> --format …` →
  parse id/session/deadline/state; `docker rm` exited; `docker rm -f`
  past-deadline running; return remaining running session_ids (sorted).
  Any docker failure ⇒ raise (daemon already treats reap failure as
  "assume none live", `daemon.py:297-300` — fail-closed).

## Step 4 — chatlink wiring (daemon-side, directed by t1120_3 notes)

- `chatlink/paths.py`: add `workspaces_root()` = `sessions_dir()/workspaces`
  (0700, gitignore already covers the parent).
- `chatlink/intake.py` step (d): **workspace-copy creation is part of the
  launch step and shares its fail path.** Inside the same `try` that guards
  `launcher.launch(spec)` (`intake.py:235`, catches `LaunchError`/`OSError`
  — `make_workspace_copy` wraps `git archive`/`tar` failures in
  `LaunchError`): create the copy
  (`make_workspace_copy(project_root(), workspaces_root()/sid)` via
  `asyncio.to_thread`), build the spec (`workspace_copy_path`,
  `workspace_id`, `on_death=self.death_signal`), launch. **Any** failure in
  that block (copy OR launch) ⇒ record marked `failed` + persisted first,
  `MSG_LAUNCH_FAILED` thread note, partial/created copy removed —
  a copy failure can never leave a non-terminal session waiting for the
  next restart.
- `chatlink/reconcile.py`: new pure `plan_agent_death_actions(record, scan)`
  (decision 1) next to `plan_startup_actions`; `[]` on terminal/absent
  record.
- `chatlink/daemon.py`: `run_daemon` creates `death_q` + the
  thread-safe signal closure, threads it into `GatewayPipeline`
  (new `death_signal` param), and consumes the merged stream (decision 1) —
  death items → `plan_agent_death_actions` → `ActionExecutor.execute`.
  `ActionExecutor`: where `REMOVE_RELAY_DIR` executes, also remove the
  session's workspace-copy dir (same phase-3 discipline, best-effort).
- `daemon.py:553` `serve()`: swap `NullLauncher()` →
  `get_launcher(DEFAULT_SANDBOX_BACKEND, repo_id=repo_identity(
  paths.project_root()))`.
- Handle retention (killing on payload completion) stays a documented
  t1120_6 handoff — the pump owns it; death/deadline paths above don't need
  the handle.

## Step 5 — image

`.aitask-scripts/chatlink/docker/Dockerfile`: slim base with bash, git,
python3, node ≥ 20 +
`ARG CLAUDE_CODE_VERSION=<pinned>` /
`npm i -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}` — **version
pinned** so rebuilding the same tag is reproducible; workdir `/work`;
no repo content baked in (the workspace copy supplies `.aitask-scripts` +
skills at runtime). Header comment documents build
(`docker build -t ait-chatlink-agent .aitask-scripts/chatlink/docker/`) and
refresh policy (bump the ARG deliberately; note that CLI drift is the first
suspect when smoke/production fails with unchanged repo code). Short infra doc
`aidocs/chat/chatlink_sandbox.md` (image contract, mounts/env table, reap
semantics incl. the bounded-leak decision, smoke-test pointer).

## Step 6 — setup/doctor + t562 alignment

- Read `aidocs/framework/aitasks_extension_points.md` first, then add a
  warn-not-block `docker` presence check: `command -v docker` warning in
  `aitask_chatlink.sh`'s preflight (runtime surface) + optional-tool mention
  in `aitask_setup.sh` per the doc's rules.
- Edit `aitasks/t562_openshell_launch_semantics.md`: openshell = second
  backend of `lib/sandbox_launch.py` (`BACKENDS` registry, same
  `SandboxSpec`/`SandboxHandle`, same `/work`–`/relay` env exports), shared
  semantics already adopted (upload-copy delivery, session naming, no-TTY
  headless, cleanup verb, reap_orphans, deadline label), backend-selection
  config knob deferred to t562, reverse pointer to t1120_5. Update
  `updated_at`. Commit via `./ait git` (bidirectional coordination).

## Testing

- `tests/test_sandbox_launch.sh` (new; fake `docker` CLI on PATH recording
  argv — `test_setup_find_modern_python.sh` pattern): spec→argv construction
  (labels incl. repo + deadline, limits, env allowlist merged, structural
  CHATLINK_* exports; assert bot-token/git-cred names never in argv/env),
  refusals (docker absent, workspace_copy_path None), handle
  alive/wait/kill against scripted inspect outputs, watchdog wall-clock kill
  + `on_death` at-most-once (short deadline; **negative controls**: without
  the guard flag the double-invoke reproduces; a raising `on_death` is
  swallowed and does not kill the watchdog), reap filter table-driven
  (exited removed / past-deadline killed / live kept+returned /
  **foreign-repo container with matching workspace label untouched** / reap
  failure raises), `make_workspace_copy` dirty-repo exclusion (fixture repo:
  committed present, staged+unstaged+untracked absent, no `.git`) and
  failure wrapping (`LaunchError` on git/tar failure, no partial dir left),
  re-export compat (`chatlink.spawn_seam` names identical objects), registry
  sync assert.
- Extend `tests/test_chatlink_daemon.sh`: intake passes
  workspace_copy_path/workspace_id/`on_death=death_signal`;
  **copy-failure fail path** (make_workspace_copy raises ⇒ record `failed`
  persisted, thread note posted, no leftover copy dir — spy on
  construction order); `plan_agent_death_actions` unit table (pending
  questions ⇒ cancel+disable+MARK_FAILED+REACT_FAILED+REMOVE_RELAY_DIR;
  terminal record ⇒ `[]`; absent record ⇒ `[]`); merged-stream dispatch
  (death signal enqueued mid-event is processed **after** the in-flight
  event completes — sequentiality assertion — and cancelled answers are
  written by the executor on the loop, not by any thread; death during
  disconnect drains on resume); executor removes the workspace dir
  alongside REMOVE_RELAY_DIR; existing 86 checks stay green (additive spec
  fields).
- `tests/test_sandbox_docker_smoke.sh` (new, skip-capable:
  `command -v docker || SKIP`, image missing ⇒ SKIP with build hint): real
  container + mounted relay dir + stub bash agent in the workspace copy
  calling `./.aitask-scripts/aitask_relay_ask.sh`; host writes the answer;
  assert continuation + `payload.json` (via `aitask_relay_payload.sh`) +
  exit 0. **Production-path assertions** (beyond the stub agent): in-image
  `command -v claude && claude --version` succeeds; host-side
  `ait codeagent invoke explore-relay --headless --dry-run` (scratch
  CHATLINK_* env) argv captured and its leading executables (`env`,
  `claude`) resolve inside the image — proving the real agent argv is
  runnable in-container without a billed run. **Negative control:** second
  session, `kill()` mid-question ⇒ death signal observed and, after the
  daemon-side actions run, cancelled answer present + `alive()` False.
- `shellcheck` on touched `.sh`; python tests stdlib-only.

## Step 9 reference

Post-implementation follows task-workflow Step 9 (gates: `risk_evaluated`
declared — orchestrator records it; archive via `aitask_archive.sh 1120_5`).

## Risk

### Code-health risk: medium
- Watchdog threads beside the asyncio daemon (thread↔loop hazard class) ·
  severity: medium · → mitigation: embedded (structural: thread only
  signals via `call_soon_threadsafe`; all spool/store/platform mutations
  run through the sequential dispatch + executor; at-most-once flag;
  negative-control tests)
- Merged-stream restructure of `run_daemon`'s hardened dispatch loop
  (`daemon.py:440-463`) could break the sequential-dispatch / reconnect
  invariants · severity: medium · → mitigation: embedded (pure
  `_merged_events` helper unit-tested; sequentiality + disconnect-drain
  assertions; full t1120_3 suite must stay green in-task)
- Edits to t1120_3's hardened intake/executor paths could regress the landed
  daemon suite · severity: medium · → mitigation: embedded (additive spec
  fields with defaults; copy-failure shares the existing launch fail path;
  full t1120_3 suite must stay green in-task)
- Seam carries chatlink-flavored env exports into `lib/` (abstraction debt
  for t562) · severity: low · → mitigation: embedded (documented seam
  contract + t562 scope-alignment edit in this task)

### Goal-achievement risk: medium
- Image feasibility (claude CLI headless inside container with workspace
  skills) unproven until the smoke test runs · severity: medium ·
  → mitigation: embedded (in-task skip-capable smoke test on the real image)
- No LLM-key wiring yet — production runs can't complete a real explore until
  t1120_6 sources the key · severity: low · → mitigation: embedded (explicit
  documented handoff; stub-agent smoke keeps this child verifiable unbilled)
- Bounded-leak reap decision (terminal-record containers live until
  deadline) could surprise · severity: low · → mitigation: embedded
  (documented in seam docstring + aidocs note)
