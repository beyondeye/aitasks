---
Task: t1981_6_obsolescence_layer.md
Parent Task: aitasks/t1981_task_relations_and_obsolescence_design.md
Sibling Tasks: aitasks/t1981/t1981_1_relations_store_and_cli.md, aitasks/t1981/t1981_2_relation_candidate_generator.md, aitasks/t1981/t1981_3_relations_worker_and_analysis.md, aitasks/t1981/t1981_4_relations_triggers.md, aitasks/t1981/t1981_5_relations_consumption.md, aitasks/t1981/t1981_7_relations_tui.md, aitasks/t1981/t1981_8_relations_website_docs.md, aitasks/t1981/t1981_9_port_relations_skill_changes.md, aitasks/t1981/t1981_10_relations_retrospective.md
Archived Sibling Plans: aiplans/archived/p1981/p1981_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-11-08 22:17
---

# t1981_6 — Obsolescence layer (verified plan)

## Context

This is the second layer of `aidocs/framework/task_relations.md`, specified in D9, with its record and dismissal defined in D2. It gives each pending task an advisory obsolete assessment: a band, cited evidence and a disposition. The assessment is never auto-actioned. It builds on:

- the store from t1981_1;
- the worker, spool and headless op from t1981_3;
- the related-work check from t1981_5.

All three have landed.

## Reality check (verified 2026-11-08 against HEAD 97a0fb6c3)

- **Schema (`lib/relations_schema.py`):** already defines the `obsolescence` and `dismissals` kinds.
  - `validate_obsolescence` and `validate_dismissal` exist, along with `BANDS`, `DISPOSITIONS` and the `landed` trigger.
  - Evidence rows are `{id, kind, detail, source}`, with a closed key set and no extra keys.
  - No writer exists yet, so tightening value checks (unique ids, string fields) is safe. Adding keys is not, under the closed-validator rule.
- **Codeagent:** `aitask_codeagent.sh` already supports `invoke obsolescence` (read-only argv, Claude only).
- **Worker (`lib/relations_worker.py`):**
  - It hardcodes `OP = "relations"`, `OPS_IMPLEMENTED = ("relations",)`, and uses OP in `analyse()` (the guards, `admit_unguarded`, the preview) and in `process_job`'s `log_job`.
  - Recovery already reads `op` from the entries.
  - The spool is op-keyed (`key(op, tid)`). Cap accounting is per op (`calls_today(op)`), and `job_state(tid, op="relations")` is op-scoped, so an obsolescence job never pollutes `ANALYSIS:`.
- **Consumers:** `relations_consume.end_state()` already classifies landed / dropped / implementing / pending. Reuse it.
- **Premise engine (t1663_1) has landed.** `aitask_premise_stale.sh check <task_file>` always exits 0 and ends with `DECISION:FRESH|ASK_STALE|SKIP` (this task currently reads `SKIP`, `no_stored_baseline`). Per the note from t1663_1, path fields are percent-encoded; we only consume `DISPLAY:` and `DECISION:`.
- **`aitask_archive.sh`:** `--superseded` adds `archived_reason: superseded` with an awk `print "archived_reason: …"`. That exact needle is pinned by `tests/lib/docs_vocabulary_scan.py` `OTHER_WRITERS` and by test 12c, so the awk shape must keep that substring. `main` dispatches to `archive_child` / `archive_parent`, and `gate_guard` blocks gated tasks unless `--ignore-gates` is passed.
- **`## Revert Notes` template:** lives in `.claude/skills/aitask-revert/SKILL.md.j2` and has the fields `**Reverted by:** t<id>`, `**Date:**`, `**Type:** Complete|Partial…`, `**Areas reverted:**`, and optionally `**Areas kept:**`. No script reads it today.
- **Origin resolution:** `lib/followup_origin.resolve_detailed(meta)` gives `verifies` as exact, `anchor` as topic, and degrades on malformed entries.
- **Path extraction:** `lib/plan_paths.extract()` and `tracked_sets()` provide extraction and classification. A rename-aware `git log -M --name-status --diff-filter=DR -z HEAD` pass takes 0.29 s over 2892 commits, so caching it per HEAD is cheap.
- **Whitelist:** `aitask_obsolete.sh` is not invoked from any skill. The pick-time display goes through the existing `aitask_relations.sh related-work`. Per `aitasks_extension_points.md` ("whitelist applies ONLY to helpers invoked from a skill"), it gets **no** permission-touchpoint entries. It does get an `ait obsolete` dispatcher entry, because it is a human-typed command. This deviates from the old plan's step 8 and is stated here on purpose.

