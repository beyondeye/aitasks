---
Task: t1981_task_relations_and_obsolescence_design.md
Base branch: main
Output branch: main
---

# Plan: t1981 — Task relations and obsolescence design

## Context

At the end of implementation, `task-workflow` Step 8e (and the offers in
`aitask-qa` / `aitask-review`) choose note recipients by agent judgement alone.
`/aitask-note` with no target reads only titles, labels and about five body
lines (`related-task-discovery.md`). Doing it well costs the implementing
session real context (t1794_9 grepped 103 files to send 63 notes). Doing it
broadly is a defect: 373 note commits and 52 read-receipt commits race on the
hottest files of the data branch. Nothing flags obsolete backlog tasks.

This task is a **brainstorming task**. Its output is:

1. a finalized design document, `aidocs/framework/task_relations.md`, that
   settles D1–D13 of the seed proposal (`ait attach get 1981
   task_relations_proposal.md`);
2. a decomposition into child tasks with plans.

The premises (decisions 1–8 in the task body) are fixed. The seed proposal's
measurements (§2) are reused, not re-run. No framework code is written in this
session.

**Settled with the user in this session (2026-11-04):**

- D8: **hybrid**. Pull by default; push narrowly.
- D1: **orphan branch `aitask-relations`**. The design must specify how readers
  refresh the branch and how failed writes are retained for retry, local-only
  mode included.
- D5: **off by default**. Activation must be clear during setup. When analysis
  is disabled, the layer must say so, so that an empty store is never read as
  "no related tasks". Usage is measured before the default is revisited.
- D6: **wait on t2192**. The candidate child depends on t2192, and only that
  child waits. D6's needs go to aitasks_go#93 as a note.

**Inbox: one note, from t2192 (claimed), acknowledged, advisory.** Used for:
- the L1/L2 vs L3 boundary (t2192 / aitasks_go#93 own query and backlinks;
  t1981 owns everything about confirmed relations);
- the open question of whether `## Inbox` edges count as a mentions source
  (decided below: yes, as a separately tagged source);
- the trail refresh request (art:trail-task-relations-and-premise), offered
  after decomposition.

**Facts checked this session that shape the design:**
- `ait artifact` always writes an `artifacts:` entry into the owning task's
  frontmatter (`aitask_artifact.sh:484-491`). Premise 2 therefore rules it out
  as the store.
- The orphan-branch pattern exists twice, copied inline:
  - `aitask_lock.sh` (`aitask-locks`): plumbing, push-as-CAS, 5 retries, no
    offline fallback.
  - `aitask_claim_id.sh` (`aitask-ids`): a local-only branch when there is no
    remote, and an auto-upgrade push when a remote appears (:183-244).
- `aitask_task_commit.sh` refuses everything outside `aitasks/` and `aiplans/`.
  Auto-merge and the `ait sync` sweep see only `aitasks/*.md` / `aiplans/*.md`.
- `aitask_create.sh` commit sites:
  - `finalize_draft`: child at 910 (auto-merge 922, lock release 924), parent at
    976 (auto-merge 986).
  - `run_batch_mode --commit`: child at 2370 (auto-merge 2383, lock release
    2385), parent at 2411 (auto-merge 2421).
  - There is no post-create hook.
- The plan-approved gate record is guarded by `profile.record_gates`, both in
  `task-workflow/SKILL.md` (572-575) and in `plan-approved-stop.md` (41-65).
- `aitask_codeagent.sh`: `explore-relay` is the headless template. It is
  Claude-only, uses `--print`, and hardcodes `--allowedTools` and timeouts.
  `codeagent_config.json` maps an op to an agent string only. No token-budget
  knob exists anywhere.
- task-workflow Step 3 Checks 1–6 exist, and Check 6 is the Inbox check.
  t1663_4 plans its premise check as "Check 6", a numbering clash.
- `archived_reason: superseded` exists (`aitask_archive.sh --superseded`, :61,
  :169-172). There is no `Obsolete` status.
- `## Revert Notes` is written by the revert skill and read by no script.
- `lib/parallel_admission.py` `HUB_THRESHOLD` is the single hub constant.
- The trail schema relation types are `hard_depends | advisory_precedes |
  coordinates_with | verifies | informs`, each with `provenance: fact|advisory`.

## Design (content of `aidocs/framework/task_relations.md`)

The doc follows `aidocs/framework/documentation_conventions.md`: current state
only, and decisions stated with their reasons. It opens with the premises and
the layer boundary (L1/L2 query = aitasks_go#93 + t2192; L3 relations and L4
obsolescence = this design). It has one section per D:

### D1 — Store: orphan branch `aitask-relations`

**Layout** (single branch, flat JSON, `schema_version` file at the root):

```
schema_version              "1"
records/t<id>.json          relations record of task <id> (one per task)
obsolescence/t<id>.json     obsolescence assessment of task <id>
dismissals/t<id>.json       a human dismissal of that assessment
approvals/t<id>.json        the latest plan-approval stamp of <id> (D8 completeness)
```

Each file has a single writer:
- `records/` and `obsolescence/`: the worker;
- `approvals/`: the task's own approving session;
- `dismissals/`: the human resolver.

**Module.** A new `lib/relations_store.py` with a small, reusable
`lib/orphan_ref_store.py` (git plumbing: temporary `GIT_INDEX_FILE`,
`update-index --cacheinfo`, `write-tree`, `commit-tree`, push-CAS / `update-ref`
CAS). `aitask_lock.sh` and `aitask_claim_id.sh` stay untouched. The doc records
them as candidates to adopt the module later, out of scope here.

**Modes:**
- *Remote mode*: the repo has the remote that `aitask-locks` uses.
- *Local-only mode*: no remote. This is the `aitask-ids` precedent.

**Reader refresh:**
- Every reader invocation does at most one fetch:
  `git fetch --no-tags origin +refs/heads/aitask-relations:refs/remotes/origin/aitask-relations`.
  The fetch is bounded (timeout) and non-interactive (no credential or SSH
  prompt). `--no-fetch` exists for tests and for a second read in the same
  step.
