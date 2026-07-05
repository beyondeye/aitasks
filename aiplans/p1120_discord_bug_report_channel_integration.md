---
Task: t1120_discord_bug_report_channel_integration.md
Base branch: main
plan_verified: []
---

# t1120 — Discord bug-report channel integration (umbrella decomposition plan)

---
Task: t1120_discord_bug_report_channel_integration.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
---

## Context

t1120 is an umbrella feature: a Discord channel configured as **bug-report intake**
for a linked repo. An authorized user's message in that channel produces a thread,
a **sandboxed headless code agent** running an aitask-explore-like flow over the
repo, a structured Q&A relay (agent questions → Discord components, answers gated
to the initiating user), and a finalized committed aitask (summary + reactions as
status posted back to the thread). The task mandates splitting into child tasks at
planning time (like t1074). **This plan is the decomposition** — 7 children + an
aggregate manual-verification sibling + 1 standalone follow-up task.

**Dependency status update (verified during planning):**
- **t1074_2 (Discord adapter) is DONE** (archived) — the hard dependency is
  satisfied. `DiscordAdapter` (`.aitask-scripts/chat/discord_adapter.py:659`,
  `connect(token, *, guild_id=None)` at :699) is live. t1074_3 (Slack) is
  Implementing but NOT on t1120's critical path.
- `agentcrew_runner.py` lives at `.aitask-scripts/agentcrew/agentcrew_runner.py`
  (task file cites `monitor/` — wrong dir). `_launch_headless` (:410-424) is the
  unsandboxed Popen reference; `openshell_headless`/`openshell_interactive` are
  stubs raising `LaunchError` (owned by t562, status Ready — not started).
- **No relay IPC, no headless explore path, no Docker/sandbox support exist
  anywhere in the repo** — all three are greenfield.
- `aidocs/chat/discord_bot_setup.md` explicitly defers token storage schema,
  allowed-user/role policy, and channel-routing config to t1120's runtime layer.
- `claude -p` headless print mode carries a billing surcharge
  (`aidocs/framework/shell_conventions.md:40-47`) — any headless invocation must
  be gated behind an explicit opt-in flag (as `batch-review --headless` does).

## Design decisions (confirmed with user)

1. **Q&A relay = structured channel** (Hermes-style): agent emits structured
   question events; gateway renders them as Discord components. No tmux
   screen-scraping.
2. **Generic relay protocol, explore wired first**: the question-event schema is
   skill-agnostic; only the explore flow is wired in this umbrella.
3. **Sandbox = Docker first**: minimal Docker backend now; the launch seam is
   shaped so t562's openshell modes slot in later as alternate backends.
4. **Gateway scope = per-workspace** (applink model), plus a **standalone
   follow-up task for multi-repo/multi-server gateway support**.

## Architecture summary

New package `.aitask-scripts/chatlink/` mirroring applink's proven split:
Textual-free headless daemon (cf. `applink/headless.py`) + shared pure core
(router/policy cf. `applink/router.py`, `profiles.py`), runtime state under
`aitasks/metadata/chatlink_sessions/` (0o700, cf. `applink/paths.py`), shared
config under `aitasks/metadata/`, audit log (cf. `applink/audit.py`). Transport
is `ChatAdapter.subscribe()` (broadcast, at-least-once while connected, **no
replay across disconnect; INTERACTION_RECEIVED non-replayable → persist
interaction outcomes on receipt**, re-query via `fetch_history(after=)`).
All gateway logic developed and tested against `MockChatAdapter`
(`chat/mock.py:73`, seams: `inject_message`, `inject_interaction`,
`simulate_disconnect`, `set_identity_claims`, `set_window_closed`).

The relay IPC seam is a **file-based JSON spool** in a bind-mountable directory
(identical for local subprocess and Docker container). The agent never talks to
Discord; the gateway owns the conversation (Hermes model: the agent is a
mediated subprocess). The sandboxed agent works on a **disposable workspace
copy** (not a live-repo mount) with writable relay/output mounts only; the
finalized aitask is committed by the **gateway** from the agent's output
payload — the agent never touches git or credentials beyond its LLM API key.

### Verified adapter primitives (checked against current source)

Everything the flow needs already exists on the **frozen** `ChatAdapter`
surface and is implemented by `DiscordAdapter`:
- Modal opening: `open_modal(interaction, modal)` (`adapter.py:402`); must beat
  the scheduled defer (`discord_adapter.py:822`, `_defer_later`).
- Ephemeral "expired" replies: `respond(interaction, text, ephemeral=True)`
  (`adapter.py:367`) and `send_ephemeral` fallback chain (`adapter.py:122`).
