"""Headless chatlink gateway daemon (t1120_3).

Textual-free — the chatlink analogue of ``applink/headless.py`` (the TUI
front-end arrives with t1120_6). Reached via ``ait chatlink --headless``
(the ``aitask_chatlink.sh`` launcher); **must never import Textual** — the
no-Textual contract is asserted by ``tests/test_chatlink_daemon.sh``.

Startup order (validation FIRST, zero side effects on the refuse paths):
config → token → intake ref, each refusal with its own distinct message;
then collaborators are constructed, the startup reconciliation pass runs
(sessions with no live agent fail closed — the crash-ownership story), and
only then does the sequential intake loop start.

**Execution shape (binding invariant):** one event at a time —
``handle_event`` is awaited to completion before the next event is dequeued;
reconciliation (startup and reconnect) always runs while no subscribe loop
is active. See ``aiplans/p1120/p1120_3_gateway_daemon_core.md``.

Run as a module (``python -m chatlink.daemon``) with ``.aitask-scripts`` on
``sys.path`` — the launcher script sets ``PYTHONPATH`` accordingly.
"""
from __future__ import annotations

import argparse
import asyncio
import shutil
import signal
import sys
import time
from pathlib import Path

from chat.errors import ChatError
from chat.model import ConversationRef, EventType, Message, MessageRef

from . import audit as audit_mod
from . import paths
from . import reconcile
from .config import ChatlinkConfig, load_config
from .intake import GatewayPipeline
from .relay import Answer, RelayError, SessionDir
from .sessions_store import SessionRecord, SessionsStore, conversation_key
from .spawn_seam import Launcher, NullLauncher

RECONNECT_BACKOFF_S = 2.0
#: Bound for the no-``after`` recovery fetch (empty-channel baseline case).
RECOVERY_FETCH_LIMIT = 100


# --------------------------------------------------------------------- #
# Spool scanning (I/O boundary for the pure planners)
# --------------------------------------------------------------------- #


def scan_relay_root(relay_root: Path, audit=None) -> dict:
    """session_id → :class:`reconcile.SpoolScan` for every session dir.

    Untrusted on-disk state: a malformed spool file must never abort the
    scan (and with it daemon startup). An unreadable session dir is skipped
    entirely (left alone on disk — conservative); a single malformed
    question/answer file excludes only that seq (neither pending nor
    healed; the never-overwrite answer write keeps any later cancel from
    clobbering it).
    """
    scans: dict[str, reconcile.SpoolScan] = {}
    if not relay_root.is_dir():
        return scans
    for entry in sorted(relay_root.iterdir()):
        if not entry.is_dir():
            continue
        session = SessionDir(entry)
        try:
            seqs = session.question_seqs()
        except OSError as exc:
            if audit is not None:
                audit.warning("relay scan: unreadable session dir %s: %s "
                              "— left alone", entry.name, exc)
            continue
        answers = {}
        pending = []
        for seq in seqs:
            try:
                ans = session.read_answer(seq)
            except (OSError, ValueError, RelayError) as exc:
                if audit is not None:
                    audit.warning("relay scan: malformed spool file s=%s "
                                  "seq=%s: %s — seq excluded",
                                  entry.name, seq, exc)
                continue
            if ans is None:
                pending.append(seq)
            else:
                answers[seq] = ans.to_dict()
        scans[entry.name] = reconcile.SpoolScan(
            session_id=entry.name,
            pending_seqs=tuple(pending),
            answers=answers,
        )
    return scans


# --------------------------------------------------------------------- #
# Action executor (phase discipline pinned in the plan)
# --------------------------------------------------------------------- #


