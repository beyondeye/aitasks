# Task relations and backlog obsolescence

Decision record for t1981. It settles the design directions D1–D13 of the seed
proposal and fixes the design that the implementation tree (see
"Implementation tree" at the bottom) lands. The children treat this file as
their durable context anchor.

Read together with:

- `aidocs/framework/task_search_analysis.md`: the query layer underneath this
  design (task-id backlinks, path citations, cards, text search), owned by
  `aitasks_go#93` and t2192.
- `aidocs/framework/task_premise_staleness.md`: premise staleness ("needs
  refresh"), owned by t1663 / t1655. This design consumes its verdict and does
  not duplicate it.
- `aidocs/framework/task_note_mailbox.md`: the note mailbox that push
  notifications still go through.
- The seed proposal, attached to t1981:
  `ait attach get 1981 task_relations_proposal.md`. It holds the measurements
  and the reproducible scripts (Appendix A) this record cites as "seed §N".

## The problem

At the end of implementation, `task-workflow` Step 8e (and the matching offers
in `aitask-qa` and `aitask-review`) chooses note recipients by agent judgement
alone. `/aitask-note` with no target runs the Related Task Discovery Procedure,
which reads only titles, labels and about five body lines of each pending task.
No file surfaces, `depends`, trails or past note edges are used.

- **Doing it well costs the implementing session real context.** t1794 needed a
  whole child task (t1794_9) to grep 103 candidate files and send 63 notes.
- **Doing it broadly is a defect.** On 2026-10-14 the shared task-data branch
  held 373 note commits and 52 read-receipt commits (seed §2.1). Each one is a
  push race on the hottest files. Over-notification is not a safe default.
- **Nothing identifies obsolete backlog tasks**: tasks whose goal was met
  elsewhere, whose direction was superseded, whose origin was reverted, or whose
  target code is gone. Premise staleness explicitly leaves "is this still worth
  doing?" out of scope.

## Premises

These were decided before the design work and are not reopened here.

1. **Precision over recall.** Notify only tasks with real connections. In
   doubt, exclude.
2. **A task-relations store**, conceptually an extension of task metadata,
   **stored separately from the task files**: never in frontmatter or body.
3. **Written by background agents** when a task is created and when its plan is
   approved, never by the implementing session.
4. **Static analysis first.** Background agents build candidates from metadata,
   task cross-references, labels and file citations, then analyse them and
   record only confirmed relations, each with a description.
5. **The end of implementation reads the store** for the notify list.
6. **Obsolescence is a second layer on the same infrastructure**, with its own
   search logic and an obsolete score with reasons. **Never auto-actioned.**
7. **A TUI comes later.** Code agents are the first consumers.
8. **Rejected as the primary mechanism:** a purely static, in-session analyzer
   run at the end of each task. It stays as the candidate generator.

Constraints carried over from the project conventions:

- Helpers report source-tagged evidence and the agent judges. There are no
  classifier tables and no relevance thresholds.
- Heuristic evidence stays advisory. A relation or a score never changes a
  task's status, requirements or authority.
- Derived records carry the content hashes of every input they consumed, never
  stat freshness.
- New write paths honour a shared opt-out and have bounded recovery: stop,
  report the actual state, retry the specific item.

## Layers and ownership

| Layer | What | Owner |
|---|---|---|
| L1 | Query: cards, task-id mentions, path citations, BM25 search | `aitasks_go#93` (Go engine) + t2192 (framework shim with a Python fallback) |
| L2 | Backlinks: the reverse of mentions and citations | same |
| L3 | **Confirmed, typed relations**, written in the background, and their consumption | this design |
| L4 | **Obsolescence assessments** on the same infrastructure | this design |

Premise staleness ("does the premise still hold?") is a neighbouring axis owned
by t1663. Its verdict is one evidence row for L4.

## Measurements this design rests on

All from the seed proposal unless stated. They describe one corpus at one date
and are not general claims.

| Measurement | Value | Source |
|---|---|---|
| Replay of 13 real senders (143 notes): task-id cross-references, both directions, **task bodies only** | 86% recall at ~23 candidates per sender (~41% precision) | seed §2.3 |
| Same, file overlap | 95% recall at ~290 candidates per sender | seed §2.3 |
| Same, labels / metadata edges alone | 24% / 26% recall | seed §2.3 |
| Reading plans as well | 97% recall, **contaminated**: a sender's archived plan is written after its notes and often lists the recipients | seed §2.3 |
| Analysis triggers | ~12 per day (234 tasks and 129 plans in 30 days) | seed §2.4 |
| Estimated cost of one analysis | 30–50k input tokens at ~25 candidates | seed §2.4 (estimate, not measured) |
| Pending tasks citing a path missing at HEAD | 184 of 577; only 3 cite a truly deleted path | seed §2.7 |
| Python scan of active tasks + plans | 0.44–0.73 s; archive 1.2–1.6 s | `task_search_analysis.md` |

Two misses that no static signal reached: a review finding about another task's
uncommitted in-flight work, and a consumer of a verdict vocabulary with no shared
path (seed §2.3).

## D1 — Store: the orphan branch `aitask-relations`

**Decision.** Relations live on a dedicated orphan branch, `aitask-relations`,
written with git plumbing and a compare-and-swap push.

**Why.** The alternatives each break something:
- **A directory on the task-data branch.** `aitask_task_commit.sh` refuses
  every path outside `aitasks/` and `aiplans/` (`REFUSED:out_of_scope`). The
  auto-merge resolver (`lib/task_automerge.sh`) and the `ait sync` sweep see
  only `aitasks/*.md` and `aiplans/*.md`. In legacy mode the directory would
  land on the code branch.
- **The artifact store.** `ait artifact create` always records an `artifacts:`
  entry in the owning task's frontmatter, which premise 2 rules out.

An orphan branch never touches the data-branch index, auto-merge or the sync
sweep. It behaves the same in branch mode and legacy mode, and the write pattern
(bursty background writers, a few per day) is what CAS on a separate ref
absorbs.

### Layout

```
schema_version               "1"
records/t<id>.json           the relations record of task <id> (one per task)
obsolescence/t<id>.json      the obsolescence assessment of task <id>
dismissals/t<id>.json        a human dismissal of that assessment
approvals/t<id>.json         the latest plan-approval stamp of <id> (D8)
```

Child tasks use `t<parent>_<child>.json`. Every file has exactly one writer:

| Files | Writer |
|---|---|
| `records/`, `obsolescence/` | the background worker |
| `approvals/` | the task's own approving session (a fact record, not a relation; see D2) |
| `dismissals/` | the human, through `ait obsolete dismiss` |

The one exception is `ait relations gc` (D11). It deletes only files whose task
is gone, in either of two ways:
- the id exists nowhere (not active, not archived, not in a bundle);
- the id was reused by a new task, whose `created_at` differs from the file's
  `task_created_at` (D2 identity).

In both cases the writer of those files no longer exists.

### Module

The store is a new `lib/relations_store.py`, on top of a small, reusable
`lib/orphan_ref_store.py`. That module does the git plumbing:
1. build a tree through a temporary `GIT_INDEX_FILE` with `update-index
   --cacheinfo` and `write-tree`;
2. `commit-tree`;
3. CAS through a push, or through `update-ref`.

The existing orphan-branch scripts, `aitask_lock.sh` (`aitask-locks`, 5 retries,
no offline fallback) and `aitask_claim_id.sh` (`aitask-ids`, with a local-only
fallback), build a **flat** tree inline with `hash-object`, `mktree` and
`commit-tree`. The relations layout has subdirectories, which is why the module
goes through a temporary index instead.

Those two scripts stay untouched. Whether they adopt the shared module is a
question for the retrospective.

### Store API

The contract the worker (t1981_3), the consumers (t1981_5) and the
obsolescence layer build on. Module: `lib/relations_store.py`, class `Store`
(one instance per invocation; it fetches at most once, and every `read()`
recomputes the local view, so writes made since are always visible).

- **Project identity.** `Store(repo)` takes the local project's logical name
  from `project.name` in `project_config.yaml`, which `ait setup` seeds. That
  is the same source the trails use. A missing or invalid name raises
  `ProjectUnresolved`; the CLI prints `PROJECT_UNRESOLVED` and exits 1. No name
  is ever assumed, because records written under a guessed name would not match
  the other clones' records.
- **Refs.** A bare id is qualified with the local name. A `<project>#<id>` ref
  keeps its own project and is parsed by the shared
  `cross_repo_notation.parse_ref` (grammar `[a-z0-9_-]+`, as for `ait note`).
- **Another project's end** is shown with its qualification. It is never
  canonicalized through the local index. Its freshness is
  `unverified:target_baseline`, and `ANALYSIS:` for it is
  `unknown(other_project)`. A record whose own task belongs to another project
  is refused at write (`PROJECT_MISMATCH:`) and reported at read (`CORRUPT:`).
- **Validation on read.** Every blob is schema-validated before it is
  consumed, compared or rendered. An invalid one is reported as
  `CORRUPT:<path>|<reason>`, always loses to a valid record, and is never
  deletion-eligible.

| Function | Contract |
|---|---|
| `write(path, record, flush=True)` | Validates first (nothing is written on `SchemaError`). Refuses `IDENTITY_MISMATCH:<path>` when the record's `task_created_at` is not the live task's. Refuses `STALE_RUN:<path>` when the visible version wins under `wins()`. Otherwise writes the outbox entry atomically (`OUTBOX:<path>`), then flushes unless `flush=False`, which is the stamp's synchronous-write mode |
| `flush()` | Publishes every outbox entry in one commit. Reports `PUBLISHED:<n>`, `SUPERSEDED:<path>`, `UPGRADED:<n>`, `UPGRADE_INCOMPLETE:`, `RETAINED:<n>\|<reason>` or `NOTHING_TO_FLUSH` |
| `read(no_fetch=False)` | A `Snapshot` (`state`, `base`, `files`, `pending`, `corrupt`). `state` is the `STORE:` value |
| `relations(task, snap)` | forward ∪ reverse (D3), folded ends canonicalized, identity-checked, each `Rel` carrying `direction`, `freshness` and `pending_push` |
| `freshness(rel, record, snap)` | `fresh`, `stale:source_changed`, `stale:target_changed`, `unverified:source_baseline` or `unverified:target_baseline` (D11) |
| `analysis_line(task, snap)` | the `ANALYSIS:` value (D1) |
| `relations_state()` | `enabled`, `disabled` or `host_off` |
| `gc(dry_run=False)` | `GC_REMOVED:<path>\|task_gone\|identity_mismatch`, `GC_KEPT:<path>\|revalidated`, `GC_NONE` or `GC_REFUSED:<reason>` |
| `relations_store.job_state(task, state_dir)` | the spool hook for `pending(settling\|queued\|running\|capped)` / `failed(<reason>)`, read from this clone's spool (`relations_spool`, "Worker API"); None when the task has no job |
| `relations_schema.digests(task_text, plan_text)` | the one D2 normalization |
| `relations_schema.wins(kind, new, old, live_created_at)` | the one comparison: identity first, then `(stage, at)` |

`aitask_relations.sh` (`ait relations`) exposes `show`, `why`, `status`,
`flush` and `gc`. Its exit status is 3 for `RETAINED:` or `GC_REFUSED:`.

### Modes

- **Remote mode:** the repository has the remote that `aitask-locks` uses.
- **Local-only mode:** no remote is configured. This is the `aitask-ids`
  precedent: the store is the local branch `refs/heads/aitask-relations`.

### Refs

- **`refs/heads/aitask-relations` (L) is the clone's durable, latest-known
  store in both modes.**
  - It only moves forward:
    - local-only writes commit on top of it;
    - in remote mode every remote commit, fetched or just pushed, enters it
      through `integrate()`, which fast-forwards or makes a local *absorb*
      merge `(remote, L)`.
  - So L holds every record the clone observed or published, plus its
    unpublished work.
  - It survives a failed fetch, `--no-fetch` and `git remote remove`, which
    deletes `refs/remotes/origin/*`. That is why the remote-tracking ref is
    never read or written.
- **`refs/aitask-relations/observed`** is advisory only: the last remote tip
  seen, used to mark `pending_push`.
- **Fetches land in a private temporary ref.** Each operation works on the
  immutable commit ids it resolved. L is resolved *before* the remote tip is
  pinned, so an L that came from the remote is always an ancestor of the pin.
  "Local work pending" is then exactly "L is not an ancestor of the remote
  tip".
- **Every push is leased** (`--force-with-lease=refs/heads/aitask-relations:<base>`,
  with an empty base when the branch must not exist). A remote that moved since
  the pin is a conflict, whatever the new commit's other parents contain.
- **Merges are three-way** over `merge-base --all`. Unrelated histories count
  as one synthetic empty base. Every path goes through one total rule:

  | Case | Result |
  |---|---|
  | both sides agree | that value |
  | local untouched (equal to every base) | remote, so a remote deletion is never resurrected |
  | remote untouched, local present | local |
  | remote untouched, local deleted | deleted only if the record is still deletion-eligible |
  | both changed, both present | `wins()` |
  | remote deleted, local changed | local only if it matches the live identity |
  | local deleted, remote changed | deleted only if the remote record is itself deletion-eligible |

  *Deletion-eligible* is gc's rule: the id exists nowhere, or the record's
  `task_created_at` differs from the live task's.

### Reader refresh

- **One fetch per reader invocation, at most.** It is an `ls-remote` probe
  (a fetch of an absent branch fails, so the probe is what tells "absent" from
  "unreachable"), then, when the branch is present, a fetch into a private
  temporary ref. Both are bounded by a timeout (`AIT_RELATIONS_FETCH_TIMEOUT`,
  default 20 s) and non-interactive through `lib/bounded_run.py`: they must not
  wait on a credential or SSH prompt. `--no-fetch` exists for tests and for a
  second read within the same workflow step.
- **After a successful fetch**, the reader integrates the fetched commit into
  the local branch (see "Refs"), stores the time in
  `<git-common-dir>/aitask-relations/fetched_at` and reports
  `STORE:fresh@<ts>`.
- **After a failed fetch**, the reader falls back to the local branch, the
  latest known store, and reports `STORE:stale:<reason>@<last fetched_at>`.
  That is `@never` when the clone has never fetched but holds local-only data.
  With no local branch at all there is no data, and it reports
  `STORE:unreachable:<reason>`.
- **`STORE:empty`** means a fetch **succeeded**, the remote has no
  `aitask-relations` branch, and this clone holds nothing either: nothing has
  ever been written. It is never used for a fetch that failed.
- **In local-only mode**, the reader reads the local branch and reports
  `STORE:local_only`.
- **Every read overlays the outbox** (below). Records this clone has written but
  not yet published win per path under the newest-wins rule, and are marked
  `pending_push`.
- **State lines.** Every reader output starts with three lines. Together they
  keep an empty or unreachable store from ever being presented as "no related
  tasks".
  1. `RELATIONS_STATE:enabled|disabled|host_off`. `host_off` means the project
     has analysis enabled but this host has `AIT_RELATIONS=0`. This host runs no
     analysis, and it still reads the store.
  2. `STORE:…`.
  3. Per task, `ANALYSIS:` with one of:
     - `analysed:<n>(stage=<1|2>[,stale][,partial])`;
     - `pending(<settling|queued|running|capped>)`;
     - `failed(<reason>)`;
     - `never`;
     - `disabled`;
     - `unknown(store_unreachable)`.

  This is a description of what the store holds. Step 8e's stricter verdict,
  `analysis-state`, is derived from the same facts and defined in D8.

The git common dir is per clone and shared by its worktrees, so the outbox, the
spool and `fetched_at` are the same for the primary checkout and for every
`aiwork/` worktree.

### Writes are retained for retry (outbox first)

1. **Validate before any mutation.** The record is checked against the schema
   and the closed vocabulary (D2). An invalid record fails the job, and nothing
   is written.
2. **Write the outbox entry** atomically:
   `<git-common-dir>/aitask-relations/outbox/<path>.json` (temporary file, fsync,
   `os.replace`). The outbox entry is the durable intent.
3. **Publish.** Every publish flushes **all** outbox entries in one commit.
   - **Remote mode:**
     1. Resolve the local branch, then probe and fetch the remote tip.
     2. Integrate the remote tip into the local branch (see "Refs").
     3. For each path, apply newest-wins against the integrated version. An
        entry that loses is reported `SUPERSEDED:<path>`. It is removed by the
        conditional removal below.
     4. Build the commit on the local branch, which now contains the remote
        tip.
     5. Push, leased on the pinned tip. A conflict retries from step 1, up to 8
        attempts with jitter.
     6. Integrate the pushed commit into the local branch.
   - **Local-only mode:** the same flush, committed on the local branch with
     `update-ref refs/heads/aitask-relations <new> <old>` as the CAS.
   - **Clearing.** The published and superseded entries are removed by the
     conditional removal below, and **only after** the local branch provably
     contains their result. When integrating the pushed or fetched commit
     fails, they stay (`RETAINED:<n>|integrate_failed`). The next flush finds
     them already published, builds no commit, and clears them.
   - **Every outbox removal is content-conditional and synchronized.**
     - Producers (entry writes) and flushers (removals of superseded and
       published entries) take one shared local lock:
       `<git-common-dir>/aitask-relations/outbox.lock`, an `flock`.
     - The lock is held only for the outbox file operations, never across the
       network steps.
     - A flusher records each entry's content hash when it reads it. Under the
       lock, it deletes an entry only if its current hash still equals the one
       recorded. An entry rewritten meanwhile, by a worker, an approval stamp
       or another flush, always survives, on every removal path.
4. **On failure** (network, authentication, retries exhausted):
   - The entries stay in the outbox, with the last error in a sidecar
     `<path>.err`. The writer reports `RETAINED:<n>|<reason>` and never drops a
     record silently.
   - The retry is targeted: the next write, `ait relations flush`, or the next
     worker start publishes the outbox first.
   - `ait relations status` lists every retained entry with its age and its
     last error.
5. **Upgrade from local-only.** Unpublished local work is any commit on the
   local branch that is not on the remote. That covers a local-only history,
   local commits made while the remote was unreachable, and a local descendant
   of the remote tip whose outbox has already drained.
   - If the remote branch does not exist, push the local branch as it is,
     leased on its absence (the `aitask-ids` precedent).
   - Otherwise, integrate the remote tip first: a three-way absorb merge,
     whose merge base keeps deletions made on either side since. Then push the
     local branch, which now descends from the remote tip.
   - Either way report `UPGRADED:<n>`. After it, the local tip is an ancestor
     of every later remote tip, so nothing is replayed twice.
6. **Newest-wins, identity first** (`relations_schema.wins`).
   - When one side's `task_created_at` is the live task's and the other's is
     not, the live incarnation wins, whatever the stage or time. A deleted
     child's record never outranks the record of the task that reuses its id.
   - Otherwise a record replaces an existing one only if its `(stage, at)` is
     greater or equal.
   - The stage is decided by **which inputs the run analysed**, never by the
     trigger:
     - **Stage 2:** the run analysed the task's **current** body together with
       its **approved** plan, the plan as of its latest approval stamp's
       `data_commit` (D2). Every run on a task that has a stamp is stage 2:
       `plan_approved`, sweep, manual, fold and `analyze --now` alike.
     - **Stage 1:** the run analysed the working tree of a task with no stamp.
   - So every stage-2 record describes the approved plan. A later working-tree
     run can never displace one.
   - The body is always read current, which is why a fold into an approved task
     is still re-analysed (D4). Plan edits made during implementation, such as
     progress marks, are never read, because the plan comes from the stamp.
   - A job that lost the race to a higher-stage or newer record is reported
     `STALE_RUN`.

### History

About one commit per analysed task, roughly 15–25 a day at the measured trigger
rate. A `compact` verb is deferred. Its trigger is a measured median fetch of
the relations branch above 2 s on a developer host; the retrospective measures
it (D13).

## D2 — Record schema and vocabulary

### The relations record

`records/t<id>.json`, schema `aitask-relations/1`:

```json
{
  "schema": "aitask-relations/1",
  "task": "aitasks#1981",
  "analysed": true,
  "run": {
    "id": "<uuid>",
    "trigger": "created|plan_approved|fold|sweep|manual",
    "stage": 2,
    "at": "<ISO 8601>",
    "host": "<hostname>",
    "agent_string": "claudecode/sonnet5_5",
    "code_base": "<code sha>",
    "data_base": "<task-data sha>",
    "candidate_provider": "<t2192's indication of the answering path, e.g. engine|fallback>"
  },
  "inputs": {
    "source": {"body_sha256": "…", "plan_sha256": "…"},
    "candidates": [
      {"ref": "aitasks#1663_4", "body_sha256": "…", "plan_sha256": null}
    ]
  },
  "considered": [
    {"ref": "aitasks#1663_4", "outcome": "related", "sources": ["mention_in", "cites"]}
  ],
  "relations": [
    {
      "from": "aitasks#1981",
      "to": "aitasks#1663_4",
      "type": "coordinates_with",
      "description": "<at most 600 characters, written for the other task's agent>",
      "basis": [
        {"kind": "path", "value": ".claude/skills/task-workflow/SKILL.md"},
        {"kind": "token", "value": "Check 6"}
      ],
      "evidence": [{"source": "mention_in", "detail": "t1663_4 body, line 14"}]
    }
  ],
  "usage": {"input_tokens": 0, "output_tokens": 0, "cost_usd": null, "wall_s": 0}
}
```

- **Refs** are canonical `<project>#<id>` from the start (D12).
- **Identity.** The record carries `task_created_at` (the task's `created_at`
  frontmatter), and every `inputs.candidates[]` entry carries its candidate's
  `created_at`. **Every kind carries `task_created_at`**: the obsolescence
  record, the dismissal and the approval stamp too, so newest-wins and gc can
  tell incarnations apart on every path.
  - Child numbers are allocated as the highest existing child number plus one
    (`get_next_child_number` in `aitask_create.sh`). Deleting the
    highest-numbered child therefore frees its number for reuse.
  - The `(id, created_at)` pair is what tells a reused id from the original
    (D11).
  - `created_at` has minute resolution, so a child deleted and recreated within
    the same minute keeps the pair. That case is accepted: the new body's digest
    differs, so its relations read `stale:target_changed`.
- **Every candidate has an entry.** Each candidate passed to the agent, those
  listed only under `TRUNCATED:` included, gets an `inputs.candidates[]` entry
  with its `created_at` and digests. The agent may record relations only to
  tasks that have an entry, so every relation end can be identity-checked and
  freshness-checked.
- **Digests.** Both are content hashes, never stat freshness.
  - `body_sha256` covers the task description only. The framework sections
    (`## Inbox`, `## Gate Runs`, folded history) are excluded through
    `plan_paths.split_task_framework_sections`.
  - `plan_sha256` covers the plan file **without** its YAML metadata header,
    which the externalize and verify helpers rewrite, and **without** the
    sections the workflow appends after approval (`## Final Implementation
    Notes`, `## Post-Review Changes`).
  - The normalization lives in one function of the schema module, used by every
    writer and every reader.
- **Single writer.** One end of every relation is the record's own task. `from`
  and `to` give the direction explicitly.
- **No confidence number.** Only included relations are recorded. Precision
  comes from the inclusion test (D7), not from a threshold on a score.
- **Screening record.** `considered[]` keeps every candidate the agent screened,
  with its outcome (`related`, `unrelated` or `unreadable`). The `unrelated`
  entries let a sweep skip a candidate whose digest is unchanged while the
  source's is unchanged too. All entries give D13 the data to measure screening.
- **Screening identity.** `inputs.screening_sha256` (optional) is the digest of
  the provider's screening inputs: the provider path, coverage, cards, evidence
  and truncation. `UP_TO_DATE` requires it to be equal, so changed evidence is
  re-analysed even when every digest is unchanged ("Worker API").
- **Schema compatibility.** The validators are closed: an unknown key makes a
  record `CORRUPT` for every reader that does not know it. So after the first
  release that carries a schema, any new field needs a schema-version bump,
  with readers that accept both versions shipped one release before any writer
  emits the new one.
  - `inputs.screening_sha256` is part of `aitask-relations/1` from its **first
    release**. The t1981_1 store (f78e2b8d5) was unreleased when t1981_3
    extended it, and t1981_3 ships the only record writer together with the
    extended reader, so no deployed reader can meet the key.
  - `tests/test_relations_store.py` pins the boundary: the f78e2b8d5 reader
    rejects the key, and the current one accepts records with and without it.
- **Coverage.** When the candidate provider answered only part of the sources
  (D6), the record carries `coverage.missing_sources`, and readers report it as
  `partial`.

### Vocabulary

The vocabulary is closed. Writers fail closed on an unknown type, and a new type
needs a schema version bump. It reuses the trail relation names where they fit.

| Type | Direction | Meaning | Consumed by |
|---|---|---|---|
| `affects` | from → to | when `from` lands, `to`'s premise, plan or surface changes | pull, push, D9 |
| `advisory_precedes` | from → to | `from` should land before `to` (advisory; never a `depends` edge) | pull, trails |
| `coordinates_with` | symmetric | both change the same surface or the same decision | pull, push |
| `duplicates` | symmetric | the same goal | pull, D9, t1634 fold candidates |
| `supersedes` | from → to | `from`'s direction replaces `to`'s goal | pull, D9 |
| `informs` | from → to | useful context; nothing to do differently | pull only, never pushed |

`hard_depends` and `verifies` are **not** recorded. They are metadata facts that
consumers read from frontmatter, and the store does not duplicate them.

### Basis kinds

A basis anchor makes a relation mechanically checkable later.

- **Impact bases** can be confirmed against a diff:
  - `path`: a full repository-relative path. A bare basename or a
    script-relative path is never stored. The agent resolves it first, with its
    Glob tool or with the shim's `cites` suffix resolution. `plan_paths`'
    `find_suffix_references` only finds references and does not canonicalize;
    it needs at least two path components and can match several modules.
  - `symbol`: a function, variable or other code identifier;
  - `token`: a vocabulary token, such as a verdict name or a status string.
- **Connectivity basis:** `task_ref`, a mention of a task id. It keeps a
  relation findable and supports staleness checks, but **never confirms
  impact** (D8).
- `affects`, `coordinates_with` and `supersedes` require at least one impact
  basis.

### The obsolescence record

`obsolescence/t<id>.json`:
- `task`, `task_created_at`;
- `run`, and `inputs`: the source digests plus an `evidence_digest` over the
  evidence rows;
- `evidence[]`: `{id, kind, detail, source}`;
- `band`: `none|low|medium|high`;
- `reasons[]`: `{text, evidence_ids[]}`;
- `disposition`: `keep|refresh|fold_into|drop`, plus `fold_target` when it
  applies.

### The dismissal

`dismissals/t<id>.json`: `{task, task_created_at, at, by, evidence_digest,
note}`. It is written by a human through `ait obsolete dismiss`.

### The approval stamp

`approvals/t<id>.json`: `{task, task_created_at, approved_at, data_commit,
body_sha256, plan_sha256}`. `approved_at` is UTC ISO 8601.

- **When it is written.** At every plan approval that keeps the plan approved
  (D4), whenever the project has analysis enabled.
  - It is written by `ait relations stamp <id>`, called **synchronously** at the
    approval.
  - `data_commit` is the task-data `HEAD`, which holds the plan as Step 6
    committed it. The digests are computed from that commit, never from the
    working copy.
  - The stamp is written into the local outbox (D1) **before** the command
    returns. Only the network publish and the analysis enqueue are detached.
  - The command prints one line, `STAMP:<plan_sha256>`, or `STAMP:disabled`.
    That is the approval's identity, which Step 8e checks (D8).
  - The per-trigger switches and `AIT_RELATIONS=0` do not suppress the stamp:
    they stop analysis jobs, and the stamp costs no tokens. A re-approval
    replaces it.
- **What it is used for.** Its `data_commit` defines the approved plan of the
  stage-2 inputs (D1). Its `plan_sha256` is the plan's freshness baseline (D11)
  and the identity Step 8e's completeness verdict checks (D8). Its `body_sha256`
  records the body as approved, for audit; the body is always compared current.
- **Premise 3.** The stamp is written by the approving session, which in
  task-workflow is also the implementing session. That stays inside premise 3:
  the stamp is a fact record of the approval (like a gate-ledger entry), not a
  relation. No relation is ever written by the implementing session.

## D3 — Single writer, reverse lookup

- Only the analysis of task X writes `records/tX.json`. No agent writes another
  task's record.
- **The query is `relations(X) = forward(X) ∪ reverse(X)`.**
  - forward(X): the relations in X's own record.
  - reverse(X): every relation in another record that names X.

  It is answered by one `ls-tree` and one `cat-file --batch` over the branch
  tree, with the outbox overlaid.
- **Consequence:** a task created *after* X's plan was approved is still found at
  X's end of implementation, through the newer task's record.
- Folded refs are canonicalized to the primary (`folded_into`) when read.
- **No reverse index in v1.** If measured reads exceed 500 ms, the next step is a
  derived cache keyed on the branch tip's tree SHA. That key is exact, and the
  cache is never the authority.

## D4 — Triggers

Job triggers go through one helper,
`aitask_relations_enqueue.sh <op> <trigger> <task_id>`:
- **Contract.** It always exits 0 and never writes to stdout, so `--silent`
  callers keep their single-line output contract.
- **Detached.** It does its work in a detached part and never blocks the
  caller.
- **Failures are retained, not hidden.** A failure goes to the spool log, and
  any unpublished write stays in the outbox (D1). `ait relations status` shows
  it.
- **Switches.** It checks `relations.enabled`, then the per-trigger switch and
  `AIT_RELATIONS=0`, before enqueueing a job.

**Plan approval is the one exception:** it calls `ait relations stamp <id>`
instead (D2). That command:
- writes the approval stamp into the local outbox **synchronously**, before it
  returns;
- prints `STAMP:<plan_sha256>` (or `STAMP:disabled`) for the workflow to keep
  as the expected identity (D8);
- then detaches the stamp's network publish and the `plan_approved` enqueue,
  with the same retained-failure behaviour as the helper.

On the approving host the outbox overlay makes an unpublished stamp visible
(`pending_push`). On other hosts its absence reads as `incomplete:unverifiable`
(D8), never as complete. The stamp depends on `relations.enabled` only (D2).

| Trigger | Site | Op |
|---|---|---|
| `created` | `aitask_create.sh`: one call after `run_auto_merge_if_needed` at each of the four commit sites (`finalize_draft` child and parent, `run_batch_mode --commit` child and parent), after the child lock is released | relations |
| `plan_approved` | task-workflow Step 7, after the plan-approved gate block and **outside** its `profile.record_gates` guard; and `plan-approved-stop.md` **only for the stop reasons that keep the plan approved** (`deferred`, `resource_admission`, the rows that stamp `plan_approved_at`). The `drift`, `drift_check_failed` and `parallel_admission` stops invalidate the plan and fire nothing. Both sites call `ait relations stamp <id>`, which writes `approvals/t<id>.json` and enqueues the job. Step 7 keeps the printed digest as `relations_expected_plan`; Re-entry Routing's `IMPLEMENT` route sets it from `ait relations plan-digest <id>` | relations, on the stamp's snapshot |
| `fold` | the end of the fold sequence (`aitask_fold_content.sh` → `aitask_update.sh --desc-file` → `aitask_fold_mark.sh`). The call goes at the end of `aitask_fold_mark.sh`, by which point the primary's body has already been rewritten, in every `--commit-mode`, including `none`, where the caller commits later; the settle window absorbs that | relations, for the primary |
| `landed` | `aitask_archive.sh` `main`, after the archive commit, **only for completed work**: an archive with status Done and no `archived_reason`. Archives `--superseded`, archives `--obsolete` and folded tasks did not land anything, and fire nothing | obsolescence, for the pending tasks in relations(landed) and the tasks whose origin is the landed task |
| sweep / manual | `ait relations sweep [--budget N] [--stale] [--unanalysed]`, `ait relations analyze <id>`, `ait obsolete sweep` | either |

- **Settle window** (default 120 s after the last enqueue for that task). It
  covers decomposition bursts, where children are created one at a time and
  each child's body is final only after its creation commit. It also debounces
  repeated triggers in general.

  The manual-verification seeder and the archive carry-over do seed a body in a
  later commit, but they create `manual_verification` tasks, which are excluded
  below. The issue-import amend touches frontmatter only, which the body digest
  excludes.
- **Coalescing.** There is one spool file per `(op, task)`. A later trigger keeps
  the higher stage.
- **Exclusion.** `issue_type: manual_verification` tasks are not analysed. Their
  relations are `verifies` facts.
- **No re-analysis on plan edits.** Approval is the moment. Edits after it show
  up as staleness (D11). Revisiting that is a retrospective question.
- **No relations re-analysis at landing.** Step 8e re-validates every relation
  against the landed change mechanically (D8), and pull reads the landed task's
  archived plan. A landing therefore triggers obsolescence only.
- **Sweeps.** There is no built-in scheduler in v1. The sweep verbs are run by
  the user, by hand or from their own cron. Their default budget is what remains
  of the host's daily cap.
- **Outside task-workflow.** `aitask-pickrem` and `aitask-pickweb` approve plans
  through their own path and have no Step 8e. In v1 their tasks get creation
  records only, plus whatever a sweep adds. `aitask-pickweb` forbids
  cross-branch operations, so it never writes the store. Extending them is a
  retrospective question.
- **Neighbour.** t1663_3 also edits the `aitask_create.sh` batch path. The
  trigger child plans against it if it has landed.

## D5 — Execution, off by default

### Configuration

`aitasks/metadata/project_config.yaml`:

```yaml
relations:
  enabled: true            # written by `ait relations enable` / the setup question
  max_jobs_per_day: 40
  job_timeout_s: 600
  settle_s: 120
  candidate_cap: 25
  triggers: {created: true, plan_approved: true, fold: true, landed: true}
```

- **Off by default.** Background analysis spends tokens on every creation and
  plan approval, through headless Claude print mode, which bills at a higher
  rate (`aitask_codeagent.sh`). That spend is opt-in.
- **An absent key means disabled.** The seed `project_config.yaml` does **not**
  carry `relations.enabled`, so the setup question below can tell "never asked"
  from "answered".
- `ait relations enable|disable` writes the key through
  `aitask_metadata_commit.sh`.
- `AIT_RELATIONS=0` is a per-host kill switch for analysis jobs. Readers report
  it as `RELATIONS_STATE:host_off`.

### Activation is visible

- **At setup.** `ait setup` always prints `RELATIONS:disabled` or
  `RELATIONS:enabled(<agent>, cap <N>/day)`, following the `TESTMAP:<state>`
  precedent (`report_testmap_state` in `aitask_setup.sh`), with the enable hint
  and a one-line cost note.
  - Interactive setup asks once, defaulting to No, when `relations.enabled` is
    absent. It writes the answer, `true` or `false`, so it never asks again.
  - Batch setup never asks, and leaves the key absent.
- **Everywhere it is consumed.** The pick-time check, Step 8e, `/aitask-note`
  and `ait relations show` all say "relations analysis is disabled in this
  project — no relation data", never "no related tasks". "Not analysed yet
  (queued, failed or never)" is likewise distinct from "analysed, 0 relations".

### Spool and worker

- **Spool.** `<git-common-dir>/aitask-relations/spool/`, written atomically
  (temporary file, `os.replace`).
- **One worker per clone.** `lib/relations_worker.py` is guarded by a
  non-blocking `flock` on `worker.lock`. The enqueue helper starts it detached
  (`start_new_session`) when the lock is free. It exits when the spool is
  empty; there is no idle daemon.
- **Inputs.** The body is always read current from the task-data working tree.
  The plan is read from the stamp's `data_commit` when the task has an approval
  stamp, and from the working tree otherwise. This fixes the record's stage
  (D1), and makes a stage-2 record's plan digest equal the stamp's.
  - **Candidates follow the same rule**: a stamped candidate contributes its
    current body and its stamp's plan.
  - The candidate digests in `inputs.candidates[]` are computed that way, so
    progress marks in a target's plan never make it look changed.
- **Per job:**
  1. Wait out the settle window. Check the daily cap.
  2. Generate candidates (D6). This is static and cheap.
  3. If the candidate provider failed, or a core source (mentions, cites) is
     missing, **fail the job** (`CANDIDATES_UNAVAILABLE` / `PROVIDER_ERROR`).
     The worker never writes an analysed record from failed candidate
     generation. This check comes before `UP_TO_DATE`, so a failure can never
     be mistaken for "nothing changed".
  4. Compute the input digests (source and candidates). If the store already
     holds a record with identical digests at the same or a higher stage, report
     `UP_TO_DATE` and skip. This is also what limits double work across hosts.
  5. With full core coverage and zero candidates, write an analysed record with
     `relations: []` and make **no LLM call**.
  6. Otherwise run the headless op under a timeout that kills the whole process
     group. With a non-core source missing, the record carries
     `coverage.missing_sources` (D2).
  7. Parse and validate the output, then write it through the store (D1).
- **Completion** is judged from the validated output only, never from pane state
  or banner text.
- **Failure** moves the job to `failed/` with its reason. A timeout is retried
  once; other failures are not.
- **`ait relations analyze <id> --now --wait <s>`** moves a task's job to the
  front, skips the settle window and waits for the record with a bound. Step 8e
  uses it (D8).
  - It counts against the daily cap.
  - When the cap is already reached, it refuses with `CAP_REACHED` unless
    `--over-cap` is passed. Step 8e passes it only after the user explicitly
    confirms, and the over-cap run is logged.
- **No designated host.**
  - Every clone with analysis enabled runs its own worker for the triggers that
    fire on it, because triggers fire where the event happens and there is no
    cross-host job queue.
  - Double work across hosts is limited by the `UP_TO_DATE` check against the
    shared store.
  - The cap is per host, so total spend can reach hosts × cap. A user who wants
    a single analysing host enables the project and sets `AIT_RELATIONS=0` on
    the others.

### The headless operation

`aitask_codeagent.sh` gains the operations `relations` and `obsolescence`,
modelled on `explore-relay`:
- Claude Code only in v1, with `--print --output-format json`. Other agents get
  `UNSUPPORTED_AGENT` until `aitask_codeagent.sh` has a headless branch for them.
- Like `explore-relay`, they require `--headless`. The worker passes it, which
  acknowledges the billing surcharge. Unlike `explore-relay`, they pass a prompt
  file rather than invoking a skill slash command.
- **Read-only by construction, not by permission grants.** `--allowedTools`
  only pre-approves tools, so on its own it would leave inherited project
  permissions able to allow mutation. The operation restricts what is
  *available*:
  - `--tools "Read,Glob,Grep"`: the only built-in tools that exist in the
    session;
  - `--strict-mcp-config` with no `--mcp-config`: no MCP server, project or
    user, is loaded, so no inherited mutation-capable MCP tool exists;
  - `--disallowedTools` naming the mutation-capable built-ins (Bash, Edit,
    Write, NotebookEdit, WebFetch) as a second layer;
  - a permission mode that never prompts and never bypasses.

  - **No settings, no hooks.** Settings-sourced hooks DO run under `--print`:
    verified on claude 2.1.319, where a project `.claude/settings.json` hook
    fired. So the op passes `--setting-sources ""`, which loads no user,
    project or local settings, and therefore no inherited permission rule or
    hook. It also passes `--settings '{"disableAllHooks":true}'` as a second
    layer.
  - The prompt goes on **stdin**, so no variadic flag can swallow a positional
    argument.
  - `--no-session-persistence` and `--disable-slash-commands` are passed as
    well.

  The worker performs every write. `tests/test_codeagent_relations.sh` pins the
  argv. Its opt-in live check (`RUN_LIVE_RELATIONS=1`) proves that a prompt
  asking for a write, a shell command and an MCP call finds no such tool, and
  that a project hook does not run.
- The seed `codeagent_config.json` default for both is `claudecode/sonnet5_5`.
- The prompts are framework files, not skills:
  `.aitask-scripts/relations/prompts/relations_analysis.md` and
  `obsolescence_assessment.md`.

### Usage is measured

- Every record carries `usage`, read from the agent's JSON output, so totals
  across hosts come from the store itself.
- A local `usage.jsonl` ledger enforces the per-host daily cap.
- `ait relations usage [--days N]` reports jobs, tokens, cost and wall time per
  operation and trigger.
- Revisiting the default is a retrospective decision, made on that data. It is
  never automatic.

### Worker API

The contract the triggers (t1981_4), the consumers (t1981_5) and the candidate
generator (t1981_2) build on. Modules: `lib/relations_worker.py` (jobs, worker,
stamp), `lib/relations_spool.py` (spool, admission, ledgers),
`lib/relations_config.py` (the `relations:` block) and
`lib/relation_candidates_contract.py` (the provider contract).

**Spool layout.** Everything is per clone, under
`<git-common-dir>/aitask-relations/spool/`:
- `jobs/<op>__t<id>.json`: one queued job per `(op, task)`;
- `running/`: the job the worker holds;
- `failed/`: a failed job with its `reason`;
- `unresolved/<op>__t<id>/<invocation>.json`: guards (below), one per
  unresolved invocation;
- `results/<request_id>.json`: the outcome a `--wait` caller polls;
- `previews/<call_id>.json`: the ownership record of a running dry run (below);
- `work/<run_id>/`: the job's `snapshot.json`, `inputs/`, `prompt.md` and the
  agent's raw output. Kept for the last 20 jobs.
- `spool.lock`, `worker.lock`, `usage.lock` and `recovery.lock` (flock), and
  `enqueue.log`.

The ledger `usage.jsonl` sits directly under `aitask-relations/`, next to
t1981_5's `pull.jsonl` and `notify.jsonl`.

**Coalescing.** An enqueue merges into the existing job for the key:
- the trigger with the higher stage priority is kept (`plan_approved` over the
  rest);
- `not_before` = now + `settle_s` (debounce);
- `now` and `over_cap` are sticky, and `request_id`s are unioned;
- a `failed/` entry for the key is removed, and a `capped` hold is re-opened;
- an `unresolved/` guard is **never** removed by an enqueue.

**Fresh state per job.** Every job builds a new config, a new `Store` (and
`TaskIndex`), and takes exactly **one** `store.read()` snapshot. Source,
candidates, stamps, `UP_TO_DATE` and identity all use that snapshot. Nothing
carries over between jobs, because the index caches task text and plans.

**The worker loop:**
1. Take `flock -n worker.lock`, else exit.
2. `recover_running()`.
3. Re-open capped jobs; unblock jobs whose guard is gone.
4. Flush the outbox.
5. Drain ready jobs, sleeping through settle windows.
6. **Shutdown handoff:** release the lock, then re-scan for *any* job that is
   not held, ready or still settling. If there is one, re-acquire and loop. A
   failed re-acquire means another worker owns the job.

Capped and blocked jobs never keep a worker alive. They wait for the next worker
start (the next enqueue, `ait relations analyze`, or a later trigger); there is
no scheduler.

**The opt-out switches are re-read before paid work.** A worker job re-reads
`relations.enabled` and `AIT_RELATIONS=0` when it starts and again immediately
before admission, so work queued before an opt-out (or a switch flipped while
the job gathered candidates) never launches an agent. Such a job ends with the
visible outcome `SKIPPED:disabled` / `SKIPPED:host_off`: in its `results/`
entry, a `kind:"job"` ledger row and `enqueue.log`. `--dry-run` is the
deliberate exception, an explicit, cap-admitted preview.

**Admission and accounting.** Every real agent call, retries and `--dry-run`
included, reserves its slot **before** the call. `admit()` counts today's (UTC)
`kind:"call"` rows and appends a new one under `usage.lock`, so two callers can
never both take the last slot. A reservation consumes allowance whatever happens
next. `settle_call()` appends a `kind:"outcome"` row: `ok`, `timeout`,
`agent_error`, `invalid_output`, `interrupted`, `unresolved` or `error`. A
token or cost the agent did not report is `null` (unknown), never 0. Every job also writes exactly
one `kind:"job"` row for its **terminal** outcome: `ANALYSED(..)`,
`UP_TO_DATE`, `ANALYSED_EMPTY`, `EXCLUDED`, `STALE_RUN`, `SKIPPED:..` or
`FAILED:<reason>`. Dry runs do too, with `dry_run: true`. A held or requeued
job writes none, so a job retried after a timeout is one job and two calls.
Job rows never count against the cap; only calls do.

**Crash recovery.** Holding the worker lock proves only that the previous
*worker* is gone, not that its agent ended. The running entry records:
- `call_id` once admitted;
- `spawning` just before `Popen`;
- `agent` (`pgid`, the leader pid and its strong identity from
  `lib/pid_anchor.sh`) right after, through `bounded_run`'s `on_start` hook.

**Dry runs own their invocation the same way.** A preview writes
`previews/<call_id>.json`, holding its owner process (pid and strong identity)
and the same `spawning` / `agent` phases, and removes it once its agent has
ended. `recover_previews()` runs at every worker start and at the start of every
dry run, **and at the shared pre-admission boundary of every paid launch**
(scoped to the task about to launch), so a preview that was alive at startup
but lost its CLI afterwards is accounted for before a replacement starts. A
preview whose owner is provably alive is left alone. One whose
owner died is settled exactly like an orphaned running entry: retired only once
its agent provably ended (killing the group if needed), otherwise turned into an
unresolved guard for the task. Recovery is **serialized**: the whole
transition of one entry (re-read, decide, kill, settle, account, release) runs
under `spool/recovery.lock`, with the entry re-read under the lock, so
concurrent recoverers act on it at most once. Outcome rows (per `call_id`) and
recovery job rows (per `invocation`) are idempotent besides. A preview never
writes relation results.

`recover_running()` settles every orphaned entry:
- an admitted entry that never spawned is retried;
- a spawned one is retried only once the old invocation provably **ended**:
  - the leader pid is gone and `killpg(pgid, 0)` answers ESRCH, or the leader
    pid now carries a different strong identity;
  - otherwise the group is killed (bounded) and the end is re-verified;
- the second interruption of a job fails it as `INTERRUPTED`.

Anything that cannot be established writes an **unresolved guard**: a weak
identity, EPERM, a group still alive after the kill, or a `spawning` marker
without an `agent` record. The job fails as `INTERRUPTED_UNRESOLVED`. The guard
is stored **per invocation**, so a second unresolved invocation of the same task
(a worker job's or a preview's) never overwrites the first one's protection.
The task is blocked while **any** invocation remains, and each one is cleared
only on its own evidence. The final guard check and the paid reservation are
**one critical section** (`admit_unguarded`, under `spool.lock`, the lock every
guard write takes, then `usage.lock`), so a guard written after the launch's
earlier liveness scan blocks the launch instead of racing it. While it is blocked, every new launch for its
`(op, task)` is refused:
- queued requests and later enqueues are held as `blocked_unresolved`, and
  their requests resolve `BLOCKED_UNRESOLVED`;
- `--dry-run` refuses.

The guard clears only when a later evaluation finds the invocation ended (every
worker start re-checks it), or through `ait relations unblock <id> [--kill]
[--force]`. `--force` is the human assertion for the spawn gap, and it is logged.

**The candidate provider contract** (`relation_candidates_contract.py`). The
worker runs `aitask_relation_candidates.sh <id> --json --cap <N> --snapshot
<manifest>`. `--json` writes **exactly one JSON object** to stdout, and
diagnostics go to stderr. Shape `aitask-relation-candidates/1`:
- `source`;
- `provider {path, detail}`, where `path` is what the text output's
  `PROVIDER:` line carries;
- `coverage {answered, missing_sources}`, and `cap`;
- `source_inputs {body_sha256, plan_sha256}`;
- `candidates[] {ref, sources, card, evidence[] {source, detail, section?,
  line?}, inputs}`;
- `truncated {count, by_class, inputs}`.

`validate()` checks every field and type and the closed D6 tag vocabulary.
- **Missing coverage, malformed output, or a core source (`mention_in`,
  `mention_out`, `cites`) not answered fails the job**, and is never read as zero
  candidates. The reasons are:
  - `CANDIDATES_UNAVAILABLE:no_provider|core_missing:<srcs>`;
  - `PROVIDER_ERROR:exit_<n>|malformed:<reason>|timeout`.
- **One result, two renderings.** `to_json` / `to_text` (`parse_text` reads the
  text one back) carry the same provider, evidence, coverage and truncation
  information. In the text rendering every free-text field (cards, evidence
  details and sections, the provider detail) is a JSON string literal, and an
  absent optional field is a bare `-`, so no value can split a record or pass
  for an absent field. t1981_2 adds its `UNCONFIRMED:` rows to the same renderer.
- **The screening snapshot.** The manifest (`aitask-relation-snapshot/1`) lists
  every identity-valid stamp of the job's snapshot. Under the D5 rule (bodies
  current; a stamped task's plan at its stamp's `data_commit`; other plans from
  the working tree), cards and plan-derived evidence come only from that
  content, and deterministically. The result **echoes the digests** of what it
  screened. A mismatch with the worker's digests re-runs the provider once, then
  fails the job as `SNAPSHOT_MISMATCH:<ref>`.
