---
Task: t1074_3_slack_adapter.md
Parent Task: aitasks/t1074_chat_adapter_abstraction_layer.md
Sibling Tasks: aitasks/t1074/t1074_1_core_domain_model_and_chatadapter.md (archived), aitasks/t1074/t1074_2_discord_adapter.md (archived)
Archived Sibling Plans: aiplans/archived/p1074/p1074_1_core_domain_model_and_chatadapter.md, aiplans/archived/p1074/p1074_2_discord_adapter.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/fable5 @ 2026-07-05 11:52
---

# Plan: t1074_3 — Slack adapter (slack_bolt + slack_sdk, Socket Mode)

> Last child of t1074. Verified against the current codebase 2026-07-05 (all
> anchors below re-checked). Parent decomposition:
> `aiplans/p1074_chat_adapter_abstraction_layer.md`; binding sibling notes in
> `aiplans/archived/p1074/p1074_2_discord_adapter.md` (Final Implementation
> Notes → "Notes for sibling tasks") and the platform checklist in
> `aidocs/chat/slack_app_setup.md`.

## Context

Implements the full frozen `ChatAdapter` contract (26 abstract methods,
`.aitask-scripts/chat/adapter.py`) for **Slack** via `slack_bolt` +
`slack_sdk` in **Socket Mode** (outbound WebSocket; no public endpoint — fits
a local `ait` workspace). Pure platform↔domain translation, zero business
logic, no aitasks concepts. Mirrors the landed Discord adapter
(`.aitask-scripts/chat/discord_adapter.py`, 1512 lines) — same testability
architecture: module-level pure normalization + injectable-client seam +
single error sink + subscription hub + two-tier SDK-free tests.

## Verified state (2026-07-05)

- `aitask_setup.sh:38-39` — `AIT_PIP_SPECS_CHAT=('discord.py>=2,<3')`,
  `AIT_IMPORTS_CHAT=(discord)`; comment at `:37` already says "t1074_3 appends
  the Slack SDKs here". `--with-chat` flag (`:3160`), `setup_chat_deps()` +
  `chat_deps_present()` (`:673-707`), revalidation clause (`:3231`) all landed
  in t1074_2 — **append-only, no new structure**.
- Contract surface frozen + amended: `Interaction._acked` = **ack-ownership**
  (`interactions.py:226-239`) — Slack is the **instant-ack special case**
  (scheduled = already-performed): ack the Socket Mode envelope on receipt,
  publish with `_acked=True`, **no delayed-defer scheduler**.
- `test_chat_contract.sh` pins signatures/docstrings — implement the exact
  ABC signatures; drift is caught mechanically.
- Discord test suite monkeypatches `da.SUBSCRIBER_QUEUE_MAXSIZE` and uses
  `da._Subscriber` / `da._DISCONNECT` directly (`tests/test_chat_discord.sh:638-650,682`)
  — constrains the hub extraction (Step 2 below).
- `aidocs/chat/slack_app_setup.md` exists (scopes/events/token checklist);
  two future-tense lines (`:18-20`) reference this task and need a
  present-tense touch-up when landing.
- No collisions: no `chat/slack_adapter.py`, no `tests/test_chat_slack.sh`.

**Plan-review hardening (user review, 2026-07-05):** cursor-pagination loops
for all paging Web APIs (+ multi-page fake tests); exact-ts guard on
`fetch_message` point lookups; `supports_message_search` honest-False
(user-token-only API; explicit task-AC amendment at Step 7); enumerated
ephemeral DM-fallback triggers (`user_not_in_channel` et al.); `thread_ts`
propagation on `files_upload_v2` for thread refs.

## Steps (ordered milestones — tree kept green at each boundary)

### 1. Install-flow append (`.aitask-scripts/aitask_setup.sh`)

Append to the existing arrays at `:38-39`:
```bash
AIT_PIP_SPECS_CHAT=('discord.py>=2,<3' 'slack-bolt>=1,<2' 'slack-sdk>=3,<4')
AIT_IMPORTS_CHAT=(discord slack_bolt slack_sdk)
```
Reword the `:37` comment (the append has happened). `shellcheck
.aitask-scripts/aitask_setup.sh` stays clean.

### 2. Extract `_SubscriptionHub` to a shared module (sibling-sanctioned)

The hub is platform-free (domain `Event`/`ConversationRef` + asyncio only)
and would be byte-identical in the Slack adapter. Per the t1074_2 sibling
note ("or extract it to a shared module if identical") extract — don't clone:

