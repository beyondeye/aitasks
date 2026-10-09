---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [codeagent, models]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1916
followup_kind: upstream_defect
created_at: 2026-10-09 11:33
updated_at: 2026-10-09 11:43
---

## Origin

Spawned from t1919 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_opencode_models.sh:178-307 — the refresh's read→write of models_opencode.json is uncoordinated with aitask_usage_update.sh / aitask_verified_update.sh: a counter write landing between the merge's read and the final write is still last-writer-wins (only detectable after the fact through the writers' commits); a shared writer lock or a commit-based compare-and-swap would close it`

## Diagnostic context

t1919 fixed the merge so a refresh carries every field it does not own
(`verified`, `verifiedstats`, `usagestats`, …) — previously only
`verified`/`verifiedstats` survived, so `usagestats` (written by
`aitask_usage_update.sh:200-248`) was silently dropped, including a write
landing *during* discovery. That fix covers writes that land before the merge
reads the registry. It does not cover a write between the merge's
`cat "$existing_file"` and the final `jq ... > "$METADATA_FILE"`.

The counter writers have no lock the refresh can share. With a remote they
commit in a temp clone, push to `origin/aitask-data`, then fast-forward local
(`lib/verified_update_lib.sh:168-242`); without a remote they write and commit
locally (`commit_metadata_update_local`). t1919 therefore coordinated its one
run by hand: pin the local + origin tips for the path before the refresh,
re-check them right before the metadata commit, push fast-forward only. Process
checks (`pgrep opencode`) are evidence only — the writers are plain shell
scripts any agent can run.

Regression test with the reusable fixture pattern:
`tests/test_opencode_models_merge.sh` (stub `opencode` whose hook can simulate a
concurrent writer).

## Suggested fix

Either make the refresh write through the same remote-aware commit flow the
counter writers use (re-apply the merge on the fresh tip and retry on a
non-fast-forward), or introduce a shared registry lock (see
`lib/registry_lock.sh`) taken by all three writers around read-modify-write.
