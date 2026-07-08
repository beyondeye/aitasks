# Chatlink Sandbox (Docker launch backend)

Infrastructure notes for the sandboxed agent launches performed by the
chatlink gateway (`ait chatlink --headless`). The launcher seam and its
Docker backend live in `.aitask-scripts/lib/sandbox_launch.py` (t1120_5,
pinned contract 8); `chatlink/spawn_seam.py` re-exports the seam names for
compatibility. t562's openshell modes are the planned second backend of the
same `BACKENDS` registry.

## Image

Built from `.aitask-scripts/chatlink/docker/Dockerfile`:

```bash
docker build -t ait-chatlink-agent .aitask-scripts/chatlink/docker/
```

The image contains only the runtime tier (bash, python3, git, node, the
pinned `@anthropic-ai/claude-code` CLI). No repo content is baked in — the
workspace copy supplies its own `.aitask-scripts` helpers and
`.claude/skills` at runtime. The CLI version is pinned via the
`CLAUDE_CODE_VERSION` build arg (see the Dockerfile header for the refresh
policy: bump deliberately; on unexplained smoke/production failures with
unchanged repo code, suspect CLI drift first).

## Mounts and environment (seam contract)

| Container path | Host source | Mode |
|---|---|---|
| `/work` (workdir) | disposable workspace copy — `git archive HEAD` of the linked repo, per session, under `aitasks/metadata/chatlink_sessions/workspaces/<session_id>/` | rw (disposable) |
| `/relay/<session_id>` | the relay session spool dir (`…/chatlink_sessions/relay/<session_id>/`) — the basename must stay the session id (the relay lib derives/validates it from the dir name) | rw |

The container runs as the gateway's uid:gid (`HOME=/tmp`) so files it
creates on the bind mounts stay removable by the gateway's cleanup.

| Env var | Value |
|---|---|
| `CHATLINK_RELAY_DIR` | `/relay/<session_id>` |
| `CHATLINK_BUG_REPORT_FILE` | `/relay/<session_id>/bug_report.md` (the gateway writes the report into the session spool dir) |
| `HOME` | `/tmp` (writable config dir for the agent CLI) |
| launch env allowlist | merged on top — the LLM API key ONLY; never the bot token, never git credentials (key sourcing is wired by t1120_6) |

The workspace copy is committed-HEAD only (no uncommitted/untracked state,
no `.git`) and is removed together with the relay dir when the session
reaches a terminal state.

## Ownership labels and reaping

Every container carries:

- `ait.chatlink.session=<session_id>` / `ait.chatlink.workspace=<chat workspace id>`
- `ait.chatlink.repo=<sha256(resolved repo root)[:12]>` — ownership is
  **repo-scoped**: two repos' gateways may share a chat workspace (e.g. one
  Discord guild); a foreign-repo container is never enumerated, killed, or
  counted live.
- `ait.chatlink.deadline=<epoch>` — the wall-clock cap, stateless: a
  restarted gateway reaps past-cap containers with no local state.

`reap_orphans` (startup reconciliation) removes exited containers, kills
running ones past their deadline (or with a malformed deadline —
fail-closed), and returns the remaining running session ids as the live
set. **Bounded-leak note (deliberate):** a running container whose session
record is already terminal is not reaped — reap is stateless by design; the
container dies at its deadline at the latest.

Mid-life deaths are signalled by a per-launch watchdog thread (signal-only;
all durable cleanup runs on the daemon loop through the reconcile executor).

## Verification

- `tests/test_sandbox_launch.sh` — unit suite with a fake `docker` CLI on
  PATH (argv construction, watchdog, reap filter, workspace-copy hygiene).
- `tests/test_sandbox_docker_smoke.sh` — real-container smoke (skip-capable
  when `docker` or the image is absent): in-container relay round trip with
  a stub agent, in-image `claude` availability, and the production
  explore-relay argv resolving inside the image.
