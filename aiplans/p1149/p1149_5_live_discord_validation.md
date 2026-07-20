---
Task: t1149_5_live_discord_validation.md
Parent Task: aitasks/t1149_chatlink_config_wizard_tui.md
Sibling Tasks: aitasks/t1149/t1149_4_wizard_docs_rewrite.md
Archived Sibling Plans: aiplans/archived/p1149/p1149_1_preflight_module.md, aiplans/archived/p1149/p1149_2_config_status_panel.md, aiplans/archived/p1149/p1149_3_config_wizard_flow.md
Worktree: (current branch — fast profile, no worktree)
Branch: current
Base branch: main
plan_verified:
  - claudecode/fable5 @ 2026-07-20 11:54
---

# p1149_5 — Live Discord validation step (optional)

Optional wizard step (between Token and Summary): connect live with the
entered token and affirmatively verify token validity, privileged intents
(Message Content / Server Members), intake-channel visibility, and bot
permissions — catching at config time what the troubleshooting table today
only diagnoses after the fact. Advisory-only: the wizard outcome never
depends on it; skipping is always possible.

**Plan verified against source this session (post-t1149_3 refresh):**

- `DiscordAdapter.connect(token, *, guild_id=None, defer_delay=…)` —
  `chat/discord_adapter.py:631-712`. Does its **own** `import discord`
  (`:646`, NOT via the `_sdk()` seam `:623` — that seam serves the
  constructed adapter). Requests both privileged intents (`:648-650`),
  `await client.login(token)` (`:708`, bad token → `discord.LoginFailure`),
  spawns `client.connect(reconnect=True)` as an untracked background task
  (`:709`), `wait_until_ready()` (`:710`). **No `close()` exists**; a
  failure after `login` (or a caller-side timeout cancellation) leaks the
  HTTP session + Gateway task. With privileged intents disabled in the
  portal, the gateway task raises `PrivilegedIntentsRequired` but
  `wait_until_ready()` **hangs forever** — connect() never surfaces it
  (matches the docs symptom "the bot sits in the channel and nothing
  happens").
- `_resolve_channel(ref)` `:774-792` — THE existence probe, raises mapped
  `ConversationNotFound` / `PermissionDenied` via `map_discord_error`
  (`:545-573`, SDK-import-free class-name matching — pattern to copy).
  It resolves via `_ref_key(ref)` = `thread_id or conversation_id`
  (`chat/_subscription.py:31-33`) — with a configured intake thread it
  resolves the THREAD object, whose `permissions_for` does not prove
  parent-channel capabilities (Create/Manage Threads live on the parent).
- `fetch_identity_claims` `:1094-1117` exposes only `view_channel` — NOT
  enough for the bot-permission check; a new adapter primitive is needed.
- Wizard (t1149_3, shipped): `chatlink/wizard.py` — `_STEPS` tuple `:609`
  (insertion point), `WizardSeams` `:67-77` + `resolve_seams` `:80`,
  `_WizardStep` base `:144` (`step_title`, `next_label`, `body()`,
  `_accept()`, `_error()`, Back/Next/Cancel + escape), `TokenScreen` `:342`
  (`state["token"]` = entered value or `None` when kept), `SummaryScreen`
  worker idiom `:529-564` (pure thread body → `call_from_thread`,
  `_probing` debounce), `start_wizard` `:577` (`make_step` passes seams to
  Token/Summary). Step titles are hardcoded `Step N/6` class attrs; **no
  test asserts them** (safe to renumber to `/7`).
- `chatlink/chatlink_app.py:109-128,166-172` — constructor seams
  (`cheap_runner`, `expensive_runner`, `wizard_config_path`,
  `token_reader`, `token_writer`) threaded into `WizardSeams` by
  `action_wizard`; new seams follow the same shape.
- `chatlink/preflight.py:69-81` — `CheckResult(id, category, severity,
  message, fix_hint="", daemon_refuse_message=None)`; severities
  `PASS/WARN/FAIL` `:51-53`; categories incl. `TRANSPORT` `:56`.
  `preflight_render.format_row` `:19` renders rows.
- Lazy cross-tier import precedent: `chatlink/daemon.py:730`
  `from chat.discord_adapter import DiscordAdapter  # lazy`.
- `ConversationRef(provider, workspace_id, conversation_id,
  thread_id=None)` — `chat/model.py:83-106`.
- Permission authority: `aidocs/chat/discord_bot_setup.md:50-61` — invite
  `permissions=397552863296`; named minimum set: View Channels, Send
  Messages, Send Messages in Threads, Create Public Threads, Create
  Private Threads, Manage Threads, Read Message History, Attach Files,
  Embed Links, Add Reactions, plus Manage Messages ("drop if not needed").
- Tests: `tests/test_chat_discord.sh` FakeClient/FakeSDK idiom (`:275-378`);
  `tests/test_chatlink_wizard.sh` headless suite + import guard;
  `tests/test_chatlink_tui.sh` Pilot wizard walk `:215-452` (navigates by
  button presses — must traverse the new step).

## Pinned contracts (parent plan)

1. **Fail-closed + guaranteed teardown**: every failure renders as a
   specific check row with a fix hint; no exception escapes to the TUI;
   the connection is torn down on ALL paths (success, failure, timeout) —
   fake-seam tests assert close is always called.
2. **Optional**: offered after token entry ("Validate live now" /
   Continue-to-skip); skip always available; wizard outcome independent.
3. **Timeout-bounded**: overall wall-clock cap (30s) with progress state;
   never hangs the wizard.
4. **Owns its docs delta**: live-validation coverage noted in
   `website/content/docs/workflows/bug-report-intake.md` troubleshooting +
   `aidocs/chat/discord_bot_setup.md` (t1149_4 excluded these by design).
5. **Token hygiene**: never logged, never rendered, never embedded in any
   `CheckResult` field; travels only to Discord. Row messages are composed
   from **fixed templates + exception class name only** — never
   `str(exc)`/`repr(exc)`, which can embed the token (HTTP layers, fakes,
   SDK reprs). The hygiene test injects an exception whose message
   contains the token and asserts it appears in no result field.

## Design decisions (this session)

- **`DiscordAdapter.close()`** — public teardown: duck-typed
  `close = getattr(self._client, "close", None)`; call and await if
  awaitable. Safe on never-connected instances and non-async fakes. No SDK
  import needed.
- **`connect()` hardening (needed for contract 1)**: wrap the body after
  `client = discord.Client(...)` in `try/except BaseException → bounded
  cleanup; raise`. The cleanup close is **bounded and suppressed** —
  `with suppress(Exception, asyncio.CancelledError, asyncio.TimeoutError):
  await asyncio.wait_for(client.close(), CONNECT_CLEANUP_TIMEOUT_S)` (5s)
  — never a bare `await client.close()`: when `run_live_checks` wraps
  `connect()` in `wait_for` and the deadline fires mid-login/readiness,
  `wait_for` waits for the coroutine's cleanup, so an unbounded (or
  re-cancelled) `close()` would hang the wizard past the advertised cap.
  The original exception is always re-raised after cleanup. Also race
  readiness against the gateway task:
  `asyncio.wait({gateway_task, ready_task}, return_when=FIRST_COMPLETED)`
  — if the gateway task finishes first (e.g. `PrivilegedIntentsRequired`),
  **consume its exception** (`gateway_task.exception()`), **cancel and
  await the losing `ready_task`** (suppress `CancelledError`), then raise
  — no pending-task warnings or late exceptions. If the gateway task
  completed **without** an exception (early clean disconnect/close before
  readiness — `exception()` is `None`), raise a deterministic fallback
  `RuntimeError("Discord gateway closed before becoming ready")` instead
  of raising `None` / falling into a generic unexpected-error row
  (live_check maps it like any connect-stage failure, keeping the row
  diagnostic). On the success path the
  gateway task keeps running (it IS the connection) and is stored as
  `adapter._gateway_task`; `close()` consumes it (below).
  Success-path semantics otherwise unchanged (login → spawn connect →
  ready → self_id → return). This also fixes the daemon's silent hang on
  disabled intents (bonus, behavior-improving only on the failure path).