- **New `.aitask-scripts/chat/_subscription.py`** (module-private; NOT added
  to the pinned `chat.__all__`): move `_ref_key`, `_Subscriber`,
  `_SubscriptionHub`, `_DISCONNECT`, `SUBSCRIBER_QUEUE_MAXSIZE` verbatim from
  `discord_adapter.py:582-641` (+ module docstring stating its slice).
- **`discord_adapter.py`**: replace the moved block with
  `from ._subscription import (_DISCONNECT, _ref_key, _Subscriber, _SubscriptionHub, SUBSCRIBER_QUEUE_MAXSIZE)`
  — re-export keeps `da._Subscriber` / `da._DISCONNECT` working in the
  existing tests.
- **`tests/test_chat_discord.sh:638-640`**: the `da.SUBSCRIBER_QUEUE_MAXSIZE = 2`
  monkeypatch no longer reaches `_Subscriber.__init__` after the move —
  retarget it at the shared module (`import chat._subscription as subs;
  subs.SUBSCRIBER_QUEUE_MAXSIZE = 2` … restore). This is the only
  cross-file test edit; the overflow test fails loudly (not silently) if
  missed.
- Gate: `test_chat_discord.sh` + `test_chat_contract.sh` green before Step 3.

### 3. Pure normalization functions (`.aitask-scripts/chat/slack_adapter.py`)

Module-level, **dict-shaped inputs** (Slack is JSON-native — stubs are plain
dicts; no SDK import anywhere on this path). `PROVIDER = "slack"`.

Platform → domain:
- `user_to_domain(d) -> User` (users.info shape: `profile.display_name` /
  `real_name` / `name`; `profile.email` only if present — never invented;
  `is_bot`), `actor_from_user(d, *, self_id=None) -> Actor`.
- `member_to_claims(user_info, usergroups, *, is_channel_member) -> IdentityClaims`
  — `is_admin`/`is_owner` flags from users.info; usergroup list →
  `Role(kind="slack_usergroup")`.
- `conversation_kind(d) -> ConversationKind`: `is_im` → DIRECT; `is_mpim` or
  `is_group` or `is_private` → PRIVATE; else CHANNEL. (TEMPORARY unused.)
- `channel_to_ref(d, *, team_id) -> ConversationRef`
  (`provider="slack"`, `workspace_id=team_id`, `conversation_id=channel id`);
  thread refs carry `thread_id=thread_ts` (built where a `thread_ts` exists).
- `channel_to_conversation(d, *, team_id) -> Conversation`
  (`name`, `topic.value`, `is_archived`).
- `message_to_domain(d, *, channel, team_id, self_id=None) -> Message` —
  `ts` string → `float` timestamp, `message_id=ts`; mentions parsed from
  `<@U…>` in text + `blocks` elements; `edited` key → `edited=True`;
  `thread_ts != ts` → ref conversation carries `thread_id`;
  `reply_to` = MessageRef of `thread_ts` parent when present; attachments
  from `files` list via `attachment_to_domain`.
- `attachment_to_domain(d, uploader=None) -> Attachment` (`id`, `name`,
  `mimetype`, `size`, `url_private`).
- `reaction_to_domain(d) -> Reaction` (reactions.get item: `name` as-is
  (Slack style, no colons), `count`, `users` → `user_ids` — honest, only
  what the API returned).
- `event_to_domain(d, *, team_id, self_id=None) -> Event` — Socket Mode
  `events_api` event payloads, per the `Event.payload` contract table:
  - `message` (no subtype) → MESSAGE_CREATED; text mentioning
    `<@self_id>` → **APP_MENTION** (single-source: the `app_mention`
    envelope is ack-only/ignored in `connect()` to avoid double-publish —
    documented in code).
  - `message` subtype `message_changed` → MESSAGE_EDITED (nested `message`).
  - `message` subtype `message_deleted` → MESSAGE_DELETED
    (`{"message_ref": …}` from `deleted_ts`).
  - `reaction_added`/`reaction_removed` → REACTION_ADDED/REMOVED
    (`{"message_ref", "emoji"}`; actor on `Event.actor`).
  - `member_joined_channel`/`member_left_channel` → USER_JOINED/USER_LEFT
    (`{"user": User}` — id-only User when the envelope has just the id).
  - `channel_created` → CHANNEL_CREATED (`{"conversation": …}`).
  - `file_shared` → FILE_UPLOADED (`{"attachment": Attachment(id-only,
    honest-None fields), "message_ref": None}` — hydration is a caller
    concern via `download_attachment`/`fetch_message`).
  - unknown → UNKNOWN with `{"raw": d}`.
  - THREAD_CREATED is emitted synthetically by `create_conversation`
    (Slack has no thread-created event — threads exist implicitly).
