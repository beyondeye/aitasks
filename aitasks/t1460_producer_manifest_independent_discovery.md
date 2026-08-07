---
priority: medium
effort: medium
depends: []
issue_type: test
status: Ready
labels: [shadow]
gates: [risk_evaluated]
anchor: 1159
created_at: 2026-08-07 16:10
updated_at: 2026-08-07 16:10
---

## Origin

Risk-mitigation ("after") follow-up for t1427_3, created at Step 8d after
implementation landed.

## Risk addressed

Marker-keyed producer discovery cannot see a fifth producer written without the
marker phrase, so every rule guard stays green while a live producer carries
none of the rules.

From `aiplans/archived/p1427/p1427_3_producer_suppression_rule.md` `## Risk`:

> Producer discovery is keyed on the marker phrase, so a fifth review procedure
> written without it inherits none of the rules and
> `test_producer_set_is_the_known_set` still passes on the original four — the
> suppression rule would be absent from a live producer with every guard green ·
> severity: low · → mitigation: producer_manifest_independent_discovery

## Goal

Give the shadow producer set an **independent discovery signal** so a new
concern producer cannot be added silently.

`TestProducerShortRegionRule._producers()` in `tests/test_concern_parser.py`
globs `.claude/skills/aitask-shadow/*.md` and keeps only files containing
`PRODUCER_MARKER` (`load-bearing for minimonitor's parser`).
`test_producer_set_is_the_known_set` then compares that filtered set to
`KNOWN_PRODUCERS`. The enumeration is therefore **self-fulfilling**: a new
review procedure that instructs an agent to emit a concern block but omits the
marker phrase is invisible to the filter, the known-set assertion still sees
exactly the original four files and passes, and the new producer inherits none
of the three inlined rules (short-region, region-mandatory, rejection
suppression).

Candidate approaches (pick one during planning, do not assume):

- an explicit producer **manifest** checked into the skill dir, with the marker
  scan cross-checked against it; or
- a **broader scan** that flags any `aitask-shadow/*.md` which instructs
  emitting a concern block (e.g. names `===AITASK-CONCERNS===` as something to
  emit, or carries a `- [priority | region]` example) but lacks the marker.

## Scope notes

- This is a **pre-existing** t1187 property, not something t1427_3 introduced.
  It is shared by all three rule guards — fixing it benefits
  `TestProducerShortRegionRule` and `TestProducerRegionRequiredRule` equally,
  not just the suppression rule.
- It was spawned rather than inlined into t1427_3 because it re-opens the shared
  discovery contract and the `KNOWN_PRODUCERS` pin that all three classes
  reference by attribute; that blast radius did not belong in a task whose job
  was "state the rule in four files".
- `concern-format.md` must NOT be made to carry the marker phrase — doing so
  registers it as a producer. Any new discovery signal has to keep the
  format-doc-vs-producer distinction intact.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests` green (read the last
  stderr line for the verdict).
- Negative control: add a synthetic fifth producer-shaped file **in a fixture
  directory** (never in the real skill tree — that tree is shared with
  concurrent sessions) that emits a block but omits the marker, and confirm the
  new discovery signal flags it while the old marker-only filter does not.
