---
priority: medium
effort: low
depends: []
issue_type: enhancement
status: Ready
labels: [framework, execution_profiles]
gates: [risk_evaluated]
anchor: 1311
followup_kind: risk_mitigation
created_at: 2026-07-29 17:04
updated_at: 2026-08-13 23:06
boardidx: 92160
---

## Origin

Risk-mitigation ("after") follow-up for t1311, created at Step 8d after
implementation landed.

## Risk addressed

Goal-achievement risk from t1311's risk evaluation:

> **The shipped `fast.yaml` value is inert unless `default_profiles.shadow` is
> set** — the resolver returns `default` when unset, so a user who sets only the
> tier key sees no change and concludes the feature is broken · severity: medium

## Goal

Surface a warning when a profile sets a **per-skill** key while
`default_profiles.<skill>` is unset or names a different profile — the state in
which that key is silently inert.

t1311 mitigated this with documentation only (five places state the condition:
an inline comment in `seed/profiles/fast.yaml`, the `PROFILE_FIELD_INFO` detail
text, the `profiles.md` schema-table row, and two website pages). This task turns
the documented condition into a **detected** one.

Two candidate surfaces — pick one or both, with a rationale:

- **Settings TUI Profiles tab** — flag the row inline when editing a profile
  whose per-skill key is orphaned. Highest-value: it fires at the moment of
  editing, which is when the user forms the wrong expectation.
- **The profile resolver / skill startup** — warn when a resolved profile carries
  a per-skill key belonging to a *different* skill than the one resolving.

## Design note — the skill↔key mapping is the real work

The warning needs to know which keys belong to which skill. Today that is
implicit in the key name (`qa_tier` → `qa`, `shadow_impl_review_tier` →
`shadow`), which is a convention, not a declaration. Prefer an explicit
declaration in `PROFILE_SCHEMA` (or a sibling map) over prefix-matching the key
name — a prefix heuristic silently misclassifies any future key whose name does
not start with its skill's short name, and would produce false warnings that
train users to ignore it.

Known per-skill keys at time of writing (verify against live source, do not
trust this list): `qa_mode`, `qa_run_tests`, `qa_tier` → `qa`;
`shadow_impl_review_tier` → `shadow`; `explore_auto_continue` → `explore`;
`review_default_modes`, `review_auto_continue` → `review`.

## Verification

- A profile setting `shadow_impl_review_tier` with no `default_profiles.shadow`
  entry warns; the same profile with `default_profiles.shadow` naming it does
  not.
- A profile setting a per-skill key while `default_profiles.<skill>` names a
  *different* profile also warns — that is the subtler half of the condition.
- No warning is emitted for non-per-skill keys.
