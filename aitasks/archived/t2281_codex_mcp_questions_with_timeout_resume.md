---
priority: medium
risk_code_health: medium
risk_goal_achievement: high
effort: high
depends: []
issue_type: feature
status: Done
labels: [codex, codeagent, skills, workflow]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/fable5_2
created_at: 2026-11-11 10:02
updated_at: 2026-11-13 14:16
completed_at: 2026-11-13 14:16
---

## Objective

Prototype, then implement a custom MCP question tool for attended aitasks workflows in Codex Default mode. Substitute for the built-in request_user_input where its optional-only instructions prevent required workflow questions. Preserve structured questions while supporting reliable recovery through ordinary Codex prompt input after a timeout.

## Problem and investigation context

On 2026-11-11, local Codex 0.167.1 reported default_mode_request_user_input enabled, but a live task session requested plan approval in plain text without invoking the question tool. Its injected Default-mode instructions restricted request_user_input to optional questions and prohibited permission requests. This is not established as a regression introduced in 0.167.1: matching restrictive text was found in older installed binaries too.

Availability, model willingness to call a tool, client rendering, and request lifetime are separate concerns. The replacement must be tested against the actual Codex CLI, not only with a mock MCP client. Workflow choices must remain distinct from Codex command/filesystem permission escalation; do not bypass those controls.

## Mandatory timeout and continuation contract

The user's primary concern is timeout behavior. A timeout is acceptable ONLY with this recovery flow:

1. Persist the question/session identity, question text and options, previously accepted answers, and remaining questions.
2. If the custom tool or client times out, pause the dependent workflow. Do not select a default, infer consent, skip the question, or continue implementation/finalization requiring the missing answer. End the turn so the ordinary Codex composer is available; do not keep the agent polling indefinitely.
3. Clearly tell the user which question still needs an answer and that they can enter it directly at the Codex prompt. Include enough context to answer even if the form has disappeared. Respect the host's plain-text fallback constraints; do not depend on an unavailable card or forbidden textual multiple-choice format.
4. On the user's next message, associate their answer with the outstanding question. Validate it; ambiguous input remains pending. Unrelated steering or a status request must not be consumed as an answer. Record whether the answer came from MCP form input or the Codex prompt, without claiming independently authenticated provenance for model-forwarded text.
5. Resume or re-establish the MCP interaction using the same logical question session. Submit/reconcile the plain-text answer with the custom tool's state, then present any remaining questions through the custom MCP question UI. Previously answered questions must not be repeated. This must also work after a fresh MCP process/connection, not require the timed-out call to remain alive.
6. When all required answers exist, continue the workflow from its saved checkpoint. Repeated timeouts repeat this fallback without losing answers or advancing prematurely.

Transport timeout must not destroy the logical pending question. Distinguish answered, awaiting-chat-answer, cancelled, unavailable, and transport failure. Define explicit cancellation/defer behavior and reconcile late form answers against prompt answers so there is one accepted result, no overwrites, and no duplicate continuation.

## Phase 1 — compatibility prototype first

- Implement the smallest local MCP server exposing an aitask-specific question tool. Start with MCP form elicitation in the Codex client; OpenAI's Codex Security plugin provides a reference implementation.
- Exercise single-choice and free-text input, then a multi-question sequence. Explore a minimal ask/resume contract (separate tools or explicit actions) with durable logical IDs and idempotent answer submission. Prefer sequential forms initially if that reduces partial-answer ambiguity.
- Test Default mode without relying on the built-in request_user_input call or forcing Plan mode. Record Codex version, model, relevant settings, negotiated MCP capability/protocol, observed UI, and timings.
- Identify all effective deadlines: Codex MCP tool timeout, SDK request timeout, and any elicitation/client timer. Do not assume increasing tool_timeout_sec disables every deadline or guarantees indefinite waiting.
- Deliberately expire question 2 of a three-question sequence. Answer question 2 at the Codex prompt, reconcile that answer through the tool, show question 3 through MCP, and finish with all three answers exactly once. Repeat with MCP reconnection and a second timeout.
- Verify that ordinary prompt input is possible after timeout, that the model uses the custom tool consistently, and that current host instructions allow the intended fallback and continuation.
- Capture findings and an implementation decision before broad integration. If native elicitation cannot meet the contract, evaluate a terminal/tmux UI backed by durable question storage; do not silently weaken the timeout requirements. A Codex fork/custom client is not the default solution.