- **`DiscordAdapter.close()` consumes the gateway task**: after the
  duck-typed client close, if `self._gateway_task` is set, bounded-await
  it (`wait_for` + suppress) so its exception/pending state is always
  consumed — strict async tests assert no pending tasks after close on
  both success and failure paths.
- **New adapter primitive `fetch_bot_permissions(conversation, names)`**
  (DiscordAdapter-only, like `connect` — not on the `ChatAdapter` ABC):
  resolve the channel, `guild = channel.guild`; DM (`guild is None`) →
  `{}` (n/a); else **resolve the bot member explicitly** — do NOT rely on
  `guild.me` (missing/stale in fakes, partial cache states, gateway edge
  cases): mirror the `fetch_identity_claims` fallback (`:1104-1112`) with
  the bot's own id (`self._self_id` / `client.user.id`): `guild.get_member(uid)`,
  else `await guild.fetch_member(uid)`, errors routed through
  `map_discord_error(exc, target="user")` so a self-member resolution
  failure surfaces distinctly instead of as a vague permission failure.
  Then `perms = channel.permissions_for(member)` and return
  `{name: bool(getattr(perms, name, False)) for name in names}`.
  Primitives-not-policy: the required-names list lives in the chatlink
  layer, the adapter just reports.
- **`chatlink/live_check.py` (Textual-free, discord-import-free at module
  level)**: `run_live_checks(token, workspace_id, conversation_id,
  thread_id=None, *, timeout=LIVE_CHECK_TIMEOUT_S, connector=None) ->
  list[preflight.CheckResult]` — a **sync** function (thread-worker
  friendly) that runs `asyncio.run(_run_async(...))` on a fresh loop.
  `connector=None` resolves lazily to `DiscordAdapter.connect` (import
  inside the function, daemon.py:730 pattern); tests inject an async fake
  connector returning a fake adapter — no `discord` import ever.
  - **Deadline-based per-stage `wait_for`** (not one outer `wait_for`): a
    monotonic deadline; each awaited stage gets the remaining budget. The
    body coroutine is never cancelled from outside, so the
    `try/finally: await adapter.close()` teardown always runs (close
    itself bounded by a short `wait_for` + suppress).
  - **Four rows** reusing `preflight.CheckResult`, category `TRANSPORT`,
    ids `live_login`, `live_intents`, `live_channel_visible`,
    `live_permissions`. Stages: connect (LoginFailure-shaped → `live_login`
    fail "token rejected", fix hint: reset token in the portal / re-enter;
    PrivilegedIntentsRequired-shaped → `live_login` pass + `live_intents`
    fail, fix hint: enable both privileged intents on the Bot page;
    connected → both pass); channel: `_resolve_channel(ConversationRef(
    provider="discord", …))` via a thin adapter call (`fetch_conversation`
    resolves too, but `_resolve_channel` errors are what we map) —
    `ConversationNotFound`/`PermissionDenied` → `live_channel_visible`
    fail, fix hint: invite the bot / check channel access; permissions:
    `fetch_bot_permissions(parent_ref, REQUIRED + OPTIONAL)` — any
    REQUIRED missing → fail listing the missing names; only
    `manage_messages` missing → warn ("optional — drop if not needed");
    DM `{}` → pass with "n/a (DM channel)".
  - **Thread scoping**: `live_channel_visible` validates the configured
    target ref as-is (thread when `thread_id` is set — proves the intake
    target is reachable; message notes "(thread)"), but
    `live_permissions` ALWAYS evaluates the **parent channel**
    (`thread_id=None` ref): `_ref_key` resolves thread-over-channel, and
    Create Public/Private Threads + Manage Threads are parent-channel
    capabilities — seeing an existing thread does not prove the bot can
    create/manage intake threads.
  - Exception matching is **class-name based** (copy the
    `map_discord_error` idiom) so live_check never imports the SDK.
  - Stage timeout → that row fails with "timed out after Ns"; stages not
    reached (earlier failure/timeout) → `WARN` "not checked — <reason>".
  - Any unexpected exception → converted to a fail row on the current
    stage with a **sanitized fixed-template message carrying only the
    exception class name** — never `str(exc)`/`repr(exc)` (pinned
    contract 5: exception text can embed the token); the function never
    raises (contract 1).
  - `REQUIRED_BOT_PERMISSIONS` / `OPTIONAL_BOT_PERMISSIONS` constants
    with a comment pinning them to `aidocs/chat/discord_bot_setup.md`
    step 5 (canonical list — update together).
