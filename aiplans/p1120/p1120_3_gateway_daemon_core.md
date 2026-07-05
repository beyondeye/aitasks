---
Task: t1120_3_gateway_daemon_core.md
Parent Task: aitasks/t1120_discord_bug_report_channel_integration.md
Sibling Tasks: aitasks/t1120/t1120_4_*.md … t1120_8_*.md
Archived Sibling Plans: aiplans/archived/p1120/p1120_1_relay_protocol_library.md, p1120_2_chatlink_config_authorization.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/fable5 @ 2026-07-05 23:52
---

Contracts: snapshot of parent plan §PINNED — **FROZEN as of t1120_1** (child
snapshots authoritative; re-checked this pass — contracts 1–6, 9–11 consumed
here match the parent plan).

# Plan: t1120_3 — Chatlink gateway daemon core

Deliverables (7 items), load-bearing chat-layer semantics, and verification
list are in the task file (`aitasks/t1120/t1120_3_gateway_daemon_core.md`).
Archived plans of t1120_1 (relay lib API) and t1120_2 (config/policy/paths
APIs) are the sibling references; their "Notes for sibling tasks" are binding
here and folded into the steps below.

## Module split (pinned — mirrors applink)

All new modules are additive to `.aitask-scripts/chatlink/` (gateway-side —
they may import `chat`/`yaml`; the import-purity guard covers only
`relay`/`relay_ask`, unaffected). Update `chatlink/__init__.py` docstring
module list.

- `chatlink/daemon.py` — entry: load config first with **zero side effects**
  (`paths.config_file()` → `config.load_config()`; `None` from either ⇒
  refuse-to-start with two distinct messages), `paths.read_token()` (missing ⇒
  refuse, distinct message), construct adapter (injected; production
  `DiscordAdapter.connect(token)` imported lazily, tests `MockChatAdapter`),
  reconstruct intake ref via `ConversationRef.from_dict(config.intake_channel)`
  (normalization guarantees no raise; `intake_channel is None` ⇒ refuse),
  run startup reconciliation, then intake loop; signal handling per
  `applink/headless.py` `serve()` (:81-225): SIGINT/SIGTERM set an
  `asyncio.Event`, idle on `stop.wait()`, clean shutdown in `finally`.
- `chatlink/intake.py` — pure-ish pipeline over injected collaborators
  (adapter, policy, sessions_store, launcher, clock): event filtering
  (MESSAGE_CREATED on intake channel only, payload `{"message": Message}`;
  drop `event.actor.is_self` / `.is_bot`), authorization
  (`policy.decide(claims, config)` — claims via
  `adapter.fetch_identity_claims`; deny ⇒ per `config.deny_message_mode`
  `ignore` or ephemeral denial; audit with `Decision.reason`), per-user rate
  ceiling (**derived from persisted session records** — count sessions by
  initiator with `created_at` within the last hour vs
  `config.intake_rate_per_user_per_hour`; restart-proof, no in-memory-only
  counter) and `max_concurrent_sandboxes` bound (count non-terminal
  sessions), thread creation
  (`create_conversation(ConversationKind.THREAD, parent=<MessageRef>)`),
  session mint (`relay.create_session_dir(paths.relay_root())` — collision-
  retry inside), persist session record, hand to spawn seam.

  **Intake step order + per-step failure behavior (pinned).** The sequence
  after a policy pass is: (a) create thread → (b) mint relay session dir →
  (c) persist session record `state=spawning` → (d) `launcher.launch(spec)`.
  The record is persisted BEFORE launch so a crash between (c) and (d)
  leaves a `spawning` record that startup reconciliation fail-closes (no
  live agent ⇒ `failed`). Live-sequence failures (each audited with the
  step name + session/user ids):
  - (a) fails → nothing was created; audit; optional ephemeral notice; stop.
  - (b) fails → thread exists but no relay dir/record: best-effort ❌
    reaction + failure note in the thread; stop. (The annotated thread is
    the visible artifact; nothing dangling to reconcile.)
  - (c) fails → best-effort remove the just-minted relay dir, then as (b).
  - (d) fails → persist terminal `state=failed` FIRST, then best-effort ❌ +
    thread notice; relay-dir removal follows the reconciliation executor's
    phase rule (only after terminal persistence succeeded).
  "Best-effort" platform calls here catch `ChatError` subclasses, audit,
  and continue — a cleanup failure never crashes the daemon and never
  changes what was persisted.

  **Denial delivery is fail-quiet (pinned):** the ephemeral-denial branch
  wraps `send_ephemeral` and catches `DeliveryFailed` (and other
  `ChatError`s): audit the failed delivery and drop it. Denial details are
  NEVER posted publicly — `send_ephemeral`'s own contract already forbids a
  public fallback (`adapter.py:131-141`); the daemon must not reintroduce
  one, and must not crash on the raise.
