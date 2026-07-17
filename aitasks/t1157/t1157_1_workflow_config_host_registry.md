---
priority: high
effort: high
depends: []
issue_type: feature
status: Ready
labels: [workflows, python, installation, remote]
gates: [risk_evaluated]
anchor: 1157
created_at: 2026-07-17 12:14
updated_at: 2026-07-17 12:14
---

## Context

First child of t1157. Chatlink currently loads one repository-local `ChatlinkConfig`, requires one `intake_channel`, reads one repo-local bot token, and starts one daemon per checkout. The parent requires a single provider-neutral host that aggregates checked-in workflow definitions from registered projects and connects one Discord bot across guilds, while preserving existing single-repo setups.

Do not modify the in-progress t1149_2 TUI panel or t1149_3 wizard surfaces in this child. Establish Textual-free configuration/path/preflight APIs that the later TUI child can consume after t1149 lands.

## Key files to modify

- `.aitask-scripts/chatlink/config.py`: versioned project workflow schema, workflow budgets/policy, legacy singleton compatibility, duplicate trigger validation.
- `.aitask-scripts/chatlink/paths.py`: per-machine host registry, global state/secret locations, legacy token fallback helpers.
- `.aitask-scripts/chatlink/preflight.py`: aggregate enabled projects/workflows and report per-workflow/project failures without constructing the daemon.
- `seed/chatlink_config.yaml`, `install.sh`: seed the new schema while preserving upgrade behavior.
- `tests/test_chatlink_config.sh`, `tests/test_chatlink_preflight.sh`: compatibility and aggregation tests.

## Reference files

- `aitasks/metadata/project_config.yaml` and `.aitask-scripts/aitask_project_resolve.sh` for logical project resolution.
- Existing `ChatlinkConfig`, `load_config_with_warnings`, `paths.read_token/write_token`, and t1149_1 `CheckResult` contracts.
- Parent task `aitasks/t1157_chatlink_multi_workflow_remote_explore.md`.

## Implementation plan

1. Define immutable workflow/host configuration types. A project config exposes a versioned `workflows:` list whose entries contain stable id, type (`bug_intake` or `explore` initially), trigger conversation ref, enabled state, authorization, and active/synthesis/retention budgets.
2. Treat existing top-level fields as one implicit `bug_intake` workflow and preserve byte-compatible effective defaults. Emit a migration warning, not a startup failure.
3. Add a per-machine host registry that lists enabled logical project names and the Discord connection; resolve names only through the project registry. Store the token separately with 0700/0600 hygiene. Permit a single legacy repo-local token fallback with a visible migration hint; never silently copy or delete secrets.
4. Aggregate project definitions, reject duplicate workflow IDs within a project and duplicate message-trigger channel refs across the host, and keep one bot token valid across configured guilds.
5. Add a process-lock/state-root contract suitable for one host daemon launched from any registered checkout.
6. Expose structured preflight results by connection, project, and workflow so the daemon and later TUI share validation.
7. Preserve unknown config keys on migration and keep config modules Textual-free.

## Verification

- Legacy singleton config loads as one effective bug workflow with current defaults.
- Two registered project fixtures across two guild refs aggregate successfully; stale projects, duplicate triggers, malformed workflow entries, empty allowlists, and missing token fail/warn at the correct layer.
- Secret permissions and gitignore behavior remain correct; no secret value enters YAML, logs, or argv.
- Existing `test_chatlink_config.sh` and `test_chatlink_preflight.sh` remain green.