- **`LiveCheckScreen`** inserted in `_STEPS` between `TokenScreen` and
  `SummaryScreen`; all step titles renumbered to `/7` (new screen is
  "Step 6/7 — Live validation (optional)"). Screen body: explanation
  label, a "Validate live now" Button (`#btn_wiz_live_run`), a results
  `Static` (`markup=False`); `next_label = "Continue"` — `_accept()`
  always dismisses `NEXT` (results are advisory; Continue == skip when
  never run). Token resolved as `state["token"] or seams.token_reader()`;
  no token → inline error on Validate (Continue still works). Provider
  ≠ `discord` → Validate disabled with an inline note (live validation is
  Discord-only). Worker: same pure-body / `call_from_thread` /
  debounce-flag idiom as `SummaryScreen._run_probes`, plus a
  **generation token + `self.is_attached` guard** in the apply callback
  (the user may Continue past the screen mid-run — a late result must not
  touch a dismissed screen). Progress line "… validating live (up to
  30s)" while running. Rows rendered via `preflight_render.format_row`.
- **Seam threading**: `WizardSeams` gains `live_runner: Callable | None`
  (resolved to `live_check.run_live_checks`); `ChatlinkApp.__init__`
  gains `live_runner=None` and `action_wizard` threads it (parallel to
  the five existing seams).
