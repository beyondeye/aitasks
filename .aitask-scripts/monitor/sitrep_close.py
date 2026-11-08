"""Harvest-and-close and the sitrep key for the monitor TUIs (t2175_5).

`h` on an agent harvests what that agent left in its terminal into the
repository's sitrep store, SHOWS what was captured, and only then offers to
close it. `S` opens (or switches to) the repository's sitrep window.

The order is the contract: capture first, then confirm. A failed capture or
harvest never offers a close — the dialog has no affirmative button for it and
the confirm callback re-checks the report. Live sitrep windows are never
harvested (the sitrep screen only echoes its own store back).

What is closed is the agent RUN that was harvested, not whatever later sits in
its pane: a :class:`~monitor.monitor_core.RunIdentity` is read before and after
the harvest, a frozen record must still be the same record at confirm time, and
a live close goes through the guarded
:meth:`~monitor.monitor_core.TmuxMonitor.kill_agent_run_guarded`.

The harvest runs through :func:`run_owned_group`: its own process group, killed
as a group on timeout AND on cancellation (Textual cancels workers at app exit),
because the harvest wrapper spawns Python children that hold the store mutex.

See ``aidocs/framework/sitrep.md`` ("The monitor surface").
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import os
import signal
import sys
from dataclasses import dataclass, field
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent.parent
_LIB_DIR = _SCRIPT_DIR / "lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

import sitrep_harvest  # noqa: E402
import sitrep_todo  # noqa: E402
# The `ait sitrep open` wording is shared with the TUI switcher, which lives in
# lib/ and cannot import this package — so it lives there.
from sitrep_cli import sitrep_open_message  # noqa: E402,F401
from guarded_dismiss import GuardedModalScreen  # noqa: E402

from monitor.monitor_core import (  # noqa: E402
    FROZEN_OPTION,
    RUN_IDENTITY_FORMAT,
    PaneCategory,
    RunIdentity,
    parse_run_identity,
    task_ref_from_window_name,
)

from textual.app import ComposeResult  # noqa: E402
from textual.binding import Binding  # noqa: E402
from textual.containers import Container, VerticalScroll  # noqa: E402
from textual.content import Content  # noqa: E402
from textual.widgets import Button, Static  # noqa: E402


#: The harvest helper (`record` / `capture` / `all`), and `ait sitrep`.
SITREP_HARVEST_SH = _SCRIPT_DIR / "aitask_sitrep_harvest.sh"
SITREP_SH = _SCRIPT_DIR / "aitask_sitrep.sh"

#: Budget for ONE `record` / `capture`: above the helper's own mutex wait
#: (20 s), one writer call (60 s) and its 20 s git / projects calls. The drop's
#: own pre-kill harvest runs on 120 s (`agent_freeze.HARVEST_TIMEOUT_DROP`).
HARVEST_ONE_TIMEOUT = 150.0
#: Budget for the maintenance `all` pass (every record still holding text).
HARVEST_ALL_TIMEOUT = 300.0
#: Live-pane capture depth: the freeze engine's default (`frozen.capture_max_lines`
#: in `agent_freeze`), so a live harvest sees what a freeze would have kept.
HARVEST_CAPTURE_LINES = 50000
#: The capture itself is one tmux call returning up to that many lines.
HARVEST_CAPTURE_TIMEOUT = 30.0
#: `ait sitrep open` launches an agent and waits for its stamp.
SITREP_OPEN_TIMEOUT = 45.0


# -- the owned-group runner ---------------------------------------------------

async def _terminate_group(proc) -> None:
    """SIGKILL the process group ``proc`` leads, then reap ``proc``.

    Called from BOTH the timeout and the cancellation exit. The group is
    killed even when the leader already exited: a grandchild can still hold
    the store mutex, and a pid stays reserved while it is a live group's id, so
    ``killpg`` can never reach an unrelated process. The kill is synchronous,
    so it lands even if the reaping ``await`` is cancelled in turn.
    """
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(proc.pid, signal.SIGKILL)
    with contextlib.suppress(Exception):
        await proc.wait()


async def run_owned_group(argv: "list[str]", *, stdin: "bytes | None" = None,
                          timeout: float) -> "tuple[int, str]":
    """Run ``argv`` in its OWN process group; ``(rc, stdout+stderr)``.

    Total for every ordinary failure — a missing script and a timeout come back
    as ``(1, "ERROR:…")`` — but NOT for cancellation: an
    ``asyncio.CancelledError`` (Textual cancels workers when the app exits, and
    ``wait_for`` does not touch the child) kills the whole group and is then
    re-raised, never swallowed. Without that branch a ``start_new_session``
    group would outlive the TUI with no supervisor left to bound it.
    """
    name = Path(argv[0]).name
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdin=(asyncio.subprocess.PIPE if stdin is not None
                   else asyncio.subprocess.DEVNULL),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,
        )
    except OSError as exc:
        return 1, f"ERROR:cannot run {name}: {exc}"
    try:
        out, _ = await asyncio.wait_for(proc.communicate(stdin), timeout=timeout)
    except asyncio.TimeoutError:
        await _terminate_group(proc)
        return 1, f"ERROR:{name} timed out after {timeout:g}s"
    except asyncio.CancelledError:
        await _terminate_group(proc)
        raise
    return proc.returncode or 0, out.decode("utf-8", "replace").strip()


# -- the report ---------------------------------------------------------------

@dataclass(frozen=True)
class HarvestItem:
    cid: str
    status: str      # added | exists
    kind: str
    ref: str


#: Final-line kinds the helper prints, plus the three this module produces
#: itself: `missing` (no final line), `skipped` (a sitrep window — nothing was
#: run) and `failed` (the capture or the run identity failed before a harvest).
_HELPER_FINALS = ("HARVESTED", "HARVEST_NONE", "HARVEST_FAILED")


@dataclass(frozen=True)
class HarvestReview:
    """A `HARVEST_REVIEW:` line (t2175_6): uncertain output kept verbatim in
    the store with one review item for the sitrep agent."""
    cid: str
    status: str      # added | exists
    case: str
    codes: str


@dataclass(frozen=True)
class HarvestReport:
    final_kind: str
    reason: str = ""
    rc: int = 0
    items: tuple = ()
    warns: tuple = ()
    added: int = 0
    existing: int = 0
    reviews: tuple = ()

    @property
    def ok(self) -> bool:
        """Whether the agent's output is safely in the store (or need not be).

        `skipped` (a sitrep window) is ok without a run. Otherwise BOTH the
        exit status and the last final line must say so: a `HARVESTED` line
        under a non-zero exit, or no final line at all, is not proof.
        """
        if self.final_kind == "skipped":
            return True
        return self.rc == 0 and self.final_kind in ("HARVESTED", "HARVEST_NONE")

    @classmethod
    def skipped(cls, reason: str) -> "HarvestReport":
        return cls(final_kind="skipped", reason=reason)

    @classmethod
    def failed(cls, reason: str) -> "HarvestReport":
        return cls(final_kind="failed", reason=reason, rc=1)

    def verdict(self) -> str:
        """One plain-text line naming the outcome (toast and dialog)."""
        if self.final_kind == "skipped":
            return "Sitrep agent — not harvested"
        if not self.ok:
            return f"HARVEST FAILED: {self.reason or 'unknown'} — the agent is kept"
        if self.final_kind == "HARVESTED":
            base = f"Harvested: {self.added} added, {self.existing} existing"
            if self.reviews:
                cids = ", ".join(r.cid for r in self.reviews)
                return f"{base} — output kept for sitrep review ({cids})"
            return base
        if self.reviews:
            cids = ", ".join(r.cid for r in self.reviews)
            return (f"Nothing new to harvest ({self.reason or 'none'}) — output "
                    f"kept for sitrep review ({cids})")
        return f"Nothing to harvest ({self.reason or 'none'})"


def parse_harvest_output(rc: int, out: str) -> HarvestReport:
    """Read `aitask_sitrep_harvest.sh` output (its header is the contract).

    Only the LAST final line counts. A runner ``ERROR:`` line, a missing final
    line or a non-zero exit is never ok; ``reason`` names which.
    """
    items: list = []
    warns: list = []
    reviews: list = []
    final_kind, reason = "missing", ""
    added = existing = 0
    runner_error = ""
    for raw in out.splitlines():
        line = raw.strip()
        if line.startswith("ERROR:"):
            runner_error = line[len("ERROR:"):]
            continue
        head, sep, rest = line.partition(":")
        if not sep:
            continue
        if head == "HARVEST_ITEM":
            parts = rest.split("|", 4)
            if len(parts) == 5:
                items.append(HarvestItem(parts[1], parts[2], parts[3], parts[4]))
        elif head == "HARVEST_WARN":
            _src, _, why = rest.partition("|")
            warns.append(why or rest)
        elif head == "HARVEST_REVIEW":
            parts = rest.split("|", 4)
            if len(parts) == 5 and parts[3].startswith("case="):
                reviews.append(HarvestReview(parts[1], parts[2],
                                             parts[3][len("case="):], parts[4]))
        elif head in _HELPER_FINALS:
            final_kind = head
            _src, _, tail = rest.partition("|")
            reason, added, existing = tail, 0, 0
            if head == "HARVESTED":
                fields = dict(p.partition("=")[::2] for p in tail.split("|"))
                added = _int(fields.get("added"))
                existing = _int(fields.get("existing"))
                reason = ""
    if final_kind == "missing":
        reason = runner_error or "no_result"
    elif rc != 0 and final_kind != "HARVEST_FAILED":
        reason = runner_error or f"exit {rc}"
    return HarvestReport(final_kind, reason, rc, tuple(items), tuple(warns),
                         added, existing, tuple(reviews))


def _int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def item_titles(root: str, cids) -> dict:
    """``{cid: title}`` for ``cids`` from ``root``'s store. Best effort.

    Display only: any failure (no store, a damaged one, an unresolvable root)
    yields ``{}`` and the report stands without titles. Lock-free read, the one
    the store's own read verbs use.
    """
    try:
        canon, _ = sitrep_harvest.canonical_root(root)
        store = sitrep_todo.load_todo_for_read(
            os.path.join(canon, ".aitask-sitrep"))
    except Exception:  # noqa: BLE001 - titles are decoration
        return {}
    wanted = set(cids)
    return {it.cid: it.title for it in store.items.values() if it.cid in wanted}


# -- the open Pick-now indicator ---------------------------------------------

@dataclass
class SitrepNowCounter:
    """Open items in a store's Pick-now group, recounted only when it changes.

    The cache key is the CONTENT of `todo.md` (its sha256), never its mtime or
    size: the file is small, reading it is cheap, and a stat key would miss a
    rewrite inside one timestamp tick. Any failure is ``None`` (no indicator),
    never zero.
    """

    _canon: dict = field(default_factory=dict)
    _cache: dict = field(default_factory=dict)
    parses: int = 0

    def count(self, root) -> "int | None":
        if not root:
            return None
        root = str(root)
        if root not in self._canon:
            try:
                self._canon[root] = sitrep_harvest.canonical_root(root)[0]
            except Exception:  # noqa: BLE001 - no indicator for this root
                self._canon[root] = None
        canon = self._canon[root]
        if not canon:
            return None
        path = os.path.join(canon, ".aitask-sitrep", "todo.md")
        try:
            with open(path, "rb") as fh:
                data = fh.read()
        except OSError:
            return None
        digest = hashlib.sha256(data).hexdigest()
        cached = self._cache.get(path)
        if cached is not None and cached[0] == digest:
            return cached[1]
        self.parses += 1
        try:
            store = sitrep_todo.parse_todo(data.decode("utf-8"), path)
            n = sum(1 for it in store.items.values()
                    if it.group == "now" and it.state == "open")
        except Exception:  # noqa: BLE001 - a damaged store shows nothing
            n = None
        self._cache[path] = (digest, n)
        return n


def format_sitrep_term(count: "int | None") -> str:
    """The session-bar term, or ``""`` when there is nothing to show."""
    return f"sitrep {count} now" if count else ""


# -- the result dialog --------------------------------------------------------

class HarvestResultDialog(GuardedModalScreen):
    """What `h` captured, then (only when it is safe) the offer to close.

    A failed report renders NO affirmative button — only "Close" — so the
    dialog itself cannot confirm a close whose output was not saved; the host
    callback re-checks the report as well. Every harvested string (titles,
    refs, reasons, the window name) is rendered as plain Content, never parsed
    as markup (t2017). Sized for the 40-column minimonitor like
    ``FreezeConfirmDialog``; carries its own CSS because both apps push it.
    """

    BINDINGS = [Binding("escape", "dismiss_dialog", "Close", show=False)]

    DEFAULT_CSS = """
    HarvestResultDialog { align: center middle; }
    #harvest-dialog {
        width: 90%; max-width: 80; min-width: 24; height: auto;
        max-height: 90%;
        background: $surface; border: thick $accent; padding: 1 2;
    }
    HarvestResultDialog.-failed #harvest-dialog { border: thick $error; }
    #harvest-header { text-style: bold; color: $accent; margin: 0 0 1 0; }
    HarvestResultDialog.-failed #harvest-header { color: $error; }
    #harvest-body { height: auto; max-height: 20; margin: 0 0 1 0; }
    #harvest-verdict { text-style: bold; margin: 0 0 1 0; }
    #harvest-buttons {
        width: 100%; height: auto; layout: horizontal; align: center middle;
    }
    #harvest-buttons Button { width: auto; min-width: 10; margin: 0 1; }
    """

    def __init__(self, window: str, state: str, report: HarvestReport,
                 titles: "dict | None" = None, *, still_active: bool = False):
        super().__init__()
        self._window = window
        self._state = state
        self._report = report
        self._titles = dict(titles or {})
        self._still_active = still_active
        if not report.ok:
            self.add_class("-failed")

    def body_text(self) -> str:
        """The plain-text body (items, warnings, notes). Public for tests."""
        lines = []
        for it in self._report.items:
            title = self._titles.get(it.cid, "")
            ref = "" if it.ref in ("", "-") else f" {it.ref}"
            lines.append(f"{it.cid} {it.status} {it.kind}{ref}"
                         + (f" — {title}" if title else ""))
        if not self._report.items and self._report.ok:
            lines.append("No new items.")
        for why in self._report.warns:
            lines.append(f"warning: {why}")
        for rv in self._report.reviews:
            lines.append(f"review {rv.cid} ({rv.status}): {rv.codes} — the full "
                         "output is saved in the sitrep store for review")
        if self._state == "live" and self._still_active and self._report.ok:
            lines.append("The agent still looks active: output after this "
                         "capture is not kept.")
        return "\n".join(lines)

    def compose(self) -> ComposeResult:
        kind = "frozen agent" if self._state == "frozen" else "agent"
        with Container(id="harvest-dialog"):
            yield Static(Content(f"Harvest {kind}: {self._window}"),
                         id="harvest-header")
            with VerticalScroll(id="harvest-body"):
                yield Static(Content(self.body_text()), id="harvest-items")
            yield Static(Content(self._report.verdict()), id="harvest-verdict")
            with Container(id="harvest-buttons"):
                if self._report.ok:
                    yield Button(
                        "Drop" if self._state == "frozen" else "Close agent",
                        variant="error", id="btn-confirm")
                    yield Button("Keep", variant="default", id="btn-cancel")
                else:
                    yield Button("Close", variant="default", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "btn-confirm" and self._report.ok)

    def action_dismiss_dialog(self) -> None:
        self.dismiss(False)


# -- the key flow -------------------------------------------------------------

class SitrepCloseMixin:
    """`h` (harvest-and-close) and `S` (sitrep window) for both monitor apps.

    Requires from the host (all provided by ``AgentMarksMixin`` and the apps):
    ``_monitor``, ``_snapshots``, ``_current_agent_snapshot()``,
    ``_kill_target_state()``, ``_strict_root_for_snap()``, ``_drop_frozen()``,
    ``_run_sitrep_harvest()``, ``_run_marks_cmd()``, ``_task_cache``,
    ``notify()``, ``push_screen()``, ``run_worker()``; and per app
    ``_close_live_after_harvest()`` and ``_default_sitrep_target()``.
    """

    #: Class-level floors (the `__new__`-built test rationale on AgentMarksMixin).
    _harvest_close_inflight: bool = False
    _completed_pane_ids: frozenset = frozenset()

    # -- h -------------------------------------------------------------------

    def action_harvest_close(self) -> None:
        """``h`` — harvest the current agent, show it, then offer to close."""
        snap = self._current_agent_snapshot()
        if snap is None:
            self.notify("No agent selected", severity="warning")
            return
        window = snap.pane.window_name
        if snap.pane.category != PaneCategory.AGENT:
            # The full monitor's focus can sit on a TUI or shell card, and
            # `_kill_target_state` calls any unfrozen pane "live".
            self.notify("h works on agent cards only", severity="warning")
            return
        pane_id = snap.pane.pane_id
        state = self._kill_target_state(pane_id)
        if state not in ("live", "frozen"):
            self.notify(f"Could not confirm the state of {window} — not "
                        "harvested", severity="warning", markup=False)
            return
        if state == "frozen" and not snap.frozen_record_id:
            self.notify("That frozen pane carries no record id",
                        severity="warning")
            return
        root = self._strict_root_for_snap(snap)
        if not root:
            self.notify(f"Project root of {window} is unknown — not harvested",
                        severity="warning", markup=False)
            return
        if self._harvest_close_inflight:
            self.notify("A harvest is already running", severity="warning")
            return
        self._dispatch_harvest_close(snap, state, str(root))

    def _dispatch_harvest_close(self, snap, state: str, root: str) -> None:
        """The one sync seam that starts the worker (tests stub THIS)."""
        self._harvest_close_inflight = True
        self.notify("Harvesting…")
        self.run_worker(self._harvest_close(snap, state, root),
                        name="harvest_close", group="sitrep-harvest",
                        exclusive=False, exit_on_error=False)

    async def _read_run_identity(self, pane_id: str) -> "RunIdentity | None":
        rc, out = await self._monitor._tmux_async(
            ["display-message", "-p", "-t", pane_id, RUN_IDENTITY_FORMAT])
        return parse_run_identity(rc, out, pane_id)

    async def _harvest_for_close(self, snap, state: str, root: str
                                 ) -> "tuple[HarvestReport, RunIdentity | None]":
        """Capture + harvest the run in ``snap``'s pane, bound to its identity."""
        pane_id = snap.pane.pane_id
        window = snap.pane.window_name
        before = await self._read_run_identity(pane_id)
        if before is None:
            return HarvestReport.failed("agent_unreadable"), None
        if not before.frozen_record and before.sitrep_tui_root:
            # The sitrep TUI (t2211_2): an `agent-sitrep` card that is not an
            # agent. Discovery never lists it; a snapshot that still does (an
            # older status server) is refused here, at the identity read.
            return HarvestReport.failed("not_an_agent"), before
        if state == "frozen":
            record_id = snap.frozen_record_id
            if before.frozen_record != record_id:
                return HarvestReport.failed("record_changed"), before
            rc, out = await self._run_sitrep_harvest(
                ["record", record_id, "--force"], timeout=HARVEST_ONE_TIMEOUT)
            report = parse_harvest_output(rc, out)
        else:
            if before.frozen_record:
                return HarvestReport.failed("agent_changed_during_harvest"), before
            if sitrep_harvest.is_sitrep_window(window):
                # `capture` does not consult the window name; the sitrep screen
                # only echoes its own store, so it is never fed back into it.
                report = HarvestReport.skipped("sitrep_agent")
            else:
                rc, text = await self._monitor._tmux_async(
                    ["capture-pane", "-p", "-J", "-t", pane_id,
                     "-S", f"-{HARVEST_CAPTURE_LINES}"],
                    timeout=HARVEST_CAPTURE_TIMEOUT)
                if rc != 0 or not text.strip():
                    return HarvestReport.failed("capture_failed"), before
                rc, out = await self._run_sitrep_harvest(
                    self._capture_args(snap, root),
                    stdin=text.encode("utf-8", "replace"),
                    timeout=HARVEST_ONE_TIMEOUT)
                report = parse_harvest_output(rc, out)
        after = await self._read_run_identity(pane_id)
        if after != before:
            return HarvestReport.failed("agent_changed_during_harvest"), before
        return report, before

    def _capture_args(self, snap, root: str) -> "list[str]":
        window = snap.pane.window_name
        args = ["capture", "--root", root, "--agent", window]
        ref = task_ref_from_window_name(window)
        operation, task_id = ref if ref else ("", "")
        if not task_id:
            cache = getattr(self, "_task_cache", None)
            if cache is not None:
                with contextlib.suppress(Exception):
                    task_id = cache.get_task_id_for_pane(snap.pane) or ""
        if task_id:
            args += ["--task", str(task_id)]
        if operation:
            args += ["--operation", operation]
        return args

    async def _harvest_close(self, snap, state: str, root: str) -> None:
        try:
            try:
                report, identity = await self._harvest_for_close(
                    snap, state, root)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - report, never close
                report, identity = HarvestReport.failed(
                    f"internal:{type(exc).__name__}"), None
            titles = {}
            if report.items:
                titles = await asyncio.to_thread(
                    item_titles, root, [it.cid for it in report.items])
            self.notify(report.verdict(), markup=False,
                        severity="information" if report.ok else "error")
            still_active = (state == "live"
                            and snap.pane.pane_id not in self._completed_pane_ids
                            and not snap.is_idle)
            self.push_screen(
                HarvestResultDialog(snap.pane.window_name, state, report,
                                    titles, still_active=still_active),
                lambda yes: self._on_harvest_close_confirmed(
                    yes, report, identity, state),
            )
        finally:
            self._harvest_close_inflight = False

    def _on_harvest_close_confirmed(self, yes, report: HarvestReport,
                                    identity: "RunIdentity | None",
                                    state: str) -> None:
        """Close the harvested run — only it, and only after a safe harvest."""
        if not yes or not report.ok or identity is None:
            return
        if state == "frozen":
            self._drop_after_harvest(identity)
        else:
            self._close_live_after_harvest(identity)

    def _drop_after_harvest(self, identity: RunIdentity) -> None:
        """Drop the harvested record — refused if the pane now holds another.

        Three reads must agree with the record that was harvested: the kill-time
        state, the current snapshot, and the live ``@aitask_frozen`` option.
        The drop itself is the leased ``aitask_frozen.sh drop``, which harvests
        again under its lease, so a capture that changed inside the same record
        is covered by its receipt check.
        """
        pane_id = identity.pane_id
        snap = self._snapshots.get(pane_id)
        name = snap.pane.window_name if snap else pane_id
        same = (self._kill_target_state(pane_id) == "frozen"
                and snap is not None
                and snap.frozen_record_id == identity.frozen_record)
        if same:
            ok, live = self._monitor.get_pane_option_sync(pane_id, FROZEN_OPTION)
            same = ok and live == identity.frozen_record
        if not same:
            self.notify(f"{name} changed since the harvest — not dropped; "
                        "press h again", severity="warning", markup=False)
            return
        self._drop_frozen(snap)

    def _close_live_after_harvest(self, identity: RunIdentity) -> None:
        """Per app: kill the harvested live run (``kill_agent_run_guarded``)."""
        raise NotImplementedError

    def _guarded_close(self, identity: RunIdentity) -> "tuple[str, bool]":
        """The shared half of both apps' live close: re-check, then kill.

        Returns the guarded kill's ``(status, killed_window)``, or
        ``("not_live", False)`` when the pane is no longer provably live. Toasts
        for every non-``killed`` status; the app adds its own success tail.
        """
        pane_id = identity.pane_id
        snap = self._snapshots.get(pane_id)
        name = snap.pane.window_name if snap else pane_id
        if self._kill_target_state(pane_id) != "live":
            self.notify(f"{name} is no longer a live agent — not closed",
                        severity="warning", markup=False)
            return "not_live", False
        status, killed_window = self._monitor.kill_agent_run_guarded(identity)
        if status == "changed":
            self.notify(f"The agent in {name} changed since the harvest — not "
                        "closed; press h again", severity="warning",
                        markup=False)
        elif status != "killed":
            self.notify(f"Could not confirm {name} was closed ({status})",
                        severity="error", markup=False)
        return status, killed_window

    # -- S -------------------------------------------------------------------

    def action_open_sitrep(self) -> None:
        """``S`` — open or switch to the sitrep window of the selected repo."""
        root = session = None
        snap = self._current_agent_snapshot()
        if snap is not None:
            root = self._strict_root_for_snap(snap)
            session = snap.pane.session_name or None
        if not root or not session:
            root, session = self._default_sitrep_target()
        if not root or not session:
            self.notify("No project session to open sitrep for",
                        severity="warning")
            return
        self._dispatch_sitrep_open(str(root), str(session))

    def _default_sitrep_target(self) -> "tuple[str | None, str | None]":
        """This app's own project root and session (per app)."""
        monitor = getattr(self, "_monitor", None)
        session = getattr(monitor, "session", None) if monitor else None
        return getattr(self, "_project_root", None), session

    def _dispatch_sitrep_open(self, root: str, session: str) -> None:
        """The one sync seam that starts the worker (tests stub THIS)."""
        self.run_worker(self._open_sitrep(root, session), name="sitrep_open",
                        group="sitrep-open", exclusive=False,
                        exit_on_error=False)

    async def _open_sitrep(self, root: str, session: str) -> None:
        rc, out = await self._run_marks_cmd(
            ["open", "--root", root, "--session", session],
            script=SITREP_SH, timeout=SITREP_OPEN_TIMEOUT)
        msg, severity = sitrep_open_message(rc, out)
        self.notify(msg, severity=severity, markup=False)