class ActionExecutor:
    """Applies planner actions per session, strictly phase-ordered.

    Phase 1 (terminal persistence) must succeed before phases 2–3 run for
    that session; a phase-1 failure audits and leaves the session's relay
    dir and record for the next startup pass. Phase 2 is best-effort
    (``ChatError`` audited + swallowed). All spool/record I/O runs via
    ``asyncio.to_thread`` (called only between subscribe loops — never
    concurrently with event handling).
    """

    def __init__(self, *, store: SessionsStore, relay_root: Path,
                 pipeline: GatewayPipeline | None, audit):
        self.store = store
        self.relay_root = relay_root
        self.pipeline = pipeline
        self.audit = audit

    async def execute(self, actions: list[reconcile.Action]) -> None:
        by_session: dict[str, list[reconcile.Action]] = {}
        global_actions: list[reconcile.Action] = []
        for a in actions:
            if a.session_id:
                by_session.setdefault(a.session_id, []).append(a)
            else:
                global_actions.append(a)

        for sid, acts in sorted(by_session.items()):
            await self._execute_session(sid, reconcile.order_for_execution(acts))
        # Global (sessionless) actions run in PLANNER order — the reconnect
        # planner interleaves handle-then-advance per message, and
        # phase-sorting would persist a cursor past an unhandled message.
        # A recovery failure stops the chain: the cursor is left pointing
        # before the failed message, so the next reconnect re-fetches it
        # (at-least-once, never silently skipped).
        for a in global_actions:
            try:
                await self._execute_global(a)
            except Exception as exc:
                self.audit.error(
                    "reconnect recovery %s failed: %s — stopping; cursor "
                    "left for re-fetch", a.kind, exc)
                break

    async def _execute_session(self, sid: str,
                               acts: list[reconcile.Action]) -> None:
        phase1_ok = True
        for a in acts:
            if a.phase == reconcile.PHASE_PERSIST:
                try:
                    await self._apply_persist(sid, a)
                except (OSError, ValueError, RelayError) as exc:
                    phase1_ok = False
                    self.audit.error(
                        "reconcile phase1 %s failed session=%s: %s",
                        a.kind, sid, exc)
            elif a.phase == reconcile.PHASE_PLATFORM:
                if not phase1_ok:
                    continue  # never clean up unpersisted state
                await self._apply_platform(sid, a)
            elif a.phase == reconcile.PHASE_REMOVE_DIR:
                if not phase1_ok:
                    self.audit.warning(
                        "reconcile: keeping relay dir for %s "
                        "(phase-1 persistence failed)", sid)
                    continue
                await asyncio.to_thread(self._remove_relay_dir, sid)

    # -- phase 1 -------------------------------------------------------- #

    async def _apply_persist(self, sid: str, a: reconcile.Action) -> None:
        if a.kind == reconcile.MARK_FAILED:
            record = await asyncio.to_thread(self.store.load, sid)
            if record is None:
                # Corrupt/half-created: replace with a failed tombstone so
                # the ceiling queries stop counting it (fail-closed resolve).
                record = SessionRecord(
                    session_id=sid, initiator_id="unknown", state="failed")
            elif record.state == "failed":
                return  # idempotent re-run — already persisted
            else:
                record.state = "failed"
            await asyncio.to_thread(self.store.save, record)
            self.audit.info("session %s marked failed (%s)", sid,
                            a.payload.get("reason"))
        elif a.kind == reconcile.WRITE_CANCELLED_ANSWER:
            seq = int(a.payload["seq"])
            session = SessionDir(self.relay_root / sid)
            question = await asyncio.to_thread(session.read_question, seq)
            if question is None:
                return
            answer = Answer(id=question.id, seq=seq, status="cancelled")
            published = await asyncio.to_thread(
                session.write_answer, answer, overwrite=False)
            if published:
                self.audit.info("cancelled answer written s=%s seq=%s",
                                sid, seq)
        elif a.kind == reconcile.HEAL_OUTCOME:
            record = await asyncio.to_thread(self.store.load, sid)
            if record is None:
                return
            seq = int(a.payload["seq"])
            if not record.has_outcome(seq):
                record.set_outcome(seq, a.payload["answer"])
                await asyncio.to_thread(self.store.save, record)

    # -- phase 2 (best-effort) ------------------------------------------ #

    async def _apply_platform(self, sid: str, a: reconcile.Action) -> None:
        if self.pipeline is None:
            return
        try:
            if a.kind == reconcile.DISABLE_COMPONENTS:
                ref = a.payload["message"]
                msg_ref = MessageRef(
                    conversation=ConversationRef.from_dict(ref["conversation"]),
                    message_id=ref["message_id"])
                await self.pipeline.adapter.edit_message(
                    msg_ref, "*(question cancelled)*", components=[])
            elif a.kind == reconcile.REACT_FAILED:
                ref = a.payload["message"]
                msg_ref = MessageRef(
                    conversation=ConversationRef.from_dict(ref["conversation"]),
                    message_id=ref["message_id"])
                await self.pipeline.adapter.add_reaction(msg_ref, "❌")
            elif a.kind == reconcile.REPOST_QUESTION:
                record = await asyncio.to_thread(self.store.load, sid)
                if record is None or record.thread is None:
                    return
                session = SessionDir(self.relay_root / sid)
                question = await asyncio.to_thread(
                    session.read_question, int(a.payload["seq"]))
                if question is not None:
                    await self.pipeline.post_question(record, question)
        except (ChatError, OSError, ValueError, RelayError) as exc:
            # Phase 2 is best-effort by contract: platform errors AND local
            # I/O / malformed-spool failures are audited, never fatal.
            self.audit.info("reconcile platform cleanup %s failed s=%s: %s",
                            a.kind, sid, exc)

    # -- phase 3 -------------------------------------------------------- #

    def _remove_relay_dir(self, sid: str) -> None:
        try:
            shutil.rmtree(self.relay_root / sid)
            self.audit.info("relay dir removed for %s", sid)
        except FileNotFoundError:
            pass
        except OSError as exc:
            self.audit.warning("relay dir removal failed for %s: %s", sid, exc)

    # -- global (reconnect) actions -------------------------------------- #

    async def _execute_global(self, a: reconcile.Action) -> None:
        if a.kind == reconcile.ADVANCE_CURSOR:
            await asyncio.to_thread(
                self.store.save_watch_cursor,
                a.payload["conversation"], a.payload["message_id"])
        elif a.kind == reconcile.PROCESS_MESSAGE:
            raw = a.payload["message"].get("raw")
            if self.pipeline is not None and raw is not None:
                await self.pipeline.handle_event(_message_event(raw))


