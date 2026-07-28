---
priority: low
effort: low
depends: []
issue_type: bug
status: Ready
labels: [artifacts]
gates: [risk_evaluated]
anchor: 1142
created_at: 2026-07-28 11:50
updated_at: 2026-07-28 11:50
---

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
