---
Task: t2281_codex_mcp_questions_with_timeout_resume.md
Base branch: main
Output branch: main
---

# Durable attended questions for Codex

## Status and scope

Plan revised after the user's approval-freshness and multi-select review;
explicitly accepted by the user ("plan accepted"). One task with a
mandatory live prototype checkpoint before integration. No children created.
The prototype is part of the requested implementation, not an optional follow-up.
Do not treat this plan, its existence, a timeout, or fast-profile selection as
approval. Task remains claimed during implementation and live prototype validation.

Implement an aitask-specific MCP server for ordinary attended workflow decisions.
Codex filesystem, command, network and tool security approvals remain host-owned.
Do not route those approvals through this server or modify approval policies.
Unattended profiles retain their explicit configured decisions; missing required
attended answers never inherit an unattended default.

## Observed planning evidence

- Local `codex --version` reports `codex-cli 0.167.1` on 2026-11-11. The mise
  launcher required sandbox escalation to update its shims; no client forms have
  been tested during planning.
- `.agents/skills/codex_tool_mapping.md` is tracked and is packaged by
  `.github/workflows/release.yml`, then copied from metadata staging by
  `.aitask-scripts/aitask_setup.sh::setup_codex`. Its unavailable-tool advice
  currently permits defaults and automatic commit/archive; replace that advice
  as part of integration, including any equivalent generated guidance.
- `seed/codex_config.seed.toml` enables `default_mode_request_user_input`.
  Setup merges it into project `.codex/config.toml`; launch paths also live in
  `aitask_codeagent.sh`, `aitask_skillrun.sh`, and `lib/agent_string.sh`.
- `chatlink/relay_ask.py` writes a terminal timeout answer after 90 seconds.
  `chatlink/relay.py` provides validation and atomic no-replace publication
  patterns, but its terminal state model cannot be reused unchanged.
- Monitor recognition uses `monitor/prompt_patterns.py`, with
  `codex_question` matching the built-in form footer and separate permission
  patterns. Durable waiting state must supplement or safely extend recognition;
  arbitrary question prose must not trigger false positives.
- t1180 is Ready, depends on t1185, and tests an older assumption that the
  feature flag alone makes required workflow questions available. It is context,
  not a prerequisite or completed validation for this work.
- Relations analysis is disabled; related work is unknown. The checkout has
  concurrent documentation edits, including setup docs and skill authoring
  conventions. Preserve them and inspect overlapping diffs before editing.
- Confirmed review concern: `lib/gate_ledger.py::_DIGEST_EXCLUDES` excludes
  `aitasks/**`, `aiplans/**` and `.aitask-data/**`. Its `code_digest()` is not a
  plan-revision witness. The revise-plan loop in `task-workflow/planning.md`
  re-presents identical option wording; question/checkpoint names alone cannot
  identify an approval occurrence.
- Confirmed review concern: creation dependencies and review guides/findings
  use multi-select, including accumulated selections across pages. Other callers
  and the existing work-report fallback are inventoried below. A passing
  three-question single-choice prototype is insufficient to replace the shared
  mapping for these callers.
- Official MCP documentation fetched on 2026-11-11 documents local STDIO,
  project-scoped config for trusted projects, initialization instructions, and
  `tool_timeout_sec` defaulting to 60 seconds. It does not prove the required
  form timeout and composer recovery behavior:
  https://learn.chatgpt.com/docs/extend/mcp

## Proposed contract

Keep logical question sessions independent of MCP connections and in-flight RPCs.
Use a repository-owned Python package under `.aitask-scripts/` and a launcher,
with a pinned compatible MCP SDK in the project's managed environment if the
prototype validates that choice. Resolve the SDK/version through its current
official API before implementation. Prefer existing Python setup machinery over
introducing a second runtime; the exact transport adapter remains a prototype
decision. Keep core persistence independent of the SDK.

Expose a small explicit API (names finalized by the spike):

- `aitask_question_ask`: durably create/reuse an idempotent logical session and
  present only the next unanswered question. Persist before issuing elicitation.
- `aitask_question_status`: retrieve accepted answers, current question, remaining
  questions, state, error classification and saved workflow checkpoint.
- `aitask_question_resume`: reconcile an explicit prompt answer, or re-present the
  pending question without an answer; resume remaining forms under the same ID.
- `aitask_question_cancel`: explicitly defer or cancel, with neither action
  supplying an answer or authorizing dependent work.

Store state in private, gitignored runtime storage, scoped to project identity,
framework/Codex logical session, task, workflow checkpoint occurrence,
artifact revision manifest and question-set digest (defined below).
Worktrees and reconnections must resolve the same intended store without
colliding with unrelated projects/sessions. Do not accept arbitrary filesystem
paths as session IDs. Discover pending state on resumed sessions, but require
disambiguation rather than guessing if more than one checkpoint is outstanding.

Records include schema version, opaque session/question IDs, immutable question
text and options, order, accepted answers, pending questions, checkpoint identity
and occurrence, artifact revision manifest,
attempt IDs/generation, transport diagnostics and a completion receipt. Questions
use stable option IDs with labels/descriptions and explicit free-text policy.
Validate bounds, duplicate IDs/options, empty answers, types, and required fields.
Begin the transport spike with single-choice and text. Broad mapping rollout
also requires the multi-select compatibility checkpoint below, using either
demonstrated native support or a demonstrated lossless adaptation.

Use transactional updates (e.g. SQLite with uniqueness/CAS guards and transactions)
or equivalently proven atomic publication. Choose during the spike and document
the decision. Accepted answers are immutable: identical duplicate submissions
are idempotent; different submissions return conflict plus the accepted result.
Race form and prompt submissions through the same acceptance path. Expired or
cancelled or invalidated form generations cannot overwrite a newer accepted
answer or authorize a different artifact revision. Never hold
a storage transaction open while waiting for the human.

Separate logical states from transport attempts. Logical states include pending,
awaiting-chat-answer, deferred, cancelled, invalidated, answered/complete; attempt results
distinguish unavailable capability/server from transport failure and deadline
expiry. Failure or timeout never creates an answer. On restart reconcile orphaned
attempts into recoverable pending state. A finite server deadline should return
before the configured outer tool deadline when possible; correctness must also
survive the outer timeout killing/cancelling the tool before that return.

Prompt recovery records the raw model-forwarded user text plus validated answer
and source `codex_prompt_model_forwarded`; form responses record `mcp_form`.
These labels describe the channel, not independently authenticated human consent.
For option questions accept unambiguous IDs/labels; ambiguous or unrelated chat
remains pending. For free text, require explicit association with the question
when intent is unclear; software cannot infer arbitrary human intent reliably.

