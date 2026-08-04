---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [workflow, git]
gates: [risk_evaluated]
anchor: 1233
created_at: 2026-07-28 01:06
updated_at: 2026-07-28 01:06
boardidx: 51200
---

## Problem

`.aitask-scripts/aitask_remote_drift_check.sh` extracts plan-referenced paths in
two steps: it pulls every token shaped like a relative path with a known
extension, then keeps only those rooted in a **hardcoded allowlist of this
repository's own top-level directories** (`:179-182`):

```
aitask-scripts|aitasks|aiplans|claude/skills|opencode/skills|gemini/skills|agents/skills|website|seed|tests
```

The framework is installed into other projects, whose source trees have entirely
different top-level directories (`src/`, `lib/`, `app/`, `internal/`, …). There,
the intersection is always empty, so the helper emits `NO_OVERLAP` for every
run.

## Impact

The overlap signal is the *strong* half of the remote-drift check: `AHEAD:<n>` +
`OVERLAP:<file>` is treated as a strong warning regardless of the
`remote_drift_check: warn|strong-only` profile setting, whereas `AHEAD` +
`NO_OVERLAP` is suppressed entirely under `strong-only`. So in every consumer
project:

- the "remote changes touch files your plan targets" escalation never fires;
- profiles using `remote_drift_check: strong-only` get **no drift warning at
  all**, because the only signal they act on is the one that can never be
  produced.

The check silently degrades to a no-op rather than failing visibly.

## Discovery

Surfaced while implementing t1233 (customizable output branch), which added a
second invocation of this helper for the merge target. The defect is pre-existing
and independent of that change.

## Suggested direction

Derive the roots rather than hardcoding them — e.g. accept any path that exists
in the working tree, or that git knows about (`git ls-files --error-unmatch`),
or take the roots from project configuration. Whatever replacement is chosen,
add a test that runs the helper in a fixture whose top-level directories do
**not** match this repository's, and assert `OVERLAP:` is still reported. The
current suite only exercises repo-shaped fixtures, which is why this went
unnoticed.

## Acceptance

- A plan referencing a file under a non-aitasks-shaped top-level directory
  produces `OVERLAP:<file>` when the remote changed that file.
- The existing repo-shaped overlap test still passes.
- A regression test covers the consumer-project directory layout.