- `interaction_to_domain(d, *, team_id, self_id=None) -> Interaction`:
  - `block_actions` → BUTTON or SELECT by `actions[0].type`
    (`custom_id=action_id`; SELECT values under `{"values": […]}`).
  - `view_submission` → MODAL_SUBMIT (`custom_id=view.callback_id`;
    `view.state.values` flattened `{field custom_id: value}`).
  - slash-command payload (`command` key) → COMMAND (`custom_id=command`
    stripped of `/`; `values={"text": text}`).
  - `message` MessageRef when the payload carries `message`/`container`.

Domain → platform:
- `components_to_payload(components) -> list[dict]` — Block Kit `actions`
  blocks: `Button` → `{"type":"button","text":plain_text,"action_id":…,
  "style"}` (style map: primary→primary, danger→danger, else omitted);
  `SelectMenu` → `static_select` (or `multi_static_select` when
  `max_values > 1`) with `options`/`placeholder`.
- `modal_to_payload(modal) -> dict` — `{"type":"modal","callback_id":…,
  "title":plain_text,"submit":plain_text("Submit"),"blocks":[input blocks
  with plain_text_input; `multiline=True` for kind multiline/paragraph]}`.
- `build_permalink(team_id, channel_id) -> str` →
  `https://slack.com/app_redirect?team=<t>&channel=<c>` (conversation-level
  deep link; message permalinks use `chat.getPermalink`, an API call —
  adapter-level, not pure).
- `map_slack_error(exc, *, target) -> ChatError` — the single sink,
  duck-matched (class name `SlackApiError` in MRO or a `response` attribute
  exposing `["error"]`/`.get("error")`; plus `status`):
  - `channel_not_found`, `thread_not_found`, `is_archived` → target
    `conversation` → `ConversationNotFound`; target `message` → `ChatError`.
  - `user_not_found` / `users_not_found` → `UserNotFound`.
  - `ratelimited` or status 429 → `RateLimited`.
  - `message_not_found`, `file_not_found` → `ChatError`.
  - `not_authed`, `invalid_auth`, `missing_scope`, `not_in_channel`,
    `user_not_in_channel`, `no_permission`, `restricted_action`,
    `channel_not_allowed`, `access_denied`, `cant_update_message`,
    `cant_delete_message` → `PermissionDenied`.
  - `expired_trigger_id` / `trigger_expired` → `InteractionExpired`.
  - `file_uploads_exceed_max_size` / status 413 → `AttachmentTooLarge`.
  - fallback → `ChatError`. Generic `not_found`-ish statuses (404)
    disambiguate by `target` as in the Discord mapper.

### 4. `SlackAdapter(ChatAdapter)` core

Constructor seam (mirrors Discord): `SlackAdapter(web, *, team_id=None,
self_id=None, sdk=None, http_get=None)`:
- `web` — duck-typed AsyncWebClient-shaped object (snake_case Web API
  methods: `chat_postMessage(...)`, `conversations_info(...)`, … returning
  dict-shaped responses). Tests pass async fakes; **no SDK import on the
  fake path**.
- `sdk` — lazily-imported `slack_sdk` namespace override (used for
  `AsyncWebhookClient` construction on the `response_url` path).
- `http_get` — injectable `async (url, headers) -> bytes` used by
  `download_attachment` (`url_private` + `Authorization: Bearer <token>`);
  defaults to a lazy aiohttp fetch through the web client's session/token.
- `connect(bot_token, app_token, *, team_id=None)` **classmethod — the only
  SDK/Socket-Mode entry point**: builds `slack_bolt.async_app.AsyncApp` +
  `AsyncSocketModeHandler`, resolves `self_id`/`team_id` via `auth.test`,
  registers the event/interactivity handlers (ack → normalize →
  `hub.publish`), wires disconnect → `hub.disconnect_all()`.