- **Docs delta scope** (t1149_4 is still pending; it will preserve this):
  a short paragraph after the `## Troubleshooting` heading in
  `bug-report-intake.md` noting the wizard's optional live-validation
  step catches the token / intents / channel-visibility / permission rows
  at config time; a one-line note in `discord_bot_setup.md` (after the
  invite-URL step) that `ait chatlink`'s wizard can verify intents and
  permissions live.

## Implementation steps

1. **`chat/discord_adapter.py`**:
   - `close()` (after `_sdk`, ~`:630`): duck-typed client-close, awaits if
     awaitable; then bounded-await `self._gateway_task` (suppress) to
     consume it; docstring: safe on never-connected/fake clients.
   - `fetch_bot_permissions(conversation, names) -> dict[str, bool]`
     (near `fetch_identity_claims`): as designed above (explicit bot-member
     resolution with `get_member`/`fetch_member` fallback — never bare
     `guild.me`); channel errors via `map_discord_error(target=
     "conversation")`, member errors via `target="user"`.
   - `connect()` hardening: post-construction `try/except BaseException`
     → **bounded, suppressed** `client.close()` (`CONNECT_CLEANUP_TIMEOUT_S`),
     re-raise; readiness raced against the gateway task, losing
     `ready_task` cancelled+awaited and gateway exception consumed;
     success stores `adapter._gateway_task`.
2. **`chatlink/live_check.py`** (NEW): as designed above.
   `LIVE_CHECK_TIMEOUT_S = 30.0`, `CLOSE_TIMEOUT_S = 5.0`.
3. **`chatlink/wizard.py`**: `LiveCheckScreen`; insert into `_STEPS`;
   renumber titles; `WizardSeams.live_runner` + `resolve_seams`;
   `make_step` passes seams to `LiveCheckScreen` too.
4. **`chatlink/chatlink_app.py`**: `live_runner=None` constructor param →
   `action_wizard` seam threading.
5. **Docs**: `website/content/docs/workflows/bug-report-intake.md`
   (troubleshooting paragraph), `aidocs/chat/discord_bot_setup.md` (note).
6. **Tests**:
   - `tests/test_chat_discord.sh`: `close()` on a FakeClient (async and
     missing-close fakes); `connect()` teardown — inject a fake `discord`
     module into `sys.modules` (Intents/Client stubs): login-failure →
     client.close awaited + raises; gateway-task failure pre-ready →
     raises that exception + closes (no hang); gateway task returning
     CLEANLY pre-ready → raises the deterministic "gateway closed before
     becoming ready" fallback (never `raise None`); **a hanging fake
     `client.close()` does not stall the cleanup past the bound**;
     **no pending/unawaited tasks after both the failure paths and a
     success→close() sequence** (race-loser cancelled, gateway task
     consumed); success path returns a ready adapter (unchanged
     semantics); `fetch_bot_permissions` member-resolution fallback
     (get_member miss → fetch_member; both fail → distinct mapped error,
     not a vague permission result).
   - `tests/test_chatlink_wizard.sh` (headless): import guard —
     `import chatlink.live_check` pulls in neither `textual` nor
     `discord`; per-failure-mode rows via fake connectors (login fail /
     intents fail / channel not found / permission gaps / all-pass);
     close-spy called on success, failure, and timeout paths (slow fake +
     tiny timeout); not-reached rows are WARN; **thread-scoping: with
     `thread_id` set, the permissions call receives the parent-channel
     ref (spy on the fake adapter) while visibility checks the thread
     ref**; token-hygiene — including an injected exception whose
     message CONTAINS the token → token appears in no CheckResult field.
   - `tests/test_chatlink_tui.sh` (Pilot): extend the wizard walk through
     the new step (Continue-to-skip path — live seam spy asserts **zero**
     calls when skipped); a second pass presses "Validate live now" with
     an injected fake `live_runner` → rows render, Continue proceeds, and
     the saved YAML is unaffected by a failing validation (advisory-only
     proof); mid-run Continue does not crash (guard test).