- After a successful fetch, the reader records `fetched_at` in
  `<git-common-dir>/aitask-relations/fetched_at` and reports `STORE:fresh@<ts>`.
- After a failed fetch, the reader uses the last fetched remote-tracking ref and
  reports `STORE:stale:<reason>@<last fetched_at>`. If the branch was never
  fetched or never written, it reports `STORE:empty`.
- In local-only mode the reader reads `refs/heads/aitask-relations` and reports
  `STORE:local_only`.
- Every read **overlays the outbox** (below): this clone's not-yet-published
  records win per path under the newest-wins rule and are marked
  `pending_push`.
- Every reader output starts with `RELATIONS_STATE:enabled|disabled`, then
  `STORE:…`, then per task
  `ANALYSIS:analysed:<n>|not_analysed:<queued|failed|never>|disabled`. These
  lines are what keep an empty store from ever being presented as "no related
  tasks".

**Writes are retained for retry (outbox first):**
1. Validate the record against the schema and the closed vocabulary.
   Validation happens before any mutation; an invalid record fails the job and
   nothing is written.
2. Write the record atomically to
   `<git-common-dir>/aitask-relations/outbox/<path>.json` (tmp + fsync +
   `os.replace`). The outbox entry is the durable intent. The git common dir is
   per clone and shared by worktrees.
3. Publish. Every publish flushes **all** outbox entries in one commit.
   - **Remote mode:**
     1. Fetch.
     2. For each path, apply newest-wins against the remote version. An entry
        that loses is reported `SUPERSEDED:<path>` and dropped from the outbox.
     3. Build the tree, then `commit-tree -p <remote tip>`.
     4. Push as CAS. A non-fast-forward rejection retries from the fetch, up to
        8 attempts with jitter.
   - **Local-only mode:** the same flush, with
     `update-ref refs/heads/aitask-relations <new> <old>` as the CAS.
   - **On success:** delete exactly the outbox entries whose content hash was
     published. An entry rewritten during the flush stays.
4. **On failure** (network, auth, retries exhausted): the entries stay in the
   outbox, with the last error in a sidecar `<path>.err`. The writer reports
   `RETAINED:<n>|<reason>` and never drops anything silently.
   - Retry is targeted: the next write, `ait relations flush`, or the next
     worker start publishes the outbox first.
   - `ait relations status` lists every entry with its age and last error.
5. **Upgrade from local-only:** on the first publish after a remote appears:
   - If the remote branch is absent, push the local branch as is (the
     `aitask-ids` precedent).
   - Otherwise, re-apply every path whose local content differs from the
     remote one, newest-wins, as one commit on the remote tip. Then reset the
     local branch to it and report `UPGRADED:<n>`.
6. **Newest-wins rule:** a record replaces the existing one only if its
   `(stage, at)` is greater than or equal, where stage is `created=1` and
   `plan_approved=2`. A sweep, manual or fold run takes the stage its inputs
   imply: 2 if the task has a plan, otherwise 1. An older-stage job that lost
   the race is reported `STALE_RUN`.

**History growth.** About one commit per analysed task, roughly 15–25 a day. A
`compact` verb is deferred. Its trigger is recorded in the doc as "measured
fetch cost over the budget".

### D2 — Record schema and vocabulary

**Relations record** (`records/t<id>.json`, schema `aitask-relations/1`):

```json
{"schema":"aitask-relations/1","task":"aitasks#1981","analysed":true,
 "run":{"id":"<uuid>","trigger":"created|plan_approved|fold|sweep|manual","stage":2,
        "at":"<ISO>","host":"<h>","agent_string":"claudecode/sonnet5_5",
        "code_base":"<sha>","data_base":"<sha>","candidate_provider":"engine|fallback"},
 "inputs":{"source":{"body_sha256":"…","plan_sha256":"…|null"},
           "candidates":[{"ref":"aitasks#1663_4","body_sha256":"…","plan_sha256":null}]},
 "considered":[{"ref":"aitasks#1663_4","outcome":"related|unrelated|unreadable","sources":["mention_in","cites"]}],
 "relations":[{"from":"aitasks#1981","to":"aitasks#1663_4","type":"coordinates_with",
   "description":"<≤600 chars, written for the other task's agent>",
   "basis":[{"kind":"path","value":".claude/skills/task-workflow/SKILL.md"},
            {"kind":"token","value":"Check 6"}],
   "evidence":[{"source":"mention_in","detail":"t1663_4 body line 14"}]}],
 "usage":{"input_tokens":0,"output_tokens":0,"cost_usd":null,"wall_s":0}}
```

**Digests.** `body_sha256` covers only the task description, with framework
sections (`## Inbox`, `## Gate Runs`, folded history) excluded via
`plan_paths.split_task_framework_sections`. `plan_sha256` covers the whole plan
file. Both are content hashes, never stat freshness.

**Single-writer rule.** One end of every relation is the record's own task.
`from`/`to` give the direction explicitly.

**Vocabulary** (closed; writers fail closed on an unknown type; a new type
needs a schema bump):

| type | direction | meaning | consumed by |
|---|---|---|---|
| `affects` | from → to | when `from` lands, `to`'s premise, plan or surface changes | pull, push, D9 |
| `advisory_precedes` | from → to | `from` should land before `to` (advisory, never `depends`) | pull, trails |
| `coordinates_with` | symmetric | both change the same surface or decision | pull, push |
| `duplicates` | symmetric | same goal | D9, t1634 fold candidates |
| `supersedes` | from → to | `from`'s direction replaces `to`'s goal | D9 |
| `informs` | from → to | useful context, nothing to do differently | pull only, never pushed |

`hard_depends` and `verifies` are **not** recorded. They are metadata facts that
consumers read from frontmatter, so the store never duplicates them.

**Basis kinds.** `path` (canonicalized with `plan_paths` suffix resolution),
`symbol`, `token`, `task_ref`. Each is mechanically checkable.
- `path`, `symbol` and `token` are **impact bases**: they can be confirmed
  against a diff.
