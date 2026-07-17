---
priority: medium
effort: high
depends: [t1120_6, 1139]
issue_type: feature
status: Ready
labels: [codeagent, sanboxing, openshell, codexcli, opencode]
gates: [risk_evaluated]
anchor: 1120
created_at: 2026-07-09 09:29
updated_at: 2026-07-09 09:29
boardidx: 150
---

## Context

Roadmap umbrella (follow-up of t1120_5): extend the chatlink sandbox from
Claude-only to multi-agent (Codex CLI, OpenCode), without losing track of
the moving parts spread across t1120_6, t1139 (auth), and t562
(OpenShell). At planning time this task should be split into children per
the moving parts below; some may resolve to "covered elsewhere — close".

**Current state (t1120_5, landed):** `lib/sandbox_launch.py` seam +
`DockerLauncher`; single image `ait-chatlink-agent`
(`.aitask-scripts/chatlink/docker/Dockerfile`: node slim + bash + python3 +
git + pinned `@anthropic-ai/claude-code`). The image is a *runtime tier
only* — all framework helpers come from the workspace copy at `/work`
(bash + python3-stdlib envelope), so framework changes need no rebuild.
Claude-only is NOT an image limitation: the `explore-relay` operation in
`aitask_codeagent.sh` is claudecode-only by design (headless `--print` +
slash-command skill discovery + `--allowedTools` are Claude-specific
invocation shapes; see t1120_4's archived plan).

## Moving parts (children at planning time)

1. **Per-agent headless explore-relay variants** — the real blocker. Codex
   (`codex exec` shape) and OpenCode (`opencode run` shape) need their own
   headless operation variants in `aitask_codeagent.sh` + skill-surface
   ports of `aitask-explorechat` (Codex/OpenCode skill trees). Each needs
   the t1120_4-style live smoke (env preconditions, relay blocking past
   default tool timeouts, payload landing).
2. **Per-agent image strategy** — prefer NOT hand-rolling a per-agent
   Dockerfile matrix. Options to evaluate: (a) extend the single Dockerfile
   with more CLIs (fat image); (b) image family
   `ait-chatlink-agent-<agent>` sharing a base layer; (c) reuse published
   images — Docker's official sandbox templates
   (`docker/sandbox-templates:opencode`,
   https://docs.docker.com/ai/sandboxes/agents/), community Codex/OpenCode
   images (icoretech/codex-docker, ghcr.io/pilinux/opencode), OpenAI's
   `openai/codex-universal` (base env only, no CLI). Whatever is chosen
   must keep the seam contract: bash + python3 present (relay helpers),
   `/work` + `/relay/<session_id>` mounts, `--user uid:gid` + `HOME=/tmp`.
   Image selection per launch needs a small seam extension (image is
   currently `DockerLauncher` constructor state).
3. **Provider credentials** — owned by t1139 (depends). Non-Anthropic
   providers (OPENAI_API_KEY etc.) are prerequisites for 1.
4. **Network hardening (optional child)** — our image has open egress;
   Anthropic's official devcontainer ships a default-deny egress firewall
   (https://github.com/anthropics/claude-code/tree/main/.devcontainer) —
   evaluate whether to adopt for the sandbox tier or defer to OpenShell.
5. **OpenShell convergence guard (t562)** — OpenShell publishes a base
   sandbox image (ghcr.io/nvidia/openshell-community/sandboxes/base) with
   Claude, Codex, OpenCode, Copilot CLIs pre-installed and gateway-managed
   credential providers + kernel-level isolation. When t562 lands as the
   second `BACKENDS` entry, parts 2 and 4 (and t1139's provisioning for
   openshell-mode) are solved at OpenShell's layer. **Rule: before
   implementing any child of parts 2/4, check t562's status — do not build
   what OpenShell mode is about to obsolete.** t562's task file carries the
   seam-contract notes.

## Sequencing

t1120_6 (e2e glue + minimal Claude key wiring) → t1139 (auth docs +
provisioning) → this roadmap's children. Frontmatter depends encodes this.

## Verification (umbrella level)

- Each agent variant proven by a live in-container relay smoke (mirror
  `tests/test_sandbox_docker_smoke.sh`, skip-capable).
- Seam unit suite (`tests/test_sandbox_launch.sh`) extended for any spec /
  image-selection changes.
- An explicit "not building X because t562/OpenShell covers it" decision
  recorded per skipped part.