Return a durable completion receipt only after every required answer exists.
Bind it to the full approval identity below. Repeated resume calls for the same
still-valid identity return that receipt without re-emitting answered forms.
Claim/acknowledge workflow
continuation idempotently and reconcile a crash at the claim/effect boundary;
do not claim transactional exactly-once external git effects from an MCP response
alone. Existing workflow checkpoints record completed actions, but a legacy
checkpoint pass is not evidence that a changed artifact has been approved.

### Approval freshness — blocking contract

An approval identity consists of project/task/logical workflow run, checkpoint
kind, a durable opaque `occurrence_id`, question-set digest, and a versioned
artifact revision manifest. Connection IDs, RPC IDs and form attempts are separate.
The workflow opens an occurrence once and persists it before showing the question;
ask retries use a stable opening idempotency key and reuse that occurrence.
Reopening the decision after a revise-plan outcome, explicit re-review, or
invalidation creates a new occurrence even if the text, options and eventual
artifact bytes are identical. A reconnect/resume is not a new occurrence.

The manifest binds every approval-relevant artifact and action parameter to
its actual reviewed snapshot: canonical logical identity, digest algorithm and
content digest, plus an occurrence-local revision generation. Plan approval
includes the bytes of the saved plan under `aiplans/` (including uncommitted
changes), relevant task requirements, and intended branch/action. Review/merge
approval binds the actual change set and target; it must not borrow the plan's
manifest or just name `review_approved`. Compute digests from authoritative
local artifacts in the workflow/server adapter; do not trust a model-supplied
digest as proof of freshness. Store the displayed snapshot identity so the user
is approving the same content that was fingerprinted. Missing or unreadable
artifacts are unverifiable and block acceptance/continuation.

Initially hash exact plan bytes conservatively. Any normalization excluding
bookkeeping must be explicit, versioned and tested to preserve all decision
content; never silently reuse relations normalization or code-only digests.
Keep receipt bookkeeping outside the approved artifact where possible. If a
post-approval metadata write changes the hashed plan, do not bypass freshness:
either avoid that write or define/test the narrowly scoped metadata projection
before enabling that workflow. Unrelated task ledger appends need not invalidate
plan approval if the task manifest explicitly hashes only relevant requirement
fields/body, but requirements or target changes must invalidate it.

Revalidate the full identity when accepting any form/prompt answer, on resume,
when issuing/returning a completion receipt, and at the consumer immediately
before recording a pass or starting the dependent action. Transactionally fence
the active occurrence/generation. On a revision mismatch, retire the old
occurrence as invalidated, invalidate its pending forms and unconsumed receipts,
and retain old answers only as audit history. Return an explicit stale-approval
result and require the new artifact to be presented and answered in a new
occurrence. Late answers, retry keys and receipts from the old occurrence cannot
attach to the new one. Reverting bytes after invalidation must not resurrect it.
For a mixed question sequence, reuse unrelated answers only where explicit
per-question dependency manifests prove their validity; never carry forward an
approval merely because its wording is unchanged. Without that proof invalidate
the entire bound sequence.

Receipt consumption must pass the expected occurrence and manifest to the
workflow action guard; checking only inside the MCP server is insufficient.
Operate on the approved immutable snapshot or use an enforceable revision/CAS
guard at the action boundary. A filesystem hash followed by an unguarded live
read leaves a race and is not sufficient. The prototype/hardening report must
name the concrete strategy and cover a writer racing this boundary. If this
cannot be enforced for an action, leave that path blocked rather than claiming
freshness. An already completed action remains historical evidence; subsequent
work on a changed artifact requires a new approval occurrence. Integrate this
guard into workflow re-entry as well, so an old gate pass cannot bypass it.

### Multi-select compatibility — blocking rollout contract

Before changing the shared mapping, inventory canonical source callers and
their rendered attended variants. Record shape, option IDs/labels/descriptions,
cardinality, free-text rules, pagination, control actions, selection order,
existing fallback and tested replacement in the prototype report. Initial
source inventory from 2026-11-11 (re-scan before rollout):

| Source | Selection surface |
| --- | --- |
| `aitask-create/SKILL.md` | dependencies, including sibling tasks and None |
| `aitask-review/SKILL.md.j2` | guides and findings; accumulated pages, select all |
| `aitask-revert/SKILL.md.j2` | children and areas, all/explicit IDs |
| `aitask-contribute/SKILL.md` | multiple selection prompts and changed files |
| `aitask-work-report/SKILL.md` | columns/tasks, pagination and explicit text fallback |
| `task-workflow/related-task-discovery.md`, `aitask-pr-import/SKILL.md.j2` | related tasks, including folding callers |
| `task-workflow/SKILL.md`, `task-workflow/planning.md` | note recipients and verification children |
| `aitask-pick/SKILL.md.j2`, `aitask-wrap/SKILL.md.j2` | labels, files and candidate tasks |
| `aitask-reviewguide-import/SKILL.md`, `aitask-refresh-code-models/` | guide selection, agents/model changes/lineages |
| `aitask-explain`, `aitask-brainstorm-discuss`, `aitask-shadow` | subjects, concerns and explanation selections |
| `aitask-gate-docs-updated`, `aitask-docs-gap`, `aitask-audit-wrappers`, `aitask-learn-skill`, `aitask-add-model` | subsets of docs, gaps, procedures and operations |

Paths above are relative to `.claude/skills/`. Also classify callers routed
through other shared procedures, and distinguish chatlink's existing multi-select
transport from attended Codex mapping consumers; do not change chatlink semantics.
The inventory must inspect behavior, not just count keyword matches.

The mapping dispatches by supported shape/capability, not a universal alias.
For every attended caller, require live native multi-select with tested recovery
OR a tested adapter preserving the full set. A proposed adapter uses a text
elicitation field per page with an unambiguous structured list of stable IDs and
separate navigation/finalization actions; finalize its schema after live testing.
It must preserve labels/descriptions, complete candidate reachability, typed IDs
(including opaque IDs containing punctuation), cardinality and caller ordering.
Do not replace multi-select with single-choice or one yes/no prompt per item;
the work-report source explicitly rejects the latter.

Persist candidate-set revision, current page, accepted page submissions and the
selection accumulator. Apply each page response exactly once, including a response
containing both selections and Next; navigation is never a selected value.
Preserve each caller's semantics for all/none, early completion, unvisited pages,
inclusion versus exclusion, and canonical result order. Reject conflicting
None-plus-items and unknown IDs. Do not truncate choices or silently cap the
result to the UI's option limit. Distinguish an explicit submitted empty set
where permitted from missing/empty tool content, cancellation and timeout.
Only explicit completion of the selection protocol yields a final set. A final
summary must show the complete accumulated selection before downstream effects.
If the candidate universe changes, invalidate or explicitly reconcile it with
the user under a new revision; never let select-all silently expand to new items.