## Design decisions (stated, not discovered)

1. **Signal rows vs context rows.** The following rows are **context**:
   - `age`;
   - `premise` with a non-`ASK_STALE` decision (`FRESH` / `SKIP` / `unavailable`);
   - `origin_state` = `archived:completed`;
   - **every path row** (`path_deleted`, `path_renamed`, `path_ambiguous`).

   Every other row is **signal**: `origin_state` that is not completed, `superseded_by`, `duplicate_of`, `affected_by_landed`, and `premise` `ASK_STALE`.
   - A completed origin is the normal state of a follow-up, not obsolescence evidence. An archived-with-reason, folded, deleted or reverted origin is signal.
   - Path rows are factual file events whose attribution to the task's **current** citation is unproved (decision 9).
   - **Invariant: scoring inputs = digest inputs = signal rows.** Context rows are **for human inspection only**. They are printed live by `ait obsolete evidence`, and are **never** in the prompt, in `evidence.json`, in the record's `evidence[]` or among the citable ids. Otherwise a context row could shape a recommendation (e.g. "refresh A→B") that its changing (B→C) would never invalidate, because UP_TO_DATE keys on the digest. The task's body and plan, which the assessor also reads, are covered by the record's body/plan digests.
   - "Only `age` evidence → band `none`, no LLM" generalises to "no signal rows → `none`, no LLM", decided in code.
2. **`evidence_digest` covers the signal rows only**, as sorted `(kind, detail, source)` with ids excluded. Otherwise `age` (which changes daily) would resurface every dismissal every day.
3. **Path history is over HEAD only, not `--all`.** A path absent at HEAD counts as deleted only if HEAD's own history deleted it. History lives in the code repo, and `aitasks/` / `aiplans/` tokens are skipped.
4. **Incomplete evidence is never `none`.** For example, an unreadable origin index, a failed git history, or a premise tool error. The collector reports `incomplete[]`, and the worker fails the job with `EVIDENCE_INCOMPLETE:<reason>`. It never writes an all-clear.
5. **The cap is per op.** Obsolescence uses the spool's existing per-op accounting with the same `relations.max_jobs_per_day`. This is documented in the doc's new API section.
6. **The landed fan-out runs in the detached part.** Computing relations(landed) needs a store read, which may fetch, so it never runs inside `aitask_archive.sh`.
7. **`--obsolete` and `--superseded` are mutually exclusive.** `--obsolete` keeps the gate guard (same as `--superseded`). `review` offers `--ignore-gates` only after a second explicit confirmation.
8. **`review` acts only on an explicit choice letter.** Empty or unknown input re-prompts, and EOF ends the review with no action.
9. **Path rows are context in v1** (Step 1). Each one reports the factual end of the cited name's latest lifetime: chains are followed forward in sequence, so a reused intermediate name never splices chains, and `lifetimes=<n>` is shown. Path rows **never** assert obsolescence, because neither `created_at` nor the oldest task-data mention dates the current reference. This deliberately yields fewer automatic warnings. Reconstructing the citation's history is deferred to a follow-up.
10. **Sweeps rotate by last attempt** (Step 6), never by id. A missing or changed assessment gets a one-attempt boost, so neither a later task nor an assessed one can be starved by a persistent failure.
11. **A warning needs an explanation:** a non-`none` band or a non-`keep` disposition requires a reason backed by evidence ids (Step 3, enforced in the schema too).

## Steps

### Pre-phase (risk mitigations)

1. [baseline_worker_suite] Before editing any code, run and record the exact per-file pass/fail counts and failing-test names for `tests/test_relations_worker.py`, `tests/test_relations_consume.py`, `tests/test_relations_store.py`, `tests/test_relations_cli.sh`, `tests/test_relations_enqueue.sh`, `tests/test_docs_vocabulary_coverage.sh` and every `tests/test_archive_*.sh`. Do this on the unmodified HEAD, without stashing (the worktree carries unrelated in-flight edits to contribution scripts, which do not touch these files). After implementation, compare the failing-test **name sets** per file against this baseline; a pass-count comparison alone is not enough.

### Main implementation