- The skip identity covers screening: `inputs.screening_sha256` is the digest of
  the provider path, coverage, cards, evidence and truncation.
- Shared fixtures, a reference provider and a reusable contract test (with the
  `AIT_CANDIDATES_UNDER_TEST` hook): `tests/fixtures/relation_candidates/` and
  `tests/test_relation_candidates_contract.py`.

**Line protocols** (`ait relations`; exit 3 = refused, retained or timed out):
- `stamp <id>` prints `STAMP:<plan_sha256>`, `STAMP:disabled` or
  `STAMP_ERROR:<reason>` (exit 1). The stamp is in the outbox before the line is
  printed; the publish and the `plan_approved` enqueue are detached.
- `plan-digest <id>` prints `PLAN_DIGEST:<sha>` or `PLAN_DIGEST_ERROR:<reason>`.
- `analysis-state <id> [--expect-plan <sha>]` prints `RELATIONS_STATE:`, then
  `STORE:`, then `ANALYSIS_STATE:<state>`, plus `NOTE:` under `AIT_RELATIONS=0`.
- `analyze <id>` prints `ENQUEUED:t<id>`:
  - `--now --wait <s>` prints `ANALYZED:t<id>|<outcome>` or
    `WAIT_TIMEOUT:t<id>|<job state>`;
  - `--dry-run` prints the validated record JSON, or `CAP_REACHED:<n>/<cap>`,
    `BLOCKED_UNRESOLVED` or `FAILED:<reason>`.
  - Without `--dry-run`, analysis must be enabled and the host not switched off:
    `DISABLED:` / `HOST_OFF:`. `--dry-run` works while analysis is disabled.
