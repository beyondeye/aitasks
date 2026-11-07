---
priority: medium
effort: high
depends: [t1981_1]
issue_type: feature
status: Implementing
labels: [task_relations, codeagent, setup]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1981
created_at: 2026-11-04 15:39
updated_at: 2026-11-07 18:48
---

## Context

Child of t1981. Design: `aidocs/framework/task_relations.md`. **Read D4 (the
enqueue helper only), D5, D7 and the "Analysis completeness" part of D8.**

This child builds the machinery that turns a task into a relations record:
- the spool and the single worker;
- the headless `relations` operation and its prompt;
- validation, caps and usage accounting;
- configuration and setup activation;
- the approval stamp and the completeness state that Step 8e will read.

It depends only on the store (t1981_1). It does **not** wait for the candidate
generator (t1981_2, which waits on t2192). Build and test it against **fixture
candidate output** that follows the D6 contract (source-tagged evidence rows,
`PROVIDER:` line, `TRUNCATED:`).

No trigger is wired here: hooking into task creation and plan approval is
t1981_4. Analysis runs only through `ait relations analyze`.

## Scope

1. **`aitask_relations_enqueue.sh <op> <trigger> <task_id>`**:
   - always exits 0, never writes to stdout;
   - checks `relations.enabled`, the per-trigger switch and `AIT_RELATIONS=0`;
   - writes a coalescing spool file per `(op, task)` (a later trigger keeps the
     higher stage);
   - starts the worker detached when `worker.lock` is free. All of its work,
     including the stamp publish, happens in the detached part, and never
     blocks the caller;
   - **for `plan_approved`, writes the approval stamp** `approvals/t<id>.json`
     (`approved_at`, `data_commit`, `body_sha256`, `plan_sha256`) through the
     store's outbox.
     - The stamp depends on `relations.enabled` only. The per-trigger switches
       and `AIT_RELATIONS=0` do not suppress it.
     - A failed publish stays in the outbox and shows in `status`.
2. **`lib/relations_worker.py`**: the per-job steps of D5, in this order.
   1. Settle window, daily cap.
   2. Candidates via `aitask_relation_candidates.sh`. Until t1981_2 lands, that
      script does not exist: the worker reports `CANDIDATES_UNAVAILABLE` and
      fails the job visibly. Tests inject a fixture provider.
   3. A provider failure or a missing core source fails the job; never write an
      empty analysed record from it. A missing optional source is recorded as
      `coverage.missing_sources`. This comes **before** the `UP_TO_DATE`
      check.
   4. Input digests, then the `UP_TO_DATE` skip (identical digests at the same
      or a higher stage).
   5. Full coverage with zero candidates → an analysed record with
      `relations: []` and no LLM call.
   6. The headless op under a process-group timeout.
   7. Validate, then write through the store.

   Also:
   - `failed/` with the reason; one retry, for timeouts only.
   - **Inputs.** The body is always current. On a task with an approval stamp,
     the plan comes from the stamp's `data_commit`: stage 2, for
     `plan_approved`, sweep, fold, manual and `--now` alike. A task without a
     stamp is read entirely from the working tree (stage 1).
     - Candidates follow the same rule, so a stamped target's progress marks
       never change its digest.
     - Record `task_created_at` and each candidate's `created_at` (the D2
       identity). Every candidate, those listed only under `TRUNCATED:`
       included, gets an `inputs.candidates[]` entry. Relations may name only
       tasks that have an entry.
     - **Materialize the analysed content** (the source and every candidate:
       current body, plus the stamped or working plan) into the job's input
       directory. The prompt directs every full read there, so the agent reads
       exactly what was hashed.
   - Exclude `issue_type: manual_verification` tasks.