On mid-page timeout, preserve prior selections, end the turn, reconcile the
prompt answer against the outstanding page, and return remaining pages through
MCP without repeating accepted pages or discarding choices. Unrelated input
does not complete an empty set. Apply identical recovery to adapter and native
forms, including fresh connections and repeated timeouts.

Keep a demonstrated working caller-specific route until its replacement passes.
The existing work-report text fallback is a behavior specification, not proof
that its numbered-text presentation is permitted on every host; adapt it to
host constraints and verify it. If native support and allowed adaptations both
fail, return `unsupported_shape`, preserve pending state and withhold migration
for that caller. Do not fall back to the optional-only built-in for required
decisions. A global mapping switch is blocked until all inventoried attended
shapes have a working path; partial enablement must be explicitly scoped and
cannot satisfy task completion by leaving required callers stranded.

## Implementation steps

1. **Compatibility prototype, isolated from normal setup/mapping.** Implement the
   smallest STDIO server and durable state needed for single-choice, text and
   three sequential forms. Recheck the task's linked Codex Security server,
   relevant Codex issues/PR and MCP SDK elicitation docs. Record exact versions,
   reference revisions and which claims are observed versus inferred. Inspect
   current CLI options and effective relevant configuration without dumping
   secrets. Use an explicit temporary launch configuration for live tests.
   Inventory attended multi-select shapes and existing fallbacks now, before
   choosing a replacement schema or promising shared-mapping compatibility.
2. **Live checkpoint and report before broad changes.** Exercise actual attended
   Codex Default mode with the intended model; record client/model/settings,
   MCP protocol/capabilities, SDK deadlines, tool timeout, UI behavior and elapsed
   times. Answer question 1 via form, expire question 2, end the agent turn,
   answer at the ordinary composer, reconcile through resume, and answer question
   3 through MCP. Repeat across server process/connection restart and a second
   timeout. Capture evidence that required work stayed paused and each answer
   was accepted once. User participation is required to validate human input;
   scripted protocol tests cannot stand in for it. Save the report at
   `aidocs/codeagents/codex_questions_prototype.md` with a go/no-go decision.
   Do not implement steps 4–6 unless this checkpoint passes. If native forms
   fail, evaluate terminal/tmux UI over the same store, record feasibility, and
   revise the plan before integration. Do not weaken the recovery contract.
   Record separate verdicts for transport recovery and multi-select compatibility.
   A transport pass alone permits continued hardening, not a global mapping
   switch. Demonstrate native selection or the lossless adapter on dependency,
   guide and finding selections with multiple pages and mid-page timeout.
3. **Harden state and transport.** Complete schema validation, isolation, bounded
   waits, cancellation/defer, restart recovery, concurrent submissions, generation
   fencing, deterministic conflict handling and continuation receipts. Implement
   occurrence/revision manifests and invalidation, plus consumer-side freshness
   enforcement and re-entry handling as specified above. Cover revision-before-
   answer and revision-after-receipt before any approval caller migration. Include
   concise MCP server instructions requiring status/reconciliation and turn-end
   fallback, with the essential constraint in the first 512 characters. Keep
   chatlink's existing terminal timeout semantics unchanged; reuse only suitable
   primitives or patterns after testing their concurrency assumptions.
4. **Setup and launch integration.** Install/package the server and its dependency
   through setup and release paths. Add deterministic project configuration with
   safe command/cwd resolution, preserving user settings and paths containing
   spaces. Verify codeagent, skillrun, manual project launches and resumed
   sessions. Never assume an already-running client dynamically reloads new MCP
   config; document restart/reconnection requirements. No global config writes
   or silent security-policy changes. Missing/unavailable server leaves attended
   questions pending with recoverable plain-text instructions.
5. **Workflow integration.** Update the canonical Codex tool mapping and affected
   `.claude/skills/task-workflow/` sources with Codex-specific rendered guidance.
   Gate the shared switch on the completed caller inventory and native/adapter
   compatibility evidence; integrate any caller-specific adaptation in its
   canonical source and verify the rendered attended variants. Preserve working
   routes during staged rollout. Bind each approval caller and gate write to
   its occurrence/artifact manifest; revise loops explicitly retire occurrences.
   Audit other attended callers for defaults after unavailable/empty input.
   On timeout: save checkpoint/ID, explain the pending question in host-permitted
   plain prose, end the turn, and accept the next explicitly relevant user
   message. Reconcile via MCP before asking remaining questions. Neither empty
   content nor elapsed time permits implementation, commit, archive or approval
   recording. Preserve explicit unattended profile behavior and other agents.
6. **Monitor, docs and final validation.** Use live form captures and durable
   waiting metadata to recognize native forms and awaiting-chat-answer safely
   in monitor/minimonitor/shadow. Clear indicators on accepted/cancelled/closed
   sessions; fence stale records by session identity. Document supported client
   versions, setup, deadlines, cancellation/defer, recovery and limitations.
   Run focused regressions and repeat the live acceptance scenarios through real
   launch surfaces. Consolidate Final Implementation Notes; follow workflow
   Steps 8–9 for review, scoped code commit, gates and archival only when required
   approvals and acceptance evidence exist. No merge is needed on current main.

## Verification

- Unit/process tests: schema failures, ambiguous/unrelated input, immutable
  answers, duplicate IDs/idempotency keys, concurrent prompt/form races,
  cancelled/stale attempts, two isolated sessions, state corruption, interrupted
  writes, process restart, missing capability, unavailable server, transport
  timeout and repeated recovery. Assert no unanswered state yields completion.
- SDK-level integration tests with a controlled MCP client verify cancellation
  and reconnection, including an outer tool deadline before server cleanup.
  These complement, and do not replace, real Codex tests.
- Meaningful workflow regressions verify pending questions block implementation
  and finalization and accepted answers survive re-entry. Exercise duplicate
  continuation and crashes around completion receipt consumption.
- Approval-freshness regressions: change an uncommitted plan while its form is
  pending and reject both old form and prompt answers; change it after a receipt
  is issued but before consumption and reject continuation/gate pass; change it
  after consumption and require fresh approval for subsequent dependent work.
  Repeat revise-plan with identical wording and identical final bytes under a
  new occurrence; reject all old answers/receipts. Test change/revert after
  invalidation, concurrent revision versus acceptance/consumption, missing or
  unreadable artifacts, approval metadata writes, altered task requirements or
  targets, and legacy gate-pass re-entry. Ordinary reconnect/restart with the
  same occurrence and manifest must retain answers and return the same receipt.
- Multi-select regressions at caller level: dependency None/IDs and sibling IDs;
  guide selection and finding selection across at least three pages; select-all,
  explicit empty where allowed, no-response versus empty, selection plus Next,
  unknown/conflicting IDs, duplicate labels with distinct IDs, punctuation in
  IDs, long descriptions, full accumulator and canonical order. Test timeout
  after an accepted page, prompt recovery for the next page, fresh process and
  second timeout, replay/late form response and candidate-universe changes.
  Assert downstream dependency lists/guide sets/finding sets exactly match the
  submitted selection; no side effect before final selection completion. Test
  unsupported capability routing and preservation of each existing working path.