1. **`lib/obsolescence_evidence.py` (new)**
   - `class EvidenceResult(rows, incomplete, digest, signal_count)`, plus `is_signal(row)` and `digest(rows)` (sha256 over the JSON of the sorted signal `(kind, detail, source)` triples).
   - `collect(root, store, snap, tid, body_raw, plan_raw, *, now=None, premise_cmd=None) -> EvidenceResult`. It assigns ids `<kind>:<n>` after a deterministic sort.
   - **Path rows:**
     - Tokens come from `plan_paths.extract()` over `normalize_body(body)` and `normalize_plan(plan)`. Skip malformed tokens and tokens under `aitasks/` and `aiplans/`. Strip `./`.
     - `tracked, _ = plan_paths.tracked_sets(root)`. A tracked token yields no row. An untracked token with exactly one tracked file ending in `/<token>` is a relative reference and yields no row.
     - Otherwise, resolve the token's history: an exact path first, then a unique suffix match among the paths that have history. A suffix matching several paths yields the context row `path_ambiguous`.
     - **Ordered event history, not two maps:**
       - One pass of `git -C root log --topo-order -M --name-status --diff-filter=ADR -z --format=%x00C%H%x00%ct HEAD` builds an **ordered** event list. Each event is `(seq, sha, ct, status, src, dst)`, with `seq` ascending oldest-to-newest. A is an addition, D a removal, and R both a removal of `src` and an addition of `dst`.
       - Per path, it indexes `additions[path]` and `removals[path]` as seq-sorted lists.
       - The list is cached at `.aitask-cache/obsolescence/history-<HEAD>.json` (atomic write; files for other HEADs pruned). A git failure goes to `incomplete`.
     - **Latest-lifetime fact, followed forward in sequence:**
       - The fact reported is how the **latest** lifetime of `T` ended: `T`'s last removal by seq, D or `R T→X`.
       - **Following a rename** `R T→X` at seq `s` continues with `X` from `s` onward only, meaning `X`'s first removal with seq greater than `s`:
         - none, and `X` tracked at HEAD → `path_renamed`;
         - D → `path_deleted`;
         - R → follow again.

         A reused intermediate name therefore never splices in an older or unrelated chain: "B deleted, then C→B later" ends the A→B chain at the deletion. A step that revisits the same `(path, seq)` (a cycle) stops and yields `path_ambiguous`.
       - An addition of `T` after its last removal means `T` should be tracked at HEAD. Since it is not, the history is inconsistent (merge interleaving), giving `path_ambiguous`.
       - `lifetimes=<n>` (the number of additions of `T`; at least 1 when history starts with a removal) is part of the detail. Examples: `"A -> B (renamed in <sha12> <date>; lifetimes=1)"`, `"A deleted in <sha12> <date> (lifetimes=2)"`.
     - **All path rows are CONTEXT in v1. They are never signal and are not in the digest.**
       - A row records a factual file event. Nothing here proves that the task's **current** citation refers to the lifetime that ended. A citation can be removed and reintroduced later, and a task written after a single deletion may be proposing to recreate the file. Neither `created_at` nor the task-data history dates the current reference reliably.
       - So a path row never triggers an LLM call or resurfaces a dismissal. It is shown live by `ait obsolete evidence` for human inspection only, and is never given to the assessor (decision 1 invariant).
       - Attributing a path event to the current citation is deferred to a follow-up task (see "Deferred").
     - A token with no removal events at all is a planned-new or phantom file and yields no row.
   - **Origin rows:**
     - Parse the task's frontmatter with `task_yaml.parse_frontmatter` and resolve `followup_origin.resolve_detailed`. Each origin id (excluding self) is looked up through `store.index`.
     - `exists() is None` goes to incomplete. `False` is `deleted`.
     - `folded_into` set is `folded into t<N>`.
     - An archived task with `archived_reason` is `archived:<reason>`.
     - An archived task that is Done is `archived:completed@<date>` (context), **unless** it carries `## Revert Notes`, in which case it is `reverted (<Type>) by t<N> on <date>` (signal).
     - An active origin with `## Revert Notes` is also `reverted`.
     - The source is `frontmatter:verifies` or `frontmatter:anchor` (the quality).
   - **`parse_revert_notes(text) -> list[dict]` (new public function):** finds each `## Revert Notes` section and reads the bullet fields `reverted_by`, `date`, `type` (`Complete` / `Partial`, first word), `areas_reverted` and `areas_kept`. It is tolerant of extra text after the type.
   - **Store relation rows**, over `store.relations(me, snap)` with each other end's `rc.end_state()`:
     - `supersedes` with the other end as `from` → `superseded_by`;
     - `duplicates` → `duplicate_of`;
     - `affects` with the other end as `from`, whose end is `landed` with `at` after the task's `created_at` → `affected_by_landed`.
     - Each detail is `"<other> (<end label>, <freshness>): <description[:200]>"`, and the source is `store:records/t<record_task>.json`.
   - **Premise row:** run `aitask_premise_stale.sh check <task_file>` from root, bounded to 60 s through `bounded_run`. The seam `AIT_OBSOLESCENCE_PREMISE_CMD` substitutes the command in tests.
     - A missing script gives the detail `unavailable`.
     - A non-zero exit or no `DECISION:` line goes to incomplete.
     - Otherwise the detail is `"<DECISION>: <DISPLAY>"`.
     - Archived tasks get no premise row.
   - **Age row:** `days since <updated_at|created_at> (weak prior)`, using integer days. It is a context row.