- `task_ref` is a **connectivity basis** only. It keeps a relation findable and
  checks staleness, but never confirms impact (D8).
- `affects`, `coordinates_with` and `supersedes` require at least one impact
  basis.

**No confidence number.** Only included relations are recorded. Precision comes
from the inclusion test (D7), not a threshold.

**Rejections.** `considered[]` keeps them inside the record. That data lets a
sweep skip unchanged candidates (when both digests are unchanged) and gives D13
something to measure screening against.

**Obsolescence record** (`obsolescence/t<id>.json`):
- `run`, `inputs` (source digests plus `evidence_digest`), `evidence[]`
  (`{id, kind, detail, source}`);
- `band: none|low|medium|high`, `reasons[]` (`{text, evidence_ids[]}`);
- `disposition: keep|refresh|fold_into|drop`, plus `fold_target`.

**Dismissal** (`dismissals/t<id>.json`): `{task, at, by, evidence_digest, note}`.
It is written by a human through `ait obsolete dismiss`.

### D3 — Single writer, reverse lookup

- Only the analysis of task X writes `records/tX.json`.
- `relations(X) = forward(X) ∪ reverse(X)`, where reverse(X) is every other
  record with a relation naming X. It is answered by one `ls-tree` plus one
  `cat-file --batch` over the branch tree, with the outbox overlaid.
- Folded refs are canonicalized to the primary (`folded_into`) when read.
- v1 has no reverse index. If measured reads exceed 500 ms, a derived cache
  keyed on the branch tip's **tree SHA** is the documented next step: exact,
  and never the authority.

### D4 — Triggers

All triggers go through one silent helper,
`aitask_relations_enqueue.sh <op> <trigger> <task_id>`:
- it always exits 0 and never writes to stdout;
- errors go to the spool log;
- it checks `relations.enabled`, the per-trigger switch and `AIT_RELATIONS=0`.