- Run affected setup/config/launch suites, including
  `tests/test_setup_agent_config_seeds.sh`, `tests/test_codex_config_tui_seed.sh`,
  `tests/test_skillrun_codex.sh`, `tests/test_codex_no_plan_injection.sh` and
  `tests/test_codeagent_resume_session.sh`; select additional tests based on
  actual changed paths. Run workflow rendering and wrapper verification for
  touched source/templates. Check chatlink regression suite unchanged.
- Monitor fixture tests must cover real form/footer captures, plain composer
  waiting, cancelled/answered cleanup and quoted-text false positives; verify
  no permission dialog becomes a workflow approval.
- Live acceptance: three-question timeout → composer answer → MCP next form,
  fresh server/connection, repeated timeout, free text, cancellation/defer,
  unrelated steering, late/conflicting answer, separate concurrent sessions.
  Validate long questions and native/adapted multi-select before mapping rollout,
  including a complete paginated selection through timeout/prompt/MCP recovery.
- If required live evidence cannot be obtained, record the limitation and leave
  the task in flight. Do not archive a mock-tested prototype as completed work.

## Risk

### Code-health risk: medium

- Setup, generated guidance and monitor status are shared paths; new defaults
  could regress other clients/profiles · severity: medium · → mitigation:
  required steps 4–6, scoped configuration, rendering and launch regressions.
- Concurrent late answers or crash recovery could overwrite decisions or repeat
  a dependent action · severity: high · → mitigation: required step 3, immutable
  acceptance, generation fencing, durable receipts and crash/race tests.
- Old approvals could authorize a revised artifact or repeated checkpoint
  occurrence despite unchanged question wording · severity: high · → mitigation:
  blocking approval-freshness contract, step 3 and consumer-side revision tests.

### Goal-achievement risk: high

- Native elicitation, host instructions or composer lifetime may prevent the
  exact requested recovery flow · severity: high · → mitigation: mandatory
  prototype/live checkpoint in steps 1–2 before integration, terminal fallback
  evaluation on failure, no inferred support from documentation or mocks.
- Model-forwarded text cannot prove provenance or reliably classify every
  free-text intent · severity: medium · → mitigation: explicit association,
  truthful channel labels and clarification when intent is ambiguous.
- A shared mapping change could lose selections or strand existing multi-select
  callers · severity: medium · → mitigation: blocking caller inventory and
  native/adapter compatibility checkpoint before step 5, caller-level result
  assertions and retention of demonstrated working routes until migration.

The original task and the user's explicit review require these mitigations as
core work. No additional spawned or optional mitigation phases are proposed.
Residual feasibility risk remains high until the real attended prototype and
multi-select compatibility checkpoint pass.

## Review resolution (2026-11-11)

- **Approval freshness: valid, blocking.** Confirmed that code freshness excludes
  plans and the revise loop repeats the same question. Added occurrence identity,
  authoritative artifact manifests, stale state/receipt invalidation, guarded
  consumption and gate re-entry, and tests before/after answer and receipt.
- **Multi-select compatibility: valid, blocking.** Confirmed the named callers
  and broader source usage, including work-report's explicit fallback. Added
  source inventory, shape-aware rollout, native-or-adapter acceptance, durable
  pagination/complete-set semantics, working-route retention and caller tests.
- This revision addressed the design gaps and was subsequently explicitly
  accepted by the user. Implementation progress is recorded below.

## Implementation progress (2026-11-11)

- User-approved plan content before this progress update had SHA-256
  `e1e2df6a49674fa26dca90f4756d996525c88d6e956d71a66023c30b7caf596f`.
  The existing workflow recorded the user's approval in `plan_approved`;
  this prototype has not been used to authorize its own implementation.
- Step 1: isolated Python/SQLite prototype implemented with pinned MCP 2.3.0
  dependency in `/tmp/aitask-2281-venv`. Four tools: ask/status/resume/cancel.
  Single-choice and free-text forms, durable occurrence/answer state, bounded
  form deadlines, recovery across fresh processes, cancellation/defer and stale
  plan/receipt invalidation are available for testing.
- Added store and actual STDIO-process test suites plus a human-operated Codex
  launcher at `tests/manual/codex_questions_probe.py`. The launcher does not
  edit Codex config files, alter security policies or inject user answers.
- Step 2: report written before integration at
  `aidocs/codeagents/codex_questions_prototype.md`. **Baseline live sequence
  passed** by user report and persisted receipt: Blue/form, Sample Alpha/prompt,
  Finish/form. Question 2 expired after approximately 20.020 seconds and its
  prompt answer arrived approximately 47.300 seconds later. The report records
  exact occurrence/receipt IDs and distinguishes user observations from storage.
- Live text-adapter multi-select passed with occurrence
  `958213a338634f44b3ae9093683ddad6`, receipt
  `8f5b0ee4110547b28ea779d540d6e676`: pages selected tasks 1/3, 4/6, 7 via
  form/prompt/form, final set exactly 1/3/4/6/7. Protocol `2025-06-18` is persisted.
  Native probe stopped at `unsupported_shape` without answers; native controls
  were not rendered. Text adaptation is the candidate route for Codex integration.
- Live accepted-answer survival across reconnect followed by repeated timeout
  remains pending. The text-run log shows a restart before any page was accepted,
  which does not settle that gap. User has a focused text-adapter reconnect test.
  Added
  persistent protocol/capability/process/timing telemetry for subsequent probes.
  User has reproducible reconnect and multi-select commands; no results are
  inferred from silence or from automated clients.
- Experimental native multi-select and exact-JSON text adaptation now share
  durable pagination, canonical complete-set accumulation, explicit all/none,
  cardinality validation, page replay/conflict handling and candidate revision
  invalidation. The live launcher accepts `--scenario multi` and an explicit
  `--multiselect-mode native|text`; neither route is deployed to workflow callers.
- Validation: 16 core-store, 9 selection and 11 real STDIO transport/launcher
  tests pass. Native/text process tests exercise three pages, fresh processes
  and two timeouts. Found and fixed SDK 2.3.0 union-argument JSON pre-parsing:
  prompt text now reaches validation unchanged, including duplicate JSON fields.
  Added older-protocol native rejection with persisted negotiation evidence and
  explicit text-adapter recovery of the same unanswered occurrence.
- Expanded the report's caller inventory with source-specific dependency,
  review, work-report, revert, contribution, folding, note/verification, wrapping,
  guide/model, explanation, docs and learned-procedure semantics. Existing
  working fallbacks remain in place; rendered audits and downstream consumer
  result assertions are still required before any shared mapping switch.