3. **The headless operation** in `aitask_codeagent.sh`: `relations` and
   `obsolescence` (the latter's prompt belongs to t1981_6; reserve the op name
   here).
   - Modelled on `explore-relay`: Claude Code only, `--print --output-format
     json`.
   - **Read-only by construction** (D5):
     - `--tools "Read,Glob,Grep"` (the available set; `--allowedTools` only
       pre-approves);
     - `--strict-mcp-config` with no `--mcp-config`, so no MCP servers load;
     - `--disallowedTools` for the mutation built-ins;
     - a permission mode that never prompts and never bypasses.

     Re-verify the flags against the installed CLI, including whether
     settings-sourced hooks run; if they do, restrict `--setting-sources`.
     Test that write, shell and MCP requests find no tool.
   - It requires `--headless`, which the worker passes. It is given a prompt
     file rather than a skill.
   - Other agents get `UNSUPPORTED_AGENT`.
   - Default `claudecode/sonnet5_5` in the seed and project
     `codeagent_config.json`.
4. **Prompt**: `.aitask-scripts/relations/prompts/relations_analysis.md`, with
   the D7 inclusion test.
   - The impact-basis rule for `affects`, `coordinates_with` and `supersedes`.
   - Two-stage reading, at most 8 full reads.
   - Output JSON in the record shape. Zero is a normal result.
5. **Configuration.**
   - The `relations:` block of D5, with `triggers` including `fold`.
   - The seed carries **no** `relations.enabled`: an absent key means disabled.
   - `ait relations enable|disable` through `aitask_metadata_commit.sh`.
   - Setup activation:
     - `ait setup` prints `RELATIONS:<state>` (the `report_testmap_state`
       precedent in `aitask_setup.sh`);
     - interactive setup asks once, default No, when the key is absent, and
       writes the answer;
     - batch setup never asks.
6. **Verbs added to `aitask_relations.sh`**:
   - `analyze <id> [--dry-run] [--now --wait <s>] [--over-cap]`.
     - `--dry-run` prints the validated record without writing; t1981_2's
       replay uses it.
     - `--now` refuses with `CAP_REACHED` at the cap unless `--over-cap` is
       passed.
   - `stamp <id>` (D2):
     - computes the normalized digests of body and plan as committed at the
       task-data `HEAD`;
     - writes `approvals/t<id>.json` into the local outbox **synchronously**;
     - prints one line, `STAMP:<plan_sha256>` (or `STAMP:disabled`);
     - then detaches the network publish and the `plan_approved` enqueue.
   - `plan-digest <id>`: prints `PLAN_DIGEST:<sha>` for the plan as committed at
     the task-data `HEAD`. Re-entry Routing uses it.
   - `analysis-state <id> --expect-plan <sha>`, with the D8 table:
     - `complete` only when two things hold:
       - the latest visible stamp's `plan_sha256` equals the expected identity;
       - a stage-2 record's plan digest equals it, and its body digest equals
         the current body digest;
     - `inputs_mismatch`;
     - `unverifiable`, for no stamp, `stamp_mismatch`, `no_expected_identity`,
       an unreadable stamp, or `STORE:stale` / `unreachable`;
     - `pending`, `failed`, `missing`, `disabled`;
   - `usage [--days N]`, from the record `usage` fields plus the local
     `usage.jsonl` ledger;
   - `ledgers --export`: the local `usage.jsonl`, plus `pull.jsonl` and
     `notify.jsonl` once t1981_5 writes them, as host-tagged JSON lines.
7. **Extension points.** Follow `aidocs/framework/aitasks_extension_points.md`
   for the setup edit and the new config key.

## Key files

- New: `aitask_relations_enqueue.sh`, `lib/relations_worker.py`, the prompt
  file, tests.
- Changed: `aitask_codeagent.sh`, `aitask_relations.sh`, `aitask_setup.sh`,
  `seed/` config, `aitasks/metadata/codeagent_config.json`,
  `aitasks/metadata/project_config.yaml`.

## Reference patterns

- `aitask_codeagent.sh` `explore-relay`: headless constants, the agent refusal,
  the billing note.
- `agentcrew_runner_control.py` `start_runner`: detached start with
  `start_new_session`.
- `lib/relations_store.py` (t1981_1): every write goes through the outbox.
- Testing conventions for subprocess and timeout tests
  (`aidocs/framework/testing_conventions.md`).

## Implementation plan

See `aiplans/p1981/p1981_3_relations_worker_and_analysis.md`.