- `usage [--days N]` prints `USAGE:local|<op>|<trigger>|jobs=|calls=|failed_calls=|unsettled=|in=|out=|cost=|wall=`,
  where `jobs` counts terminal job outcomes (paid or not, dry runs included)
  and `calls` counts agent invocations (each retry is one),
  and `USAGE:store|<op>|<trigger>|records=|…`. A total with unknown
  contributions reads `<sum>+unknown(<n>)`.
- `ledgers --export` prints JSON lines tagged `{host, ledger}`. A corrupt line
  becomes `{…, corrupt_line: n}` and is never skipped.
- `unblock <id> [--op <op>]` prints `UNBLOCKED:t<id>|ended|forced` (only when every
  invocation is resolved), `STILL_UNRESOLVED:t<id>|<why>|remaining=<n>` or
  `NO_GUARD:t<id>`.
- `enable` prints `PROJECT_NAME:kept|seeded:<name>`, `ENABLED_SET:`,
  `COMMIT:<metadata-commit line>` and `RELATIONS:enabled(<agent>, cap <N>/day)`.
  It refuses with `PROJECT_UNRESOLVED:`.
- `disable` prints `ENABLED_SET:false` and `RELATIONS:disabled`.

**The project-name rule of `enable`.** Keep an existing valid `project.name`.
Otherwise seed it only from **one** unambiguous registry binding of this
repository root (`aitask_project_resolve.sh bindings`, complete). Otherwise
refuse and explain how to set it. Setup's "yes" applies the same rule, and on a
refusal leaves `relations.enabled` absent, so the question returns.

