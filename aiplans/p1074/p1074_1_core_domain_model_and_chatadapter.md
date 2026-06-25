---
Task: t1074_1_core_domain_model_and_chatadapter.md
Parent Task: aitasks/t1074_chat_adapter_abstraction_layer.md
Sibling Tasks: aitasks/t1074/t1074_2_discord_adapter.md, aitasks/t1074/t1074_3_slack_adapter.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
---

# Plan: t1074_1 — core domain model + ChatAdapter + Mock (dependency-free)

> Parent decomposition + full contract rationale (incl. the reviewed design
> concerns #1–#7 and four follow-up concerns): `aiplans/p1074_chat_adapter_abstraction_layer.md`.
> Read it first — this plan executes its core-child slice.

## Goal

Create `.aitask-scripts/chat/`, a self-contained, **dependency-free**, asyncio
Python package that freezes the complete platform-agnostic chat contract the two
adapter children implement. No aitasks imports anywhere in the package.

## Steps

1. **Package scaffold.** Create `.aitask-scripts/chat/__init__.py` exporting the
   public API (model types, `ChatAdapter`, errors, `MockChatAdapter`,
   interaction + capability types). The `__init__` must import only from within
   `chat/` and the stdlib — no `monitor`, `lib`, `aitask_*`, or any framework module.

2. **`model.py`** (pure dataclasses/enums, `from __future__ import annotations`):
   `Workspace`, `ConversationKind` (CHANNEL/THREAD/DIRECT/PRIVATE/TEMPORARY),
   `Conversation`, `ConversationRef` (carries `provider`, `workspace_id`,
   `conversation_id`, optional `thread_id`, `metadata`; implement `to_dict`/`from_dict`
   for the round-trip), `Message`, `MessageRef`, `User`, `ActorType`
   (USER/BOT/SYSTEM), `Actor` (`is_bot`), `Role` (`id`, `name`, `kind`), `IdentityClaims`
   (`roles: list[Role]`, `is_workspace_admin`, `is_owner`, `is_channel_member`,
   `metadata`), `Attachment`, `Mention`, `Reaction`, `EventType` (the 14 members
   incl. INTERACTION_RECEIVED + UNKNOWN), `Event` (`type`, `actor`, `conversation`,
   `payload`, `metadata`), `Permission`. Every entity has `metadata: dict`.

3. **`errors.py`:** `ChatError(Exception)` base; subclasses `ConversationNotFound`,
   `PermissionDenied`, `RateLimited`, `AttachmentTooLarge`, `UserNotFound`,
   `DeliveryFailed`, `InteractionExpired`.

4. **`interactions.py`:** outbound `Button`, `SelectMenu`, `ActionRow`,
   `Modal`/`Form` (with `fields`), `SlashCommand` (registration spec); inbound
   `InteractionType` (BUTTON/SELECT/MODAL_SUBMIT/COMMAND) + `Interaction`
   (`type`, `actor: Actor`, `conversation`, `message: MessageRef | None`,
   `values: dict`, `metadata`; an internal `_acked` flag the adapter/Mock sets).

5. **`capabilities.py`:** `Capabilities` dataclass with the documented bool flags +
   `max_message_length: int`, `max_attachment_bytes: int`.

6. **`adapter.py`:** `ChatAdapter(abc.ABC)` with all async methods from the parent
   plan's adapter.py row. Each method `@abstractmethod` with a docstring stating the
   contract (esp. thread anchoring, auto-defer/ack, private-only ephemeral,
   subscription recoverability). `subscribe` typed as `AsyncIterator[Event]`.

7. **`mock.py`:** `MockChatAdapter(ChatAdapter)` — in-memory dict stores for
   workspaces/conversations/messages/reactions/users/claims; an `asyncio.Queue`
   driving `subscribe`. Implements the **entire** ABC + the four contract semantics:
   - Thread create requires `parent`; THREAD ref round-trips; `fetch_history` works
     on a reconstructed ref. Standalone-thread create honors a configurable
     `supports_standalone_threads` (default mimics Discord=True; expose a knob so
     tests can assert the Slack=raise path).
   - Injected interactions arrive **pre-acked** (`_acked=True`); `ack` idempotent;
     `respond`/`follow_up` succeed until a test-controllable "window closed" flag →
     `InteractionExpired`.
   - `send_ephemeral`: native (configurable) → DM → raise `DeliveryFailed`; never
     records a public message on the fallback-exhausted path; returns the path used.
   - `subscribe(conversations=…)` filters; `fetch_reactions` returns current set;
     interactions are not replayed after a simulated disconnect (document + test).
   - Provide small test-helper injectors (e.g. `inject_message`, `inject_interaction`,
     `inject_reaction`, `set_window_closed`) so the bash tests drive deterministic flows.

8. **Tests** (`tests/test_chat_*.sh`; each sources `lib/python_resolve.sh`,
   `PYTHON="$(require_ait_python)"`, runs an inline python heredoc with
   `sys.path.insert(0, root/".aitask-scripts")`; assert PASS/FAIL, exit nonzero on fail):
   - `test_chat_model.sh` — construct each entity; `ConversationRef.to_dict/from_dict`
     round-trip incl. THREAD; every `EventType`/`ConversationKind` member present.
   - `test_chat_mock.sh` — full lifecycle + the four contract semantics + every error.
   - `test_chat_no_aitasks_import.sh` — `import chat` then assert no module whose name
     starts with a framework prefix (e.g. `monitor`, `applink`, `aitask`) and nothing
     from `.aitask-scripts/lib` got imported (inspect `sys.modules`).

## Verification

```bash
bash tests/test_chat_model.sh && \
bash tests/test_chat_mock.sh && \
bash tests/test_chat_no_aitasks_import.sh
```
All PASS on the stock venv with **no** new deps. Run
`shellcheck .aitask-scripts/chat/*.py` is N/A (Python); instead ensure the package
imports cleanly: `~/.aitask/venv/bin/python -c "import sys; sys.path.insert(0,'.aitask-scripts'); import chat; print('ok')"`.

## Notes for sibling tasks

- The `ChatAdapter` ABC is the **frozen contract** — adapter children must not add
  public methods; platform extras go in `metadata`. If a genuine gap is found, amend
  the ABC here (and the Mock) rather than diverging in an adapter.
- The pure-normalization-function pattern (duck-typed input → domain) is established
  here via the Mock's injectors; adapters mirror it for stub-based testing.

## Reference: Step 9 (Post-Implementation)
Standard archival/merge per `task-workflow` Step 9 when this child completes.