## Verification

Tests with a stub agent command (no real LLM):
- coalescing and the settle window;
- a single worker under concurrent enqueues;
- the cap;
- the timeout kills the process group;
- an invalid agent output fails the job and writes nothing;
- zero candidates → an analysed empty record with no agent call;
- `--dry-run` writes nothing;
- `--now --wait` bypasses settle and is bounded;
- `analysis-state`: every state, including:
  - the cross-host case (a stage-2 record from an earlier approval plus a newer
    stamp → `inputs_mismatch`; no stamp → `unverifiable`);
  - a newer plan committed without its stamp (the expected identity from
    `plan-digest` differs from the visible stamp) → `unverifiable(stamp_mismatch)`;
  - re-approval with a delayed publish: `stamp` has written the new entry to
    the outbox before returning, so the overlay shows it and the older stamp is
    never accepted;
  - no `--expect-plan` → `unverifiable(no_expected_identity)`;
  - a fold after approval: the body digest differs, so the record is
    re-analysed rather than `UP_TO_DATE`, and Step 8e reports
    `inputs_mismatch` until it is;
- a provider failure fails the job instead of writing an empty record;
- `--now` at the cap without `--over-cap` is refused;
- `plan_approved` jobs read the stamp snapshot, not the working tree;
- the enqueue helper prints nothing and exits 0 when disabled, killed or
  failing;
- setup prints `RELATIONS:disabled` by default.

Run `shellcheck` on the scripts.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1981_1** id=2026-11-07T16:10:54Z.b20f561290a4db5202538fb1 from=t1981_1 from_verified=yes at=2026-11-07T16:10:54Z base=f78e2b8d59718a1e07660fef262bdf6477f09af2 base_branch=main dirty=yes host=omg16
>
> | Advisory, from t1981_1, the relations store (code commit f78e2b8d5). The store contract you will build on differs from the D2/D1 text your plan was written against. The current contract is in aidocs/framework/task_relations.md, D1 "Store API" and "Refs".
> | 
> | - `task_created_at` is REQUIRED on every kind, including the approval stamp (`approvals/t<id>.json` = {task, task_created_at, approved_at, data_commit, body_sha256, plan_sha256}). Take it from the live task's `created_at`. `write()` refuses a mismatch (`IDENTITY_MISMATCH:`).
> | - Synchronous stamp: `Store.write(path, record, flush=False)` validates and writes the outbox entry atomically under the outbox lock, returns `["OUTBOX:<path>"]` and does not publish. Detach `flush()` yourself.
> | - Spool hook: `relations_store.job_state(task_id)` returns None today. Replace it so `ANALYSIS:` can report `pending(..)` / `failed(..)`.
> | - Refs: build them with `Store.ref(id)` (or `relations_schema.canon_ref(id, store.project)`). The project comes from `project.name` in project_config.yaml (`ProjectUnresolved` if missing). Never hardcode `aitasks#`. A record whose own task is not local is refused (`PROJECT_MISMATCH:`).
> | - Digests: use only `relations_schema.digests(task_text, plan_text)`. Body edge blank lines and framework sections are ignored, as are the plan's YAML header, Final Implementation Notes and Post-Review Changes.
> | - Newest-wins is identity first (`relations_schema.wins`), then (stage, at). Your `UP_TO_DATE` check should compare digests on an identity-valid record. `Store.read().files` holds only schema-validated records. Invalid blobs appear in `snap.corrupt`.
> | - Every candidate needs an `inputs.candidates[]` entry whose `created_at` matches the live task, or that relation end is dropped at read.
> | - Test helpers: `Env` / `record()` / `HookPlan` / `set_config()` in tests/test_relations_store.py. Every scratch repo needs `project.name`.
> | 
> | Read t1981_1's archived plan "Final Implementation Notes / Notes for sibling tasks" for the full list.

> **👁 note:read** id=2026-11-07T16:48:26Z.db2b4a4ee7d873dad8cf7a86 by=t1981_3 at=2026-11-07T16:48:26Z mode=explicit ids=2026-11-07T16:10:54Z.b20f561290a4db5202538fb1