- Component disabling: `edit_message(message, text, components=)`
  (`adapter.py:83`) + `Button(disabled=True)` (`interactions.py:38`).
- Routing: `Interaction.custom_id` / `Interaction.values` round-trip
  (`interactions.py:213`); expiry raises `InteractionExpired`.

**Escalation rule:** the `ChatAdapter` surface is frozen (adapters add no
public methods). If any child discovers a genuinely missing adapter behavior,
it must NOT hack it into chatlink or the adapter — first try `metadata` dicts;
if a real contract extension is needed, create a follow-up **t1074 child** and
scope the chatlink child around it. No silent adapter forks.

### Crash ownership & startup reconciliation (gateway death story)

Chat reconnect reconciliation alone is not enough: if the gateway dies while
containers/relay sessions are live, the supervisor and death→cancellation path
die with it. Therefore:
- Every spawned container carries labels `ait.chatlink.session=<session_id>`
  and `ait.chatlink.workspace=<workspace_id>` — orphans are discoverable
  statelessly (`docker ps --filter label=…`), consistent with the
  stateless-routing philosophy.
- **On daemon startup, a reconciliation/reaper pass runs before intake**:
  (a) enumerate labeled containers → kill/remove any past wall-clock cap or
  whose session state is terminal/absent; (b) scan `<relay_root>/` → sessions
  with no live container are marked failed, pending questions get `cancelled`
  answers (spool hygiene), Discord messages best-effort edited (components
  disabled, ❌ reaction); (c) half-created session state (crash between
  persist steps) is resolved fail-closed (mark failed, never resume a
  half-session). Stale relay dirs are removed after their terminal state is
  persisted.
- Ownership: session-state reconciliation lives in t1120_3; the container
  reaper (label enumeration, kill/remove) lives in t1120_5 behind the launcher
  seam (`reap_orphans(workspace_id)`); t1120_6 adds the e2e
  crash-restart-reconcile test (kill daemon mid-question, restart, assert
  reaped + reconciled).

## PINNED cross-child contracts

These are normative for every child plan; each child plan restates the parts it
consumes verbatim.

0. **Contract freeze rule** — contracts 1–13 are provisional until t1120_1's
   Step-0 spike passes. **Back-propagation is not just the parent plan**: if
   the spike forces a contract change, t1120_1 MUST update (a) this parent
   plan's pinned contracts, (b) **every already-created sibling task file and
   child plan file that embeds the changed contract text** (they are created
   up front and carry snapshots for self-containment), committing all of it
   via `./ait git` in one pass — no stale embedded copies may survive.
   Each child plan carries a header line
   `Contracts: snapshot of parent plan §PINNED — provisional until t1120_1
   freeze` so a fresh context knows to re-check; after t1120_1 archives, this
   parent plan's freeze status flips to FROZEN (t1120_1's plan records the
   flip) and snapshots are authoritative.
1. **Canonical `session_id`** — one per spawned agent: **short opaque id**,
   format `s<base36-epoch-seconds><2-char random>` — **max 12 chars**, charset
   `[a-z0-9]`. Appears in: relay session dir name, Discord `custom_id`s,
   container label, audit lines, output payload. The relay lib is the single
   mint point and validates length/charset at construction.
2. **Relay spool layout** (t1120_1 ↔ 3 ↔ 4 ↔ 5):
   `<relay_root>/<session_id>/question-<seq>.json`, `answer-<seq>.json`,
   `payload.json` (final output), `status.json`. **Atomic writes everywhere**:
   write `*.tmp`, rename; readers ignore `*.tmp` (applink `sessions.json`
   pattern).
3. **Question schema** (generic, skill-agnostic) *(amended by t1120_1 —
   stable option values)*:
   `{id, seq, session_id, text, header, options: [{value, label,
   description}], multi_select: bool, allow_free_text: bool, timeout_s}`.
   Option `value` is a stable id **auto-assigned by the relay lib at
   question-write time** as `o<idx>` (zero-based, `[a-z0-9]`) — callers never
   pass values; labels are display-only (non-empty, ≤ 100 chars; values are
   unique by construction).
   **Answer schema:** `{id, seq, status: answered|timeout|cancelled,
   values: [..], free_text: str|null, answered_by}` — `values` carries option
   **values** (not labels).
   One question in flight at a time (sequential v1); batch is a documented
   extension point, not implemented.
