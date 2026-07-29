---
priority: medium
effort: low
depends: []
issue_type: test
status: Ready
labels: [tests, codeagent]
gates: [risk_evaluated]
anchor: 1307
created_at: 2026-07-29 10:16
updated_at: 2026-07-29 10:16
---

`tests/test_shadow_spawn_learner.sh` asserts a `defaults.learn` value that the
codeagent config no longer carries, so the suite fails 17/18 on a clean tree.

## Symptom

```
FAIL: resolve learn returns the configured default
  (expected output containing 'AGENT_STRING:claudecode/opus4_8',
   got 'AGENT_STRING:claudecode/opus5')
Results: 17/18 passed, 1 failed
```

## Root cause

`tests/test_shadow_spawn_learner.sh:65-67` pins the expected default:

```bash
out=$("$CODEAGENT" resolve learn 2>&1)
assert_contains "resolve learn returns the configured default" \
    "AGENT_STRING:claudecode/opus4_8" "$out"
```

but `aitasks/metadata/codeagent_config.json` now sets `defaults.learn` to
`claudecode/opus5` — promoted by **t1241** ("Register claudecode/opus5 +
sonnet5 and promote opus5 to default"), which did not update this assertion.
The comment on line 36 (`codeagent_config.json defaults.learn → claudecode/opus4_8`)
is stale for the same reason.

## Why it matters

This is the test file **t1307** edited (it made the pane-id fixtures
multi-digit). A permanently-red suite gives that change — and any future one
touching the shadow learner spawn path — no clean regression signal: a real
break is indistinguishable from the known failure.

## Proposed fix

1. Update the expected value at `tests/test_shadow_spawn_learner.sh:67` to the
   live `defaults.learn` (`claudecode/opus5`), and refresh the stale comment on
   line 36.
2. Consider whether the assertion should pin a literal at all, or read the
   configured default from `aitasks/metadata/codeagent_config.json` so a future
   default promotion cannot silently rot it. Pinning a literal is a legitimate
   choice (it catches an *unintended* default change) — decide deliberately and
   record the reasoning, rather than leaving it to drift again.
3. Sweep for the same staleness elsewhere: grep the test tree for other
   hard-coded `claudecode/opus4_8` / per-operation default expectations that
   t1241 / t1242 may have invalidated.

## Verification

```bash
bash tests/test_shadow_spawn_learner.sh   # expect 18/18
```

Confirm the assertion can still fail: temporarily point `defaults.learn` at a
different registered model and check the test goes red.

## Provenance

Surfaced during **t1307** (harden aitask-shadow against pane-id truncation),
which edited this test's pane-id fixtures and hit the pre-existing failure.
Pre-dates t1307; not caused by it.
