---
priority: medium
effort: medium
depends: [1074_2]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1074_2]
created_at: 2026-07-05 10:43
updated_at: 2026-07-05 10:43
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1074_2

## Verification Checklist

- [ ] Connect the Gateway with a real bot token via DiscordAdapter.connect (guild_id set); bot comes online with the required intents (Server Members + Message Content enabled per aidocs/chat/discord_bot_setup.md)
- [ ] send_message / edit_message / delete_message round-trip in a test channel (edit returns edited=True)
- [ ] create_conversation(THREAD, parent=MessageRef) creates a message-anchored thread; parent=channel ConversationRef creates a standalone thread
- [ ] register_commands syncs a guild-scoped slash command (visible immediately); invoking it yields a COMMAND Interaction
- [ ] Button interaction: auto-defer fires within 3 s when the consumer waits; respond() afterwards arrives via the follow-up webhook
- [ ] open_modal called promptly (<2 s) after a button interaction opens the modal; submitting it yields a MODAL_SUBMIT interaction; open_modal after the defer fired raises InteractionExpired
- [ ] send_ephemeral: native ephemeral inside an interaction context; DM fallback outside one; with DMs closed raises DeliveryFailed and posts NOTHING publicly
- [ ] get_permalink for a guild message and a DM message — both links open correctly in the Discord client (@me form for the DM)
- [ ] add_reaction / remove_reaction / fetch_reactions round-trip (custom emoji shows as <:name:id>)
- [ ] upload_attachment / download_attachment round-trip through the Discord CDN (filename and bytes preserved; >8 MiB rejected before any network call)
- [ ] subscribe() delivers MESSAGE_CREATED / REACTION_ADDED / THREAD_CREATED / INTERACTION_RECEIVED events live; a second concurrent subscriber receives the same events independently
