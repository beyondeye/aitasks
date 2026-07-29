---
Task: t1318_fix_stale_learn_default_assertion_in_shadow_spawn_test.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1318 — Fix stale `learn` default assertion in the shadow spawn test

## Context

`tests/test_shadow_spawn_learner.sh:67` pins `AGENT_STRING:claudecode/opus4_8`
as the expected `defaults.learn`, but **t1241** promoted the live value to
`claudecode/opus5` without updating the assertion. The suite fails 17/18 on a
clean tree, so the file **t1307** just edited (multi-digit pane-id fixtures) has
no clean regression signal — a real break is indistinguishable from the known
failure.

t1318's item 3 asks to sweep for the same staleness elsewhere. The sweep found
this is the **third** file, not the only one: **8 broken assertions across 3
test files**, all from the same t1241/t1242 promotion.

| file:line | asserts | expected | actual |
|---|---|---|---|
| `tests/test_shadow_spawn_learner.sh:67` | `resolve learn` | `claudecode/opus4_8` | `claudecode/opus5` |
| `tests/test_codeagent_trail.sh:108,109` | seeded `resolve trail` / `pick` | `claudecode/opus4_8` | `claudecode/opus5` |
| `tests/test_codeagent_trail.sh:116` | no-config fallback | `claudecode/opus4_8` | `claudecode/opus5` |
| `tests/test_codeagent_work_report.sh:107,108` | seeded `work-report` / `explain` | `claudecode/sonnet4_6` | `claudecode/sonnet5` |
| `tests/test_codeagent_work_report.sh:116,117` | no-config fallback | `claudecode/opus4_8` | `claudecode/opus5` |

Root cause of the recurrence: `aidocs/framework/model_reference_locations.md` —
the canonical "what to touch when promoting a model" checklist — does not list
any of these three files.

### The trap in the obvious fix

Simply swapping the literal to `opus5` would make
`test_shadow_spawn_learner.sh:67` **stop discriminating**. Its section header
claims *"explicit learn default (no silent DEFAULT_AGENT_STRING fallback)"*, but
`DEFAULT_AGENT_STRING` is now **also** `claudecode/opus5`
(`.aitask-scripts/lib/agent_string.sh:26`) — the assertion would pass whether or
not the config was ever read. The same vacuity now affects
`test_codeagent_trail.sh` Test 4 (seed `pick` == `DEFAULT_AGENT_STRING` ==
`claudecode/opus5`).

## Approach

**Derive every expectation from a hermetic fixture, and inject a sentinel
`DEFAULT_AGENT_STRING` so "config was read" is always distinguishable from
"fell back".**

Seams, all probed live during planning (not assumed):

- `resolve_agent_string()` (`.aitask-scripts/aitask_codeagent.sh:56-86`) reads
  `$METADATA_DIR/codeagent_config.local.json` → `$METADATA_DIR/codeagent_config.json`
  → `$DEFAULT_AGENT_STRING`.
- `METADATA_DIR` and `DEFAULT_AGENT_STRING` are both `${VAR:-default}` in
  `.aitask-scripts/lib/agent_string.sh:26-27` → **both env-overridable**.
- `resolve` needs `models_<agent>.json` in `METADATA_DIR` for its `CLI_ID:`
  line; without them it prints `AGENT_STRING:` then exits **1**. The fixture
  must copy them.
- All three `models_<agent>.json` share the shape `{"models":[{"name":…}]}`, so
  a sentinel can be derived **agent-agnostically** as `<agent>/<name>`.
- End-to-end probe of the exact fixture below returned **rc=0** and:
  config present → `claudecode/opus5`; config absent → the sentinel; config
  present but `learn` key deleted → the sentinel. A `codex/…` sentinel resolves
  cleanly too.

Every resolution assertion follows one pattern, with **three fixture variants**
that make the discriminator a permanent test case rather than a manual ritual:

| fixture | expected result | what it proves |
|---|---|---|
| config present | the **derived** config value, and **not** the sentinel | the config is actually read |
| config absent | the **injected sentinel** | the injection seam is live → the row above is not vacuous |
| config present, `<op>` key deleted | the **injected sentinel** | a missing `defaults.<op>` silently falls back — the exact hazard the section guards |

