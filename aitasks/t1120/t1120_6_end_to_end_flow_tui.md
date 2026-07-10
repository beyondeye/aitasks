---
priority: high
risk_code_health: medium
risk_goal_achievement: medium
effort: high
depends: [t1120_5]
issue_type: feature
status: Implementing
labels: [chat_surface, python]
gates: [risk_evaluated]
risk_mitigation_tasks: [1144]
assigned_to: dario-e@beyond-eye.com
anchor: 1120
implemented_with: claudecode/fable5
created_at: 2026-07-05 12:00
updated_at: 2026-07-10 09:06
---

## Context

Sixth child of t1120 — the glue that delivers the umbrella acceptance
criteria: message → policy → thread → sandbox spawn → relay Q&A → payload
validation → committed aitask → thread summary + reactions-as-status. Also
the minimal chatlink TUI. Parent plan:
`aiplans/p1120_discord_bug_report_channel_integration.md` (§PINNED + crash
ownership). All prior children (relay, config/policy, daemon, explore skill,
docker backend) are landed — read their archived plans
(`aiplans/archived/p1120/`) first.

**Contracts: snapshot of parent plan §PINNED — provisional until t1120_1
freeze (expected FROZEN by now — verify in the parent plan).** Consumes
contracts 6-7 (cancel semantics, payload validation), 10 (config), 12
(degradation) and the reactions vocabulary below.

## Payload validation (contract 7 — enforced HERE, fail-closed)

The payload is untrusted input (prompt-influenced agent). Before any
`aitask_create.sh` call the gateway MUST validate: JSON schema (required
fields, types, no extra keys); field allowlists (`issue_type` from
`aitasks/metadata/task_types.txt`, `labels` ⊆ `aitasks/metadata/labels.txt`,
priority/effort ∈ {high,medium,low}); size limits (title ≤ 120 chars, name
slug `[a-z0-9_]` ≤ 64, description ≤ 64 KiB); description passed via
argv/`--desc-file -` (never shell interpolation, never user-controlled
frontmatter keys); control characters stripped. **Reject fail-closed**:
invalid payload ⇒ session failed, ❌ + reason in thread, audit entry, nothing
created — never partial creation or "fix-up".

## Reactions-as-status vocabulary (pinned, used by tests)

⏳ working · ❓ awaiting answer · ✅ task created · ❌ failed/denied.
Applied to the original bug-report message; thread gets the summary post
(task id, title, plan pointer).

## Key deliverables

1. `chatlink/flow.py` (or equivalent per daemon module split) — session
   orchestration: spawn via the launcher seam, pump relay questions →
   `render.py` components → answers (initiating-user gating via
   `policy.may_answer`), progress via `edit_message`, completion → payload
   validation → `aitask_create.sh --batch` + `./ait git` commit (gateway
   identity; aitask-data branch semantics respected) → summary + ✅.
2. Task commit plumbing: create via
   `./.aitask-scripts/aitask_create.sh --batch --commit --desc-file -` with
   validated fields (argv-only), then `./ait git push` best-effort.
3. Minimal chatlink TUI (status/sessions/audit view) — read
   `aidocs/framework/tui_conventions.md` first; register in
   `lib/tui_registry.py` `TUI_REGISTRY` (switcher derives from it).
4. e2e crash-restart-reconcile test: kill daemon mid-question, restart,
   assert reaped (via fake launcher `reap_orphans`) + reconciled (session
   failed/cancelled per crash-ownership section).

## Verification (this section seeds the MV sibling)

Full e2e tests against `MockChatAdapter` + fake launcher (no live platform,
no docker):
- Authorized message → thread → Q&A round-trip (select + modal free-text) →
  valid payload → task file created + committed → summary + ✅.
- Unauthorized user ⇒ ignored/ephemeral denial, no spawn (negative control).
- Non-initiating user's interaction rejected (ephemeral), question stays
  pending.
- Malformed payload (bad issue_type / oversize description / extra keys) ⇒
  fail-closed rejection, ❌ + audit, nothing created.
- Multi-thread concurrency: two sessions in flight, answers route by
  custom_id session_id (no cross-talk).
- Crash-restart-reconcile (deliverable 4).
- Reactions vocabulary asserted at each state transition.

## Coordination (reverse pointers)

- **t1139** (`sandbox_llm_auth_docs_and_provisioning`) depends on this
  task: the LLM-key → `env_allowlist` config surface you land here is the
  surface t1139 extends (multi-provider + semi-automatic provisioning).
  Keep the config key / env-var naming minimal and extensible — t1139 must
  build on it, not replace it.
- **t1140** (`multi_agent_sandbox_roadmap`) also depends on this task
  (multi-agent explore-relay variants come after the e2e glue).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-09T08:11:04Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-10T06:03:41Z status=pass attempt=1 type=human
