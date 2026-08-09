---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [shadow, aitask_monitormini, aitask_monitor]
gates: [risk_evaluated]
anchor: 1159
created_at: 2026-08-09 10:44
updated_at: 2026-08-09 10:44
---

## Origin

Spawned from t1427_4 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_shadow_rejected.sh:61` — the usage/header comment documents the machine format as `REJECTED:<id>|<ts>|<producer>|<marker line>`, but `cmd_list` at `:339` emits `REJECTED:r%s|…` with an `r`-prefixed id. A consumer written against the comment would build the wrong entry ids for `remove`.

## Diagnostic context

t1427_4 documented the rejection store in `aidocs/framework/shadow_agent.md`.
The first draft of the machine-format line was written from the helper's own
header comment at `:61` and stated `REJECTED:<id>|…`. The `keys_match_source`
post-phase check re-derived the format from the actual emitter — the `printf` at
`:339`, which is `printf "REJECTED:r%s|%s|%s|%s\n", id, ts, prod, marker` — and
caught the mismatch. The aidocs text was corrected to `REJECTED:r<id>|…`, but
the helper's own comment is still wrong.

This matters because the id is what `remove` consumes. `remove` happens to
accept ids both with and without the `r` prefix, so a consumer built from the
comment would not fail loudly — it would work by luck of that tolerance, which
is exactly the kind of latent mismatch that breaks when the tolerance is
tightened.

Corroborating evidence that the comment misled a reader before: the archived
sibling notes disagree with each other on this exact point —
`aiplans/archived/p1427/p1427_1_rejection_store_helper.md` records the format as
`REJECTED:<id>|…` while `p1427_2_picker_reject_tristate.md` records
"Entry ids are `r`-prefixed on the wire (`REJECTED:r1|…`)".

## Suggested fix

Update the comment at `.aitask-scripts/aitask_shadow_rejected.sh:61` to
`REJECTED:r<id>|<ts>|<producer>|<marker line>`. Check whether
`tests/test_shadow_rejected.sh` pins the `r` prefix on the `list --machine`
output; if not, add an assertion so the emitted format and its documentation
cannot drift again.
