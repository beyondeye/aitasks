"""Chatlink intake + minimal interaction pipeline (t1120_3).

The event-handling core the daemon drives. **Execution shape (binding
invariant, p1120_3):** the daemon awaits :meth:`GatewayPipeline.handle_event`
to completion for each event before dequeuing the next — handlers are never
spawned as concurrent tasks, so every check-then-write here (rate/concurrency
ceilings, interaction-outcome persistence) is serialized by construction.

Intake step order + per-step failure behavior are pinned in the plan:
policy pass → (a) create thread → (b) mint relay dir → (c) persist
``spawning`` record → (d) launch. The record lands BEFORE launch so a crash
between (c) and (d) is fail-closed by startup reconciliation.

The minimal interaction path (scope boundary with t1120_6): select
submissions are handled end-to-end — the atomic
``write_answer(overwrite=False)`` is the durable outcome and the handler's
FIRST awaited side effect; free-text triggers, page navigation and modal
submits are recognized but deferred (audited ephemeral stub) until
t1120_6's ``flow.py``.
"""
from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

from chat.adapter import ChatAdapter
from chat.errors import ChatError
from chat.interactions import Interaction
from chat.model import (
    Actor,
    ConversationKind,
    ConversationRef,
    Event,
    EventType,
    Message,
    MessageRef,
)

from lib.sandbox_launch import make_workspace_copy, remove_workspace_copy

from . import paths
from . import policy as policy_mod
from .config import ChatlinkConfig
from .relay import (
    CustomIdError,
    RelayError,
    SessionDir,
    create_session_dir,
    parse_custom_id,
)
from .render import (
    AnswerMismatch,
    RenderRejected,
    assemble_answer,
    build_modal,
    is_free_text_trigger,
    is_page_nav,
    render_question,
)
from .sessions_store import SessionRecord, SessionsStore, message_ref_dict
from .spawn_seam import Launcher, LaunchError, SandboxSpec

RATE_WINDOW_S = 3600.0  # contract 11: intake_rate_per_user_per_hour

#: Deny-audit reasons that are ceilings, not policy (distinct from
#: ``policy.REASON_*`` — tests pin one negative control per reason).
REASON_CEILING_SANDBOXES = "ceiling_sandboxes"
REASON_CEILING_USER_RATE = "ceiling_user_rate"

MSG_DENIED = "You are not authorized to open bug reports here."
MSG_RATE_LIMITED = "Rate limit reached — please try again later."
MSG_BUSY = "All bug-report slots are busy — please try again later."
MSG_EXPIRED = "This question has expired."
MSG_NOT_INITIATOR = "Only the user who opened this bug report can answer."
MSG_LAUNCH_FAILED = "Could not start the analysis agent — session failed."

#: Reactions-as-status vocabulary (pinned, applied to the original
#: bug-report message; asserted by tests at each state transition).
STATUS_WORKING = "⏳"
STATUS_AWAITING = "❓"
STATUS_CREATED = "✅"
STATUS_FAILED = "❌"


def _ref_of(event_conversation: ConversationRef | None) -> ConversationRef | None:
    return event_conversation


