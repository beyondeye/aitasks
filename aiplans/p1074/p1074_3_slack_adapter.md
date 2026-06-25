---
Task: t1074_3_slack_adapter.md
Parent Task: aitasks/t1074_chat_adapter_abstraction_layer.md
Sibling Tasks: aitasks/t1074/t1074_1_core_domain_model_and_chatadapter.md, aitasks/t1074/t1074_2_discord_adapter.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
---

# Plan: t1074_3 — Slack adapter (slack_bolt + slack_sdk, Socket Mode)

> Depends on t1074_2 (Discord lands first and validates the interface + the
> `--with-chat` scaffold). Parent decomposition:
> `aiplans/p1074_chat_adapter_abstraction_layer.md`. Read the archived Discord
> plan (`aiplans/archived/p1074/p1074_2_*.md`) and `chat/discord_adapter.py` to
> mirror structure and pick up gotchas.

## Goal

Implement `SlackAdapter(ChatAdapter)` against `slack_bolt`/`slack_sdk` in Socket
Mode, appending the Slack SDKs to the existing opt-in `--with-chat` tier. Pure
platform↔domain translation; no aitasks concepts.

## Steps

1. **Install-flow append** (`.aitask-scripts/aitask_setup.sh`): append
   `'slack-bolt>=1,<2'` and `'slack-sdk>=3,<4'` to `AIT_PIP_SPECS_CHAT`, and
   `slack_bolt`, `slack_sdk` to `AIT_IMPORTS_CHAT`. The `--with-chat` flag + install
   block already exist (t1074_2). `shellcheck` must stay clean.

2. **Pure normalization functions** in `slack_adapter.py` (duck-typed inputs, no
   slack import to call): Slack event/payload → domain `Message`/`Event`/`User`/
   `Interaction`; `usergroups + admin/owner flags → IdentityClaims`
   (`Role.kind="slack_usergroup"`); Block Kit components ↔ domain; `views.open`
   payload ↔ `Modal`. Conversation mapping: channel/group/im/thread → `Conversation`
   + `ConversationRef` (`provider="slack"`, `thread_id=thread_ts` for threads).

3. **`SlackAdapter(ChatAdapter)`** — lazy `import slack_bolt`/`slack_sdk`; Socket
   Mode app (`xoxb-` + `xapp-`). Implement every ABC method. Contract semantics:
   - **Threads:** message-anchored only (`reply_to`/`thread_ts`);
     `supports_standalone_threads=False` → channel-rooted thread create raises
     `PermissionDenied`.
   - **Interactions:** ack within 3 s on receipt **before** yielding; `respond`/
     `follow_up` via `response_url`; past-window → `InteractionExpired`; `ack` idempotent.
   - **Ephemeral:** `chat.postEphemeral` (per-user); fallback DM → `DeliveryFailed`;
     never public.
   - **Discovery:** `get_permalink` via `chat.getPermalink`; `fetch_conversation`
     raises `ConversationNotFound` when gone; `search.messages` →
     `supports_message_search=True`.
   - **Reconciliation:** `fetch_reactions` via `reactions.get`.
   - **Events:** `message_deleted`, `reaction_removed`, `member_left_channel`,
     message create/edit, `app_mention`, `file_shared` → `EventType`. Ensure the
     commonly-missed scopes/events are documented in code (channels:history,
     groups:history, message.channels, app_mention, files:read).
   - **Capabilities:** buttons/selects/modals/slash=True, ephemeral=True, search=True,
     standalone_threads=False, Slack `max_message_length`/`max_attachment_bytes`.

4. **Tests** (`tests/test_chat_slack.sh`): pure functions against `SimpleNamespace`
   stubs — no slack import; graceful SKIP if a future live path needs the libs.

## Verification

```bash
bash tests/test_chat_slack.sh                          # PASS on stock venv (stub-based)
shellcheck .aitask-scripts/aitask_setup.sh
ait setup --with-chat && ~/.aitask/venv/bin/python -c "import slack_bolt, slack_sdk; print('ok')"
```

## Final Implementation Notes
_(to be filled at implementation time.)_

## Reference: Step 9 (Post-Implementation)
This is the last child. When it completes and `children_to_implement` is empty,
parent t1074 auto-archives per `task-workflow` Step 9.
