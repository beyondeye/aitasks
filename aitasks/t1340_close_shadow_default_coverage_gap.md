---
priority: medium
effort: low
depends: []
issue_type: test
status: Ready
labels: [tests, codeagent]
gates: [risk_evaluated]
anchor: 1307
created_at: 2026-07-29 21:37
updated_at: 2026-07-29 21:37
---

## Origin

Risk-mitigation ("after") follow-up for t1318, created at Step 8d after
implementation landed.

## Risk addressed

*Code-health risk (low) — silent coverage loss at sites t1318 did not touch:*

> `tests/test_shadow_spawn_config.sh` passes an explicit `--agent-string` on
> every invocation, so it stopped exercising the real `defaults.shadow` when
> that moved to `codex/gpt5_6_terra`.

This is the *quiet* form of the bug t1318 fixed. t1318's three files went **red**
when the defaults were promoted, which is how they were noticed. This one stayed
**green** while silently no longer covering what its name implies — strictly
worse, because nothing signals it.

## Context

`defaults.shadow` in `aitasks/metadata/codeagent_config.json` is
`codex/gpt5_6_terra`, while `seed/codeagent_config.json` has
`claudecode/opus5` — a deliberate divergence. No test currently asserts that
`resolve shadow` honours the configured default at all:

- `tests/test_shadow_spawn_config.sh:31,38,43,50` — every invocation supplies an
  explicit `--agent-string`, so none exercises the default.
- `:62,64` invoke `shadow` with no agent-string but assert exit codes only.

Note this is a **cross-agent** default, so any new assertion must not assume the
claudecode family (a bug the t1318 helper already guards against by deriving its
sentinel agent-agnostically).

## Goal

Add coverage that `resolve shadow` / `invoke shadow` honour the configured
`defaults.shadow`, following the t1318 idiom rather than pinning a literal:

1. Source `tests/lib/codeagent_defaults.sh`.
2. Build a hermetic fixture with `codeagent_fixture_metadata` (it copies
   `models_*.json`, required for the `CLI_ID:` line, and never copies the
   gitignored `codeagent_config.local.json`).
3. Derive the expectation with `codeagent_config_default shadow <config>`.
4. Derive a sentinel with `codeagent_sentinel_excluding` and inject it as
   `DEFAULT_AGENT_STRING`; assert the configured value is returned and the
   sentinel is not.
5. Add the config-less control asserting the sentinel IS returned, so the
   assertion above cannot pass vacuously.
6. Assert with `codeagent_resolve_field` + `assert_eq` (exact field), never
   `assert_contains` on a `KEY:value` substring.

While there, consider whether the existing explicit-`--agent-string` cases should
stay (they cover per-agent command composition, which is still worth testing) —
the gap is the *absence* of a default-resolution case, not the presence of the
explicit ones.

## Verification

```bash
bash tests/test_shadow_spawn_config.sh    # expect all pass
```

Prove the new case discriminates: run with
`AIT_CODEAGENT_FIXTURE_OMIT_OPS=shadow` — the completeness and
configured-default assertions must go red and the suite must exit non-zero.