- No shared mapping/setup/monitor changes, code commits or archival yet. Live
  text multi-select evidence is scoped to the fixture. Steps 3–6 remain incomplete. Production
  action guards and complete caller compatibility are explicitly blocked on
  the approved checkpoints; prototype receipts authorize no workflow actions.
- Next: obtain remaining live accepted-answer fresh-connection/repeated-timeout
  evidence; record go/no-go, then finish the
  approved hardening and multi-select compatibility work before integration.

## Saved progress and abort (2026-11-12)

- User explicitly requested saving progress and aborting, then specified that
  no commit was needed. All prototype source, tests, launcher and evidence report
  remain saved locally. No checkpoint code commit or archival was performed.
- Task returned to Ready, assignment cleared, plan retained. Plan approval was
  reopened through the gate ledger for a future pick; no deferred-approval marker
  is retained. This is an incomplete implementation, not completion acceptance.
- Last validation: 36 automated tests passed. Baseline and text-adapter
  three-page live recovery passed; accepted-answer survival across a live restart
  followed by another timeout is still unverified. Details and receipts are in
  `aidocs/codeagents/codex_questions_prototype.md`.
- Resume via `/aitask-pick 2281`, review this saved plan and local prototype, then
  finish the remaining live checkpoint before hardening/integration. Shared
  mapping/setup/monitor rollout, guarded approval consumption and caller-level
  compatibility tests are still incomplete. Temporary fixtures/venv under `/tmp`
  may need recreation; the report retains the observed evidence.

## Resumed (2026-11-12, claudecode/fable5_2)

- Re-picked; existing plan used as-is and approved again at the Checkpoint
  ("Start implementation"). Remote drift check: `main` up to date.
- Revalidated the saved prototype before touching it: 16 store, 9 selection and
  11 STDIO transport/launcher tests passed. Installed CLI is now
  `codex-cli 0.167.2` (the recorded live runs used 0.167.1); `--no-daemon`,
  `--no-alt-screen`, `-C`, `--model` and `resume [SESSION_ID] [PROMPT]` are
  still accepted. `/tmp/aitask-2281-venv` (mcp 2.3.0) and the three earlier live
  state directories still exist.
- Prepared (not launched) the reconnect fixture `/tmp/aitask-2281-live-reconnect`,
  question session `8f6c70e5e61c4250b29dc00c01d09a8d`. **The live
  accepted-answer-survives-restart + second-timeout run is still not done** — it
  needs the user at a real Codex session. Steps 4–6 stay blocked on it.
- Step 3 (partial): store-side receipt consumption guard. `Store.consume()`
  (freshness re-proven in the claiming transaction, one consumer key per
  receipt, same-consumer retry returns the original claim), `Store.acknowledge()`
  and `Store.snapshot()` (approved bytes stored in a `snapshots` table from the
  same read that was fingerprinted). Five new store tests; totals now 21 / 9 / 11,
  all passing. Concrete action-boundary strategy: **consume, then act on the
  stored snapshot** — never hash-then-reread the live file. No workflow caller
  uses it yet; no MCP tool exposes it.
- Not touched: shared mapping, setup, launch paths, monitor, skills. Unrelated
  uncommitted monitor/shadow edits in the same checkout were left alone.
- **Live checkpoint (later the same day).** Two attended runs on Codex 0.167.2 /
  `gpt-6-astra`. Run 1 (`8f6c70e5…`, receipt `64e28a36…`): restart survived, but
  q3 was answered in its form, so no second timeout. Run 2 (`1a80ae43…`,
  receipt `51d3cda4…`): q1 form, q2 timeout, restart, q2 at the composer, q3
  timeout, q3 at the composer; one receipt, q1 never re-asked. **Transport
  recovery: go. Multi-select: no-go for a global switch** (see the report).
- Step 3: corrupt/locked state fails closed, crash-before-commit keeps the old
  state, bounded event history, `outstanding()` session recovery, production
  server name and instructions (rule within the first 512 characters),
  `consume` / `acknowledge` / `outstanding` MCP tools, form deadline bound
  raised to 900 s. Not done: gate scripts requiring a claimed receipt, semantic
  task-requirement manifests.
- Step 4: launcher `.aitask-scripts/aitask_questions_mcp.sh`, entry point
  renamed to `aitask_questions_server.py`, `[mcp_servers.aitask_questions]` in
  `seed/codex_config.seed.toml`, `mcp>=2.3,<2.4` tier installed from `main()`
  when the project's Codex config registers the server. No launch-argument
  changes: the registration is project configuration. State directory is
  per-user, outside the project, so no gitignore group was needed. The repo's
  own `.codex/config.toml` and `aitasks/metadata/codex_config.seed.toml` were
  not edited.
- **Deviation / incident:** the dependency install first sat inside
  `setup_codex_cli`, which `tests/test_agent_instructions.sh` and
  `tests/test_setup_agent_config_seeds.sh` call directly; running them
  installed `mcp 2.3.0` and its dependencies into the real `~/.aitask/venv`.
  Moved to `main()` behind `questions_server_registered`;
  `tests/test_setup_questions_server.sh` pins that the Codex setup function
  cannot reach pip.
- Step 5: `.agents/skills/codex_tool_mapping.md` rewritten for attended
  questions; the commit-and-archive-on-defaults finalization fallback removed.
  No `.claude/skills/` source was edited (no default-on-no-answer fallback
  found there), so no goldens changed. `aitask-work-report` and
  `aitask-screen-recording` still name `request_user_input` in prose.
- Step 6: spec at `aidocs/codeagents/codex_questions.md`. Monitor and website
  untouched (no live form capture; installed-configuration run not done).
- Tests: 26 store, 9 selection, 13 STDIO, 37 setup/launcher assertions pass.
  The STDIO module skips when the SDK is absent. Setup, seed, launch and
  manifest suites pass. Two failures in untouched files:
  `tests/test_codex_no_plan_injection.sh` (retired-manifest references) and
  `tests/test_cd_guard_lint.sh` (`tests/test_issue_update_ledger.sh:231`).
- **Still required before archival:** a live session started from the
  installed configuration, multi-select restart and caller-shape evidence, a
  form capture for monitor recognition, website pages.
- **Review checkpoint (2026-11-12): user chose to keep everything uncommitted.**
  The mapping rewrite stays uncommitted until multi-select compatibility and
  the approval safeguards are validated as well. Next evidence: the
  installed-configuration live run (steps in the report). Note: the rewritten
  mapping is live in this working tree, so a Codex session started here reads
  it even though it is not committed.

## Continued after the review checkpoint (2026-11-12, same session)

Everything below is uncommitted, by the user's instruction ("Keep everything
uncommitted until review"). Evidence detail is in
`aidocs/codeagents/codex_questions_prototype.md`.