def _message_event(message: Message):
    """Synthesize the MESSAGE_CREATED event shape for a recovered message."""
    from chat.model import Event

    return Event(
        id=f"recovered-{message.ref.message_id}",
        type=EventType.MESSAGE_CREATED,
        actor=message.author,
        conversation=message.ref.conversation,
        timestamp=message.timestamp,
        payload={"message": message},
    )


# --------------------------------------------------------------------- #
# Reconciliation passes
# --------------------------------------------------------------------- #


async def run_startup_reconciliation(
    *, store: SessionsStore, relay_root: Path, launcher: Launcher,
    workspace_id: str, pipeline: GatewayPipeline | None, audit,
) -> None:
    """The pre-intake crash-ownership pass (plan §reconcile)."""
    records, corrupt = await asyncio.to_thread(store.list_records)
    scans = await asyncio.to_thread(scan_relay_root, relay_root, audit)
    try:
        live = set(launcher.reap_orphans(workspace_id))
    except Exception as exc:  # a broken backend must not block startup
        audit.error("reap_orphans failed (assuming none live): %s", exc)
        live = set()
    actions = reconcile.plan_startup_actions(records, corrupt, live, scans)
    if actions:
        audit.info("startup reconciliation: %d action(s)", len(actions))
    executor = ActionExecutor(store=store, relay_root=relay_root,
                              pipeline=pipeline, audit=audit)
    await executor.execute(actions)


async def ensure_watch_baseline(
    *, store: SessionsStore, adapter, intake_ref: ConversationRef, audit,
) -> None:
    """Establish the intake-channel watch baseline if none exists (pinned
    no-cursor policy).

    The daemon watches the channel **from startup onward** — pre-existing
    messages are never intake candidates (a first run must not slurp the
    channel's history and spawn sandboxes for old reports). The baseline is
    the newest message at startup; an **empty channel persists an explicit
    ``message_id: None`` marker**, telling reconnect recovery that
    everything later found in the channel is new (bounded no-``after``
    fetch). A failed baseline fetch is audited and retried at the next
    reconnect (recovery is skipped until a baseline exists — fail-safe,
    never fail-open over old history).
    """
    cursors = await asyncio.to_thread(store.load_watch_cursors)
    if conversation_key(intake_ref.to_dict()) in cursors:
        return
    try:
        newest = await adapter.fetch_history(intake_ref, limit=1)
    except ChatError as exc:
        audit.warning("watch baseline fetch failed (retrying at next "
                      "reconnect): %s", exc)
        return
    baseline_id = newest[-1].ref.message_id if newest else None
    try:
        await asyncio.to_thread(
            store.save_watch_cursor, intake_ref.to_dict(), baseline_id)
    except OSError as exc:
        # Same local-I/O resilience class as _advance_cursor_for: a failed
        # baseline save must never abort startup or escape reconnect
        # recovery — audited, retried at the next reconnect (fail-safe:
        # recovery stays skipped until a baseline exists).
        audit.warning("watch baseline save failed (retrying at next "
                      "reconnect): %s", exc)
        return
    audit.info("watch baseline established (%s)",
               baseline_id or "empty channel")


