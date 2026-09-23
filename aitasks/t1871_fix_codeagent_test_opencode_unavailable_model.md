---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [codeagent, models]
gates: [risk_evaluated]
anchor: 1865
followup_kind: upstream_defect
created_at: 2026-09-23 17:34
updated_at: 2026-09-23 17:34
---

## Origin

Spawned from t1868 during Step 8b review.

## Upstream defect

- `tests/test_codeagent.sh:353` — Test 11e loops over `opencode/openai_gpt_5_2`,
  which commit 2d9db16ab (t1867) flipped to `"status": "unavailable"` in
  `seed/models_opencode.json`; `aitask_codeagent.sh` now refuses it and the file
  aborts under `set -e` before its remaining tests run.

## Diagnostic context

While verifying t1868 (a prose edit to the aitask-add-model Step 5 reminder),
`bash tests/test_codeagent.sh` exited 1. `bash -x` shows the last command:

```
bash .../aitask_codeagent.sh --agent-string opencode/openai_gpt_5_2 --dry-run invoke pick 42
Error: Model 'openai_gpt_5_2' is unavailable (not currently marked as available
by connected providers). Run 'ait opencode-models' to refresh.
```

`git diff 2d9db16ab~1 2d9db16ab -- seed/models_opencode.json` shows
`openai_gpt_5_2` going `"status": "active"` → `"unavailable"` (t1867, landed
2026-09-23 16:48). The test's fixture installs the seed registry, so it picks
up the new status. The whole file stops at that point, so every test after
11e (11e onward, including `test_codeagent.sh`'s later coauthor / list checks)
goes unrun, not just the one assertion. t1867 is archived, so no task owned the
breakage.

This is the same drift class as t1246 / the t1318 derive idiom: a test pinned
to a literal registry entry that a later refresh legitimately changes.

## Suggested fix

Stop pinning a literal opencode model in Test 11e: derive an `active` opencode
model from the fixture's `models_opencode.json` (jq select on
`status == "active"`), the same way t1865 made the default-resolution
assertions derive from `seed/codeagent_config.json`. Fail loudly (not skip) if
the registry has no active opencode model. Check the rest of the file, and
`tests/test_codeagent_work_report.sh`, for other literal opencode/codex model
names with the same exposure.