4. **`custom_id` encoding** — statelessly parseable
   `cl1:<session_id>:<seq>:<component>` with **pinned length budget**:
   prefix `cl1` (3) + session_id ≤ 12 + seq ≤ 6 digits (decimal, monotonic
   per session) + component tag ≤ 8 chars (`[a-z0-9_]`), plus 3 separators —
   worst case 32 chars, hard-validated ≤ 100 (Discord limit) by the relay lib
   at construction (reject, never truncate). **Restart safety is stateless**:
   routing derivable from `custom_id` + spool state alone (question-N present
   ∧ answer-N absent ⇒ pending); no in-memory-only routing maps.
5. **Free-text = two-step modal dance**: question message carries an "Answer…"
   button; on that interaction the gateway calls `open_modal` immediately
   (must beat the ~2 s scheduled defer, `discord_adapter.py:822`). Late/expired
   clicks get an ephemeral "question expired".
6. **Timeout/cancel ownership** *(amended by t1120_1 — durable timeout)*: the
   agent-side blocking helper owns the timeout (bounded default, fail-safe —
   on timeout the agent proceeds with `status: timeout`, never hangs). **The
   timeout is a durable spool state**: at the deadline the helper does a final
   poll — if an answer appeared it is consumed as answered; otherwise the
   helper atomically writes `answer-<seq>.json` `{status: timeout, values: [],
   free_text: null, answered_by: null}` before proceeding (never overwriting
   an existing answer file). A timed-out question is therefore terminal, not
   forever-"pending" — restart-derivability (contract 4) and gateway
   reconciliation read it from the spool. The gateway disables components
   (message edit) on timeout/cancel/agent-death and writes `cancelled` answers
   for spool hygiene on agent death. Stale answers (seq already passed) are
   ignored; an interaction for a seq whose answer file already exists is stale
   ⇒ ephemeral "question expired".
7. **Agent output contract** (4 ↔ 5 ↔ 6): agent writes `payload.json`
   (task-creation payload: name/title, priority, effort, issue_type, labels,
   description markdown) and exits; exit code + `payload.json` presence =
   completion signal. **The gateway creates and commits the aitask via
   `aitask_create.sh --batch` + `./ait git`** — the agent has no git access.
   **The payload is untrusted input** (prompt-influenced agent): before any
   `aitask_create.sh` call the gateway MUST validate it — JSON schema
   (required fields, types, no extra keys); field allowlists (`issue_type`
   from `aitasks/metadata/task_types.txt`, `labels` ⊆ `labels.txt`,
   priority/effort ∈ {high,medium,low}); size limits (title ≤ 120 chars, name
   slug `[a-z0-9_]` ≤ 64, description ≤ 64 KiB); description passed as plain
   body content via argv/`--desc-file -` (never shell interpolation, never
   user-controlled frontmatter keys); control characters stripped. **Reject
   fail-closed**: invalid payload ⇒ session failed, ❌ + reason in thread,
   audit entry, nothing created — never partial creation or "fix-up" of a bad
   payload.
8. **Backend-agnostic launcher seam, aligned with launch_modes/t562**
   (5 ↔ t562): the seam lives in `lib/` (e.g. `lib/sandbox_launch.py`) as a
   mode registry mirroring `lib/launch_modes.py`'s
   `VALID_LAUNCH_MODES`/`LAUNCHERS` pattern:
   `launch(spec) -> handle{wait(), kill(), alive()}` +
   `reap_orphans(workspace_id)`, where `spec` bundles workspace-copy path,
   relay dir, env allowlist, resource limits, session_id. It adopts t562's
   decided semantics up front so openshell is a drop-in second backend, not a
   post-hoc reconciliation: workspace **delivery by copy/upload** (t562
   `--upload`), sandbox/container **named from session identity** (t562
   `agent-<crew>-<name>` convention → here the session_id label), headless =
   non-interactive no-TTY, explicit cleanup verb. t1120_5 updates t562's task
   definition (via `./ait git`) to target this shared seam — a scope
   alignment, not just a pointer.
9. **Policy API** (2 ↔ 3): `decide(claims: IdentityClaims, config) ->
   Decision{allow: bool, reason: str}` — deny-by-default;
   `initiating-user-only answer gating` is a named primitive of the policy
   layer, not ad-hoc checks in the daemon.
10. **Config & secrets** (2 ↔ 3 ↔ 6): shared config
    `aitasks/metadata/chatlink_config.yaml` (intake channel ref, allowed
    users/roles, repo linkage, ceilings); bot token in a gitignored per-PC file
    under `aitasks/metadata/chatlink_sessions/` with 0600 (applink `paths.py`
    style). No env-var names invented outside t1120_2.
11. **Ceilings (DoS posture, t985/applink `server.py:42` style)**: max
    concurrent sandboxes, per-user intake rate limit, container
    `--memory/--cpus/--pids-limit`, wall-clock cap — constants defined in
    t1120_2 config, enforced in t1120_3 (intake) and t1120_5 (container).
