---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [task_relations, git]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1981
implemented_with: claudecode/opus5_5
created_at: 2026-11-04 15:39
updated_at: 2026-11-06 07:53
---

## Context

Child of t1981 (task relations and backlog obsolescence). The design is settled
in `aidocs/framework/task_relations.md`. **Read sections D1, D2, D3 and D11
before planning.** This child builds the store that every other child reads or
writes. It does no analysis.

Records live on a dedicated orphan branch, `aitask-relations`, never in task
files (premise 2). The store must work in branch and legacy mode, with and
without a remote, and must never present an empty or unreachable store as "no
related tasks".

## Scope

1. **`.aitask-scripts/lib/orphan_ref_store.py`** (new): git plumbing for a flat
   JSON store on an orphan ref:
   - building a tree through a temporary `GIT_INDEX_FILE` with
     `update-index --cacheinfo` and `write-tree`;
   - `commit-tree`;
   - CAS through a push, where a non-fast-forward rejection means retry;
   - CAS through `update-ref <ref> <new> <old>` in local-only mode;
   - a bounded, non-interactive fetch.

   It is reusable. Do not change `aitask_lock.sh` or `aitask_claim_id.sh`.
2. **`.aitask-scripts/lib/relations_store.py`** (new): the store itself.
   - The D1 layout (`schema_version`, `records/`, `obsolescence/`,
     `dismissals/`, `approvals/`).
   - The outbox under `<git-common-dir>/aitask-relations/outbox/`: write it
     first, flush everything in one commit, keep an `.err` sidecar per entry.
     - Every removal (published and superseded entries alike) is
       content-conditional, under one `flock` (`outbox.lock`) shared by
       producers and flushers. The lock is never held across network steps.
     - An entry rewritten during a flush always survives.
   - Reader refresh: one fetch per invocation, `fetched_at`, and the `STORE:`
     states `fresh`, `stale`, `unreachable` (never fetched successfully),
     `local_only` and `empty` (a fetch succeeded and there is no remote branch).
   - The state lines:
     - `RELATIONS_STATE:enabled|disabled|host_off`, where an absent key means
       disabled and `AIT_RELATIONS=0` means `host_off`;
     - `ANALYSIS:analysed:<n>(stage=..[,stale][,partial])|pending|failed|never|disabled|unknown(store_unreachable)`.
   - Digest normalization in one function: the body without framework
     sections; the plan without its YAML header and without the
     `## Final Implementation Notes` / `## Post-Review Changes` sections.
   - Freshness baseline:
     - the body is always compared current;
     - the plan is compared with the approval stamp's `plan_sha256` when the
       task has one, otherwise with its current digest.
   - Identity at read: a relation end whose recorded `created_at` differs from
     the live task's is a reused child id. It is dropped, and `gc` removes such
     records.
   - `gc` is the single-writer exception: it deletes files only for ids that
     exist nowhere.
   - The outbox overlay on every read.
   - Newest-wins by `(stage, at)`, with `SUPERSEDED` and `STALE_RUN` reports.
   - The local-only → remote upgrade (`UPGRADED:<n>`).
   - Forward ∪ reverse lookup (D3).
   - Folded-ref canonicalization at read.
   - Staleness computed at read (D11): `stale:source_changed|target_changed`.
3. **Schema and vocabulary module** (new): `lib/relations_schema.py` or part of
   the store.
   - The `aitask-relations/1` record, the obsolescence record, the dismissal and
     the approval stamp.
   - The closed vocabulary of six types with their direction rules.
   - Basis kinds, split into impact (`path` / `symbol` / `token`) and
     connectivity (`task_ref`).
   - The rule that `affects`, `coordinates_with` and `supersedes` need at
     least one impact basis.
   - Writers fail closed on anything unknown.
4. **`.aitask-scripts/aitask_relations.sh`** (new) with the store verbs: `show
   <id> [--json]`, `why <a> <b>`, `status` (store state, outbox entries with age
   and last error), `flush`, `gc`.
   - Every output starts with the state lines `RELATIONS_STATE:` / `STORE:` /
     `ANALYSIS:`.
   - `gc` resolves existence through `aitask_query_files.sh`, `old.tar.zst`
     bundles included.
   - The worker child adds the analysis verbs to this script.
5. **Dispatcher and permissions.** Add `ait relations` routing, and the helper
   whitelist touchpoints for a script invoked from skills
   (`aidocs/framework/aitasks_extension_points.md`).
6. **CLAUDE.md pointer.** Add one "Read `aidocs/framework/task_relations.md`
   when …" line.

## Key files

- New: `lib/orphan_ref_store.py`, `lib/relations_store.py`, the schema module,
  `aitask_relations.sh`, and tests.
- Changed: the `ait` dispatcher, the whitelist touchpoints, `CLAUDE.md`.

## Reference patterns

- `aitask_lock.sh`: `BRANCH=aitask-locks`, the plumbing write, push-as-CAS with
  5 retries.
- `aitask_claim_id.sh`: `has_remote`, the local-only branch via `update-ref`,
  and the auto-upgrade push when a remote appears.
- `lib/plan_paths.py`: `split_task_framework_sections`, used for body digests.
- `chatlink/relay.py`: atomic tmp + `os.replace` writes.
- Memory and conventions to apply:
  - bounded operations: a stop request plus read-back, and `GIT_TERMINAL_PROMPT=0`
    does not cover SSH prompts;
  - git path output read with `-z`;
  - every exit status checked (`PIPESTATUS`).

## Implementation plan

See `aiplans/p1981/p1981_1_relations_store_and_cli.md`.

## Verification

Self-contained tests under `tests/`, with scratch repositories and bare remotes,
never the real store. Cases:
- no remote (local-only);
- unreachable remote: the entry is retained, and `status` shows it;
- a CAS race between two writers;
- outbox retention and a targeted retry;
- the local-only → remote upgrade, both when the remote branch is absent and when
  it is present;
- newest-wins, with `SUPERSEDED` and `STALE_RUN`;
- the removal interleaving: a flusher judges an entry superseded (or published)
  while a producer rewrites the same path; the rewritten entry must survive;
- forward ∪ reverse lookup;
- staleness markers;
- `gc` with an archived, a bundled and a deleted id;
- the state lines for disabled / empty / stale / local-only.

Run `shellcheck` on the new script and `bash tests/run_all_python_tests.sh
--test-dir <dir>` for the Python tests.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-06T05:53:22Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-06T12:46:22Z status=pass attempt=1 type=human
