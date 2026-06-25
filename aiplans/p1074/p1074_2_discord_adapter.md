---
Task: t1074_2_discord_adapter.md
Parent Task: aitasks/t1074_chat_adapter_abstraction_layer.md
Sibling Tasks: aitasks/t1074/t1074_1_core_domain_model_and_chatadapter.md, aitasks/t1074/t1074_3_slack_adapter.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
---

# Plan: t1074_2 — Discord adapter (discord.py, Gateway)

> Depends on t1074_1 (the frozen `ChatAdapter` contract). Parent decomposition:
> `aiplans/p1074_chat_adapter_abstraction_layer.md`. Read t1074_1's archived plan
> (`aiplans/archived/p1074/p1074_1_*.md`) for the exact public surface before starting.

## Goal

Implement `DiscordAdapter(ChatAdapter)` against `discord.py` and introduce the
opt-in `ait setup --with-chat` dependency tier. Pure platform↔domain translation;
no aitasks concepts.

## Steps

1. **Install-flow scaffold** (`.aitask-scripts/aitask_setup.sh`). **First read
   `aidocs/framework/aitasks_extension_points.md`** (install-flow touchpoints).
   - Add near the existing dep arrays (`:29-32`):
     `AIT_PIP_SPECS_CHAT=('discord.py>=2,<3')` and `AIT_IMPORTS_CHAT=(discord)`.
   - Add a `--with-chat` flag (mirror `--with-pypy`: arg-parse near `:3100`, install
     block near `:514+`). When set, `pip install` `AIT_PIP_SPECS_CHAT` into the
     **CPython** venv (`$VENV_DIR`) and verify imports via `AIT_IMPORTS_CHAT`. When
     not set, behavior is unchanged (deps not installed).
   - `shellcheck .aitask-scripts/aitask_setup.sh` must stay clean.

2. **Pure normalization functions** (module-level in `discord_adapter.py`, no
   `discord` import needed to call them — accept duck-typed objects):
   - `message_to_domain(obj) -> Message`, `user_to_domain(obj) -> User`,
     `member_to_claims(obj) -> IdentityClaims` (`Role.kind="discord_role"`),
     `event_to_domain(kind, obj) -> Event` (map MESSAGE_DELETE/REACTION_REMOVE/
     GUILD_MEMBER_REMOVE/INTERACTION_CREATE/create/edit/thread/member-join → `EventType`),
     `interaction_to_domain(obj) -> Interaction`, and the reverse
     `components_to_payload(components) -> list/dict`, `modal_to_payload(modal)`.
   - Conversation/thread mapping: channel/thread/DM → `Conversation` + `ConversationRef`
     (`provider="discord"`, `thread_id` for threads).

3. **`DiscordAdapter(ChatAdapter)`** — lazy `import discord` inside the methods that
   open the gateway / call the REST API. Implement every ABC method, delegating
   mapping to the pure functions. Honor contract semantics:
   - **Threads:** `create_conversation(THREAD, parent=MessageRef)` → message thread;
     `parent=channel ConversationRef` → standalone thread (`supports_standalone_threads=True`).
   - **Interactions:** on `INTERACTION_CREATE`, **defer within 3 s** (`interaction.response.defer`)
     **before** yielding the `Interaction`; `respond`/`follow_up` use the follow-up
     webhook; responding past the window → `InteractionExpired`. `ack` idempotent.
   - **Ephemeral:** `respond(ephemeral=True)` uses the ephemeral flag; `send_ephemeral`
     outside an interaction → DM the actor; if DM closed → `DeliveryFailed` (no public post).
   - **Discovery:** `get_permalink` builds `https://discord.com/channels/<g>/<c>/<m>`;
     `fetch_conversation` raises `ConversationNotFound` when gone.
   - **Reconciliation:** `fetch_reactions` from `message.reactions`.
   - **Capabilities:** buttons/selects/modals/slash=True, ephemeral=True (interaction
     ctx), search=False, standalone_threads=True, plus Discord `max_message_length`
     (2000) and `max_attachment_bytes` (note boost-tier variance — use the base limit).
   - Register required gateway intents; `register_commands` registers Application Commands.

4. **Tests** (`tests/test_chat_discord.sh`): exercise the **pure functions** against
   `SimpleNamespace` stand-ins for discord objects (events→domain, member→claims,
   interaction→domain, components→payload) — **no `discord` import**. Guard any
   future live path with `import discord` → `echo SKIP; exit 0` (per
   `tests/test_applink_router.sh`).

## Verification

```bash
bash tests/test_chat_discord.sh                       # PASS on stock venv (stub-based)
shellcheck .aitask-scripts/aitask_setup.sh
ait setup --with-chat && ~/.aitask/venv/bin/python -c "import discord; print(discord.__version__)"
# Default install unchanged:
ait setup            # must NOT install discord.py
```

## Final Implementation Notes
_(to be filled at implementation time — actual work, deviations, issues, upstream defects, notes for sibling t1074_3)._

## Reference: Step 9 (Post-Implementation)
Standard archival/merge per `task-workflow` Step 9 when this child completes.