- `chatlink/sessions_store.py` — session records as JSON files
  (`chatlink_sessions/sessions/<session_id>.json`, atomic `.tmp`+rename
  writes; dir via `paths.ensure_secure_dir`): initiator id, thread
  ConversationRef dict (`to_dict()` — the reconnect token), bug-report
  MessageRef dict, last-seen message ref per conversation (the
  `fetch_history(after=)` cursor), state
  (`spawning|asking|working|awaiting_payload|done|failed`), interaction
  outcomes (persisted on receipt), timestamps.
- `chatlink/reconcile.py` — **pure** planners (no I/O; daemon executes the
  returned actions):
  `plan_reconnect_actions(persisted_sessions, fetched_events) -> [Action]`
  (missed-message recovery via history diff; missed interaction window ⇒
  re-prompt action — never assume replay) and
  `plan_startup_actions(persisted_sessions, live_session_ids, relay_scan)
  -> [Action]` (no live agent ⇒ mark failed; pending questions ⇒ write
  `cancelled` answers; **session-record outcome entries healed FROM the
  spool** — an answer file with no matching record outcome ⇒ record-update
  action, spool is source of truth; half-created record ⇒ fail-closed
  `failed`, never resume; stale relay dir removal AFTER terminal state
  persisted; best-effort Discord cleanup actions — disable components, ❌
  reaction).

  **Executor phase discipline (pinned — planner tests alone don't cover
  this).** Each `Action` carries a phase tag; the daemon-side executor
  applies a session's actions strictly by phase:
  1. **Terminal persistence** (must-succeed): session-record state write +
     `cancelled` answer writes (`write_answer(..., overwrite=False)`). If
     any phase-1 write for a session fails: audit, SKIP phases 2–3 for that
     session entirely (its relay dir and record are left for the next
     startup pass) — never proceed to cleanup on unpersisted state.
  2. **Platform cleanup** (best-effort): `edit_message` component disabling,
     ❌ reactions, re-prompt posts. `ChatError`s audited and swallowed;
     never affects phase 3.
  3. **Relay-dir removal**: only for sessions whose phase 1 fully succeeded.
  Idempotency: every phase-1 write is a no-op-safe re-write (record state
  already terminal ⇒ skip; answer file exists ⇒ `write_answer` returns
  False, fine), so a crash mid-executor re-runs cleanly at next startup.
- `chatlink/spawn_seam.py` — the injectable launcher protocol **stub**
  (contract 8 signature only): `launch(spec) -> handle{wait,kill,alive}`,
  `reap_orphans(workspace_id)`; plus `FakeLauncher` for tests. t1120_5
  promotes this into `lib/sandbox_launch.py` (its plan already references
  this stub by name — keep the name).
- `chatlink/audit.py` — applink `audit.py` pattern verbatim: lazy idempotent
  `get_logger(sessions_dir)` → `chatlink_sessions/chatlink_audit.log`,
  NullHandler fallback (logging failure never takes the daemon down), ids
  truncated (`bearer_tag`-style helper for session/user ids).
- `aitask_chatlink.sh` + `ait` dispatcher entry (`ait chatlink --headless`):
  case line `chatlink) shift; exec "$SCRIPTS_DIR/aitask_chatlink.sh" "$@" ;;`
  + help text line in `ait`. Dependency preflight mirrors
  `aitask_monitor.sh:14-42`: check `yaml` + `discord` imports, `die` with the
  chat-tier `ait setup` hint. v1 is headless-only: `--headless` required
  (without it, print a hint that the TUI arrives in t1120_6) — keeps the
  launcher surface stable for t1120_6's TUI registration.

## Consumed sibling APIs (verified against source this pass)

- `relay.SessionDir`: `pending_questions()` (stateless pending set) for
  reconciliation; `write_answer(a, overwrite=False)` create-no-replace
  (`os.link`) for cancelled answers — first publisher wins, returns False if
  an answer exists; `read_status`/`write_status` (gateway-owned, opaque to
  relay); `read_payload`.
