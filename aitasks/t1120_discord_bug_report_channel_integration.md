---
priority: medium
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [chat_surface, python, sanboxing]
gates: [risk_evaluated]
children_to_implement: [t1120_1, t1120_2]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-05 08:27
updated_at: 2026-07-05 11:58
---

## Goal

A Discord channel configured as a **bug-report intake** for a linked repo: when an
authorized user posts a bug report in that channel, a thread is created from the
message and a **sandboxed headless code agent** is spawned to run an
aitask-explore-like flow over the repo, searching sources for probable causes. The
agent's clarifying questions are relayed into the thread as Discord interactions,
answerable **only by the initiating user**, and the flow ends with a finalized
aitask tracking the bug (posted back to the thread with a summary +
reactions-as-status).

This is a **complex umbrella task — must be split into child tasks at planning
time** (like t1074 was).

## Dependencies / coordination

- **Hard dependency: t1074_2 (Discord adapter).** The chat abstraction core
  (t1074_1, `.aitask-scripts/chat/`) already landed; the gateway logic can be built
  and tested against `MockChatAdapter` before t1074_2 lands, but live operation
  needs the real Discord adapter.
- **Coordination (not folded): t562 (openshell launch semantics)** — implements
  the `openshell_headless`/`openshell_interactive` launch modes stubbed in
  `agentcrew_runner.py`; the sandboxed-spawn child here should reuse/extend that
  work rather than reimplement it. **t427 (openshell integration brainstorm)** is
  the broader openshell-integration task — also kept separate.

## What already exists (exploration findings)

- **`.aitask-scripts/chat/` (t1074_1, landed)** — the platform-agnostic substrate:
  - `ChatAdapter.subscribe()` (adapter.py:415) — the event-stream primitive for
    monitoring the bug-report channel (no replay across disconnect;
    `INTERACTION_RECEIVED` non-replayable — persist outcomes on receipt).
  - `create_conversation(kind=THREAD, parent=MessageRef)` (adapter.py:147) — the
    "thread from bug-report message" primitive.
  - `edit_message` (adapter.py:83) — progress streaming = repeated edits.
  - `interactions.py` — Button/SelectMenu/Modal/ActionRow + normalized
    `Interaction` round-trip (custom_id → values): the substrate for relaying
    agent questions to the Discord user.
  - `IdentityClaims` + `fetch_identity_claims` (model.py:281) — raw authorization
    claims; the allowlist/policy layer is explicitly deferred to a higher layer
    (does not exist yet).
  - `MockChatAdapter` (mock.py:73) with test seams (`inject_message`,
    `inject_interaction`, `simulate_disconnect`) — build all gateway logic
    platform-free.
- **Applink is the gateway architecture template** (`.aitask-scripts/applink/`):
  Textual TUI (`applink_app.py`) / Textual-free headless daemon (`headless.py`) /
  `server.py` (connection state machine, DoS ceilings) / `router.py` (pure verb
  dispatch + permission-profile gating) / `sessions.py` (token model) /
  `profiles.py` (tiered profiles in `aitasks/metadata/`) / `audit.py`. Clone the
  *architectural style* for the chat gateway; the transport is
  `ChatAdapter.subscribe()` instead of a WebSocket listener.
- **Headless agent spawn exists but unsandboxed:**
  `agentcrew_runner._launch_headless` (:410) does
  `Popen(ait codeagent --agent-string ... invoke raw -p <prompt>)`.
  `openshell_headless`/`openshell_interactive` are registered launch modes
  (`lib/launch_modes.py:26`) whose launchers raise `LaunchError` (stubs).
- **`ait codeagent` operations** (`aitask_codeagent.sh`,
  `SUPPORTED_OPERATIONS=(pick explain batch-review qa explore raw shadow learn)`):
  `explore` exists but is interactive-only; `raw` passes an arbitrary prompt.
- **No structured question relay exists.** Prompt detection today is regex
  screen-scraping (`monitor/prompt_patterns.py`, no options capture); the shadow
  agent reads questions but is advisory-only; applink can inject raw keystrokes
  through a profile gate but has no structured Q&A round-trip.
- **Hermes agent reference** (https://github.com/NousResearch/hermes-agent,
  https://hermes-agent.nousresearch.com/docs/user-guide/messaging/): single
  background gateway process for all platforms; agent process separate from the
  gateway; sandboxing via pluggable terminal backends (local, Docker, SSH,
  Singularity, Modal, Daytona); deny-by-default allowlist or DM pairing; admin vs
  regular user tiers per scope (DM vs channel); `/approve`-`/deny` for dangerous
  commands; interrupt-by-message (SIGTERM/SIGKILL); reactions as status. Model to
  adopt: **the gateway owns the conversation; the agent is a mediated subprocess
  in a container backend** — per-user permission restriction is secondary to
  execution isolation.

## Proposed child decomposition (finalize at planning time)

1. **Chatlink gateway daemon + TUI** — applink-style split (Textual-free headless
   daemon + TUI front-end); owns the `subscribe()` loop, bug-report channel
   watching, thread lifecycle, session/state persistence (interaction outcomes
   must be persisted on receipt). Developed against `MockChatAdapter`.
2. **Authorization + channel/repo config layer** — policy above `IdentityClaims`:
   which channel is bug-intake, which users/roles may initiate,
   initiating-user-only answer gating; repo ↔ Discord-server linkage config under
   `aitasks/metadata/` (applink `profiles.py` as the model).
3. **Structured Q&A relay protocol** — agent ↔ gateway IPC seam: the spawned agent
   emits structured question events (options/free-text), the gateway renders them
   as Discord selects/modals, answers route back to the agent. Design doc first;
   this is the riskiest novel piece.
4. **Chat-native explore operation** — a headless `explore` variant for
   `ait codeagent` that uses the relay instead of AskUserQuestion (the inverse of
   aitask-pickrem's no-questions contract).
5. **Sandboxed spawn** — launch the gateway-spawned agent in a sandbox without
   granting it extra permissions (the human in the loop is on Discord, not at the
   terminal). Reuse/extend t562's openshell launch modes; consider a plain Docker
   backend as the minimal first target (Hermes precedent: pluggable backends).
6. **End-to-end bug-report flow** — glue: message → authorization check → thread →
   sandbox spawn → explore with Q&A relay → task creation → thread summary +
   reactions-as-status; live manual-verification follow-up against a real Discord
   test server.

## Open questions for planning

- Relay design: structured agent-side channel (preferred, Hermes-style) vs tmux
  screen-scrape + keystroke injection (reuses monitor machinery, fragile).
- Generic relay (any skill's questions) vs explore-specific first iteration.
- Sandbox backend: openshell (waits on t562) vs minimal Docker path first.
- Where the gateway daemon lives: new `.aitask-scripts/chatlink/` package
  mirroring `applink/`?
- Single gateway process for multiple repos/servers, or one per workspace
  (applink is per-workspace; Hermes is a single multi-platform gateway).

## Acceptance criteria (umbrella level)

- An authorized user's message in the configured Discord channel produces a
  thread, a sandboxed exploring agent, an interactive Q&A limited to the
  initiating user, and a committed aitask for the bug.
- Unauthorized users' messages are ignored (or get an ephemeral denial); the
  agent never gains permissions beyond its sandbox.
- All gateway logic unit-tested against `MockChatAdapter`; no live-platform calls
  in the test suite.