**Test seams** (never set in production): `AIT_RELATIONS_CANDIDATES_CMD`,
`AIT_RELATIONS_AGENT_CMD`, `AIT_RELATIONS_AGENT_STRING`, and
`AIT_RELATIONS_TEST_BARRIER=<point>[,…]:<dir>`.

## D6 — Static candidate generation

**Decision.** `lib/relation_candidates.py`, exposed as
`aitask_relation_candidates.sh <id> [--json]`, reports source-tagged evidence
and gives no verdict.

Task-id backlinks, path citations, cards and text search come from **t2192's
shim**. It answers with the `aitasks_go#93` engine when that is installed and
with its Python fallback otherwise. The generator passes through t2192's
indication of which path answered, in whatever form t2192 settles: its Scope
item 2 leaves open whether the fallback covers a subset of the verbs or emits a
distinct "engine absent" line. Either form maps onto D5's rules: a verb that did
not answer is a missing source, and a missing core source fails the job. The
generator itself adds only framework-side signals.

| Source tag | Signal |
|---|---|
| `mention_out`, `mention_in` | task-id references in either direction, over description and plan sections (shim `mentions` / `mentioned-by`) |
| `inbox_note` | note edges (`from=`). Tagged separately, because `from=` is a claim |
| `family` | parent, children and siblings; a reference to the parent counts |
| `meta:<field>` | `depends` (both directions), `anchor`, `verifies`, `children_to_implement`, `risk_mitigation_tasks`, `folded_tasks` / `folded_into`, the follow-up origin |
| `trail` | co-membership in a stored trail (`lib/trail_discovery.py`) |
| `cites` | path overlap (shim `cites` / `cited-by`, with suffix resolution). A `hub` flag marks a path whose fan-in reaches `parallel_admission.HUB_THRESHOLD`. Hub overlaps are reported, never dropped, because hub files carry real signal in refactors (seed §2.3) |
| `line_anchor` | the candidate cites `file:line` in one of the source's surface files |
| `inflight_overlap` | `parallel_admission` OVERLAP rows for in-flight tasks. They come from each in-flight task's **declared** surface (`plan_declared`, `origin_derived`, `task_declared`), not from its uncommitted diff, so they cover another task's in-flight work as far as that work is declared |
| `token` | shim `search` hits for distinctive tokens of the source (backticked identifiers, UPPER_SNAKE names). Covers contract consumers with no shared path |
| `label_rare` | a shared label used by fewer than 40 tasks. Only breaks ties |

