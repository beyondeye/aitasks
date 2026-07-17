---
priority: high
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [workflows, remote, python, tui, codeagent, sanboxing, crash_recovery]
gates: [risk_evaluated]
children_to_implement: [t1157_1, t1157_2, t1157_3, t1157_4, t1157_5, t1157_6, t1157_7, t1157_8, t1157_9, t1157_10]
folded_tasks: [1127, 1144]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-17 11:50
updated_at: 2026-07-17 16:57
---

## Goal

Evolve Chatlink from a single hard-coded bug-intake daemon into a provider-neutral, multi-workflow host that ships on Discord first. Preserve bug intake as a focused workflow, remove value-degrading interaction limits, and add a separate open-ended remote explore workflow that approaches native `aitask-explore` behavior while retaining sandbox isolation and gateway-owned task creation.

## Confirmed product decisions

- Chatlink is one shared workflow host/TUI, not one daemon per workflow.
- The initial triggers are distinct configured channels: a bug-intake channel and an open-ended explore channel.
- Remote explore may create an aitask only; it may not implement code or mutate source.
- Workflow routing is provider-neutral, but Discord is the only required production integration in the first release.
- Use one Discord bot connection across configured guilds and registered projects.
- Configuration is layered: checked-in workflow definitions live per project, while a per-machine host registry enables projects/connections and owns secret locations.
- Preserve legacy singleton bug-intake configuration through a compatibility reader and explicit wizard migration.
- Use visible time budgets rather than a small turn cap. Defaults are 30 minutes for bug intake (20 exploration + 10 synthesis reserve) and 60 minutes for remote explore (45 exploration + 15 synthesis reserve). Each question shows remaining time, response deadline, named timeout behavior, and is clamped to the remaining active budget.
- Never create a task on timeout. The agent writes an unapproved proposal and exits; the gateway retains it for explicit approval.
- Durable workflow sessions are separate from disposable sandbox attempts. Paused/proposed sessions remain resumable for seven days.
- Existing threads expose both Resume (from checkpoint) and Restart (from original/thread context). New attempts inspect latest committed HEAD and revalidate carried findings.
- Request Changes launches a short revision attempt using the proposal, transcript, requested changes, and latest HEAD.
- Stage native parity: first ship intents, iterative Continue/Redirect/Create/Abort steering, metadata review, and task creation; later add Discord-adapted file selection, related-task folding, and cross-repo task shaping.
- Coordinate with the in-progress t1149 config/TUI work and extend its shipped surfaces rather than editing over them.
- Keep t1136, t1137, t1139, and t1140 as related independent multi-agent/auth work.

## Required architecture

1. Add a versioned workflow configuration schema, per-machine host registry, one-bot/many-guild routing, duplicate-trigger validation, global host locking/state, and legacy config/token compatibility.
2. Introduce durable workflow-session, attempt, checkpoint, transcript, and unapproved task-proposal records. Group attempt history by Discord thread and make controls initiator-only.
3. Generalize the daemon, event router, flow pump, reconciliation, task creation, audit, and TUI away from bug-specific singleton fields while preserving fail-closed behavior.
4. Harden bug intake: no arbitrary three-question limit, budget-aware clarification, durable incremental checkpoints, reserved synthesis, explicit approval only, and resume/restart support.
5. Add open-ended remote explore: intent selection, findings summaries inside interactions, Continue/Redirect/Propose/Pause/Abort loop, task metadata adjustment, proposal approval/revision, and no implementation handoff.
6. Add advanced parity for file selection, related-task discovery/folding with gateway-side revalidation, and cross-repo exploration/task shaping using registered read-only committed snapshots.
7. Extend the TUI and configuration wizard after t1149 lands with project/workflow/attempt health, budgets, paused/proposal states, aggregated preflight, and multi-workflow editing.
8. Add automated and live verification for multi-project/multi-guild routing, no cross-talk, more than three useful bug questions, deadline behavior, explicit approval, resume/restart/revision, retention expiry, daemon crash recovery, concurrent randomized sessions, and Discord UX.

## Safety and compatibility invariants

