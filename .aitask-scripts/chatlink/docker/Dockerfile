# ait-chatlink-agent — sandbox image for the chatlink gateway (t1120_5).
#
# Build:
#   docker build -t ait-chatlink-agent .aitask-scripts/chatlink/docker/
#
# Contract (lib/sandbox_launch.py seam — see its module docstring):
#   - The disposable workspace copy (committed HEAD of the linked repo) is
#     mounted at /work (the working directory); the relay session dir at
#     /relay/<session_id> (the basename must stay the session id — the
#     relay lib derives/validates it from the dir name). No repo content is
#     baked into the image — /work supplies its own .aitask-scripts helpers
#     and .claude/skills at runtime.
#   - The agent CLI (claude) runs headless with CHATLINK_RELAY_DIR /
#     CHATLINK_BUG_REPORT_FILE from the environment and the LLM API key
#     from the launch env allowlist. No bot token, no git credentials.
#
# Refresh policy: CLAUDE_CODE_VERSION is PINNED so rebuilding the same tag
# is reproducible — bump it deliberately (then rebuild + rerun
# tests/test_sandbox_docker_smoke.sh). When a smoke/production run fails
# with unchanged repo code, agent-CLI drift is the first suspect: compare
# the pinned version against the host's `claude --version`.

FROM node:25-slim

ARG CLAUDE_CODE_VERSION=2.1.204

# bash + python3: aitask_relay_ask.sh / relay_ask.py (stdlib-only) inside
# the workspace copy; git: available for read-only agent exploration
# (the copy carries no .git and no credentials); procps: healthier ps/top
# for the agent's shell tooling.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash ca-certificates git procps python3 \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}"

WORKDIR /work

# No default agent command: the gateway supplies the full argv (resolved
# via `ait codeagent invoke explore-relay --headless --dry-run` on the
# host). A bare `docker run` of this image just prints the CLI version.
CMD ["claude", "--version"]
