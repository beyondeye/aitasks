---
Task: t1981_1_relations_store_and_cli.md
Parent Task: aitasks/t1981_task_relations_and_obsolescence_design.md
Sibling Tasks: aitasks/t1981/t1981_2_relation_candidate_generator.md, aitasks/t1981/t1981_3_relations_worker_and_analysis.md, aitasks/t1981/t1981_4_relations_triggers.md, aitasks/t1981/t1981_5_relations_consumption.md, aitasks/t1981/t1981_6_obsolescence_layer.md, aitasks/t1981/t1981_7_relations_tui.md, aitasks/t1981/t1981_8_relations_website_docs.md, aitasks/t1981/t1981_9_port_relations_skill_changes.md, aitasks/t1981/t1981_10_relations_retrospective.md
Archived Sibling Plans: aiplans/archived/p1981/p1981_*_*.md
Base branch: main
Output branch: main
---

# t1981_1 — Relations store and CLI

## Context

First child of t1981. Builds the orphan-branch store for task relations
(`aidocs/framework/task_relations.md` D1, D2, D3, D11). No analysis, no
triggers, no skill changes. Every later child reads or writes through this
module.

## Steps

0. **Reality check.**
   - Re-read D1–D3 and D11 of the design doc.
   - Re-verify the precedents:
     - `aitask_lock.sh`: `BRANCH`, `MAX_RETRIES`, the plumbing write, push as
       CAS;
     - `aitask_claim_id.sh`: `has_remote`, the local-only `update-ref` branch,
       the auto-upgrade push;
     - `lib/plan_paths.py` `split_task_framework_sections`;
     - `aitask_query_files.sh`: how it resolves archived and bundled ids.
   - Check `git log` for any new orphan-branch helper that landed since
     2026-11-04.
1. **`lib/orphan_ref_store.py`** (new). A pure git-plumbing layer:
   - `fetch(ref, timeout)`: bounded and non-interactive. Pass
     `GIT_TERMINAL_PROMPT=0`, and give SSH `BatchMode` only when the user has no
     custom `core.sshCommand` (see the memory on bounded ops and SSH prompts).
     Returns ok, or a reason.
   - `read_tree(ref)` → `{path: blob_sha}` from `ls-tree -r -z` (NUL-separated),
     and `cat_blobs(shas)` through `cat-file --batch`.
   - `build_commit(base_commit, changes{path: bytes|None}, message)`: a temporary
     `GIT_INDEX_FILE`, `read-tree <base>`, `update-index --add --cacheinfo` per
     change, `write-tree`, `commit-tree [-p base]`.
   - `cas_push(commit, ref)`: push `<c>:refs/heads/<ref>`. A non-fast-forward
     rejection is a `CONFLICT` result, distinct from network or auth failure.
   - `cas_local(ref, new, old)`: `update-ref`.
   - Every subprocess's exit status is checked; no pipelines.
2. **Schema module** (new, `lib/relations_schema.py`):
   - JSON validators for the four record kinds of D2: the relations record, the
     obsolescence record, the dismissal, the approval stamp;
   - the six-type vocabulary, with a direction attribute (`directed` /
     `symmetric`);
   - the basis kinds, split into impact (`path` / `symbol` / `token`) and
     connectivity (`task_ref`);
   - the rule that `affects`, `coordinates_with` and `supersedes` need at least
     one impact basis;
   - canonical-ref parsing (`<project>#<id>`) that accepts the id shapes of
     t1635.

   Unknown fields or types fail validation.