Methods (every SDK call funnels through `map_slack_error` with its own
`target`; two-step resolution where a bare not-found is ambiguous —
conversation first, then message, as in Discord):
- **Messaging:** `send_message` → `chat.postMessage` (`thread_ts` from
  `ref.thread_id`, or from `reply_to.message_id` — Slack threading IS
  reply); `blocks` from `components_to_payload`; returns
  `message_to_domain` of the response `message`. `edit_message` →
  `chat.update` (`edited=True` enforced). `delete_message` → `chat.delete`.
  `fetch_message` → resolve conversation (`conversations.info`,
  target=conversation) then `conversations.replies`/`history`
  point-lookup (`latest=ts, inclusive=True, limit=1`; thread refs use
  `replies`). **Exact-ts guard (binding):** Slack returns the nearest
  message at-or-before `latest` — a deleted/inaccessible target silently
  yields the *wrong* message. Assert the returned message's `ts` equals
  the requested `MessageRef.message_id`; mismatch or empty → `ChatError`
  (never hand higher layers a neighbor).
- **Ephemeral:** `send_ephemeral` → `chat.postEphemeral` (true native path —
  works without interaction context; richer than Discord) → DM fallback
  (`conversations.open` + `chat.postMessage`) → `DeliveryFailed`. Never a
  public post. **Fallback triggers (binding):** ANY native-path failure
  falls through to DM (blanket catch, Discord parity) — the tests
  enumerate the Slack failures that occur on *normal* approval-prompt
  flows and must each reach the DM path, not surface as errors:
  `user_not_in_channel` (actor not in channel), `not_in_channel` /
  `channel_not_found` (app not a member / gone channel), `no_permission`,
  and thread-ephemeral refusal (inactive thread view).
  `EphemeralReceipt(path=NATIVE, message=None)` (ephemerals have no
  re-addressable handle); DM path returns the posted Message.
