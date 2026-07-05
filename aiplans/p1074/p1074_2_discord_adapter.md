---
Task: t1074_2_discord_adapter.md
Parent Task: aitasks/t1074_chat_adapter_abstraction_layer.md
Sibling Tasks: aitasks/t1074/t1074_1_core_domain_model_and_chatadapter.md (archived), aitasks/t1074/t1074_3_slack_adapter.md
Archived Sibling Plans: aiplans/archived/p1074/p1074_1_core_domain_model_and_chatadapter.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/fable5 @ 2026-07-05 09:30
---

# Plan: t1074_2 — Discord adapter (discord.py, Gateway)

> Depends on t1074_1 (landed 2026-07-02 — the frozen `ChatAdapter` contract in
> `.aitask-scripts/chat/`). Parent decomposition:
> `aiplans/p1074_chat_adapter_abstraction_layer.md`. Verified against the
> current codebase 2026-07-05; all anchors below re-checked.

## Context

Second child of t1074. Implements the full `ChatAdapter` contract for Discord
via `discord.py` (persistent Gateway connection, bot token), and introduces the
opt-in chat dependency tier (`ait setup --with-chat`) — the first child needing
a real SDK. Pure platform↔domain translation; no aitasks concepts.

**Connection model (answers "how does aitasks connect"):** aitasks operates as
a **bot the user installs into their own server/workspace** — Discord: Gateway
bot (bot token, persistent outbound WebSocket; no public HTTP endpoint);
Slack (t1074_3): Socket Mode app (`xoxb-` bot token + `xapp-` app token; also
no public endpoint). Credentials are adapter-construction parameters;
credential *storage* and runtime config schema (env vars / config file) belong
to the later runtime/feature layer (e.g. t1120), not this task.

**Scope addition (user request at plan review):** gather the operational
platform-side setup steps (bot/app creation, tokens, intents, scopes, invite)
in `aidocs/` now — modeled on the Hermes agent docs
(hermes-agent.nousresearch.com/docs/user-guide/messaging/{discord,slack}) —
so user-facing website docs can be derived later when feature tasks (t1120)
land. Both platform docs are gathered here since the research is done; the
Slack doc is reference material for t1074_3.

## Verified contract surface (from landed t1074_1)

