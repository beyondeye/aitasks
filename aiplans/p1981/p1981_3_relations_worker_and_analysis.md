---
Task: t1981_3_relations_worker_and_analysis.md
Parent Task: aitasks/t1981_task_relations_and_obsolescence_design.md
Sibling Tasks: aitasks/t1981/t1981_1_relations_store_and_cli.md, aitasks/t1981/t1981_2_relation_candidate_generator.md, aitasks/t1981/t1981_4_relations_triggers.md, aitasks/t1981/t1981_5_relations_consumption.md, aitasks/t1981/t1981_6_obsolescence_layer.md, aitasks/t1981/t1981_7_relations_tui.md, aitasks/t1981/t1981_8_relations_website_docs.md, aitasks/t1981/t1981_9_port_relations_skill_changes.md, aitasks/t1981/t1981_10_relations_retrospective.md
Archived Sibling Plans: aiplans/archived/p1981/p1981_*_*.md
Base branch: main
Output branch: main
---

# t1981_3 — Relations worker, headless analysis and activation

## Context

The execution machinery of `aidocs/framework/task_relations.md`: D5, D7, the
enqueue helper of D4, and the completeness rules of D8. It depends only on
t1981_1, and is tested against fixture candidates, because the real generator
(t1981_2) waits on t2192. No automatic triggers are wired here (that is
t1981_4).

## Steps

0. **Reality check.**
   - Re-read D4, D5, D7 and D8's "Analysis completeness".
   - Re-verify in `aitask_codeagent.sh`: `SUPPORTED_OPERATIONS`, the
     `explore-relay` constants and the Claude-only refusal, the `--headless`
     billing guard, and the `codeagent_config.json` `.defaults` lookup order.
   - Re-verify `report_testmap_state` in `aitask_setup.sh`,
     `aitask_metadata_commit.sh`, and `agentcrew_runner_control.py`
     `start_runner`.
   - Read `aidocs/framework/aitasks_extension_points.md` (setup and new config
     key) and `aidocs/framework/testing_conventions.md`.
1. **Configuration.**
   - The `relations:` block (D5), with `triggers.fold`, in
     `aitasks/metadata/project_config.yaml`.
   - The `seed/` copy carries the block **without** `enabled`: an absent key
     means disabled, and lets setup tell "never asked" from "answered".
   - The `relations` and `obsolescence` defaults (`claudecode/sonnet5_5`) in
     `codeagent_config.json`, seed and project.
   - `ait relations enable|disable`, writing through
     `aitask_metadata_commit.sh`.
2. **`aitask_relations_enqueue.sh <op> <trigger> <id>`.**
   - Never prints to stdout and always exits 0. A log goes to
     `<git-common-dir>/aitask-relations/spool/enqueue.log`.
   - Honours `enabled`, `triggers.<t>` and `AIT_RELATIONS=0`.
   - Coalesces the spool file `(op, task)`.
   - **For `plan_approved`, writes the approval stamp** through the store:
     - `data_commit` = the task-data `HEAD` after the plan commit;
     - the D2-normalized digests of body and plan at that commit.
     - The stamp depends on `relations.enabled` only, not on the trigger
       switches or `AIT_RELATIONS=0`.
     - It is published in the detached part. On failure it is retained in the
       outbox.
   - Starts the worker detached when `flock -n worker.lock` succeeds.
3. **`lib/relations_worker.py`**:
   - It takes the lock, flushes the outbox, then drains jobs following the D5
     per-job steps.
   - Candidates come from `aitask_relation_candidates.sh` when it exists.
     Otherwise the job fails with `CANDIDATES_UNAVAILABLE`, visible in `status`.
     Tests inject a provider.
   - Per-job order: settle and cap → candidates → provider-failure check →
     digests and the `UP_TO_DATE` skip → the zero-candidate shortcut → agent.
     - A provider failure or a missing core source fails the job.
     - A missing optional source goes into `coverage.missing_sources`.
   - **Inputs.** The body is always current from the task-data working tree.
     On a task with a stamp, the plan comes via `git show <stamp
     data_commit>:<plan path>` (stage 2). A task without a stamp is read from
     the working tree (stage 1).
     - Candidates use the same rule.
     - Record `task_created_at` and each candidate's `created_at`. Truncated
       candidates get entries too, and relations to tasks without an entry fail
       validation.
     - Materialize every analysed file into `<job dir>/inputs/`. The prompt reads
       only from there, so the content the agent judges equals the content
       hashed.
     - `approved_at` in the stamp is UTC ISO 8601.
   - Manual-verification tasks are excluded.
   - Zero candidates, with full coverage → an analysed empty record, with no
     agent call.
   - The agent runs under a timeout that kills its process group.
   - The output is parsed from `--output-format json`, validated with the schema
     module, and written through the store.
   - Failure moves the job to `failed/`. A timeout is retried once.
   - Usage goes to the record and to `usage.jsonl`, and the daily cap is
     enforced from the ledger.