12. **Renderer degradation** (1): >25 options ⇒ paginated select or
    reject-with-reason; >2000 chars ⇒ chunked messages; branch on
    `Capabilities`, never platform name.
13. **Injection surface**: bug-report text is attacker-adjacent. All process
    construction is argv-list only (never shell interpolation); prompt
    injection is mitigated by sandbox + gateway-owned commit, not by prose
    sanitizing.

## Child decomposition

Children auto-depend on prior siblings (sequential); each child owns its tests
(testability-first: pure units early). Effort/priority set per child.

1. **t1120_1 `relay_protocol_library`** (feature, high priority, medium effort)
   **Step 0 (FIRST, before any contract-consuming code): throwaway
   headless-relay spike** — hand-write a minimal skill that calls a blocking
   relay helper stub, invoke the agent headlessly (`ait codeagent … invoke raw
   -p`), hand-write the answer file, and verify the round trip (question
   emitted → agent blocks → answer consumed → agent continues). This validates
   the umbrella's central assumption while contracts are still provisional
   (contract 0); spike findings are back-propagated into the parent plan's
   pinned contracts before the real implementation starts. Then: design doc
   (`aidocs/chat/qa_relay_protocol.md`) + implementation of the generic Q&A
   relay: spool read/write lib (`chatlink/relay.py`, pure stdlib, atomic
   writes, session_id mint point, custom_id length validation),
   question→component renderer + answer assembly (`chatlink/render.py`,
   consumes `chat/interactions.py`, degradation rules), agent-side blocking
   helper `aitask_relay_ask.sh` (+ small Python core for testability) with
   timeout ownership. Unit tests incl. restart-derivability and stale-answer
   negative controls.
2. **t1120_2 `chatlink_config_authorization`** (feature, high, medium)
   Config schema + loader (`chatlink/config.py`), token storage/paths
   (`chatlink/paths.py`), policy layer (`chatlink/policy.py`:
   `decide()`, initiating-user gating primitive, deny-by-default), ceilings
   constants, `ait setup` seeding of the config file (extension-points doc
   rules). **Secrets hygiene owned here**: add/verify the `.gitignore` rule
   for `aitasks/metadata/chatlink_sessions/` (mirroring applink_sessions) and
   enforce dir 0700 / token file 0600 — with a unit test asserting
   `git check-ignore` matches the token path and permissions are set on
   creation. Pure unit tests incl. deny-by-default negative controls.
3. **t1120_3 `gateway_daemon_core`** (feature, high, high)
   `chatlink/daemon.py` (Textual-free, applink `headless.py` skeleton):
   `subscribe()` intake loop (drop `is_self`/`is_bot`), policy check, thread
   creation (`create_conversation(THREAD, parent=MessageRef)`), session/state
   persistence (interaction outcomes persisted on receipt), **pure
   reconnect-reconciliation unit** (`fetch_history(after=)` diff + persisted
   outcome replay guard — separately tested), **startup
   session-reconciliation pass** (fail-closed resolution of half-created
   sessions, cancelled-answer spool hygiene, best-effort Discord message
   cleanup — see crash-ownership section), audit log, intake ceilings.
   Internal module split pinned to mirror applink (`daemon`/`intake`/
   `sessions_store`/`audit`). Launcher `ait chatlink --headless` via a new
   `aitask_chatlink.sh`. All tests against `MockChatAdapter` incl.
   `simulate_disconnect` negative controls.
4. **t1120_4 `chat_native_explore`** (feature, high, high)
   A **dedicated skill** (pickrem precedent — separate contract, not a runtime
   branch in aitask-explore): explore-like flow whose every decision point
   calls `aitask_relay_ask.sh` instead of AskUserQuestion, ending in
   `payload.json` (contract 7). New `ait codeagent` operation (e.g.
   `explore-relay`) with explicit opt-in headless flag (billing caveat).
   Builds on the t1120_1 Step-0 spike findings (assumption already validated).
   Skill-authoring conventions apply (stub/j2/goldens).