async def run_reconnect_reconciliation(
    *, store: SessionsStore, relay_root: Path, intake_ref: ConversationRef,
    pipeline: GatewayPipeline, audit,
) -> None:
    """The post-disconnect re-query pass: history diff + re-prompts."""
    cursors = await asyncio.to_thread(store.load_watch_cursors)
    cursor = cursors.get(conversation_key(intake_ref.to_dict()))
    fetched: list[Message] = []
    try:
        if cursor is None:
            # No baseline (first-run fetch failed earlier): recovery cannot
            # distinguish downtime messages from old history — skip it
            # (fail-safe) and re-establish the baseline so the NEXT
            # disconnect recovers.
            audit.warning("no watch baseline — history recovery skipped; "
                          "re-establishing baseline")
            await ensure_watch_baseline(
                store=store, adapter=pipeline.adapter,
                intake_ref=intake_ref, audit=audit)
        elif cursor.get("message_id") is None:
            # Empty-channel baseline marker: everything now in the channel
            # arrived after startup — bounded recovery fetch.
            fetched = await pipeline.adapter.fetch_history(
                intake_ref, limit=RECOVERY_FETCH_LIMIT)
        else:
            after_ref = MessageRef(
                conversation=ConversationRef.from_dict(cursor["conversation"]),
                message_id=cursor["message_id"])
            fetched = await pipeline.adapter.fetch_history(
                intake_ref, after=after_ref)
    except ChatError as exc:
        audit.warning("reconnect history fetch failed: %s", exc)

    fetched_dicts = [
        {
            "conversation": m.ref.conversation.to_dict(),
            "message_id": m.ref.message_id,
            "author_is_self": bool(m.author and m.author.is_self),
            "author_is_bot": bool(m.author and m.author.is_bot),
            "raw": m,
        }
        for m in fetched
    ]
    records, _corrupt = await asyncio.to_thread(store.list_records)
    scans = await asyncio.to_thread(scan_relay_root, relay_root, audit)
    actions = reconcile.plan_reconnect_actions(records, fetched_dicts, scans)
    if actions:
        audit.info("reconnect reconciliation: %d action(s)", len(actions))
    executor = ActionExecutor(store=store, relay_root=relay_root,
                              pipeline=pipeline, audit=audit)
    await executor.execute(actions)


# --------------------------------------------------------------------- #
# Daemon core
# --------------------------------------------------------------------- #


async def run_daemon(
    *,
    adapter,
    config: ChatlinkConfig,
    store: SessionsStore,
    launcher: Launcher,
    relay_root: Path,
    audit,
    stop: asyncio.Event,
    clock=time.time,
) -> int:
    """Reconcile, then consume events sequentially until ``stop`` is set.

    The adapter is injected (production: ``DiscordAdapter.connect(token)``;
    tests: ``MockChatAdapter``) — this function performs no construction,
    keeping it fully drivable by the test suite.
    """
    intake_ref = ConversationRef.from_dict(config.intake_channel)
    pipeline = GatewayPipeline(
        adapter=adapter, config=config, store=store, launcher=launcher,
        relay_root=relay_root, audit=audit, clock=clock,
    )

    await run_startup_reconciliation(
        store=store, relay_root=relay_root, launcher=launcher,
        workspace_id=intake_ref.workspace_id, pipeline=pipeline, audit=audit)
    # Pinned no-cursor policy: watch from startup onward — baseline the
    # intake channel BEFORE the first subscribe, so a disconnect that
    # happens before any live message still recovers downtime messages.
    await ensure_watch_baseline(
        store=store, adapter=adapter, intake_ref=intake_ref, audit=audit)

    while not stop.is_set():
        stream = await _open_stream(adapter)
        try:
            async for event in stream:
                # Sequential dispatch: awaited to completion (binding
                # invariant) — the next event is not read until this one
                # is fully handled.
                await pipeline.handle_event(event)
                await _advance_cursor_for(event, store, audit)
                if stop.is_set():
                    break
        except ChatError as exc:
            audit.warning("subscribe stream error: %s", exc)
        if stop.is_set():
            break
        # Stream ended (disconnect): re-query, then re-subscribe.
        audit.info("subscribe stream ended — reconciling and re-subscribing")
        await run_reconnect_reconciliation(
            store=store, relay_root=relay_root, intake_ref=intake_ref,
            pipeline=pipeline, audit=audit)
        try:
            await asyncio.wait_for(stop.wait(), timeout=RECONNECT_BACKOFF_S)
        except asyncio.TimeoutError:
            pass
    return 0


