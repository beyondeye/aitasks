---
Task: t1981_3_relations_worker_and_analysis.md
Parent Task: aitasks/t1981_task_relations_and_obsolescence_design.md
Sibling Tasks: aitasks/t1981/t1981_2_relation_candidate_generator.md, aitasks/t1981/t1981_4_relations_triggers.md, aitasks/t1981/t1981_5_relations_consumption.md, aitasks/t1981/t1981_6_obsolescence_layer.md, aitasks/t1981/t1981_7_relations_tui.md, aitasks/t1981/t1981_8_relations_website_docs.md, aitasks/t1981/t1981_9_port_relations_skill_changes.md, aitasks/t1981/t1981_10_relations_retrospective.md
Archived Sibling Plans: aiplans/archived/p1981/p1981_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-11-07 22:18
---

# t1981_3: relations worker, headless analysis and activation

## Context

This task builds the machinery that turns a task into a relations record. It
covers D4 (the enqueue helper only), D5, D7 and the "Analysis completeness" part
of D8 in `aidocs/framework/task_relations.md`. It builds only on the t1981_1
store, which has landed. It is tested against fixture candidates, because the
real generator (t1981_2) waits on t2192. No automatic trigger is wired here
(that is t1981_4); analysis runs only through `ait relations analyze`.

## Verification findings (2026-11-07, against HEAD f78e2b8d5)

The original plan predates the landed store. These corrections apply; the
t1981_1 note has been acknowledged.

- **Store API.** Build only on `Store.write(path, rec, flush=False|True)`,
  `read()`, `ref()`, `canonical_ref()`, `relations_state()` and
  `relations_schema.digests()`, `wins()` and `validate()`.
  - Every kind needs `task_created_at` from the live task's `created_at`. The
    approval stamp shape is `{task, task_created_at, approved_at, data_commit,
    body_sha256, plan_sha256}`.
  - Every `inputs.candidates[]` entry needs a string `created_at`. The schema
    already refuses a relation end without an entry.
  - Refs come from `Store.ref()`. The project comes from `project.name`.
- **`relations_store.job_state(task)`** is a stub that returns None, and
  `analysis_line` calls it as `job_state(tid)`. Replace it with
  `job_state(tid, self.state_dir)`, delegating to the spool module.
- **`Store.relations_state()`** reads only `relations.enabled`. Nothing reads
  the other D5 keys yet. A config loader with defaults is new.
- **`aitask_codeagent.sh`** (886 lines):
  - `SUPPORTED_OPERATIONS` is at :26 and is validated at :363 and :697.
  - The explore-relay Claude-only gate (:481) is a plain `die`. The only
    machine-readable refusal token is `RESUME_UNSUPPORTED:` (:682, exit 2), so
    `UNSUPPORTED_AGENT:` follows that pattern.
  - Defaults are resolved in this order: `--agent-string`, then
    `codeagent_config.local.json`, then `codeagent_config.json`, then
    `DEFAULT_AGENT_STRING`. The seed is not read at run time.
  - `invoke` `exec`s the command, and `--dry-run` prints a single
    `DRY_RUN: …` line.
  - `--tools`, `--allowedTools` and `--disallowedTools` are variadic, so a
    positional argument must come before them or the prompt must go via stdin.
- **Installed CLI: `claude` 2.1.319.** It has the flags the read-only op needs:
  - `--tools`, `--strict-mcp-config`, `--disallowedTools`;
  - `--permission-mode` with the choices
    `acceptEdits|auto|bypassPermissions|manual|dontAsk|plan`; `dontAsk`
    never prompts and is not a bypass;
  - `--permission-prompts none`, `--setting-sources`,
    `--no-session-persistence`, `--disable-slash-commands`.
  - `--bare` skips hooks but forces API-key auth, so it is unusable here.
  - There is no `--max-turns`.
- **Setup.**
  - `report_testmap_state` is at `aitask_setup.sh:2879`, called at :5967.
  - There is no batch flag: every prompt is guarded by `[[ -t 0 ]]`.
  - Metadata writes before :5915 go through `_note_metadata_write` and
    `commit_setup_metadata_writes`.
  - YAML writes are surgical (sed/awk, a temp file, then `cat >` to preserve a
    symlink), never a whole-file re-dump.
