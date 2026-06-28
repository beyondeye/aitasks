---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [aitasks, task-management, git]
anchor: 1077
created_at: 2026-06-28 10:54
updated_at: 2026-06-28 10:54
---

## Origin

Spawned from t1077 during Step 8b review.

## Upstream defect

`.aitask-scripts/aitask_claim_id.sh:255-262` — `peek_counter()` has the same
latent diagnostic weakness that t1077 fixed in the claim path: it discards
`git fetch` stderr (`git fetch origin "$BRANCH" --quiet 2>/dev/null`) and, when
no local branch exists, dies with a `Run 'ait setup'` hint even if the fetch
failed for a real environmental reason (network, auth, unwritable
`.git/FETCH_HEAD`) while the remote branch is healthy. Out of scope for t1077
(claim-path-only); low impact (peek is read-only and already falls back to the
local branch when one is present).

## Diagnostic context

While fixing the claim path in t1077, `claim_next_id()` was reworked to capture
fetch stderr, use an explicit refspec, and disambiguate "remote branch absent"
from "fetch failed" via a new `remote_branch_state()` helper (`git ls-remote`,
which does not write `.git/FETCH_HEAD`). `peek_counter()` was deliberately left
untouched to keep t1077 scoped to the claim path, but it carries the identical
stderr-discard + misleading-setup-hint pattern.

## Suggested fix

Apply the t1077 pattern to `peek_counter()`: capture `git fetch` stderr, and on
failure use `remote_branch_state()` to decide between the local fallback (branch
present but fetch failed -> show local value with the real error), an
unreachable-origin message, and the genuinely-uninitialized case (only then
suggest `ait setup`). Coheres with t1079, which also touches
`aitask_claim_id.sh`.