async def _open_stream(adapter):
    """`subscribe` is an async-generator method: calling it returns the
    iterator (some impls need an await) — normalize both shapes."""
    stream = adapter.subscribe()
    if hasattr(stream, "__aiter__"):
        return stream
    return await stream


async def _advance_cursor_for(event, store: SessionsStore, audit) -> None:
    """Persist the intake-channel history cursor (loop-only mutation; the
    file write itself runs off-loop like all spool/record I/O).

    A cursor-save failure (disk-full, permissions) is audited and swallowed
    — the same local-I/O resilience class as the handler boundary. The
    event was already handled; a stale cursor only means the next reconnect
    re-fetches it (at-least-once), never a stopped daemon.
    """
    if event.type is not EventType.MESSAGE_CREATED:
        return
    message = event.payload.get("message")
    if message is None:
        return
    try:
        await asyncio.to_thread(
            store.save_watch_cursor,
            message.ref.conversation.to_dict(), message.ref.message_id)
    except OSError as exc:
        audit.warning("watch-cursor save failed (will re-fetch on "
                      "reconnect): %s", exc)


# --------------------------------------------------------------------- #
# Entry point (validate-then-serve; refuse paths have zero side effects)
# --------------------------------------------------------------------- #


def _refuse(msg: str) -> int:
    print(f"chatlink: {msg}", file=sys.stderr)
    return 2


async def serve() -> int:
    # 1. Config — resolve + load, each refusal distinct (fail-closed).
    cfg_path = paths.config_file()
    if cfg_path is None:
        return _refuse(
            "no gateway config found — create "
            f"{paths.CONFIG_DEFAULT_REL} (seeded by 'ait setup') first.")
    config = load_config(cfg_path)
    if config is None:
        return _refuse(
            f"gateway config {cfg_path} is missing or malformed — fix the "
            "YAML before starting.")
    if config.intake_channel is None:
        return _refuse(
            "config has no valid intake_channel — the daemon refuses to "
            "watch without one.")

    # 2. Token (per-PC secret; written by the operator — see t1120_6/7).
    token = paths.read_token()
    if token is None:
        return _refuse(
            f"no bot token at {paths.token_file()} — write the bot token "
            "there (0600) before starting.")

    # 3. Only now: side effects (adapter connect, dirs, logger).
    from chat.discord_adapter import DiscordAdapter  # lazy: needs chat tier

    audit = audit_mod.get_logger(paths.sessions_dir())
    store = SessionsStore(paths.sessions_dir() / "sessions")
    relay_root = paths.relay_root()

    adapter = await DiscordAdapter.connect(token)
    try:
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop.set)
            except (NotImplementedError, RuntimeError):
                pass
        print("chatlink gateway running (headless) — SIGINT/SIGTERM to stop.",
              flush=True)
        return await run_daemon(
            adapter=adapter, config=config, store=store,
            launcher=NullLauncher(), relay_root=relay_root, audit=audit,
            stop=stop)
    finally:
        close = getattr(adapter, "close", None)
        if close is not None:
            try:
                await close()
            except Exception:
                pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ait chatlink",
        description=(
            "Chatlink gateway daemon: watch the configured bug-intake "
            "channel and relay agent Q&A (headless; TUI arrives with "
            "t1120_6)."
        ),
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="Run the headless gateway daemon (required in v1).")
    args = parser.parse_args(list(argv) if argv is not None else sys.argv[1:])
    if not args.headless:
        print("chatlink: only --headless is available in this build "
              "(the TUI arrives with t1120_6).", file=sys.stderr)
        return 2
    return asyncio.run(serve())


if __name__ == "__main__":
    sys.exit(main())