- **`project.name` is never seeded.** The seed has it commented out. Store
  construction raises `ProjectUnresolved` without it.
  - **User decision:** `enable` (and setup's "yes") keeps any existing valid
    `project.name`. It seeds the name only from **one unambiguous registry
    binding** for this repository root
    (`aitask_project_resolve.sh bindings <root>`: `BINDING:registry:` lines
    plus `BINDINGS_COMPLETE`). Otherwise it refuses and explains how to set
    the name explicitly.
- **Reuse:**
  - `bounded_run.run_bounded()`: process-group kill on timeout, `/dev/null`
    stdin;
  - `config_utils.load_yaml_config()`;
  - the test helpers `Env`, `record()`, `stamp()`, `set_config()`,
    `write_task()` and `write_plan()` from `tests/test_relations_store.py`.
  - The data repository is the git toplevel of `realpath(<root>/aitasks)`.
    That is `.aitask-data` in branch mode and the root in legacy mode and in
    the test fixtures.
- **Wiring touchpoints for the new codeagent ops:**
  - `seed/` and project `codeagent_config.json`;
  - `settings/settings_app.py` `OPERATION_DESCRIPTIONS`;
  - `tests/test_codeagent_op_wiring.sh` `EXEMPT_OPS`;
  - the Operations table in `website/content/docs/commands/codeagent.md`.
- **`tests/test_metadata_writer_inventory.py`** pins every writer of
  `aitasks/metadata/`. The new config writer is pinned there with its reason.

## Interfaces fixed here (consumed by t1981_2, t1981_4 and t1981_5)

- **Candidate provider contract** (the worker's input; user-confirmed JSON
  interface, D6). It is owned by a new shared module,
  `lib/relation_candidates_contract.py`, which both the worker (consumer) and
  t1981_2's generator (producer) import.
  - **`--json` writes exactly one JSON object to stdout**, and nothing else.
    The information of the text output's `PROVIDER:` line goes in the
    `provider` field. All diagnostics go to stderr. Exit 0 means a complete
    answer.
  - **The exact shape** (`schema: "aitask-relation-candidates/1"`):
    ```json
    {
      "schema": "aitask-relation-candidates/1",
      "source": "aitasks#1981_3",
      "provider": {"path": "engine|fallback", "detail": "<free text, may be empty>"},
      "coverage": {"answered": ["mention_in", "mention_out", "cites", "..."],
                   "missing_sources": ["token"]},
      "cap": 25,
      "candidates": [
        {"ref": "aitasks#1663_4", "sources": ["mention_in", "cites"],
         "card": "<one-paragraph card>",
         "evidence": [{"source": "mention_in", "detail": "t1663_4 body, line 14",
                       "section": "description", "line": 14}]}
      ],
      "truncated": {"count": 3, "by_class": {"cites_hub": ["aitasks#12", "aitasks#40"],
                                              "label": ["aitasks#77"]}}
    }
    ```
    - `section` and `line` are optional. `truncated.count` must equal the
      number of ids in `by_class`. Refs are canonical and qualified.
    - A ref appears at most once across `candidates` and `truncated`.
    - Every tag in `sources` and `evidence[].source` is in the D6 tag
      vocabulary, or matches the `meta:<field>` form.
  - **Validation** (`validate(obj) -> Candidates`): every required field and
    type, and the closed tag vocabulary.
    - **Missing `coverage` (or `answered` / `missing_sources`), malformed
      output, an unknown schema, or a core source (`mention_in`,
      `mention_out`, `cites`) absent from `answered` or present in
      `missing_sources` fails the job.** It is never read as zero
      candidates.
    - Worker reasons:
      - script absent → `CANDIDATES_UNAVAILABLE:no_provider`;
      - non-zero exit → `PROVIDER_ERROR:exit_<n>`;
      - not exactly one JSON object, or a validation error →
        `PROVIDER_ERROR:malformed:<reason>`;
      - core missing → `CANDIDATES_UNAVAILABLE:core_missing:<srcs>`.
  - **One internal result, two renderings.** The module owns `to_json(result)`
    and `to_text(result)`. The text rendering is the agent-facing line
    protocol: `PROVIDER:`, `COVERAGE:`, `CANDIDATE:`, `  EVIDENCE:`, `CARD:` and
    `TRUNCATED:<n>|<class>:<ids>`. It is kept for agent consumers, along with
    t1981_2's `UNCONFIRMED:` fallback rows, which t1981_2 adds to the same
    renderer. A `parse_text()` lets the contract test prove the two renderings
    carry equivalent provider, evidence, coverage and truncation information.
  - **Shared fixtures and contract test**:
    - `tests/fixtures/relation_candidates/`:
      - valid cases: full, partial coverage, zero candidates, truncation;
      - invalid cases: missing coverage, core missing, two objects, unknown
        tag, bad truncation count, duplicate ref, missing input echoes;
      - `reference_provider.py`: a minimal provider that implements the
        snapshot rule. It is the behavioural reference for t1981_2, and the
        worker tests' default provider.
    - `tests/test_relation_candidates_contract.py`:
      - validates every fixture;
      - checks the JSON/text equivalence round-trip;
      - checks the worker's consumption of each fixture (job outcome per
        case);
      - exposes `assert_conforms(json_text, text_output=None)` for t1981_2. It
        also checks a producer command named by
        `AIT_CANDIDATES_UNDER_TEST`, when set, against the same assertions.
  - **The screening snapshot: the worker owns it, and the provider must
    follow it.**
    - The worker invokes `aitask_relation_candidates.sh <id> --json --cap <N>
      --snapshot <manifest.json>`. The manifest is
      `{schema: "aitask-relation-snapshot/1", data_repo, source: <ref>,
      stamps: {<ref>: <data_commit>}}`. It lists every task with a visible,
      identity-valid approval stamp in the job's single store snapshot.
    - **The rule, identical to the analysed inputs (D5):**
      - every body is the current working-tree file;
      - a task in `stamps` contributes its plan as of
        `git -C <data_repo> show <data_commit>:<plan path>`;
      - every other task contributes its working-tree plan.
    - **Every card, and all plan-derived evidence** (mentions, cites, tokens and
      line anchors found in a plan) **comes from that content**, the source's
      own included. A stamped task's working plan is never screened.
    - Cards and evidence are deterministic functions of the snapshot: no
      timestamps, no ordering that depends on the filesystem.
    - **Echo for verification.** The output carries `source_inputs:
      {body_sha256, plan_sha256}` and, per candidate, `inputs:
      {body_sha256, plan_sha256}`, computed with `relations_schema.digests()`
      over the content the provider actually screened. `validate()` requires
      them.
    - The worker compares every echo with its own digests, computed by the
      same rule from the same snapshot.
      - A mismatch (a concurrent edit, or a provider reading the wrong plan)
        → re-run the provider once.
      - A second mismatch → `fail SNAPSHOT_MISMATCH:<ref>`.
  - **Skip identity covers screening.** The record gains
    `inputs.screening_sha256`: sha256 of the canonical JSON (sorted keys) of
    `{provider.path, coverage, candidates[{ref, sources, card, evidence}],
    truncated}`. `UP_TO_DATE` requires it to be equal, so evidence that changed
    while refs, digests and coverage stayed equal still re-analyses.
    - This needs a schema extension in `lib/relations_schema.py`: an optional
      `screening_sha256` (sha256) in `inputs`.
    - **Compatibility, verified rather than assumed.** The landed validator is
      closed. A user probe confirmed that a record carrying the key fails at
      f78e2b8d5 with `record.inputs: unknown key(s)`, and `Store._decode`
      would report it `CORRUPT`. So the extension is a reader-breaking change
      and needs an explicit rollout:
      - **Rollout: readers ship no later than the first writer.** The t1981_1
        store is **unreleased**: no tag contains f78e2b8d5, and the latest is
        v0.40.1. The extended reader lands in the same commit as the only
        record writer (this task's worker). The only possible old readers are
        dev checkouts between f78e2b8d5 and this commit, which cannot publish
        analysed records (no worker, analysis off). So
        `aitask-relations/1` includes optional `inputs.screening_sha256` from
        its first release.
      - **Mixed-version test** (`tests/test_relations_store.py`): load the
        f78e2b8d5 `relations_schema.py` from `git show` into a temp module.
        Assert that it rejects a screening-bearing record, which pins the
        boundary the rollout rule covers. Assert that the current validator
        accepts records with and without the key, and that a current
        `Store.read()` of a pre-extension record (no key) consumes it, not
        `CORRUPT`.
      - **Release guard.** Add to D2 a "Schema compatibility" paragraph: the
        validators are closed, so after the first release that carries a
        schema, any new field needs a schema-version bump with readers that
        accept both versions, shipped one release before any writer emits the
        new version. Record this rollout's state there: unreleased at
        f78e2b8d5, extended before first release.
      - Add a pre-release check to the plan's Step 9 notes: confirm
        `git tag --contains f78e2b8d5` is still empty when this task's commit
        lands. If a release has been cut meanwhile, stop and switch to the
        version-bump rollout instead.
  - Test seam for the worker: `AIT_RELATIONS_CANDIDATES_CMD`.
- **`ait relations stamp <id>`** prints `STAMP:<plan_sha256>`,
  `STAMP:disabled` or `STAMP_ERROR:<reason>` (exit 1).
- **`ait relations plan-digest <id>`** prints `PLAN_DIGEST:<sha>` or
  `PLAN_DIGEST_ERROR:<reason>`.
- **`analysis-state`** prints `RELATIONS_STATE:`, `STORE:`, then
  `ANALYSIS_STATE:<state>`, plus a `NOTE:` under `AIT_RELATIONS=0`.
- **`aitask_relations_enqueue.sh <op> <trigger> <id>`** prints nothing and
  always exits 0.

## Steps

### Pre-phase (risk mitigations)

1. [probe_claude_headless_flags] Probe the installed CLI in a scratch git repo,
   with a cheap model, and record verbatim results in the plan:
   - does `claude --print --output-format json` take the prompt on stdin with
     no positional argument?
   - Does a project `.claude/settings.json` hook (a `SessionStart` or
     `PreToolUse` hook that touches a marker file) run under the chosen flags?
     Compare `--setting-sources ""` (if accepted), `--setting-sources user`,
     and `--settings '{"disableAllHooks":true}'`. Pick the narrowest
     combination that stops project and local hooks and still authenticates.
   - The JSON result shape: which `usage` keys exist, `total_cost_usd`,
     `is_error`.

   The flag set used in step 4 is the one this probe proved.

   **Done (2026-11-07, claude 2.1.319, model claude-haiku-5-5).** Every
   variant used the same base flags: `--print --output-format json
   --no-session-persistence --disable-slash-commands --permission-mode
   dontAsk --strict-mcp-config --tools Read,Glob,Grep --disallowedTools
   Bash,Edit,Write,NotebookEdit,WebFetch,WebSearch`. Each took its prompt on
   stdin with no positional argument. A scratch git repo had a project
   `.claude/settings.json` with `SessionStart` and `UserPromptSubmit` hooks
   that each touched a marker file.

   | Variant | Extra flags | rc | Hook markers | result |
   |---|---|---|---|---|
   | A | none | 0 | **2** | `OK` |
   | B | `--setting-sources ""` | 0 | 0 | `OK` |
   | C | `--setting-sources user` | 0 | 0 | `OK` |
   | D | `--settings '{"disableAllHooks":true}'` | 0 | 0 | `OK` |
   | E | B + D | 0 | 0 | `OK` |

   - **Stdin prompt input works.**
   - **Project hooks run by default under `--print`**, so a restriction is
     required.
   - Authentication still works with no setting sources (variant E).
   - **Chosen: E**, `--setting-sources "" --settings
     '{"disableAllHooks":true}'`: no user, project or local settings, so no
     inherited permission rules or hooks, plus an explicit hook kill as a
     second layer.
   - **JSON result keys:** `type`, `subtype` (`success`), `is_error`, `result`
     (text), `usage` {`input_tokens`, `cache_creation_input_tokens`,
     `cache_read_input_tokens`, `output_tokens`, …}, `total_cost_usd`,
     `duration_ms`, `num_turns`, `permission_denials`, `stop_reason`, and
     others.
   - Usage mapping: `input_tokens` = input + cache_creation + cache_read.

### Main steps

0. **Candidate contract: `lib/relation_candidates_contract.py`** (new,
   stdlib only), as specified under "Interfaces fixed here":
   - `SCHEMA`, `CORE_SOURCES`, the D6 tag vocabulary, and a `Candidates`
     dataclass;
   - `parse_json_stdout(text)`, which demands exactly one JSON object;
   - `validate(obj)`, which raises `ContractError(reason)`;
   - `to_json` / `to_text` / `parse_text`;
   - the fixtures under `tests/fixtures/relation_candidates/`.

1. **Config: `lib/relations_config.py`** (new).
   - `load(root) -> RelationsConfig` with the defaults `max_jobs_per_day` 40,
     `job_timeout_s` 600, `settle_s` 120, `candidate_cap` 25, and all four
     triggers true.
     - It validates types and clamps nonsense values (≤ 0) to the defaults.
     - `enabled` is True only for a literal `true`, the same rule as
       `Store.relations_state`.
     - `trigger_enabled(t)`.
   - `set_enabled(root, value)` and `seed_project_name(root, name)`:
     - surgical, line-based YAML edits of `aitasks/metadata/project_config.yaml`
       (`relations:` block: replace `enabled:` or insert it as the first child,
       or append the block; `project:` block: insert `name:`, or append the
       block);
     - write to the realpath through a temp file and `os.replace`;
     - **re-parse with `load_yaml_config` and require the read-back value to
       match before replacing**. A mismatch leaves the file untouched and
       fails.
   - `resolve_project_name(root)`:
     - an existing valid `project.name` → keep it;
     - else run `aitask_project_resolve.sh bindings <root>`. Exactly one
       distinct `registry` binding, valid under `relations_schema.valid_project`,
       with `BINDINGS_COMPLETE` → seed it;
     - else → `PROJECT_UNRESOLVED:<why>` with the hint "set
       `project:\n  name: <name>` in project_config.yaml or `ait projects add`".
   - The project `aitasks/metadata/project_config.yaml` and
     `seed/project_config.yaml` each get the D5 `relations:` block **without
     `enabled`**, with commented knobs including `triggers.fold`. Check
     `install.sh` for how the seed config is installed, so the block reaches
     new projects.
   - Pin the module in `tests/test_metadata_writer_inventory.py` with its
     reason.
2. **Spool: `lib/relations_spool.py`** (new). All state lives under
   `<git-common-dir>/aitask-relations/spool/`:
   - `jobs/<op>__t<id>.json`: `{op, task, trigger, enqueued_at, not_before,
     now, over_cap, attempts, request_ids[], state?}`;
   - `running/`, `failed/` (`+reason`), `results/<request_id>.json`;
   - `spool.lock` and `worker.lock` (flock);
   - `enqueue.log`, `usage.jsonl`;
   - `work/<run_id>/` (inputs, prompt, raw output). These are kept on failure
     and pruned to the last 20.

   Behaviour:
   - `enqueue(...)`, under `spool.lock`, coalesces per `(op, task)`:
     - the trigger with the higher stage priority is kept (`plan_approved` >
       others);
     - `not_before` = now + `settle_s` (debounce);
     - `now` and `over_cap` are sticky;
     - `request_ids` are unioned;
     - a `failed/` entry for the same key is removed.
   - `claim()` renames a ready job into `running/`. Ready means `now`, or
     `not_before` ≤ now, and not capped; ordering is `now` first, then oldest.
   - `finish(outcome)` / `fail(reason)`.
   - `job_state(state_dir, tid)` → `pending(settling|queued|running|capped)` /
     `failed(<reason>)` / None. `relations_store.job_state` and `analysis_line`
     delegate here.
   - Atomic writes reuse `relations_store._atomic_write`.
   - **Agent-call admission and accounting** (`admit()` / `settle_call()`). One
     mechanism covers every real agent invocation: worker jobs, timeout
     retries, `--now` and `--dry-run`.
     - **Admission is a reservation, appended before the call.** Under
       `usage.lock` (flock), `admit(op, task, trigger, dry_run, over_cap)`
       counts today's (UTC) `kind:"call"` rows for the op.
       - At the cap and not `over_cap` → `CAP_REACHED`.
       - Otherwise it appends `{kind:"call", call_id, at, host, op, task,
         trigger, dry_run, over_cap}` and fsyncs, then releases the lock and
         returns the `call_id`.
       - Check and append happen under one lock, so two concurrent callers
         can never both take the last slot.
     - **A reservation consumes allowance permanently**, whatever happens
       next (success, timeout, `AGENT_ERROR`, `INVALID_OUTPUT`, a crash). A
       timeout retry is a new `admit()`, so it consumes a second slot.
     - **`settle_call(call_id, outcome, usage)`** appends
       `{kind:"outcome", call_id, outcome, input_tokens, output_tokens,
       cost_usd, wall_s}`. Token and cost fields are `null` (unknown, never 0)
       when the agent output carried none or was unparseable.
     - A reservation with no outcome row is reported by `usage` as
       `outcome=unknown`.
     - Rows without an agent call (`UP_TO_DATE`, zero candidates, `EXCLUDED`,
       provider failures) are logged as `kind:"job"` and never count.
     - The `--now` pre-check in the CLI is advisory only; admission in the
       worker is authoritative. A `--now` job without `over_cap` that loses
       the last slot becomes `pending(capped)` and resolves its request as
       `CAP_REACHED`.
   - **Interrupted-job recovery** (`recover_running()`, run by a worker
     immediately after it acquires `worker.lock`, before draining):
     - Holding the lock proves no live worker owns a `running/` entry: only
       the lock holder claims jobs, and flock releases on process death. So
       every `running/` entry is orphaned.
     - **The worker lock proves only that the previous worker is gone, not
       that its agent ended.** `run_bounded`'s timeout owner dies with a
       SIGKILLed worker; the user reproduced the orphaned child outliving
       its timeout. So:
       - Before spawning, the running entry records `spawning: <call_id>`.
       - Immediately after `Popen`, it records `agent: {pgid, leader_pid,
         identity, identity_kind, deadline}`, through a new, backward-
         compatible `on_start(proc)` callback on `bounded_run.run_bounded`.
         The agent always runs in its own process group (`_child_isolation`),
         so `pgid == leader_pid`.
       - `identity` and `identity_kind` come from `lib/pid_anchor.sh`
         `get_pid_identity` (strong `proc` / `bsdinfo`, weak `ps`). Liveness
         is read with `lock_holder_liveness`, shelled out the way
         `parallel_admission_collect.lock_holder_liveness` already does.
     - **Establish that the previous invocation ended** before any retry
       (`_agent_ended(agent) -> ended | alive | unknown`):
       - The leader pid is present with a **different** strong identity:
         the pid was reused. A pid is never reused while a process group of
         that id exists, so the old group is gone → `ended`.
       - The leader pid is absent: `os.killpg(pgid, 0)` is then definitive.
         `ESRCH` → `ended`; success → orphaned members are `alive`. `EPERM`
         → `unknown`.
       - The leader pid is present with the **same strong** identity →
         `alive`. A weak or unreadable identity → `unknown`.
     - **`alive` → terminate it, bounded.** SIGTERM, SIGCONT, then the grace
       period, then SIGKILL to the group, reusing `bounded_run`'s group-kill
       helpers (exposed as `kill_process_group_by_id(pgid, grace)`). Then
       re-check `killpg(pgid, 0)` until `ESRCH`, for at most grace + 3 s.
       Confirmed gone → `ended`.
     - **Only `ended` permits a retry.** On `ended`:
       - a `call_id` with no outcome row gets
         `settle_call(call_id, "interrupted", nulls)`;
       - the consumed attempt stays counted;
       - the job requeues per the rules below.
     - **`unknown`, still alive after the kill, or `spawning` with no `agent`
       record** (killed between the two writes) → write an **unresolved
       guard** `spool/unresolved/<op>__t<id>.json` = `{call_id, agent record
       or null, why, at}`. Settle the reservation `unresolved`. The running
       entry goes to `failed/INTERRUPTED_UNRESOLVED:<why>|pgid=<n>`, and its
       `request_id`s are resolved with that outcome.
     - **The guard blocks every new launch for its `(op, task)` until
       termination is established or a human resolves it:**
       - `enqueue` still coalesces and records the request (nothing is
         dropped), but **never removes a guard**; it removes only `failed/`;
       - the worker checks the guard **immediately before `admit()`** (step
         8), and so does `--dry-run`. When a guard exists it re-evaluates
         `_agent_ended(guard.agent)`:
         - `ended` → remove the guard (logged `UNRESOLVED_CLEARED:ended`) and
           proceed;
         - otherwise the job is **held**: it goes back to `jobs/` with
           `state: blocked_unresolved`, its current `request_id`s resolve
           `BLOCKED_UNRESOLVED`, and no agent starts. `--dry-run` refuses
           `BLOCKED_UNRESOLVED` (exit 3);
       - held jobs count like capped ones for the shutdown handoff: they never
         keep a worker alive. Every worker start re-evaluates every guard
         first, in `recover_running()`, so a group that later exits clears
         itself on the next start;
       - `job_state` reports `failed(interrupted_unresolved)` while a guard
         exists, whatever is queued behind it;
       - **explicit resolution**: `ait relations unblock <id> [--kill]
         [--force]`:
         - re-evaluates;
         - `--kill` retries the bounded group termination;
         - `--force` is a human assertion that the invocation ended, for the
           spawning gap where no pgid exists. It is logged in
           `enqueue.log` and `usage.jsonl` as `kind:"unblock"`.
         - It prints `UNBLOCKED:<id>|<ended|forced>` or
           `STILL_UNRESOLVED:<id>|<why>` (exit 3), and starts the worker when
           it clears a guard.
     - A running entry with no `spawning` marker (interrupted before any
       agent work) is safe to retry directly.
     - **A newer coalesced request is preserved.** If `jobs/` already holds an
       entry for the same `(op, task)` (an enqueue that arrived while the job
       ran), the running entry's `request_ids`, its higher-priority trigger and
       its sticky `now` / `over_cap` are merged into it, and the running entry
       is removed. Otherwise the running entry goes back to `jobs/` with
       `interrupted += 1` and `not_before = now` (no new settle).
     - **Bounded.** Once `interrupted` reaches 2, the job moves to
       `failed/INTERRUPTED`, and every `request_id` it carries gets a
       `results/` entry with that outcome, so `--wait` callers never hang on
       it.
3. **Worker: `lib/relations_worker.py`** (new).
   - `main` with the subcommands `run`, `enqueue <op> <trigger> <id>` and
     `stamp-publish <id>`. `start_worker_detached()` uses Popen with
     `start_new_session=True`, `stdin=DEVNULL` and stdout/stderr appended to
     `enqueue.log`.
   - **Loop:**
     1. `flock -n worker.lock`, else exit.
     2. `recover_running()`.
     3. `store.flush()` if the outbox is non-empty.
     4. Drain ready jobs. While settling jobs remain, sleep until the earliest
        `not_before`, bounded at `settle_s + 5`, then re-scan. Capped-only or
        empty → go to 5.
     5. **Shutdown handoff.** Release the lock, then re-scan the spool for
       **any non-capped job, ready or still settling**.
        - If there is one, try `flock -n` again. On success go back to step 2;
          on failure another worker now holds the lock, and because it starts
          with its own full scan it owns the job. Exit.
        - Only a spool that is empty or capped-only lets the worker exit for
          good.
        - **Capped jobs are deliberately left for the next worker start**
          (the next enqueue, `ait relations analyze`, or a later trigger).
          With no scheduler, they show as `pending(capped)` in
          `status` and `ANALYSIS:`, and the docs say so. This closes both
          stranded-enqueue windows: before and after the worker's empty
          check.
   - **Fresh state per job, coherent within it.** Each job constructs a new
     `relations_config.load(root)`, a new `Store(root)` (and so a new
     `TaskIndex`, whose `load_active` and `plan_digest` caches would otherwise
     go stale across jobs and settle sleeps), and performs exactly one
     `store.read()`. Everything inside the job uses that store, index and
     snapshot: source, candidates, stamps, `UP_TO_DATE` and identity. Nothing
     carries over to the next job. `--dry-run` follows the same rule.
   - **Per job (D5 order):**
     1. Daily-cap pre-check: a non-reserving count, done before spending
        candidate work. At the cap without `over_cap` → `state: capped`, back
        to `jobs/`. The **reservation** happens in step 8, right before the
        call.
     2. Source lookup through the job's `store.index`.
        - Not found → `fail TASK_NOT_FOUND`.
        - `issue_type: manual_verification` → drop with `EXCLUDED`; no
          record.
     3. Build the snapshot manifest from the job's single snapshot: the
        identity-valid stamps and the data repo. Then run the provider
        (`<id> --json --cap <candidate_cap> --snapshot <work>/snapshot.json`,
        stderr captured into the job log). The output is parsed and checked
        with `relation_candidates_contract.validate()`. Every contract failure
        (absent, non-zero exit, malformed, missing coverage, core missing)
        fails the job here, **before** any `UP_TO_DATE` check, and is never
        read as zero candidates. `provider.path` becomes
        `run.candidate_provider`, and `coverage.missing_sources` becomes the
        record's `coverage`.
     4. **Inputs.**
        - The body is always the current working tree.
        - A visible, identity-valid stamp (`approvals/t<id>` with
          `task_created_at` == live) means **stage 2**, with the plan read
          by `git -C <data repo> show <data_commit>:<plan path>`. The plan
          path is found with `ls-tree` at that commit, matching
          `_find_plan`'s name regex.
        - Otherwise **stage 1**, with the plan from the working tree.
        - The same rule applies to every candidate, `truncated` ids included.
        - Each candidate gets `created_at` from `index.live_created_at`.
          Candidates the index cannot find are dropped and logged; foreign
          refs are dropped and logged.
        - Digests come only from `relations_schema.digests()`.
        - An unreadable stamped plan → `fail STAMP_PLAN_UNREADABLE`.
        - **Snapshot agreement.** Compare the provider's `source_inputs` and
          per-candidate `inputs` echoes with these digests. Re-run the
          provider once on mismatch, then `fail SNAPSHOT_MISMATCH:<ref>`.
          Compute `screening_sha256`.
     5. `UP_TO_DATE`: a visible record that is identity-valid, analysed, with
        stage ≥ this stage, equal `inputs.source`, an equal candidate set
        (ref, created_at, digests), equal `coverage` and equal
        `inputs.screening_sha256` (an older record without one is never
        `UP_TO_DATE`) → skip. `--dry-run`
        never skips.
     6. Zero candidates → an analysed record with `relations: []` (with
        `coverage.missing_sources` if partial). No agent call.
     7. Materialize the **normalized** body and plan text, so the agent reads
        exactly what was hashed, into `work/<run>/inputs/source/` and
        `inputs/candidates/t<id>/`. Compose `work/<run>/prompt.md`: the
        template plus a job section listing the source ref, the inputs dir,
        the cards with evidence, the `TRUNCATED:` ids and the output contract.
     8. `call_id = admit(...)`. `CAP_REACHED` here (the slot was lost to a
        concurrent caller) → `state: capped`, back to `jobs/`. Record
        `call_id` in the running entry (atomic rewrite). Then run
        `aitask_codeagent.sh --headless invoke relations <prompt.md> <inputs
        dir>` with `run_bounded(timeout=job_timeout_s)`, cwd = repo root. Test
        seam: `AIT_RELATIONS_AGENT_CMD`.
        - Every exit path calls `settle_call(call_id, <outcome>, <usage or
          nulls>)` in a `finally`. A crash leaves the reservation for
          `recover_running()`.
        - Timeout → `settle_call(...timeout)`, then requeue once with a new
          admission on the retry (`attempts`), then `fail TIMEOUT`.
        - A non-zero exit or `is_error` → `fail AGENT_ERROR:<detail>`, with
          whatever usage the output carried.
     9. Parse the claude JSON and extract exactly one JSON object
        `{considered, relations}` from `result` (a bare or a ```json-fenced
        object). Refs are canonicalized with `store.canonical_ref`.
        `considered` refs outside the candidate set → invalid.
        - Build the full record: `run` = uuid, trigger, stage, at, host,
          `agent_string` (from `aitask_codeagent.sh resolve relations`),
          `code_base`, `data_base` and `candidate_provider`; plus `usage`
          (tokens including cache, `total_cost_usd`, wall time).
        - `rs.validate()`. Any failure → `fail INVALID_OUTPUT:<reason>`, and
          **nothing is written**.
     10. Write: `store.write(path, rec)`.
         - `OUTBOX`, `PUBLISHED` or `RETAINED` → done; a retained entry is the
           store's retry.
         - `STALE_RUN` → done, logged.
         - `IDENTITY_MISMATCH` or `PROJECT_MISMATCH` → fail.
         - The `usage.jsonl` call and outcome rows were already written by
           steps 8 and 9 (`settle_call`). Steps without a call append one
           `kind:"job"` row. Write `results/<request_id>` for every
           `request_id` on success and on failure.
   - Op `obsolescence`: the enqueue logs `SKIPPED:op_unimplemented`
     (t1981_6 owns it).
4. **Headless ops in `aitask_codeagent.sh`.**
   - Add `relations` and `obsolescence` to `SUPPORTED_OPERATIONS`, the help,
     and the argument rule: exactly `<prompt_file> <input_dir>`, both existing,
     checked even under `--dry-run`.
   - The non-Claude gate prints `Error: UNSUPPORTED_AGENT:<agent>` and exits 2.
   - Without `--headless`, the op is refused with the billing note.
   - `CMD=(claude --model <id> --print --output-format json
     --no-session-persistence --disable-slash-commands --permission-mode
     dontAsk --strict-mcp-config <probe-proven hook restriction> --add-dir
     <input_dir> --tools Read,Glob,Grep --disallowedTools
     Bash,Edit,Write,NotebookEdit,WebFetch,WebSearch)`, then
     `exec "${CMD[@]}" < "$prompt_file"`. `--dry-run` prints the `DRY_RUN:`
     line, then `PROMPT_STDIN:<file>`.
   - Add `"relations"` and `"obsolescence"` as `claudecode/sonnet5_5` in both
     `codeagent_config.json` files.
   - Add an `OPERATION_DESCRIPTIONS` entry for each.
   - Add both ops to `EXEMPT_OPS` with a reason comment.
   - Add website Operations table rows.
5. **Prompt** `.aitask-scripts/relations/prompts/relations_analysis.md`:
   - the D7 inclusion test word for word;
   - the vocabulary table with directions;
   - the basis kinds and the impact-basis rule; `path` must be a full
     repository path, resolved with Glob;
   - two-stage reading, at most 8 full reads, full reads **only** from the
     inputs dir;
   - the output JSON `{considered:[{ref,outcome,sources}], relations:[{from,to,
     type,description≤600,basis,evidence}]}` with an example;
   - "zero relations is normal";
   - the description is addressed to the other task's agent and is advisory;
   - only refs listed as candidates.
6. **Verbs in `lib/relations_cli.py`.** Extend `VERBS`, the parser, `USAGE` and
   the header comment of `aitask_relations.sh`:
   - **`analyze <id> [--dry-run] [--now [--wait <s>]] [--over-cap]`**:
     - `--dry-run` runs the job pipeline in-process, ignoring `enabled`, and
       prints the validated record JSON. It writes nothing to the store. Its
       agent call goes through the same `admit()` / `settle_call()` under
       `usage.lock` (`dry_run: true`), so concurrent dry runs and workers share
       one atomic allowance.
     - Without `--dry-run`, the verb refuses `DISABLED` / `HOST_OFF` (exit 1).
     - At the cap, `--now` or `--dry-run` without `--over-cap` →
       `CAP_REACHED:<n>/<cap>` (exit 3).
     - Plain → `ENQUEUED:<id>`.
     - `--now --wait <s>` polls `results/<request_id>`, bounded by `<s>`:
       `ANALYZED:<id>|<outcome>` or `WAIT_TIMEOUT:<id>|<job_state>`
       (exit 3).
   - **`stamp <id>`**:
     - disabled → `STAMP:disabled`;
     - otherwise `data_commit` = the data repo `HEAD`; body and plan via
       `git show HEAD:<path>`;
     - `task_created_at` live; `approved_at` UTC ISO;
     - `store.write(..., flush=False)`, synchronous, under the outbox lock;
     - print `STAMP:<plan_sha>`;
     - then detach `relations_worker.py stamp-publish <id>` (flush, then
       enqueue `plan_approved`, honouring the trigger switch and
       `AIT_RELATIONS`).
     - `aitask_relations_enqueue.sh relations plan_approved` routes to the
       same detached path, writing the stamp there, so there is one stamp
       implementation.
   - **`plan-digest <id>`**: the plan at the data repo `HEAD`.
   - **`analysis-state <id> [--expect-plan <sha>]`**, in this order:
     1. `disabled`;
     2. `unverifiable(no_expected_identity)`;
     3. store stale or unreachable → `unverifiable(store_stale|store_unreachable)`;
     4. the stamp is corrupt → `unverifiable(stamp_unreadable)`; absent or
        identity-mismatched → `unverifiable(no_stamp)`; its `plan_sha` ≠
        expected → `unverifiable(stamp_mismatch)`;
     5. `complete`: a stage-2, identity-valid record whose plan digest equals
        expected and whose body digest equals the current one;
     6. a local job → `pending(..)` / `failed(..)`;
     7. a record for other inputs → `inputs_mismatch`;
     8. else `missing`.

     Document this order in the design doc, D8.
   - **`usage [--days N]`** (default 7): `USAGE:local|<op>|<trigger>|jobs=|calls=|failed_calls=|unsettled=|in=|out=|cost=|wall=`
     from `usage.jsonl`. It joins call and outcome rows by `call_id`. A total
     with any null contribution is printed as `<sum>+unknown(<n>)`, never as a
     plain sum. and `USAGE:store|…` from `run.at` and `usage` of
     records in the snapshot. Corrupt ledger lines are counted and reported
     (`LEDGER_CORRUPT:<file>|<n>`), never silently skipped.
   - **`ledgers --export`**: JSON lines of `usage`, `pull` and `notify` `.jsonl`
     (the last two when present), each tagged `{host, ledger}`. A corrupt line
     becomes `{host, ledger, corrupt_line: n}`.
   - **`unblock <id> [--kill] [--force]`**: clears an unresolved-invocation
     guard (see the spool step), with the line protocol defined there.
   - **`enable` / `disable`**:
     - `enable` resolves `project.name` first and refuses with
       `PROJECT_UNRESOLVED:` (exit 1) if it cannot;
     - then writes the keys through `relations_config` and commits with
       `aitask_metadata_commit.sh aitasks/metadata/project_config.yaml`;
     - prints `RELATIONS:enabled(<agent>, cap <N>/day)` / `RELATIONS:disabled`
       plus the commit line.
7. **`aitask_relations_enqueue.sh <op> <trigger> <id>`** (new, bash):
   - `exec >/dev/null 2>>"$log"`, falling back to `/dev/null`;
   - an EXIT trap forcing exit status 0;
   - `nohup "$PY" relations_worker.py enqueue … &` then `disown`;
   - Python calls `os.setsid()` first, then checks `enabled`, the trigger
     switch and `AIT_RELATIONS=0`, enqueues, and starts the worker;
   - `relations plan_approved` writes the stamp when `enabled` (independent of
     the trigger switch and `AIT_RELATIONS`).

   Not whitelisted: no skill calls it (t1981_4's call sites are scripts and
   task-workflow via `aitask_relations.sh`). Check `ait relations` is already
   whitelisted through `aitask_relations.sh`; if not, run
   `aitask_audit_wrappers.sh`.
8. **Setup.**
   - `report_relations_state` after `report_testmap_state`. It prints
     `RELATIONS:disabled` or `RELATIONS:enabled(<agent>, cap <N>/day)`, plus
     the enable hint (`ait relations enable`) and a one-line cost note
     (headless print-mode billing).
   - `ask_relations_activation`, placed before `commit_setup_metadata_writes`:
     - only when `[[ -t 0 ]]` and `relations.enabled` is absent;
     - `[y/N]`; it writes `true` or `false` through the same Python helper
       (`relations_config.py set-enabled`, with the project-name rule on yes);
     - `_note_metadata_write`.
   - Batch (non-tty) never asks.
9. **Docs.**
   - `aidocs/framework/task_relations.md`: a "Worker API" section with the
     spool layout, the candidate provider contract (with the exact JSON shape,
     the one-object/stderr rule, the failure reasons, and a pointer to the
     shared module, fixtures and contract test; D6 references it), the CLI
     line protocols,
     the analysis-state evaluation order, the test seams, and the project-name
     rule for `enable`.
   - A `CLAUDE.md` pointer is not needed: the `task_relations.md` pointer
     already exists.

### Post-phase (risk mitigations)

1. [pin_candidate_contract] After the commit, send an `ait note` to t1981_2. It
   carries:
   - the exact JSON shape (`aitask-relation-candidates/1`), and the rule that
     `--json` emits one object with diagnostics on stderr;
   - the `--snapshot <manifest>` rule: approved plans for stamped tasks; cards
     and plan-derived evidence only from that content, deterministic; the
     `source_inputs` / `inputs` digest echoes. This includes making the shim's
     plan-derived signals (mentions, cites, tokens over plans) honour the
     snapshot, which t1981_2 may have to raise with t2192;
   - `reference_provider.py` as the behavioural reference;
   - the core-source set and the failure reasons;
   - the shared module `lib/relation_candidates_contract.py` (`validate`,
     `to_json`, `to_text`, `parse_text`). Build one internal result and render
     both formats through it; add `UNCONFIRMED:` to the same renderer;
   - the fixtures dir and `tests/test_relation_candidates_contract.py`
     (`assert_conforms`, `AIT_CANDIDATES_UNDER_TEST`) to run against the real
     generator;
   - the seam `AIT_RELATIONS_CANDIDATES_CMD`, to be removed or kept per
     t1981_2's step 3.

   Send `ait note` to t1981_4 and t1981_5 with the `stamp`, `plan-digest`,
   `analysis-state` and enqueue line protocols. Cite the code commit SHA in
   all notes.

## Verification

- **`tests/test_relations_worker.py`** (unittest, reusing the store fixtures;
  the stub agent and fixture provider are scripts in a temp dir, injected
  through the seams):
  - coalescing (trigger priority, sticky `now`, debounce of `not_before`);
  - settle respected, and `--now` bypasses it;
  - a single worker under concurrent `enqueue` from 4 processes;
  - **shutdown handoff** (hook barriers in the worker):
    - (a) a normal **non-`now`** job is enqueued after the worker's empty scan
      but before it releases `worker.lock`. The detached start fails the
      lock; the job still executes after its settle window **with no further
      enqueue**;
    - (b) the same, but the job is enqueued after the release;
    - (c) a capped-only spool lets the worker exit, and the job stays
      `pending(capped)`;
  - **per-job refresh**: one worker process, two jobs. Between them (a hook
    barrier) a candidate task is created and the second job's source task is
    rewritten (body and `created_at`). The second job sees the new candidate,
    the new body digest and the new identity. A within-job test shows one
    snapshot is used throughout: a change made mid-job, after the snapshot
    hook, is not half-applied;
  - **cap accounting**:
    - a timeout, an `AGENT_ERROR` and an `INVALID_OUTPUT` each consume
      allowance;
    - a timeout retry consumes a second slot;
    - after enough failures a new job is `pending(capped)`;
    - unknown cost is `null` and reported as `unknown`, not 0;
    - **two concurrent `--dry-run`s with one slot left**: exactly one runs the
      agent, the other gets `CAP_REACHED`. Repeat with a worker against a
      dry run;
    - `over_cap` bypasses the cap and is recorded;
  - **interrupted recovery**:
    - SIGKILL a worker subprocess after `claim()` and after `admit()` (hook
      barrier). Start another worker: the reservation gets an `interrupted`
      outcome and stays counted, the job re-runs, and its `request_id`
      resolves;
    - **with a live agent**: the stub agent starts and spawns a grandchild,
      and both record their pids. The worker is SIGKILLed while the agent
      runs. The recovering worker must kill the whole orphaned group, verify
      that both pids are gone **before** the replacement agent starts (the
      replacement stub asserts the old pids are dead at its own start), then
      retry;
    - **unresolvable**: the agent record is forced to `unknown` (a weak
      identity, or a `spawning` marker without an `agent` record). The job
      becomes `failed(INTERRUPTED_UNRESOLVED…)`, a guard is written, no
      replacement agent runs, and the request resolves;
    - **the guard holds across requests**, in the same setup:
      - (a) a request for that task that was **already queued** before
        recovery;
      - (b) a **new automatic enqueue** after recovery (trigger `created`, via
        the enqueue helper);
      - (c) a `--dry-run`.

      None of them starts an agent: the stub's launch counter stays 0. The
      jobs are held as `blocked_unresolved`, `job_state` stays
      `failed(interrupted_unresolved)`, the guard still exists after the
      enqueue, and `--wait` resolves `BLOCKED_UNRESOLVED`;
    - **guard release**:
      - the orphaned group exits on its own → the next worker start clears
        the guard and the held job runs exactly once;
      - `unblock --force` clears a spawning-gap guard and logs it;
      - `unblock` with the group still alive → `STILL_UNRESOLVED`;
        `unblock --kill` → `UNBLOCKED:…|ended`;
    - pid reuse: the leader pid is present with a different identity →
      `ended`;
    - a newer coalesced request enqueued while the job was "running" is
      merged, not lost;
    - a second interruption → `failed(INTERRUPTED)`, with every `request_id`
      resolved;
  - the cap: a capped job stays `pending(capped)`, `over_cap` runs;
  - a timeout kills the process group (the stub spawns a grandchild whose pid
    is recorded; it is dead afterwards), retried once, then `failed(TIMEOUT)`;
  - invalid agent output → `failed(INVALID_OUTPUT…)`, store and outbox
    untouched;
  - zero candidates → an empty analysed record, with an agent-call counter of
    0;
  - provider failure and missing core source fail the job even when a
    matching record exists (before `UP_TO_DATE`);
  - an `UP_TO_DATE` skip;
  - a stamped task: the working-tree plan is edited after the stamp, and the
    record's plan digest still equals the stamp's;
  - **screening snapshot agreement**: the source and one candidate are both
    stamped, and their working plans differ from the approved ones.
    - Each working plan carries a distinctive path and token that only it
      contains. With the reference provider, no card or evidence row contains
      them, and the echoes match.
    - A non-conforming provider that reads the working plan →
      `SNAPSHOT_MISMATCH` after one re-run, with nothing written.
    - Evidence changed while refs, digests and coverage stayed equal → a
      different `screening_sha256` → re-analysed, not `UP_TO_DATE`.
  - a fold after approval (body changed) → re-analysed, not `UP_TO_DATE`;
  - truncated candidates get entries;
  - manual_verification is excluded;
  - `job_state` values.
- **`tests/test_relations_analysis_cli.sh`** (with `assert_counters_init` /
  `assert_counters_load` if it uses subshells):
  - `analyze --dry-run` writes nothing (outbox and L unchanged);
  - `--now --wait` is bounded (a slow stub → `WAIT_TIMEOUT` within the bound);
  - `--now` at the cap without `--over-cap` → `CAP_REACHED`;
  - `stamp` prints `STAMP:<sha>`, and the outbox entry exists before return;
  - `STAMP:disabled`;
  - `plan-digest`;
  - `analysis-state`, every state:
    - complete;
    - `inputs_mismatch` cross-host (a stage-2 record from an earlier approval
      plus a newer stamp from a second clone);
    - no stamp → `unverifiable`;
    - `stamp_mismatch` (a newer committed plan, expected from `plan-digest`);
    - a delayed publish after re-approval (the new stamp in the outbox wins
      over the published old one);
    - `no_expected_identity`;
    - a fold after approval → `inputs_mismatch`;
    - pending, failed, missing, disabled, and the `AIT_RELATIONS=0` note;
  - `usage` and `ledgers --export` (including a corrupt-line report);
  - `enable` / `disable`:
    - a commit with the key read back;
    - an existing `project.name` is kept;
    - one registry binding is seeded;
    - zero or two bindings, or `BINDINGS_INCOMPLETE` → `PROJECT_UNRESOLVED`
      with the file untouched;
  - the enqueue helper prints nothing and exits 0 when disabled, when Python
    is missing, and when its detached part is killed.
- **`tests/test_relation_candidates_contract.py`**:
  - every valid fixture passes;
  - every invalid fixture fails with its expected reason: missing coverage, a
    core source missing, two JSON objects or trailing text, an unknown tag, a
    bad truncation count, a duplicate ref;
  - the JSON/text equivalence round-trip;
  - worker consumption per fixture: the valid ones produce records, and every
    invalid one gives a `failed(...)` job state, never an analysed empty
    record;
  - `assert_conforms` / `AIT_CANDIDATES_UNDER_TEST`, exercised against a
    fixture-echo producer.
- **`tests/test_relations_config.py`**: surgical edits over comment-heavy YAML,
  existing and absent blocks, a symlinked config, and the read-back guard.
- **`tests/test_codeagent_relations.sh`**:
  - the dry-run argv carries every read-only flag and `PROMPT_STDIN:`;
  - refusals: a non-Claude agent → `UNSUPPORTED_AGENT:` exit 2, no
    `--headless`, a missing prompt or dir;
  - a real invoke with a PATH-stub `claude` captures argv and stdin;
  - `RUN_LIVE_RELATIONS=1`: a live run whose prompt asks for a file write, a
    Bash command and an MCP tool. Assert no file exists, and that the result
    reports those tools as unavailable. **Run once during implementation (user
    choice) with a cheap model, and record the result.**
- **Setup:** an `insetup`-style test (`tests/test_install_engine_binary.sh`
  pattern):
  - `report_relations_state` prints `RELATIONS:disabled` by default;
  - the question is skipped with `</dev/null`;
  - with a tty stub and a "y" answer it writes `enabled: true`.
- Run the existing tests: `tests/test_relations_store.py`,
  `tests/test_relations_cli.sh`, `tests/test_codeagent.sh`,
  `tests/test_codeagent_op_wiring.sh`,
  `tests/test_metadata_writer_inventory.py`, the full Python suite, and
  `shellcheck` on the changed and new scripts. `aitask_skill_verify.sh` is
  needed only if skill text changes (it should not).

## Risk

### Code-health risk: medium
- The read-only, no-hooks guarantee of the headless op rests on CLI flag
  behaviour (stdin prompt input, which settings sources load hooks) that
  `--help` does not fully pin down. · severity: low (residual: addressed by
  inline pre-phase probe_claude_headless_flags) · → mitigation: inline
  pre-phase probe_claude_headless_flags
- New concurrency in the spool and worker:
  - lost coalescing updates under concurrent enqueue;
  - a job stranded when an enqueue lands while the worker is exiting
    (ready or settling);
  - orphaned `running/` entries after a crash, and an agent process group
    that outlives its worker;
  - cap evasion through failed or concurrent calls;
  - stale task state across jobs.

  Addressed in the design by `spool.lock`, the any-non-capped shutdown
  handoff, `recover_running()`, reserve-before-call admission under
  `usage.lock`, and fresh per-job Store/TaskIndex/config. Each is covered by
  hook-barrier tests. · severity: medium · → mitigation: none
- Surgical edits of the shared `project_config.yaml` could corrupt an unusual
  block shape. Guarded by re-parse and read-back before `os.replace`, and by
  tests over comment-heavy YAML. · severity: low · → mitigation: none

### Goal-achievement risk: medium
- t1981_2's shim-backed signals may find it hard to honour the screening
  snapshot (an engine that indexes working-tree files). Until it does, the
  digest echo catches plan reads that disagree, but not evidence an index
  derived from a working plan. · severity: medium · → mitigation: inline
  post-phase pin_candidate_contract (the requirement is handed to t1981_2,
  which owns the shim side)
- The candidate-provider contract is defined here before t1981_2 exists, so the
  two may drift. · severity: low (residual: addressed by the shared contract
  module, fixtures and contract test, and by inline post-phase
  pin_candidate_contract) · → mitigation: inline post-phase pin_candidate_contract
- Analysis quality (the prompt) cannot be measured until t1981_2's D13.2
  replay. Accepted, because t1981_2 owns that measurement. · severity: low ·
  → mitigation: none

### Planned mitigations
- timing: pre-phase | name: probe_claude_headless_flags | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: read-only/no-hooks guarantee rests on unverified CLI flags | desc: Probe stdin prompt input, hook loading under the candidate settings flags, and the JSON result shape before writing the codeagent op
- timing: post-phase | name: pin_candidate_contract | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: contract drift with unbuilt siblings | desc: ait note to t1981_2 (provider JSON contract) and t1981_4/t1981_5 (stamp/plan-digest/analysis-state/enqueue protocols) citing the code commit

## Step 9

Post-implementation per task-workflow Step 9 (current branch, no merge;
archival via `aitask_archive.sh 1981_3`).

Pre-commit release check (schema rollout): `git tag --contains f78e2b8d5` must
be empty. If not, stop: a release shipped the closed `aitask-relations/1`
reader, and `screening_sha256` must move to a schema-version bump instead.

## Post-Review Changes

### Change Request 1 (2026-11-08 00:30)
- **Requested by user:** four confirmed review findings:
  - **(high)** queued work ran after an opt-out, because no switch was
    re-checked before paid admission;
  - **(high)** a killed `--dry-run` left its agent running with no ownership
    record, and a second dry run launched;
  - **(medium)** `evidence.section` was emitted raw into the pipe-delimited text
    protocol (`|`, a newline or `-` broke framing);
  - **(medium)** `usage` `jobs=` counted only no-call jobs, so a successful
    paid job read `jobs=0|calls=1`.
- **Changes made:**
  - `relations_worker.switched_off()` re-reads `relations.enabled` and
    `AIT_RELATIONS=0` at job start and again immediately before `admit()`.
    `JobSkipped` ends the job as `SKIPPED:disabled|host_off`, with a
    `results/` entry, a `kind:"job"` row and a log line. Dry runs are exempt.
  - Dry runs now write `previews/<call_id>.json`: the owner pid and strong
    identity, plus `call_id` / `spawning` / `agent`. The entry is removed once
    the agent ends. `recover_previews()` runs at every worker start and at every
    dry-run start:
    - a preview whose owner is alive is left alone;
    - a dead owner's agent is ended (group kill) before the entry is released;
    - an invocation that cannot be established becomes an unresolved guard,
      settled `unresolved`.
  - The text protocol JSON-encodes `evidence.section` (as it already did for
    details and cards); absence is a bare `-`. `parse_text` uses a JSON-aware
    evidence parser.
  - Every terminal job outcome writes exactly one `kind:"job"` row: analysed,
    up-to-date, empty, excluded, stale-run, skipped, failed, interrupted, and
    dry runs (`dry_run: true`). Held and requeued jobs write none, so a
    timeout-retried job is 1 job and 2 calls. The CLI test assertion is now
    `jobs=1|calls=1`.
  - Docs ("Worker API"): the switch re-check, previews, the job/call counters,
    and the text encoding.
  - New tests:
    - `SwitchTests`: disabled or host-off after queueing, and flipped mid-job
      before admission (0 launches, 0 calls, visible outcome); dry-run
      exception;
    - `DryRunRecoveryTests`: SIGKILLed preview CLI; the second dry run ends the
      orphan group first (the replacement stub verifies the old pids are dead);
      worker-start recovery; spawn-gap preview with a dead owner → guard +
      `BLOCKED_UNRESOLVED`, worker job held; a live preview is left alone;
    - `UsageCountTests`;
    - contract `test_text_round_trip_of_awkward_optional_fields`.
- **Files affected:** `.aitask-scripts/lib/relations_worker.py`,
  `relations_spool.py`, `relations_cli.py`, `relation_candidates_contract.py`,
  `aidocs/framework/task_relations.md`, `tests/test_relations_worker.py`,
  `tests/test_relations_analysis_cli.py`,
  `tests/test_relation_candidates_contract.py`.

### Change Request 2 (2026-11-08 08:10)
- **Requested by user:** three confirmed findings:
  - **(high)** preview recovery ran only at worker or dry-run startup, so a
    preview alive at startup that lost its CLI during candidate gathering
    could leave its agent alive while the worker launched another;
  - **(medium)** concurrent recoverers acted on the same preview snapshot (two
    terminal job rows for one preview);
  - **(medium)** `tests/test_setup_relations.sh` used `cp -R` of
    `.aitask-scripts`, which `tests/test_framework_copy.sh` (t2226) rejects
    for tracked tests. The t2226 session also sent this as an advisory inbox
    note.
- **Changes made:**
  - `analyse()` calls `recover_previews(sp, task=tid)` at the shared
    pre-admission boundary, before the guard check. This covers worker jobs
    and dry runs, and live previews are still left alone.
  - `recover_previews` holds `spool/recovery.lock` for each entry's whole
    transition and re-reads the entry under it, skipping it if it is already
    released.
  - `Spool.settle_call` is idempotent per `call_id`, and `Spool.log_job(...,
    invocation=)` is idempotent per invocation; both check and append under
    `usage.lock`.
  - The setup test sources `tests/lib/framework_copy.sh` and uses
    `copy_framework_tree "$PROJECT_DIR/.aitask-scripts" "$t/.aitask-scripts"`.
    The guard's own pattern finds no hit in the new tests, and the control (the
    old line) still matches.
  - Docs ("Worker API"): the pre-admission reconcile, the recovery lock and
    idempotency.
  - New tests:
    - `test_preview_dying_after_startup_is_reconciled_before_admission`. The
      preview owner is killed in the worker's `after_snapshot`; no launch
      happens while the agent lives. A mutant without the pre-admission call
      fails this test.
    - `test_concurrent_recoverers_act_once`: a barrier subprocess holds a stale
      listing while a second recoverer settles; exactly one job row and one
      outcome row result.
    - `test_accounting_is_idempotent_per_invocation`.
- **Files affected:** `.aitask-scripts/lib/relations_worker.py`,
  `relations_spool.py`, `aidocs/framework/task_relations.md`,
  `tests/test_relations_worker.py`, `tests/test_setup_relations.sh`.

### Change Request 3 (2026-11-08 09:20)
- **Requested by user:** two confirmed findings:
  - **(high)** a single guard file per `(op, task)` let a second unresolved
    invocation overwrite the first one's protection, so ending only the second
    agent cleared the guard while the first stayed unresolved;
  - **(low)** `parse_text` split on `str.splitlines()`, so a valid section
    containing U+0085, U+2028 or U+2029 (kept raw by `ensure_ascii=False`)
    failed to round-trip.
- **Changes made:**
  - Guards are stored per invocation:
    `spool/unresolved/<op>__t<id>/<invocation>.json`, keyed by `call_id`,
    or a generated id for a corrupt running entry. `guard()` returns every
    outstanding invocation and `has_guard()` whether any remains.
    `clear_guard(op, tid, inv)` clears one; the directory goes when it is empty.
    - The pre-admission check, `recover_running`, `job_state`, `reset_holds`,
      `status` and `unblock` evaluate each invocation on its own evidence.
    - A task stays blocked while any invocation remains: worker-originated and
      preview-originated alike. `unblock` succeeds only when none remains,
      and otherwise prints `remaining=<n>`.
  - `parse_text` splits on `"\n"` only, and strips only the two-space indent.
  - New tests:
    - `test_every_unresolved_invocation_must_be_resolved`: a spawn-gap
      preview, a weak-identity live preview and a worker spawn gap. After only
      the weak one's agent ends, the task stays blocked (0 launches, dry run
      refused, `remaining=2`) until a forced unblock. A one-guard-per-task
      mutant fails this test.
    - The contract round-trip now covers U+0085, U+2028, U+2029, VT, FF and FS
      in sections, details, cards and the provider detail.
- **Files affected:** `.aitask-scripts/lib/relations_spool.py`,
  `relations_worker.py`, `relations_cli.py`, `relation_candidates_contract.py`,
  `aidocs/framework/task_relations.md`, `tests/test_relations_worker.py`,
  `tests/test_relation_candidates_contract.py`.

### Change Request 4 (2026-11-08 10:05)
- **Requested by user:** **(medium)** a guard admission race. The final guard
  read and `admit()` were not coordinated with guard writers (`write_guard`
  takes `spool.lock`, `admit` only `usage.lock`), so a guard created between
  the pre-admission scan and the reservation was missed and an agent launched.
- **Changes made:**
  - New `Spool.admit_unguarded()`: under `spool.lock`, it raises `Blocked`
    when any guard exists for the key, else calls `admit()` (`usage.lock`
    nested). Lock order is spool → usage; no path takes them the other way.
  - `analyse()` keeps the liveness cleanup (`recover_previews` and
    per-invocation `agent_ended`) outside, then calls `admit_unguarded`.
    `Blocked` holds the job as `blocked_unresolved`, or refuses a dry run with
    `BLOCKED_UNRESOLVED`. A new `before_admit` test-hook point sits between
    the scan and the reservation.
  - New tests: a guard written at `before_admit` blocks a worker job (no call,
    no launch, no record, request resolved `BLOCKED_UNRESOLVED`), and blocks a
    dry-run CLI (subprocess barrier, exit 3). A mutant using plain `admit()`
    fails.
- **Files affected:** `.aitask-scripts/lib/relations_spool.py`,
  `relations_worker.py`, `aidocs/framework/task_relations.md`,
  `tests/test_relations_worker.py`.

## Final Implementation Notes
- **Actual work done:** everything in the approved plan, plus four review
  rounds (Change Requests 1-4 above).
  - New modules:
    - `lib/relation_candidates_contract.py`: provider contract, JSON/text
      renderings, snapshot manifest, screening digest;
    - `lib/relations_config.py`: loader; surgical, read-back-guarded YAML
      edits; the project-name rule;
    - `lib/relations_spool.py`: spool, coalescing, admission and ledger,
      per-invocation guards, previews;
    - `lib/relations_worker.py`: per-job pipeline, worker loop, recovery,
      stamp, enqueue/stamp-publish entry points.
  - New files:
    - `aitask_relations_enqueue.sh`;
    - `.aitask-scripts/relations/prompts/relations_analysis.md`.
  - Changed files:
    - `aitask_codeagent.sh`: `relations` / `obsolescence` ops;
    - `relations_cli.py` and `aitask_relations.sh`: 9 new verbs;
    - `relations_store.py`: `job_state` hook;
    - `relations_schema.py`: optional `inputs.screening_sha256`;
    - `bounded_run.py`: `on_start`, `kill_process_group_by_id`;
    - `aitask_setup.sh`: `ask_relations_activation`,
      `report_relations_state`;
    - the seed and project `codeagent_config.json` / `project_config.yaml`;
    - `settings_app.py`: descriptions;
    - the `ait` help line;
    - website codeagent table;
    - the design doc "Worker API" section, plus D2 "Screening identity" /
      "Schema compatibility", D5 headless-flag outcome, D6 contract pointer,
      and D8 evaluation order;
    - the metadata-writer inventory pin;
    - `EXEMPT_OPS`.
  - Tests:
    - `test_relations_worker.py` (53), `test_relations_analysis_cli.py` (24),
      `test_relation_candidates_contract.py` (10), `test_relations_config.py`
      (17), `test_relations_store.py` (+1);
    - `test_relations_enqueue.sh` (19), `test_codeagent_relations.sh` (49, plus
      an opt-in live block), `test_setup_relations.sh` (13);
    - fixtures, a reference provider and a stub agent in
      `tests/fixtures/relation_candidates/`.
- **Deviations from plan:**
  - The analysis-state and verb tests are Python, through the CLI subprocess,
    rather than the planned `.sh`; only the enqueue helper's
    no-stdout/exit-0 contract is a bash test.
  - `usage.jsonl` lives directly under `aitask-relations/`, as the design doc
    places the ledgers, not under `spool/`.
  - A new enqueue re-opens a `capped` hold; a `blocked_unresolved` hold
    follows only its guard.
  - The provider contract also carries `truncated.inputs` echoes, because
    truncated candidates get record entries too.
  - Review rounds added: switch re-check before admission, `SKIPPED:*`
    outcomes; dry-run ownership (`previews/`) and its recovery at
    worker start, dry-run start and the pre-admission boundary; serialized,
    idempotent recovery (`recovery.lock`, per-`call_id` outcome, per-invocation
    job row); one terminal job row per job; per-invocation guards;
    `admit_unguarded` (atomic final guard check plus reservation); JSON-encoded
    evidence sections; newline-only text framing.
- **Issues encountered:**
  - The CLI and registry helpers resolve their interpreter under a scratch
    `HOME`, so tests pin `AIT_PYTHON`.
  - A killed child of the test process lingers as a zombie, so group-kill tests
    use orphaned sleepers (init reaps them).
  - The bash enqueue test raced its own detached parts until each case waited
    for its log line.
  - `codeagent` resolves models from the repo root, so the live check runs the
    `--dry-run` launch line from a scratch dir.
- **Key decisions:**
  - **Live probe results (claude 2.1.319):**
    - project hooks DO run under `--print` unless settings are restricted;
    - chosen: `--setting-sources ""` plus `--settings
      '{"disableAllHooks":true}'`, the prompt on stdin, `--permission-mode
      dontAsk`, `--tools Read,Glob,Grep`, `--strict-mcp-config`, and
      `--disallowedTools Bash,Edit,Write,NotebookEdit,WebFetch,WebSearch`.
  - **Live read-only check** (`RUN_LIVE_RELATIONS=1`, claudecode/haiku5_5,
    2026-11-07): the model-reported tools were exactly `Glob,Grep,Read`; no
    file was written, no shell command ran, no project hook ran.
  - Analysis-state evaluation order: a local job outranks `inputs_mismatch`
    (documented in D8).
  - Schema rollout: f78e2b8d5 is in no release tag, so the extended reader
    ships with the first writer; this was re-checked at commit time.
  - `enable` project-name rule (user decision): keep a valid name; else exactly
    one complete registry binding; else refuse with a how-to.
- **Upstream defects identified:**
  - `.aitask-scripts/aitask_setup.sh:5915-5967` — `ensure_*` writes are
    committed at :5915 but the venv (PyYAML) is only set up afterwards, so any
    setup question that writes YAML through Python must commit itself (this
    task's `ask_relations_activation` calls `_flush_metadata_batch`
    directly). Not a bug in itself; an ordering constraint worth knowing.
- **Notes for sibling tasks:**
  - **t1981_2 (generator):**
    - Conform to `lib/relation_candidates_contract.py`: one JSON object on
      stdout with `--json`, diagnostics on stderr, and `--snapshot <manifest>`
      honoured (stamped plans from `data_commit`, deterministic cards and
      plan-derived evidence, digest echoes via `relations_schema.digests`).
    - Render the text output through `to_text` and add `UNCONFIRMED:` there.
    - Run `tests/test_relation_candidates_contract.py` with
      `AIT_CANDIDATES_UNDER_TEST`.
    - `reference_provider.py` is the behavioural reference.
    - The worker calls `aitask_relation_candidates.sh` and reports
      `CANDIDATES_UNAVAILABLE:no_provider` until it exists. The seam is
      `AIT_RELATIONS_CANDIDATES_CMD`.
    - `analyze --dry-run` works while analysis is disabled and is
      cap-admitted.
  - **t1981_4 (triggers):**
    - `aitask_relations_enqueue.sh <op> <trigger> <id>` never prints and always
      exits 0.
    - `ait relations stamp <id>` prints `STAMP:<sha>|STAMP:disabled|STAMP_ERROR:<r>`.
      It writes the stamp synchronously (outbox) and detaches the publish and
      the `plan_approved` enqueue.
    - `plan-digest <id>` prints `PLAN_DIGEST:<sha>` or
      `PLAN_DIGEST_ERROR:<r>`.
    - `obsolescence` is accepted by the helper but logged
      `SKIPPED:op_unimplemented`.
  - **t1981_5 (consumption):**
    - `analysis-state <id> [--expect-plan <sha>]` prints `ANALYSIS_STATE:`
      after `RELATIONS_STATE:` / `STORE:`, with the D8 order. `ANALYSIS:` can
      now read `pending(capped)` and `failed(interrupted_unresolved)`.
    - Write `pull.jsonl` / `notify.jsonl` under `<git-common-dir>/aitask-relations/`.
      `ledgers --export` already picks them up.
  - **t1981_6:** the `obsolescence` op name is reserved in `aitask_codeagent.sh`.
    Add `OPS_IMPLEMENTED` and a job path in `relations_worker.py`, and reuse
    `admit_unguarded`, previews and guards.
  - **Every launch path** must go through `analyse()`'s pre-admission
    sequence: switch re-check, `recover_previews(task=)`, the per-invocation
    guard scan, then `admit_unguarded`. Ownership records go in the running
    entry or a preview.
  - Tests: reuse `tests/test_relations_worker.py::WBase`, `orphan_sleeper()`,
    and the barrier seam `AIT_RELATIONS_TEST_BARRIER`.