- **Installed-configuration live runs (user, then agent-driven through tmux).**
  Repo-relative `command`, default state directory, 300 s deadline under the
  360 s client timeout, restart recovery through `aitask_question_outstanding`,
  claim and acknowledge all observed. The `-c mcp_servers.…env={…}` override
  crashes Codex 0.167.2 at start (user report); removed from the steps.
- **Defect found live and fixed:** a question deferred with Esc refused every
  later prompt answer, leaving no way to answer it. `Store.submit` now accepts
  an explicit prompt answer on a deferred occurrence; a late form response is
  still `stale_attempt`. This reverses what
  `test_defer_and_cancel_never_produce_receipt` used to pin for `deferred`.
- **`outstanding()` now lists `retired` occurrences** (voided in the last 24 h,
  unconsumed), after a live run where an edit to a bound file made an open
  question vanish from recovery.
- **Multi-select:** restart with an accepted page passed; dependency, guide and
  finding shapes passed through the mapping's guidance, each with a
  mid-question timeout. Verdict revised to go for the text route. The other
  inventoried callers were not each run live.
- **Step 3/5, gate enforcement — done, scoped to attended Codex.** Chosen by the
  user over a follow-up: "retain the approved plan's action-boundary and gate
  re-entry enforcement. Scope the changes to attended Codex approvals and
  preserve other agents' behavior."
  - `aitask_gate.sh append` refuses (exit 3, nothing written) a `pass` for
    `plan_approved` / `review_approved` / `merge_approved` without
    `approval=<session>:<receipt>` that this task may claim for that gate, or
    `approval=profile:<name>` verified against the profile file.
    `aitask_gate_record.sh` surfaces it as `GATE_RECORD_REFUSED`, exit 3.
  - `resume-point` demotes `IMPLEMENT` to `PLAN` when the plan approval is
    `STALE` or `UNBOUND`; `approval-check` prints the evidence. (The first
    version resumed on `APPENDED`, any file starting with the approved bytes;
    replaced after review, see "Review findings" below.)
  - Active only when `CODEX_THREAD_ID` is set **and** the project owning
    `TASK_DIR` registers the server. Keyed on `TASK_DIR`'s project rather than
    the script's checkout so a gate test run from inside Codex is not judged
    by, and never writes state for, the real checkout.
  - New: `.aitask-scripts/aitask_questions/approval.py`,
    `tests/test_gate_codex_approvals.sh` (62 assertions). Artifact limit raised
    20 → 200 so a review can bind its change set.
  - Not done from the plan's freshness contract: archive is not guarded (it
    has no approval gate of its own); receipts are per-user, per-machine.
- **Review findings on the enforcement (user review, same day) — six, all
  confirmed and fixed.**
  1. *History used as authority.* A claimed receipt stayed usable as
     `duplicate` after the checkpoint was asked again, and `check` judged the
     newest historical claim; a stale verdict was not persisted, so reverting
     bytes restored `IMPLEMENT`. Now a claim has *standing*: `Store._revoke`
     ends it permanently when the checkpoint is reopened or when any refresh
     finds a bound entry uncovered; `claim` refuses a revoked earlier claim
     (`stale_approval`); `check` judges the occurrence named in the ledger's
     current record. Consequence: a review record after the reviewed files
     changed again is refused (the earlier test pinned the opposite).
  2. *`APPENDED` too wide.* Replaced by `plan-bookkeeping/v1`
     (`aitask_questions/projection.py`): checkbox state, and appended sections
     under `## Implementation Progress` / `## Post-Review Changes` /
     `## Final Implementation Notes` only. Verdict renamed `BOOKKEEPING`. The
     tolerance is recorded on the claim (`tolerates`), for the plan file only.
  3. *Task requirements unbound.* For `plan_approved` on a task workflow the
     server binds `task-requirements/v1` itself: the task body without
     frontmatter and without ledger blocks. Checked at answer, claim and
     re-entry; `claim` refuses an occurrence without it
     (`task_requirements_not_bound`). Frontmatter is deliberately not bound.
  4. *Deletions unrepresentable.* New `deleted` argument: path must be absent
     and in `HEAD`; the committed original is fingerprinted and stored. A
     rename is old path in `deleted` plus new path in `artifacts`. After the
     claim only absence is re-proven, because `HEAD` moves with the commit.
  5. *No run identity.* New optional `run` joins the supersession scope; a
     task workflow is its own run and refuses one. `outstanding` rows carry
     and can filter by `run`. The mapping tells skills without a task to pass
     `$CODEX_THREAD_ID`; that it survives `codex resume` was not measured
     live, and recovery does not depend on it (rows carry the value).
  6. *Profile approvals demoted on re-entry.* `resume-point` now reads the
     ledger's current record: `approval:profile:<name>` resumes while that
     profile still pre-answers the step (`PROFILE`).
  Tests: `tests/test_gate_codex_approvals.sh` 107 assertions (sections 7-11
  are these six); `tests/test_aitask_questions.py` 30. Not re-run live in
  Codex after these changes. Five mutants (no revocation, prefix-only
  projection, no requirement binding, no profile re-entry, absence not
  re-proven) each fail the shell test in an isolated copy.
- **Second review round on the enforcement (2026-11-12) — six, all confirmed
  and fixed.** Two of them reverse decisions of the first round.
  1. *Claim and commit were separate operations over mutable files.* New
     `aitask_gate.sh commit-approved` / `aitask_questions/commit.py`: the
     review commit is built from the stored snapshots in a private index on
     top of the branch tip, after each path's bound `base` blob is checked
     against that tip; the commit object is recorded in the claiming
     transaction; the branch moves by compare-and-swap. `review_approved`
     occurrences bind file mode, per-path `base` and the branch (`target`).
     A review pass is recordable only for such a commit
     (`review_commit_missing`), and once committed the approval is judged by
     the commit, not the files - so "record refused after a later edit"
     (round 1, item 1) no longer applies after a guarded commit. Reproduced
     with a `reference-transaction` hook that rewrites the file inside
     `update-ref`: the commit holds the approved bytes.
  2. *Bookkeeping could carry requirements.* `plan-bookkeeping/v2` tolerates
     checkbox state only. Round 1's three allowed headings are gone:
     `## Post-Review Changes` / `## Final Implementation Notes` end the plan
     approval's standing, which costs a re-approval only on re-entry before
     the review is recorded.
  3. *Frontmatter requirements unbound.* `task-requirements/v2` adds
     `issue_type`, `depends`, `xdeps`, `xdeprepo`, `gates`, `verifies`,
     `folded_tasks`, compared by value. Reverses round 1's "frontmatter is
     deliberately not bound".
  4. *Legacy claims kept standing.* `projection.unmet` is checked first in
     `Store.coverage`, so a saved plan claim without the current binding is
     revoked on first read instead of only being refused at a new claim.
  5. *Timed-out question read as idle.* The server stamps a waiting
     occurrence with its process (pid, start time, ancestors); monitors read
     the state read-only and flag the idle pane whose process is an ancestor
     (`codex_question_at_prompt`). Cleared by answer, cancel, invalidation or
     the process ending.
  6. *Form pattern matched a quoted footer.* `codex_mcp_form` now needs the
     footer as the last row with the option row or answer row directly above.
  Tests: `tests/test_gate_codex_approvals.sh` 161 assertions (section 12 is
  the commit boundary); `tests/test_aitask_questions.py` 34;
  `tests/test_prompt_detection.py` 32; the MCP process test checks the
  waiting stamp against a real server. Not run live in Codex.
  Not done (merge binding and the archive guard followed in the third
  round): the shadow's phase signal does not use the waiting state; a raw
  `git commit` cannot be prevented, only kept from being recorded as reviewed.
