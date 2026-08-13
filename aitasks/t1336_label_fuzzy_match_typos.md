---
priority: medium
effort: low
depends: []
issue_type: enhancement
status: Ready
labels: [aitask_explore, aitask-create, bash_scripts]
gates: [risk_evaluated]
anchor: 1312
followup_kind: risk_mitigation
created_at: 2026-07-29 18:39
updated_at: 2026-08-13 23:06
boardidx: 95232
---

## Origin

Risk-mitigation ("after") follow-up for t1312, created at Step 8d after
implementation landed.

## Risk addressed

addresses: goal-achievement — normalization misses the typo class

Verbatim from t1312's plan `## Risk` → Goal-achievement risk:

> - Normalization matching misses the typo class that dominates actual drift
>   (`brainstom_modules`, `skill_optiomizations`) · severity: medium ·
>   → mitigation: `label_fuzzy_match_typos`

t1312 shipped `aitask_labels.sh classify`, whose `NEAR:` match is a
**separator/case** equivalence only: it strips `_` and `-` and compares
(`aitask-create` ≡ `aitask_create`). That catches the separator-drift half of
the vocabulary problem and none of the typo half — which is the half actually
visible in the current `aitasks/metadata/labels.txt`.

## Goal

Add edit-distance near-matching to `.aitask-scripts/aitask_labels.sh classify`
so typo variants are suggested against existing labels, not just separator and
case variants.

Concretely, a proposed `brainstom_modules` should classify as
`NEAR:brainstom_modules:brainstorm_modules` rather than `NEW:`, letting the
/aitask-explore Step 3a "Use the suggested existing labels" option prevent the
new variant from ever entering the vocabulary.

Real typo pairs already present in the live vocabulary, usable as fixtures:
`aitakspickrem`, `brainstom_modules`, `brainstorm_synthetize`,
`skill_optiomizations`, `sanboxing`, `modelvrapper`.

Design notes:
- Keep it deterministic and unit-testable — `aitask_labels.sh` is deliberately
  a pure function over `labels.txt` with no I/O beyond reading it.
- Pick a distance threshold that scales with label length; a fixed edit
  distance of 2 over short labels produces noise.
- `NEAR:` already carries a comma-separated candidate list, so the output shape
  does not need to change — only the candidate set does. Rank
  separator/case matches ahead of edit-distance matches so the existing exact
  behaviour is never displaced.
- Extend `tests/test_label_vocabulary_lib.sh` or add a dedicated
  `tests/test_aitask_labels_classify.sh` with the typo fixtures above, plus a
  negative control proving the threshold rejects genuinely unrelated labels.
