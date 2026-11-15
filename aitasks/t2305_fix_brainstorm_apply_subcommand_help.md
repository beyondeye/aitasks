---
priority: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [brainstorm]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1879
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-15 18:09
updated_at: 2026-11-15 18:54
---

## Origin

Spawned from t1879 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_brainstorm_apply_initializer.sh:29-35` — no `--help` handling: `ait brainstorm apply-initializer --help` treats "--help" as a task number and prints `APPLY_FAILED:No initializer output at .aitask-crews/crew-brainstorm---help/initializer_bootstrap_output.md` (exit 1), although the dispatcher (`ait`, brainstorm `--help` block, around line 326) advertises "Run 'ait brainstorm <subcommand> --help' for subcommand-specific help."
- `.aitask-scripts/aitask_brainstorm_apply_explorer.sh:30-33` / `.aitask-scripts/aitask_brainstorm_apply_synthesizer.sh:30-33` — `--help` prints only a one-line usage on stderr and exits 2 instead of help text with exit 0.
- `.aitask-scripts/brainstorm/brainstorm_app.py:2351` — the comment names the Running-tab group retry-apply key `S`; the handler (`on_key`, around line 2775) binds `i`.

## Diagnostic context

While documenting these subcommands for the website (t1879), each script's usage was probed. `delete`, `init`, `status` and `archive` all have a `show_help` with `--help|-h` handling; the three `apply-*` scripts parse positional arguments only. The t1879 docs therefore deliberately do not mention `--help` for the apply commands; once this is fixed, consider noting it on `website/content/docs/tuis/brainstorm/reference.md` ("Command-line subcommands").

Related, a judgement call for the implementer rather than a bug: `apply-initializer` calls `apply_initializer_output` directly, without `n000_needs_apply`'s placeholder check, so it overwrites an edited first node and proposal with no confirmation (Ctrl+R does the same, by design `force=True`). The t1879 docs warn about this; adding a guard or a confirmation is optional.

## Suggested fix

Give the three apply scripts a `show_help` + `--help|-h` branch modelled on `aitask_brainstorm_delete.sh` (usage, arguments, `APPLIED:` / `APPLY_FAILED:` output, example), and fix the `S` → `i` comment.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-15T16:54:37Z status=pass attempt=1 type=human
