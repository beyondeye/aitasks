---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [git, bash_scripts]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2123
followup_kind: upstream_defect
created_at: 2026-10-23 12:14
updated_at: 2026-10-23 12:23
---

## Origin

Spawned from t2132 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/verified_update_lib.sh:118-121` — `is_retryable_push_error`
  matches `failed to push some refs`, which git prints for **every** rejected
  push (auth denied, ambiguous destination, hook refusal, protected branch),
  not only races. Any non-race push failure is therefore retried
  `MAX_REMOTE_RETRIES` times and then reported as "concurrent pushes",
  hiding git's real error.

## Diagnostic context

t2132 fixed `current_task_branch` (it read `heads/<b>` beside a same-named tag)
and qualified the push destination as `HEAD:refs/heads/${branch}`. The
regression `tests/test_verified_update.sh` Test 9t was run red in two stages.
With only the branch-name fix, the push failed on the origin's same-named tag
with `dst refspec main matches more than one`. The classifier read that as a
race, retried 5 times, and the user saw
`Error: Failed to update metadata after 5 retries due to concurrent pushes`.
git's actual reason never reached the output.

The regex is
`'non-fast-forward|fetch first|rejected|failed to push some refs'`. The
`failed to push some refs` alternative (and arguably the bare `rejected`) is the
summary line git appends to every push failure, so it is not evidence of a race.

## Suggested fix

Classify only race-specific markers (`non-fast-forward`, `fetch first`, and the
`[rejected] ... (fetch first|non-fast-forward)` ref lines) as retryable. Every
other failure should `die` immediately with git's output verbatim. Probe each
stop family against a real remote (`-q` included) and pin each in a test: a
race (retries), a hook refusal, and an ambiguous destination (both must fail
fast and show git's message). `aitask_usage_update.sh` shares the lib, so cover
both entry points.