`.aitask-scripts/chat/` ships: `model.py` (16 dataclasses + 4 enums),
`errors.py` (`ChatError` + 7 subclasses), `interactions.py` (11 types incl.
pre-acked `Interaction` with `_acked` field), `capabilities.py`, `adapter.py`
(`ChatAdapter` ABC, 26 abstract methods), `mock.py` (`MockChatAdapter` —
reference for semantics). Binding notes for this adapter (from the sibling
plan's Final Implementation Notes):

- Implement the **exact pinned signatures** — `tests/test_chat_contract.sh`
  pins them; drift will be caught.
- Yield interactions only **after** auto-defer/ack, with `_acked=True`.
- `send_ephemeral` returns `EphemeralReceipt` (`path: EphemeralPath`,
  `message: Message | None`) naming the private path used; fallback chain
  native → DM → `DeliveryFailed`, never a public post.
- `respond`/`follow_up` return `None` when the platform yields no
  re-addressable handle; `InteractionExpired` past the follow-up window.
- No `MessageNotFound` in the taxonomy — use base `ChatError` for a gone
  message; `ConversationNotFound` for a gone conversation.
- `fetch_user(user_id: str)`; `fetch_identity_claims(conversation, user_id)`
  → `IdentityClaims` with `Role(kind="discord_role")`; never invent
  privileges (absent knowledge → False/empty).
- Honor the `Event.payload` conventions documented on `Event` in `model.py`.
- `subscribe` is an async generator (`inspect.isasyncgenfunction` must hold —
  use a real `yield` in the implementation).
- `capabilities()` is synchronous.

## Steps

1. **Install-flow scaffold** (`.aitask-scripts/aitask_setup.sh`). **First read
   `aidocs/framework/aitasks_extension_points.md`** (install-flow touchpoints).
   Verified anchors:
   - Dep arrays at `aitask_setup.sh:29-32` — add
     `AIT_PIP_SPECS_CHAT=('discord.py>=2,<3')` and `AIT_IMPORTS_CHAT=(discord)`
     beside them (extend the explanatory comment at `:23-28`).
   - Arg-parse: add `--with-chat) INSTALL_CHAT=1; shift ;;` beside
     `--with-pypy` at `:3110` (initialize `INSTALL_CHAT=0` beside
     `INSTALL_PYPY`'s init).
   - Install block: when `INSTALL_CHAT=1`, `pip install` `AIT_PIP_SPECS_CHAT`
     into the **CPython** venv (`$VENV_DIR`, install site near `:717-734`) and
     verify via `verify_venv_imports`/`verify_venv_specs` with
     `AIT_IMPORTS_CHAT` (mirror the `--with-pypy` opt-in structure at
     `:514-643`, but target `$VENV_DIR`, not a separate venv). When not set,
     behavior is unchanged.
   - `shellcheck .aitask-scripts/aitask_setup.sh` must stay clean.

2. **Pure normalization functions** (module-level in
   `.aitask-scripts/chat/discord_adapter.py`, callable without `discord`
   installed — accept duck-typed objects, `SimpleNamespace`-compatible):
   - `user_to_domain(obj) -> User`, `actor_from_user(obj) -> Actor`,
     `member_to_claims(obj) -> IdentityClaims` (guild roles →
     `Role(kind="discord_role")`, owner/admin flags from permissions).
   - `channel_to_conversation(obj) -> Conversation` + ref building:
     channel/thread/DM → `ConversationKind` (CHANNEL/THREAD/DIRECT/PRIVATE),
     `ConversationRef(provider="discord", workspace_id=guild_id,
     conversation_id=channel_id, thread_id=…)` for threads.
   - `message_to_domain(obj) -> Message` (attachments, mentions, reactions,
     reply_to, edited).
   - `event_to_domain(kind, obj) -> Event` — map message create/edit/delete,
     reaction add/remove, thread create/delete, member join/leave,
     INTERACTION_CREATE → `EventType`; unknown → `EventType.UNKNOWN`.
   - `interaction_to_domain(obj) -> Interaction` (BUTTON/SELECT/MODAL_SUBMIT/
     COMMAND, custom_id, submitted values).
   - Reverse direction: `components_to_payload(components) -> list`,
     `modal_to_payload(modal) -> dict`, `commands_to_payload(specs) -> list`
     (domain → discord API payload dicts; keeps the discord.py UI classes out
     of the pure layer).
   - `build_permalink(guild_id, channel_id, message_id) -> str` →
     `https://discord.com/channels/<g>/<c>/<m>`.

3. **`DiscordAdapter(ChatAdapter)` — architecture (binding design contracts).**
   Lazy `import discord` confined to **construction-time seams** (pattern:
   `.aitask-scripts/applink/content.py`'s lazy `import msgpack`); the class
   itself, all method bodies, and all mapping logic run without the SDK.

   - **Injectable-client seam (testability contract):** `DiscordAdapter`'s
     constructor takes a duck-typed `client` (plus small injectable factories,
     see Files below). The real Gateway client is built only by a
     `DiscordAdapter.connect(token, *, guild_id=None, intents=…)` classmethod
     (the only place that imports/instantiates `discord.Client` +
     `app_commands.CommandTree` and starts the Gateway). No-network tests
     construct the adapter directly with fakes — no SDK import anywhere on
     that path.
   - **Error translation at one sink, with explicit call-site context:** a
     module-level pure helper
     `map_discord_error(exc, *, target: str) -> ChatError` — `target` ∈
     `{"conversation", "message", "user", "attachment"}` is passed by every
     call site, because the right taxonomy class for `NotFound` depends on
     what the operation was addressing, not on the exception alone
     (`NotFound` + `target="conversation"` → `ConversationNotFound`;
     `target="message"` → base `ChatError`; `target="user"` →
     `UserNotFound`; `target="attachment"` → `ChatError`). Independent of
     target: `Forbidden` → `PermissionDenied`; `HTTPException` with
     `status == 429` → `RateLimited`; 413/code-40005 payload errors →
     `AttachmentTooLarge`; anything else → `ChatError`. Matching is on
     exception **class name and attributes** (SDK-import-free, unit-testable
     with `SimpleNamespace` exceptions). Every SDK call site funnels through
     it with its own `target` — SDK exception types never cross the
     boundary. For ops where a `NotFound` is ambiguous at one call site
     (e.g. `fetch_message`: channel gone vs message gone), the adapter
     resolves the channel first (`target="conversation"`), then the message
     (`target="message"`) — two sites, two targets, no guessing inside the
     mapper.
   - **Subscription hub (`_SubscriptionHub`, explicit fan-out design):**
     discord.py delivers each Gateway dispatch to a single event handler; the
     contract requires *independent* per-subscriber streams. Mirror the
     mock's proven design (`mock.py:58-80` `_Subscriber` + `_DISCONNECT`
     sentinel): one set of client event handlers normalizes each dispatch to
     a domain `Event` **once**, then the hub broadcasts it into one
     `asyncio.Queue` per active subscriber. `subscribe()` registers a queue
     with its filter keys (conversation/thread refs via the same `_key`
     normalization; `since` timestamp), yields from it, and deregisters in
     `finally:` (generator close = clean unsubscribe). Filtering applies at
     enqueue time. Queues are bounded (maxsize 1024); on overflow the hub
     pushes `_DISCONNECT` to that subscriber only (per-subscriber backpressure
     disconnect — honest "at-least-once WHILE CONNECTED", never silent drop).
     A Gateway disconnect pushes `_DISCONNECT` to all subscribers (no replay);
     discord.py's own auto-reconnect restores the transport for future
     subscribers.
   - **Interaction ack — delayed-defer scheduler + EXPLICIT contract
     amendment (resolves the modal conflict honestly):** Discord modals must
     be the *initial* interaction response — an immediate defer would make
     `open_modal` permanently impossible, while the frozen contract currently
     reads "an `Interaction` is yielded pre-acked (`_acked=True`)"
     (`interactions.py:226-227`), i.e. the platform ack has *already
     happened* at yield time. These two cannot both hold on Discord, and the
     task AC requires modals — so this plan makes a **deliberate, explicit
     semantic amendment of the frozen contract** (the sanctioned t1074_1
     amendment path: ABC + Mock + contract test move together, never a silent
     adapter divergence):

     **Amended `_acked` semantics:** `_acked=True` means "the ack deadline is
     **owned and guaranteed by the adapter** — the platform ack is either
     already performed or irrevocably scheduled within the platform window;
     the consumer must never ack and may respond at its own pace." An
     instant-ack adapter (Mock; Slack's HTTP 200 in t1074_3) is the special
     case where scheduled = already-performed, so **no Mock behavior
     changes**.

     **Amendment surface (one commit, all together):**
     - `interactions.py` `Interaction` docstring (`:226-227`) — restate
       `_acked` as ack-ownership, note the modal-window consequence.
     - `adapter.py` `ack`/`open_modal`/`subscribe` docstrings — adapter owns
       the deadline; a scheduled defer may narrow the modal window; consumers
       should open modals promptly after receipt.
     - `mock.py` — docstring parity only (instant-ack special case stays).
     - `test_chat_contract.sh` — existing `_acked` pins (field presence,
       compare-exclusion, `ack` signature) stay green; **add** an assertion
       pinning the amended docstring language on `Interaction` (grep for
       "owned" / ack-ownership phrasing) so the semantics can't silently
       drift back.

     **Discord mechanics under the amended contract:** on
     `INTERACTION_CREATE`, normalize and yield immediately with
     `_acked=True`, scheduling a defer task at **~2.0 s** (guaranteed ack
     within Discord's 3 s window). A consumer `open_modal` /
     `respond(ephemeral=…)` before it fires cancels the pending defer and
     becomes the initial response; after the defer fires, `open_modal`
     raises `InteractionExpired` (modal window closed at defer — documented
     limitation: open modals promptly). `ack()` = idempotent no-op.
     MODAL_SUBMIT interactions cannot open a further modal (platform rule —
     `InteractionExpired`).
   - **Threads:** `create_conversation(THREAD, parent=MessageRef)` →
     `message.create_thread(...)`; `parent=channel ConversationRef` →
     `channel.create_thread(...)` (standalone,
     `supports_standalone_threads=True`); DIRECT requires `participants` →
     `user.create_dm()`.
   - **Refs & permalinks (DM-safe):** guild conversations →
     `ConversationRef(workspace_id=str(guild_id))`; **DM/guildless channels →
     `workspace_id="@me"`** (workspace_id is a required field — pinned
     convention, asserted in tests). `build_permalink(workspace_id,
     channel_id, message_id=None)` emits
     `https://discord.com/channels/@me/<c>[/<m>]` for DM refs and
     `<g>/<c>[/<m>]` otherwise — the ephemeral DM-fallback path therefore
     yields valid refs and URLs.
   - **Ephemeral:** in interaction context use the ephemeral flag (native
     path); outside → DM the actor; DM closed (`Forbidden` on
     `user.send`) → `DeliveryFailed` (nothing public). Return
     `EphemeralReceipt` naming the path.
   - **Files (full spec):** `upload_attachment` pre-checks
     `len(content) > capabilities().max_attachment_bytes` →
     `AttachmentTooLarge` (before any network call), then posts the file to
     the conversation via `channel.send(file=self._file_factory(filename,
     content))` — `_file_factory` defaults to a lazy `discord.File(BytesIO(…),
     filename=…)` and is constructor-injectable for tests. Returns a
     normalized `Attachment` preserving `id`, `filename`, `mime_type`
     (`content_type`), `size`, CDN `url`, `uploader=self-actor`.
     `download_attachment` fetches the bytes through the client's HTTP
     session from `attachment.url` (Discord CDN URLs are signed/expiring —
     an expired/gone blob maps to `ChatError`). Round-trip
     (upload→download-shaped fake flow, filename/mime preservation, oversize
     rejection with **no** send call — construction-spy fake) is covered in
     the adapter-level tests.
   - **Reconciliation:** `fetch_reactions` from `message.reactions`
     (emoji normalization: unicode as-is, custom emoji → `<:name:id>` string,
     count + `me` flag into `user_ids`/`metadata` honestly — user lists only
     when fetched).
   - **`register_commands` (scope + sync strategy):** declarative,
     **bulk-overwrite** sync — build `app_commands` from the `SlashCommand`
     specs and `tree.sync(guild=…)`, which upserts the full set and removes
     stale commands (idempotent convergence, per the ABC contract). Scope is
     an explicit **constructor/connect parameter** `guild_id: str | None`:
     when set, commands sync guild-scoped (instant propagation — the
     recommended/documented mode); when `None`, global scope (Discord may
     take up to ~1 h to propagate — documented in the method docstring and
     the aidocs setup page). Requires the `applications.commands` scope from
     the invite URL (Step 5 doc).
   - **Capabilities:** buttons/selects/modals/slash/ephemeral=True,
     search=False, standalone_threads=True, `max_message_length=2000`,
     `max_attachment_bytes=8*1024*1024` (base non-boost limit; boost-tier
     variance noted in `metadata`).
   - **Gateway intents** (in `connect()`): guilds, guild_messages,
     message_content, reactions, members, dm_messages — matching the
     privileged-intent list in the aidocs setup page (Step 5).

4. **Tests** (`tests/test_chat_discord.sh`, new): bash wrapper sourcing
   `.aitask-scripts/lib/python_resolve.sh` (pattern:
   `tests/test_applink_router.sh`); **must PASS on the stock venv — no
   `discord` import anywhere** (guard any future live path with
   `import discord` → `echo SKIP; exit 0`). Two tiers:
   - **Tier 1 — pure normalization** (`SimpleNamespace` stand-ins):
     events→domain, member→claims, interaction→domain, message→domain,
     components/modal/commands→payload, permalink (guild **and** `@me` DM
     forms), conversation-kind mapping, `map_discord_error` full
     target-matrix table (`NotFound` × each `target` value → the four
     distinct outcomes; Forbidden / 429 / oversize / fallback).
   - **Tier 2 — adapter-level, no-network:** import `discord_adapter` and
     instantiate `DiscordAdapter` with fake client/channel/message/user
     objects (async fakes recording calls):
     - ABC satisfaction: instantiation succeeds (no abstract methods left),
       `isinstance(adapter, ChatAdapter)`,
       `inspect.isasyncgenfunction(DiscordAdapter.subscribe)`, and
       signature-pinning of all 26 methods against the ABC
       (`inspect.signature` comparison — the same drift net the contract
       test uses for Mock).
     - Method behavior through fakes: `send_message` (text + components
       payload lands on `channel.send`; `reply_to` → message reply),
       `edit_message`, `fetch_history` pagination args, thread creation
       (both parent kinds), ephemeral DM fallback chain (native → DM →
       `DeliveryFailed` with **no public post** — construction spy),
       upload/download round-trip + oversize-rejects-before-send,
       `register_commands` bulk-sync call shape (guild vs global),
       error translation **through real adapter call sites** (fake raising
       a `NotFound`-shaped exception from a channel resolve →
       `ConversationNotFound`; from a message fetch on a resolvable
       channel → base `ChatError`; from a user fetch → `UserNotFound` —
       proving the call sites pass the right `target`, not just the
       mapper table).
     - Subscription hub: two concurrent subscribers each receive a pushed
       event (independent streams); conversation filtering; `since`
       filtering; generator close deregisters; overflow pushes
       `_DISCONNECT` to the slow subscriber only; disconnect ends all
       streams with no replay.
     - Delayed-defer: consumer calling `open_modal` before the defer fires
       cancels it and opens the modal (fake `interaction.response` records
       order); after the defer fires, `open_modal` →
       `InteractionExpired`; `ack()` idempotent.
   - Also re-run `tests/test_chat_contract.sh` (must stay green after the
     doc-only ABC/Mock docstring clarifications).

5. **Platform setup docs in `aidocs/chat/`** (new directory, sits beside the
   layer it documents; the existing untracked `aidocs/slack/pros_and_cons.md`
   belongs to another session — do not touch it):
   - `aidocs/chat/discord_bot_setup.md` — connection model (Gateway bot, no
     public endpoint); Developer-Portal steps: app creation (note Application
     ID), bot user, **privileged intents** (Server Members + Message Content —
     without Message Content the bot receives events with empty text), token
     reset/copy (never commit), invite URL construction
     (`scope=bot+applications.commands` + minimum permissions: View Channels,
     Send Messages, Read Message History, Attach Files, Embed Links, plus
     thread + reaction permissions our adapter needs), server authorization.
     Close with a "framework-side configuration" section stating what is
     decided here (adapter takes the bot token as a constructor arg) and what
     is deferred (env var / config-file schema, allowed-users policy → runtime
     layer, e.g. t1120).
   - `aidocs/chat/slack_app_setup.md` — reference for t1074_3: Socket Mode
     toggle + `connections:write` app-level token (`xapp-`), bot token scopes
     (`chat:write`, `app_mentions:read`, `channels:history`, `groups:history`,
     `im:*`, `mpim:*`, `users:read`, `files:read`, `files:write`), event
     subscriptions (`message.channels`, `message.groups`, `message.im`,
     `message.mpim`, `app_mention`), App Home Messages tab, install →
     `xoxb-` token; note the app-manifest option for one-shot creation.
   - Both docs are **aidocs** (maintainer-facing groundwork) — user-facing
     website docs are explicitly deferred to the feature tasks.

## Implementation order & completeness guard (scope control)

This child has grown beyond the original sketch (adapter + setup flag + hub +
delayed-defer amendment + files + command sync + two aidocs pages). To keep
the blast radius inspectable and partial-implementation detectable:

**Ordered milestones — each lands with its own tests passing before the next
starts** (single Step-8 commit at the end, but the working tree is kept
green at every milestone boundary so review can walk them):

1. `aitask_setup.sh` scaffold (`--with-chat`) + shellcheck clean.
2. Contract amendment (docstrings in `interactions.py`/`adapter.py`/`mock.py`
   + the new contract-test docstring pin) — `test_chat_contract.sh` green.
3. Pure normalization functions + Tier-1 tests green.
4. Adapter core: constructor/seams, `_SubscriptionHub`, messaging/threads/
   discovery/identity/reconciliation methods + their Tier-2 tests green.
5. Interactions (delayed-defer, respond/follow_up/open_modal), files,
   `register_commands` + remaining Tier-2 tests green.
6. `aidocs/chat/` setup docs (no code).
7. Full verification sequence (below).

**Completeness guard (anti-"tests mirror the design"):** the Tier-2
assertions enumerated in Step 4 are written from the **ABC contract text**
(adapter.py docstrings), not from the Discord implementation — the contract
is the independent ground truth. Structural nets: `DiscordAdapter()`
instantiation fails if any of the 26 methods is missing;
signature-pinning catches drift; and a dedicated check asserts **no method
body is a stub** (none raise `NotImplementedError`), so "implemented but
hollow" cannot pass silently. Any method whose behavior genuinely cannot be
exercised no-network (pure Gateway lifecycle) is listed explicitly in the
plan's Final Implementation Notes with the reason — not silently skipped.

**Approval mode:** manual edit approval is recommended for this task (user
reviews each file edit as it lands) given the touched surfaces include the
frozen contract files and the load-bearing `aitask_setup.sh`.

## Verification

Order matters — the default-path check is only meaningful **before** the
`--with-chat` install (plain `ait setup` never uninstalls, so checking absence
afterwards proves nothing):

```bash
bash tests/test_chat_discord.sh                       # PASS on stock venv (no discord)
bash tests/test_chat_contract.sh                      # still PASS (no contract drift)
shellcheck .aitask-scripts/aitask_setup.sh

# 1. Default path FIRST — precondition is enforced, not advisory:
#    if discord.py is already present in the live venv, this branch MUST NOT
#    run against it (the check would be vacuous). Hard-branch to scratch:
if ~/.aitask/venv/bin/python -c "import discord" 2>/dev/null; then
  # Scratch default-path check: fresh venv, same interpreter, default dep set
  scratch="$(mktemp -d)"; ~/.aitask/venv/bin/python -m venv "$scratch/venv"
  VENV_DIR="$scratch/venv" ait setup      # default install into scratch (env override; if
                                          # aitask_setup.sh doesn't honor VENV_DIR from env,
                                          # recreate ~/.aitask/venv instead — do NOT proceed
                                          # against a venv that already has discord)
  "$scratch/venv/bin/python" -c "import discord" 2>/dev/null \
    && { echo "FAIL: default installed discord"; exit 1; } \
    || echo "OK: default leaves chat tier out"
  rm -rf "$scratch"
else
  ait setup                               # default install, live venv (discord absent)
  ~/.aitask/venv/bin/python -c "import discord" 2>/dev/null \
    && { echo "FAIL: default installed discord"; exit 1; } \
    || echo "OK: default leaves chat tier out"
fi

# 2. Only after 1 passed — the opt-in path (live venv):
ait setup --with-chat
~/.aitask/venv/bin/python -c "import discord; print(discord.__version__)"   # OK
```

The default-path check is pass/fail, never advisory: a `FAIL` line or an
unusable scratch path **blocks** proceeding to step 2 (exit 1), so the
verification cannot silently degrade into checking an already-polluted venv.

## Risk

### Code-health risk: low
- `aitask_setup.sh` is a load-bearing 3k-line install script; the new flag/install block could disturb the default path · severity: low · → mitigation: TBD (contained: flag-gated, mirrors the proven `--with-pypy` structure, shellcheck + ordered default-first install verification in-task)
- Explicit semantic amendment of the frozen contract's `_acked` meaning (already-acked → ack-ownership-guaranteed) — touches ABC/Interaction/Mock docstrings + adds a contract-test pin; no signature or Mock behavior change, but future adapters (t1074_3 Slack) must be written against the amended semantics · severity: medium · → mitigation: amendment lands as one milestone-2 commit unit with the contract-test docstring pin; t1074_3 notes updated via this plan's "Notes for sibling tasks"

### Goal-achievement risk: medium
- Live Gateway/REST paths (defer timing, thread creation, ephemeral webhooks, intents) cannot be exercised in-session — stub tests cover only pure normalization; live-path defects would surface only when a real bot runs · severity: medium · → mitigation: discord_live_smoke_verification

### Planned mitigations
- timing: after | name: discord_live_smoke_verification | type: manual_verification | priority: medium | effort: medium | addresses: goal-achievement (live Gateway/REST paths untested in-session) | desc: With a real bot token/guild — connect Gateway, send/edit/delete message, create message-anchored + standalone threads, button interaction (auto-defer → follow-up), ephemeral + DM fallback, permalink, reactions

## Reference: Step 9 (Post-Implementation)
Standard archival/merge per `task-workflow` Step 9 when this child completes.

## Final Implementation Notes

- **Actual work done:** Implemented per the approved plan, all 7 milestones:
  (1) `aitask_setup.sh` chat tier — `AIT_PIP_SPECS_CHAT=('discord.py>=2,<3')` +
  `AIT_IMPORTS_CHAT=(discord)` beside the existing dep arrays, `--with-chat`
  arg-parse, `setup_chat_deps()` installing into the CPython venv with
  verify/retry/warn-never-die, `chat_deps_present()` revalidation probe;
  (2) the `_acked` contract amendment (docstrings in `interactions.py`,
  `adapter.py` `ack`/`open_modal`/`subscribe`, `mock.py` instant-ack parity)
  + 2 contract-test pins on the amended language (146→148 checks);
  (3–5) `chat/discord_adapter.py` — module-level pure normalization
  functions, `map_discord_error(exc, target=…)` single sink,
  `_SubscriptionHub` (per-subscriber bounded queues, sentinel disconnect on
  overflow/gateway drop), `DiscordAdapter` implementing all 26 ABC methods
  with the delayed-defer (2.0 s) owned-ack scheme, DM-safe `@me`
  refs/permalinks, files with oversize pre-check + CDN download via the
  client session, guild-vs-global declarative command sync via HTTP bulk
  upsert, `connect()` as the only SDK/Gateway entry point;
  (6) `aidocs/chat/discord_bot_setup.md` + `slack_app_setup.md` (t1074_3
  reference) documenting the bot-install connection model and platform-side
  configuration; (7) full ordered verification. Tests:
  `tests/test_chat_discord.sh` (Tier 1 pure + Tier 2 adapter-level, 140
  checks, SDK-free with `sys.modules` guards at both ends), decoupling
  guard extended to import `chat.discord_adapter`.
- **Deviations from plan:**
  - Plain `ait setup` *after* a `--with-chat` opt-in revalidates/repairs the
    chat deps (`chat_deps_present()` clause) — pypy-parity behavior beyond
    the strict "only when the flag is set" wording; never-opted-in users are
    untouched. Surfaced at review; accepted.
  - `_build_view`/`_build_modal` take the SDK namespace as a parameter
    (stub-testable) instead of a constructor-injected `file_factory`; the
    `sdk=` constructor seam covers files too.
  - `register_commands` uses `http.bulk_upsert_{guild,global}_commands` (raw
    declarative payloads from `commands_to_payload`) rather than an
    `app_commands.CommandTree` — truer to bulk-overwrite convergence and
    fake-able without the SDK.
- **Issues encountered:** One review-caught bug (see Post-Review Changes):
  the INTERACTION_RECEIVED event initially re-normalized the native object,
  handing subscribers an `_acked=False` copy — fixed by publishing the
  identical ack-owned Interaction, with an object-identity regression check.
  Scratch-install verification required overlaying the working-tree
  `aitask_setup.sh` (install.sh downloads the released tarball, which
  predates `--with-chat`).
- **Key decisions:** explicit `_acked` semantic amendment (ack-ownership:
  performed-or-irrevocably-scheduled) instead of a silently-untrue flag or
  dropping modal support; defer at 2.0 s inside Discord's 3 s window;
  per-subscriber overflow = sentinel disconnect of that subscriber only
  (never silent drop); `workspace_id="@me"` pinned for guildless refs;
  `NotFound` disambiguated by call-site `target`, with `fetch_message`
  resolving channel first so the two targets never guess; base 8 MiB
  attachment cap (boost variance in `capabilities().metadata`).
- **Upstream defects identified:** None
- **Notes for sibling tasks:** For t1074_3 (Slack): append
  `'slack-bolt>=1,<2' 'slack-sdk>=3,<4'` to `AIT_PIP_SPECS_CHAT` and
  `slack_bolt slack_sdk` to `AIT_IMPORTS_CHAT` (arrays + install fn already
  in place — no new setup.sh structure needed). Write the adapter against
  the **amended** `_acked` contract: Slack's HTTP-200 ack is the instant-ack
  special case (no delayed defer; modals open via `views.open` within the
  `trigger_id` window). Reuse the patterns: pure normalization functions on
  duck-typed objects, `map_slack_error(exc, target=…)` with call-site
  targets, a `_SubscriptionHub` clone (or extract it to a shared module if
  identical), `sdk=`-style constructor seam, two-tier SDK-free test layout
  from `tests/test_chat_discord.sh`. `aidocs/chat/slack_app_setup.md` holds
  the scope/event/token checklist. `register_commands` on Slack is
  app-config-level: validate + no-op per the ABC contract.

## Post-Review Changes

### Change Request 1 (2026-07-05 09:10)
- **Requested by user:** Bug — `_on_interaction()` returned an ack-owned Interaction (`_acked=True`) but published an INTERACTION_RECEIVED event carrying a separately re-normalized Interaction with `_acked=False`, violating the ack-ownership contract for subscribers.
- **Changes made:** `_on_interaction` now constructs the Event directly around the same ack-owned `domain` object (no re-normalization); added a regression check asserting `event.payload["interaction"] is` the returned object with `_acked=True` (suite now 140 checks).
- **Files affected:** `.aitask-scripts/chat/discord_adapter.py`, `tests/test_chat_discord.sh`