- **Universe:** pending tasks (Ready, Editing, Implementing, Postponed), minus
  the source itself and folded tasks.
- **Ordering, with no relevance cutoff.** By the number of distinct non-hub
  sources; then by source class, in this order: meta, mention, inflight, non-hub
  cites, line_anchor, token, trail, hub cites, label; then by id.
- **Cap.** `candidate_cap` bounds how many candidates get full cards and
  evidence.
  - Nothing beyond the cap is hidden. Its refs are passed to the agent as one
    `TRUNCATED:<n>` list grouped by source class (ids only), and the agent may
    read any of them with its Read tool.
  - This matters for hub-heavy refactors such as t1794_9, where most candidates
    are hub cites. The D13.2 replay measures whether truncation loses real
    recipients, and the cap is tuned from that.
- **Provider coverage.**
  - A failed provider, or a missing core verb (mentions, cites), fails the job
    (D5).
  - A missing optional verb, such as `search` behind `token`, is recorded as
    `coverage.missing_sources`.
  - Neither case can produce a false "analysed, 0 relations".
- **The output contract** (the exact `--json` shape, one object on stdout,
  diagnostics on stderr, the screening snapshot and its digest echoes) is fixed
  in D5's "Worker API". It is owned by `lib/relation_candidates_contract.py` and
  checked by `tests/test_relation_candidates_contract.py`, which this generator
  must pass.
- **Not in v1.** File-to-dependents widening through the testmap engine's
  `Graph.Reverse` is not part of v1. The retrospective revisits it if replays
  show misses it would catch.
- **The path grammar.** Extractor gaps (more extensions, suffix resolution of
  bare basenames) are fixed in the shared grammar owned by t2192 and
  `aitasks_go#93` ("one grammar, or a pinned differential"), never in a private
  copy here.
- **Evidence from plans is legitimate here.** At creation and at approval the
  source's plan is pre-implementation, so it cannot leak recipients. The
  contamination caveat applies to replaying history (D13), not to live
  analysis.

## D7 — The analysis (agent side)

**The inclusion test.** A relation is recorded only when all three hold:
1. The agent can state concretely what the other task's agent would do
   differently.
2. At least one basis anchor exists. For `affects`, `coordinates_with` and
   `supersedes`, at least one of them is an impact basis (`path`, `symbol` or
   `token`), not only a `task_ref`.
3. The type is in the vocabulary.

Zero relations is a normal result. There is no quota and no "find at least N"
pressure.

- **Two-stage reading.** Screen on the cards and the evidence. Read the full
  body and plan only for the survivors, at most 8 full reads per job.
- **The agent reads exactly what was hashed.** The worker materializes the
  analysed content of the source and of every candidate (current body, plus the
  stamped or working plan, per D5) into the job's input directory. The prompt
  directs every full read there, never to the task-data working tree. So the
  content the agent judges is the content the digests describe.
- **The description** is addressed to the other task's future agent. It is
  advisory context, never an instruction.
- **The two named misses** have evidence to work from: `inflight_overlap` for
  another task's in-flight work (through its declared surface), and `token` for
  a vocabulary consumer.
- **Output** is JSON in the record's `relations[]` and `considered[]` shape. The
  worker validates it, and a malformed answer fails the job.

## D8 — Consumption: hybrid

**Decision.** Pull by default, push narrowly.

**Why.** Every pushed note is a commit and a push race, and its read receipt is
another one. Pull delivers the information at the moment the recipient's agent
needs it, with no writes. Push remains for the cases where the recipient would
otherwise act before pull could reach it.

### Pull, at both ends of the target's implementation

One "related work" procedure file runs at two points:

- **At pick time:** a task-workflow Step 3 check after Check 6 (the Inbox
  check). Its number is coordinated with t1663_4's premise check: whichever
  lands second takes the next number.
- **Again at the target's own Step 8**, before its review and commit, as
  "related work during this implementation". It shows relations(T) whose other
  side landed after T was picked, and relations published after T's pick-time
  check. This covers a relation analysed late, after T had passed its
  pick-time check, as long as it is published before T's Step 8.
  - A relation whose source already sent T a note since T's pick is marked
    "covered by note <id>". This is checked mechanically: a note from that
    source in T's `## Inbox`.
  - The check is display only, so it never produces a second note.

For task T, the check reads relations(T) and shows each relation with its
**direction stated** ("t<L> affects this task" or "this task affects t<L>"):

- **Related tasks that landed since** T's reference time, with type,
  description, freshness, confirmation, and the path of the archived plan.
  - The reference time is T's last plan approval, otherwise its creation. At
    Step 8 it is T's pick.
  - "Landed" means archived as completed work: status Done and no
    `archived_reason`. Tasks archived as superseded or obsolete are shown as
    "dropped", not as landed.
  - **Confirmation is recomputed at read.** For a landed task L, its impact
    bases are checked against L's own landed change, derived from the commits
    whose subject carries `(t<L>)`, exactly as Step 8e does. So pull shows
    `confirmed_impact` or `unconfirmed_impact` without relying on any host's
    ledger. Relations whose other side has not landed show "not landed".
  - This group holds only edges that run from the landed task L toward T, or
    symmetric ones: `affects`, `advisory_precedes`, `supersedes` or `informs`
    with `from = L`, or `coordinates_with` or `duplicates` with either
    endpoint.
  - Edges that run from T toward L are listed separately, as "this task's own
    relations".