7. Run `bash tests/test_chat_discord.sh`, `bash tests/test_chatlink_wizard.sh`,
   `bash tests/test_chatlink_tui.sh`, `bash tests/test_chatlink_preflight.sh`,
   `bash tests/test_chatlink_daemon.sh` (connect() is on the daemon's lazy
   path — prove no regression).

## Risk

### Code-health risk: medium
- `connect()` hardening touches the only real-Gateway entry point (also
  used by the daemon); a mistake could break live connection behavior,
  hang cleanup past the deadline, or leak pending tasks · severity:
  medium · → mitigation: in-plan — success-path ordering kept
  byte-equivalent; cleanup close bounded + suppressed; race loser
  cancelled/awaited and gateway task consumed; covered by new
  fake-`discord`-module tests (incl. hanging-close and no-pending-task
  assertions); full daemon suite re-run.
- Late worker result touching a dismissed LiveCheckScreen (user continued
  mid-run) · severity: low · → mitigation: in-plan — generation token +
  `is_attached` guard in the apply callback, Pilot guard test.
- Step renumbering / `_STEPS` insertion could desync the Pilot walk ·
  severity: low · → mitigation: in-plan — walk updated in the same
  commit; no test pins the old titles (verified).

### Goal-achievement risk: medium
- Real-Discord failure surfacing (PrivilegedIntentsRequired timing,
  permission attribute names) is only partially verifiable with fakes ·
  severity: medium · → mitigation: manual verification with a real bot
  token (queued via the Step 8c manual-verification follow-up: valid
  token all-pass; revoked token → login row; intent off → intent row;
  bot removed → visibility row; UI never hangs; skip works).
- Intent-failure granularity: Discord reports one error for either
  privileged intent, so the row cannot name which one is off · severity:
  low · → mitigation: fix hint names both intents explicitly.

### Planned mitigations
None as separate risk-mitigation tasks — the live-token manual check is
deliberately routed through the standard Step 8c manual-verification
follow-up (single-task path) instead, to avoid double-created follow-ups;
all other risks are mitigated in-plan by the pinned contracts and tests.

## Verification

- `bash tests/test_chatlink_wizard.sh` — live_check rows per failure mode; teardown spy on success/failure/timeout; import guard (no textual, no discord); token-hygiene assertion.
- `bash tests/test_chat_discord.sh` — `close()` fakes; `connect()` teardown + gateway-failure surfacing via fake `discord` module.
- `bash tests/test_chatlink_tui.sh` — wizard walk with the live step skipped (zero live-seam calls) and with injected results; advisory-only save; mid-run Continue guard.
- `bash tests/test_chatlink_daemon.sh` + `bash tests/test_chatlink_preflight.sh` — no daemon-path regression.
- Manual (real bot token, via the queued manual-verification follow-up): valid token all-pass; revoked token → token row fails; portal intent off → intent row fails; bot removed from channel → visibility row fails; UI never hangs; skip works.

Refer to Step 9 (Post-Implementation) of the task workflow for merge/archival.

## Post-Review Changes

### Change Request 1 (2026-07-20 09:35)
- **Requested by user:** (1) connect()'s failure path awaited the
  cancelled gateway/ready tasks unbounded — a cancellation-resistant
  gateway task could stall a cancelling caller past the wizard deadline;
  bound those awaits too. (2) Keep the unrelated
  `.claude/settings.local.json` diff out of the task commit. (3)
  `fetch_bot_permissions` called `channel.permissions_for` without the
  duck-typed callability guard used elsewhere — map its absence
  deliberately.
- **Changes made:** (1) Every cleanup await in connect()'s except path is
  now `wait_for(..., CONNECT_CLEANUP_TIMEOUT_S)` + suppress (over-bound
  tasks are abandoned with their outcome consumed); new
  cancellation-resistant-gateway test asserts the caller-side deadline
  holds and the client still closes. (2) The commit stages only this
  task's files explicitly. (3) Absent/non-callable `permissions_for` now
  raises a deliberate `ChatError` ("cannot inspect bot permissions");
  new test pins it.
- **Files affected:** `.aitask-scripts/chat/discord_adapter.py`,
  `tests/test_chat_discord.sh`