Because the sentinel is injected, **no test ever needs to know the real
`DEFAULT_AGENT_STRING`** — that literal disappears from the suite entirely.

For `trail` / `work-report`, additionally assert the **equivalence their own
comments already state** ("resolve trail == resolve pick", "resolve work-report
== resolve explain") with `assert_eq` on the full outputs — a stronger and
permanently promotion-proof encoding of the heavy/light class contract.

### Reused, not reinvented

- `tests/lib/asserts.sh` — `assert_eq`, `assert_contains`, `assert_not_contains`,
  `assert_exit_zero` (takes a command, so `assert_exit_zero "…" test -n "$x"`
  covers the non-empty check with no new helper).
- The `jq -r '.defaults.<op>'` derivation idiom at `tests/test_add_model.sh:138-142,149`.
- The "derive expectations rather than hardcoding a copy" precedent and rationale
  in `tests/test_settings_brainstorm_descriptions.py:27,47`.
- The existing fixture builder + `cleanup_test_env` in
  `tests/test_codeagent_trail.sh:30-58` / `test_codeagent_work_report.sh:29-57`
  — **kept as-is**; only their assertions change.

## Files to change

### 1. `tests/lib/codeagent_defaults.sh` — NEW

Three call sites need the same derivations; triplicating the `jq` incantations
is what let them drift apart in the first place. Follows the `tests/lib/`
convention (`asserts.sh`, `work_report_equiv.py`) with the same
`_AIT_…_LOADED` double-source guard, BSD-safe (`jq` + POSIX `grep -vxF` only).

```bash
codeagent_fixture_metadata <dest_dir> [<config_src>]
    # mkdir -p <dest_dir>; copy models_*.json AND project_config.yaml from
    # $PROJECT_DIR/aitasks/metadata. If <config_src> is given, copy it in as
    # codeagent_config.json.
    # NEVER copies codeagent_config.local.json -> the fixture is hermetic and
    # a developer's gitignored local override cannot change the result.
    # Honors $AIT_CODEAGENT_FIXTURE_OMIT_OPS (csv of op names): jq-deletes
    # those keys from the copied config. This is the negative-control seam.

codeagent_config_default <op> <config_file>
    # jq -r --arg op "$op" '.defaults[$op] // empty' -- prints empty if absent.

codeagent_sentinel_excluding <metadata_dir> <agent_string>...
    # Scans <metadata_dir>/models_<agent>.json, emits "<agent>/<name>" for every
    # registered model of EVERY agent, drops the excluded ones, prints the first
    # survivor. Agent-agnostic (a codex/opencode default gets a valid sentinel)
    # and guaranteed registered in the very dir the resolve runs against.
```

There is deliberately **no** `codeagent_hardcoded_default`: tests assert the
sentinel they injected, so nothing has to read (or re-source) the real
`agent_string.sh`. That removes any chance of the helper describing a different
`DEFAULT_AGENT_STRING` than the copied library under test in the fixture repos.

### 2. `tests/test_shadow_spawn_learner.sh`

The current test resolves against **live** `aitasks/metadata/`, where
`codeagent_config.local.json` takes precedence — so today's assertion is
machine-dependent. Replace lines **60-67** with a hermetic block:

```bash
FIXTURE_ROOT="$(mktemp -d)"
trap 'rm -rf "$FIXTURE_ROOT"' EXIT

live_cfg="$PROJECT_DIR/aitasks/metadata/codeagent_config.json"
codeagent_fixture_metadata "$FIXTURE_ROOT/withcfg" "$live_cfg"
codeagent_fixture_metadata "$FIXTURE_ROOT/nocfg"           # no config at all
AIT_CODEAGENT_FIXTURE_OMIT_OPS=learn \
    codeagent_fixture_metadata "$FIXTURE_ROOT/nolearn" "$live_cfg"

learn_default=$(codeagent_config_default learn "$FIXTURE_ROOT/withcfg/codeagent_config.json")
sentinel=$(codeagent_sentinel_excluding "$FIXTURE_ROOT/withcfg" "$learn_default")

# Config completeness: a missing `learn` key is the silent-fallback hazard.
assert_exit_zero "codeagent config declares a learn default" test -n "$learn_default"

out=$(METADATA_DIR="$FIXTURE_ROOT/withcfg" DEFAULT_AGENT_STRING="$sentinel" \
      "$CODEAGENT" resolve learn 2>&1)
assert_contains     "resolve learn returns the configured default" "AGENT_STRING:$learn_default" "$out"
assert_not_contains "resolve learn does not fall back to DEFAULT_AGENT_STRING" "AGENT_STRING:$sentinel" "$out"

out=$(METADATA_DIR="$FIXTURE_ROOT/nocfg" DEFAULT_AGENT_STRING="$sentinel" \
      "$CODEAGENT" resolve learn 2>&1)
assert_contains "no-config resolve learn falls back to DEFAULT_AGENT_STRING" "AGENT_STRING:$sentinel" "$out"

out=$(METADATA_DIR="$FIXTURE_ROOT/nolearn" DEFAULT_AGENT_STRING="$sentinel" \
      "$CODEAGENT" resolve learn 2>&1)
assert_contains "config without a learn key falls back to DEFAULT_AGENT_STRING" "AGENT_STRING:$sentinel" "$out"
```

The fixture copies the **live project config**, so the completeness assertion
still guards the real shipped file — it just cannot be perturbed by a local
override. 1 assertion → 5; file goes 18 → 22.

Also refresh the stale comment at **line 36** (drop `→ claudecode/opus4_8`).

Leave lines 39-58 alone: 45/52/57 pass explicit `--agent-string` (fixtures), and
40-42 assert agent-family / pane-id facts that survive promotion. *Known,
pre-existing and out of scope:* those dry-run cases still read live metadata, so
a local override pointing `learn` at a non-claudecode agent would fail line 40 —
true before this task and unchanged by it.

### 3. `tests/test_codeagent_trail.sh`

Keep `setup_test_env` / `cleanup_test_env` exactly as they are (they already
copy `models_*.json`, `project_config.yaml` and `agent_string.sh`, and already
build a config-less variant via `setup_test_env false`). Change only assertions:

- **Test 4 (104-109):** derive from the seed file the fixture actually copies —
  `codeagent_config_default pick "$PROJECT_DIR/seed/codeagent_config.json"`;
  derive the sentinel from `$TMPDIR_TEST/aitasks/metadata`; run both resolves
  with `DEFAULT_AGENT_STRING="$sentinel"`; assert the derived value, assert the
  sentinel is absent, and `assert_eq "$output_pk" "$output_tr"` for the
  heavy-class equivalence.
- **Test 5 (114-116):** run against the already-config-less env with
  `DEFAULT_AGENT_STRING="$sentinel"` and assert the sentinel is returned.
- Refresh stale comments at **4, 27, 104**.

### 4. `tests/test_codeagent_work_report.sh`

Same treatment: **Test 4 (104-108)** against `.defaults["work-report"]` and
`.defaults.explain` from `seed/codeagent_config.json`, plus `assert_eq`
equivalence; **Test 5 (113-117)** asserting the injected sentinel. Refresh the
stale comment at **26**.

> Seed-vs-live divergence is deliberate here: these tests copy
> `seed/codeagent_config.json` into their fixture (`:47-48`), so the derivation
> must read the **seed** file. The two disagree on `shadow`
> (`claudecode/opus5` vs `codex/gpt5_6_terra`).

### 5. `aidocs/framework/model_reference_locations.md`

Add three rows to the **§7 Tests** table (after line 116) registering the three
files, tagged `informational_only` with the note that they now derive their
expectations from config + an injected sentinel and are promotion-proof. Update
the §7 row of the Summary matrix (line 130) to match. Scope is deliberately
limited to registering these files — the doc's other stale `opus4_*` line
references are handled by the `refresh_model_reference_locations_doc` follow-up.

## Verification

```bash
bash tests/test_shadow_spawn_learner.sh      # expect 22/22
bash tests/test_codeagent_trail.sh           # expect all pass
bash tests/test_codeagent_work_report.sh     # expect all pass
shellcheck tests/lib/codeagent_defaults.sh
```

**Negative controls — no source neutering, no dirty state.** Two of the three
controls are now *permanent test cases* (the `nocfg` and `nolearn` fixtures
above): every run proves the sentinel injection is live and that a missing key
falls back, so the positive assertion can never pass vacuously.

The remaining "prove the harness can actually fail" check runs through the
fixture seam and mutates **nothing** in the repo:

```bash
# Drops defaults.learn from the COPIED fixture config only (temp dir, auto-removed).
AIT_CODEAGENT_FIXTURE_OMIT_OPS=learn bash tests/test_shadow_spawn_learner.sh
# EXPECT: non-zero exit — "codeagent config declares a learn default" and
# "resolve learn returns the configured default" both go red.
```

**AC deviation, stated explicitly.** t1318's Verification says *"temporarily
point `defaults.learn` at a different registered model and check the test goes
red."* Under a derived assertion that is no longer a valid control — surviving a
deliberate default change is the entire point of the fix. The env-knob control
above replaces it and is repeatable, self-cleaning, and requires no edit to any
tracked file.

## Risk

### Code-health risk: medium
- Replacing a failing literal assertion with a derived one can **weaken the
  test into vacuity** — the derived expectation and the resolver read the same
  config, so a broken resolver could still satisfy it · severity: medium ·
  → mitigation: in-plan (injected sentinel + the permanent `nocfg` / `nolearn`
  fixture cases + the `AIT_CODEAGENT_FIXTURE_OMIT_OPS` control), reinforced by
  `document_derived_assertion_idiom`
- New shared helper `tests/lib/codeagent_defaults.sh` adds a file under
  `tests/lib/` that three tests source; a bug there fails three suites at once ·
  severity: low · → mitigation: in-plan (shellcheck + the three suites are the
  helper's own coverage)
- Sites the sweep found **silently under-covering** are left as-is:
  `tests/test_shadow_spawn_config.sh` passes an explicit `--agent-string` on
  every invocation, so it stopped exercising the real `defaults.shadow` when
  that moved to `codex/gpt5_6_terra` · severity: low ·
  → mitigation: `close_shadow_default_coverage_gap`

### Goal-achievement risk: low
- The promotion checklist is only **partially** refreshed: registering these
  three files in a doc whose other `opus4_*` line references are stale leaves
  the next promoter with a partly-untrustworthy checklist · severity: low ·
  → mitigation: `refresh_model_reference_locations_doc`
- Otherwise the goal is directly verifiable by running the three scripts, and
  every seam the approach depends on (`METADATA_DIR` override,
  `DEFAULT_AGENT_STRING` override, the `models_*.json` requirement, the
  three-fixture matrix, cross-agent sentinels) was probed live during planning.

### Planned mitigations
- timing: after | name: document_derived_assertion_idiom | type: documentation | priority: medium | effort: low | addresses: derived assertions drifting into vacuity (code-health) | desc: Record the derive-from-fixture + injected-sentinel pattern in aidocs/framework/testing_conventions.md so future default-sensitive tests are promotion-proof by construction
- timing: after | name: close_shadow_default_coverage_gap | type: test | priority: medium | effort: low | addresses: silent coverage loss at sites this task does not touch (code-health) | desc: tests/test_shadow_spawn_config.sh passes an explicit --agent-string everywhere and no longer exercises the real defaults.shadow (now codex/gpt5_6_terra) — add a case that resolves the configured shadow default
- timing: after | name: refresh_model_reference_locations_doc | type: documentation | priority: low | effort: low | addresses: partly-untrustworthy promotion checklist (goal-achievement) | desc: Refresh the remaining stale opus4_6/4_7/4_8 line-number references throughout aidocs/framework/model_reference_locations.md, beyond the three test files t1318 registers

## Post-implementation

Follow `task-workflow` **Step 8** (review before commit; `test:` commit type per
the task's `issue_type`) and **Step 9** (merge approval, `ait gates run 1318`
for the `risk_evaluated` gate, archival). Working on the current branch —
`Output branch: main`.
