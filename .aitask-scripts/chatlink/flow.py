"""Flow orchestration (t1120_6): spool→post pump + payload completion.

**Concurrency safety contract (binding; tested):**

1. The pump task is a pure **reader** — it scans spool dirs + records via
   ``asyncio.to_thread`` and its only write is ``flow_q.put_nowait``. Every
   record/spool/reaction/platform mutation for flow events executes inside
   the daemon's single sequential consumer (``run_daemon``'s merged-event
   loop), which already owns intake/interaction/death mutations.
2. ``flow_q`` joins ``_merged_events`` as a third source (the death_q
   pattern) — no new dispatch path.
3. Scan results are stale by construction: every handler re-loads the
   record and re-checks the spool inside the loop before acting. A
   stale/duplicate event is a no-op by construction (the same idempotent
   supersession guard as ``plan_agent_death_actions``).
4. Terminal transitions are single-assignment: only the loop consumer
   assigns ``done``/``failed``, always behind a non-terminal re-check.
5. ``flow_q`` is bounded; overflow drops + audits — the scan is
   level-triggered (state re-derived from disk each tick), so a dropped
   event is regenerated on the next tick. A scan-tick exception is audited
   and skipped, never daemon-fatal.

**Crash window note:** ``complete_session`` persists ``awaiting_payload``
before validating. A crash inside that window leaves a non-terminal record
with no live agent — startup reconciliation fail-closes it to ``failed``
(pinned crash ownership; the window is a few seconds).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from chat.errors import ChatError
from chat.model import ConversationRef

from .intake import (
    STATUS_CREATED,
    STATUS_FAILED,
    GatewayPipeline,
    _tag,
)
from .payload_guard import PayloadRejected, validate_payload
from .relay import Answer, RelayError, SessionDir
from .render import RenderRejected
from .sessions_store import SessionsStore
from .task_create import TaskCreateError, create_task_from_payload

#: Pump cadence + queue bound (level-triggered scan ⇒ drops are safe).
FLOW_SCAN_INTERVAL_S = 2.0
FLOW_QUEUE_MAX = 256

QUESTION_READY = "question_ready"
PAYLOAD_READY = "payload_ready"

MSG_SESSION_FAILED = "❌ Bug-report session failed: {reason}"
MSG_QUESTION_UNRENDERABLE = "❌ A question could not be rendered: {reason}"


@dataclass(frozen=True)
class FlowEvent:
    kind: str  # QUESTION_READY | PAYLOAD_READY
    session_id: str
    seq: int = -1


# --------------------------------------------------------------------- #
# Pump (pure reader; enqueue-only)
# --------------------------------------------------------------------- #


def scan_flow_events(store: SessionsStore, relay_root: Path,
                     audit=None) -> list:
    """One level-triggered scan pass: derive ready events from disk.

    Pure read (blocking I/O — run via ``asyncio.to_thread``). Emits
    ``QUESTION_READY`` for each pending question with no posted marker and
    ``PAYLOAD_READY`` when ``payload.json`` exists — for non-terminal
    sessions only. The loop-side handlers re-validate everything.
    """
    from .daemon import scan_one_session  # deferred: daemon imports flow

    events: list[FlowEvent] = []
    records, _corrupt = store.list_records()
    for record in records:
        if record.is_terminal:
            continue
        sid = record.session_id
        if (relay_root / sid / "payload.json").exists():
            events.append(FlowEvent(PAYLOAD_READY, sid))
            continue  # completion supersedes question posting
        scan = scan_one_session(relay_root, sid, audit)
        if scan is None:
            continue
        for seq in scan.pending_seqs:
            if str(int(seq)) not in record.question_messages:
                events.append(FlowEvent(QUESTION_READY, sid, seq=int(seq)))
    return events


async def run_flow_pump(*, store: SessionsStore, relay_root: Path,
                        flow_q: asyncio.Queue, stop: asyncio.Event,
                        audit, interval_s: float = FLOW_SCAN_INTERVAL_S) -> None:
    """Background scan loop; its only side effect is ``flow_q.put_nowait``."""
    while not stop.is_set():
        try:
            events = await asyncio.to_thread(
                scan_flow_events, store, relay_root, audit)
            for ev in events:
                try:
                    flow_q.put_nowait(ev)
                except asyncio.QueueFull:
                    audit.warning(
                        "flow queue full — dropped %s for %s (regenerated "
                        "next scan)", ev.kind, ev.session_id)
        except Exception as exc:  # noqa: BLE001 — pump must never die
            audit.error("flow scan failed: %s: %s", type(exc).__name__, exc)
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_s)
        except asyncio.TimeoutError:
            pass


# --------------------------------------------------------------------- #
# Loop-side handlers (ALL mutations live here)
# --------------------------------------------------------------------- #


async def handle_flow_event(ev: FlowEvent, *, pipeline: GatewayPipeline,
                            store: SessionsStore, relay_root: Path,
                            executor, audit) -> None:
    """Dispatch one flow event inside the sequential consumer."""
    if ev.kind == QUESTION_READY:
        await _handle_question_ready(ev, pipeline=pipeline, store=store,
                                     relay_root=relay_root, audit=audit)
    elif ev.kind == PAYLOAD_READY:
        await complete_session(ev.session_id, pipeline=pipeline, store=store,
                               relay_root=relay_root, executor=executor,
                               audit=audit)


async def _handle_question_ready(ev: FlowEvent, *, pipeline: GatewayPipeline,
                                 store: SessionsStore, relay_root: Path,
                                 audit) -> None:
    """Post one newly-spooled question (re-validated at dispatch)."""
    record = await asyncio.to_thread(store.load, ev.session_id)
    if record is None or record.is_terminal:
        return
    if str(int(ev.seq)) in record.question_messages:
        return  # already posted (duplicate/stale event)
    session = SessionDir(relay_root / ev.session_id)
    question = await asyncio.to_thread(session.read_question, ev.seq)
    if question is None:
        return
    answer = await asyncio.to_thread(session.read_answer, ev.seq)
    if answer is not None:
        return  # answered while queued (timeout/cancel) — nothing to post
    try:
        await pipeline.post_question(record, question)
    except RenderRejected as exc:
        # Contract 12 reject-with-reason: unblock the agent (terminal
        # cancelled answer — never-clobber) and surface in-thread; without
        # this the level-triggered scan would re-emit forever.
        cancelled = Answer(id=question.id, seq=question.seq,
                           status="cancelled")
        await asyncio.to_thread(session.write_answer, cancelled,
                                overwrite=False)
        await _thread_note_quiet(
            pipeline, record,
            MSG_QUESTION_UNRENDERABLE.format(reason=exc.reason), audit)


async def complete_session(session_id: str, *, pipeline: GatewayPipeline,
                           store: SessionsStore, relay_root: Path,
                           executor, audit) -> None:
    """The single completion sink (pump ``PAYLOAD_READY`` + death-with-
    payload both converge here).

    Order per ActionExecutor phase discipline: persist → platform →
    remove-dir. Fail-closed: any validation/creation failure terminates the
    session as ``failed`` with reason — nothing created, no fix-up.
    """
    record = await asyncio.to_thread(store.load, session_id)
    if record is None or record.is_terminal:
        return  # supersession guard — stale/duplicate arrival is a no-op
    session = SessionDir(relay_root / session_id)
    try:
        raw = await asyncio.to_thread(session.read_payload)
    except (OSError, ValueError, RelayError) as exc:
        audit.warning("payload read failed s=%s: %s", session_id, exc)
        raw = None
    if raw is None and not (session.path / "payload.json").exists():
        return  # not actually ready (stale event)

    record.state = "awaiting_payload"
    await asyncio.to_thread(store.save, record)
    audit.info("payload received session=%s — validating", session_id)

    metadata_dir = pipeline.repo_root / "aitasks" / "metadata"
    try:
        payload = validate_payload(raw, metadata_dir)
        created = await asyncio.to_thread(
            create_task_from_payload, payload,
            repo_root=pipeline.repo_root,
            initiator_tag=_tag(record.initiator_id),
            audit=audit,
            create_script=pipeline.create_script,
            push_argv=pipeline.push_argv,
        )
    except (PayloadRejected, TaskCreateError) as exc:
        await _fail_session(record, exc.reason, pipeline=pipeline,
                            store=store, executor=executor, audit=audit)
        return

    # Phase 1 — terminal persistence first.
    record.state = "done"
    await asyncio.to_thread(store.save, record)
    _kill_handle(pipeline, session_id, audit)
    # Phase 2 — platform (best-effort).
    summary = (f"✅ Task created: **{created.task_id}** — {payload.title}\n"
               f"`{created.path}`")
    await _thread_note_quiet(pipeline, record, summary, audit)
    await pipeline._set_status_reaction(record, STATUS_CREATED)
    # Phase 3 — spool + workspace cleanup.
    await asyncio.to_thread(executor._remove_relay_dir, session_id)
    audit.info("session %s done: task %s", session_id, created.task_id)


async def _fail_session(record, reason: str, *, pipeline: GatewayPipeline,
                        store: SessionsStore, executor, audit) -> None:
    """Fail-closed terminal path for invalid payload / failed creation."""
    sid = record.session_id
    record.state = "failed"
    await asyncio.to_thread(store.save, record)
    audit.error("session %s failed: %s", sid, reason)
    _kill_handle(pipeline, sid, audit)
    await _thread_note_quiet(pipeline, record,
                             MSG_SESSION_FAILED.format(reason=reason), audit)
    await pipeline._set_status_reaction(record, STATUS_FAILED)
    await asyncio.to_thread(executor._remove_relay_dir, sid)


def _kill_handle(pipeline: GatewayPipeline, session_id: str, audit) -> None:
    """Pop + kill the retained sandbox handle (best-effort)."""
    handle = pipeline.handles.pop(session_id, None)
    if handle is None:
        return
    try:
        handle.kill()
    except Exception as exc:  # noqa: BLE001 — backend-specific, best-effort
        audit.info("handle kill failed s=%s: %s", session_id, exc)


async def _thread_note_quiet(pipeline: GatewayPipeline, record,
                             text: str, audit) -> None:
    """Post into the session thread; audited, never raises."""
    if record.thread is None:
        return
    try:
        await pipeline.adapter.send_message(
            ConversationRef.from_dict(record.thread), text)
    except ChatError as exc:
        audit.info("thread note failed s=%s: %s", record.session_id, exc)
