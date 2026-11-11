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
- Live reconnect/repeated timeout and native multi-select remain pending. Added
  persistent protocol/capability/process/timing telemetry for subsequent probes.
  User has reproducible reconnect and multi-select commands; no results are
  inferred from silence or from automated clients.
- Experimental native multi-select and exact-JSON text adaptation now share
  durable pagination, canonical complete-set accumulation, explicit all/none,
  cardinality validation, page replay/conflict handling and candidate revision
  invalidation. The live launcher accepts `--scenario multi` and an explicit
  `--multiselect-mode native|text`; neither route is deployed to workflow callers.
- Validation: 16 core-store, 9 selection and 10 real STDIO transport/launcher
  tests pass. Native/text process tests exercise three pages, fresh processes
  and two timeouts. Found and fixed SDK 2.3.0 union-argument JSON pre-parsing:
  prompt text now reaches validation unchanged, including duplicate JSON fields.
- Expanded the report's caller inventory with source-specific dependency,
  review, work-report, revert, contribution, folding, note/verification, wrapping,
  guide/model, explanation, docs and learned-procedure semantics. Existing
  working fallbacks remain in place; rendered audits and downstream consumer
  result assertions are still required before any shared mapping switch.
- No shared mapping/setup/monitor changes, code commits or archival yet. No
  live multi-select support is claimed. Steps 3–6 remain incomplete. Production
  action guards and complete caller compatibility are explicitly blocked on
  the approved checkpoints; prototype receipts authorize no workflow actions.
- Next: obtain remaining live fresh-connection/repeated-timeout and multi-select
  evidence; record go/no-go, then finish the
  approved hardening and multi-select compatibility work before integration.