- Agent sandboxes never receive bot tokens, git credentials, or repository write access.
- Only the gateway validates proposals and creates/commits tasks.
- No task is created without an explicit initiator approval interaction.
- Active wait time counts against the sandbox lifecycle; final human approval does not keep a sandbox alive.
- Soft-budget expiry switches to synthesis; hard expiry pauses/fails closed from the latest checkpoint without partial creation.
- Legacy single-repo setups remain functional during migration.
- Parent/child task and plan commits continue to use `./ait git`; code commits remain separate.

## Merged from t1127: chatlink multi repo gateway


## Context

Follow-up of t1120 (Discord bug-report channel integration). t1120 delivers a
**per-workspace** chatlink gateway (applink model: one daemon per ait
workspace) by explicit design decision; this follow-up extends it to the
Hermes model — a **single gateway daemon serving multiple repos/Discord
servers**. Deferred from t1120 to keep the first iteration simple and pattern-
consistent with applink.

## Goal

One chatlink daemon can watch bug-intake channels across multiple linked
repos/Discord servers and route each session to the right workspace:

- **Repo-routing config**: per-repo channel map (channel ref → workspace),
  resolved via the `ait projects` registry (`~/.config/aitasks/projects.yaml`)
  — reference sibling projects by logical name, never by sibling-directory
  path.
- **Cross-workspace process management**: sandbox spawns and task commits
  execute in the routed workspace; `reap_orphans(workspace_id)` (already
  workspace-keyed in `lib/sandbox_launch.py` by design) scoped per workspace.
- **Config layering**: decide where multi-repo config lives (per-user vs
  per-workspace) without breaking t1120's per-workspace
  `aitasks/metadata/chatlink_config.yaml`.
- Multiple bot tokens / one bot across guilds — decide and document.

## Preconditions

- All t1120 children landed (relay, config/policy, daemon, explore skill,
  docker backend, e2e glue). Read `aiplans/archived/p1120*` first.
- The launcher seam and session store are already keyed by
  workspace/session_id (t1120 contracts 1, 8) — this task builds on those
  keys rather than refactoring them.

## Acceptance criteria

- Two configured repos, two channels, one daemon: a bug report in each
  channel produces a task committed in the correct repo, with no cross-talk
  (session routing verified by tests against MockChatAdapter).
- Single-repo setups keep working unchanged (t1120 config remains valid).

## Merged from t1144: chatlink flow concurrency soak


## Origin

Risk-mitigation ("after") follow-up for t1120_6, created at Step 8d after implementation landed.

## Risk addressed

Daemon-loop sequential-dispatch races + completion-vs-death misclassification:

- Daemon-loop integration (third merged-event source + death-path amendment) touches the load-bearing sequential-dispatch core; a pump mutating outside the loop or double-handling death would corrupt session state (code-health, medium).
- Completion-vs-death race: the sandbox watchdog fires on every container exit, so a missed payload check misclassifies successful sessions as failed (goal-achievement, medium).

## Goal

Soak/stress test for the chatlink flow: N concurrent mock sessions (MockChatAdapter + FakeLauncher, no live platform) with randomized event interleavings — intake, question spool writes, select/modal answers, payload writes, death signals — and repeated daemon kill-restart cycles over the same store. Assert:

- no cross-talk between sessions (answers/payloads route strictly by custom_id session_id);
- no double terminal transitions (each session reaches exactly one of done/failed exactly once, across restarts);
- correct completion-vs-death routing under racing orders (payload_ready vs death signal in both orders, including arrival during restart reconciliation);
- the pump's bounded queue and level-triggered scan never lose a session permanently (dropped events are regenerated);
- the sequential-dispatch invariant holds (no interleaved handler mutations — e.g. via a store-save spy asserting single-writer ordering).

Seed harness: `tests/test_chatlink_flow.sh` (t1120_6) — the Env class, spy create script, and wait_until helpers are directly reusable; add a seeded RNG so failures are reproducible from the printed seed.

## Folded Tasks

The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

- **t1127** (`t1127_chatlink_multi_repo_gateway.md`)
- **t1144** (`t1144_chatlink_flow_concurrency_soak.md`)
