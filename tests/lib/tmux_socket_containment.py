"""Socket containment for mocked tmux tests (t1216_4).

The shadow-spawn tests are mock-based: `launch_in_tmux`, `resolve_pane_id_by_pid`
and `attach_shadow_cleanup_hook` are patched, so no tmux call should ever leave
the process. The mocks are the primary protection. This mixin is the **belt**: if
a patch target is ever missed — the silent failure mode of the t1216_4 lift, since
patching a name in the wrong module intercepts nothing — the real call would go to
whatever socket the cached gateway holds, and with `AITASKS_TMUX_SOCKET` unset that
is the user's dedicated `-L ait` server carrying live agents.

`TmuxClient.__init__` resolves `tmux_socket_args()` **once** ("Cached once — never
recomputed per call", `lib/tmux_exec.py`), and several modules build a client at
import time, so setting the environment alone cannot redirect them: under full-suite
discovery any earlier module may already have imported `agent_launch_utils` and
pinned its `_TMUX` to `-L ait`. The singletons must therefore be **rebuilt** inside
the patched environment, mirroring the pattern documented at
`tests/test_launch_in_tmux_pane_pid.py::TestLaunchInTmuxIntegration`.

Containment is asserted **statically**, via the read-only `socket_args` property —
never by attempting a launch and observing that it fails, which could only discover
a leak by performing the mutation it is meant to prevent.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from unittest.mock import patch


class TmuxSocketContainmentMixin:
    """Rebuild import-time `_TMUX` singletons onto a throwaway socket.

    Subclasses list the modules holding a module-level `_TMUX` in
    ``CONTAINED_MODULES``. Call ``assert_contained()`` from a test to prove the
    redirection took effect.
    """

    SOCK = "ait_t1216_4_test"
    CONTAINED_MODULES: tuple = ()

    def setUp(self):  # noqa: D102  (fixture)
        super().setUp()
        self._tmpdir = tempfile.mkdtemp(prefix="ait_t1216_4_tmux_")
        # AIT_NO_SYSTEMD_RUN forces the setsid/plain rung: a systemd-run
        # transient unit would not inherit this test's TMUX_TMPDIR.
        self._env = patch.dict(
            os.environ,
            {"TMUX_TMPDIR": self._tmpdir,
             "AITASKS_TMUX_SOCKET": self.SOCK,
             "AIT_NO_SYSTEMD_RUN": "1"},
            clear=False,
        )
        self._env.start()
        os.environ.pop("TMUX", None)
        # Popped so a synthetic pane id in a test can never collide with a real
        # one, and so nothing can read an ambient companion pane.
        os.environ.pop("TMUX_PANE", None)
        self._saved_tmux = {}
        for mod in self.CONTAINED_MODULES:
            # Deliberately unguarded: a module listed here without a module-level
            # `_TMUX` (or without `TmuxClient` in scope) is an authoring error, and
            # silently skipping it would leave the caller believing it is contained.
            self._saved_tmux[mod] = mod._TMUX
            mod._TMUX = mod.TmuxClient()
        self.addCleanup(self._restore_tmux)

    def _restore_tmux(self):
        for mod, client in self._saved_tmux.items():
            mod._TMUX = client
        self._env.stop()
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def assert_contained(self):
        """Prove every contained singleton points at the throwaway socket."""
        for mod in self.CONTAINED_MODULES:
            self.assertEqual(
                mod._TMUX.socket_args, ["-L", self.SOCK],
                f"{mod.__name__}._TMUX not contained to the test socket",
            )
