---
priority: medium
effort: low
depends: []
issue_type: feature
status: Implementing
labels: [codeagent, models]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5_5
created_at: 2026-11-10 08:22
updated_at: 2026-11-10 09:59
---

Register **Fable 5.2** (`claude-fable-5-2`) as a Claude Code model in the aitasks framework, following the Fable 5.1 precedent (t1680, commit 1a120ec73) and the recent Haiku 5.5 registration (t1916, af5bc8645).

## Why
Fable 5.2 isn't registered in `models_claudecode.json` yet, so a Fable 5.2 session currently:
- self-detects through `aitask_resolve_detected_agent.sh` as the reserved fallback `claudecode/unregistered_*` rather than a real entry
- gets the coauthor name `Claude Code/fable5_2` instead of `Claude Code/Fable 5.2` (checked: `aitask_codeagent.sh coauthor claudecode/fable5_2` prints the raw name; for `fable5_1` it prints `Fable 5.1`)
- can't be picked as a configured model for any op

## Scope
Do every write through `.aitask-scripts/aitask_add_model.sh` (the `/aitask-add-model` skill), never by hand:

1. **Add** with `add-json --agent claudecode --name fable5_2 --cli-id claude-fable-5-2 --notes "Fable 5.2 — ..."`, which writes both `seed/models_claudecode.json` and `aitasks/metadata/models_claudecode.json`. Model the notes on the `fable5_1` entry and say Fable 5.1 is now the previous generation. You may also refresh the `fable5_1` notes, which currently call it "most capable".
2. **Lineage** with `record-supersession --agent claudecode --old fable5_1 --new fable5_2`, which adds the edge to `.aitask-scripts/lib/model_supersessions.json` so `ait upgrade` offers 5.2 to projects still on 5.1. The existing `fable5 → fable5_1` edge stays as it is.
3. **No promotion.** Fable isn't the seed default for any op in `seed/codeagent_config.json`, and `DEFAULT_AGENT_STRING` stays `claudecode/opus5_5`.
4. **`[1m]` variant check.** Fable 5.1 has no `_1m` sibling. Find out whether Claude Code reports a Fable 5.2 session's model as `claude-fable-5-2[1m]`, for example by checking the model id a real Fable 5.2 session self-detects with. If it does, also register `fable5_2_1m` → `claude-fable-5-2[1m]` so those sessions resolve to a real entry (the precedent is `opus5_5_1m` / `sonnet5_5_1m` / `haiku5_5_1m`; [1m] entries are the same model, not a distinct one). If it doesn't, skip it and record why in the plan.

## Out of scope
- **opencode**: `opencode/claude-fable-5-2` in `seed/models_opencode.json` is CLI-discovered and goes through `aitask-refresh-code-models`, not `aitask_add_model.sh`. Mention it as a possible follow-up only.
- t967 (Fable 5 launch-time fallback to Opus) is a separate investigation and is unaffected.

## Verification
- `./.aitask-scripts/aitask_resolve_detected_agent.sh --agent claudecode --cli-id claude-fable-5-2` → `AGENT_STRING:claudecode/fable5_2`
- `bash .aitask-scripts/aitask_codeagent.sh coauthor claudecode/fable5_2` → `AGENT_COAUTHOR_NAME:Claude Code/Fable 5.2`
- the supersession lineage tests still pass: `bash tests/test_install_superseded_models.sh`, `tests/test_model_supersession.py` (through `bash tests/run_all_python_tests.sh --test-dir`, or directly), and `bash tests/test_codeagent.sh`
- both registry files stay valid JSON and agree with each other on the new entry

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-10T07:59:58Z status=pass attempt=1 type=human