- **Conversations:** `create_conversation`:
  - THREAD + `MessageRef` parent → no create API exists (threads are
    implicit): resolve the parent channel (`conversations.info`,
    existence probe), build `Conversation(kind=THREAD,
    ref(conversation_id=channel, thread_id=parent ts))`, emit synthetic
    THREAD_CREATED to the hub.
  - THREAD + channel `ConversationRef` parent → `PermissionDenied`
    (`supports_standalone_threads=False` — the contract's gated raise).
  - DIRECT (requires `participants`) → `conversations.open(users=…)`.
  - CHANNEL → `conversations.create` (+ emit CHANNEL_CREATED);
    PRIVATE → `conversations.create(is_private=True)`.
  - TEMPORARY → `PermissionDenied`.
  - Missing required args (THREAD w/o parent, DIRECT w/o participants) →
    `ValueError` (caller bug — Mock parity).
  - `archive_conversation` → `conversations.archive`; a THREAD ref →
    `ChatError` (Slack threads cannot be archived — documented platform
    gap, mirroring Discord's channel-lock note).
- **Cursor pagination (binding — Slack collection APIs page):**
  `conversations.list`, `conversations.members`, `conversations.history`,
  and `conversations.replies` all page via
  `response_metadata.next_cursor` / `has_more`; slack_sdk does **not**
  auto-paginate a single call (unlike discord.py's history iterator). A
  shared private helper `_paginate(method, key, *, limit=None, **kwargs)`
  loops `cursor=next_cursor` until the cursor is empty/`has_more` falsy or
  `limit` items are collected, concatenating the `key` list from each page.
  Every collection method below goes through it — a one-page fake must not
  be the only shape the code ever sees.
- **History:** `fetch_history` → channel refs: `conversations.history`
  (`latest` from `before` exclusive, `oldest` from `after` exclusive,
  `limit`); thread refs: `conversations.replies(ts=thread_id)` with the
  same paging args. Cursor-paginated until `limit` messages or exhaustion;
  chronological sort, ≤ limit.
- **Participants/discovery:** `fetch_participants` →
  `conversations.members` (cursor-paginated to completion) + `users.info`
  per id. `fetch_conversation` → `conversations.info`
  (target=conversation). `list_conversations` → `conversations.list`
  (`types="public_channel,private_channel,im,mpim"`, cursor-paginated to
  completion), kind-filtered. `get_permalink` → MessageRef:
  `chat.getPermalink`; ConversationRef: pure `build_permalink`.
- **Identity:** `fetch_user` → `users.info` (target=user).
  `fetch_identity_claims` → `users.info` (admin/owner flags) +
  `conversations.members` (is_channel_member) + `usergroups.list` /
  `usergroups.users.list` membership scan → `Role(kind="slack_usergroup")`.
  Usergroup-scan failures (e.g. missing `usergroups:read`) degrade to
  `roles=[]` with a `metadata` note — claims never invent privileges, and
  a missing optional scope must not make claims unusable.
- **Reconciliation:** `fetch_reactions` → `reactions.get` →
  `reaction_to_domain` list.
- **Files:** `upload_attachment` — size pre-check vs
  `capabilities().max_attachment_bytes` **before any network call**
  (`AttachmentTooLarge`), then `files_upload_v2(channel=…, filename,
  content)` — **with `thread_ts=ref.thread_id` when the ConversationRef is
  a thread ref** (binding: without it, uploads into a task thread land in
  the channel root); normalize the returned file. `download_attachment` — via the
  `http_get` seam with bearer auth; 404/gone → `ChatError`; no URL →
  `ChatError`.
- **Reactions:** `add_reaction`/`remove_reaction` → `reactions.add`/
  `reactions.remove` (`name=emoji.strip(":")` — accepts both `:tada:` and
  `tada`); "already reacted"/"no reaction" errors → no-op (contract).

### 5. Interactions + subscribe + capabilities

- **Instant-ack (amended `_acked` contract, Slack special case):** bolt
  handlers receive `ack` — `await ack()` (or the modal/command response
  envelope) **on receipt, before publishing**; `_on_interaction(payload,
  ack)` normalizes once, sets `_acked=True`, stores a `_LiveInteraction`
  analog (`payload`, `response_url`, `trigger_id`, `received_at`), and
  publishes an INTERACTION_RECEIVED event **around the identical ack-owned
  object** (t1074_2 post-review regression — pin with an object-identity
  check). No defer scheduler; `ack()` ABC method = idempotent no-op.
- **`respond` / `follow_up`:** POST to the stored `response_url`
  (`response_type: "ephemeral"|"in_channel"`, `blocks` from components) via
  a lazily-built `slack_sdk` `AsyncWebhookClient` (through the `sdk` seam —
  fake-able). Slack's webhook returns no message handle → return `None`
  (contract-sanctioned). Unknown/expired interaction id or a failed post →
  `InteractionExpired`. `respond` marks `responded=True`; `follow_up`
  requires a live entry, same window.
- **`open_modal`:** `views.open(trigger_id, view=modal_to_payload(modal))`.
  Expired `trigger_id` (~3 s window) → the SDK error maps to
  `InteractionExpired` (via the sink); missing live entry → same. A
  MODAL_SUBMIT interaction has no fresh trigger_id → `InteractionExpired`
  (platform rule; mirror Discord's guard).
- **`register_commands`:** Slack slash commands are **app-config-level**
  (no bulk programmatic registration — `aidocs/chat/slack_app_setup.md` §5):
  validate specs (non-empty lowercase names, no spaces) raising
  `ValueError` on caller bugs, then **no-op** — idempotent convergence per
  the ABC contract ("adapters document what can be automated").
- **`subscribe`:** identical shape to Discord — `_Subscriber` from the
  shared `chat/_subscription.py` hub; async generator yields until
  `_DISCONNECT`; deregisters in `finally`.
- **`capabilities()`:** buttons/selects/modals/slash/reactions/files/
  ephemeral/dm/editing/thread_creation = True; voice=False;
  standalone_threads=False; **message_search=False** (platform-honest:
  `search.messages` requires a **user token** (`xoxp-`) with
  `search:read` — this adapter's credentials are bot+app tokens only, so
  an instance genuinely cannot search; advertising True would invite
  higher layers to branch onto a dead path. `metadata` notes the platform
  supports it behind a user-token seam — flipping the flag requires that
  seam plus an ABC search verb via the amendment path, both out of scope).
  **Explicit AC deviation:** the task file's "search.messages →
  `supports_message_search=True`" line is amended at Step 7
  (post-approval, committed via `./ait git`) to record this
  capability-honesty decision — no silent deviation.
  `max_message_length=40000` (chat.postMessage text limit; blocks
  section-text 3000-char limit noted in `metadata`);
  `max_attachment_bytes=1 GiB` (platform per-file cap, plan-independent).

### 6. Tests — `tests/test_chat_slack.sh` (new)

Bash wrapper mirroring `tests/test_chat_discord.sh` exactly (source
`lib/python_resolve.sh` → `require_ait_python` → heredoc with
`sys.path.insert`). **SDK-free guards at both ends**:
`assert "slack_sdk" not in sys.modules and "slack_bolt" not in sys.modules`.

- **Tier 1 — pure functions on plain dicts:** conversation kinds (im/mpim/
  group/private/channel), refs incl. thread_ts, `message_to_domain` (ts
  float, edited, mentions, files, thread reply_to), full `event_to_domain`
  table (message/changed/deleted, self-mention → APP_MENTION,
  reactions, member join/leave, channel_created, file_shared, unknown),
  `interaction_to_domain` (block_actions button + select, view_submission
  value flattening, slash command), `components_to_payload` (actions
  blocks, multi_static_select on max_values>1), `modal_to_payload`,
  `build_permalink`, `map_slack_error` full matrix (error-string × target,
  429/413/trigger-expired/fallback).
- **Tier 2 — adapter-level, no-network, fake `web` client** (async fakes
  recording calls):
  - ABC satisfaction: instantiation, `isinstance(…, ChatAdapter)`,
    `inspect.isasyncgenfunction(SlackAdapter.subscribe)`, signature-pin of
    all 26 methods vs the ABC, **no-stub check** (no method raises
    `NotImplementedError`).
  - Behavior: `send_message` (thread_ts from ref / reply_to; blocks),
    `edit_message`, `fetch_history` args (latest/oldest/limit; replies for
    thread refs), thread create (MessageRef ok + synthetic THREAD_CREATED;
    channel-ref → `PermissionDenied`; missing parent → `ValueError`),
    DIRECT open, ephemeral chain (postEphemeral → DM → `DeliveryFailed`,
    construction-spy proves **no public post**), upload pre-check rejects
    oversize **before** any web call, download via fake `http_get`
    (bearer header asserted), reactions name-strip + no-op semantics,
    identity claims (admin/owner/usergroups + missing-scope degradation to
    empty roles), `register_commands` validate+no-op, error translation
    through real call sites (channel resolve → `ConversationNotFound`;
    message fetch on a resolvable channel → `ChatError`; user fetch →
    `UserNotFound`).
  - **Pagination (multi-page fakes — one-page fakes must not be the only
    shape):** `fetch_history` with a fake returning two pages
    (`has_more=True` + `next_cursor`, then final page) yields the
    concatenated chronological result and passed `cursor=` on page 2;
    `list_conversations` and `fetch_participants` likewise assemble across
    a `next_cursor` boundary; `limit` stops the history loop mid-cursor.
  - **fetch_message exact-ts guard:** a fake whose bounded-range lookup
    returns a *neighbor* message (older ts than requested — the
    deleted-target shape) → `ChatError`, never the neighbor; exact match →
    returned.
  - **Ephemeral fallback matrix:** fake `postEphemeral` raising each of
    `user_not_in_channel`, `not_in_channel`, `channel_not_found`,
    `no_permission` → DM fallback path taken (receipt `path=DM`), never a
    raw error and never a public post.
  - **Upload thread_ts:** upload with a thread ConversationRef records
    `thread_ts=<thread_id>` on the fake `files_upload_v2` call; a channel
    ref records no `thread_ts`.
  - **Capability honesty:** `capabilities().supports_message_search is
    False` pinned with the user-token rationale.
  - Interactions: ack-called-before-publish ordering (fake `ack` records),
    event payload `is` the returned ack-owned object with `_acked=True`
    (identity regression), respond/follow_up through a fake webhook client
    (payload shape, `None` return), expired → `InteractionExpired`,
    `open_modal` via fake `views_open` + expired-trigger mapping,
    MODAL_SUBMIT-cannot-modal.
  - Subscription: two concurrent subscribers, conversation filter, `since`,
    generator close deregisters, overflow sentinel, disconnect ends all —
    exercised through `SlackAdapter` + the shared hub module.
- **Extend `tests/test_chat_no_aitasks_import.sh`** to also import
  `chat.slack_adapter` (decoupling guard parity — t1074_2 did this for the
  Discord module).
- Re-run `test_chat_discord.sh` + `test_chat_contract.sh` (hub extraction
  + no contract drift).

### 7. Docs touch-up (`aidocs/chat/slack_app_setup.md`)

Current-state-only pass: reword `:18-20` ("will install … once t1074_3
appends") to present tense; align §5/§8 phrasing with the landed adapter
surface (`connect(bot_token, app_token)` actual signature); **fix the
`search:read` scope line (`:46`)** — it is a user-token (`xoxp-`) scope,
not a bot-token scope; annotate it accordingly and note
`supports_message_search=False` until a user-token seam exists. No new
doc pages (user-facing website docs stay deferred to t1120).

## Verification

Ordered — default-path check only meaningful with the live venv state known;
chat deps are likely already installed here (t1074_2 opt-in ran), so the
`--with-chat` check is the meaningful one:

```bash
bash tests/test_chat_slack.sh                    # PASS on stock venv (no slack libs)
bash tests/test_chat_discord.sh                  # still PASS (hub extraction)
bash tests/test_chat_contract.sh                 # still PASS (no contract drift)
bash tests/test_chat_no_aitasks_import.sh        # still PASS (+ slack_adapter import)
shellcheck .aitask-scripts/aitask_setup.sh

# Opt-in path (live venv; discord already present from t1074_2):
ait setup --with-chat
~/.aitask/venv/bin/python -c "import slack_bolt, slack_sdk; print('ok')"
```

## Risk

### Code-health risk: low
- `_SubscriptionHub` extraction edits the landed `discord_adapter.py` and retargets one monkeypatch site in `tests/test_chat_discord.sh` · severity: low · → mitigation: TBD (contained: verbatim move + re-export keeps all names; discord + contract suites re-run as a Step-2 gate before any Slack code lands)
- `aitask_setup.sh` array append on a load-bearing install script · severity: low · → mitigation: TBD (contained: append-only to arrays purpose-built for it in t1074_2; shellcheck + opt-in install verification in-task)

### Goal-achievement risk: medium
- Live Socket Mode / Web API paths (instant ack over the real envelope, trigger_id windows, response_url posts, files_upload_v2, bearer downloads) cannot be exercised in-session — stub tests cover normalization and call shapes only · severity: medium · → mitigation: t1129

### Planned mitigations
- timing: after | name: slack_live_smoke_verification | created: t1129 | type: manual_verification | priority: medium | effort: medium | addresses: goal-achievement (live Socket Mode / Web API paths untested in-session) | desc: With a real Slack app (xoxb-/xapp- per aidocs/chat/slack_app_setup.md) — connect Socket Mode, send/edit/delete message, thread reply, button interaction (instant ack → response_url follow-up), open modal within trigger window, ephemeral + DM fallback, file upload/download, reactions, permalink

## Reference: Step 9 (Post-Implementation)

This is the last child. When it completes and `children_to_implement` is
empty, parent t1074 auto-archives per `task-workflow` Step 9.

## Post-Review Changes

### Change Request 1 (2026-07-05 12:35)
- **Requested by user:** Three review findings: (1) `_webhook_send` resolved `AsyncWebhookClient` via `self._sdk().webhook.async_client` attribute traversal, but the real `slack_sdk` does not bind that submodule on bare import — every live `respond`/`follow_up` would die as `InteractionExpired` while nested-shape fakes passed; (2) `send_message` accepted the ABC's `attachments` param but silently dropped it (partial send masquerading as success); (3) the shared hub's `disconnect_all()` used a bare `put_nowait` — a subscriber with an exactly-full bounded queue would raise `QueueFull` out of the transport's disconnect listener, leaving later streams never ended.
- **Changes made:** (1) new `_webhook_client(url)` seam: a fake override with the nested shape is used directly; anything else (no override, or the bare real module passed by `connect`) resolves via a genuine `from slack_sdk.webhook.async_client import AsyncWebhookClient`; dead `_sdk()` helper removed; added a separate live-seam test block (SKIPs without the SDK; runs on the opt-in venv) that exercises the bare-module override BEFORE any submodule import — the exact regression shape. (2) `send_message` now raises base `ChatError` on non-empty `attachments` (loud platform gap; construction-spy test proves no post happened). (3) `disconnect_all()` drains-then-pushes on `QueueFull` like the overflow path; full-queue disconnect test added (sentinel terminal on the full queue AND on later subscribers, no raise).
- **Files affected:** `.aitask-scripts/chat/slack_adapter.py`, `.aitask-scripts/chat/_subscription.py`, `tests/test_chat_slack.sh`

## Final Implementation Notes

- **Actual work done:** Implemented per the approved plan, all 7 milestones:
  (1) `aitask_setup.sh` chat-tier append — `slack-bolt>=1,<2` + `slack-sdk>=3,<4`
  in `AIT_PIP_SPECS_CHAT`, `slack_bolt slack_sdk` in `AIT_IMPORTS_CHAT`
  (comment reworded to current state); no new shellcheck findings (diffed
  against the pre-edit baseline — identical). (2) `_SubscriptionHub` extracted
  verbatim to new shared `chat/_subscription.py` (module-private, not in the
  pinned `__all__`); `discord_adapter.py` imports + re-exports the names;
  the one monkeypatch site in `tests/test_chat_discord.sh` retargeted at
  `chat._subscription`. (3–5) new `chat/slack_adapter.py` (~1470 lines) —
  module-level pure normalization on plain dicts (Slack is JSON-native),
  `map_slack_error(exc, target=…)` single sink with the string×target table,
  `_paginate` cursor loop driving conversations.list/members/history/replies,
  `SlackAdapter` implementing all 26 ABC methods: instant-ack interactions
  (ack-before-publish, identical ack-owned object in INTERACTION_RECEIVED),
  `response_url` respond/follow_up via a webhook-client seam, `views.open`
  modals (MODAL_SUBMIT guard), exact-ts guard on `fetch_message` point
  lookups, ephemeral chain postEphemeral → DM → DeliveryFailed (blanket
  native-failure fallthrough), synthetic THREAD_CREATED on implicit thread
  creation (standalone → PermissionDenied), `thread_ts` propagation on
  `files_upload_v2`, bearer-authed `http_get` download seam, usergroup-scan
  degradation to empty roles + metadata note, `register_commands`
  validate+no-op (app-config-level), `connect(bot_token, app_token)` as the
  only SDK/Socket-Mode entry. (6) `aidocs/chat/slack_app_setup.md`
  current-state pass incl. the `search:read` user-token correction.
  (7) full verification: `tests/test_chat_slack.sh` 187 SDK-free checks +
  3 live-seam checks (separate process, SKIPs without the SDK), discord 140,
  contract 148, decoupling 4 (+ `chat.slack_adapter` import), model 17,
  mock 57; `ait setup --with-chat` installed both Slack SDKs into the live
  venv (`import slack_bolt, slack_sdk` ok) alongside discord.py.
- **Deviations from plan:**
  - `supports_message_search=False` (plan-review amendment, recorded in the
    task AC pre-implementation): `search.messages` is a user-token
    (`xoxp-`/`search:read`) API the adapter's bot+app credentials cannot
    call; metadata documents the user-token-seam path.
  - `respond`/`follow_up` are response_url-only (no chat.postMessage
    fallback for payloads without one) — plan-faithful, noted here for the
    runtime layer: modal `view_submission` responses may need a
    conversation-addressed post pattern later.
- **Issues encountered:** Three review-caught defects (see Post-Review
  Changes): the real SDK's lazily-bound `webhook.async_client` submodule
  (attribute traversal worked only on nested-shape fakes — fixed with a
  resolution seam + live-seam test ordered before any submodule import);
  silent `attachments` drop on `send_message` (now a loud `ChatError`);
  `QueueFull` escaping `disconnect_all` on an exactly-full subscriber queue
  (now sentinel-safe drain). Also: running `ait setup --with-chat` for
  verification auto-committed the entire uncommitted working tree
  (including a concurrent session's files) as `ait: Add aitask framework`;
  reset away cleanly with `git reset --mixed HEAD~1` and recomposed.
- **Key decisions:** dict-shaped pure normalization (vs Discord's
  attribute-shaped) — Slack payloads are JSON-native so stubs are literal
  dicts; hub extraction over cloning (sibling-sanctioned; re-exports keep
  the Discord test surface); APP_MENTION single-sourced from the `message`
  event with the `app_mention` envelope registered ack-only (no
  double-publish, no dedupe state); `trigger_id` as the Interaction id
  (unique + present on all three payload shapes); exact-ts guard returns
  `ChatError` rather than a nearest-neighbor message; 1 GiB platform
  attachment cap with the 3000-char blocks-section limit in metadata.
- **Upstream defects identified:**
  - `.aitask-scripts/aitask_setup.sh:2655-2678 — non-interactive setup auto-accepts the "commit framework files" prompt and sweeps ALL uncommitted framework-path changes (including other sessions' in-progress work) into an "ait: Add aitask framework" commit; running any ait-setup invocation mid-implementation on a dirty tree silently commits foreign work`
  - `.aitask-scripts/chat/discord_adapter.py:880 — send_message accepts the ABC's attachments parameter and silently drops it (same partial-send-as-success gap fixed for Slack in this task; Discord should also reject loudly or implement the file path)`
- **Notes for sibling tasks:** This is the last child of t1074. For the
  runtime layer (t1120+): both adapters now share `chat/_subscription.py`;
  Slack's `respond`/`follow_up` return `None` always (response_url yields
  no handle) — persist interaction outcomes on receipt; Slack search
  needs a user-token seam + an ABC verb (amendment path) before
  `supports_message_search` can flip; `send_message(attachments=…)` is a
  loud platform gap on Slack (use `upload_attachment`) and a silent one on
  Discord until the upstream defect above is fixed.
