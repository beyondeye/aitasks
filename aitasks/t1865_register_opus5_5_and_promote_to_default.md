---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [codeagent, models, ait_settings, backend]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
folded_tasks: [1316]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-09-22 22:59
updated_at: 2026-09-22 23:00
---

## Goal

Register `claudecode/opus5_5` (`cli_id`: `claude-opus-5-5`) in the model registry and promote it to the operational default in place of `claudecode/opus5` for the heavy operations.

Follow the canonical audit at `aidocs/framework/model_reference_locations.md` — it tags every model-reference site `covered_by_refresh` / `needed_for_add` / `needed_for_promote` / `informational_only`. Do not hand-edit the registry JSON; drive the automated sites through `.aitask-scripts/aitask_add_model.sh` and `/aitask-add-model`.

## Current state (verified during exploration)

- `opus5_5` is **absent** from `models_claudecode.json` (14 entries; newest are `opus5`, `sonnet5`, `opus5_1m`, `fable5_1`).
- `aitasks/metadata/codeagent_config.json` has 18 ops; **9 sit on `claudecode/opus5`**: `pick`, `explore`, `learn`, `trail`, `brainstorm-explorer`, `brainstorm-synthesizer`, `brainstorm-module_decomposer`, `brainstorm-module_merger`, `brainstorm-module_syncer`. The other 9 are `claudecode/sonnet5` (7) or `codex/gpt5_6_terra` (`shadow`, `discuss`) and are **out of scope**.
- `seed/codeagent_config.json` carries a smaller 7-op subset (no `brainstorm-*`); its `shadow`/`discuss` are `claudecode/opus5`, unlike the live metadata copy. Decide deliberately whether those two move.
- `.aitask-scripts/lib/agent_string.sh:26` — `DEFAULT_AGENT_STRING="${DEFAULT_AGENT_STRING:-claudecode/opus5}"` (the `${...:-...}` shape must be preserved).
- `.aitask-scripts/aitask_codeagent.sh:743` — human-readable mirror `4. Hardcoded default: claudecode/opus5`.

## Automated path

`.aitask-scripts/aitask_add_model.sh` implements only **3 of the 6** subcommands in the design spec:

| Subcommand | State |
|---|---|
| `add-json` | implemented |
| `promote-config` | implemented |
| `promote-default-agent-string` | implemented (patches `agent_string.sh:26` **and** the `aitask_codeagent.sh` resolution-chain note) |
| `promote-aidocs` | **not implemented** |
| `promote-brainstorm` | **not implemented** (spec'd as a no-op after t579_5 — brainstorm reads `agent_string` exclusively from `codeagent_config.json`) |
| `emit-manual-review` | **not implemented** — `.claude/skills/aitask-add-model/SKILL.md` Step 5 inlines the reminder as prose instead |

Run with `--dry-run` first and review the diffs.

## Manual tail (not covered by the helper)

1. `aidocs/codeagents/claudecode_tools.md:5` — `**Model:** Claude Opus 5 (`claude-opus-5`)`. The audit says this file should always reflect the current default `pick` model. (`promote-aidocs` was never built, so this is a hand edit.)
2. `website/content/docs/commands/codeagent.md` — defaults table L53–63, the sample `resolve` output at L111–114 (`AGENT_STRING`/`MODEL`/`CLI_ID`), the hardcoded-default line L176, and the example config at L185. Run `python3 check_links.py --build` in `website/` afterwards per CLAUDE.md.
3. `tests/test_brainstorm_crew.py:304–310, 419` — literal `"claudecode/opus5"` assertions. **This file never adopted the t1318 derive-don't-pin idiom** (`tests/lib/codeagent_defaults.sh`), so it goes red on promote. Prefer converting it to derive the expected value from the config the code actually reads rather than re-pinning the new literal.

## Out of scope / leave alone

- `tests/test_cross_repo_settings.py` — many `claudecode/opus5` occurrences, all **fixture payloads** for provenance/push logic; the model choice is incidental and stable. Do not churn them.
- `tests/test_shadow_spawn_learner.sh:46` — `--agent-string claudecode/opus4_8` is an **intentional explicit-override** test. Preserve it.
- `verifiedstats` blocks — historical per-model scoring, never edited.
- `.gemini/`, `.codex/`, `.agents/`, `.opencode/` trees — no live model references.

## Open questions to settle during planning

1. **`[1m]` variant.** `opus5` has a sibling `opus5_1m` (`claude-opus-5[1m]`). Whether `opus5_5` warrants an `opus5_5_1m` entry is **unverified** — confirm against the vendor's published model list before adding one. If added, the bracketed `[1m]` suffix must be passed to `aitask_resolve_detected_agent.sh --cli-id` verbatim (stripping it mis-attributes `implemented_with`).
2. **Which ops actually move.** "Most ops" was the stated intent; the concrete list above is the 9 currently on `opus5`. Confirm before running `promote-config --ops`.
3. **`explore-relay`** appears in `website/content/docs/commands/codeagent.md:56` as an op defaulting to `claudecode/opus5` but is **not** present in `aitasks/metadata/codeagent_config.json`. Determine whether this is a doc-only artifact or a missing config entry; it may deserve its own task rather than being fixed here.
4. **Seed vs metadata divergence** for `shadow` / `discuss` (see Current state above).

## Commit strategy

Per the audit's spec and CLAUDE.md, keep three path-scoped commits:

1. `./ait git` (via `aitask_task_commit.sh`) for `aitasks/metadata/models_claudecode.json` + `codeagent_config.json` — never a bare `./ait git commit`, which takes the whole shared `.aitask-data` index.
2. Plain `git` for `seed/*.json`, path-scoped.
3. Plain `git` for `.aitask-scripts/` + `aidocs/` + `website/` + `tests/`, path-scoped.

## Verification

- `jq . <file>` on every JSON written.
- `./.aitask-scripts/aitask_codeagent.sh resolve pick` → `claudecode/opus5_5`.
- `bash tests/test_codeagent.sh`, `bash tests/test_codeagent_trail.sh`, `bash tests/test_codeagent_work_report.sh`, `bash tests/test_shadow_spawn_learner.sh`.
- `bash tests/run_all_python_tests.sh --test-dir tests` (read the **last** line only; use `set -o pipefail` if piping).
- `shellcheck .aitask-scripts/aitask_add_model.sh` if it is touched.

## Note on the folded t1316 (read before acting on its content)

t1316's three cited defects are **already fixed** — t1318 converted
`tests/test_codeagent_work_report.sh`, `tests/test_codeagent_trail.sh`, and
`tests/test_shadow_spawn_learner.sh` to source `tests/lib/codeagent_defaults.sh`
and derive the expected default from the config the resolver actually reads.
Its line references (`:80`, `:81`, `:67`) and its `sonnet4_6` / `opus4_8`
expectations are **stale** — verified 2026-09-22.

What survives from t1316 is its *principle*, which this task must apply to the
one file that never adopted the idiom: `tests/test_brainstorm_crew.py`. Derive,
do not re-pin.

## Merged from t1316: refresh codeagent suite default model expectations


## Origin

Spawned from t1221 during Step 8b review.

## Upstream defect

- `tests/test_codeagent_work_report.sh:80` — seeded and fallback model assertions still expect `sonnet4_6` / `opus4_8` after configuration moved to `sonnet5` / `opus5`.
- `tests/test_codeagent_trail.sh:81` — seeded and fallback model assertions still expect `opus4_8` after configuration moved to `opus5`.
- `tests/test_shadow_spawn_learner.sh:67` — default learn resolution still expects `opus4_8` after configuration moved to `opus5`.

## Diagnostic context

While verifying t1221's skill-launch composer hardening, `tests/test_codeagent.sh` passed 156/156 and every composer-specific assertion in the auxiliary suites passed. `tests/test_codeagent_work_report.sh`, `tests/test_codeagent_trail.sh`, and `tests/test_shadow_spawn_learner.sh` remained red solely because their seeded/default resolution assertions name obsolete Claude models. The current seed configuration and fallback resolve to `sonnet5` and `opus5`.

## Suggested fix

Update the obsolete expected defaults, preferably deriving them from the copied seed configuration where that keeps the tests meaningful and prevents harmless model rotations from making unrelated composer suites red. Preserve explicit old-model override tests that intentionally exercise a named model.

## Folded Tasks

The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

- **t1316** (`t1316_refresh_codeagent_suite_default_model_expectations.md`)

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-22T20:44:29Z status=pass attempt=1 type=human