- `render`: `render_question(q, capabilities) -> RenderedQuestion`
  (`text_chunks`, `rows`, `page`, `page_count`); `build_modal(q)`;
  `is_page_nav(q, interaction)` / `is_free_text_trigger(q, interaction)` —
  the interaction-routing helpers; `assemble_answer(q, interaction)` raises
  `AnswerMismatch` for stale/foreign ⇒ map to ephemeral "question expired".

  **Exact minimal interaction path owned by THIS task (pinned scope
  boundary with t1120_6):**
  - **Implemented here, end-to-end through the real event path:**
    (1) `post_question(session, q)` — render a pending `Question` and
    `send_message` it to the session thread with components (used by tests
    and by reconciliation re-prompt actions; no continuous spool polling).
    (2) INTERACTION_RECEIVED handling for **select submissions**: route by
    `parse_custom_id` → known session? (unknown ⇒ audit + ignore) →
    `policy.may_answer(initiator, actor)` (deny ⇒ ephemeral, question stays
    pending) → `assemble_answer` (pure, in-memory) →
    `write_answer(overwrite=False)` — **the durable-outcome write, and the
    handler's FIRST awaited side effect for the interaction** → returned
    True: update the session-record outcome entry, then best-effort
    component disabling; returned False: the answer file already exists ⇒
    stale/repeated interaction ⇒ ephemeral "question expired" + audit (no
    separate check-then-act — staleness is decided by the atomic
    create-no-replace itself, race-free). `AnswerMismatch` ⇒ same ephemeral
    "question expired" path.
  - **Deferred to t1120_6 (`flow.py`):** the continuous spool→Discord pump
    loop, the free-text modal dance (`open_modal` + MODAL_SUBMIT), select
    pagination nav, reaction choreography (⏳/❓/✅), and payload
    completion handling. Free-text-trigger and page-nav interactions ARE
    recognized here (via the routing helpers) but answered with an
    ephemeral "not available yet" + audit — never silently dropped, never
    crashing. Nothing is live before t1120_5/6 land, so the stub reply is
    honest.
  - **Test consequence:** interaction-persistence tests MUST drive the real
    path — `inject_interaction` through the running subscribe loop into the
    daemon's handler — not hand-persisted outcomes. At least one test posts
    a question via `post_question`, injects the select submission, and
    asserts spool answer + record outcome + disable call, in that order.
- `policy`: `decide()` / `may_answer()` are the ONLY authorization call
  sites; branch on `REASON_*` constants, never string literals.
- `config`: ceilings arrive clamped — enforce, don't re-validate.
- `chat`: `subscribe()` contract at `adapter.py:421-453` (at-least-once while
  connected, NO replay across disconnect, INTERACTION_RECEIVED non-replayable
  ⇒ persist outcomes on receipt); `fetch_history(after=MessageRef)`
  chronological; mock seams at `mock.py:679-757` (`inject_message`,
  `inject_interaction`, `simulate_disconnect`, `set_identity_claims`,
  `inject_reaction`); Capabilities `supports_buttons/selects/modals` default
  True on all shipped adapters.

## Key async invariants (binding — concurrency safety contract)

- **Sequential event dispatch (the execution shape, pinned):** the daemon
  consumes `subscribe()` strictly sequentially — each event's handler is
  `await`ed to completion (including all session-record and spool
  persistence) before the next event is dequeued. Handlers are NOT spawned
  as concurrent tasks. This is what makes "loop-only mutation" sufficient:
  the rate/concurrency check-then-write and interaction-outcome persistence
  are serialized by construction — two intake messages from the same user
  cannot interleave their ceiling checks, and no per-user/per-session locks
  are needed. v1 volumes make head-of-line blocking a non-issue (bug-intake
  channel, ≤ `max_concurrent_sandboxes` live sessions). No other task
  mutates session records in this child: the spawn seam is stubbed (no live
  death-monitor task — that arrives with t1120_5/6 and must marshal
  mutations through the loop), and startup/reconnect reconciliation runs
  before the subscribe loop (re)starts, never concurrently with it.
- Loop-only mutation: session records mutated solely from the daemon's single
  event loop; relay spool I/O via `asyncio.to_thread` (the `await` of the
  to_thread call still completes inside the handler — sequentiality holds).