5. **t1120_5 `docker_sandbox_backend`** (feature, high, high)
   Launcher seam (contract 8, `lib/sandbox_launch.py` registry aligned with
   `lib/launch_modes.py` and t562 semantics) + Docker backend: disposable
   workspace copy (clone/archive of committed HEAD — t562 `--upload`
   semantics), writable relay/output mounts, env allowlist (LLM key only; no
   bot token, no git creds), resource limits, wall-clock supervision,
   exit/liveness detection, death→cancellation (contract 6), **container
   labels + `reap_orphans()` reaper** (crash-ownership section),
   Dockerfile/image ownership (ait + agent CLI + deps). **In-container relay
   smoke test** (owned by this child, before t1120_6's glue): spawn the real
   container with mounted relay dir, a stub agent script inside asks one
   question via `aitask_relay_ask.sh`, host writes the answer, assert
   continuation + `payload.json` lands — proves bind mounts, env allowlist,
   workdir layout, and agent-CLI availability inside the image together
   (skip-capable when `docker` is absent). `docker` presence check wired into
   setup/doctor path. **Updates t562's task definition to target the shared
   seam** (scope alignment, committed via `./ait git`).
6. **t1120_6 `end_to_end_flow_tui`** (feature, high, high)
   Glue: message → policy → thread → spawn → relay Q&A → payload →
   payload validation (contract 7, fail-closed) → `aitask_create.sh --batch`
   + `./ait git` commit → thread summary + reactions-as-status (pinned emoji
   vocabulary: ⏳ working, ❓ awaiting answer, ✅ task created, ❌
   failed/denied). Minimal chatlink TUI (status/sessions/audit view) +
   `lib/tui_registry.py` registration. Full e2e tests against
   `MockChatAdapter` (multi-thread concurrency, **crash-restart-reconcile:
   kill daemon mid-question, restart, assert reaped + reconciled**,
   malformed-payload rejection, unauthorized-user negative control). Emits a
   real `## Verification` section (seeds the MV sibling).
7. **t1120_7 `chatlink_docs`** (documentation, medium, low)
   User-facing website docs (workflows page + `_index.md` bullet) + aidocs
   runtime doc for chatlink (setup: bot config → channel config → run daemon).
   Chat-platform user docs were explicitly deferred to t1120. Generic naming
   conventions (no real repo names; "cross-repo" not "sister").

**Aggregate manual-verification sibling** (offered post-creation per workflow):
live Discord server run — bot setup, authorized/unauthorized message, full
Q&A round-trip, task commit, reactions.

## Follow-up task (standalone, not a child)

- `chatlink_multi_repo_gateway` — extend the per-workspace gateway to serve
  multiple repos/Discord servers from one daemon (Hermes model): repo-routing
  config, per-repo channel map, cross-workspace process management. Created at
  child-creation time with `followup_of: 1120`.

## Verification (umbrella level)

- Each child's tests pass individually (bash test scripts, self-contained).
- e2e acceptance in t1120_6 against `MockChatAdapter` covers the umbrella AC
  (authorized flow end-to-end; unauthorized ignored/ephemeral-denied; no
  live-platform calls in the suite).
- Live Discord validation via the aggregate MV sibling.

## Step 9 reference

Parent archival follows task-workflow Step 9 once all children complete: gate
check (`risk_evaluated` declared), archive script, push. The umbrella itself
lands no code.

## Risk

### Code-health risk: medium
- New always-on asyncio daemon + subprocess supervision — race hazards around
  reconnect reconciliation and interaction-outcome persistence · severity:
  medium · → mitigation: embedded (pure reconciliation unit + disconnect
  negative-control tests pinned in t1120_3)
- Shared-surface edits (`aitask_codeagent.sh` dispatch, launcher seam next to
  agentcrew, `ait setup`, tui_registry) could regress existing flows ·
  severity: medium · → mitigation: embedded (additive-only edits; each child
  owns regression tests for the surface it touches)
- Security surface: attacker-adjacent channel input spawns processes ·
  severity: medium · → mitigation: embedded (contract 13 argv-only, contract 11
  ceilings, sandbox + gateway-owned commit; uniform across children)

### Goal-achievement risk: medium
- Central unvalidated assumption: a headless agent reliably runs a skill that
  blocks on `aitask_relay_ask.sh` instead of AskUserQuestion · severity: high ·
  → mitigation: embedded (t1120_1 Step-0 throwaway spike, sequenced FIRST —
  before any contract-consuming code is built; contract-freeze rule 0 makes
  the pinned contracts provisional until it passes)
- Gateway crash while containers/relay sessions are live could orphan
  resources · severity: medium · → mitigation: embedded (crash-ownership
  section: labeled containers, startup reconciliation/reaper in t1120_3/5,
  e2e crash-restart test in t1120_6)
- Docker image with agent CLI + API key + network is feasible but heavy;
  first-run friction may be significant · severity: medium · → mitigation:
  embedded (t1120_5 owns image contract + setup/doctor check; MV sibling
  validates live)
- Discord free-text modal timing (must beat scheduled defer) could be flaky in
  practice · severity: low · → mitigation: embedded (contract 5 two-step dance;
  MV sibling exercises it live)