- **Third review round (user review, 2026-11-13) - six findings, all
  confirmed and fixed.**
  1. *Merge approval unbound.* `merge_approved` occurrences bind
     `merge_source` / `merge_into` (new ask parameters): the commit the source
     names and the destination branch (`Store._merge_target`,
     `projection.MERGE_CHECKPOINT`). New `aitask_gate.sh merge-guard`;
     `aitask_merge_task.sh begin` asks it in a Codex tool shell and merges the
     bound commit, not the branch name (`--approval` for profiles that do not
     record gates). A refusal is exit 2 + `APPROVAL_REFUSED:` on stderr, no
     verdict, before the reservation - chosen so the broker's verdict
     vocabulary, and so every agent's rendered Step 9, is unchanged.
  2. *Archive unguarded.* New `aitask_gate.sh approvals-settled`;
     `aitask_archive.sh` (`approval_guard`) refuses in a Codex tool shell
     while the newest plan/review/merge question of the task is unanswered,
     declined, voided, not approved, not recorded, not committed or stale.
     Not overridden by `--ignore-gates`. A never-asked gate is not judged.
     Review standing now survives the task branch's deletion after its merge.
  3. *Raw `hash-object`.* Change-set entries bind `blob`, the object git
     stores for the bytes at that path (clean filters applied); the commit
     converts the stored bytes the same way and requires that object.
  4. *Tree frozen before `pre-commit`.* The private index is re-read after the
     hook; a change refuses the commit (`hook_changed_index:pre-commit`).
  5. *Parent checked by object id only.* `base` is the whole tree entry
     (mode, type, object), compared against the commit's actual parent.
  6. *Pane identity through ancestry only.* Measured live (codex 0.167.2): a
     hand-started Codex runs the server under the shared app-server daemon,
     outside the pane; framework launches run it in-process. The ancestor
     chain now stops below an app-server process (`detached`), and a detached
     question is tied to the pane that shows its `session_id` - printed there
     by the client itself as the first line of the tool result - while that
     pane still runs `codex`. Validated live in a default Codex session with
     the real `TmuxMonitor`: flagged while waiting after Esc, across a
     quit/relaunch, cleared after the answer at the prompt. The client also
     sends `_meta.threadId` with each call, but nothing on the pane side
     maps a pane to a thread in daemon mode, so it is not used.
  Tests: `tests/test_gate_codex_approvals.sh` 222 assertions (sections 13-15);
  `tests/test_aitask_questions.py` 39; `tests/test_prompt_detection.py` 35.
  Touched outside the question code: `aitask_merge_task.sh`,
  `aitask_archive.sh` (both only inside `CODEX_THREAD_ID` branches).
- **Fourth review round (user review, 2026-11-13) - four findings, all
  confirmed and fixed.**
  1. *Archive check blessed every claimed plan approval.* `settled()` now
     uses the real standing. Because the workflow's closing sections make an
     approved plan differ, one shape is recognised instead of a blanket pass:
     `plan-closing-notes/v1`, verdict `NOTES` (`projection.plan_closed`) -
     the approved text intact, followed only by `## Post-Review Changes` /
     `## Final Implementation Notes`, no other `#`/`##` heading. `NOTES`
     settles an archive, never resumes implementation, never re-records the
     gate and is not a revocation. Changed requirements, any other plan
     change and an earlier revocation are `plan_approved:stale`.
  2. *Auto-archived parent unchecked.* `archive_child` decides up front
     whether the run also archives the parent (no other child left in
     `children_to_implement`) and runs `approval_guard` on the parent before
     anything is written.
  3. *Detached question tied by screen text and in-memory last sighting.*
     Measured on codex 0.168.0: a terminal client exposes no link to its
     thread (argv, open files, environment, its log rows; the daemon logs a
     connection number only), so no vendor identity exists to use. The tie
     is now to the client PROCESS in the pane's foreground (pid + start
     time), made on the first sighting of the id by a client that hosts no
     question server and whose cwd is inside the question's project, stored
     in `prompt_ties.json` beside the state under a file lock. First
     sighting wins; later monitors read the same file.
  4. *Cached association outlived the client.* Follows from 3: a pane back
     at its shell or running a new client has another foreground process.
  Live, real `TmuxMonitor`: hand-started codex 0.168.0 flagged after Esc;
  still flagged by a newly started monitor after the pane history was
  cleared (not flagged with the tie file hidden); with a stand-in client and
  a server kept alive, flagged while the client ran and not after Ctrl-C at
  the shell, in one monitor process. On 0.168.0 the daemon ends a thread's
  question server when its client quits (0.167.2 kept it).
  Tests: `tests/test_gate_codex_approvals.sh` 237 assertions;
  `tests/test_aitask_questions.py` 42 tests. 14 mutants, all killed.
  Not closed: no monitor running while the id was visible; a second
  hand-started client in the same project showing the id first; `/new`
  inside a tied client. Folded tasks deleted by an archive are not checked.
- **Fifth review round (user review, 2026-11-13) - three findings, all
  confirmed and fixed. Supersedes item 3 of the fourth round.**
  1. *The first client to show a session id owned the question.* No reliable
     conversation identity exists (fourth round, measured), so the tie from
     screen text and `prompt_ties.json` are removed. `Watcher.for_pane(pane_pid)`
     takes no screen text, writes nothing and returns an `association`:
     `process` (ancestry, kind `codex_question_at_prompt`) or `candidate`
     (kind `codex_question_unassociated`): every pane whose foreground
     process is a codex client running no sessions in its own process tree
     (`owner.hosts_sessions`: no question server and no
     `codex-code-mode-host` below it, measured on 0.166.0-0.168.0 - an
     in-process client that never loaded the question server is thereby
     excluded too), with its cwd inside the question's project. Derived from processes on each refresh,
     so it needs no sighting and survives a monitor restart; it never names
     one pane among several.
  2. *`serves_questions` descended through a shared app-server.* The walk
     (now `hosts_sessions`) skips app-server children, as `describe` stops
     at them.
  3. *Children read from the main thread only.* `_children` unions
     `task/*/children`.
  Tests: stand-in clients that start their server from the main thread, from
  a worker thread, behind an app-server stand-in, or run a session host
  only. 10 mutants, all killed. Live (codex 0.168.0, 101 panes, 18 running a
  codex client, scratch state): only the hand-started client was a
  candidate; nothing was written.
  Limits: several hand-started clients in one project are all marked; on
  0.167.2 a lingering server can mark a pane after its conversation closed.