- **The durable interaction outcome IS the relay answer file** (contract 4/6:
  spool state is the restart-derivable truth; the session-record outcome
  entry is derived bookkeeping). The invariant, precisely: on
  INTERACTION_RECEIVED, the atomic `write_answer(overwrite=False)` (via
  `asyncio.to_thread` — it is itself an awaited operation) is the handler's
  FIRST awaited side effect for that interaction; no other await on the same
  session (record update, `edit_message`, ephemeral) may precede it. Crash
  before the write ⇒ spool still shows the question pending ⇒ startup
  reconciliation re-prompts (nothing lost); crash after ⇒ the answer is
  durable and `plan_startup_actions` heals the session-record outcome FROM
  the spool (spool is source of truth for record outcomes). Stale/repeated
  interactions are detected by the write itself returning False — never by
  a separate exists-check.
- Fail-closed everywhere: unknown custom_id ⇒ audit + ignore; half-created
  session at startup ⇒ failed, never resumed.
- Bounded: intake honors `max_concurrent_sandboxes` + per-user rate ceiling
  (drop with audit + optional ephemeral notice when exceeded).
- Deterministic test seam: injected clock/launcher; `MockChatAdapter` logical
  clock.

## Implementation order

1. `sessions_store.py` (+ tests) — pure persistence.
2. `reconcile.py` (+ tests) — pure planners, table-driven cases.
3. `intake.py` + `spawn_seam.py` (+ tests vs MockChatAdapter, FakeLauncher).
4. `audit.py`, `daemon.py` wiring (+ no-Textual import guard test).
5. `aitask_chatlink.sh` + dispatcher entry (+ launcher argv test).

Read `aidocs/framework/shell_conventions.md` +
`aidocs/framework/aitasks_extension_points.md` before step 5 (new helper
script + dispatcher wiring; shellcheck both).

## Testing

Bash test script(s) per the task file's Verification list, all against
`MockChatAdapter` seams — no live-platform calls:
- Intake happy path (authorized message → thread + session); unauthorized ⇒
  deny path + audit (negative control, per-reason); self/bot echo dropped.
- Interaction outcome ordering (spy adapter + spy store recording call
  order): `write_answer` is the first awaited side effect, then record
  update, then component disabling — driven through the REAL path:
  `post_question` → `inject_interaction` → subscribe-loop handler (no
  hand-persisted outcomes). Repeat-interaction control: second injection of
  the same submission ⇒ `write_answer` returns False ⇒ ephemeral "question
  expired", record untouched. Spool-heal control: answer file present +
  record outcome absent ⇒ startup actions include the record update.
- Sequential-dispatch race negative control: two same-user intake messages
  injected back-to-back at the rate/concurrency boundary ⇒ exactly one
  session created, second denied with audit (proves the serialized
  check-then-write).
- Deferred-interaction stubs: free-text trigger and page-nav interactions ⇒
  ephemeral "not available yet" + audit, question stays pending, no crash.
- `simulate_disconnect` negative controls: missed message recovered via
  history diff; missed interaction ⇒ re-prompt, no replay assumed.
- Startup reconciliation: half-created session ⇒ failed (fail-closed);
  pending question ⇒ cancelled answer written (`overwrite=False` semantics
  respected); stale relay dir removed only after terminal state persisted.
- **Executor-level tests (not just planner tables):** spy adapter/store
  recording call order proves phase 1 (terminal persistence) precedes
  phases 2–3; failure injection — phase-1 store write raises ⇒ relay dir
  NOT removed, platform cleanup skipped, audit entry present; re-running
  the executor after a simulated mid-run crash is a clean no-op.
- Intake failure-point tests (one per step): thread-creation failure ⇒
  nothing persisted; record-persist failure ⇒ relay dir removed
  best-effort; launch failure ⇒ terminal `failed` persisted BEFORE any
  platform cleanup (spy order).
- Denial-delivery failure: `send_ephemeral` raising `DeliveryFailed` ⇒
  daemon continues, audit entry, nothing posted publicly (assert no
  `send_message` call on the deny path).
- Rate-limit ceiling enforced (t985-style bound test) + concurrent-sandbox
  bound; rate limit survives a simulated restart (derived from records).
- No-Textual import contract test mirroring `tests/test_applink_headless.sh`
  Group A (`import chatlink.daemon` ⇒ `"textual" not in sys.modules`).
- Existing `tests/test_chatlink_relay.sh` + `test_chatlink_config.sh` still
  pass (import posture unaffected).
- shellcheck on `aitask_chatlink.sh` + edited `ait`.

## Verification notes (2026-07-05, pre-implementation verify pass)

- Contract 0 **FROZEN as of t1120_1**; consumed contracts 1–6, 9–11 match the
  parent plan §PINNED (incl. the t1120_1 amendments: option `value` identity,
  durable timeout answers).
