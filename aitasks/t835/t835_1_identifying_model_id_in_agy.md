---
priority: medium
effort: low
depends: []
issue_type: bug
status: Folded
labels: [codeagent]
folded_into: 835
created_at: 2026-05-28 08:41
updated_at: 2026-05-28 10:02
---

## Context

Migrated from t345 (geminicli-era, archived). Reliable model-id
identification was a non-obvious surface for geminicli — only the
`cli_help` tool gave a consistent answer. For agy (Antigravity CLI),
the equivalent surface must be identified and wired into the
framework's detection path.

## Original concern (from t345)

In gemini CLI the only reliable way to identify the current model id
was to call the `cli_help` tool. Need to update the task_workflow to
use a similarly reliable method for agy.

## Scope

1. Identify agy's reliable model-id surface (candidates: `agy --version`,
   a `cli_help`/`cli_info` equivalent, or `~/.gemini/settings.json`
   inspection). Test each in practice.
2. Wire the chosen method into `aitask_resolve_detected_agent.sh` and
   the Model Self-Detection Sub-Procedure so agy returns a valid
   `AGENT_STRING:agy/<name>` matching an entry in `models_agy.json`.
3. Ensure detection works headless (no interactive prompt required).

## Verification

- Launch agy in a test repo; run a workflow that triggers
  model-self-detection; confirm `implemented_with` is written
  correctly to the task frontmatter.
