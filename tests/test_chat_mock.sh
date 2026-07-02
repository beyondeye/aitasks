#!/usr/bin/env bash
# test_chat_mock.sh — MockChatAdapter lifecycle + contract-semantics tests (t1074_1).
#
# Exercises the full frozen contract against the in-memory mock: messaging,
# threads (incl. recovery from a round-tripped ref), history pagination,
# interactions (pre-acked + per-interaction expiry), ephemeral private-only
# fallback, identity/claims, discovery, files, reactions, and the broadcast
# subscription / no-replay semantics. Dependency-free (stdlib only).
# Run: bash tests/test_chat_mock.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"

PYTHON="$(require_ait_python)"

"$PYTHON" - "$PROJECT_DIR" <<'PYEOF'
import asyncio
import sys
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".aitask-scripts"))

from chat import (
    Actor, ActorType, AttachmentTooLarge, Button, ActionRow, ChatError,
    ConversationKind, ConversationNotFound, ConversationRef, DeliveryFailed,
    EphemeralPath, EventType, IdentityClaims, Interaction, InteractionType,
    InteractionExpired, MockChatAdapter, PermissionDenied, RateLimited, Role,
    SlashCommand, User, UserNotFound,
)

PASS = 0
def check(label, cond):
    global PASS
    assert cond, f"FAIL: {label}"
    PASS += 1
    print(f"ok - {label}")


async def collect(aiter, n, timeout=1.0):
    """Collect up to n events from an async iterator with a timeout."""
    out = []
    for _ in range(n):
        out.append(await asyncio.wait_for(anext(aiter), timeout))
    return out