- **Related tasks in flight now.**
- **At pick time only:** T's own obsolescence band, when it is medium or higher
  (D9).

The check is display only. It never blocks and never writes, and it shows at
most 8 items. The pick-time list is handed to planning as context.

### Analysis completeness at Step 8e

Analysis is asynchronous (settle window, queue, daily cap, failures), so the
source S can reach Step 8e before its plan-stage analysis exists. Completeness
is judged against the **approval stamp**, which is shared across hosts.

- **The stamp.** At every plan approval that keeps the plan approved, `ait
  relations stamp <S>` writes `approvals/t<S>.json` (D2) synchronously into the
  local outbox. It holds the task-data commit that contains the approved plan,
  and the digests of the approved body and plan. A re-approval replaces it.
- **The approved plan.** Every run on a task with a stamp analyses the plan as
  of the stamp's `data_commit`, together with the current body (D1, D5). A
  stage-2 record's plan digest therefore equals the stamp's exactly.
- **The expected identity: what the session implements.** Completeness is tied
  to evidence naming the plan this session actually implements. It never rests
  on a stamp or a ledger merely being visible.
  - **Fresh path (Step 7).** `ait relations stamp` prints
    `STAMP:<plan_sha256>`. The workflow keeps it as the context variable
    `relations_expected_plan`.
  - **Resumed path (Re-entry Routing, `IMPLEMENT` route).** Before any work
    resumes, `ait relations plan-digest <S>` computes the normalized digest of
    the plan as committed at the task-data `HEAD`, which is exactly the plan the
    resumed session follows. It keeps that as `relations_expected_plan`.
    - This covers every inconsistent combination. Say a newer plan was
      published without its approval record, its gate-ledger entry or its
      stamp. Then the committed plan the session follows differs from the
      visible stamp, so the state is incomplete. It cannot be reported
      `complete` against the older stamp.
  - **Step 8e** passes it: `analysis-state <S> --expect-plan
    <relations_expected_plan>`.
  - With no expected identity (any other route, or the variable lost), the
    state is `incomplete:unverifiable(no_expected_identity)`. Under
    task-workflow every path to Step 8e passes through Step 7 or Re-entry
    Routing's `IMPLEMENT` route. `POSTIMPL` skips Step 8e.

`ait relations analysis-state <S> --expect-plan <sha>` is meant for
task-workflow Step 8e. It reports one of:

| State | Meaning |
|---|---|
| `complete` | the latest visible stamp's `plan_sha256` **equals** the expected identity, **and** a stage-2 record exists whose plan digest equals it and whose body digest equals S's **current** body digest. Stage alone never counts, and it does not matter which host wrote the stamp or the record |
| `incomplete:inputs_mismatch` | a record exists, but for other inputs: the plan was revised and re-approved, or the body changed since the analysis (for example, a fold) |
| `incomplete:unverifiable(<reason>)` | no stamp (for example, analysis was disabled at approval time); a stamp whose `plan_sha256` differs from the expected identity (`stamp_mismatch`, for example an older stamp after a re-approval whose stamp is not visible yet); `no_expected_identity`; an unreadable stamp; or a store read that came back `STORE:stale` or `STORE:unreachable`. Unverifiable never counts as complete |
| `incomplete:pending(settling\|queued\|running\|capped)` | a job for S is in this clone's spool |
| `incomplete:failed(<reason>)` | the job failed |
| `incomplete:missing` | a stamp exists, but there is no matching record and no local job (for example, the approving host has not published yet) |
| `disabled` | analysis is disabled in this project |

**Evaluation order** (first match wins):
1. `disabled`;
2. `unverifiable(no_expected_identity)`;
3. a stale or unreachable store gives `unverifiable(store_stale|store_unreachable)`;
4. a corrupt stamp gives `unverifiable(stamp_unreadable)`; a missing or
   identity-mismatched stamp gives `unverifiable(no_stamp)`; a stamp whose plan
   digest differs from the expected one gives `unverifiable(stamp_mismatch)`;
5. `complete`;
6. a job for S in this clone's spool gives `pending(..)` / `failed(..)`;
7. a record for other inputs gives `inputs_mismatch`;
8. `missing`.

A local job outranks `inputs_mismatch`, because it names the action already
under way.

With `AIT_RELATIONS=0` on this host, the states are computed the same way. A
missing record then reads `incomplete:missing`, with the note that analysis is
switched off on this host.

Consumers outside task-workflow that never approve a plan, such as `/aitask-note`
after `aitask-wrap`, use the plain `ANALYSIS:` line (D1). The stage-1 rule
applies there: a record whose body digest equals the current one.

**An incomplete state is never read as "no affected targets."** Step 8e then:
1. **States it**, naming the state. It still computes rows from whatever record
   exists, marked with that record's stage, and with `inputs_mismatch` where that
   applies.
2. **Offers a choice:**
   - *Run the analysis now and wait*: `ait relations analyze <S> --now --wait
     <job_timeout_s>` analyses S's current body with the plan from its latest
     stamp (the stage-2 inputs, D1).
     - When the daily cap is already reached, the prompt says so. The run then
       needs an explicit second confirmation, and is passed `--over-cap` (D5).
     - On success, the push rows are computed normally.
   - *Static discovery fallback*: D6's generator runs synchronously, with no LLM,
     restricted to push-eligible targets (Implementing, or holding a plan that
     cites a changed path). Its rows are `UNCONFIRMED:<to>|<sources>|<changed
     paths cited>`, and the implementing agent judges them against the diff, as
     today. They are evidence, not relations.
   - *Proceed with what exists*: the rows from the existing record only. The
     incomplete state is recorded in `notify.jsonl`, a per-host ledger (D13).

   With nobody to answer, the profile key `relations_incomplete_action`
   (`ask`, the default, or `wait`, `fallback`, `proceed`) picks the option.
   `wait` never passes `--over-cap`. The remote and web pick variants have no
   Step 8e (D4).

**When analysis is disabled,** Step 8e says so and keeps today's
judgement-based offer. It also offers the static fallback as an optional
evidence aid. That stays inside premise 8: the static analyzer is not the
layer's mechanism here, only an aid the agent may ask for. The disabled path
does not claim to be the relations layer.

### Push, narrow, requiring current impact evidence

`ait relations notify-candidates <S>` feeds Step 8e:

1. Read relations(S) and keep the pending targets.
2. **Validate against S's own change.** That change is the set of commits whose
   subject carries `(t<S>)` (the commit convention) reachable from HEAD.
   - In current-branch mode they are already on the output branch.
   - In worktree mode they are on the task branch, which is exactly what Step 9
     merges. Step 8e runs after the Step 8 commit and before the merge.
   - `--diff <range>` overrides the derivation, for tests and unusual layouts.

   Only an impact basis can confirm a relation: a `path` in the changed files
   (`-M` rename map included), or a `symbol` or `token` in the diff hunks. A
   `task_ref` establishes connectivity only and never confirms impact. The
   relation was inferred from a planned change, and the push has to rest on what
   was actually committed.
3. **Emit rows:**
   - `PUSH:<to>|<type>|<matched bases>|<description>` only when all of these
     hold:
     - the type is `affects` or `coordinates_with`;
     - **the direction fits**, checked by the helper deterministically:
       - `affects` is push-eligible only when `from` is the completing source
         S, and the recipient is its `to`. A reverse edge "X affects S" is never
         pushed when S lands.
       - `coordinates_with` is symmetric. Either endpoint may be S, and the
         recipient is the other endpoint.
     - at least one impact basis is confirmed by the diff;
     - the target is Implementing, or holds a plan (a plan file or
       `plan_approved_at`);
     - **the target still cites it now**: the target's *current* body or plan
       cites at least one of the confirmed impact bases (path, symbol or token).
       This holds for both target states. A target that has moved away from the
       surface since the relation was recorded (`stale:target_changed` and no
       longer citing it) gets a PULL row with `reason=target_moved`, not a push.

     Step 8e **offers** a note for each PUSH row, as a multi-select and never
     automatically. The body is pre-filled with the description **and the
     matched diff evidence**. Before offering, the agent checks that the stored
     description still matches what landed.
   - `PULL:<to>|<type>|<reason>`: every other connected target. This covers
     other types, targets in neither state, and relations whose impact the diff
     did not confirm (`reason=unconfirmed_impact`, the task-ref-only case
     included). They stay available through pull, at pick time and at the
     target's Step 8 check, marked unconfirmed. Step 8e discards no relation.

Findings that relations cannot derive, such as review findings or decisions made
in conversation, keep today's judgement-based offer.

Composing the note stays in Step 8e. The agent pre-fills it from the stored
description and the matched evidence, which is cheap. Moving composition into
the background worker after the merge is not done in v1, because every push is
an offer a human confirms in the session.

**`/aitask-note` with no target** reads relations(sender) first, then falls back
to Related Task Discovery (as t2192 upgrades it).

**The other note offers and discovery consumers, in v1:**
- **`aitask-qa` and `aitask-review`.** Their note offers are about findings
  (test gaps, review findings), which relations cannot derive. They keep their
  judgement-based offer. When the user picks no target, they route through
  `/aitask-note`, which reads the store first.
- **`aitask-explore`, `aitask-fold` and `aitask-contribution-review`.** They use
  the Related Task Discovery Procedure to find related tasks for a *new* piece
  of work, before any task or record exists. They keep t2192's engine-based
  discovery and do not read the store in v1.
- Whether `aitask-fold` should consume `duplicates` relations (with t1634) is a
  retrospective question.

### Consumer API

Module `lib/relations_consume.py`, behind three `ait relations` verbs. All three
are read-only except for the local ledgers, and none writes task data, commits
or sends a note: offers are made, and notes sent, by the agent through
`/aitask-note`.

- **One plain-words summary.** Every surface (Step 3 Check 8, the Step 8
  re-check, Step 8e, `/aitask-note`) displays the verbs' `SUMMARY:` line
  verbatim. It is rendered by one function from the state lines, so "disabled",
  "not analysed yet", "analysed, 0 relations" and "the store could not be read —
  unknown, not none" read the same everywhere.
- **Disabled projects never fetch** (the store is read with `no_fetch`) and
  never push. A previously enabled project keeps its stored records, and those
  are still shown, but every one of them is `PULL …|relations_disabled`.
- **`related-work <id> --point pick|review|note [--since <ts>] [--log]`.**
  - Output: the state lines, then `SUMMARY:`, `CHECKED_AT:`, `REFERENCE:<iso>|<source>`;
  - per item, `ITEM:<group>|<direction>|<type>|<other>|<freshness>|<confirmation>|<end state>|<archived plan>[|covered_by_note=<id>]`,
    with the description on the next line;
  - then `MORE:<n>`, `BEFORE_REFERENCE:<n>`, or `RELATED_WORK:0`, which always follows `SUMMARY:`.
  - The groups are `landed`, `dropped`, `late` (review only), `in_flight`, `own` and `pending`, capped at 8 items in that priority.
  - **The reference time.** At `pick` it is `plan_approved_at`, else the visible stamp's `approved_at`, else `created_at`. At `review` it is `--since`, else the lock's `locked_at`, else `created_at`.
  - Naive task and lock times are local time; record times are UTC; an unparseable time is shown (fail-open), never hidden.
  - The lock time is read from the local `origin/aitask-locks` ref as last fetched, never through `aitask_lock.sh --check` (which fetches): no related-work call ever pays a network round trip in a disabled project.
  - A landed item's archived plan is reported repo-relative when loose. A plan that exists only inside a numbered or legacy bundle is extracted to `<git-common-dir>/aitask-relations/archived-plans/` and that path is reported.
- **Note targets.** Every `ITEM:` and `PUSH:` row is followed by `NOTE_TARGET:<id>` (or `<id>|project=<name>`): the bare id `aitask_note.sh` accepts. The qualified ref stays the relation identity and the ledger key.
- **Covered by note.** A review item is `covered_by_note=<id>` when the task's
  `## Inbox` holds a note from the other task's `t<id>` after `--since`, read or
  unread alike. It is checked with `lib/note_inbox.py`'s validated parser, not
  with `aitask_query_files.sh inbox`, which lists unread notes only.
