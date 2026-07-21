---
priority: medium
effort: medium
depends: [t1120_6]
issue_type: feature
status: Ready
labels: [codeagent, sanboxing, tui]
gates: [risk_evaluated]
anchor: 1120
created_at: 2026-07-09 09:28
updated_at: 2026-07-09 09:29
boardidx: 200
---

## Context

Follow-up of t1120_5 (Docker sandbox backend). Sandboxed agent launches
receive credentials ONLY via `spec.env_allowlist`
(`lib/sandbox_launch.py` seam; currently `{}` — t1120_6 owns the minimal
LLM-key config wiring for Claude, per pinned contract 10: env-var names are
owned by the config layer). Beyond that minimal wiring, the framework has
no documented, verified story for how LLM-provider authentication should be
provisioned for sandboxed/headless agents — and no tooling to set it up.
The user wants (a) clear, **verified** reference documentation and (b) a
semi-automatic provisioning helper — **the more automated, the better**
(a skill is acceptable, but a script/TUI that detects and provisions
credentials with minimal typing is preferred).

## Deliverables

1. **Verified auth reference doc** (`aidocs/chat/` — e.g.
   `sandbox_llm_auth.md`): per agent/provider, the supported headless
   in-container auth mechanisms, each **live-verified against a real
   container** (not just collected links — record the verification date +
   image/CLI version):
   - Claude Code: `ANTHROPIC_API_KEY` (API billing) and
     `CLAUDE_CODE_OAUTH_TOKEN` via `claude setup-token` (subscription
     users; long-lived token — likely the right default for this
     framework's audience).
   - Codex CLI: `OPENAI_API_KEY`; ChatGPT-plan login in containers is
     awkward (headless OAuth is an open upstream issue —
     https://github.com/openai/codex/issues/2798; the workaround is
     copying `auth.json`). Document the trade-off honestly.
   - OpenCode: provider env keys (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
     …) or its `auth.json`.
   - Cross-cutting: which mechanism survives `--user uid:gid` +
     `HOME=/tmp` (the seam's container contract, see
     `aidocs/chat/chatlink_sandbox.md`).
2. **Semi-automatic provisioning helper**: a `.aitask-scripts` helper
   (plus TUI integration or skill wrapper as design dictates) that:
   - detects credentials already available on the host (env vars, agent
     config/auth files, `claude setup-token` capability), confirms with
     the user which to use;
   - stores the chosen secret per-PC under
     `aitasks/metadata/chatlink_sessions/` with the same hygiene as the
     bot token (0600 file, 0700 dir, gitignore-verified by unit test —
     mirror `chatlink/paths.py` `write_token`);
   - wires it into the gateway's `env_allowlist` sourcing (BUILD ON
     t1120_6's config surface — do not invent a parallel one; if t1120_6
     has landed, extend its key names/config keys instead of adding new
     ones).
   - Never prints the secret; never commits it; audit-logs provisioning
     events without values.
3. Tests: gitignore + permission hygiene (git check-ignore), detection
   logic against fixture HOME/env, no-secret-in-argv/env-name allowlist
   assertions at the seam boundary.

## Coordination

- **depends: t1120_6** (set in frontmatter) — the env_allowlist sourcing
  config surface lands there; this task extends it multi-provider and adds
  provisioning UX. A reverse pointer is recorded in t1120_6's task file.
- The multi-agent sandbox roadmap task (created alongside this one)
  depends on this task for non-Anthropic provider credentials.
- t562 (OpenShell backend) solves credentials via OpenShell's provider
  system at a different layer — the doc should note that openshell-mode
  sandboxes will NOT use this provisioning path.

## Verification

- Each documented mechanism proven live in-container (skip-capable test or
  recorded manual verification with date + versions).
- Provisioning helper round trip: detect → confirm → store → gateway
  launch env contains exactly the allowlisted key (fake docker argv
  recording, `tests/test_sandbox_launch.sh` pattern).
- Negative controls: bot token / git credentials never enter argv/env;
  secret file unreadable by other users; nothing secret in audit lines.
