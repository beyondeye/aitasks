---
priority: low
effort: low
depends: []
issue_type: test
status: Implementing
labels: [git, bash_scripts, robustness]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1599
followup_kind: risk_mitigation
created_at: 2026-10-19 17:14
updated_at: 2026-10-19 17:16
---

## Origin

Risk-mitigation ("after") follow-up for t2060, created at Step 8d after implementation landed.

## Risk addressed

guard coverage is shape-limited (code-health)

- Guard coverage is shape-limited (per-file variable discovery, `PYTHON`-named interpreter); an unrecognized future call site would be silently omitted · severity: low (boundary documented + assertion labels qualified in this plan) · → mitigation: exhaustive_merge_driver_guard_discovery

## Goal

Make Test 3 of `tests/test_aitask_merge_boardgroup.sh` (the "every recognized
merge-driver invocation passes --base-file" guard) exhaustive. Today
`driver_invocations` discovers driver-path variables (assigned
`.../aitask_merge.py`) per file, and recognizes only the call shape
`"$<..PYTHON..>" "$<var>"`. The floor and the `lib/task_automerge.sh`
canonical-site assertion still pass when a call site is omitted, so the guard
misses:

1. a caller that uses a driver-path variable assigned in a **different**
   (sourced) file — e.g. sourcing `lib/task_automerge.sh` and reusing
   `_AIT_AUTOMERGE_SCRIPT`;
2. an invocation whose interpreter variable name lacks `PYTHON`, a call by
   literal path, or a call through an array.

Acceptance: both omission classes become either recognized (and base-checked)
or a hard failure ("unclassified aitask_merge.py reference — update the
guard"). Each class needs a planted fixture proving it is caught. Keep the
existing planted control and the base-removal mutant behaviour.
