"""Live-terminal harness for minimonitor's companion width pin (t2050).

Runs INSIDE a tmux pane, under a real pty, so a real window resize reaches the
real `MiniMonitorApp.on_resize` as a real SIGWINCH, and the pin's
`resize-pane` goes through the real gateway (`TmuxMonitor.resize_pane`) to the
real tmux server the pane lives on.

WHAT IS AND IS NOT EXERCISED. The app is the real `MiniMonitorApp`. `TMUX` is
popped at import, so the real `on_mount` takes its "Not inside tmux" early
return — no marker stamping, no refresh timer, no auto-close (which would
otherwise judge a window holding a plain shell and close it). After mount the
harness installs a real `TmuxMonitor` itself, which is the only collaborator the
pin reaches. `main()`'s config load and tmux detection are NOT exercised; the
pin, the gateway and tmux are.

Instrumentation lives HERE, not in production code: ``trace.jsonl`` under
``--out-dir`` gets a ``{"event": "ready"}`` line once the monitor is installed,
then one ``{"event": "pin", "width": …, "stale": …}`` line per
`_maybe_pin_width` call (``stale`` is `self.size.width` at that moment).

``AIT_T2050_LEGACY_PIN=1`` swaps in the PRE-FIX decision — `self.size.width`
instead of the event's width — so the fixture can be shown to reproduce the
drift before it is trusted to show the fix. It overrides `_maybe_pin_width`, not
`on_resize`: Textual runs every class's `on_resize` in the MRO, so a subclass
override would not suppress the production handler. The replica is test-local
and used only as a negative control.

Usage (the test drives this; see tests/test_minimonitor_width_pin_live.py):

    python3 tests/lib/minimonitor_width_pin_harness.py --out-dir DIR
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

# TMUX_PANE is KEPT: the pin reads it to target its own pane.
os.environ.pop("TMUX", None)

from monitor import minimonitor_app as mm  # noqa: E402
from monitor.monitor_core import TmuxMonitor  # noqa: E402

TARGET_WIDTH = 40


class WidthPinHarnessApp(mm.MiniMonitorApp):

    def __init__(self, out_dir: Path, legacy: bool) -> None:
        super().__init__(session="t2050", project_root=REPO_ROOT,
                         target_width=TARGET_WIDTH)
        self._out_dir = out_dir
        self._legacy = legacy
        self._trace_path = out_dir / "trace.jsonl"

    def _emit(self, record: dict) -> None:
        with self._trace_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    def on_mount(self) -> None:
        # Runs alongside (not instead of) the production on_mount, which has
        # already taken its no-TMUX early return. The real gateway honours
        # AITASKS_TMUX_SOCKET, so it stays on the test's private server.
        self._monitor = TmuxMonitor(session="t2050")
        self._emit({"event": "ready", "size": list(self.size),
                    "legacy": self._legacy})

    def _maybe_pin_width(self, width: int) -> None:
        self._emit({"event": "pin", "width": width,
                    "stale": self.size.width})
        if self._legacy:
            # Pre-fix body verbatim, apart from the unused argument.
            if self._monitor is None:
                return
            own_pane = os.environ.get("TMUX_PANE")
            if not own_pane:
                return
            if self.size.width <= self._target_width:
                return
            self._monitor.resize_pane(own_pane, x=self._target_width)
            return
        super()._maybe_pin_width(width)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    legacy = os.environ.get("AIT_T2050_LEGACY_PIN") == "1"
    WidthPinHarnessApp(args.out_dir, legacy).run()


if __name__ == "__main__":
    main()