async def main():
    mock = MockChatAdapter()
    user = User(id="U1", display_name="dev")
    actor = Actor(id="U1", type=ActorType.USER, display_name="dev")
    mock.register_user(user)

    # --- messaging lifecycle ---------------------------------------------
    chan = await mock.create_conversation(ConversationKind.CHANNEL, name="general")
    msg = await mock.send_message(chan.ref, "hello")
    check("send_message returns Message", msg.text == "hello")
    check("author is self bot", msg.author.is_self and msg.author.is_bot)

    edited = await mock.edit_message(msg.ref, "hello v2")
    check("edit_message updates text + edited flag", edited.text == "hello v2" and edited.edited)

    fetched = await mock.fetch_message(msg.ref)
    check("fetch_message returns current state", fetched.text == "hello v2")

    await mock.delete_message(msg.ref)
    try:
        await mock.fetch_message(msg.ref)
        check("fetch of deleted message raises", False)
    except ChatError:
        check("fetch of deleted message raises", True)

    # --- history pagination -------------------------------------------------
    sent = [await mock.send_message(chan.ref, f"n{i}") for i in range(10)]
    hist = await mock.fetch_history(chan.ref, limit=4)
    check("history returns most recent, chronological",
          [m.text for m in hist] == ["n6", "n7", "n8", "n9"])
    back = await mock.fetch_history(chan.ref, before=sent[5].ref, limit=3)
    check("history pages backward via before=",
          [m.text for m in back] == ["n2", "n3", "n4"])
    fwd = await mock.fetch_history(chan.ref, after=sent[5].ref, limit=3)
    check("history pages forward via after=",
          [m.text for m in fwd] == ["n6", "n7", "n8"])
    check("forward paging exhausts to empty list",
          await mock.fetch_history(chan.ref, after=sent[9].ref, limit=5) == [])

    # --- threads: create / reply / recovery ---------------------------------
    anchor = sent[0]
    thread = await mock.create_conversation(ConversationKind.THREAD, parent=anchor.ref, name="disc")
    check("message-anchored thread created", thread.kind is ConversationKind.THREAD
          and thread.ref.thread_id is not None
          and thread.ref.conversation_id == chan.ref.conversation_id)
    treply = await mock.send_message(thread.ref, "in-thread")
    check("reply lands in thread", (await mock.fetch_history(thread.ref))[0].text == "in-thread")

    # Recovery: serialize the THREAD ref, reconstruct, use it cold.
    recovered = ConversationRef.from_dict(thread.ref.to_dict())
    check("recovered thread ref fetches history",
          [m.text for m in await mock.fetch_history(recovered)] == ["in-thread"])
    check("recovered ref resolves via fetch_conversation",
          (await mock.fetch_conversation(recovered)).ref == thread.ref)

    try:
        await mock.create_conversation(ConversationKind.THREAD)
        check("THREAD without parent raises", False)
    except ValueError:
        check("THREAD without parent raises", True)

    standalone = await mock.create_conversation(ConversationKind.THREAD, parent=chan.ref)
    check("standalone thread allowed when supported (Discord-like)",
          standalone.ref.thread_id is not None)
    slacky = MockChatAdapter(standalone_threads=False)
    schan = await slacky.create_conversation(ConversationKind.CHANNEL, name="s")
    try:
        await slacky.create_conversation(ConversationKind.THREAD, parent=schan.ref)
        check("standalone thread raises when unsupported (Slack-like)", False)
    except PermissionDenied:
        check("standalone thread raises when unsupported (Slack-like)", True)
    check("capability reflects standalone-thread knob",
          mock.capabilities().supports_standalone_threads
          and not slacky.capabilities().supports_standalone_threads)

    # --- discovery -----------------------------------------------------------
    dangling = ConversationRef(provider="mock", workspace_id="W1", conversation_id="NOPE")
    try:
        await mock.fetch_conversation(dangling)
        check("fetch_conversation raises ConversationNotFound", False)
    except ConversationNotFound:
        check("fetch_conversation raises ConversationNotFound", True)
    threads = await mock.list_conversations(kinds=[ConversationKind.THREAD])
    check("list_conversations filters by kind",
          threads and all(c.kind is ConversationKind.THREAD for c in threads))
    link = await mock.get_permalink(treply.ref)
    check("message permalink is human-openable and thread-scoped",
          link.startswith("https://mock.chat/") and thread.ref.thread_id in link
          and treply.ref.message_id in link)

    # --- identity --------------------------------------------------------------
    check("fetch_user resolves", (await mock.fetch_user("U1")).display_name == "dev")
    try:
        await mock.fetch_user("ghost")
        check("fetch_user raises UserNotFound", False)
    except UserNotFound:
        check("fetch_user raises UserNotFound", True)
    default_claims = await mock.fetch_identity_claims(chan.ref, "U1")
    check("claims default to no privileges",
          not default_claims.roles and not default_claims.is_workspace_admin
          and not default_claims.is_owner and not default_claims.is_channel_member)
    mock.set_identity_claims(chan.ref, IdentityClaims(
        user_id="U1", roles=[Role(id="r1", name="ops", kind="slack_usergroup")],
        is_workspace_admin=True, is_channel_member=True))
    claims = await mock.fetch_identity_claims(chan.ref, "U1")
    check("installed claims returned (role kind + flags)",
          claims.roles[0].kind == "slack_usergroup" and claims.is_workspace_admin
          and claims.is_channel_member and not claims.is_owner)

    # --- files -------------------------------------------------------------------
    att = await mock.upload_attachment(chan.ref, "log.txt", b"payload", mime_type="text/plain")
    check("upload/download round-trips bytes",
          await mock.download_attachment(att) == b"payload" and att.size == 7)
    tiny = MockChatAdapter(max_attachment_bytes=4)
    tchan = await tiny.create_conversation(ConversationKind.CHANNEL, name="t")
    try:
        await tiny.upload_attachment(tchan.ref, "big.bin", b"12345")
        check("oversized upload raises AttachmentTooLarge", False)
    except AttachmentTooLarge:
        check("oversized upload raises AttachmentTooLarge", True)

    # --- reactions + diff reconciliation ------------------------------------------
    target = sent[1]
    await mock.add_reaction(target.ref, "eyes")
    mock.inject_reaction(target.ref, "eyes", actor)
    mock.inject_reaction(target.ref, "tada", actor)
    current = {r.emoji: r for r in await mock.fetch_reactions(target.ref)}
    check("fetch_reactions returns current authoritative set",
          current["eyes"].count == 2 and current["tada"].user_ids == ["U1"])
    await mock.add_reaction(target.ref, "eyes")  # idempotent no-op
    check("re-adding same reaction is a no-op",
          {r.emoji: r.count for r in await mock.fetch_reactions(target.ref)}["eyes"] == 2)
    await mock.remove_reaction(target.ref, "eyes")
    check("remove_reaction removes only the bot's",
          {r.emoji: r.count for r in await mock.fetch_reactions(target.ref)}["eyes"] == 1)

    # --- interactions: pre-acked, respond/follow_up, per-id expiry, modal ------------
    await mock.register_commands([SlashCommand(name="task", description="d")])
    check("register_commands stores specs", mock.registered_commands[0].name == "task")

    sub = mock.subscribe()
    await asyncio.sleep(0)  # let the subscriber register... (generator starts lazily)
    # Async generators start on first anext; prime the stream inside a task.
    stream_task = asyncio.ensure_future(collect(sub, 1))
    await asyncio.sleep(0)
    i1 = mock.inject_interaction(Interaction(
        id="i1", type=InteractionType.BUTTON, actor=actor,
        conversation=chan.ref, message=target.ref, custom_id="approve"))
    (evt,) = await stream_task
    check("interaction surfaces as INTERACTION_RECEIVED event",
          evt.type is EventType.INTERACTION_RECEIVED
          and evt.payload["interaction"] is i1)
    check("yielded interaction is already acked", i1._acked is True)
    await mock.ack(i1)  # idempotent
    check("ack is idempotent", i1._acked is True)

    r1 = await mock.respond(i1, "approved!")
    check("respond posts into source conversation",
          r1 is not None and r1.ref.conversation == chan.ref)
    f1 = await mock.follow_up(i1, "and more")
    check("follow_up works within window", f1 is not None)

    i2 = mock.inject_interaction(Interaction(
        id="i2", type=InteractionType.SELECT, actor=actor,
        conversation=chan.ref, custom_id="pick", values={"values": ["a"]}))
    mock.set_window_closed("i1")
    try:
        await mock.respond(i1, "too late")
        check("respond past window raises InteractionExpired", False)
    except InteractionExpired:
        check("respond past window raises InteractionExpired", True)
    try:
        await mock.follow_up(i1, "too late")
        check("follow_up past window raises InteractionExpired", False)
    except InteractionExpired:
        check("follow_up past window raises InteractionExpired", True)
    check("closing one window leaves other interactions responsive",
          (await mock.respond(i2, "still fine")) is not None)

    from chat import Modal, FormField
    await mock.open_modal(i2, Modal(custom_id="m1", title="T",
                                    fields=[FormField(custom_id="f1", label="F")]))
    check("open_modal records within window", mock.opened_modals[-1][0] is i2)
    mock.set_window_closed("i2")
    try:
        await mock.open_modal(i2, Modal(custom_id="m2", title="T2", fields=[]))
        check("open_modal past window raises InteractionExpired", False)
    except InteractionExpired:
        check("open_modal past window raises InteractionExpired", True)

    # --- ephemeral: private-only fallback --------------------------------------------
    n_public = len(await mock.fetch_history(chan.ref, limit=1000))
    rc = await mock.send_ephemeral(chan.ref, actor, "secret")
    check("native ephemeral path used", rc.path is EphemeralPath.NATIVE
          and rc.message is not None and rc.message.metadata["ephemeral_for"] == "U1")
    check("native ephemeral not in public history",
          len(await mock.fetch_history(chan.ref, limit=1000)) == n_public)

    dm_mock = MockChatAdapter(native_ephemeral=False)
    dchan = await dm_mock.create_conversation(ConversationKind.CHANNEL, name="d")
    rc2 = await dm_mock.send_ephemeral(dchan.ref, actor, "psst")
    check("DM fallback path used", rc2.path is EphemeralPath.DM and rc2.message is not None)
    check("DM fallback lands in a DIRECT conversation",
          (await dm_mock.fetch_conversation(rc2.message.ref.conversation)).kind
          is ConversationKind.DIRECT)
    check("DM fallback not in public channel",
          await dm_mock.fetch_history(dchan.ref, limit=1000) == [])

    sealed = MockChatAdapter(native_ephemeral=False, dm_enabled=False)
    schan2 = await sealed.create_conversation(ConversationKind.CHANNEL, name="s2")
    try:
        await sealed.send_ephemeral(schan2.ref, actor, "leak?")
        check("exhausted fallback raises DeliveryFailed", False)
    except DeliveryFailed:
        check("exhausted fallback raises DeliveryFailed", True)
    check("exhausted fallback posted NOTHING public",
          await sealed.fetch_history(schan2.ref, limit=1000) == []
          and sealed.ephemeral_messages == [])

    # --- subscription: broadcast, filtering, no-replay ----------------------------------
    other = await mock.create_conversation(ConversationKind.CHANNEL, name="other")
    all_stream = mock.subscribe()
    filt_stream = mock.subscribe(conversations=[other.ref])
    t_all = asyncio.ensure_future(collect(all_stream, 2))
    t_filt = asyncio.ensure_future(collect(filt_stream, 1))
    await asyncio.sleep(0)
    mock.inject_message(chan.ref, "for-all-only", actor)
    mock.inject_message(other.ref, "for-both", actor)
    got_all = await t_all
    got_filt = await t_filt
    check("unfiltered subscriber receives both events",
          [e.payload["message"].text for e in got_all] == ["for-all-only", "for-both"])
    check("filtered subscriber gets only its conversation (no theft)",
          [e.payload["message"].text for e in got_filt] == ["for-both"])

    # APP_MENTION emission
    m_stream = mock.subscribe(conversations=[chan.ref])
    t_m = asyncio.ensure_future(collect(m_stream, 2))
    await asyncio.sleep(0)
    mock.inject_message(chan.ref, "hey @bot", actor, mention_bot=True)
    got_m = await t_m
    check("mention_bot also emits APP_MENTION",
          [e.type for e in got_m] == [EventType.MESSAGE_CREATED, EventType.APP_MENTION])

    # Disconnect: streams end; nothing emitted while down is replayed.
    d_stream = mock.subscribe()
    t_d = asyncio.ensure_future(collect(d_stream, 1))
    await asyncio.sleep(0)
    mock.simulate_disconnect()
    try:
        await t_d
        check("disconnect ends active streams", False)
    except StopAsyncIteration:
        check("disconnect ends active streams", True)
    lost = mock.inject_interaction(Interaction(
        id="i3", type=InteractionType.BUTTON, actor=actor,
        conversation=chan.ref, custom_id="missed"))
    re_stream = mock.subscribe()
    t_re = asyncio.ensure_future(collect(re_stream, 1))
    await asyncio.sleep(0)
    mock.inject_message(chan.ref, "after-reconnect", actor)
    got_re = await t_re
    check("no replay after reconnect (i3 lost; only live events arrive)",
          got_re[0].type is EventType.MESSAGE_CREATED
          and got_re[0].payload["message"].text == "after-reconnect")
    # ...but message state IS recoverable by re-query (unlike the interaction):
    check("missed messages recoverable via fetch_history(after=)",
          any(m.text == "after-reconnect"
              for m in await mock.fetch_history(chan.ref, after=target.ref, limit=1000)))

    # --- participants / archive / capabilities / errors ------------------------------------
    mock.add_participant(chan.ref, "U1")
    check("fetch_participants resolves registered users",
          [u.id for u in await mock.fetch_participants(chan.ref)] == ["U1"])
    await mock.archive_conversation(chan.ref)
    check("archive flips is_archived",
          (await mock.fetch_conversation(chan.ref)).is_archived)
    caps = mock.capabilities()
    check("capabilities reflect knobs + limits",
          caps.supports_ephemeral and caps.supports_dm
          and caps.max_message_length == 4000 and not caps.supports_message_search)
    # RateLimited is in the frozen taxonomy; the mock has no rate limits, so
    # verify it is a raiseable ChatError directly.
    try:
        raise RateLimited("simulated")
    except ChatError:
        check("RateLimited is a raiseable ChatError", True)

    print(f"\nPASS: {PASS} checks")


asyncio.run(main())
PYEOF