- **`notify-candidates <S> [--rev <rev> | --diff <range>] [--expect-plan <sha>] [--option <opt>] [--log]`.**
  - Output: the state lines, `ANALYSIS_STATE:` (recomputed, never trusted from the caller), `RECORD:stage=<n>|source=<fresh|stale|unverified>` or `RECORD:none`, `SUMMARY:`, `CHANGESET:<n>|<origin>`, any `WARN:`, `CHANGED_FILE:<path>…` and `RUN_ID:<uuid>`;
  - then `PUSH:<to>|<type>|<matched bases>|<description>` rows, each with `  EVIDENCE:<kind>:<value>|<commit>|<file>`, and `PULL:<to>|<type>|<reason>` rows;
  - and when there is no PUSH row, `PUSH_NONE:complete|disabled|changeset_unreadable|changeset_empty|incomplete:<…>`. Only `complete` may be worded "no affected targets", and it needs both a complete analysis and a readable, non-empty change set.
- **The worktree rule.** The change set is the `(t<S>)`-subject commits reachable from `--rev` (default `HEAD`). In worktree mode Step 8e passes `--rev aitask/<task_name>` and runs from the main repository root, because the task data is not visible inside the worktree.
- **The PULL reasons, in rule order** (the first failing rule wins):

  | Reason | Rule that failed |
  |---|---|
  | `relations_disabled` | the project has analysis disabled |
  | `type_not_pushed` | the type is not `affects` or `coordinates_with` |
  | `reverse_direction` | an `affects` edge whose `from` is not S |
  | `other_project` | the recipient belongs to another project |
  | `target_closed` | the recipient has landed or been dropped |
  | `unconfirmed_impact` | no impact basis is confirmed by the change set (the task-ref-only case included) |
  | `target_state` | the recipient is neither Implementing nor a plan holder |
  | `target_moved` | the recipient's current body or plan cites none of the confirmed bases |
- **`notify-outcome <S> --run <id> --to <ref> --type <type|unconfirmed> --outcome sent|declined|not_offered [--note-id <id>]`** records one Step 8e offer outcome.
- **The ledgers** (`pull.jsonl`, `notify.jsonl`) are written one JSON line per `O_APPEND` write.
  - Each row carries `at`, `host`, `task`, the relation `{from, to, type, record_task}`, `freshness`, `confirmation` and `outcome` (`shown` / `offered` / `sent` / `declined` / `not_offered`).
  - Summary rows carry the point or the Step 8e `analysis_state` and `option`.
  - `ledgers --export` emits them, tagged with the host.

### Deliberately deferred: a retained later review

A relation published after both its source and its target have landed reaches no
one. The target's Step 8 re-check covers every case where the target is still in
flight.

- Covering the rest would need a second notification path that reviews late
  relations. That path could re-offer a note the immediate path had already
  sent, unless both paths shared one resolution identity scoped to (source,
  target, landed change).
- v1 therefore has no retained review.
- The retrospective measures the gap from store and archive timestamps: records
  published after their source landed, with targets that were in flight at that
  moment. If the gap is real, a later design must use that shared identity for
  both paths.

Batching several notes into one commit is out of scope. The hybrid push is the
volume reduction.

## D9 — The obsolescence layer

**Decision.** The same store and the same worker, with its own operation
(`obsolescence`). **Never auto-actioned.**

### Evidence

`lib/obsolescence_evidence.py`, exposed as `aitask_obsolete.sh evidence <id>`,
collects static rows, each tagged by kind:

| Kind | Evidence |
|---|---|
| `path_deleted` | a cited path that was deleted and not renamed. Rename-aware history (`git log -M --diff-filter=DR`), cached per HEAD in `.aitask-cache/` |
| `path_renamed` | the cited path was renamed: the task needs a refresh, not removal |
| `origin_state` | the origin (`verifies`, `anchor` or the follow-up origin) is archived, folded, deleted or **reverted**. Reverts are read from `## Revert Notes`, which no script reads today; this layer adds the reader |
| `superseded_by`, `duplicate_of` | store relations from landed or pending tasks |
| `affected_by_landed` | an `affects` relation from a task that landed after this one was created |
| `premise` | t1663's `aitask_premise_stale.sh check` verdict when that tool exists, otherwise `unavailable` |
| `age` | days without activity. A weak prior, labelled as such, never a verdict on its own |

The 2026-10-14 measurement (seed §2.7) is why judgement is needed: most missing
paths are renames, relative paths or planned-new files, and only 3 of 577 pending
tasks cited a truly deleted path. Not every row is a scoring input. Path rows,
`age`, a non-stale premise reading and a completed origin are **context**, shown
for human inspection only (see "Obsolescence API" below).

### Judgement

- If there is no evidence row other than `age`, the band is `none` and no LLM
  runs.
- Otherwise the agent assigns a band, reasons that cite evidence ids, and a
  disposition: `keep`, `refresh`, `fold_into` (with `fold_target` naming the
  task) or `drop`, exactly as the D2 record holds it.

### Triggers

A landing (D4) re-scores the pending tasks related to the landed task, since
landing is what makes tasks obsolete. `ait obsolete sweep [--budget N]` covers the
whole backlog on demand.

### Surfaces and dispositions

- `ait obsolete ls [--min-band <band>]`, `show <id>`, `evidence <id>`, `dismiss
  <id> [--note]`.
- **A dismissal is keyed to the evidence digest.** The task resurfaces when the
  evidence changes, and not before.
- `ait obsolete review` walks the list. For each task: open it, fold it (the
  existing fold flow), archive it as obsolete, dismiss it, or skip.
- **No new status.** "Drop" archives the task with `aitask_archive.sh
  --obsolete`, which writes `archived_reason: obsolete` next to the existing
  `superseded` value. The reasons stay in the store record.

### Boundary with t1663 and t1655

Premise staleness ("needs refresh") stays theirs. Its verdict is one evidence row
here. The two layers share no engine: this layer never emits FRESH or ASK_STALE,
and the premise engine never scores obsolescence. The roadmap has no slot for an
obsolete score (`lib/roadmap_policy.py`). Adding one is left to the
retrospective.

### Obsolescence API

This is the contract the TUI (t1981_7) and the docs (t1981_8) build on.

**Modules:**
- `lib/obsolescence_evidence.py`: the evidence rows (`collect`), `parse_revert_notes` and the path history;
- `lib/relations_worker.py`: `analyse_obsolescence`, `landed_targets` and `obs_eligible`;
- `lib/obsolete_cli.py` with `aitask_obsolete.sh`: the `ait obsolete` verbs.

**Signal and context rows.** Every row is classified as one of two kinds.

| Class | Rows |
|---|---|
| signal | `origin_state` other than a completed origin (archived with a reason, folded, deleted, reverted); `superseded_by`; `duplicate_of`; `affected_by_landed`; `premise` with `ASK_STALE` |
| context | `age`; `premise` with `FRESH`, `SKIP` or `unavailable`; `origin_state` `archived:completed@…`; **every path row** (`path_deleted`, `path_renamed`, `path_ambiguous`) |

- **Scoring inputs = digest inputs = signal rows.** Only signal rows reach the assessor (`evidence.json` and the prompt). Only they can be cited by `reasons[].evidence_ids`, only they are stored in the record's `evidence[]`, and only they make up `inputs.evidence_digest`, which is the sha256 over the sorted `(kind, detail, source)` triples, ids excluded.
- **Context rows are for human inspection only**, shown live by `ait obsolete evidence`. A context row that reached the prompt could shape a recommendation that its later change would never invalidate, because `UP_TO_DATE` and dismissals key on the digest.
- **Path rows are factual file events, followed forward in sequence.** Each row reports how the cited name's latest lifetime ended, with `lifetimes=<n>`, and comes from one `git log --topo-order -M --name-status --diff-filter=ADR` pass over HEAD, cached at `.aitask-cache/obsolescence/history-<HEAD>.json`.
  - They never assert obsolescence: nothing yet proves that the task's current citation refers to the lifetime that ended. A citation can be removed and reintroduced, and a task may be proposing to recreate the file.
  - Attributing a path event to the current citation is a follow-up.
- **No signal row** → band `none`, disposition `keep`, no agent call.
- **Incomplete evidence** fails the job as `EVIDENCE_INCOMPLETE:<reason>`, never `none`, and leaves any stored assessment in place. The check runs before `UP_TO_DATE`, so it can neither publish nor replace an all-clear. Causes:
  - an unreadable origin, or a malformed `verifies` / `anchor`;
  - a failed path history, or a premise tool error;
  - a relations snapshot that cannot vouch for "no relation rows": a corrupt record (`store_corrupt:<path>`; `Store.read` omits it) or an `unreachable` store (`store_unreachable:<reason>`, no data at all).

  An `empty`, `local_only`, `fresh@` or `stale:` (latest-known) store is complete.

**The job** (`op = obsolescence`, the same spool, admission, recovery and headless launch as `relations`):
- **Cap:** the daily cap counts per op: the spool's `calls_today(op)` against `relations.max_jobs_per_day`.
- **Eligibility:** only active tasks that are not `Done` / `Folded`, not folded and not `manual_verification` are assessed. Others end as `EXCLUDED`.
- **Up to date:** a job skips as `UP_TO_DATE` when the stored record has the same body and plan digests (the D5 plan rule) and the same `evidence_digest`, at the same or a higher stage.
- **Output validation:** the agent's output must be exactly `{band, reasons, disposition[, fold_target]}`.
  - A band other than `none`, or a disposition other than `keep`, needs at least one reason, and band `none` requires `keep`. `relations_schema.validate_obsolescence` enforces both.
  - Every reason cites at least one of this job's signal ids.
  - `fold_target` is allowed only with `fold_into`, and only to a listed target: a foldable (Ready/Editing) pending end of a `duplicates` / `supersedes` relation, or a sibling.
- **Outcomes:** `ASSESSED(published|retained)`, `UP_TO_DATE`, `EXCLUDED`, `FAILED:<reason>`.

**The landed trigger.**
- `aitask_archive.sh` `main` calls `aitask_relations_enqueue.sh obsolescence landed <id>` after a **successful archive commit**, for each id that commit archived as completed work. That is the task, plus a parent the child flow auto-archived in the same commit.
- The call is skipped for `--dry-run`, `--no-commit` (stage only), a verified nothing-to-commit, `--superseded`, `--obsolete`, and an archived file carrying `archived_reason` or `folded_into`. It is silent, and `|| true`.
- The detached part checks the switches (`enabled`, `AIT_RELATIONS=0`, `triggers.landed`) before it reads anything, logging `ENQUEUE:obsolescence|landed|t<id>|SKIPPED:…`.
- It then enqueues one `obsolescence` job for every eligible task that is a pending end of relations(landed) or whose origin (`verifies` / `anchor`) is the landed task, and logs `LANDED_FANOUT:t<id>|<n>`.

**`ait obsolete` line protocols.** Every output starts with `RELATIONS_STATE:` and `STORE:`. Free text is percent-encoded (`%0D`, `%0A`, `%7C`, `%25`).

