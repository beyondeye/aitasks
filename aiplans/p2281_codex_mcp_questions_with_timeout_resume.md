---
Task: t2281_codex_mcp_questions_with_timeout_resume.md
Base branch: main
Output branch: main
---

# Durable attended questions for Codex

## Status and scope

Planning completed; awaiting explicit implementation approval. One task with a
mandatory live prototype checkpoint before integration. No children created.
The prototype is part of the requested implementation, not an optional follow-up.
Do not treat this plan, its existence, a timeout, or fast-profile selection as
approval. Task remains claimed while awaiting the planning checkpoint.

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
framework/Codex logical session, task, workflow checkpoint and question-set
digest. Worktrees and reconnections must resolve the same intended store without
colliding with unrelated projects/sessions. Do not accept arbitrary filesystem
paths as session IDs. Discover pending state on resumed sessions, but require
disambiguation rather than guessing if more than one checkpoint is outstanding.

Records include schema version, opaque session/question IDs, immutable question
text and options, order, accepted answers, pending questions, checkpoint identity,
attempt IDs/generation, transport diagnostics and a completion receipt. Questions
use stable option IDs with labels/descriptions and explicit free-text policy.
Validate bounds, duplicate IDs/options, empty answers, types, and required fields.
Begin with single-choice and text; promise multi-select only after live proof.

Use transactional updates (e.g. SQLite with uniqueness/CAS guards and transactions)
or equivalently proven atomic publication. Choose during the spike and document
the decision. Accepted answers are immutable: identical duplicate submissions
are idempotent; different submissions return conflict plus the accepted result.
Race form and prompt submissions through the same acceptance path. Expired or
cancelled form generations cannot overwrite a newer accepted answer. Never hold
a storage transaction open while waiting for the human.

Separate logical states from transport attempts. Logical states include pending,
awaiting-chat-answer, deferred, cancelled, answered/complete; attempt results
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
Bind it to the question digest and workflow checkpoint. Repeated resume calls
return that receipt without re-emitting answered forms. Claim/acknowledge workflow
continuation idempotently and reconcile a crash at the claim/effect boundary;
do not claim transactional exactly-once external git effects from an MCP response
alone. Existing workflow checkpoints remain authoritative for completed actions.

## Implementation steps

1. **Compatibility prototype, isolated from normal setup/mapping.** Implement the
   smallest STDIO server and durable state needed for single-choice, text and
   three sequential forms. Recheck the task's linked Codex Security server,
   relevant Codex issues/PR and MCP SDK elicitation docs. Record exact versions,
   reference revisions and which claims are observed versus inferred. Inspect
   current CLI options and effective relevant configuration without dumping
   secrets. Use an explicit temporary launch configuration for live tests.
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
3. **Harden state and transport.** Complete schema validation, isolation, bounded
   waits, cancellation/defer, restart recovery, concurrent submissions, generation
   fencing, deterministic conflict handling and continuation receipts. Include
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
  Probe long questions and multi-select explicitly before documenting support.
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

### Goal-achievement risk: high

- Native elicitation, host instructions or composer lifetime may prevent the
  exact requested recovery flow · severity: high · → mitigation: mandatory
  prototype/live checkpoint in steps 1–2 before integration, terminal fallback
  evaluation on failure, no inferred support from documentation or mocks.
- Model-forwarded text cannot prove provenance or reliably classify every
  free-text intent · severity: medium · → mitigation: explicit association,
  truthful channel labels and clarification when intent is ambiguous.

The task already requires these mitigations as core work. No additional spawned
or optional mitigation phases are proposed. Residual feasibility risk remains
high until the real attended prototype passes.
