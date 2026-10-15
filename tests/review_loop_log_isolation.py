"""Module-scoped isolation of the durable review-loop event store (t2001).

Any test that drives ``MiniMonitorApp._loop_auto_disarm`` / ``_loop_hold``
appends a record through ``review_loop_log.record_event``. Without a redirect
that lands in the user's real ``~/.config/aitasks/review_loop_events/``, and
because retention keeps only ``MAX_SESSION_FILES`` session files, every test
run evicts real diagnostic history. Per-class redirects are not enough: one
class without it is a leak, and that is how the leak happened.

Call :func:`isolate_event_store` from ``setUpModule`` and the returned restore
from ``tearDownModule``. Both the pytest and the unittest-discover backends
honour that pair, so the redirect covers the whole module whichever runner
executes it.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Callable


def isolate_event_store(rll) -> tuple[Path, Callable[[], None]]:
    """Point the store at a private directory; return ``(dir, restore)``.

    ``rll`` is the ``review_loop_log`` module OBJECT the code under test
    writes through (``minimonitor_app.review_loop_log``). Passing it, rather
    than importing a fresh copy here, is what guarantees the memoized session
    path being reset is the one the app actually uses.
    """
    tmp = tempfile.TemporaryDirectory(prefix="ait_loop_events_")
    events_dir = Path(tmp.name) / "events"
    env = rll.LOG_DIR_ENV
    previous = os.environ.get(env)
    os.environ[env] = str(events_dir)
    # A session path memoized before this module ran would keep pointing at
    # whatever directory was in force then — possibly the real one.
    rll.reset_session_for_tests()

    def restore() -> None:
        if previous is None:
            os.environ.pop(env, None)
        else:
            os.environ[env] = previous
        rll.reset_session_for_tests()
        tmp.cleanup()

    return events_dir, restore
