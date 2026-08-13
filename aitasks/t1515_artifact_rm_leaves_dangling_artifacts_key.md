---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [artifacts, task_metadata]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1210
followup_kind: upstream_defect
created_at: 2026-08-13 21:53
updated_at: 2026-08-13 22:03
---

## Origin

Spawned from t1505_1 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_artifact.sh` — `ait artifact rm` leaves a dangling empty
  `artifacts:` key in the task's frontmatter after removing the task's only
  artifact, instead of removing the key. Harmless to the board today (every reader
  goes through `meta.get("artifacts") or []`) but it is residue a create/remove
  round trip should not leave, and it makes a task look like it still owns
  artifacts. Observed on `aitasks/t1505/t1505_1_bytrail_summary_pane.md` and cleaned
  up by hand in that task.

## Diagnostic context

t1505_1 needed a schema-valid trail artifact for its live terminal check (both
stored trail handles return `ERROR:invalid_trail` until t1468_7 refreshes them to
schema 1.1.0). It registered a temporary artifact and removed it afterwards to leave
no residue:

```
ait artifact create 1505_1 <file> --kind implementation_trail --handle art:trail-t1505-1-livecheck
ait artifact rm 1505_1 art:trail-t1505-1-livecheck
```

`rm` reported success ("manifest deleted, 1 orphan blob(s) swept") but the task
frontmatter was left as:

```yaml
updated_at: 2026-08-13 16:04
artifacts:
---
```

`task_yaml.parse_frontmatter` then yields `artifacts: None`. The board tolerates it
because `_iter_trail_frontmatter_records` reads `meta.get("artifacts") or []`, so
this is latent rather than user-visible today — but any consumer that iterates the
key without the `or []` guard would hit a `TypeError` on `None`.

## Suggested fix

In `aitask_artifact.sh`'s `rm` path, drop the `artifacts:` key entirely when the
removal empties the list, rather than leaving the bare key. Worth a regression test
that a create → rm round trip restores the frontmatter byte-for-byte, since "the key
is absent" and "the key is present but empty" are exactly the distinction the current
code loses.