2. **`.aitask-scripts/relations/prompts/obsolescence_assessment.md` (new)**, modelled on `relations_analysis.md`.
   - It covers:
     - the assessor's role, and that it is read-only;
     - that D9 is advisory, and "no evidence → no obsolescence";
     - the band definitions;
     - the dispositions `keep|refresh|fold_into|drop`, with `fold_into` requiring a `fold_target` from the given candidate refs;
     - that every reason must cite evidence ids from the given list, and that the judgement rests **only** on the given evidence rows and the task's body and plan. It reads no repository file outside the input directory, as in `relations_analysis.md`;
     - that `refresh` fits premise drift (`ASK_STALE`) and `affected_by_landed`;
     - that `drop` needs strong signal: a reverted or obsolete origin, or a supersession by a landed task.

     There is no path wording: path rows are not scoring inputs.
   - Output is **exactly one JSON object** `{band, reasons:[{text, evidence_ids}], disposition, fold_target?}`.
   - The worker appends a "This job" block: the task ref; file paths for `body.md`, `plan.md` and `evidence.json`; the **signal-row** evidence table; and the allowed fold targets (the pending ends of `duplicate_of` / `superseded_by` rows plus the task's family).

3. **Worker job for `obsolescence` (`lib/relations_worker.py`)**
   - `OPS_IMPLEMENTED = ("relations", "obsolescence")` and `OBS_OP = "obsolescence"`. `OBS_PROMPT_TEMPLATE` is the new file.
   - **Refactor, behaviour-preserving:**
     - Extract the paid-launch tail of `analyse()` (preview reconcile, guard scan, switch re-read, `admit_unguarded`, ownership phases, `run_bounded`, `parse_agent_output`, settle) into `_paid_invocation(root, sp, job, op, tid, prompt, inputs_dir, cfg, dry_run, log, build)`. `build(payload, usage) -> rec` raises `JobFailed` / `SchemaError`, which settles as `invalid_output`.
     - `analyse()` calls it with `op=OP`. `process_job` uses `job["op"]` for `log_job` and dispatches `analyse` or `analyse_obsolescence`. `cmd_analyze`'s dry run stays relations-only.
   - **`analyse_obsolescence(root, sp, job, *, dry_run=False, log=None)`:**
     1. Run the switches and build the Store. Apply the cap pre-check with `OBS_OP`. Look up the task; it fails with `TASK_NOT_FOUND` / `IDENTITY_UNKNOWN`.
     2. The outcome is `EXCLUDED` for `manual_verification`, for any non-active (archived) task, or for status `Done` / `Folded` / `folded_into`.
     3. Take one `snap`, then the stamps and `task_inputs()` (the D5 plan rule). Stage is 2 if the task is stamped, else 1.
     4. Run `collect(...)`. A non-empty `incomplete` fails the job with `EVIDENCE_INCOMPLETE:<first reason>`.
     5. **UP_TO_DATE:** the existing obsolescence record passes the identity check, has the same body / plan digests and `evidence_digest`, and has a stage at least as high.
     6. With zero signal rows, the record is `band none`, `reasons []`, `disposition keep`, zero usage, and no launch.
     7. Otherwise, materialize `work/<run>/inputs/{body.md,plan.md,evidence.json}`, with `evidence.json` holding **signal rows only**. Compose the prompt from those same rows and call `_paid_invocation(op=OBS_OP)`. The record's `evidence[]` is the same signal-row list, so the schema's "reason ids ⊆ evidence ids" check also refuses any context id.
     8. **`canonical_obsolescence(payload, ids, fold_targets)`:**
        - The key set must be `{band, reasons, disposition}` plus an optional `fold_target`.
        - **An explanation is required for any warning or action.** If `band != none` **or** `disposition != keep`, `reasons` must be non-empty.
        - `band == none` requires `disposition == keep`.
        - Every reason needs non-empty `text` and at least one `evidence_ids` entry, each a **signal-row** id from this job's prompt. A context-row id (path, age, non-stale premise, completed origin) is unknown here.
        - `fold_target` is canonicalised and must be in `fold_targets`, and it is required if and only if the disposition is `fold_into`.
        - Any violation is `INVALID_OUTPUT:…`; nothing is written and the call is settled `invalid_output`.

        The same "explanation required" rule goes into `relations_schema.validate_obsolescence`, so no writer or reader accepts an unexplained warning.
     9. `build_obs_record`, then `rs.validate("obsolescence", …)`, then `store.write(obsolescence/t<id>.json)`, reusing the `_write` mapping (generalised to take a kind).
   - **Landed fan-out:** `landed_targets(root, tid) -> list[tid]`.
     - It collects the pending ends (`end_state` kind in `pending|plan_holder|implementing`) of `store.relations(landed)`, plus the active tasks whose `followup_origin` origins include the landed id.
     - It excludes `manual_verification`, folded tasks and the landed task itself, and returns the list sorted.
     - In `cmd_enqueue`: `op == "obsolescence" and trigger == "landed"` → for each target, `enqueue_job(root, OBS_OP, "landed", t)`, logging `LANDED_FANOUT:t<id>|<n>`. The `trigger_enabled("landed")` switch is honoured by `enqueue_job`.
   - **Schema tightening (`relations_schema.validate_obsolescence`):** evidence ids must be unique, and `kind` / `detail` / `source` must be strings. Reason `text` must be a non-empty string with `evidence_ids` as a list of strings. No key changes.

4. **Landed trigger (`aitask_archive.sh`)**
   - Add the global `LANDED_IDS=()`. Append the task id when an archival completes, in both `archive_parent` and `archive_child`, and the parent id when the child flow archives the parent. Skip when `DRY_RUN`.
   - In `main`, after the archive: `fire_landed_triggers` runs only when `SUPERSEDED` and `OBSOLETE` are both false. For each id, it re-reads the archived file and fires only if `archived_reason` is empty and `folded_into` is empty: `"$SCRIPT_DIR/aitask_relations_enqueue.sh" obsolescence landed "$id" >/dev/null 2>&1 || true`. The call is silent and never changes the exit status.

5. **`aitask_archive.sh --obsolete`**
   - Add `OBSOLETE=false` and the flag. `--superseded` together with `--obsolete` is a `die`.
   - Generalise the insert to `ARCHIVED_REASON` (`superseded` / `obsolete`) as `awk -v r="$ARCHIVED_REASON" '/^status:/{print; print "archived_reason: " r; next}1'`. This keeps the pinned `print "archived_reason: ` needle.
   - Add the help line, and update the header comment.
   - Update `website/content/docs/development/task-format.md` (`archived_reason` values `superseded`, `obsolete`; written by `ait archive --superseded` / `--obsolete`, the latter via `ait obsolete review`). Check `test_docs_vocabulary_coverage.sh` still passes, and update its fixture or registry if it enumerates values.

6. **`aitask_obsolete.sh` + `lib/obsolete_cli.py` (new) + `ait obsolete` dispatch**
   - **Output shape:** every output starts with `RELATIONS_STATE:` and `STORE:`. Free text is percent-encoded with `rc.enc`. A disabled project reads local data only, through `_snap`. Add `obsolete` to the `ait` update-check skip list and the help text.
   - **`evidence <id> [--json] [--no-fetch]`:** `EVIDENCE:<id>|<kind>|signal|context|<source>|<detail>`, then `INCOMPLETE:<reason>`, `SIGNAL_ROWS:<n>` and `EVIDENCE_DIGEST:<sha>`. It works while the project is disabled, since it is static and makes no LLM call.
   - **`ls [--min-band low|medium|high] [--all]`:** prints `OBSOLETE:t<id>|<band>|<disposition>[:<target>]|<inputs fresh|stale>|reasons=<n>[|dismissed]`.
     - The default `--min-band` is `low`.
     - It shows only active, identity-valid tasks.
     - A dismissal whose `evidence_digest` equals the record's hides the task, unless `--all` is given.
     - It prints `OBSOLETE:0` when nothing is listed.
   - **`show <id>`:** prints the record: band, disposition, reasons with their cited rows, the scoring (signal) evidence rows, run and usage. It also prints the dismissal state and input freshness, and a hint line `CONTEXT:see ait obsolete evidence <id>`, since context rows are live facts and are not stored. Otherwise `NO_ASSESSMENT:t<id>`.
   - **`dismiss <id> [--note <text>]`:**
     - It requires a record (exit 1 with `NO_ASSESSMENT:`).
     - It writes `dismissals/t<id>.json` with `{task, task_created_at, at, by, evidence_digest, note}` through `store.write`. `by` is the userconfig email, else `git config user.email`, else the host name.
     - It prints `DISMISSED:t<id>|<digest12>` plus the flush reports, and exits 3 on `RETAINED:`.
   - **`review`** (bash loop over `ls`):
     - For each item it runs `show`, then prompts `[o]pen [f]old [a]rchive-obsolete [d]ismiss [s]kip [q]uit`. Each action needs that explicit letter.
     - `o` opens the task in `${PAGER:-less}`.
     - `f` asks for the primary, defaulting to `fold_target`. A primary equal to the item is refused (`FOLD_REFUSED:is_self`) before any helper runs.
       - **Validate both ends by parsing the lines.** `aitask_fold_validate.sh` exits 0 for every content outcome, so its exit status authorises nothing. Two calls:
         - `aitask_fold_validate.sh <primary>` must print exactly `VALID:<primary>:<path>`. This is the same eligibility `/aitask-fold` applies to every task it folds: Ready/Editing, no pending children.
         - `aitask_fold_validate.sh --exclude-self <primary> <id>` must print `VALID:<id>:<path>`.
       - Any `INVALID:<x>:<reason>`, a missing line or an unexpected line becomes `FOLD_REFUSED:<x>|<reason>`, with no mutation.
       - `WARNING:<id>:xdeps_loss:…` lines are shown, and the confirmation question names them.
       - After the explicit `y` confirmation, **both validations are re-run** immediately before mutating (the foldee may have changed while the prompt was open). Only then does the existing sequence run: `aitask_fold_content.sh <primary_file> <id_file> | aitask_update.sh --batch <primary> --desc-file -` → `aitask_fold_mark.sh --commit-mode fresh <primary> <id>`. Each step's failure stops the sequence and is reported.
     - `a` requires `y`, then runs `aitask_archive.sh --obsolete <id>`. If that exits 2 with `GATE_PENDING:`, the user is asked again before retrying with `--ignore-gates`.
     - `d` asks for an optional note, then runs `dismiss`.
     - Anything else re-prompts. EOF prints `REVIEW_ENDED:eof`.
   - **`sweep [--budget N]`:**
     - It requires the project enabled and the host on (`DISABLED:` / `HOST_OFF:`, exit 1).
     - It walks active, non-MV, non-folded tasks, skipping tasks whose obsolescence job is already pending.
     - **Fair rotation, one key for every task.** No group has unconditional priority. A permanently failing task must not monopolise a bounded sweep, and evidence such as a newly deleted path or a reverted origin can change while body and plan do not.
       - **`last_attempt(t)`** is the time of the newest `kind:"job"` row with `op == "obsolescence"` for `t` in this host's `usage.jsonl`. Every terminal outcome writes one, `UP_TO_DATE` and every `FAILED:` included. A task never attempted counts as epoch.
       - **`boosted(t)`** is true when the task has no record, or its body / plan digests differ from the record's, **and** no attempt has happened since. That means no record and `last_attempt` is epoch, or `last_attempt ≤ record.run.at`. **A boost is spent by one attempt**: a failed or unchanged attempt clears it, and the task then rotates like every other.
       - **The order** is `(not boosted, last_attempt, id)` ascending.
     - Each processed job recomputes the evidence, so a changed digest is re-assessed. Every attempt moves its task to the back. A bounded sweep therefore revisits every task within ⌈N / budget⌉ sweeps after its boost, whatever fails.
     - It enqueues `obsolescence sweep` jobs up to the budget (default: `max_jobs_per_day - calls_today(obsolescence)`, minimum 0). It prints `ENQUEUED:t<id>` and `SWEEP:<n>|budget=<b>|candidates=<N>`.

7. **Pick-time display**
   - In `relations_cli.cmd_related_work`, for `--point pick` only: when the task's own obsolescence record is identity-valid, has band `medium` or higher and is not dismissed at its digest, emit `OBSOLESCENCE:<band>|<disposition>[:<target>]|<inputs fresh|stale>` plus up to three `OBSOLESCENCE_REASON:<enc text>` lines. These go before `RELATED_WORK:` / the items, and are also in `--json` as an `"obsolescence"` field. Nothing is emitted otherwise.
   - Document the lines in `.claude/skills/task-workflow/related-work-check.md` ("Reading the output" and `## Pick-time check` step 1). They are advisory and display-only: "show the band, disposition and reasons; point at `ait obsolete show <id>`; never act on it". `SKILL.md` is unchanged, so no golden regeneration is needed. Run `aitask_skill_verify.sh` anyway.

8. **Docs (current-state)**
   - Add an **"Obsolescence API"** subsection to `aidocs/framework/task_relations.md` D9, covering: the evidence kinds with the signal/context split, the digest rule, the line protocols of `ait obsolete`, the landed fan-out, the per-op cap, `EVIDENCE_INCOMPLETE`, and the `OBSOLESCENCE:` pick lines. t1981_7 (TUI) and t1981_8 (website) build on it.
   - Update the comment of `aitask_relations_enqueue.sh` (callers now include `aitask_archive.sh`).
   - Do **not** touch other agent trees; t1981_9 owns the ports.

9. **Deferred.** Create one follow-up task (`issue_type: feature`, anchor 1981): "obsolescence: attribute path events to the current citation". It covers dating the citation from task-data history, removed-and-reintroduced citations, planned recreations, and promoting attributable path rows to signal. Create it at Step 8, after the commit.

10. **Step 9 (post-implementation)** follows task-workflow Step 9: commit, archival, merge to main.

### Post-phase (risk mitigations)

1. [measure_backlog_evidence] Run `./.aitask-scripts/aitask_obsolete.sh evidence <id> --no-fetch` for every active non-`manual_verification` task in this repository. Record exact counts in the plan's Final Implementation Notes:
   - tasks scanned;
   - tasks with ≥1 signal row (each of these would cost one LLM call in a sweep);
   - signal rows by kind;
   - tasks reporting `INCOMPLETE:`, with their reasons;
   - total wall time.

   If more than 25% of tasks carry a signal row, list the dominant kind and reassess its signal/context classification before archiving.

## Verification

- **`tests/test_obsolescence_evidence.py` (new),** over a scratch git repo:
  - deleted vs renamed (including a two-hop chain) vs relative (`b/one.py` → `a/b/one.py`), with planned-new and `aitasks/` tokens producing no rows;
  - **lifetime fixtures:**
    - (a) reused source name: A→B, A recreated, the new A deleted → the latest lifetime's fact `path_deleted … lifetimes=2`;
    - (b) reused intermediate name: A→B, B deleted, later C→B → the A row reports the deletion, never "renamed to B";
    - (c) a rename cycle A→B→A, then A deleted → it terminates;
    - (d) an ambiguous suffix → `path_ambiguous`;
  - **path rows never assert obsolescence.** Each case must report its path rows as context, with `SIGNAL_ROWS:0`, an unchanged digest and band `none` without an agent call in the worker test:
    - a citation removed and reintroduced around a rename and recreation;
    - an uncommitted planned recreation after a single deletion;
    - a plain single deletion;
  - the history cache keyed per HEAD (a second call does not re-run git, verified with a seam counter or by mtime);
  - `parse_revert_notes` on Complete and Partial templates; a reverted origin (archived, with notes) as signal; archived-superseded, folded and deleted origins; a completed origin as context;
  - `superseded_by` / `duplicate_of` / `affected_by_landed` rows from store records written into a local-only store;
  - premise rows: `unavailable`, `SKIP` (context) and `ASK_STALE` (signal), all through the seam; premise exit 1 → incomplete;
  - the digest is stable under row reordering and under a changed `age`, and changes when a signal row changes.
- **`tests/test_obsolescence_worker.py` (new),** reusing the `WBase` fixture from `test_relations_worker.py`, with `stub_agent.py` extended by a `"payload"` override:
  - only context rows → `none`, zero launches;
  - a signal row with a valid payload → the record is validated and written;
  - a reason citing an unknown id → `FAILED:INVALID_OUTPUT`, nothing written, the call settled `invalid_output`;
  - an unexplained warning (`band:high, disposition:drop, reasons:[]`) and `band:none, disposition:drop` → both rejected the same way, plus a schema unit test that `validate_obsolescence` refuses them;
  - **context rows are not scoring inputs:**
    - (a) A task with a `duplicate_of` signal row and a `path_renamed` context row gets an assessment. `prompt.md`, `evidence.json` and the record's `evidence[]` contain no path row. A stub payload citing the path row's id is rejected as `INVALID_OUTPUT`, with nothing written.
    - (b) The cited path is then renamed again (B→C) with body, plan and signal rows unchanged. The next job's `prompt.md` and `evidence.json` are **byte-identical** to the first job's, so `UP_TO_DATE` is correct: no scoring input changed. `ait obsolete evidence` shows the new path fact.
  - `fold_into` without a target, or with a non-allowed one → failure;
  - `UP_TO_DATE` on a re-run;
  - an archived task → `EXCLUDED`;
  - `EVIDENCE_INCOMPLETE`;
  - the landed fan-out enqueues the pending related tasks and origin children, and skips MV, archived and self;
  - the obsolescence cap is independent of the relations cap.
- **CLI (in the same file, through subprocesses of `aitask_obsolete.sh`):**
  - `dismiss` hides the task from `ls` until a new record with a different digest is written, and `--all` shows it;
  - `review` with piped stdin: EOF → no action; `x\ns\n` → re-prompt then skip, nothing written; `d\n\n` → dismissal written;
  - **review fold cases** (task files and the git index compared before and after; nothing mutated in any case):
    - the destination is Implementing → `FOLD_REFUSED:<primary>|status_Implementing`;
    - the destination equals the item → `FOLD_REFUSED:is_self`;
    - the foldee became ineligible between the prompt and the confirmation → the re-validation refuses. This is simulated through the test-only seam `AIT_OBSOLETE_REVIEW_PRE_MUTATE_HOOK=<cmd>`, which `review` runs after the `y` and before the re-validation; the test's hook flips the foldee to `Implementing`;
    - a valid fold: content merged and `folded_into` set;
  - `sweep` respects `--budget` and `DISABLED:`;
  - **failure starvation:** one task whose evidence permanently fails (the premise seam exits 1, so it stays unassessed) plus two previously assessed tasks, with `--budget 1`. Each sweep's job is run; within 3 sweeps both assessed tasks are re-attempted. A control asserts that a "no record first" group rule would have picked the failing task every time;
  - **sweep rotation:** three tasks, all with up-to-date records, and `--budget 1`. Between sweeps, the third task's origin is archived as `superseded` (a signal change); its body and plan are unchanged. Each sweep's job is run. Within at most 3 sweeps the third task is re-assessed and its record carries the new `origin_state` row and a new digest. A control asserts the old id-ordered prefix rule would have picked task 1 every time.
- **`tests/test_archive_obsolete.sh` (new),** with the scaffold copied from an existing `test_archive_*.sh`:
  - `--obsolete` writes `archived_reason: obsolete`, and `--superseded --obsolete` dies;
  - a normal archive appends `ENQUEUE:obsolescence|landed|t<id>|SKIPPED:disabled` to the scratch repo's `enqueue.log` (bounded wait);
  - `--superseded` / `--obsolete` add no such line;
  - an enqueue helper replaced by `exit 1` still lets the archive exit 0.
- **`tests/test_relations_consume.py`:** an `OBSOLESCENCE:` line appears for a `medium` record at `--point pick`, and is absent for a `low` record, a dismissed record and `--point review`.
- **Regression:** `test_relations_worker.py`, `test_relations_store.py`, `test_relations_consume.py`, `test_relations_cli.sh`, `test_relations_enqueue.sh`, `test_codeagent_relations.sh`, `test_docs_vocabulary_coverage.sh`, and the archive tests (`test_archive_*.sh`).
- `shellcheck .aitask-scripts/aitask_obsolete.sh .aitask-scripts/aitask_archive.sh`; `./.aitask-scripts/aitask_skill_verify.sh`; `cd website && python3 check_links.py --build`, because `task-format.md` changed.

## Risk

### Code-health risk: medium
- Extracting `analyse()`'s paid-launch tail into a shared `_paid_invocation` touches load-bearing admission and crash-recovery code. A behaviour change there would mis-account calls or orphan agents · severity: medium · → mitigation: inline pre-phase baseline_worker_suite
- `aitask_archive.sh` gains a call on every archive, a hot path. It is detached and `|| true`, but a regression there blocks every task closure · severity: low · → mitigation: inline pre-phase baseline_worker_suite

- Lifetime-ordered path history, sweep rotation and the two-ended fold validation (added after plan review) widen the surface. Each has a dedicated fixture or control in Verification · severity: low · → mitigation: inline pre-phase baseline_worker_suite

### Goal-achievement risk: medium
- The signal/context split and the path-history rules are unmeasured heuristics. Too loose means many paid LLM calls per sweep; too strict means real obsolescence is missed · severity: medium · → mitigation: inline post-phase measure_backlog_evidence

### Planned mitigations
- timing: pre-phase | name: baseline_worker_suite | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health (worker refactor, archive hot path) | desc: record per-file failing-test name sets of the relations and archive suites on unmodified HEAD, compare after implementation
- timing: post-phase | name: measure_backlog_evidence | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement (heuristic signal rate / sweep cost) | desc: run `ait obsolete evidence` over the live backlog and record exact signal counts per kind in Final Implementation Notes