## Phase 2 — implementation after prototype validation

- Harden the question schema, validation, persistence, cancellation, stale-answer handling, session isolation, and recovery. Cover option labels/descriptions and free text; verify multi-select and long-question support before promising parity with AskUserQuestion.
- Register/install the server through ait setup and cover codeagent, skillrun, direct project sessions, and resumed sessions as appropriate. A plugin may package the server and guidance; it does not itself replace Codex's built-in tool implementation.
- Update the canonical Codex tool mapping and relevant rendered skill guidance to use the custom tool for attended workflow questions and to implement the timeout-to-prompt-to-MCP continuation explicitly. Preserve unattended execution-profile behavior.
- Audit task-workflow approval/finalization fallbacks so missing answers do not cause automatic commit/archive or other dependent actions. Keep ordinary workflow decisions separate from sandbox/security permission approvals.
- Check monitor/minimonitor/shadow recognition of custom forms and awaiting-chat-answer states. Document configuration, supported clients, timeout behavior, recovery, and limitations.
- Reuse suitable pieces of chatlink's relay storage, IDs, atomic answer publication, and validation. Its current 90-second timeout creates a terminal answer and is not this requested recoverable state; do not change existing chatlink semantics accidentally.

## Acceptance and validation

- The three-question timeout/prompt-answer/MCP-resume scenario succeeds in a real attended Codex Default-mode session, including reconnect and repeated-timeout cases.
- No required decision is treated as answered because a timer elapsed, the UI disappeared, or the MCP tool returned empty content.
- Previously accepted answers survive recovery; remaining questions return through the custom tool; the workflow continues once only after all required answers.
- Cancellation, ambiguous/unrelated prompt input, late/duplicate form answers, concurrent sessions, unavailable server, and restart are covered by appropriate automated tests and live verification.
- The prototype report precedes full integration and clearly separates observed support from assumptions. Deliver implementation, setup/mapping changes, docs, and reproducible live verification steps under this task; split child tasks during planning if useful.

## Relevant code and prior work

- .agents/skills/codex_tool_mapping.md and its setup/source-generation path
- .aitask-scripts/aitask_setup.sh; seed/codex_config.seed.toml
- .aitask-scripts/aitask_codeagent.sh; .aitask-scripts/aitask_skillrun.sh; .aitask-scripts/lib/agent_string.sh
- .claude/skills/task-workflow/ and Codex-rendered workflow procedures
- .aitask-scripts/chatlink/relay.py; .aitask-scripts/chatlink/relay_ask.py; .aitask-scripts/aitask_relay_ask.sh
- aidocs/chat/qa_relay_protocol.md
- Related existing task t1180 covers older Default-mode live verification; inspect its assumptions, but it is not a prerequisite for this implementation.

## Upstream references (investigated 2026-11-11; recheck at implementation)

- Exact custom-skill instruction conflict: https://github.com/openai/codex/issues/53829
- Default-mode timeout and proposed blocking configuration: https://github.com/openai/codex/issues/37472 (default_mode_is_blocking was a community prototype proposal, not a verified stock setting)
- Explicit blocking behavior: https://github.com/openai/codex/pull/36410
- Async UI lifetime issue, distinct from the instruction conflict: https://github.com/openai/codex/issues/54136
- OpenAI MCP form fallback example: https://github.com/openai/codex-security/blob/main/plugins/codex-security/mcp-app/server.ts (request_codex_security_user_input)
- Codex MCP configuration: https://learn.chatgpt.com/docs/extend/mcp
- MCP elicitation: https://ts.sdk.modelcontextprotocol.io/v2/servers/elicitation

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-11T11:02:28Z status=pass attempt=1 type=human

> **❌ gate:plan_approved** run=2026-11-12T05:08:08Z status=fail attempt=2 type=human
>
> Note: aborted

> **✅ gate:plan_approved** run=2026-11-12T07:07:53Z status=pass attempt=3 type=human

> **✅ gate:review_approved** run=2026-11-13T10:14:37Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-13T12:16:44Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:ef855a3e752347ad

> **✅ gate:risk_evaluated** run=2026-11-13T12:16:44Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2281/risk_evaluated_2026-11-13T12:16:44Z-risk_evaluated-a1.log`
