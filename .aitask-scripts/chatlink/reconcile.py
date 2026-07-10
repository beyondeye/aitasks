"""Pure reconciliation planners for the chatlink gateway (t1120_3).

Pure planners — **no I/O anywhere in this module** — turn observed state
into an ordered list of :class:`Action`\\ s the daemon-side executor applies:

- :func:`plan_startup_actions` — the crash-ownership pass that runs BEFORE
  the intake loop starts: sessions with no live agent are failed, pending
  questions get ``cancelled`` answers (spool hygiene), half-created /
  corrupt records are resolved fail-closed (never resumed), record outcome
  bookkeeping is healed FROM the spool (the spool is the source of truth),
  and stale relay dirs are removed only after terminal persistence.
- :func:`plan_reconnect_actions` — the re-query pass after a ``subscribe``
  stream drop: missed intake messages are recovered from a
  ``fetch_history(after=)`` diff, cursors advance, and every still-pending
  question is re-prompted (missed INTERACTION_RECEIVED events are lost —
  the documented non-replayable case — so re-prompt, never assume replay).
- :func:`plan_agent_death_actions` — the mid-life death pass (t1120_5):
  the launcher backend's watchdog signals an observed sandbox death; the
  daemon dispatches this planner from its sequential loop and the executor
  applies the same fail-closed treatment as the startup branch.

Executor phase discipline (pinned in p1120_3 — the planners tag, the
executor enforces): per session, phase ``1`` (terminal persistence:
must-succeed record writes + cancelled-answer spool writes) strictly
precedes phase ``2`` (best-effort platform cleanup / re-prompts) which
precedes phase ``3`` (relay-dir removal). A phase-1 failure skips that
session's phases 2–3 entirely — cleanup never runs on unpersisted state.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .sessions_store import SessionRecord

# Executor phases (see module docstring).
PHASE_PERSIST = 1
PHASE_PLATFORM = 2
PHASE_REMOVE_DIR = 3

# Action kinds — phase 1 (terminal persistence).
MARK_FAILED = "mark_failed"                 # payload: {reason}
WRITE_CANCELLED_ANSWER = "write_cancelled_answer"  # payload: {seq}
HEAL_OUTCOME = "heal_outcome"               # payload: {seq, answer}
ADVANCE_CURSOR = "advance_cursor"           # payload: {conversation, message_id}
# Action kinds — phase 2 (best-effort platform).
DISABLE_COMPONENTS = "disable_components"   # payload: {seq, message}
REACT_FAILED = "react_failed"               # payload: {message, prev_reaction}
REPOST_QUESTION = "repost_question"         # payload: {seq}
PROCESS_MESSAGE = "process_message"         # payload: {message} (raw event msg)
# Action kinds — phase 3 (cleanup).
REMOVE_RELAY_DIR = "remove_relay_dir"       # payload: {reason}

_PHASES = {
    MARK_FAILED: PHASE_PERSIST,
    WRITE_CANCELLED_ANSWER: PHASE_PERSIST,
    HEAL_OUTCOME: PHASE_PERSIST,
    ADVANCE_CURSOR: PHASE_PERSIST,
    DISABLE_COMPONENTS: PHASE_PLATFORM,
    REACT_FAILED: PHASE_PLATFORM,
    REPOST_QUESTION: PHASE_PLATFORM,
    PROCESS_MESSAGE: PHASE_PLATFORM,
    REMOVE_RELAY_DIR: PHASE_REMOVE_DIR,
}

FAIL_REASON_NO_LIVE_AGENT = "no_live_agent"
FAIL_REASON_CORRUPT_RECORD = "corrupt_record"
FAIL_REASON_AGENT_DIED = "agent_died"
REMOVE_REASON_ORPHAN_DIR = "orphan_relay_dir"
REMOVE_REASON_TERMINAL = "terminal_session"


@dataclass(frozen=True)
class Action:
    """One executor instruction. ``phase`` is derived from ``kind``."""

    kind: str
    session_id: str
    payload: dict = field(default_factory=dict)

    @property
    def phase(self) -> int:
        return _PHASES[self.kind]


@dataclass(frozen=True)
class SpoolScan:
    """Pure snapshot of one relay session dir (built by the daemon from
    ``relay.SessionDir`` — planners never touch the filesystem).

    ``pending_seqs``: question present ∧ answer absent.
    ``answers``: seq → answer dict for every existing answer file.
    """

    session_id: str
    pending_seqs: tuple = ()
    answers: dict = field(default_factory=dict)


def _heal_actions(record: SessionRecord, scan: SpoolScan | None) -> list[Action]:
    """Record-outcome bookkeeping healed FROM the spool (source of truth)."""
    if scan is None:
        return []
    out = []
    for seq, answer in sorted(scan.answers.items()):
        if not record.has_outcome(int(seq)):
            out.append(Action(HEAL_OUTCOME, record.session_id,
                              {"seq": int(seq), "answer": dict(answer)}))
    return out


def _cancel_and_disable(record_or_id, scan: SpoolScan | None,
                        question_messages: dict) -> list[Action]:
    """Cancelled answers (phase 1) + component disabling (phase 2) for every
    pending question of a session being failed."""
    sid = record_or_id if isinstance(record_or_id, str) else record_or_id.session_id
    out = []
    if scan is not None:
        for seq in sorted(scan.pending_seqs):
            out.append(Action(WRITE_CANCELLED_ANSWER, sid, {"seq": int(seq)}))
            msg = question_messages.get(str(int(seq)))
            if msg is not None:
                out.append(Action(DISABLE_COMPONENTS, sid,
                                  {"seq": int(seq), "message": msg}))
    return out


def plan_startup_actions(
    records: list[SessionRecord],
    corrupt_ids: list[str],
    live_session_ids: set,
    relay_scans: dict,
) -> list[Action]:
    """The startup reconciliation pass (see module docstring).

    ``relay_scans``: session_id → :class:`SpoolScan` for every relay dir on
    disk (including dirs with no record — orphans). ``live_session_ids``:
    sessions the launcher seam reports as having a live agent.
    """
    actions: list[Action] = []
    record_ids = set()

    for rec in records:
        record_ids.add(rec.session_id)
        scan = relay_scans.get(rec.session_id)
        actions.extend(_heal_actions(rec, scan))
        if rec.is_terminal:
            # Terminal state already persisted — only stale-dir cleanup.
            if scan is not None:
                actions.append(Action(REMOVE_RELAY_DIR, rec.session_id,
                                      {"reason": REMOVE_REASON_TERMINAL}))
            continue
        if rec.session_id in live_session_ids:
            continue  # live agent — session carries on untouched
        # Non-terminal with no live agent: fail closed.
        actions.extend(
            _cancel_and_disable(rec, scan, rec.question_messages))
        actions.append(Action(MARK_FAILED, rec.session_id,
                              {"reason": FAIL_REASON_NO_LIVE_AGENT}))
        if rec.bug_report_message is not None:
            actions.append(Action(REACT_FAILED, rec.session_id,
                                  {"message": rec.bug_report_message,
                                   "prev_reaction": rec.status_reaction}))
        if scan is not None:
            actions.append(Action(REMOVE_RELAY_DIR, rec.session_id,
                                  {"reason": FAIL_REASON_NO_LIVE_AGENT}))

    # Corrupt records: half-created sessions — fail-closed, never resumed.
    for sid in corrupt_ids:
        scan = relay_scans.get(sid)
        actions.extend(_cancel_and_disable(sid, scan, {}))
        actions.append(Action(MARK_FAILED, sid,
                              {"reason": FAIL_REASON_CORRUPT_RECORD}))
        if scan is not None:
            actions.append(Action(REMOVE_RELAY_DIR, sid,
                                  {"reason": FAIL_REASON_CORRUPT_RECORD}))

    # Relay dirs with no record at all (crash between mint and persist):
    # spool hygiene + removal. There is no record to mark failed.
    for sid, scan in sorted(relay_scans.items()):
        if sid in record_ids or sid in corrupt_ids:
            continue
        actions.extend(_cancel_and_disable(sid, scan, {}))
        actions.append(Action(REMOVE_RELAY_DIR, sid,
                              {"reason": REMOVE_REASON_ORPHAN_DIR}))

    return actions


def plan_agent_death_actions(
    record: SessionRecord | None,
    scan: SpoolScan | None,
) -> list[Action]:
    """Mid-life agent-death pass (t1120_5): the daemon consumes the
    backend's death signal from its sequential dispatch loop and applies
    the same fail-closed treatment as startup's non-terminal-no-live-agent
    branch — outcome healing, cancelled answers + component disabling,
    ``MARK_FAILED``, the ❌ reaction, and relay-dir removal.

    ``[]`` when the record is absent or already terminal: a stale or
    duplicate death signal (e.g. the session completed between the
    watchdog's observation and this dispatch) is a no-op by construction —
    the idempotent supersession guard.
    """
    if record is None or record.is_terminal:
        return []
    actions = _heal_actions(record, scan)
    actions.extend(_cancel_and_disable(record, scan, record.question_messages))
    actions.append(Action(MARK_FAILED, record.session_id,
                          {"reason": FAIL_REASON_AGENT_DIED}))
    if record.bug_report_message is not None:
        actions.append(Action(REACT_FAILED, record.session_id,
                              {"message": record.bug_report_message,
                               "prev_reaction": record.status_reaction}))
    if scan is not None:
        actions.append(Action(REMOVE_RELAY_DIR, record.session_id,
                              {"reason": FAIL_REASON_AGENT_DIED}))
    return actions


def plan_reconnect_actions(
    records: list[SessionRecord],
    fetched_messages: list[dict],
    relay_scans: dict | None = None,
) -> list[Action]:
    """The post-disconnect re-query pass (see module docstring).

    ``fetched_messages``: normalized message dicts from the daemon's
    ``fetch_history(after=last_seen)`` sweep of the intake channel —
    ``{"conversation": <ref dict>, "message_id": str, "author_is_self":
    bool, "author_is_bot": bool, "raw": <opaque>}`` in chronological order.
    Self/bot messages advance the cursor but are never processed
    (self-trigger-loop protection lives here too — the planner is the
    single filter for the recovery path).

    Every still-pending question is re-prompted: INTERACTION_RECEIVED is
    non-replayable, so a missed window can only be recovered by re-posting
    the components. ``relay_scans`` (session_id → :class:`SpoolScan`)
    supplies the pending set; ``None`` means no spool state was gathered
    (no re-prompts planned).
    """
    actions: list[Action] = []

    # Handle-then-advance, PER MESSAGE (matching the live path's ordering):
    # each recovered message is processed BEFORE its cursor advance is
    # persisted, so a crash mid-recovery re-fetches the unhandled message
    # instead of permanently skipping it. Self/bot messages advance the
    # cursor without processing. The executor preserves this emitted order
    # for global (sessionless) actions — it must NOT phase-sort them.
    for msg in fetched_messages:
        if not msg.get("author_is_self") and not msg.get("author_is_bot"):
            actions.append(Action(PROCESS_MESSAGE, "", {"message": msg}))
        actions.append(Action(ADVANCE_CURSOR, "",
                              {"conversation": dict(msg.get("conversation") or {}),
                               "message_id": msg.get("message_id")}))

    if relay_scans:
        for rec in records:
            if rec.is_terminal:
                continue
            scan = relay_scans.get(rec.session_id)
            if scan is None:
                continue
            actions.extend(_heal_actions(rec, scan))
            for seq in sorted(scan.pending_seqs):
                actions.append(Action(REPOST_QUESTION, rec.session_id,
                                      {"seq": int(seq)}))

    return actions


def order_for_execution(actions: list[Action]) -> list[Action]:
    """Stable phase-major ordering (the executor's iteration order)."""
    return sorted(actions, key=lambda a: a.phase)