3. **`lib/relations_store.py`** (new):
   - Paths: `<git-common-dir>/aitask-relations/{outbox/,fetched_at}`.
   - `write(path, record)`: validate, write the outbox entry atomically
     (tmp + fsync + `os.replace`), then `flush()`.
   - `flush()`, following the D1 algorithm:
     - remote mode: fetch, per-path newest-wins against the remote, one commit,
       `cas_push`, up to 8 attempts with jitter;
     - local-only mode: `cas_local`;
     - on failure, write an `.err` sidecar and return
       `RETAINED:<n>|<reason>`;
     - report `SUPERSEDED:<path>` and `STALE_RUN`.
   - **Outbox synchronization.**
     - `write()` and every removal take one `flock` on
       `<git-common-dir>/aitask-relations/outbox.lock`. It is held only for the
       file operations, never across fetch or push.
     - A flusher records each entry's content hash when it reads it.
     - Removal, for published and superseded entries alike, deletes an entry
       only if its current hash still equals the recorded one. A concurrent
       rewrite always survives.
   - The upgrade path from local-only to remote (`UPGRADED:<n>`).
   - `read()`:
     - fetch at most once per process unless `no_fetch` is set, and record
       `fetched_at`;
     - return the tree with the outbox overlay;
     - report `STORE:` as one of `fresh`, `stale:<reason>@<ts>`,
       `unreachable:<reason>` (never fetched successfully: no data), `local_only`
       or `empty` (a fetch succeeded and there is no remote branch).
   - `relations(task)` = forward ∪ reverse (D3), with folded refs canonicalized
     through `folded_into`.
   - `digests(task)`, the D2 normalization, in one function:
     - the body without framework sections;
     - the plan without its YAML header and without the `## Final
       Implementation Notes` / `## Post-Review Changes` sections.
   - `freshness(relation)` compares each end's record inputs with that task's
     **baseline**, and returns `fresh`, `stale:source_changed` or
     `stale:target_changed`.
     - Body: always the current normalized digest.
     - Plan: the latest approval stamp's `plan_sha256` if the task has one,
       otherwise the current normalized digest.
   - Identity: drop any relation end whose recorded `created_at` differs from
     the live task's (a reused child id). `gc` also removes a record whose
     `task_created_at` no longer matches.
4. **`aitask_relations.sh`** (new) and the `ait relations` dispatch: `show <id>
   [--json] [--no-fetch]`, `why <a> <b>`, `status`, `flush`, `gc [--dry-run]`.
   - Every output starts with three state lines:
     1. `RELATIONS_STATE:enabled|disabled|host_off`. Read `relations.enabled`;
        an absent key means `disabled`, and `AIT_RELATIONS=0` means `host_off`.
     2. `STORE:`.
     3. Per task, `ANALYSIS:`, with the D1 states:
        `analysed:<n>(stage=..[,stale][,partial])`, `pending(..)`, `failed(..)`,
        `never`, `disabled` or `unknown(store_unreachable)`. `pending` and
        `failed` read the local spool if t1981_3 has created it; otherwise
        those states are simply absent.
   - `gc` removes records, assessments, dismissals and stamps for ids that
     exist nowhere: not active, not archived, not in a bundle. It is the
     documented single-writer exception.
5. **Helper whitelist and permissions.** The five touchpoints in
   `aidocs/framework/aitasks_extension_points.md`.
6. **CLAUDE.md.** One pointer line: "Read `aidocs/framework/task_relations.md`
   when editing the relations store, worker, triggers or consumers".

## Verification

- `tests/test_relations_store.py`, against scratch repos plus bare remotes,
  covering:
  - local-only mode;
  - an unreachable remote: the entry is retained, `status` lists it, and the
    next `flush` publishes it;
  - a two-writer CAS race;
  - newest-wins with `SUPERSEDED` and `STALE_RUN`;
  - the removal interleaving: a flusher judges an entry superseded or published,
    and a producer rewrites that path before the removal. The new entry survives
    on both removal paths;
  - `unreachable` (never fetched) vs `stale` vs `empty`;
  - digest normalization: implementation notes appended to a plan do not change
    its digest;
  - the upgrade, both with the remote branch absent and present;
  - the outbox overlay;
  - forward ∪ reverse;
  - folded canonicalization;
  - freshness markers;
  - `gc` with an archived, a bundled and a deleted id.
- `tests/test_relations_cli.sh` for the state lines and the verbs, with the
  file-backed counters if subshells are used (CLAUDE.md, t1207).
- `shellcheck .aitask-scripts/aitask_relations.sh`.
- No test touches the real `aitask-relations` branch or `~/.aitask*`.

## Step 9

Post-implementation per task-workflow Step 9: the archival and lock release of
this child.
