---
priority: medium
effort: low
depends: []
issue_type: documentation
status: Ready
labels: [tests, codeagent]
gates: [risk_evaluated]
anchor: 1307
created_at: 2026-07-29 21:37
updated_at: 2026-07-29 21:37
boardidx: 730
---

## Origin

Risk-mitigation ("after") follow-up for t1318, created at Step 8d after
implementation landed.

## Risk addressed

*Code-health risk (medium) — derived assertions drifting into vacuity:*

> Replacing a failing literal assertion with a derived one can **weaken the
> test into vacuity** — the derived expectation and the resolver read the same
> config, so a broken resolver could still satisfy it.

t1318 solved this for three specific test files. Nothing yet stops the next
default-sensitive test from being written with a pinned literal (which rots) or
with a naive derived assertion (which goes vacuous).

## Goal

Record the pattern t1318 established in `aidocs/framework/testing_conventions.md`
so future default-sensitive tests are promotion-proof *by construction*.

Document, with the concrete rationale:

1. **Derive, don't pin.** Read the expected value from the config the code under
   test actually reads (`aitasks/metadata/codeagent_config.json` live,
   `seed/codeagent_config.json` for fixture envs — they diverge). Helpers already
   exist in `tests/lib/codeagent_defaults.sh`.
2. **Inject a sentinel to prove the derivation is not vacuous.** Asserting the
   real fallback constant is worthless when it happens to equal the configured
   value (in t1318 both were `claudecode/opus5`, so a refreshed literal would
   have passed whether or not the config was ever read). Override
   `DEFAULT_AGENT_STRING` with a registered-but-different sentinel and assert the
   config value AND not-the-sentinel.
3. **Keep the fallback path as a permanent test case**, not a manual ritual: a
   config-less fixture that must return the sentinel is what proves the injection
   seam is live.
4. **Build fixtures hermetically.** Never resolve against live metadata when a
   gitignored per-developer override (`codeagent_config.local.json`) outranks the
   project config — that makes assertions machine-dependent.
5. **Assert exact extracted fields, not substrings.** `assert_contains
   "KEY:$expected"` degrades into the always-true `"KEY:"` when `$expected` is
   empty, and lets a prefix (`opus5`) match a longer name (`opus5_1m`). Anchoring
   with a trailing newline does NOT fix it: the assert helpers use `grep -F`,
   which reads an embedded newline as a second, empty pattern matching every
   line, making `assert_not_contains` unpassable. Use
   `codeagent_resolve_field` + `assert_eq`.

Cross-reference the note added to `aidocs/framework/model_reference_locations.md`
§7 by t1318, so the promotion checklist and the testing conventions point at each
other.

## Verification

- The new section exists in `aidocs/framework/testing_conventions.md` and names
  `tests/lib/codeagent_defaults.sh` as the shared helper home.
- `aidocs/framework/model_reference_locations.md` §7 and the new section
  cross-reference each other (bidirectional doc link).
