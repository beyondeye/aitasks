---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [bash_scripts, robustness]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1661
followup_kind: upstream_defect
created_at: 2026-09-01 22:37
updated_at: 2026-09-02 09:22
---

## Origin

Spawned from t1668 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/attachment_lock.sh:39-45` — `with_attach_lock` runs its
  callback as `"$@" || rc=$?`, which disables errexit for the whole callback;
  every other consumer (`aitask_attach.sh`'s add/rm transactions) inherits that,
  so any unchecked command inside one of those callbacks fails silently.

## Diagnostic context

Surfaced while implementing t1668 (make the fold-mark pre-Step-6 abort
transactional). Verified empirically:

```bash
bash -c 'set -euo pipefail
f(){ false; echo "REACHED-AFTER-FALSE"; declare -A m; m[x]=1; }
rc=0; f || rc=$?; echo "rc=$rc"'
# -> REACHED-AFTER-FALSE
# -> rc=0
```

Bash disables errexit for the entire function invocation when its status is
tested by `||`. So inside a `with_attach_lock` callback:

1. A failing command does **not** abort the callback; execution continues.
2. Worse, the callback's *return status* is that of its last command — so a
   trailing successful assignment overwrites the failure, and
   `with_attach_lock` returns **0**.

That is exactly what `aitask_fold_mark.sh`'s `_fold_merge_one` did: a failed
`frontmatter_patch.py append` was immediately followed by `seen_hashes["$h"]=1`,
so the fold committed partial attachment state and reported success. t1668 fixed
that at its own three call sites (`_fold_merge_one`, `_fold_merge_one_artifact`,
`_fold_rebind_refs`) with explicit `|| die` / captured-status checks, and added a
`NOTE:` comment in `_fold_attach_txn` recording that errexit is off there.

**What t1668 did NOT do:** the shared seam still has no guard rail, no
documentation of the property in `attachment_lock.sh`'s own header, and no test
pinning it. `aitask_attach.sh`'s `add` / `rm` transactions run under the same
wrapper and were not audited.

## Scope

1. Audit every `with_attach_lock` callback in the tree (start with
   `aitask_attach.sh` add/rm) for unchecked mutating commands whose failure
   would be swallowed.
2. Decide and implement a durable fix at the seam rather than per-call-site —
   candidates: document the property prominently in `attachment_lock.sh` and
   require callbacks to be explicit; or restructure `with_attach_lock` so the
   callback runs under errexit (e.g. run it in a way that does not test its
   status directly) while still releasing the lock; or have the wrapper verify
   a callback-set success sentinel rather than trusting the return status.
3. Add a test that pins the chosen contract — a callback whose mutating command
   fails must not be reported as success.

Note that any restructuring must preserve `registry_lock`'s EXIT-trap lifecycle
(acquire installs a lock-release EXIT handler; release clears EXIT), which
t1668 works around by chaining its own handler in front of it.
