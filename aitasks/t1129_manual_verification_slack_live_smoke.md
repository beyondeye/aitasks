---
priority: medium
effort: medium
depends: [1074_3]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1074_3]
created_at: 2026-07-05 12:39
updated_at: 2026-07-05 12:39
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1074_3

## Verification Checklist

- [ ] Connect Socket Mode with a real app (xoxb- bot token + xapp- app token per aidocs/chat/slack_app_setup.md) via SlackAdapter.connect; auth.test resolves self_id/team_id and events start flowing
- [ ] send_message / edit_message / delete_message round-trip in a test channel (edit returns edited=True); reply_to posts into the parent's thread
- [ ] create_conversation(THREAD, parent=MessageRef) yields a working thread ref (fetch_history on it uses conversations.replies); parent=channel ConversationRef raises PermissionDenied
- [ ] Slash command invocation (declared on the app config page) arrives as a COMMAND Interaction with _acked=True; respond() lands via response_url within the window
- [ ] Button interaction: instant ack on receipt (no Slack retry banner); respond(ephemeral=True) posts an ephemeral via response_url; follow_up posts again through the same webhook
- [ ] open_modal called promptly after a button interaction opens the modal via views.open; submitting yields a MODAL_SUBMIT interaction with flattened values; waiting past the trigger window raises InteractionExpired
- [ ] send_ephemeral: chat.postEphemeral outside any interaction context (true native path); with the actor not in the channel falls back to a DM; with DMs unreachable raises DeliveryFailed and posts NOTHING publicly
- [ ] fetch_history cursor pagination on a channel with >200 messages returns the full requested range in chronological order (no one-page truncation); fetch_message of a deleted ts raises ChatError (never a neighbor message)
- [ ] add_reaction / remove_reaction / fetch_reactions round-trip (name form without colons; already_reacted is a no-op)
- [ ] upload_attachment into a thread ref lands IN the thread (thread_ts propagated); download_attachment retrieves the bytes through url_private with the bearer token; oversize rejected before any network call
- [ ] subscribe() delivers MESSAGE_CREATED / APP_MENTION (no double-publish for one mention) / REACTION_ADDED / FILE_UPLOADED / INTERACTION_RECEIVED live; a second concurrent subscriber receives the same events independently
- [ ] get_permalink for a message opens correctly in the Slack client; conversation-level app_redirect link opens the channel