| trigger | site | op |
|---|---|---|
| created | `aitask_create.sh`: one helper call after `run_auto_merge_if_needed` at the four commit sites, after the child lock release | relations |
| plan_approved | Step 7 (after the plan-approved gate block, **outside** the `record_gates` guard) and `plan-approved-stop.md`; also writes the approval stamp `approvals/t<id>.json` (D8) | relations, on the stamp's snapshot |
| fold | `aitask_fold_mark.sh` after its commit (the primary's body changed) | relations (primary) |
| landed | `aitask_archive.sh` `main` after the archive commit | obsolescence, for the pending tasks in relations(landed) plus the tasks whose origin is the landed task |
| sweep / manual | `ait relations sweep [--budget N] [--stale] [--unanalysed]`, `ait relations analyze <id>`, `ait obsolete sweep` | either |

- **Settle window** (default 120 s after the last enqueue for that task). It
  covers decomposition bursts and wrappers that seed the body in a later commit
  (manual-verification seeder, archive carry-over, issue-import amend).
- **Coalescing.** One spool file per `(op, task)`; a later trigger keeps the
  higher stage.
- **Excluded.** `issue_type: manual_verification` tasks are not analysed: their
  relations are `verifies` facts.
- **No re-analysis on plan edits.** Approval is the moment. Edits after it show
  up as staleness (D11).
- **Sequencing.** t1663_3 also edits the `aitask_create.sh` batch path, so the
  trigger child plans against it if it has landed.

### D5 — Execution (off by default)

**Config.** `project_config.yaml`:

```yaml
relations: {enabled: false, max_jobs_per_day: 40, job_timeout_s: 600,
            settle_s: 120, candidate_cap: 25,
            triggers: {created: true, plan_approved: true, landed: true}}
```

- The seed default is `enabled: false`.
- `ait relations enable|disable` writes the key through
  `aitask_metadata_commit.sh`.
- `AIT_RELATIONS=0` is a per-host kill switch.

**Activation at setup.**
- `ait setup` always prints `RELATIONS:disabled|enabled(<agent>, cap N/day)`,
  following the `TESTMAP:<state>` precedent (`aitask_setup.sh:2876`), with the
  enable hint and a one-line cost note.
- Interactive setup asks once, default No, when the key is absent.

**Disabled is visible everywhere.** The pick-time check, Step 8e,
`/aitask-note` and `ait relations show` all say "relations analysis is disabled
in this project — no relation data". They never say "no related tasks". "Not
analysed yet (queued, failed or never)" is distinct from "analysed, 0
relations".

**Spool and worker.**
- The spool lives at `<git-common-dir>/aitask-relations/spool/` (atomic tmp +
  `os.replace`).
- One worker per clone, `lib/relations_worker.py`, guarded by a non-blocking
  `flock` on `worker.lock`. The enqueue helper starts it detached
  (`start_new_session`) when the lock is free. It exits when the spool is
  empty; there is no idle daemon.
- Per job:
  1. Wait for the settle window and check the daily cap.
  2. If the store already holds identical input digests at ≥ this stage,
     report `UP_TO_DATE` and skip. This is also what limits double work across
     hosts.
  3. Generate candidates (D6). With zero candidates, write an analysed record
     with `relations: []` and **no LLM call**.
  4. Otherwise run the headless op under a timeout that kills the process
     group.
  5. Parse and validate the output, then write through the store (D1).
- Completion is judged from the validated output only, never from pane state
  or banner text.
- A failure moves the job to `failed/` with its reason. One retry, for
  timeouts only.

**Headless op.** `aitask_codeagent.sh` gains the ops `relations` and
`obsolescence`, modelled on `explore-relay`:
- Claude Code only in v1, with `--print --output-format json`.
- `--allowedTools "Read,Glob,Grep"`, so the agent is read-only; the worker does
  every write.
- The seed `codeagent_config.json` default is `claudecode/sonnet5_5`.
- Prompts are framework files:
  `.aitask-scripts/relations/prompts/{relations_analysis,obsolescence_assessment}.md`.
- Other agents get `UNSUPPORTED_AGENT` until `aitask_codeagent.sh` has a
  headless branch for them.

**Usage measured.**
- Every record carries `usage` (from the JSON output), so cross-host totals
  come from the store itself.
- A local `usage.jsonl` ledger enforces the per-host daily cap.
- `ait relations usage [--days N]` reports jobs, tokens, cost and wall time per
  op and trigger.
- Revisiting the default is a retrospective decision, never automatic.

### D6 — Static candidate generation

A new `lib/relation_candidates.py` + `aitask_relation_candidates.sh <id>
[--json]`. It reports source-tagged evidence and gives no verdict. Task-id
backlinks, path citations, cards and text search come from **t2192's shim**,
which answers with the engine when installed and its fallback otherwise.
`PROVIDER:engine|fallback` is passed through. The generator adds only
framework-side signals.

| source tag | signal |
|---|---|
| `mention_out` / `mention_in` | task-id refs both ways over description and plan sections (shim `mentions` / `mentioned-by`) |
| `inbox_note` | note edges (`from=`), tagged separately because `from=` is a claim |
| `family` | parent / children / siblings (a ref to the parent counts) |
| `meta:<field>` | `depends` (both ways), `anchor`, `verifies`, `children_to_implement`, `risk_mitigation_tasks`, `folded_*`, follow-up origin |
| `trail` | co-membership in a stored trail (`lib/trail_discovery.py`) |
| `cites` | path overlap (shim `cites` / `cited-by`, suffix resolution); a `hub` flag when fan-in ≥ `parallel_admission.HUB_THRESHOLD` — reported, never dropped |
| `line_anchor` | the target cites `file:line` in one of the source's surface files |
| `inflight_overlap` | `parallel_admission` OVERLAP rows; covers another task's uncommitted work |
| `token` | shim `search` hits for distinctive tokens of the source (backticked identifiers, UPPER_SNAKE); covers contract consumers with no shared path |
| `label_rare` | a shared label with fan-in < 40; used only to break ties |

- **Universe:** pending tasks (Ready, Editing, Implementing, Postponed), minus
  self and folded tasks.
- **Ordering, never a cutoff:** by the count of distinct non-hub sources, then
  by source class (meta > mention > inflight > non-hub cites > line_anchor >
  token > trail > hub cites > label), then by id.
- **Cap** `candidate_cap`. Overflow is reported as `TRUNCATED:<n>`.

### D7 — The analysis (agent side)

The inclusion test records a relation only when all three hold:
1. The agent can state concretely what the other task's agent would do
   differently.
2. At least one basis anchor exists. For `affects`, `coordinates_with` and
   `supersedes` that anchor must be an impact basis (`path`, `symbol` or
   `token`), not only a `task_ref`.
3. The type is in the vocabulary.

Zero relations is a normal result. There is no quota.

**Two-stage reading.** Screen on cards and evidence. Read the full body and
plan only for survivors, at most 8 full reads.

**The description** is addressed to the other task's future agent. It is
advisory, never an instruction.

**The two named misses** have evidence to work from: `inflight_overlap` and
`token`.

### D8 — Consumption: hybrid

**Pull (default), at both ends of the target's implementation.** One
"related work" procedure file, run at two points:
- **At pick time:** a task-workflow Step 3 check after Check 6. The number is
  coordinated with t1663_4's premise check (the note below).
- **Again at the target's own Step 8**, before its review and commit, as "related
  work during this implementation". It shows relations(T) whose other side
  landed after T was picked, and relations published after T's pick-time check.
  This covers a relation analysed late, after T had passed its pick-time check,
  as long as it is published before T's Step 8.
  - A relation whose source already sent T a note since T's pick is marked
    "covered by note <id>". This is checked mechanically, by a note from that
    source in T's `## Inbox`.
  - The check is display only, so it never produces a second note.

For task T the check reads relations(T) and shows each relation with its
**direction stated** ("t<L> affects this task" vs "this task affects t<L>"):
- related tasks that **landed since** T's reference time (T's last plan
  approval, otherwise its creation; at Step 8, T's pick), with type,
  description, freshness, confirmation, and the path of the archived plan.
  This group holds only edges whose direction runs **from** the landed task L
  toward T, or symmetric ones:
  - `affects`, `advisory_precedes`, `supersedes` or `informs` with `from = L`;
  - `coordinates_with` or `duplicates` with either endpoint.

  Edges running from T toward L are listed separately as "this task's own
  relations".
- related tasks **in flight now**;
- at pick time only, T's own obsolescence band when it is ≥ medium (from D9).

It is display only: it never blocks and never writes. It shows at most 8 items.
The pick-time list is handed to planning as context.

**Analysis completeness at Step 8e: digests against a shared approval stamp.**
- **The stamp.** At every plan approval (Step 7 and `plan-approved-stop.md`)
  the enqueue helper writes `approvals/t<S>.json` into the store. It records
  `{approved_at, data_commit, body_sha256, plan_sha256}`: the task-data commit
  holding the approved plan and the digests of that approved body and plan. Its
  single writer is the approving session, and a re-approval replaces it
  (newest wins). The stamp goes through the outbox like any write, so it is
  shared across hosts.
- **Analysing the approved snapshot.** For `plan_approved` jobs the worker reads
  body and plan **from the stamp's `data_commit`**, not from the working tree.
  The record's input digests therefore equal the stamp's exactly, even when the
  implementing session edits the plan during the settle window.

`ait relations analysis-state <S>` then reports one of:
- `complete`: the latest stamp is readable, and a stage-2 record exists whose
  `inputs.source` digests **equal** the stamp's. Stage alone never counts, and
  any record will do whichever host wrote it or the stamp. Without a plan
  approval (stage 1), the record's body digest must equal S's current body
  digest.
- `incomplete:inputs_mismatch`: a record exists, but for different inputs. This
  is the case of a plan revised and re-approved, on this host or another.
- `incomplete:unverifiable(<reason>)`: no stamp, an unreadable stamp, or a store
  read that came back stale (`STORE:stale`). Unverifiable never counts as
  complete.
- `incomplete:pending(settling|queued|running|capped)`, from the local spool.
- `incomplete:failed(<reason>)`.
- `incomplete:missing`: a matching stamp exists, and there is no matching record
  and no local job. For example, S was approved on another host and that host
  has not published yet.
- `disabled`.

**An incomplete state is never read as "no affected targets."** Step 8e then:
1. **States it**, naming the state. It still computes rows from whatever record
   exists, marked with that record's stage and `inputs_mismatch` where that
   applies.
2. **Offers a choice:**
   - *Run the analysis now and wait*: `ait relations analyze <S> --now --wait
     <job_timeout_s>` analyses the latest stamp's snapshot. It moves the job to
     the front, skips the settle window and counts against the daily cap; the
     prompt says so when the cap is already reached. It waits with a bound, and
     on success the push rows are computed normally.
   - *Static discovery fallback*: D6's generator runs synchronously with no LLM,
     restricted to push-eligible targets (Implementing, or holding a plan that
     cites a changed path). Rows are `UNCONFIRMED:<to>|<sources>|<changed paths
     cited>`, and the implementing agent judges them against the diff, as
     today. They are evidence, not relations.
   - *Proceed with what exists*: the rows from the existing record only, with
     the incomplete state recorded in `notify.jsonl`.

When analysis is disabled, Step 8e says so and offers the static fallback.

**Deliberately deferred: a retained later review.** A relation published after
both its source and its target have landed reaches no one. The target's Step 8
re-check covers every case where the target is still in flight.
- Doing more would need a later "review the late relations" path. That path
  could duplicate notes the immediate path already sent, unless the immediate
  and later paths shared one resolution identity scoped to (source, target,
  landed change).
- v1 therefore has no retained review.
- The retrospective measures the gap from store and archive timestamps: records
  published after their source landed, with targets that were in flight at that
  moment. If the gap is real, a later design must use that shared identity for
  both paths.

**Push (narrow), requiring current impact evidence.** `ait relations
notify-candidates <S> --diff <base>..<head>`:
1. Read relations(S) and keep the pending targets.
2. Validate against the **landed diff**. Only an **impact basis** can confirm a
   relation: a `path` in the changed files (rename map included), or a `symbol`
   or `token` in the diff hunks. A `task_ref` establishes connectivity only and
   **never confirms impact**.
3. Emit rows:
   - `PUSH:<to>|<type>|<matched bases>|<description>` only when all of these
     hold:
     - the type is `affects` or `coordinates_with`;
     - **the direction fits**, checked deterministically by the helper rather
       than left to the agent:
       - `affects` is push-eligible only when `from` is the completing source
         S, and the recipient is its `to`. A reverse-lookup edge "X affects S"
         is never pushed when S lands.
       - `coordinates_with` is symmetric. Either endpoint may be S, and the
         recipient is the other endpoint.
     - at least one impact basis is confirmed by the diff;
     - the target is Implementing, or holds a plan (plan file or
       `plan_approved_at`) that cites a confirmed path or token.

     Step 8e **offers** a note for each PUSH row (multi-select, never automatic),
     pre-filled with the description **and the matched diff evidence**. The
     relation was inferred from a planned change, so before offering, the agent
     checks that the stored description still matches what landed.
   - `PULL:<to>|<type>|<reason>`: every other connected target. That covers other
     types, targets in neither state, and relations whose impact the diff did
     not confirm (`reason=unconfirmed_impact`, the task-ref-only case
     included). They stay available through pull, at pick time and at the
     target's Step 8 check, marked unconfirmed. Step 8e discards no relation.

Findings that relations cannot derive (review findings, decisions made in
conversation) keep today's judgement-based offer.

**`/aitask-note` with no target.** It reads relations(sender) first, then falls
back to Related Task Discovery (as t2192 upgrades it).

Batching several notes into one commit is out of scope: hybrid push is the
volume reduction.

### D9 — Obsolescence layer

Same store, same worker, op `obsolescence`. **Never auto-actioned.**

**Evidence collector** `lib/obsolescence_evidence.py` +
`aitask_obsolete.sh evidence <id>`. Static rows, each tagged:

| kind | evidence |
|---|---|
| `path_deleted` | a cited path deleted with no rename (`git log -M --diff-filter=DR`, cached per HEAD in `.aitask-cache/`) |
| `path_renamed` | the cited path was renamed: refresh, not obsolete |
| `origin_state` | the origin (`verifies` / `anchor` / follow-up origin) is archived, folded, deleted or **reverted** (a new `## Revert Notes` reader) |
| `superseded_by` / `duplicate_of` | store relations from landed or pending tasks |
| `affected_by_landed` | an `affects` relation from a task that landed after T was created |
| `premise` | t1663's `aitask_premise_stale.sh check` verdict when that tool exists, otherwise `unavailable` |
| `age` | days without activity; a weak prior, labelled as such and never a verdict alone |

**Judgement.**
- If there are no rows besides `age`, the band is `none` and no LLM runs.
- Otherwise the agent assigns a band, reasons that cite evidence ids, and a
  disposition: keep, refresh, fold_into:<id> or drop.

**Triggers.** Landed (D4) and `ait obsolete sweep [--budget N]`.

**Surfaces.**
- `ait obsolete ls [--min-band]`, `show <id>`, `dismiss <id> [--note]`.
- A dismissal is keyed to `evidence_digest`, so the task resurfaces when the
  evidence changes.
- `ait obsolete review` walks the list: open, fold (the existing fold flow),
  archive as obsolete, dismiss, or skip.

**Disposition "drop".**
- There is no new status.
- `aitask_archive.sh --obsolete` writes `archived_reason: obsolete`, alongside
  the existing `superseded` value.
- The reasons stay in the store record.

**Boundary with t1663 / t1655.**
- Premise staleness ("needs refresh") stays theirs, and its verdict is one
  evidence row here.
- The two layers share no engine. This layer never emits
  FRESH / ASK_STALE.
- Roadmap integration (`roadmap_policy` has no slot for an obsolete score) is
  left to the retrospective.

### D10 — Surfaces

**CLI.** `ait relations show|why <a> <b>|status|flush|gc|analyze [--now
--wait]|analysis-state|sweep|usage|notify-candidates|enable|disable` and
`ait obsolete ls|show|evidence|dismiss|review|sweep`.

**Agent surfaces.** The pick-time check, planning context, Step 8e,
`/aitask-note`, t1634 (`duplicates`), and trails (relations as gather input,
later).

**TUI (a later child).** A read-only Textual `ait relations` with two tabs:
- **Relations:** per task, type, description, evidence, freshness and the
  neighbourhood.
- **Obsolete:** sorted by band, with reasons and actions.

It is registered in `KNOWN_TUIS`, and the board's detail screen gets a
"Relations: n (k stale)" field.

### D11 — Lifecycle and freshness

- **Staleness at read.** Readers compare current digests with the record's
  inputs. A mismatch marks the relation `stale:source_changed|target_changed`;
  stale relations are still shown, with the marker.
- **Re-analysis.** Eager only through triggers. `sweep --stale` catches up
  within the budget.
- **Revisited from data.** Both rules (show stale relations with a marker; no
  re-analysis on plan edits) are the v1 choice. Consumers log freshness with
  every surfaced or offered relation, and the retrospective (D13.3) explicitly
  reassesses them: whether stale results stay useful, whether they mislead
  notifications, and whether triggers or hiding rules should change.
- **Archived tasks.** Their records are **kept**, because pull needs them.
- **Folded tasks.** Canonicalized at read; the fold trigger re-analyses the
  primary.
- **Deleted tasks.** `ait relations gc` removes records, assessments,
  dismissals and approval stamps for ids that exist nowhere: active, archived, or inside
  `old.tar.zst` bundles (resolved via `aitask_query_files.sh`). Relations
  pointing at deleted ids are filtered at read.

### D12 — Cross-repo

- Refs are canonical `<project>#<id>` from v1.
- Candidates and relations stay inside the local project in v1. Cross-project
  relations are deferred, and the schema already allows them.
- `xdeps` stay metadata facts. `ait note --project` already routes pushes.

### D13 — Evaluation (automation-first, no human review precondition)

1. **Candidates** (candidate child): the Appendix A.1 replay over the
   generator's output, **task bodies only**, reporting recall and candidates per
   sender, compared with aitasks_go#93's numbers.
2. **Pipeline, offline, before triggers exist** (candidate child, through the
   worker's `analyze --dry-run`): run the op on
   at least 10 historical senders (at least 4 notes each), using the sender's
   body and plan as of its plan-approval commit (data-branch history) and
   candidates as of today, a stated post-hoc caveat. It reports:
   - recall against the actual recipients;
   - recorded relations (the notify-list size) and the PUSH/PULL split;
   - tokens, cost and wall time per job.

   The report goes into the child's archived plan. Enabling the layer in this
   repo is the user's call on that report.
3. **Live** (retrospective child, after ≥ 4 weeks enabled or ≥ 100 records):
   - Step 8e offers / sends / declines (local `notify.jsonl`) and pick-time
     displays (local `pull.jsonl`). Every logged row carries the relation's
     freshness (`fresh` / `stale:source_changed` / `stale:target_changed`), its
     confirmation (`confirmed_impact` / `unconfirmed_impact`) and the outcome:
     sent or declined.
   - Every Step 8e analysis state (complete / incomplete with reason /
     disabled) and the option chosen.
   - The late-relation gap, from store and archive timestamps: records published
     after their source landed whose targets were in flight at that moment
     (D8, the deferred retained review).
   - records and tokens per day, stale ratio;
   - obsolescence bands and the dispositions taken.

   It decides: the default (D5), the reverse index, roadmap integration,
   non-Claude headless support, and adoption of `orphan_ref_store.py` by locks
   and ids.

   It also **explicitly reassesses stale-relation handling** from those logs:
   - whether stale relations shown at pick time or offered at Step 8e were
     still useful;
   - whether they caused misleading or unwanted notifications (stale PUSH rows
     that were declined, or sent but wrong);
   - whether the refresh triggers (D4: no re-analysis on plan edits; `sweep
     --stale` as the only catch-up) or the display rule (D11: stale relations
     are shown with a marker, never hidden) need to change. Changing them is
     filed as follow-up tasks only if the data justifies it.

## Implementation steps (after plan approval)

This session writes no framework code. The order is: design doc → commit →
coordination notes → decomposition.

1. **Step 7 preamble** (the normal workflow): ownership guard, resource
   admission, agent attribution, the plan_approved gate record, and the risk
   field writes.
2. **Write `aidocs/framework/task_relations.md`** from the Design section above.
   Re-verify every `file:line` it cites against the tree at writing time, with
   the measurements dated and attributed to the seed proposal (§2) or to
   `task_search_analysis.md`. No version history in the body.
3. **Step 8 review** (after the post-phase `independent_design_review`
   below), then commit the doc only:
   `documentation: Add task relations and obsolescence design (t1981)` (path-scoped).
4. **Coordination notes** via `./ait note`, one heredoc each, with the doc's
   commit SHA cited:
   - `ait note 93 --project aitasks_go --from 1981`: what D6 needs from the
     engine. Batch ids for `mentioned-by` / `cited-by`; section tags and line
     numbers on `cites` hits (for `line_anchor`); per-path fan-in (or
     `cited-by --count`) for the hub flag; `search` restricted to pending
     tasks; card fields (status, plan presence, labels, parent / children).
     `## Inbox` edges as a separately tagged `mentions` source. It also records
     that `Graph.Reverse` widening is not needed in v1, and that t1981 will
     consume its replay numbers in D13.
   - `ait note 2192 --from 1981`: the boundary.
     - t1981_5 owns Step 8e and adds a store-first step ahead of the Related
       Task Discovery that t2192 upgrades. t2192 should not edit Step 8e.
     - t1981_2 consumes t2192's shim verbs and its `PROVIDER:` line.
   - `ait note 1663_4 --from 1981`: Step 3 Check 6 is already the Inbox check
     (t1657, `task-workflow/SKILL.md:103`). t1981_5 plans a "related work"
     check after it; whichever lands second takes the next number.
5. **Decompose** (post-approval creation, per `planning_conventions.md`):
   - Create the children through the Batch Task Creation Procedure
     (`task-creation-batch.md`, mode child) with `--no-sibling-dep` and
     explicit `--deps`.
   - Each child body carries the Context, Key files, Reference patterns,
     Implementation plan and Verification sections, plus a pointer to the doc
     section it implements.
   - Then write a plan per child (`aiplans/p1981/p1981_<n>_<name>.md`), each
     opening with a **Reality-check step**: the files and functions it assumes,
     re-verified at pick time, naming which neighbour (t1663_3, t1663_4, t2192)
     may have moved them.
   - Commit the plans path-scoped via `aitask_task_commit.sh`.
   - Revert the parent to Ready (`--plan-approved-at ""`) and unlock the
     parent.
   - Offer the manual-verification sibling and the child checkpoint.

| child | scope | deps |
|---|---|---|
| t1981_1 `relations_store_and_cli` | `lib/orphan_ref_store.py`, `lib/relations_store.py` (layout including approval stamps, outbox, reader refresh, local-only, upgrade, newest-wins), schema and vocabulary module (impact vs connectivity bases), `aitask_relations.sh` (`show`, `why`, `status`, `flush`, `gc`) with the state lines, helper-whitelist touchpoints, CLAUDE.md pointer. Tests: no-remote, offline, CAS race, outbox retention, upgrade | — |
| t1981_2 `relation_candidate_generator` | `lib/relation_candidates.py` + `aitask_relation_candidates.sh` on t2192's shim; framework signals; ordering and cap; the A.1 candidate replay (D13.1); **then** the offline pipeline replay (D13.2) through the worker's `analyze --dry-run`, with the report written into its plan | 3, 2192 |
| t1981_3 `relations_worker_and_analysis` | spool, enqueue helper, worker, `relations` op in `aitask_codeagent.sh` + config default, analysis prompt, validation, caps, usage ledger + `usage` verb, `relations.*` config + seed, `enable` / `disable`, setup status line + interactive opt-in, `analyze [--dry-run] [--now --wait]` verb, `analysis-state` (digests against the approval stamp; mismatched, missing or stale-read stamps are incomplete), plan_approved jobs read the stamp's `data_commit` snapshot. Built and tested against **fixture candidate output** that follows the doc's candidate contract, so it does not wait on t2192 | 1 |
| t1981_4 `relations_triggers` | create hook (4 sites), plan-approved hooks (Step 7 + `plan-approved-stop.md`, goldens), fold hook, `sweep` (backfill / stale); plans against t1663_3 if landed. Waits for t1981_2 on purpose: no automatic analysis before real candidates exist and the D13.2 report is in | 2 |
| t1981_5 `relations_consumption` | the "related work" procedure at both points (a Step 3 check + entry + planning hand-off, and the target's own Step 8 re-check, with "covered by note" marking); `notify-candidates` with impact-only confirmation (task_ref never confirms; unconfirmed → PULL); Step 8e hybrid with the completeness flow (state, then a wait / static fallback / proceed-with-what-exists choice); `/aitask-note` store-first; disabled / not-analysed wording; goldens; local `pull.jsonl` / `notify.jsonl` ledgers recording each surfaced or offered relation with freshness, confirmation and outcome, plus the Step 8e state and choice (D13.3 input); coordinates with t1663_4 and t2192's skill edits; tested against fixture records, including an incomplete-analysis case, a task-ref-only relation, **direction cases**, and the **cross-host case**. The direction cases:
- forward-only: "S affects X" pushes to X when S lands;
- reverse-only: "X affects S" never pushes when S lands, even with a shared basis in S's diff, and shows as "this task's own relations" in pull;
- symmetric: `coordinates_with` pushes to the other endpoint whichever end S is.

The cross-host case: a stage-2 record from an earlier approval plus a newer stamp written on another host must report `incomplete:inputs_mismatch`, and a missing stamp or stale store read must report `unverifiable` | 1, 3 |
| t1981_6 `obsolescence_layer` | evidence collector, `## Revert Notes` reader, `obsolescence` op + prompt, records, `ait obsolete` verbs, dismissals, landed hook in `aitask_archive.sh`, `--obsolete` reason, display in the related-work check | 3, 5 |
| t1981_7 `relations_tui` | read-only TUI with two tabs, switcher registration, board detail field | 6 |
| t1981_8 `relations_website_docs` | website pages for the CLI verbs, the TUI and the workflow changes (`documentation_conventions.md`, `check_links.py`) | 4, 5, 6, 7 |
| t1981_9 `port_relations_skill_changes` | port the task-workflow / aitask-note / setup-facing skill changes to the Codex / agy (`.agents/`) and OpenCode trees | 4, 5, 6 |
| t1981_10 `relations_retrospective` | D13.3 live review; decides the D5 default, reverse index, roadmap slot, non-Claude headless; **explicitly reassesses stale-relation handling** (are stale results still useful, do they cause misleading notifications, do the refresh triggers or the show-with-marker rule need changing); measures the late-relation gap and decides whether a retained review is needed (only with one resolution identity shared by the immediate and later paths); files follow-ups only if the data justifies them | 8, 9 (transitively all) |

   Only t1981_2, and through it t1981_4, waits on t2192 (which itself waits
   on aitasks_go#93 through `xdeps`). The store (1), worker (3), consumption
   (5), obsolescence (6), TUI (7) and ports (9) proceed without it.

   Priorities: medium (child 10 low). Efforts:
   - high: 1, 3, 5, 6;
   - medium: 2, 4, 7;
   - low: 8, 9, 10.

   Labels: `task_relations` plus the area labels (`task-workflow`, `backlog`,
   `tui`, `documentation`), validated against
   `aitasks/metadata/labels.txt` at creation.
6. **Brainstorm session.** `crew-brainstorm-1981` (root node only) is left as
   is. `ait brainstorm archive` would export the seed proposal into `aiplans/`.
   The final message mentions it.
7. **Next step offered, not run:** refresh `art:trail-task-relations-and-premise`
   (`/aitask-trail`) so the children join it.

### Post-phase (risk mitigations)

1. [independent_design_review] **Timing: after step 2 and before step 3's
   commit.**
   - Spawn one fresh-context review agent (general-purpose). Give it only:
     - the written `aidocs/framework/task_relations.md`;
     - the seed proposal (`ait attach get 1981 task_relations_proposal.md`);
     - the t1981 task body;
     - the four user decisions in this plan's Context.

     Do not give it this plan's reasoning.
   - Ask it to report, as a numbered list with doc line references:
     - (a) any of D1–D13 that does not end in a stated decision with a reason;
     - (b) any contradiction of premises 1–8;
     - (c) any missing user requirement: D1 reader refresh / outbox retention /
       local-only mode and upgrade; D5 setup activation / disabled-state
       reporting / usage measurement;
     - (d) at least 10 sampled `file:line` or code-fact claims checked against
       the tree, each marked holds / wrong.
   - Fix every confirmed finding in the doc. Record findings and dispositions
     in the plan's Final Implementation Notes. Then proceed to step 3.
   - Done when the agent's (a)–(c) lists are empty after the fixes and every
     sampled claim marked wrong has been corrected or removed.

Step 9 (archival) does not run for the parent in this session. The parent stays
open with `children_to_implement` and is archived by the normal
orphaned-parent path when its last child lands.

## Verification

- The doc has a section for each of D1–D13. Every D1 requirement the user
  stated is present:
  - reader refresh;
  - outbox retention and retry;
  - local-only mode and the upgrade.

  The D5 requirements are present: setup activation and disabled-state
  reporting.
- D8 specifies:
  - Step 8e's behaviour for every analysis state (complete, each incomplete
    reason, disabled);
  - digest comparison against the shared approval stamp, with
    mismatched, missing or stale stamps counting as incomplete;
  - the target's Step 8 re-check;
  - the rule that a `task_ref` never confirms impact for PUSH;
  - the PUSH direction guard (`affects` only with `from = S`;
    `coordinates_with` either endpoint) and direction-labelled pull display;
  - the deferred retained review, with its measurement and its
    shared-identity precondition.
- Every `file:line` cited in the doc resolves at the commit. A grep pass checks
  each cited path exists (planned-new paths are marked as such).
- `git show --stat HEAD` for the doc commit lists only
  `aidocs/framework/task_relations.md`.
- Each note returns `NOTE_APPENDED:`.
- `./.aitask-scripts/aitask_ls.sh -v --children 1981 99` lists 10 children
  with the dependency edges in the table.
  `./.aitask-scripts/aitask_query_files.sh plan-file 1981_<n>` resolves for
  every n.
- The parent is `Ready`, unlocked, and carries `children_to_implement`.

## Risk

### Code-health risk: low
- The session changes no framework code. It writes one new doc, task and plan
  files, and three notes; the notes add commits to other task files, one of
  them in another repository · severity: low · → mitigation: none (each note
  carries a decision the recipient's plan depends on)
- The decomposition points future children at hot shared files
  (`aitask_create.sh`, task-workflow Steps 3/7/8e, `aitask_archive.sh`,
  `aitask_codeagent.sh`) that t1663_3, t1663_4 and t2192 also edit · severity:
  low for this plan (each child re-assesses its own risk when it is planned) ·
  → mitigation: none (designed in: Reality-check steps, sequencing notes,
  coordination notes)

### Goal-achievement risk: medium
- The design doc is the deliverable. It may leave a direction unsettled,
  misstate a premise or the user's four decisions, or cite code facts that are
  wrong, and nine children would inherit the error · severity: low (residual,
  addressed by inline post-phase independent_design_review) · → mitigation:
  inline post-phase independent_design_review
- The core bet is unmeasured: that a headless agent applying the inclusion test
  gives useful precision at acceptable cost · severity: medium · → mitigation:
  none (designed in: off by default; the D13.2 offline replay runs before
  triggers exist; t1981_4 depends on it)
- Child plans go stale before they are picked, because neighbours land first
  (t1663_3, t1663_4, t2192, aitasks_go#93) · severity: medium · → mitigation:
  none (designed in: a Reality-check step in every child plan, the fast
  profile's child-plan verify, and the coordination notes)
- The external chain aitasks_go#93 → t2192 can stall candidates and triggers ·
  severity: low · → mitigation: none (designed in: only t1981_2 and t1981_4
  wait; the store, worker, consumption and obsolescence children proceed)
- Asynchronous analysis (settle window, queue, cap, failures) can still be
  incomplete when the source reaches Step 8e, and a relation published late
  could reach no one · severity: low · → mitigation: none (designed in: the
  `analysis-state` report on digests against a shared approval stamp, the wait
  or static-fallback choice, and the target's Step 8 re-check. The remaining
  gap, where both tasks landed first, is measured by the retrospective rather
  than handled by a second notification path that could duplicate notes)
- A relation inferred from a planned change could push a note after an
  unrelated landing · severity: low · → mitigation: none (designed in: PUSH
  requires an impact basis confirmed by the landed diff; a `task_ref` never
  confirms; unconfirmed relations stay pull-only; a deterministic direction
  guard, so `affects` pushes only from its `from` endpoint)
- The store starts empty, so the pull surface shows "not analysed" for the
  backlog until a sweep runs · severity: low · → mitigation: none (designed in:
  explicit state lines; `sweep` backfill in t1981_4)

### Planned mitigations
- timing: post-phase | name: independent_design_review | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement: the design doc may leave a direction unsettled or carry wrong facts into the children | desc: fresh-context agent reviews the written doc against the seed proposal, premises and user decisions, samples 10+ code-fact claims; findings fixed before the doc commit