- t1120_2 landed: `paths.py` (`config_file()` absolute, `read_token`,
  `relay_root`, `ensure_secure_dir`), `config.py` (`load_config` fail-closed
  `None`, clamped ceilings, normalized `intake_channel`), `policy.py`
  (9-reason enum, `may_answer`) — all verified in source; the daemon consumes
  them exactly as its archived plan's sibling notes prescribe.
- t1120_1 landed: `relay.py` `SessionDir` (incl. `write_answer(...,
  overwrite=False)` atomic create-no-replace via `os.link`,
  `pending_questions()`), `render.py` (`RenderedQuestion`, `is_page_nav`,
  `is_free_text_trigger`, `AnswerMismatch`), `aitask_relay_ask.sh`
  (PYTHONPATH=.aitask-scripts pattern for the launcher).
- Anchor drift (content unchanged): applink `headless.py` skeleton cited as
  :75-186 → `serve()` now :81-225 (t1061_1 added advertise flags + firewall
  doctor — neither applies to chatlink); `adapter.py` reconnect semantics
  cited :434-449 → :438-448. Mock seams :679-757 exact.
- `aitask_monitor.sh:14-42` preflight interception pattern confirmed exact;
  chat tier imports are `discord`/`slack_bolt`/`slack_sdk`
  (`aitask_setup.sh:38-39`) — daemon preflight checks `yaml` + `discord`.
- `ait` dispatcher: flat case list at `ait:188-228`; `chatlink` slot is a
  one-line addition + help text (~line 29).
- `create_conversation(kind=THREAD, parent=MessageRef)` contract confirmed
  (`adapter.py:148-169`); MESSAGE_CREATED payload `{"message": Message}`,
  INTERACTION_RECEIVED payload `{"interaction": Interaction}` (mock emits
  confirmed); `Actor.is_self` field + `is_bot` property (`model.py:236-258`).
- t1120_5's pending plan references `chatlink/spawn_seam.py` by name as the
  stub it promotes — seam ownership consistent; t1120_6 owns full `flow.py`
  pumping, minimal here.
- `aitasks/metadata/chatlink_config.yaml` present in this repo (seeded by
  t1120_2) — live smoke of config loading possible without setup runs.
- **Plan-review findings addressed (this pass):** (1) pinned sequential
  event dispatch as the execution shape (loop-only mutation alone doesn't
  serialize handlers); (2) pinned the exact minimal interaction path
  (select submissions end-to-end + `post_question`; modal/pagination/pump
  deferred to t1120_6 with honest ephemeral stubs) + real-entry-point test
  requirement; (3) pinned the reconciliation executor's 3-phase discipline
  (terminal persistence → platform cleanup → dir removal) + executor-level
  failure-injection tests; (4) pinned intake step order (record persisted
  before launch) + per-step failure behavior; (5) pinned fail-quiet denial
  delivery (`DeliveryFailed` audited + swallowed, never public —
  `send_ephemeral` contract at `adapter.py:131-141`); (6) resolved the
  outcome-persistence ambiguity — the relay answer file IS the durable
  interaction outcome (first awaited side effect; record entry derived,
  healed from spool at startup; staleness = `write_answer` returning
  False, race-free).

## Risk

### Code-health risk: medium
- New always-on asyncio daemon (subscribe loop + to_thread spool I/O +
  signal handling) — race hazards around interaction-outcome persistence
  ordering and reconnect reconciliation · severity: medium · → mitigation:
  embedded (pinned sequential event dispatch — handlers awaited to
  completion, no concurrent handler tasks; executor phase discipline with
  failure-injection tests; pure `reconcile.py` planners; ordering-assertion
  + disconnect negative-control tests + same-user race negative control)
- Shared-surface edits are minimal and append-style (`ait` dispatcher case
  line + help text; new helper script) — everything else is additive
  greenfield in `chatlink/` · severity: low · → mitigation: embedded
  (shellcheck; existing chatlink test suites re-run to guard import posture)

### Goal-achievement risk: low
- Central relay assumption already validated (t1120_1 spike PASS; contracts
  frozen; every consumed API verified in source this pass) · severity: low ·
  → mitigation: embedded (verification notes above)
- Scope boundary with t1120_6 (minimal Q&A pumping vs full flow
  orchestration) could creep or under-deliver the reconciliation tests ·
  severity: low · → mitigation: embedded (plan pins "enough to test
  persistence + reconciliation"; t1120_6's plan owns `flow.py`)

## Step 9 reference

Post-implementation follows task-workflow Step 9.
