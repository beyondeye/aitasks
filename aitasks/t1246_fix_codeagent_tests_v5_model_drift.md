---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [codeagent, test]
created_at: 2026-07-26 00:19
updated_at: 2026-07-26 00:19
---

## Origin

Surfaced during t1232 (Test-7 verified-parity fix). Pre-existing, unrelated to
t1232's Test-7 change — recorded as a concrete follow-up so the regression is
traceable.

## Upstream defect

`seed/codeagent_config.json` and `seed/models_*.json` were migrated to the
Claude 5 model family (`claudecode/opus5`, `claudecode/sonnet5`,
`claude-opus-5`, `claude-sonnet-5`), but two codeagent test suites still assert
the v4 model names, so they now fail at HEAD:

- `tests/test_codeagent_work_report.sh` — Test 1 (dry-run seeded default),
  Test 4 (`resolve work-report == resolve explain` → `sonnet4_6`), Test 5
  (no-config fallback → `opus4_8`). 5 assertions fail.
- `tests/test_codeagent_trail.sh` — Test 1 (dry-run seeded default), Test 4
  (`resolve trail == resolve pick` → `opus4_8`), Test 5 (no-config fallback →
  `opus4_8`). 4 assertions fail.

`tests/test_codeagent.sh` currently passes. Other tests that hardcode v4 names
(`test_add_model.sh`, `test_usage_update.sh`, `test_shadow_spawn_*`,
`test_risk_mitigation_landed.sh`, `test_crew_init.sh`) should be swept for the
same drift while here — check each rather than assuming.

## Suggested fix

Update the affected assertions to the current seed model names:
- `claudecode/sonnet4_6` → `claudecode/sonnet5`, `claudecode/opus4_8` →
  `claudecode/opus5`, `claude-sonnet-4-6` → `claude-sonnet-5`,
  `claude-opus-4-8` → `claude-opus-5` — matching whatever `seed/codeagent_config.json`
  and `seed/models_*.json` actually declare at fix time.

Consider whether these assertions should derive the expected model from the seed
config instead of hardcoding, to avoid re-breaking on the next model bump.