- **Sixth review round (user review, 2026-11-13) - one finding, confirmed
  and fixed.** *Candidates rendered as ordinary PROMPT and were counted as
  awaiting.* `monitor_shared`: `is_maybe_awaiting` / `is_awaiting`, badge
  `ASKED? <t>` in `STATE_STYLE_MAYBE` (fits `PANE_STATUS_MAX_CELLS`), hollow
  dot, `format_awaiting_terms` (separate `N asked?` term in both session
  bars); monitor auto-switch ranks a PROMPT pane above a candidate. Tests
  render cards and bars of both apps from snapshots a real `TmuxMonitor`
  classified (`tests/test_monitor_completed_status.py`); 7 mutants, all
  killed. Not changed: the applink status record still carries
  `awaiting_input: true` with the kind for the mobile client to interpret.
- **Seventh review round (user review, 2026-11-13) - one finding,
  confirmed and fixed.** *The minimonitor review loop took a candidate as
  positive awaiting evidence.* `monitor_shared.awaiting_evidence(snap)`
  returns `(None, "")` for a candidate; `_service_review_loop` uses it for
  the controller tick, the work classifier and both baseline writes. Test:
  `test_candidate_for_an_unassociated_question_never_fires` in
  `tests/test_minimonitor_concern_smoke.py` (real arm and service path; no
  round delivered for the candidate, then one once the pane's own prompt is
  seen). 2 mutants, both killed. Not changed: the applink status record
  (kind is sent for the client to interpret) and the workflow-phase
  resolver, which assigns no phase for this kind.
- **Step 6.** `codex_mcp_form` prompt pattern (whole-line footer,
  `skip_trailing_blank_rows`) and question-widget kind with the
  `Field N/M (… required …)` block boundary, from live captures.
  `review_loop.py` was deliberately not edited (another session has
  uncommitted work in it); its coverage guard is satisfied through
  `QUESTION_WIDGET_KINDS`. (A timed-out question waiting at the prompt was
  not shown at this point; see the second review round, item 5.) Website: `known-issues.md`, `getting-started.md`,
  `commands/codeagent.md`, `skills/_index.md` and seven skill pages;
  `check_links.py --build` passed.
- **Not changed:** `.claude/skills/` sources (so no goldens); the repo's
  `aitasks/metadata/codex_config.seed.toml`; `aitask-work-report` /
  `aitask-screen-recording` sources still mention `request_user_input` in
  prose (the Codex wrapper line for work-report was corrected).
- **Left for review / follow-up candidates:** per-caller live runs for the remaining multi-select
  callers; other agents' question routes; the `[features]
  default_mode_request_user_input` seed line is now unused by workflows.


## Final Implementation Notes

- **Actual work done:** A durable question server for attended Codex
  workflows (`.aitask-scripts/aitask_questions/`, launcher
  `aitask_questions_mcp.sh`, entry `aitask_questions_server.py`): questions
  are shown as MCP forms; a form that times out, fails or is postponed stays
  open and is answered at the ordinary prompt; answers survive a restart;
  multi-select is paged. `ait setup` and the Codex seed register the server
  and install its Python tier. The Codex tool mapping routes every workflow
  question through it. Approvals are enforced for attended Codex only
  (`CODEX_THREAD_ID` plus a registered server): the gate ledger takes a
  `plan_approved` / `review_approved` / `merge_approved` pass only with a
  claimable receipt, `resume-point` re-checks the plan approval,
  `commit-approved` builds the reviewed commit from the reviewed content,
  the merge lands only the approved revision, and archiving refuses a task
  (and a parent archived with its last child) with an unsettled approval.
  Monitors recognise an open form (`codex_mcp_form`), a question waiting at
  the prompt (`codex_question_at_prompt`) and, for a hand-started Codex whose
  server the shared daemon runs, candidate panes
  (`codex_question_unassociated`, badge `ASKED?`).
- **Deviations from plan:** The plan expected a waiting question to be tied
  to one pane. For a daemon-hosted server no conversation identity exists
  (measured on codex 0.167.2 and 0.168.0), so after three review rounds the
  screen-text tie and its stored file were dropped in favour of marking
  every candidate pane, rendered and counted apart from a prompt and
  withheld from the review loop. Archiving accepts one narrow change to an
  approved plan, the workflow's own closing sections
  (`plan-closing-notes/v1`, verdict `NOTES`), which the plan did not foresee.
- **Issues encountered:** `-c` MCP env overrides crash Codex during
  bootstrap (avoided). Codex 0.168.0 ends a thread's question server when
  its client quits; 0.167.2 kept it. Linux lists child processes per thread,
  and framework-launched clients that never loaded the question server look
  like hand-started ones unless their `codex-code-mode-host` child is
  counted (`owner.hosts_sessions`). SDK 2.3.0 pre-parses JSON strings for
  union annotations, so `prompt_answer` is a plain `str`.
- **Key decisions:** Enforcement is scoped to attended Codex; other agents'
  behaviour is unchanged. Receipts bind the reviewed content, and the gate
  scripts, not the model, claim them. The monitor's question reader is
  read-only and advisory. A candidate is never positive evidence about a
  pane (`monitor_shared.awaiting_evidence`).
- **Limits left open:** Several hand-started Codex clients in one project
  are all marked `ASKED?` while a daemon-hosted question waits; on 0.167.2 a
  lingering server can mark a pane after its conversation closed. Folded
  tasks deleted by an archive are not checked for open approvals. The
  applink status record sends the new kind with `awaiting_input: true`; the
  mobile client does not render it apart yet. The archive guards were
  validated by shell tests, not in a live Codex run.
- **Upstream defects identified:**
  - `tests/test_workflow_phase_standalone.sh:155-157 — guard expects two `agent_key_from_command(shadow_command)` sites in `minimonitor_app.py`; there are none, so the test fails`
  - `tests/test_codex_no_plan_injection.sh — fails on `.aitask-scripts/retired_scripts_manifest.txt:58,73`, which lists the removed plan-mode files it forbids references to`
  - `tests/test_issue_update_ledger.sh:231 — unconfined `cd … &&` chain fails `tests/test_cd_guard_lint.sh``
