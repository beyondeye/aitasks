"""View of questions waiting for an answer at the prompt.

For monitors. A form that timed out, failed or was deferred leaves nothing on
screen: the agent has said what is pending and ended its turn, and the pane
looks idle. The durable state says otherwise, so a monitor can show the pane
as waiting on the user.

Which pane? A record comes back with an `association` saying how sure that is:

  process     the serving process is stamped on the record (owner.py). When
              the client runs in-process, the pane's own process is its
              ancestor. This is the question of the conversation in the pane.
  candidate   a daemon-hosted server (`detached`, see owner.py) has no process
              in the pane, and the client exposes no identity of the
              conversation it shows (measured on codex 0.167.2 and 0.168.0: no
              argv, open file, environment or log row links a terminal client
              to its thread). Nothing can say WHICH client such a question
              belongs to, so none is picked: every pane whose foreground
              process could be its client is reported as a candidate - a codex
              client that runs no sessions in its own process tree (an
              in-process client has its own questions, tied by ancestry, or
              none) and whose working directory is inside the question's
              project.

              What a pane displays is not evidence: a question's id on screen
              may be a quotation, and is gone after a scroll or a restart. A
              candidate is derived from running processes alone, so it needs
              no earlier sighting, is the same in every monitor, and ends when
              the pane's program does.

A record counts only while all of these hold, so the indicator clears itself:
  * the occurrence is in a WAITING state - an accepted answer, a cancellation,
    an invalidation or a re-opened form all leave it;
  * the process stamped on it is still running (a closed or restarted client
    is not waiting; a resumed one re-stamps the question when it touches it).

Writes nothing, never creates the state directory, and reports nothing rather
than raise: this is an advisory signal read on a monitor's refresh path.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import time

from . import owner as owner_identity

WAITING_STATES = ("awaiting-chat-answer", "deferred")  # mirrors store.WAITING_STATES
# Surfaced as a snapshot's awaiting_input_kind, by association.
KIND = "codex_question_at_prompt"
CANDIDATE_KIND = "codex_question_unassociated"


def default_state_dir():
    """Same resolution as the launcher, aitask_questions_mcp.sh."""
    explicit = os.environ.get("AIT_QUESTIONS_STATE_DIR")
    if explicit:
        return Path(explicit)
    base = os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")
    return Path(base) / "aitasks" / "questions"


def waiting(state_dir):
    """Questions waiting at the prompt whose server is alive: list of dicts."""
    db = Path(state_dir) / "questions.sqlite3"
    if not db.is_file():
        return []
    try:
        conn = sqlite3.connect(f"{db.as_uri()}?mode=ro", uri=True, timeout=0.2)
        try:
            rows = conn.execute("SELECT body FROM sessions").fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return []
    found = []
    for (text,) in rows:
        try:
            body = json.loads(text)
            stamp = body.get("waiting")
            if body.get("state") not in WAITING_STATES or not isinstance(stamp, dict):
                continue
            if not owner_identity.alive(stamp):
                continue
            found.append({"session_id": str(body["id"]), "workflow": body["workflow"],
                          "checkpoint": body["checkpoint"], "project": body["project"],
                          "pid": int(stamp["pid"]),
                          "detached": bool(stamp.get("detached")),
                          "ancestors": [int(pid) for pid in stamp.get("ancestors", [])]})
        except (TypeError, ValueError, KeyError, AttributeError):
            continue
    return found


PROCESS = "process"      # the question of the conversation in this pane
CANDIDATE = "candidate"  # a question some hand-started client in this project holds


class Watcher:
    """`waiting()` behind a short cache, keyed for per-pane lookups."""

    def __init__(self, state_dir=None, ttl=2.0):
        self.state_dir = state_dir
        self.ttl = ttl
        self._at = None
        self._records = []

    def for_pane(self, pane_pid):
        """A waiting question for this pane with its `association`, or None.

        pane_pid is the pane's top-level process. `process` records come
        first: a pane that serves a waiting question is never reported as a
        mere candidate for another one.
        """
        now = time.monotonic()
        if self._at is None or now - self._at > self.ttl:
            self._records = waiting(Path(self.state_dir or default_state_dir()))
            self._at = now
        if not isinstance(pane_pid, int) or pane_pid <= 1:
            return None
        for record in self._records:
            if pane_pid in record["ancestors"] or pane_pid == record["pid"]:
                return {**record, "association": PROCESS}
        hosted = [record for record in self._records if record["detached"]]
        if not hosted:
            return None
        client = owner_identity.foreground(pane_pid)
        if not client or not owner_identity.is_client(owner_identity._argv(client["pid"])) \
                or owner_identity.hosts_sessions(client["pid"]):
            return None
        for record in hosted:
            if owner_identity.inside(client["pid"], record["project"]):
                return {**record, "association": CANDIDATE}
        return None
