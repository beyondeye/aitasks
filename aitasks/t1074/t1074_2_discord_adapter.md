---
priority: medium
effort: high
depends: [t1074_1]
issue_type: feature
status: Ready
labels: [chat_surface, python]
anchor: 1074
created_at: 2026-06-25 11:53
updated_at: 2026-06-25 11:53
---

## Context

Second child of t1074 (depends on t1074_1 — the frozen `ChatAdapter` contract).
Implements the **full** `ChatAdapter` contract for **Discord** via `discord.py`
(persistent Gateway connection, bot token). Also introduces the **opt-in chat
dependency tier** (`ait setup --with-chat`) since this is the first child needing
a real SDK. Still **non-aitasks-specific** — pure platform↔domain translation.

Parent plan: `aiplans/p1074_chat_adapter_abstraction_layer.md`.
Child plan: `aiplans/p1074/p1074_2_discord_adapter.md`.

## Key Files

- **New:** `.aitask-scripts/chat/discord_adapter.py` — `DiscordAdapter(ChatAdapter)`.
  Lazy `import discord` **inside** the methods that make network calls; the
  platform→domain normalization is written as **module-level pure functions taking
  duck-typed objects** so they unit-test without `discord` installed.
- **New:** `tests/test_chat_discord.sh`.
- **Edit (install flow):** `.aitask-scripts/aitask_setup.sh` — add
  `AIT_PIP_SPECS_CHAT=('discord.py>=2,<3')` + `AIT_IMPORTS_CHAT=(discord)` arrays
  and `--with-chat` flag handling that installs `AIT_PIP_SPECS_CHAT` into the
  CPython venv **only when the flag is set** (mirror the existing `--with-pypy`
  blocks near `aitask_setup.sh:514+` and the arg-parse near `:3100`; dep arrays at
  `:29-32`). **Read `aidocs/framework/aitasks_extension_points.md` first** (install-flow
  touchpoint checklist) and run `shellcheck .aitask-scripts/aitask_setup.sh`.

## Reference Files for Patterns

- Lazy heavyweight import: `.aitask-scripts/applink/content.py` (`import msgpack` inside fns).
- Dep-validation launcher idiom + `require_ait_python`: `.aitask-scripts/aitask_applink.sh`,
  `.aitask-scripts/lib/python_resolve.sh`.
- `--with-pypy` opt-in install precedent: `.aitask-scripts/aitask_setup.sh` (PyPy blocks).
- Graceful test SKIP: `tests/test_applink_router.sh`.

## Discord specifics to implement

- Gateway connection + required intents; map channel/thread/DM ↔ `Conversation`/`ConversationKind`.
- Components (buttons/selects), modals, slash-command registration (`register_commands`).
- `INTERACTION_CREATE` → `Interaction`; **auto-defer on receipt** (3 s) then follow-up
  webhook for `respond`/`follow_up`; past-window → `InteractionExpired`.
- Ephemeral: interaction-response flag only; **DM fallback** otherwise; if neither →
  `DeliveryFailed` (never public). `supports_ephemeral` context-dependent.
- Permalink: `https://discord.com/channels/<guild>/<channel>/<message>`.
- Events: `MESSAGE_DELETE`, `MESSAGE_REACTION_REMOVE`, `GUILD_MEMBER_REMOVE`,
  `INTERACTION_CREATE`, message create/edit, thread create/delete, member join → normalized `EventType`.
- `fetch_reactions` from message reactions; `IdentityClaims` from guild roles (`kind=discord_role`).
- `Capabilities`: `supports_standalone_threads=True`, `supports_message_search=False`,
  Discord `max_message_length`/`max_attachment_bytes` (note boost-tier attachment limits).

## Implementation Plan (high level — see child plan)

1. Write the install-flow edits to `aitask_setup.sh` (arrays + `--with-chat`); shellcheck.
2. Implement pure normalization functions (discord object → domain `Event`/`Message`/`Interaction`/`Actor`/`IdentityClaims`, and domain components → discord payloads).
3. Implement `DiscordAdapter(ChatAdapter)` methods using `discord.py` (lazy import), delegating mapping to the pure functions; honor the contract semantics (auto-defer, private-only ephemeral, subscription recovery).
4. Write `tests/test_chat_discord.sh` against `SimpleNamespace` stubs (no real lib), with graceful SKIP if a future live path needs `discord`.

## Verification

```bash
bash tests/test_chat_discord.sh          # PASSES with no `discord` installed (stub-based)
shellcheck .aitask-scripts/aitask_setup.sh
ait setup --with-chat && ~/.aitask/venv/bin/python -c "import discord; print(discord.__version__)"
```
The stub-based normalization tests must pass on the stock venv; `--with-chat` must
install `discord.py` into `~/.aitask/venv` and leave default (`ait setup` without the
flag) installs unchanged.