## Final Implementation Notes

- **Actual work done:** Implemented as planned (with the plan's two
  review-driven amendment rounds folded in before implementation).
  `chat/discord_adapter.py`: `CONNECT_CLEANUP_TIMEOUT_S = 5.0`; public
  `close()` (duck-typed client close + bounded gateway-task consumption,
  safe on never-connected/fake clients); hardened `connect()` (readiness
  raced against the gateway task — `PrivilegedIntentsRequired` and clean
  early exits surface instead of hanging in `wait_until_ready()`, with a
  deterministic `RuntimeError("Discord gateway closed before becoming
  ready")` fallback; every failure-path cleanup await bounded +
  suppressed; gateway task stored on the adapter for `close()`);
  `fetch_bot_permissions(conversation, names)` primitive (explicit bot
  member via `get_member`/`fetch_member` fallback, `permissions_for`
  callability guard raising a deliberate `ChatError`). NEW
  `chatlink/live_check.py`: sync `run_live_checks(token, workspace_id,
  conversation_id, thread_id=None, *, timeout=30.0, connector=None)` →
  exactly four `CheckResult` rows (`live_login`, `live_intents`,
  `live_channel_visible`, `live_permissions`, category `transport`);
  deadline-shared per-stage `wait_for` (body never cancelled from
  outside, so the finally-close always runs, itself bounded by
  `CLOSE_TIMEOUT_S`); class-name-based exception matching (never imports
  the SDK); fixed-template messages (token hygiene);
  `REQUIRED_BOT_PERMISSIONS`/`OPTIONAL_BOT_PERMISSIONS` pinned to
  `aidocs/chat/discord_bot_setup.md` step 5; visibility checks the
  configured (possibly thread) ref while permissions ALWAYS evaluate the
  parent-channel ref. `chatlink/wizard.py`: `LiveCheckScreen` inserted
  between Token and Summary (`_STEPS`), titles renumbered to `/7`,
  `WizardSeams.live_runner` + `resolve_seams` default, worker with
  generation token + `is_attached` guard. `chatlink_app.py`:
  `live_runner=None` constructor seam threaded into `action_wizard`.
  Docs: troubleshooting note in
  `website/content/docs/workflows/bug-report-intake.md` + live-validation
  note in `aidocs/chat/discord_bot_setup.md`.
- **Deviations from plan:** None material. The provider≠discord case
  disables the Validate button at compose time (plus a defensive guard in
  the handler) rather than an inline-error-only approach.
- **Issues encountered:** The screen's planned `_running`/`_gen`
  attribute names silently collided with Textual's internal
  `MessagePump._running` (set True when the pump starts), making the
  validate handler early-return unconditionally — renamed to
  `_live_running`/`_live_gen`. In the connect() teardown test, the fake
  client subclass configured `next_config` on the subclass while
  `__init__` reads the base-class attribute — a stale `ready: True`
  leaked into the resistant-gateway scenario until reset on the base.
- **Key decisions:** (1) connect() self-cleans on ANY failure including
  caller-side cancellation (the caller has no adapter handle to close on
  timeout), with every cleanup await bounded so a cancellation-resistant
  gateway task cannot stall a cancelling caller past its deadline. (2)
  live_check uses a deadline shared across stages instead of one outer
  `wait_for`, so the teardown `finally` is never itself cancelled. (3)
  Row messages carry at most an exception class name — hygiene tests
  inject exceptions whose message contains the token. (4)
  `fetch_bot_permissions` is a DiscordAdapter-specific primitive (like
  `connect`), NOT added to the `ChatAdapter` ABC; the permission-name
  policy lives in chatlink. (5) The live step is advisory-only: the
  Pilot walk saves successfully right after a FAILING injected live row.
- **Upstream defects identified:** None
- **Notes for sibling tasks:** t1149_4 (docs rewrite) should describe the
  wizard as seven steps and may fold the live-validation troubleshooting
  paragraph (added at the top of the bug-report-intake troubleshooting
  section) into its rewritten structure — keep the content. The
  `live_runner` seam follows the exact same constructor-seam pattern as
  the other five wizard seams; `tests/test_chatlink_tui.sh` shows the
  spy/blocking-Event idiom for driving the live step. `connect()` now
  surfaces disabled privileged intents as an exception instead of
  hanging — the daemon inherits this (its "bot sits there silently"
  failure mode becomes a crash with a real error).
