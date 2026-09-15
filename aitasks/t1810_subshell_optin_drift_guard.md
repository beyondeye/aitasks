---
priority: medium
effort: low
depends: []
issue_type: test
status: Ready
labels: [codex]
gates: [risk_evaluated]
anchor: 1797
followup_kind: risk_mitigation
created_at: 2026-09-15 09:13
updated_at: 2026-09-15 09:13
---

## Origin

Risk-mitigation ("after") follow-up for t1803, created at Step 8d after implementation landed.

## Risk addressed

Code-health recurrence — T12/T13 cannot see asserts-in-subshell-without-opt-in

- Recurrence: the t1207 drift guard (`tests/test_asserts_counters.sh` T12/T13) only matches the old private-counter scaffolding, so a future test file that asserts inside `( … )` without the opt-in goes silently green again — exactly how this file slipped through · severity: medium · → mitigation: subshell_optin_drift_guard

## Goal

Extend the drift guard in `tests/test_asserts_counters.sh` so the t1207 / t1803
class cannot come back unnoticed:

- **New test:** fail when a `tests/test_*.sh` file sources `tests/lib/asserts.sh`,
  calls an `assert_*` helper (including `assert_record_pass` /
  `assert_record_fail`) inside a standalone `( … )` block, and never calls
  `assert_counters_init`. Ignore comment lines, as T12 does.
- **Negative control (T13 style):** a probe with that shape must be detected, so
  an over-narrow scan cannot make the guard vacuous; plus a positive control that
  an opted-in probe is not flagged.
- **Reference scan used during t1803** (it found only
  `tests/test_session_hook_install.sh`, since fixed in commit 757a7e59f): for each
  line matching `^(\s*)\($`, take the body up to the matching `^\1\)` line and
  look for `assert_*` calls. It can be Python or awk; if bash, keep it
  bash-3.2-safe like `tests/lib/asserts.sh`.
- Consider also requiring the `assert_counters_load` footer call — `init`
  without `load` would still report only in-process counts.
