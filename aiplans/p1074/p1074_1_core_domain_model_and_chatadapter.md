---
Task: t1074_1_core_domain_model_and_chatadapter.md
Parent Task: aitasks/t1074_chat_adapter_abstraction_layer.md
Sibling Tasks: aitasks/t1074/t1074_2_discord_adapter.md, aitasks/t1074/t1074_3_slack_adapter.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/fable5 @ 2026-07-02 15:11
---

# Plan: t1074_1 — core domain model + ChatAdapter + Mock (dependency-free)

> Parent decomposition + full contract rationale (incl. the reviewed design
> concerns #1–#7 and four follow-up concerns): `aiplans/p1074_chat_adapter_abstraction_layer.md`.
> Read it first — this plan executes its core-child slice.

## Goal

Create `.aitask-scripts/chat/`, a self-contained, **dependency-free**, asyncio
Python package that freezes the complete platform-agnostic chat contract the two
adapter children implement. No aitasks imports anywhere in the package.

## Frozen surface specification

This child freezes the contract, so the public schemas and signatures are pinned
**here**, not improvised at implementation time. Every entity additionally
carries `metadata: dict = field(default_factory=dict)` (platform extras; last
field). All dataclasses use `from __future__ import annotations`.

**Abstraction-documentation rule (binding):** every public class/enum and every
`ChatAdapter` method carries a docstring with three parts:
1. **What it abstracts** — the concrete platform concept(s) it normalizes, named
   on both sides (e.g. `ConversationRef`: "wraps Slack `channel_id`+`thread_ts` /
   Discord `guild_id`+`channel_id`/`thread_id`"; `send_ephemeral`: "Slack
   `chat.postEphemeral` / Discord interaction-response ephemeral flag";
   `IdentityClaims`: "Slack usergroups+admin/owner flags / Discord guild roles —
   deliberately NOT coerced into a common role model").
2. **Purpose** — why the abstraction exists / what higher layers rely on it for
   (e.g. `ConversationRef`: "opaque reconnect token — enables thread recovery
   after restart without the runtime knowing the platform").
3. **Contract** — behavior guarantees and raise conditions (already required for
   ABC methods; for data types: equality/round-trip/metadata semantics).
Each module also gets a module docstring stating its slice of the layer and the
design-doc principle it serves ("abstract concepts, not APIs"). Enum members
with non-obvious platform mappings get inline comments (e.g. `TEMPORARY`,
`UNKNOWN`). `test_chat_contract.sh` extends its docstring check to every
public class in `__all__`, not just ABC methods.

**Mutable-default rule:** the `= []` / `= {}` defaults in the tables below are
*public default behavior* shorthand — the implementation MUST declare every
list/dict default as `field(default_factory=list)` / `field(default_factory=dict)`
(literal mutable defaults raise `ValueError` in dataclasses, and shared-state
workarounds are contract violations). `test_chat_contract.sh` asserts that two
default-constructed instances do not share list/dict field objects.

### model.py — dataclass field schemas

| Type | Fields (in order) |
|------|-------------------|
| `Workspace` | `id: str`, `name: str`, `provider: str` |
| `ConversationKind` (Enum) | CHANNEL, THREAD, DIRECT, PRIVATE, TEMPORARY |
| `ConversationRef` | `provider: str`, `workspace_id: str`, `conversation_id: str`, `thread_id: str \| None = None`; `metadata` excluded from equality (`field(compare=False)`). Methods: `to_dict() -> dict`, classmethod `from_dict(d: dict) -> ConversationRef` (round-trip incl. `thread_id` + `metadata`) |
| `Conversation` | `ref: ConversationRef`, `kind: ConversationKind`, `name: str \| None = None`, `topic: str \| None = None`, `is_archived: bool = False` |
| `MessageRef` | `conversation: ConversationRef`, `message_id: str`; `metadata` compare-excluded |
| `Message` | `ref: MessageRef`, `author: Actor`, `text: str`, `timestamp: float` (epoch s), `attachments: list[Attachment] = []`, `mentions: list[Mention] = []`, `reactions: list[Reaction] = []`, `reply_to: MessageRef \| None = None`, `edited: bool = False` |
| `User` | `id: str`, `display_name: str`, `username: str \| None = None`, `email: str \| None = None`, `avatar_url: str \| None = None`, `is_bot: bool = False` |
| `ActorType` (Enum) | USER, BOT, SYSTEM |
| `Actor` | `id: str`, `type: ActorType`, `display_name: str \| None = None`, `is_self: bool = False`; property `is_bot` → `type is not ActorType.USER` |
| `Role` | `id: str`, `name: str`, `kind: str` (`discord_role` \| `slack_usergroup`) |
| `IdentityClaims` | `user_id: str`, `roles: list[Role] = []`, `is_workspace_admin: bool = False`, `is_owner: bool = False`, `is_channel_member: bool = False` |
| `Attachment` | `id: str`, `filename: str`, `mime_type: str \| None = None`, `size: int \| None = None`, `url: str \| None = None`, `uploader: Actor \| None = None` |
| `Mention` | `user_id: str`, `display_name: str \| None = None` |
| `Reaction` | `emoji: str`, `count: int = 0`, `user_ids: list[str] = []` |
| `EventType` (Enum) | MESSAGE_CREATED, MESSAGE_EDITED, MESSAGE_DELETED, REACTION_ADDED, REACTION_REMOVED, APP_MENTION, THREAD_CREATED, THREAD_DELETED, FILE_UPLOADED, USER_JOINED, USER_LEFT, CHANNEL_CREATED, INTERACTION_RECEIVED, UNKNOWN |
| `Event` | `id: str`, `type: EventType`, `timestamp: float`, `actor: Actor \| None = None`, `conversation: ConversationRef \| None = None`, `payload: dict = {}` |
| `Permission` | `name: str` (kept minimal at this layer; platform-honest, no pretend-common model) |
| `EphemeralPath` (Enum) | NATIVE, DM |
| `EphemeralReceipt` | `path: EphemeralPath`, `message: Message \| None = None` |

**`Event.payload` conventions (documented in `Event`'s docstring, enforced by Mock):**
MESSAGE_CREATED/MESSAGE_EDITED/APP_MENTION → `{"message": Message}`;
MESSAGE_DELETED → `{"message_ref": MessageRef}`;
REACTION_ADDED/REACTION_REMOVED → `{"message_ref": MessageRef, "emoji": str}` (actor on `Event.actor`);
THREAD_CREATED/CHANNEL_CREATED → `{"conversation": Conversation}`;
THREAD_DELETED → `{"conversation_ref": ConversationRef}`;
FILE_UPLOADED → `{"attachment": Attachment, "message_ref": MessageRef | None}`;
USER_JOINED/USER_LEFT → `{"user": User}`;
INTERACTION_RECEIVED → `{"interaction": Interaction}`;
UNKNOWN → `{"raw": <provider payload>}`.

### interactions.py — schemas

| Type | Fields |
|------|--------|
| `Button` | `custom_id: str`, `label: str`, `style: str = "primary"`, `disabled: bool = False` |
| `SelectMenu` | `custom_id: str`, `options: list[SelectOption]`, `placeholder: str \| None = None`, `min_values: int = 1`, `max_values: int = 1` |
| `SelectOption` | `value: str`, `label: str`, `description: str \| None = None` |
| `ActionRow` | `components: list[Button \| SelectMenu]` |
| `FormField` | `custom_id: str`, `label: str`, `kind: str = "text"`, `required: bool = True`, `placeholder: str \| None = None` |
| `Modal` (alias `Form = Modal`) | `custom_id: str`, `title: str`, `fields: list[FormField]` |
| `SlashCommand` | `name: str`, `description: str`, `options: list[CommandOption] = []` |
| `CommandOption` | `name: str`, `description: str`, `kind: str = "string"`, `required: bool = False` |
| `InteractionType` (Enum) | BUTTON, SELECT, MODAL_SUBMIT, COMMAND |
| `Interaction` | `id: str`, `type: InteractionType`, `actor: Actor`, `conversation: ConversationRef`, `message: MessageRef \| None = None`, `custom_id: str \| None = None`, `values: dict = {}`; internal `_acked: bool = False` (set by adapter before yielding) |

### capabilities.py

`Capabilities` dataclass: `supports_buttons`, `supports_selects`, `supports_modals`,
`supports_slash_commands`, `supports_reactions`, `supports_files`,
`supports_ephemeral`, `supports_dm`, `supports_voice`, `supports_editing`,
`supports_thread_creation`, `supports_standalone_threads`,
`supports_message_search` (all `bool`), `max_message_length: int`,
`max_attachment_bytes: int`.

### adapter.py — `ChatAdapter(abc.ABC)` pinned signatures

All `@abstractmethod`; every method carries a docstring stating its contract and
raise behavior. Async unless noted.

```python
# Messaging
async def send_message(self, conversation: ConversationRef, text: str, *,
    attachments: list[Attachment] | None = None,
    components: list[ActionRow] | None = None,
    reply_to: MessageRef | None = None) -> Message
async def edit_message(self, message: MessageRef, text: str, *,
    components: list[ActionRow] | None = None) -> Message
async def delete_message(self, message: MessageRef) -> None
async def fetch_message(self, message: MessageRef) -> Message
async def send_ephemeral(self, conversation: ConversationRef, actor: Actor, text: str, *,
    components: list[ActionRow] | None = None) -> EphemeralReceipt
    # native → DM → raises DeliveryFailed; NEVER posts publicly

# Conversations / threads
async def create_conversation(self, kind: ConversationKind, *,
    parent: MessageRef | ConversationRef | None = None,
    name: str | None = None,
    participants: list[str] | None = None) -> Conversation
    # kind=THREAD requires parent (MessageRef both platforms; channel
    # ConversationRef = standalone thread, gated by supports_standalone_threads
    # → PermissionDenied when unsupported). kind=DIRECT requires participants.
async def archive_conversation(self, conversation: ConversationRef) -> None
async def fetch_history(self, conversation: ConversationRef, *,
    before: MessageRef | None = None, after: MessageRef | None = None,
    limit: int = 100) -> list[Message]
    # chronological order; ≤ limit; page backward via before=, forward via
    # after=; empty list when exhausted. Adapter owns cursoring.
async def fetch_participants(self, conversation: ConversationRef) -> list[User]

# Discovery
async def fetch_conversation(self, ref: ConversationRef) -> Conversation   # raises ConversationNotFound
async def list_conversations(self, *, kinds: list[ConversationKind] | None = None) -> list[Conversation]
async def get_permalink(self, ref: ConversationRef | MessageRef) -> str

# Identity
async def fetch_user(self, user_id: str) -> User                           # raises UserNotFound
async def fetch_identity_claims(self, conversation: ConversationRef, user_id: str) -> IdentityClaims

# Reconciliation
async def fetch_reactions(self, message: MessageRef) -> list[Reaction]     # current set, for diff-recovery

# Files / reactions
async def upload_attachment(self, conversation: ConversationRef, filename: str,
    content: bytes, *, mime_type: str | None = None) -> Attachment         # raises AttachmentTooLarge
async def download_attachment(self, attachment: Attachment) -> bytes
async def add_reaction(self, message: MessageRef, emoji: str) -> None
async def remove_reaction(self, message: MessageRef, emoji: str) -> None

# Interactions
async def register_commands(self, specs: list[SlashCommand]) -> None
async def ack(self, interaction: Interaction) -> None                      # idempotent no-op post-auto-defer
async def respond(self, interaction: Interaction, text: str, *,
    components: list[ActionRow] | None = None,
    ephemeral: bool = False) -> Message | None                             # raises InteractionExpired
async def follow_up(self, interaction: Interaction, text: str, *,
    components: list[ActionRow] | None = None,
    ephemeral: bool = False) -> Message | None                             # raises InteractionExpired
async def open_modal(self, interaction: Interaction, modal: Modal) -> None # raises InteractionExpired

# Events — async GENERATOR (inspect.isasyncgenfunction must hold)
async def subscribe(self, *, conversations: list[ConversationRef] | None = None,
    since: float | None = None) -> AsyncIterator[Event]

# Capabilities — sync (static data)
def capabilities(self) -> Capabilities
```

`respond`/`follow_up` return the posted `Message`, or `None` when the platform
gives no message handle back for an ephemeral response.

### `__init__.py` — `__all__` (exact, contract-tested)

All names in the three schema tables above plus `ChatAdapter`,
`MockChatAdapter`, and the 7 error classes + `ChatError`. No other exports; no
imports from outside `chat/` + stdlib.

## Steps

1. **Package scaffold.** `.aitask-scripts/chat/__init__.py` with the pinned
   `__all__` re-exported from the submodules.

2. **`model.py`** per the field-schema table above (pure dataclasses/enums).

3. **`errors.py`:** `ChatError(Exception)` base; subclasses `ConversationNotFound`,
   `PermissionDenied`, `RateLimited`, `AttachmentTooLarge`, `UserNotFound`,
   `DeliveryFailed`, `InteractionExpired`.

4. **`interactions.py`** per its schema table above.

5. **`capabilities.py`** per its spec above.

6. **`adapter.py`:** `ChatAdapter(abc.ABC)` with the **exact pinned signatures**
   above, each with a contract docstring (thread anchoring, auto-defer/ack,
   private-only ephemeral, subscription recoverability, pagination semantics).

7. **`mock.py`:** `MockChatAdapter(ChatAdapter)` — in-memory dict stores for
   workspaces/conversations/messages/reactions/users/claims. Implements the
   **entire** ABC + the four contract semantics:
   - **Broadcast subscription (per-subscriber queues — NOT one shared queue):**
     each `subscribe()` call registers its own `_Subscriber` (own
     `asyncio.Queue` + optional conversation-filter set) in
     `self._subscribers`; the generator yields from its queue and unregisters
     in `finally`. `_emit(event)` fans out: for every active subscriber whose
     filter matches, `queue.put_nowait(event)`. Multiple concurrent
     subscribers each receive every matching event (no competition, no
     cross-subscriber event theft) — at-least-once per active subscription
     while connected. `simulate_disconnect()` pushes a sentinel ending all
     active subscriber streams; events emitted while a subscriber is not
     registered are simply not delivered to it (no buffering, no replay) —
     matching the documented no-replay-across-disconnect contract.
   - Thread create requires `parent`; THREAD ref round-trips; `fetch_history`
     works on a reconstructed ref. Standalone-thread create honors a
     configurable `supports_standalone_threads` (default True = Discord-like;
     knob lets tests assert the Slack raise path).
   - Injected interactions arrive **pre-acked** (`_acked=True`); `ack`
     idempotent. **Expiry is per-interaction, keyed by `Interaction.id`:** the
     Mock keeps `self._closed_windows: set[str]`;
     `set_window_closed(interaction_id)` adds one id (a global flag would hide
     concurrent-interaction bugs). `respond`/`follow_up`/`open_modal` raise
     `InteractionExpired` iff the interaction's id is in the set — test that
     with two live interactions, closing one leaves the other responsive.
   - `send_ephemeral`: native (configurable) → DM → raise `DeliveryFailed`;
     never records a public message on the fallback-exhausted path; returns
     `EphemeralReceipt` with the path used.
   - `fetch_reactions` returns the current set; interactions are not replayed
     after a simulated disconnect (document + test).
   - Test-helper injectors: `inject_message`, `inject_interaction`,
     `inject_reaction`, `set_window_closed(interaction_id)`,
     `simulate_disconnect` — the deterministic seams the bash tests drive.

8. **Tests** (each sources `lib/python_resolve.sh`,
   `PYTHON="$(require_ait_python)"`, inline python heredoc with
   `sys.path.insert(0, root/".aitask-scripts")`; per `tests/test_applink_router.sh`
   idiom; exit nonzero on fail):
   - `test_chat_model.sh` — construct each entity; `ConversationRef.to_dict/from_dict`
     round-trip incl. THREAD; every `EventType`/`ConversationKind` member present.
   - `test_chat_mock.sh` — full lifecycle + the four contract semantics + every
     error; **subscription broadcast**: two concurrent subscribers both receive
     the same event; a conversation-filtered subscriber does not steal events
     from an unfiltered one; no replay after `simulate_disconnect`.
   - `test_chat_contract.sh` — **contract introspection guard** (drift
     protection for the frozen surface): `chat.__all__` equals the pinned
     export list exactly; `ChatAdapter.__abstractmethods__` equals the pinned
     method-name set exactly; `inspect.signature(...)` of every ABC method
     matches the pinned parameter names/kinds/defaults;
     `inspect.iscoroutinefunction` holds for the async methods,
     `inspect.isasyncgenfunction` for `subscribe`, plain function for
     `capabilities`; every abstract method AND every public class in
     `__all__` has a non-empty docstring (abstraction-documentation rule);
     `dataclasses.fields` names of the public dataclasses match the schema
     tables above; two default-constructed instances of each dataclass with
     list/dict defaults do not share field objects (default_factory guard).
   - `test_chat_no_aitasks_import.sh` — `import chat` then assert no module whose
     name starts with a framework prefix (`monitor`, `applink`, `aitask`, `board`)
     and nothing from `.aitask-scripts/lib` got imported (inspect `sys.modules`).

9. **Task AC update (explicit, not silent):** the task file's Verification
   section names three tests; this plan adds `test_chat_contract.sh` as a
   fourth. At Step 7 (post-approval, before implementing), update
   `aitasks/t1074/t1074_1_core_domain_model_and_chatadapter.md`'s Verification
   command to include it (commit via `./ait git`).

## Verification

```bash
bash tests/test_chat_model.sh && \
bash tests/test_chat_mock.sh && \
bash tests/test_chat_contract.sh && \
bash tests/test_chat_no_aitasks_import.sh
```
All PASS on the stock venv with **no** new deps. Also ensure the package
imports cleanly: `~/.aitask/venv/bin/python -c "import sys; sys.path.insert(0,'.aitask-scripts'); import chat; print('ok')"`.

## Plan verification notes (2026-07-02)

Re-verified against the current codebase (main HEAD):
- `.aitask-scripts/chat/` does not exist; no `tests/test_chat_*` collisions; no
  `chat` module shadowing in the venv (Python 3.14.5).
- Reference patterns unchanged: `tests/test_applink_router.sh` wrapper idiom
  (source `python_resolve.sh` → `require_ait_python` → dep SKIP → heredoc with
  `sys.path.insert`), `monitor/monitor_core.py` dataclass/enum style,
  `applink/router.py` pure-seam style. Recent applink commits (t1045/t1057/t1092)
  did not affect the cited patterns.
- Review hardening (this verification pass): pinned explicit field schemas for
  all public dataclasses, pinned the full ABC signature set (params, returns,
  raise behavior, pagination semantics), replaced the single-queue mock
  subscription with per-subscriber broadcast fan-out, and added
  `test_chat_contract.sh` (introspection guard against surface drift) with an
  explicit task-AC update.

## Risk

### Code-health risk: low
- None identified. All-new, self-contained package; no edits to existing files;
  zero third-party deps; the no-aitasks-import guard test structurally prevents
  accidental coupling.

### Goal-achievement risk: medium
- The frozen contract's real fitness test — the later aitasks integration and
  real Slack/Discord API fidelity — cannot be proven inside this child; the
  surface is validated only via `MockChatAdapter` · severity: medium ·
  → mitigation: decided at parent level (p1074 `## Risk`): none gated as
  before/after — the adapter children (t1074_2/t1074_3) exercise the contract
  next, the ABC-amendment path is documented in "Notes for sibling tasks", and
  the deferred live-integration follow-up validates real-API fidelity. The
  contract-introspection test added in this plan further pins the surface so
  drift is caught mechanically, not by adapter-child surprise.

(Mitigations were evaluated and confirmed as "none gated" during the approved
parent planning for this exact decomposition — not re-prompted per child.)

## Notes for sibling tasks

- The `ChatAdapter` ABC is the **frozen contract** — adapter children must not add
  public methods; platform extras go in `metadata`. If a genuine gap is found, amend
  the ABC here (and the Mock **and `test_chat_contract.sh`'s pinned tables**)
  rather than diverging in an adapter.
- The pure-normalization-function pattern (duck-typed input → domain) is established
  here via the Mock's injectors; adapters mirror it for stub-based testing.

## Reference: Step 9 (Post-Implementation)
Standard archival/merge per `task-workflow` Step 9 when this child completes.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned — new dependency-free
  package `.aitask-scripts/chat/` (`__init__.py` with exact 41-name `__all__`,
  `model.py` 16 dataclasses + 4 enums, `errors.py` `ChatError` + 7 subclasses,
  `interactions.py` 11 types incl. pre-acked `Interaction`, `capabilities.py`,
  `adapter.py` `ChatAdapter` ABC with 26 abstract methods at the pinned
  signatures, `mock.py` full `MockChatAdapter`), plus the four bash test
  wrappers (`test_chat_model.sh` 17 checks, `test_chat_mock.sh` 57,
  `test_chat_contract.sh` 146, `test_chat_no_aitasks_import.sh` 4 — 224 total,
  all PASS on the stock venv, zero new deps). The task file's Verification AC
  was explicitly updated (committed pre-implementation) to include the fourth
  test.
- **Deviations from plan:** None material. Two small additions beyond the
  pinned seams, both documented in-code: mock helpers `register_user` /
  `set_identity_claims` / `add_participant` (needed to populate the simulated
  platform directory; allowlisted in the contract test's
  `ALLOWED_MOCK_EXTRAS`), and `inject_message(..., mention_bot=True)` to
  exercise APP_MENTION. `Capabilities` carries a `metadata` field like the
  model entities (pinned in the contract test).
- **Issues encountered:** None significant. `subscribe` as an abstract async
  generator needs the `if False: yield` idiom in the ABC body so
  `inspect.isasyncgenfunction` holds on both ABC and Mock (asserted by the
  contract test). Shellcheck reports info-level SC1091 on the test wrappers'
  `source` line — identical to the pre-existing `test_applink_router.sh`
  pattern (project lint target is `.aitask-scripts/aitask_*.sh`).
- **Key decisions:** deterministic logical clock (ticks of 1.0) + id counter
  instead of wall clock for reproducible event order; per-subscriber broadcast
  queues with `_DISCONNECT` sentinel; per-interaction expiry keyed by
  `Interaction.id`; ephemeral fallback records native ephemerals in a
  test-inspectable list (never the public store); mock `fetch_message` of a
  missing message raises base `ChatError` (taxonomy has no MessageNotFound —
  documented in the ABC docstring); missing required args (THREAD without
  parent, DIRECT without participants) raise `ValueError` (caller bug, not
  platform failure); the mock's public surface is itself contract-tested
  (ABC methods + allowlisted seams only).
- **Upstream defects identified:** None
- **Notes for sibling tasks:** see the "Notes for sibling tasks" section above
  (frozen-ABC amendment path — amend ABC + Mock + `test_chat_contract.sh`
  pinned tables together; pure-normalization pattern via Mock injectors). For
  the adapter children specifically: implement the exact pinned signatures
  (the contract test will catch drift); yield interactions only after
  auto-defer/ack (`_acked=True`); honor the `Event.payload` conventions
  documented on `Event`; map platform errors onto the 7-subclass taxonomy
  (no MessageNotFound — use `ChatError`); return `EphemeralReceipt` naming
  the private path; `respond`/`follow_up` return `None` when the platform
  yields no re-addressable handle.
