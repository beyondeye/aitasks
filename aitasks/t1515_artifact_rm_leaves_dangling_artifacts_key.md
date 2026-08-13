---
priority: medium
risk_code_health: low
risk_goal_achievement: low
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
folded_tasks: [1285]
assigned_to: dario-e@beyond-eye.com
anchor: 1210
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-08-13 21:53
updated_at: 2026-08-13 22:49
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

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-13T19:48:11Z status=pass attempt=1 type=human

## Merged from t1285: artifact rm leaves empty artifacts key


`ait artifact rm` leaves a bare `artifacts:` key in the task frontmatter after
removing a task's **last** artifact, instead of dropping the key entirely.

## Observed

During the t1142 manual-verification run (dir backend against a real mount):

```
$ ./ait artifact rm 1142 art:t1142-movetest
Removed artifact art:t1142-movetest from t1142 (manifest deleted, ...)

$ grep -n -A2 '^artifacts:' aitasks/t1142_...md
18:artifacts:
19:---
```

The key is left with no value — it parses as YAML null rather than an absent
key or an empty list. It was stripped by hand before archiving t1142.

## Why it matters

Every other consumer of the frontmatter now sees `artifacts: null` where it
previously saw a list. Any reader that does `for a in fm.get("artifacts", [])`
without a null guard iterates over `None`. The removal path should leave the
frontmatter exactly as it was before the first `artifact create`.

## Where to look

- `.aitask-scripts/aitask_artifact.sh` — `cmd_remove` / `_artifact_rm_txn`
  (around line 461); the frontmatter rewrite that drops the artifact entry.

## Acceptance

- Removing the last artifact from a task drops the `artifacts:` key entirely.
- Removing a non-last artifact leaves the remaining entries untouched.
- Covered by a test in `tests/test_artifact_cli.sh` asserting the frontmatter
  round-trips to its pre-create state.

## Source

Found incidentally during the t1142 verification run; recorded under "Upstream
defects identified" in `aiplans/archived/p1142_manual_verification_auto.md`.

## Folded Tasks

The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

- **t1285** (`t1285_artifact_rm_leaves_empty_artifacts_key.md`)

> **✅ gate:review_approved** run=2026-08-13T20:47:37Z status=pass attempt=1 type=human
