---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [git, bash_scripts, robustness, syncer]
gates: [risk_evaluated]
anchor: 1599
followup_kind: upstream_defect
created_at: 2026-10-21 17:18
updated_at: 2026-10-21 17:18
---

## Origin

Spawned from t2029 during Step 8b review.

## Upstream defect

- `.aitask-scripts/agentcrew/agentcrew_utils.py:623` — `_merge_diverged` runs `merge-tree --write-tree --no-messages --name-only` through text-mode `git_cmd`. Under `core.quotePath=false`, a conflict on a non-UTF-8 path prints raw bytes, and decoding them raises `UnicodeDecodeError` out of `git_pull`, which ends the runner. This dates from t2018 and was not introduced by t2029.

## Diagnostic context

t2029 found that text-mode `git_cmd` mangles file names in its own new `ls-tree -z` / `mktree -z` tree rebuild (a CR became a LF; a non-UTF-8 byte raised). It fixed that path by adding `git_cmd(..., text=False)`. The merge-tree conflict listing in the same function stayed in text mode. With the default `core.quotePath=true`, git C-quotes unusual names (`"f\351.txt"`), so the output is ASCII and decodes fine. With `core.quotePath=false` (a common setting for users with non-ASCII file names), the same conflict prints `f\xe9.txt` raw, and the decode fails.

Verified in a scratch repo: two branches modify a file named `f\xe9.txt`; `git -c core.quotePath=X merge-tree --write-tree --no-messages --name-only HEAD side` exits 1 in both cases; with `X=true` the conflict line decodes, with `X=false` `bytes.decode("utf-8")` raises `UnicodeDecodeError`.

The runner calls `git_pull` without catching this, so the runner process terminates instead of deferring the pull.

## Suggested fix

Run the merge proof with `text=False` (the `text=` switch t2029 added to `git_cmd`) and split the output on bytes. Use `-z` so conflicted names are NUL-separated and never quoted, and compare them to `_runner_alive.yaml` as bytes. Render names for the deferral detail with `errors="replace"`. Keep the harness seam working: `tests/test_crew_pull_no_autostash.sh`'s `wrapped_git_cmd` keys on `a[0] == "merge-tree"` and forwards `**kw`. Add a cell with `core.quotePath=false` set in the fixture repo and a conflicted non-UTF-8 path; it must defer, not crash.