4. **The headless operations** in `aitask_codeagent.sh`.
   - `relations` and `obsolescence`: Claude-only refusal for other agents,
     `--print --output-format json`, and prompt files passed by path (not a
     skill).
   - **Read-only by construction**, never by permission grants:
     - `--tools "Read,Glob,Grep"` (the available built-in set);
     - `--strict-mcp-config` with no `--mcp-config` (no MCP servers);
     - `--disallowedTools Bash,Edit,Write,NotebookEdit,WebFetch` as a second
       layer;
     - a never-prompt, never-bypass permission mode.

     Re-verify each flag in `claude --help` at implementation time, check
     whether settings-sourced hooks run under `--print` (restrict
     `--setting-sources` if so), and add a test that a stub prompt requesting a
     write, a Bash command or an MCP tool gets no such tool.
   - They require `--headless`, which the worker passes.
   - Mirror the `explore-relay` billing acknowledgement.
5. **The prompt** `.aitask-scripts/relations/prompts/relations_analysis.md`.
   - The D7 inclusion test, word for word.
   - The vocabulary table, with directions.
   - The impact-basis rule.
   - Two-stage reading, at most 8 full reads.
   - The output schema, with an example.
   - "zero is normal".
   - The description is addressed to the other task's agent and is advisory.
6. **Verbs** in `aitask_relations.sh`:
   - `analyze <id> [--dry-run] [--now --wait <s>] [--over-cap]`. At the cap,
     `--now` without `--over-cap` returns `CAP_REACHED`.
   - `stamp <id>`:
     - computes the normalized digests of body and plan at the task-data
       `HEAD`;
     - writes the stamp into the outbox synchronously (under the outbox lock);
     - prints `STAMP:<plan_sha256>` or `STAMP:disabled`;
     - then detaches the publish and the `plan_approved` enqueue.
   - `plan-digest <id>`: prints `PLAN_DIGEST:<sha>` for the committed plan.
   - `analysis-state <id> --expect-plan <sha>`, implementing the D8 state table
     exactly:
     - `complete` requires both of these:
       - the latest visible stamp's `plan_sha256` equals `<sha>`;
       - a stage-2 record whose plan digest equals `<sha>`, and whose body
         digest equals the current one.
     - Otherwise: `inputs_mismatch`; `unverifiable` (no stamp,
       `stamp_mismatch`, `no_expected_identity`, an unreadable stamp, a stale
       or unreachable store); `pending`; `failed`; `missing`; or `disabled`.
     - Under `AIT_RELATIONS=0`, a note that analysis is off on this host.
   - `usage [--days N]`, and `ledgers --export` (host-tagged JSON lines of the
     local ledgers).
7. **Setup.**
   - `ait setup` prints `RELATIONS:<state>`, plus the enable hint and the cost
     note, after the TESTMAP line.
   - Interactive setup asks once, default No, when the key is absent, and
     writes the answer. Batch setup never asks.

## Verification

Python and bash tests with a stub agent:
- coalescing and the settle window;
- a single worker under concurrent enqueues;
- the cap;
- the process-group timeout;
- invalid output writes nothing;
- the zero-candidate path makes no agent call;
- `--dry-run` writes nothing;
- `--now --wait` bypasses settle and is bounded;
- every `analysis-state` value, including:
  - the cross-host `inputs_mismatch` case (a stamp written by another clone);
  - `stamp_mismatch` (a committed plan newer than the visible stamp);
  - a delayed publish after re-approval: the synchronous outbox write makes the
    new stamp visible locally, so the old one is never accepted;
  - `no_expected_identity`;
  - a fold after approval: the body changed, so the job re-analyses;
- the provider-failure check runs before `UP_TO_DATE`;
- stamp-snapshot reads;
- the silent, always-exit-0 enqueue;
- setup's default `RELATIONS:disabled`.

Then `shellcheck`, and `aitask_skill_verify.sh` if any skill text changed.

## Step 9

Post-implementation per task-workflow Step 9.