| Verb | Lines |
|---|---|
| `evidence <id> [--json] [--no-fetch]` | `EVIDENCE:<id>\|<kind>\|signal\|context\|<source>\|<detail>`, `INCOMPLETE:<reason>`, `SIGNAL_ROWS:<n>`, `EVIDENCE_DIGEST:<sha>`. Works while analysis is disabled; it is static. |
| `ls [--min-band low\|medium\|high] [--all]` | `OBSOLETE:t<id>\|<band>\|<disposition>[:<target>]\|<fresh\|stale\|unverified>\|reasons=<n>[\|dismissed]`, or `OBSOLETE:0`. A dismissal at the record's digest hides the task unless `--all` is passed. |
| `show <id> [--json]` | `OBSOLESCENCE:`, `RUN:`, `REASON:<ids>\|<text>`, `EVIDENCE:` (signal rows), `USAGE:`, `DISMISSED:no\|current\|stale…`, `CONTEXT:see ait obsolete evidence <id>`. Otherwise `NO_ASSESSMENT:t<id>` (exit 1). |
| `dismiss <id> [--note <text>]` | Writes `dismissals/t<id>.json` keyed to the record's `evidence_digest` and prints `DISMISSED:t<id>\|<digest12>`, then the flush reports (exit 3 on `RETAINED:`). The task resurfaces when a new assessment has a different digest. |
| `review` | One item at a time: `[o]pen [f]old [a]rchive-obsolete [d]ismiss [s]kip [q]uit`. Each action needs that explicit letter; anything else re-prompts, and EOF prints `REVIEW_ENDED:eof`. See below for fold and archive. |
| `unblock <id> [--kill] [--force]` | The obsolescence op's unresolved-invocation guards only, with the same protocol as `ait relations unblock` (`UNBLOCKED:` / `STILL_UNRESOLVED:` / `NO_GUARD:`). Guards are per `(op, task)`: `ait relations unblock <id> [--op relations\|obsolescence]` defaults to `relations`, and clearing one op never touches the other's. |
| `sweep [--budget N]` | `ENQUEUED:t<id>` per job, then `SWEEP:<n>\|budget=<b>\|candidates=<N>`. Requires analysis enabled (`DISABLED:` / `HOST_OFF:`). The default budget is the obsolescence op's remaining daily cap. |

**How `review` folds and archives.**
- **Fold** validates both ends by parsing `aitask_fold_validate.sh` lines, since that helper exits 0 for every content outcome: the destination must be `VALID:` on its own, and the item must be `VALID:` with `--exclude-self <destination>`. Any other answer is `FOLD_REFUSED:<id>|<reason>`. After the `y` confirmation both are re-validated, then the existing fold sequence runs.
- **Archive** runs `aitask_archive.sh --obsolete` after a `y`. It offers `--ignore-gates` only after a second confirmation when gates are pending.

**Sweep rotation.** The sort key is `(not boosted, last_attempt, id)`.
- `last_attempt` is the ledger position of the task's newest `kind:"job"` row of the obsolescence op in this host's `usage.jsonl`. Every terminal outcome writes one, `UP_TO_DATE` and failures included. The append order is exact; the rows' one-second `at` would tie.
- A task with no assessment is **boosted** until its first attempt.
- A task whose body or plan changed since its assessment is boosted while its newest attempt is still the successful one the record came from. An attempt that fails after the change spends the boost.
- So a persistent failure can never monopolise a bounded sweep, and evidence that changes while body and plan do not is still revisited.

**Pick-time display.** `ait relations related-work <id> --point pick` adds `OBSOLESCENCE:<band>|<disposition>[:<target>]|<inputs>` and up to three `OBSOLESCENCE_REASON:` lines. They appear when the task's own identity-valid assessment is `medium` or higher and not dismissed at its digest. They are display-only, as the rest of the check is.

## D10 — Surfaces

| Surface | What |
|---|---|
| `ait relations` | `show <id>`, `why <a> <b>`, `status`, `flush`, `gc`, `analyze <id> [--now --wait <s>] [--over-cap] [--dry-run]`, `analysis-state <id> --expect-plan <sha>`, `stamp <id>`, `plan-digest <id>`, `sweep`, `usage`, `ledgers --export`, `notify-candidates <id> [--rev <rev> \| --diff <range>] [--expect-plan <sha>] [--option <opt>] [--log]`, `notify-outcome <id> --run <id> --to <ref> --type <type> --outcome <o>`, `related-work <id> --point pick\|review\|note [--since <ts>] [--log]`, `enable`, `disable` |
| `ait obsolete` | `ls`, `show`, `evidence`, `dismiss`, `review`, `sweep`, `unblock` |
| Agent surfaces | the pick-time related-work check, planning context, the target's Step 8 re-check, Step 8e, `/aitask-note` with no target, t1634 (`duplicates`), trails (relations as gather input, later) |
| TUI (later) | a read-only Textual `ait relations` with two tabs: **Relations** (per task: type, description, evidence, freshness, neighbourhood) and **Obsolete** (sorted by band, with reasons and actions). Registered in `KNOWN_TUIS`; the board's detail screen gets a "Relations: n (k stale)" field |

## D11 — Lifecycle and freshness

- **Staleness is computed at read.** For each end of a relation, the reader
  compares the record's input digests with that task's **baseline**. A mismatch
  marks the relation `stale:source_changed|target_changed`. Stale relations are
  still shown, with the marker.
  - **The body baseline** is always the current normalized body digest. Body
    edits after approval are rare and meaningful (a fold, a rewritten goal).
  - **The plan baseline** is the latest approval stamp's `plan_sha256` when the
    task has one, otherwise the current normalized plan digest. Plan edits
    during implementation (progress marks, implementation notes) therefore never
    make relations look stale. Only a re-approval does.
  - **Archived tasks are compared like active ones.** Their baselines come from
    the archive text, whether the file is loose, in a numbered
    `_bN/oldM.tar.zst` bundle or in the legacy `old.tar.zst`, for the task file
    and the plan alike. A relation that was stale before archival stays stale
    after it.
  - **A baseline that cannot be read is never "fresh".** For example, a corrupt
    bundle. The marker is then `unverified:source_baseline` or
    `unverified:target_baseline`.
- **Identity at read.** A relation end whose recorded `created_at` differs from
  the live task's `created_at` names a deleted task whose id was reused. It is
  dropped at read, never attributed to the new task.
- **Re-analysis is eager only through triggers.** `ait relations sweep --stale`
  catches up within the budget.
- **These rules are revisited from data.** Showing stale relations with a marker,
  and not re-analysing on plan edits, are the v1 choices. Consumers log freshness
  with every relation they surface or offer, and the retrospective reassesses
  both rules: whether stale results stay useful, whether they mislead
  notifications, and whether the triggers or the display rule should change.
- **Archived tasks keep their records.** Pull needs them.
- **Folded tasks** are canonicalized to the primary at read. The fold trigger
  re-analyses the primary.
- **Deleted tasks.** `ait relations gc` removes records, assessments, dismissals
  and approval stamps for ids that exist nowhere: not active, not archived, not
  inside a numbered or legacy bundle, and not folded into a task that exists.
  Relations that point at a deleted id are filtered at read. This is the
  single-writer exception named in D1.
  - **Two independent negatives** are required before a delete: a complete
    index scan (any read error refuses with `GC_REFUSED:scan_incomplete`), and
    `NOT_FOUND` from `aitask_query_files.sh` for that id.
  - **Eligibility is decided on the exact tree the deletion is built from**:
    the integrated local branch plus the outbox, re-checked on every attempt.
    A valid replacement found there, whether from the remote, a local-only
    commit or the outbox, is kept and reported `GC_KEPT:<path>|revalidated`.
- **Renumbering and id reuse.**
  - No renumbering operation exists, and parent ids are monotonic
    (`aitask_claim_id.sh`).
  - Child numbers can be reused: the next child number is the highest existing
    one plus one, so deleting the highest-numbered child frees its number.
  - The `(id, created_at)` identity (D2) covers that case. `gc` also removes a
    record whose `task_created_at` no longer matches the live task, and the new
    task reads as unanalysed (`sweep --unanalysed`).

## D12 — Cross-repo

- Refs are canonical `<project>#<id>` from the start.
- Candidates and relations stay inside the local project in v1. Cross-project
  relations are deferred, and the schema already allows them. A cross-project
  end the store does meet keeps its qualification, and is reported as
  unverifiable rather than rewritten as local (D1 "Store API").
- **Revisit trigger:** the retrospective counts cross-project notes (`ait note
  --project`) and `xdeps` edges that touch analysed tasks. If cross-project
  traffic is a real share of the notes sent, cross-project candidates become a
  follow-up.
- `xdeps` stay metadata facts. `ait note --project` already routes a push to
  another repository.

## D13 — Evaluation

Automation-first: no human review step is a precondition for the layer to
operate.

1. **Candidates** (candidate child). The seed's Appendix A.1 replay, run over the
   generator's output, **on task bodies only**. It reports recall and candidates
   per sender, compared with `aitasks_go#93`'s numbers for the same replay.
2. **The pipeline, offline, before any trigger exists** (candidate child,
   through `analyze --dry-run`). Run the operation on at least 10 historical
   senders with at least 4 notes each, using the sender's body and plan as of its
   plan-approval commit and the candidates as of today. That is a stated
   post-hoc caveat. It reports:
   - recall against the actual recipients;
   - the recorded relations (the notify-list size) and the PUSH/PULL split;
   - tokens, cost and wall time per job.

   The report goes into that child's archived plan. Enabling the layer in this
   repository is the user's decision, made on that report.
3. **Live** (the retrospective child, after at least 4 weeks enabled or 100
   records):
   - Step 8e offers, sends and declines (`notify.jsonl`) and pick-time displays
     (`pull.jsonl`). Every logged row carries the relation's freshness, its
     confirmation (`confirmed_impact` / `unconfirmed_impact`) and its outcome.
     - The ledgers are local to each host, under
       `<git-common-dir>/aitask-relations/`.
     - `ait relations ledgers --export` prints them, together with
       `usage.jsonl`, as JSON lines tagged with the host name.
     - The retrospective asks the user to run it on every host that ran
       analysis, and merges the outputs. Totals that need no ledger (records,
       usage per record) come from the shared store directly.
   - Every Step 8e analysis state and the option chosen.
   - The late-relation gap (D8).
   - Records and tokens per day, and the stale ratio.
   - Obsolescence bands and the dispositions taken.

   It decides:
   - the D5 default;
   - `compact`, if the median fetch is above 2 s (D1);
   - the reverse index (D3);
   - the candidate cap and `Graph.Reverse` widening (D6);
   - whether a retained review is needed (D8);
   - fold consumption of `duplicates` (D8);
   - roadmap integration (D9);
   - non-Claude headless support (D5);
   - coverage for the remote and web pick variants (D4);
   - cross-project relations (D12);
   - adoption of `orphan_ref_store.py` by the lock and id scripts (D1).

   It explicitly reassesses stale-relation handling (D11). It files follow-up
   tasks only where the data justifies them.

## Implementation tree

Children of t1981. Dependencies are explicit.

**What waits on t2192**, which itself waits on `aitasks_go#93` through `xdeps`:
- Directly: only t1981_2.
- Through t1981_2: the triggers (t1981_4), and transitively the docs, ports and
  retrospective (t1981_8, t1981_9, t1981_10).

The store (t1981_1), worker (t1981_3), consumption (t1981_5), obsolescence
(t1981_6) and TUI (t1981_7) do not wait.

| Child | Scope | Depends on |
|---|---|---|
| t1981_1 | Store and CLI: `lib/orphan_ref_store.py`, `lib/relations_store.py` (D1, D2, D3, D11), `aitask_relations.sh` read verbs and the state lines | — |
| t1981_2 | Candidate generator (D6), including its static fallback mode for Step 8e, and the replays D13.1 and D13.2 | t1981_3, t2192 |
| t1981_3 | Worker, spool, headless operation, analysis prompt, approval stamp and `analysis-state`, configuration and setup activation (D4 enqueue helper, D5, D7). Until t1981_2 lands, the worker fails jobs with `CANDIDATES_UNAVAILABLE`, and its tests use a fixture candidate provider | t1981_1 |
| t1981_4 | Triggers: creation, plan approval, fold, sweep (D4) | t1981_2 |
| t1981_5 | Consumption: the related-work check at both points, `notify-candidates`, Step 8e, `/aitask-note` (D8). Until t1981_2 lands, the Step 8e static fallback reports that it is unavailable | t1981_1, t1981_3 |
| t1981_6 | Obsolescence layer (D9), including the `landed` trigger in `aitask_archive.sh` and `aitask_archive.sh --obsolete` | t1981_3, t1981_5 |
| t1981_7 | TUI (D10) | t1981_6 |
| t1981_8 | Website documentation | t1981_4, t1981_5, t1981_6, t1981_7 |
| t1981_9 | Ports of the skill changes to the other agent trees | t1981_4, t1981_5, t1981_6 |
| t1981_10 | Retrospective (D13.3) | t1981_8, t1981_9 |