class GatewayPipeline:
    """Sequentially-driven event pipeline over injected collaborators.

    ``agent_argv`` is the sandbox command (resolved by the daemon glue);
    ``clock`` is the deterministic test seam shared with the store.
    ``repo_root`` is the checkout the per-session workspace copy is taken
    from (test seam: a small fixture repo). ``death_signal`` is the
    thread-safe agent-death callback threaded into every launched spec
    (t1120_5 — a ``call_soon_threadsafe`` enqueue supplied by the daemon;
    it must never do I/O itself).
    """

    def __init__(
        self,
        *,
        adapter: ChatAdapter,
        config: ChatlinkConfig,
        store: SessionsStore,
        launcher: Launcher,
        relay_root: str | Path,
        audit,
        clock=time.time,
        agent_argv: tuple = (),
        repo_root: str | Path | None = None,
        death_signal=None,
        handles: dict | None = None,
        environ=None,
        create_script=None,
        push_argv: tuple | None = None,
    ):
        self.adapter = adapter
        self.config = config
        self.store = store
        self.launcher = launcher
        self.relay_root = Path(relay_root)
        self.audit = audit
        self.clock = clock
        self.agent_argv = tuple(agent_argv)
        self.repo_root = Path(repo_root) if repo_root is not None \
            else paths.project_root()
        self.workspaces_root = paths.workspaces_root_beside(self.relay_root)
        self.death_signal = death_signal
        #: Live sandbox handles by session_id (daemon-owned registry;
        #: t1120_6 kill-on-payload-completion). Popped on terminal paths.
        self.handles: dict = {} if handles is None else handles
        #: Env source for ``sandbox_env_passthrough`` resolution (test seam).
        self.environ = os.environ if environ is None else environ
        #: Task-creation seams consumed by ``flow.complete_session``
        #: (``None`` ⇒ the real script / ``ait git push`` at repo_root).
        self.create_script = create_script
        self.push_argv = push_argv
        if config.intake_channel is None:
            # The daemon refuses to start without it; belt-and-braces here.
            raise ValueError("config.intake_channel is required")
        self.intake_ref = ConversationRef.from_dict(config.intake_channel)

    # ------------------------------------------------------------------ #
    # Event dispatch (called sequentially by the daemon loop)
    # ------------------------------------------------------------------ #

    async def handle_event(self, event: Event) -> None:
        """Handle one normalized event; never raises (fail-quiet + audit).

        Catches platform errors (``ChatError``) AND local I/O failures
        (``OSError`` from spool/record writes, ``RelayError`` from relay
        validation, ``ValueError`` — malformed spool JSON raises
        ``json.JSONDecodeError``): a disk-full, permission, or corrupt-file
        failure must leave the spool/record state for reconciliation to
        heal — never stop the gateway.
        """
        try:
            if event.type is EventType.MESSAGE_CREATED:
                await self._handle_message(event)
            elif event.type is EventType.INTERACTION_RECEIVED:
                await self._handle_interaction(event)
        except (ChatError, OSError, ValueError, RelayError) as exc:
            self.audit.error("handler error: %s: %s",
                             type(exc).__name__, exc)

    # ------------------------------------------------------------------ #
    # Intake (MESSAGE_CREATED on the intake channel)
    # ------------------------------------------------------------------ #

    async def _handle_message(self, event: Event) -> None:
        message: Message | None = event.payload.get("message")
        if message is None or event.conversation is None:
            return
        if event.conversation != self.intake_ref:
            return
        actor = event.actor
        if actor is None or actor.is_self or actor.is_bot:
            return  # self-trigger-loop protection — silent drop

        # -- authorization (deny-by-default) --
        claims = None
        try:
            claims = await self.adapter.fetch_identity_claims(
                event.conversation, actor.id)
        except ChatError as exc:
            self.audit.warning("claims fetch failed for %s: %s",
                               _tag(actor.id), exc)
        decision = policy_mod.decide(claims, self.config)
        if not decision.allow:
            await self._deny(event.conversation, actor, decision.reason,
                             MSG_DENIED)
            return

        # -- ceilings (bounded intake; derived from persisted records) --
        if self.store.count_nonterminal() >= self.config.max_concurrent_sandboxes:
            await self._deny(event.conversation, actor,
                             REASON_CEILING_SANDBOXES, MSG_BUSY)
            return
        if (self.store.count_recent_by_initiator(actor.id, RATE_WINDOW_S)
                >= self.config.intake_rate_per_user_per_hour):
            await self._deny(event.conversation, actor,
                             REASON_CEILING_USER_RATE, MSG_RATE_LIMITED)
            return

        await self._open_session(event.conversation, actor, message)

    async def _open_session(self, conversation: ConversationRef,
                            actor: Actor, message: Message) -> None:
        """Pinned step order (a)→(d); see module docstring for the failure
        table. Each failure is audited with its step name."""
        # (a) create thread
        try:
            thread = await self.adapter.create_conversation(
                ConversationKind.THREAD, parent=message.ref,
                name=f"bug: {message.text[:48]}" if message.text else "bug report",
            )
        except ChatError as exc:
            self.audit.error("intake step=create_thread user=%s failed: %s",
                             _tag(actor.id), exc)
            await self._ephemeral_quiet(conversation, actor,
                                        "Could not open a bug-report thread.")
            return

        # (b) mint relay session dir
        try:
            session = await asyncio.to_thread(create_session_dir,
                                              self.relay_root)
        except (OSError, RelayError) as exc:
            self.audit.error("intake step=mint_relay_dir user=%s failed: %s",
                             _tag(actor.id), exc)
            await self._thread_failure_note(thread.ref, message.ref,
                                            "internal error (relay)")
            return
        sid = session.session_id

        # (c) persist session record (BEFORE launch — crash ⇒ fail-closed)
        record = self.store.new_record(
            sid, actor.id,
            thread=thread.ref.to_dict(),
            bug_report_message=message_ref_dict(
                message.ref.conversation.to_dict(), message.ref.message_id),
        )
        try:
            await asyncio.to_thread(self.store.save, record)
        except OSError as exc:
            self.audit.error(
                "intake step=persist_record session=%s failed: %s", sid, exc)
            await asyncio.to_thread(_remove_dir_quiet, session.path)
            await self._thread_failure_note(thread.ref, message.ref,
                                            "internal error (state)")
            return

        # (d) launch through the seam. The bug-report write and the
        # workspace-copy creation are PART of the launch step and share its
        # fail path (a failure here must never leave a non-terminal session
        # waiting for the next startup reconciliation).
        workspace_copy = self.workspaces_root / sid
        try:
            # The agent reads the report via CHATLINK_BUG_REPORT_FILE —
            # the backend points it at <relay>/bug_report.md (seam
            # contract), so the file must exist before launch.
            await asyncio.to_thread(
                (session.path / "bug_report.md").write_text,
                message.text or "(no text)", "utf-8")
            await asyncio.to_thread(
                make_workspace_copy, self.repo_root, workspace_copy)
            spec = SandboxSpec(
                session_id=sid,
                relay_dir=str(session.path),
                agent_argv=self.agent_argv,
                workspace_copy_path=str(workspace_copy),
                workspace_id=self.intake_ref.workspace_id,
                env_allowlist=self._resolve_env_passthrough(),
                limits={
                    "memory": self.config.sandbox_memory,
                    "cpus": self.config.sandbox_cpus,
                    "pids": self.config.sandbox_pids,
                    "wall_clock_s": self.config.sandbox_wall_clock_s,
                },
                on_death=self.death_signal,
            )
            self.handles[sid] = self.launcher.launch(spec)
        except (LaunchError, OSError) as exc:
            self.audit.error("intake step=launch session=%s failed: %s",
                             sid, exc)
            # Terminal persistence FIRST, platform cleanup after; the
            # (partial) workspace copy is removed last (best-effort).
            record.state = "failed"
            await asyncio.to_thread(self.store.save, record)
            await self._thread_failure_note(thread.ref, message.ref,
                                            MSG_LAUNCH_FAILED)
            await asyncio.to_thread(remove_workspace_copy, workspace_copy)
            return

        self.audit.info("intake accepted session=%s user=%s", sid,
                        _tag(actor.id))
        await self._set_status_reaction(record, STATUS_WORKING)

    def _resolve_env_passthrough(self) -> dict:
        """``sandbox_env_passthrough`` names → gateway env values.

        A configured name absent from the environment is skipped with an
        audit warning — never a launch blocker (the agent fails visibly
        in-thread if it truly needed the key).
        """
        env: dict = {}
        for name in self.config.sandbox_env_passthrough:
            val = self.environ.get(name)
            if val is None:
                self.audit.warning(
                    "env passthrough: %s not set — skipped", name)
            else:
                env[name] = val
        return env

    # ------------------------------------------------------------------ #
    # Minimal interaction path (select submissions end-to-end)
    # ------------------------------------------------------------------ #

    async def _handle_interaction(self, event: Event) -> None:
        interaction: Interaction | None = event.payload.get("interaction")
        if interaction is None or not interaction.custom_id:
            return
        try:
            sid, seq, _component = parse_custom_id(interaction.custom_id)
        except CustomIdError:
            # Not ours (or malformed): fail-closed — audit + ignore.
            self.audit.info("ignoring unknown custom_id %r",
                            interaction.custom_id[:40])
            return

        record = await asyncio.to_thread(self.store.load, sid)
        if record is None:
            self.audit.info("interaction for unknown session %s — ignored", sid)
            return

        gate = policy_mod.may_answer(record.initiator_id,
                                     interaction.actor.id if interaction.actor else None)
        if not gate.allow:
            self.audit.info("interaction denied reason=%s session=%s user=%s",
                            gate.reason, sid,
                            _tag(interaction.actor.id if interaction.actor else None))
            await self._respond_quiet(interaction, MSG_NOT_INITIATOR)
            return

        session = SessionDir(self.relay_root / sid)
        question = await asyncio.to_thread(session.read_question, seq)
        if question is None:
            self.audit.info("interaction for absent question s=%s seq=%s",
                            sid, seq)
            await self._respond_quiet(interaction, MSG_EXPIRED)
            return

        if is_free_text_trigger(question, interaction):
            # Contract 5: open the modal IMMEDIATELY — this must be the
            # first awaited platform call so it beats the adapter's
            # scheduled defer (~2 s window on Discord).
            try:
                await self.adapter.open_modal(interaction,
                                              build_modal(question))
            except ChatError as exc:
                self.audit.info("open_modal failed s=%s seq=%s: %s",
                                sid, seq, exc)
                await self._respond_quiet(interaction, MSG_EXPIRED)
            return

        page = is_page_nav(question, interaction)
        if page is not None:
            await self._render_page(record, question, page, interaction)
            return

        try:
            answer = assemble_answer(question, interaction)
        except AnswerMismatch as exc:
            self.audit.info("stale/foreign interaction s=%s seq=%s: %s",
                            sid, seq, exc)
            await self._respond_quiet(interaction, MSG_EXPIRED)
            return

        # THE durable-outcome write — the handler's FIRST awaited side
        # effect for this interaction (binding invariant). Atomic
        # create-no-replace: False ⇒ an answer already exists ⇒ stale.
        published = await asyncio.to_thread(
            session.write_answer, answer, overwrite=False)
        if not published:
            self.audit.info("repeat interaction s=%s seq=%s — stale", sid, seq)
            await self._respond_quiet(interaction, MSG_EXPIRED)
            return

        # Derived bookkeeping + best-effort component disabling. The
        # status-reaction mutation rides the same save (persist=False).
        record.set_outcome(seq, answer.to_dict())
        if record.state == "asking":
            record.state = "working"
        await self._set_status_reaction(record, STATUS_WORKING,
                                        persist=False)
        await asyncio.to_thread(self.store.save, record)
        await self._disable_question_components(record, seq, question.text)
        self.audit.info("answer recorded session=%s seq=%s", sid, seq)

    async def _render_page(self, record: SessionRecord, question,
                           page: int, interaction: Interaction) -> None:
        """Page-nav re-render: edit the stored question message in place.

        The re-render is the visible outcome; the interaction itself is
        acked quietly so the platform stops its spinner.
        """
        ref_dict = record.question_messages.get(str(int(question.seq)))
        if ref_dict is None:
            await self._respond_quiet(interaction, MSG_EXPIRED)
            return
        try:
            rendered = render_question(question, self.adapter.capabilities(),
                                       page=page)
        except RenderRejected as exc:
            self.audit.error("page render rejected s=%s seq=%s: %s",
                             record.session_id, question.seq, exc.reason)
            await self._respond_quiet(interaction, MSG_EXPIRED)
            return
        msg_ref = MessageRef(
            conversation=ConversationRef.from_dict(ref_dict["conversation"]),
            message_id=ref_dict["message_id"],
        )
        try:
            await self.adapter.edit_message(msg_ref, rendered.text_chunks[-1],
                                            components=rendered.rows)
            await self.adapter.ack(interaction)
        except ChatError as exc:
            self.audit.info("page nav failed s=%s seq=%s: %s",
                            record.session_id, question.seq, exc)

    async def post_question(self, record: SessionRecord, question) -> None:
        """Render + post one pending question into the session thread.

        Used by tests and by reconciliation re-prompt actions (the
        continuous spool→Discord pump is t1120_6). Raises
        ``RenderRejected`` (audited) for unrenderable questions.
        """
        try:
            rendered = render_question(question, self.adapter.capabilities())
        except RenderRejected as exc:
            self.audit.error("render rejected s=%s seq=%s: %s",
                             record.session_id, question.seq, exc.reason)
            raise
        thread_ref = ConversationRef.from_dict(record.thread)
        posted = None
        for i, chunk in enumerate(rendered.text_chunks):
            last = i == len(rendered.text_chunks) - 1
            posted = await self.adapter.send_message(
                thread_ref, chunk, components=rendered.rows if last else None)
        if posted is not None:
            record.question_messages[str(int(question.seq))] = message_ref_dict(
                posted.ref.conversation.to_dict(), posted.ref.message_id)
        if record.state == "spawning" or record.state == "working":
            record.state = "asking"
        await self._set_status_reaction(record, STATUS_AWAITING,
                                        persist=False)
        await asyncio.to_thread(self.store.save, record)

    # ------------------------------------------------------------------ #
    # Quiet platform helpers (fail-quiet: audit, never crash, never public)
    # ------------------------------------------------------------------ #

    async def _deny(self, conversation: ConversationRef, actor: Actor,
                    reason: str, text: str) -> None:
        self.audit.info("intake denied reason=%s user=%s", reason,
                        _tag(actor.id))
        if self.config.deny_message_mode == "ephemeral":
            await self._ephemeral_quiet(conversation, actor, text)

    async def _ephemeral_quiet(self, conversation: ConversationRef,
                               actor: Actor, text: str) -> None:
        """Private-only delivery; ``DeliveryFailed`` (and any other
        ``ChatError``) is audited and dropped — NEVER retried publicly."""
        try:
            await self.adapter.send_ephemeral(conversation, actor, text)
        except ChatError as exc:
            self.audit.info("ephemeral delivery failed for %s: %s",
                            _tag(actor.id), exc)

    async def _respond_quiet(self, interaction: Interaction, text: str) -> None:
        try:
            await self.adapter.respond(interaction, text, ephemeral=True)
        except ChatError as exc:
            self.audit.info("interaction response failed: %s", exc)

    async def _set_status_reaction(self, record: SessionRecord,
                                   emoji: str, *, persist: bool = True) -> None:
        """Swap the status reaction on the original bug-report message.

        Mutates + persists ``record.status_reaction`` (pinned vocabulary
        ⏳/❓/✅/❌); the platform part is best-effort/audited. No-op when
        the record has no bug-report ref or already carries ``emoji``.
        ``persist=False`` when the caller issues the save itself right
        after (keeps single-save orderings intact — the caller MUST save).
        """
        if record.bug_report_message is None or \
                record.status_reaction == emoji:
            return
        prev = record.status_reaction
        record.status_reaction = emoji
        if persist:
            await asyncio.to_thread(self.store.save, record)
        ref = record.bug_report_message
        msg_ref = MessageRef(
            conversation=ConversationRef.from_dict(ref["conversation"]),
            message_id=ref["message_id"],
        )
        try:
            if prev:
                await self.adapter.remove_reaction(msg_ref, prev)
            await self.adapter.add_reaction(msg_ref, emoji)
        except ChatError as exc:
            self.audit.info("status reaction failed s=%s: %s",
                            record.session_id, exc)

    async def _thread_failure_note(self, thread_ref: ConversationRef,
                                   bug_msg_ref: MessageRef, note: str) -> None:
        try:
            await self.adapter.send_message(thread_ref, f"❌ {note}")
        except ChatError as exc:
            self.audit.info("thread failure-note failed: %s", exc)
        try:
            await self.adapter.add_reaction(bug_msg_ref, "❌")
        except ChatError as exc:
            self.audit.info("failure reaction failed: %s", exc)

    async def _disable_question_components(self, record: SessionRecord,
                                           seq: int, text: str) -> None:
        ref_dict = record.question_messages.get(str(int(seq)))
        if ref_dict is None:
            return
        msg_ref = MessageRef(
            conversation=ConversationRef.from_dict(ref_dict["conversation"]),
            message_id=ref_dict["message_id"],
        )
        try:
            await self.adapter.edit_message(
                msg_ref, f"{text}\n*(answered)*", components=[])
        except ChatError as exc:
            self.audit.info("component disable failed s=%s seq=%s: %s",
                            record.session_id, seq, exc)


def _tag(user_id: str | None) -> str:
    """Truncated id for audit lines (never log raw ids in full)."""
    if not user_id:
        return "<none>"
    return f"{user_id[:8]}…" if len(user_id) > 8 else user_id


def _remove_dir_quiet(path: Path) -> None:
    import shutil

    try:
        shutil.rmtree(path)
    except OSError:
        pass
