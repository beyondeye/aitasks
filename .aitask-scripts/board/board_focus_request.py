"""board_focus_request.py - `ait board --focus <id>` and the board's pane mailbox (t2211_3).

Two routes put a task card under focus from outside the board:

* **cold** -- `ait board --focus <id>`: the board selects the card after its
  first load;
* **warm** -- a request written to a RUNNING board's pane mailbox by
  `agent_launch_utils.launch_or_focus_board` (the sitrep TUI's "open in
  board"). The design is the `ait trails` one (t1957_2): the board stamps its
  own pane `@aitask_board_app <pid>` after a baseline read, polls
  `@aitask_board_focus "<32-hex id> <task id>"`, and acts on a request id it
  has not seen; the latest request wins, nobody ever unsets the request.

Host contract (KanbanApp): ``manager`` (``find_task_by_id`` /
``find_task_including_archived``), ``expanded_tasks``, ``refresh_board``,
``_queue_refocus``, ``_focused_card``, ``_modal_is_active``. Flat-imported like
every board module; never imports ``aitask_board``.
"""

from __future__ import annotations

import re

from textual import work

from agent_launch_utils import (
    mark_board_receiver,
    pane_on_gateway_server,
    parse_board_focus_request,
    read_board_focus_request,
    unmark_board_receiver,
)

#: Seconds between mailbox reads (one `display-message` on the board's own pane).
BOARD_FOCUS_POLL_SECONDS = 1.0

#: Layout passes to wait for the focused card before calling it hidden.
_FOCUS_VERIFY_HOPS = 5

_TASK_ID_RE = re.compile(r"^t?([0-9]+(?:_[0-9]+)?)\Z")


def normalize_task_id(value: str | None) -> str | None:
    """``"t12_3"`` / ``"12_3"`` -> ``"12_3"``; anything else -> None."""
    m = _TASK_ID_RE.match((value or "").strip())
    return m.group(1) if m else None


class BoardFocusMailboxMixin:
    """`--focus` + the pane mailbox, mixed into ``KanbanApp``."""

    def _init_focus_request(self, focus_task: str | None = None,
                            focus_pane: str | None = None,
                            focus_tmux_env: str = "") -> None:
        #: The cold `--focus` id (already normalized), applied after mount.
        self._initial_focus_task = focus_task
        self._focus_req_pane = focus_pane or None
        self._focus_req_tmux_env = focus_tmux_env or ""
        self._focus_req_seen: str | None = None
        self._focus_req_stamped = False
        self._focus_req_timer = None
        self._focus_req_busy = False
        #: A request that arrived while a modal was open: applied on resume.
        self._pending_focus_task: str | None = None

    def _start_focus_request(self) -> None:
        """From on_mount, after the startup focus claim was queued."""
        if self._initial_focus_task:
            self.call_after_refresh(self.focus_task_by_id, self._initial_focus_task)
        if self._focus_req_pane:
            self._focus_req_register_worker(self._focus_req_pane, self._focus_req_tmux_env)

    def _stop_focus_request(self) -> None:
        if self._focus_req_timer is not None:
            self._focus_req_timer.stop()
            self._focus_req_timer = None
        if self._focus_req_stamped and self._focus_req_pane:
            # Best effort; a stamp left by a crash is ignored once its pid is gone.
            unmark_board_receiver(self._focus_req_pane)
            self._focus_req_stamped = False

    # -- the mailbox -----------------------------------------------------------

    @work(thread=True, group="board_focus_request")
    def _focus_req_register_worker(self, pane: str, tmux_env: str):
        """Verify the pane, read the baseline, THEN stamp (trails' order: a
        request left in this pane by an earlier board is recorded as seen,
        never replayed; a failed read stops here -- fail closed)."""
        if not pane_on_gateway_server(pane, tmux_env):
            return
        baseline = read_board_focus_request(pane)
        if baseline is None:
            return
        stamped = mark_board_receiver(pane)
        self.call_from_thread(self._on_focus_req_registered, baseline, stamped)

    def _on_focus_req_registered(self, baseline: str, stamped: bool) -> None:
        parsed = parse_board_focus_request(baseline)
        self._focus_req_seen = parsed[0] if parsed else None
        if not stamped:
            return
        self._focus_req_stamped = True
        self._focus_req_timer = self.set_interval(BOARD_FOCUS_POLL_SECONDS,
                                                  self._poll_focus_req)

    def _poll_focus_req(self) -> None:
        if self._focus_req_busy or not self._focus_req_stamped:
            return
        self._focus_req_busy = True
        self._focus_req_poll_worker(self._focus_req_pane)

    @work(thread=True, group="board_focus_request")
    def _focus_req_poll_worker(self, pane: str):
        """Read this App's OWN pane mailbox -- never another pane's."""
        self.call_from_thread(self._on_focus_req_value, read_board_focus_request(pane))

    def _on_focus_req_value(self, value: str | None) -> None:
        self._focus_req_busy = False
        parsed = parse_board_focus_request(value)
        if parsed is None:
            return
        request_id, task_id = parsed
        if request_id == self._focus_req_seen:
            return
        self._focus_req_seen = request_id
        if task_id is None:
            self.notify("Ignored a malformed board focus request", severity="warning")
            return
        self.focus_task_by_id(task_id)

    # -- focusing a card ---------------------------------------------------------

    def focus_task_by_id(self, task_id: str) -> None:
        """Select and scroll to ``task_id``'s card (``12`` or ``12_3``).

        A child's parent is expanded first. An archived or unknown id, and a
        card the current view hides (a filter, a collapsed column, a trail
        view), are reported -- never silently ignored. Behind a modal the
        request waits for the modal to close."""
        task_id = normalize_task_id(task_id)
        if task_id is None:
            return
        if self._modal_is_active():
            self._pending_focus_task = task_id
            self.notify(f"t{task_id} will be shown when this dialog closes", markup=False)
            return
        self._pending_focus_task = None
        task = self.manager.find_task_by_id(f"t{task_id}")
        if task is None:
            if self.manager.find_task_including_archived(f"t{task_id}") is not None:
                self.notify(f"t{task_id} is archived — it is not on the board",
                            severity="warning", markup=False)
            else:
                self.notify(f"t{task_id} not found", severity="warning", markup=False)
            return
        filename = task.filename
        parent_id = task_id.split("_", 1)[0] if "_" in task_id else None
        parent = self.manager.find_task_by_id(f"t{parent_id}") if parent_id else None
        if parent is not None and parent.filename not in self.expanded_tasks:
            self.expanded_tasks.add(parent.filename)
            self.refresh_board(refocus_filename=filename)
        else:
            self._queue_refocus(filename)
        self.call_after_refresh(self._verify_focus_task, task_id, filename,
                                _FOCUS_VERIFY_HOPS)

    def _verify_focus_task(self, task_id: str, filename: str, hops: int) -> None:
        card = self._focused_card()
        if card is not None and card.task_data.filename == filename:
            return
        if hops > 0:
            self.call_after_refresh(self._verify_focus_task, task_id, filename, hops - 1)
            return
        self.notify(f"t{task_id} is not visible in the current view (a filter, a "
                    "collapsed column or a trail view hides it)",
                    severity="warning", markup=False)

    def _resume_focus_request(self) -> None:
        """A modal closed: apply the request it held back."""
        pending, self._pending_focus_task = self._pending_focus_task, None
        if pending and not self._modal_is_active():
            self.focus_task_by_id(pending)
