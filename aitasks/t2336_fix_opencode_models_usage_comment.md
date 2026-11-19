---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [codeagent, opencode, models]
gates: [risk_evaluated]
anchor: 2333
followup_kind: upstream_defect
created_at: 2026-11-19 05:15
updated_at: 2026-11-19 05:15
---

## Origin

Spawned from t2333 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_opencode_models.sh:9-11` — the usage comment names an `ait opencode-models` subcommand (`--dry-run`, `--list`, `--sync-seed`) that the `./ait` dispatcher does not route: `./ait opencode-models --help` prints `ait: unknown command 'opencode-models'`.

## Diagnostic context

t2333's task body told the implementer to "Run `ait opencode-models --sync-seed`", repeating this script header. The command failed, and the refresh was run as `./.aitask-scripts/aitask_opencode_models.sh --sync-seed` instead. The current user docs already call the script directly: `website/content/docs/installation/updating-model-lists.md:25,38-40` and `.claude/skills/aitask-refresh-code-models/SKILL.md:48`. So only the script's own header (and an old release blog post, which is history and should be left alone) still advertise the unrouted command.

## Suggested fix

Either rewrite the header's usage lines to `bash .aitask-scripts/aitask_opencode_models.sh [--dry-run|--list|--sync-seed]`, matching the docs, or route `opencode-models` in the `ait` dispatcher if a user-facing verb is wanted. Decide which during planning. Re-verify with `./ait opencode-models --help`, and grep `aitasks/` for task bodies that still quote the old command.
