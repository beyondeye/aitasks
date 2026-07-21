"""Config wizard for the ``ait chatlink`` TUI (t1149_3).

Textual ModalScreens stepping through: intake channel → token → live
check → allowlist → deny mode / repo name → ceilings → summary (write +
final preflight). Imported ONLY by ``chatlink_app.py`` — the daemon
stays Textual-free (guard-tested).

The token and the (optional) live check precede the allowlist so the
allowlist step can fetch live Discord members/roles (t1186_3 reorder).
:data:`_STEPS` is the single source of truth for both order and the
rendered ``Step N/7`` numbering — screens declare only their
:attr:`_WizardStep.step_name` and whether they
:attr:`_WizardStep.needs_seams`.

Contracts (pinned in aiplans/p1149/p1149_3_config_wizard_flow.md; draft
amendment t1190):

- The config file and the token file are written ONLY at the summary
  step; Back/Escape/Cancel before that never touch either. A resumable
  DRAFT of the non-secret step values (never the token —
  :data:`chatlink.wizard_draft.DRAFT_STATE_KEYS`) is written to the
  gitignored sessions dir on every step transition; the next launch
  offers resume / start-fresh, and the draft is deleted on a fully
  successful save or "Start fresh".
- The config write goes through :mod:`chatlink.config_write` (merge,
  never drop); the token through the injected ``token_writer`` (default
  :func:`chatlink.paths.write_token`, 0700 dir / 0600 file). The token
  value is never rendered anywhere (``password=True`` Input; the summary
  shows only "(will write)" / "(kept)").
- The save sequence is failure-aware: each write renders its own outcome
  and a failed token write after a landed config write is shown exactly
  as that — Save retries idempotently.
- This wizard configures the current Discord bug-report intake /
  explore-relay flow (parent-plan §1b scope contract).
"""
from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, SelectionList, Static
from textual.widgets.selection_list import Selection

try:
    from profile_editor import CycleField
except ImportError:  # entrypoint did not pre-insert .aitask-scripts/lib
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
    from profile_editor import CycleField

from . import allowlist_fetch, config, config_write, live_check, paths, \
    policy, preflight, preflight_render, wizard_draft

#: Screen-dismissal sentinels for the step chain.
BACK = object()
NEXT = object()
DONE = object()

_ID_SPLIT_RE = re.compile(r"[,\s]+")

#: (state key, label, range tuple or None for sandbox_memory)
_CEILING_FIELDS = (
    ("max_concurrent_sandboxes", "max concurrent sandboxes",
     config.RANGE_MAX_CONCURRENT_SANDBOXES),
    ("intake_rate_per_user_per_hour", "intake rate / user / hour",
     config.RANGE_INTAKE_RATE_PER_USER_PER_HOUR),
    ("sandbox_memory", "sandbox memory (e.g. 2g)", None),
    ("sandbox_cpus", "sandbox cpus", config.RANGE_SANDBOX_CPUS),
    ("sandbox_pids", "sandbox pids", config.RANGE_SANDBOX_PIDS),
    ("sandbox_wall_clock_s", "sandbox wall clock (s)",
     config.RANGE_SANDBOX_WALL_CLOCK_S),
)


@dataclass(frozen=True)
class _Dimension:
    """One authorization dimension's state keys + widget ids (t1186_4).

    Users and roles are identical code paths; every per-dimension lookup
    goes through this table so neither is hand-duplicated.
    """

    key: str          #: "user" / "role" (also the summary noun, pluralized)
    mode_state: str   #: state key holding this dimension's mode
    mode_id: str      #: CycleField id
    input_id: str     #: ids Input id
    label_id: str     #: mode-relabelled Label id
    inactive_id: str  #: inactive-list disclosure Static id
    list_id: str      #: fetched-rows SelectionList id


_DIMENSIONS = (
    _Dimension("user", "user_authorization_mode", "wiz_user_mode",
               "wiz_user_ids", "wiz_user_ids_label", "wiz_user_inactive",
               "wiz_member_list"),
    _Dimension("role", "role_authorization_mode", "wiz_role_mode",
               "wiz_role_ids", "wiz_role_ids_label", "wiz_role_inactive",
               "wiz_role_list"),
)
_DIM_BY_MODE_ID = {dim.mode_id: dim for dim in _DIMENSIONS}
_DIM_BY_INPUT_ID = {dim.input_id: dim for dim in _DIMENSIONS}
_DIM_BY_LIST_ID = {dim.list_id: dim for dim in _DIMENSIONS}

#: All four authorization list keys, in (allowed, denied) x (user, role).
_LIST_KEYS = tuple(f"{prefix}_{dim.key}_ids"
                   for dim in _DIMENSIONS
                   for prefix in ("allowed", "denied"))


def _active_key(dim_key: str, mode: str) -> str:
    """The list a dimension in ``mode`` actually consults (policy.decide)."""
    return f"{'allowed' if mode == 'allowlist' else 'denied'}_{dim_key}_ids"


def _inactive_key(dim_key: str, mode: str) -> str:
    """The other list — preserved verbatim, but ignored at runtime."""
    return f"{'denied' if mode == 'allowlist' else 'allowed'}_{dim_key}_ids"


def _fetch_key(state: dict, token: str) -> tuple:
    """Identity of the Discord context a picker fetch was made against.

    Carries every argument :func:`allowlist_fetch.run_allowlist_fetch`
    receives, so cached rows can never be shown after the operator edits the
    intake channel — or the token — on an earlier step and comes back. The
    token enters as a one-way digest: the raw value never reaches the
    long-lived state entry (pinned token-hygiene contract).
    """
    return (
        state["provider"], state["workspace_id"], state["conversation_id"],
        state["thread_id"] or None,
        hashlib.sha256(token.encode("utf-8")).hexdigest()[:12],
    )


def _authorization_lines(state: dict) -> list[str]:
    """Summary lines: one per dimension, mode + its ACTIVE ids.

    A non-empty INACTIVE list is disclosed rather than hidden. The wizard
    preserves it (merge-never-drop), so a Save that silently carried ids the
    operator never reviewed — and which a later mode switch would activate —
    would be a surprise. Wording follows preflight's
    ``authorization_<dim>_ignored`` rows.
    """
    lines = []
    for dim in _DIMENSIONS:
        mode = state[dim.mode_state]
        active = state[_active_key(dim.key, mode)]
        inactive_key = _inactive_key(dim.key, mode)
        inactive = state[inactive_key]
        line = f"{dim.key}s: {mode}: {', '.join(active) or '(none)'}"
        if inactive:
            line += (f"   ({inactive_key} kept but ignored: "
                     f"{', '.join(inactive)})")
        lines.append(line)
    return lines


@dataclass
class WizardSeams:
    """Injection points for the wizard — every ``None`` resolves to the
    production ``paths``/``preflight`` function at :func:`resolve_seams`
    time, so tests can redirect all I/O to a tmp dir."""

    config_path: Path | None = None
    token_reader: Callable | None = None
    token_writer: Callable | None = None
    cheap_runner: Callable | None = None
    expensive_runner: Callable | None = None
    live_runner: Callable | None = None
    allowlist_fetch_runner: Callable | None = None


def resolve_seams(seams: WizardSeams | None) -> WizardSeams:
    seams = seams or WizardSeams()
    return WizardSeams(
        config_path=Path(seams.config_path) if seams.config_path
        else (paths.config_file()
              or paths.project_root() / paths.CONFIG_DEFAULT_REL),
        token_reader=seams.token_reader or paths.read_token,
        token_writer=seams.token_writer or paths.write_token,
        cheap_runner=seams.cheap_runner or preflight.run_cheap_checks,
        expensive_runner=(seams.expensive_runner
                          or preflight.run_expensive_checks),
        live_runner=seams.live_runner or live_check.run_live_checks,
        allowlist_fetch_runner=(seams.allowlist_fetch_runner
                                or allowlist_fetch.run_allowlist_fetch),
    )


def initial_state(seams: WizardSeams) -> dict:
    """Pre-fill from the existing config when one exists (edit flow ==
    create flow); config defaults otherwise."""
    cfg = None
    if seams.config_path.exists():
        cfg, _warnings = config.load_config_with_warnings(seams.config_path)
    if cfg is None:
        cfg = config.ChatlinkConfig()
    intake = cfg.intake_channel or {}
    return {
        "provider": intake.get("provider") or "discord",
        "workspace_id": intake.get("workspace_id") or "",
        "conversation_id": intake.get("conversation_id") or "",
        "thread_id": intake.get("thread_id") or "",
        "allowed_user_ids": list(cfg.allowed_user_ids),
        "allowed_role_ids": list(cfg.allowed_role_ids),
        "denied_user_ids": list(cfg.denied_user_ids),
        "denied_role_ids": list(cfg.denied_role_ids),
        "user_authorization_mode": cfg.user_authorization_mode,
        "role_authorization_mode": cfg.role_authorization_mode,
        "deny_message_mode": cfg.deny_message_mode,
        "repo_name": cfg.repo_name or "",
        "max_concurrent_sandboxes": cfg.max_concurrent_sandboxes,
        "intake_rate_per_user_per_hour": cfg.intake_rate_per_user_per_hour,
        "sandbox_memory": cfg.sandbox_memory,
        "sandbox_cpus": cfg.sandbox_cpus,
        "sandbox_pids": cfg.sandbox_pids,
        "sandbox_wall_clock_s": cfg.sandbox_wall_clock_s,
        "token": None,
    }


def build_edits(state: dict) -> dict:
    """The wizard-edited keys, shaped for :func:`config_write.write_config`.
    An emptied ``repo_name`` maps to :data:`config_write.DELETE` — the
    wizard owns the exposed keys, so clearing the field must remove a
    pre-existing value (merely omitting it would let the merge writer
    preserve the stale one). Unexposed keys never appear here (the writer
    carries them through).

    Every key is listed explicitly — never ``**state`` — so the transient,
    underscore-prefixed working entries the allowlist step stashes in the
    shared state dict (``_fetched``: cached picker rows keyed to their fetch
    inputs) can never reach the config file.

    An authorization list is emitted as a plain list even when empty: unlike
    ``repo_name``, ``[]`` is a meaningful value, and a dimension's INACTIVE
    list must round-trip verbatim rather than be cleared (t1186_4)."""
    return {
        "intake_channel": {
            "provider": state["provider"],
            "workspace_id": state["workspace_id"],
            "conversation_id": state["conversation_id"],
            "thread_id": state["thread_id"] or None,
        },
        "allowed_user_ids": list(state["allowed_user_ids"]),
        "allowed_role_ids": list(state["allowed_role_ids"]),
        "denied_user_ids": list(state["denied_user_ids"]),
        "denied_role_ids": list(state["denied_role_ids"]),
        "user_authorization_mode": state["user_authorization_mode"],
        "role_authorization_mode": state["role_authorization_mode"],
        "deny_message_mode": state["deny_message_mode"],
        "repo_name": state["repo_name"] or config_write.DELETE,
        **{key: state[key] for key, _label, _rng in _CEILING_FIELDS},
    }


class _WizardStep(ModalScreen):
    """Shared step shape: dialog container, title, body fields, inline
    error label, Back/Next/Cancel buttons. ``Next`` validates via
    :meth:`_accept` — invalid input updates the error label and the modal
    stays open (never dismissed on bad input)."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    DEFAULT_CSS = """
    _WizardStep #wizard_dialog {
        width: 76;
        height: auto;
        max-height: 90%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
        overflow-y: auto;
    }
    _WizardStep .wizard-label { margin-top: 1; }
    _WizardStep #wizard_error { margin-top: 1; height: auto; }
    _WizardStep #wizard_buttons { margin-top: 1; height: auto; }
    _WizardStep #wizard_buttons Button { margin-right: 2; }
    """

    #: Title text WITHOUT numbering — the ``Step N/7`` prefix is derived
    #: from the screen's position in :data:`_STEPS` by :func:`make_step`.
    step_name = ""
    next_label = "Next"
    #: Whether :func:`make_step` must pass the :class:`WizardSeams` arg.
    #: Declared here rather than in a hardcoded class tuple so reordering
    #: or adding a screen never touches the factory.
    needs_seams = False

    def __init__(self, state: dict, *, first: bool = False,
                 step_no: int = 0, step_total: int = 0):
        super().__init__()
        self.state = state
        self._first = first
        self.step_no = step_no
        self.step_total = step_total

    def compose(self) -> ComposeResult:
        with Container(id="wizard_dialog"):
            yield Label(f"Step {self.step_no}/{self.step_total} — "
                        f"{self.step_name}", id="wizard_title")
            yield from self.body()
            yield Label("", id="wizard_error")
            with Horizontal(id="wizard_buttons"):
                if not self._first:
                    yield Button("Back", id="btn_wiz_back")
                yield Button(self.next_label, variant="success",
                             id="btn_wiz_next")
                yield Button("Cancel", id="btn_wiz_cancel")

    def body(self) -> ComposeResult:  # pragma: no cover - abstract
        raise NotImplementedError
        yield  # noqa: unreachable — makes this a generator

    def _error(self, msg: str) -> None:
        self.query_one("#wizard_error", Label).update(f"[red]{msg}[/red]")

    def _input_value(self, input_id: str) -> str:
        return self.query_one(f"#{input_id}", Input).value.strip()

    def _submits_on_enter(self, widget: Input) -> bool:
        """Whether Enter in ``widget`` means "Next".

        Default: every Input on a step is a field, so Enter submits. A
        screen carrying an auxiliary Input that is NOT a step field (the
        allowlist step's picker filter) overrides this predicate rather than
        ``on_input_submitted``: Textual dispatches naming-convention
        handlers for EVERY class in the MRO, so a subclass
        ``on_input_submitted`` would run *in addition to* this one — calling
        ``_accept`` twice per keypress — not instead of it.
        """
        return True

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self._submits_on_enter(event.input):
            self._accept()

    @on(Button.Pressed, "#btn_wiz_next")
    def _on_next(self) -> None:
        self._accept()

    def _before_back(self) -> None:
        """Hook: last chance to persist working state before Back.

        Default no-op — the wizard's baseline contract is that edits on the
        current screen are only committed by ``_accept()``. A screen whose
        work is expensive to redo (the allowlist step's live fetch +
        multi-select) overrides this to persist without validating; the
        forward path still runs ``_accept()``, so nothing skips validation.
        Overriding ``_on_back`` itself would drop its ``@on`` registration.
        """

    @on(Button.Pressed, "#btn_wiz_back")
    def _on_back(self) -> None:
        self._before_back()
        self.dismiss(BACK)

    @on(Button.Pressed, "#btn_wiz_cancel")
    def _on_cancel(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _accept(self) -> None:  # pragma: no cover - abstract
        raise NotImplementedError


class IntakeChannelScreen(_WizardStep):
    step_name = ("Bug-report intake channel "
                 "(Discord bug-report intake / explore-relay flow)")

    def body(self) -> ComposeResult:
        yield Label("Provider:", classes="wizard-label")
        yield Input(value=self.state["provider"], id="wiz_provider")
        yield Label("Workspace id (Discord: guild id):",
                    classes="wizard-label")
        yield Input(value=self.state["workspace_id"], id="wiz_workspace")
        yield Label("Conversation id (Discord: channel id):",
                    classes="wizard-label")
        yield Input(value=self.state["conversation_id"],
                    id="wiz_conversation")
        yield Label("Thread id (optional):", classes="wizard-label")
        yield Input(value=self.state["thread_id"], id="wiz_thread")

    def _accept(self) -> None:
        values = {
            "provider": self._input_value("wiz_provider"),
            "workspace_id": self._input_value("wiz_workspace"),
            "conversation_id": self._input_value("wiz_conversation"),
        }
        for key, val in values.items():
            if not val:
                self._error(f"{key} is required (non-empty)")
                return
        self.state.update(values)
        self.state["thread_id"] = self._input_value("wiz_thread")
        self.dismiss(NEXT)


class AllowlistScreen(_WizardStep):
    """Authorization step: per-dimension modes + live Discord pickers.

    Each dimension (users, roles) runs in ``allowlist`` or ``denylist`` mode
    (t1186_1) and owns BOTH lists; its ``Input`` always shows exactly the
    active-mode one, and the inactive one round-trips untouched. "Fetch from
    Discord" pulls the intake channel's members and the guild's roles
    (t1186_2) into two multi-select lists; manual entry stays available on
    every failure path (offline, no token, non-Discord provider, failed
    fetch) and a failed fetch never blocks Next.

    **Pinned invariant:** at every moment a picker's ticked set is exactly
    ``active list ∩ visible rows``, and the ``Input`` is the single source of
    truth for the active list. All four mutation paths (typing, selecting,
    filtering, mode toggle) maintain it. Without it a visible-but-unticked
    row would be ambiguous — "the operator removed it" vs. "the operator
    typed it after the rows were built" — and :meth:`_on_selection_changed`
    would silently drop the typed id.
    """

    step_name = "Who may open a bug report"
    needs_seams = True

    DEFAULT_CSS = """
    AllowlistScreen SelectionList {
        height: 8;
        margin-top: 1;
        border: round $primary;
    }
    AllowlistScreen #wiz_fetch_status { height: auto; }
    AllowlistScreen .wizard-note { height: auto; color: $warning; }
    """

    def __init__(self, state: dict, seams: WizardSeams, **kwargs):
        super().__init__(state, **kwargs)
        self.seams = seams
        self._working = {key: list(state[key]) for key in _LIST_KEYS}
        self._modes = {dim.key: state[dim.mode_state] for dim in _DIMENSIONS}
        self._fetched: dict[str, list] = {dim.key: [] for dim in _DIMENSIONS}
        self._visible: dict[str, list] = {dim.key: [] for dim in _DIMENSIONS}
        #: What a rebuild-originated SelectedChanged looks like, per
        #: dimension — see :meth:`_rebuild_list`.
        self._echo: dict[str, set] = {dim.key: set() for dim in _DIMENSIONS}
        self._fetch_key = None
        self._pending_key = None
        self._fetch_running = False
        self._fetch_gen = 0
        #: The exact configuration a posture warning was shown for; only a
        #: press that still matches it may advance (see :meth:`_accept`).
        self._warned_signature = None
        self._notice = self._restore_cache()

    # -------------------------- cached rows --------------------------- #

    def _restore_cache(self) -> str:
        """Adopt Back-cached picker rows only if they match THIS context.

        On a mismatch both the rows AND the ids chosen from them are
        dropped. A Discord role id is guild-scoped, so under a new
        ``workspace_id`` such an id is not stale-but-plausible, it is
        meaningless — and nothing downstream can catch it
        (:func:`allowlist_fetch.invalid_snowflakes` passes any well-formed
        snowflake, and ``policy.decide`` just never matches it). Manually
        typed ids are the operator's own assertion and are kept.

        Dropping is also the fail-closed direction: if it empties an
        allowlist, :meth:`_accept`'s posture check classifies the result
        ``deny_all`` and warns. Over-removal is therefore loud, while
        retention would have been silent. Returns the notice to render.
        """
        cached = self.state.get("_fetched")
        if not cached:
            return ""
        token = self.state["token"] or self.seams.token_reader()
        if token and cached.get("key") == _fetch_key(self.state, token):
            self._fetch_key = cached["key"]
            for dim, rows in (("user", cached["members"]),
                              ("role", cached["roles"])):
                self._fetched[dim] = [tuple(row) for row in rows]
            return ""
        del self.state["_fetched"]
        removed: list[str] = []
        for dim in _DIMENSIONS:
            origin = set(cached.get(f"origin_{dim.key}", ()))
            if not origin:
                continue
            for key in (f"allowed_{dim.key}_ids", f"denied_{dim.key}_ids"):
                gone = [i for i in self._working[key] if i in origin]
                if gone:
                    removed += gone
                    self._working[key] = [i for i in self._working[key]
                                          if i not in origin]
        if removed:
            return ("intake channel or token changed — discarded the fetched "
                    f"rows and removed {len(removed)} id(s) selected from the "
                    "previous context: "
                    f"{', '.join(allowlist_fetch.dedupe_ids(removed))}. "
                    "Manually typed ids were kept. "
                    'Press "Fetch from Discord" to reload.')
        return ("intake channel or token changed — previously fetched rows "
                'discarded. Press "Fetch from Discord" to reload.')

    # ---------------------------- rendering ---------------------------- #

    def _ids_label(self, dim: _Dimension) -> str:
        word = "Allowed" if self._modes[dim.key] == "allowlist" else "Denied"
        return f"{word} {dim.key} ids (comma/space separated):"

    def _inactive_text(self, dim: _Dimension) -> str:
        key = _inactive_key(dim.key, self._modes[dim.key])
        ids = self._working[key]
        if not ids:
            return ""
        return (f"note: {key} is kept but ignored while {dim.mode_state} "
                f"is '{self._modes[dim.key]}': {', '.join(ids)}")

    def _render_inactive(self, dim: _Dimension) -> None:
        self.query_one(f"#{dim.inactive_id}", Static).update(
            self._inactive_text(dim))

    def body(self) -> ComposeResult:
        for dim in _DIMENSIONS:
            yield CycleField(f"{dim.key} authorization mode",
                             list(config.AUTHORIZATION_MODES),
                             self._modes[dim.key], dim.mode_state,
                             id=dim.mode_id)
            yield Label(self._ids_label(dim), id=dim.label_id,
                        classes="wizard-label")
            yield Input(value=", ".join(
                self._working[_active_key(dim.key, self._modes[dim.key])]),
                id=dim.input_id)
            yield Static(self._inactive_text(dim), id=dim.inactive_id,
                         markup=False, classes="wizard-note")
        discord_only = self.state["provider"] != "discord"
        yield Button("Fetch from Discord", id="btn_wiz_fetch",
                     disabled=discord_only)
        if discord_only:
            yield Label("live pickers support Discord only — enter ids "
                        "manually", classes="wizard-label")
        yield Static(self._notice, id="wiz_fetch_status", markup=False)
        filter_input = Input(placeholder="filter fetched members / roles",
                             id="wiz_fetch_filter")
        filter_input.display = False
        yield filter_input
        for dim in _DIMENSIONS:
            picker = SelectionList[str](id=dim.list_id)
            picker.display = False
            yield picker

    def on_mount(self) -> None:
        if self._fetch_key is not None:   # rows survived a Back excursion
            self._reveal_picker()

    def _reveal_picker(self) -> None:
        self.query_one("#wiz_fetch_filter", Input).display = True
        for dim in _DIMENSIONS:
            self.query_one(f"#{dim.list_id}", SelectionList).display = True
            self._rebuild_list(dim)

    # ------------------------- list <-> widgets ------------------------ #

    @staticmethod
    def _parse_ids(raw: str) -> list[str]:
        return [part for part in _ID_SPLIT_RE.split(raw) if part]

    def _sync_active(self, dim: _Dimension) -> None:
        """Input → working list for ``dim``'s ACTIVE mode (single writer)."""
        self._working[_active_key(dim.key, self._modes[dim.key])] = \
            allowlist_fetch.dedupe_ids(
                self._parse_ids(self._input_value(dim.input_id)))

    def _rebuild_list(self, dim: _Dimension) -> None:
        """(Re)build ``dim``'s option rows — the ONLY place options change.

        Ticks are always recomputed from the active list, so a mode toggle
        can never leave marks belonging to the other list.

        Textual posts a ``SelectedChanged`` for every ``initial_state=True``
        option, and ``post_message`` *queues* — a synchronous "am I
        rebuilding" flag would already be cleared by the time the handler
        ran. Two guards instead: ``prevent`` suppresses at the post site,
        and ``_echo`` records what a rebuild-originated selection looks like
        so :meth:`_on_selection_changed` recognises it whenever it arrives.
        """
        self._sync_active(dim)
        picker = self.query_one(f"#{dim.list_id}", SelectionList)
        active = set(self._working[_active_key(dim.key, self._modes[dim.key])])
        pattern = self._input_value("wiz_fetch_filter").casefold()
        visible = [(i, name) for i, name in self._fetched[dim.key]
                   if not pattern
                   or pattern in name.casefold() or pattern in i]
        self._visible[dim.key] = [i for i, _name in visible]
        self._echo[dim.key] = {i for i, _name in visible if i in active}
        with picker.prevent(SelectionList.SelectedChanged):
            picker.clear_options()
            picker.add_options(
                Selection(f"{name} ({i})", value=i, initial_state=i in active)
                for i, name in visible)

    def _sync_selection_from_input(self, dim: _Dimension) -> None:
        """Reconcile ticks with the Input — keeps the pinned invariant.

        Typing is a mutation path like any other: an id typed AFTER the last
        rebuild would otherwise leave its row unticked, and
        :meth:`_on_selection_changed` reads an unticked visible row as "the
        operator removed it" and would drop it on the next click.

        Diffs against the existing options (no clear / re-add), so it costs
        O(changed rows) per keystroke and never disturbs scroll position.
        Idempotent by construction — the ``Input.Changed`` Textual posts when
        the mode toggle assigns ``Input.value`` is a harmless no-op.
        """
        self._sync_active(dim)
        picker = self.query_one(f"#{dim.list_id}", SelectionList)
        active = set(self._working[_active_key(dim.key, self._modes[dim.key])])
        target = {i for i in self._visible[dim.key] if i in active}
        current = set(picker.selected)
        if target == current:
            return
        with picker.prevent(SelectionList.SelectedChanged):
            for value in target - current:
                picker.select(value)
            for value in current - target:
                picker.deselect(value)
        self._echo[dim.key] = target

    # ----------------------------- events ------------------------------ #

    @on(CycleField.Changed)
    def _on_mode_changed(self, event: CycleField.Changed) -> None:
        dim = _DIM_BY_MODE_ID.get(event.field.id)
        if dim is None:
            return
        outgoing, incoming = self._modes[dim.key], event.value
        if incoming == outgoing:
            return
        # Park the edited text in the OUTGOING list, then load the INCOMING
        # one: both survive an allowed → denied → allowed round trip.
        self._working[_active_key(dim.key, outgoing)] = \
            allowlist_fetch.dedupe_ids(
                self._parse_ids(self._input_value(dim.input_id)))
        self._modes[dim.key] = incoming
        self.query_one(f"#{dim.input_id}", Input).value = ", ".join(
            self._working[_active_key(dim.key, incoming)])
        self.query_one(f"#{dim.label_id}", Label).update(self._ids_label(dim))
        self._render_inactive(dim)
        self._rebuild_list(dim)
        self._warned_signature = None   # the posture may have changed

    @on(SelectionList.SelectedChanged)
    def _on_selection_changed(
            self, event: SelectionList.SelectedChanged) -> None:
        dim = _DIM_BY_LIST_ID.get(event.selection_list.id)
        if dim is None:
            return
        live = set(event.selection_list.selected)
        if live == self._echo[dim.key]:
            return   # a rebuild's own echo, not an operator action
        # The mode is read HERE, at event time: a selection must land in the
        # list that is active NOW, never the one active when rows were built.
        key = _active_key(dim.key, self._modes[dim.key])
        visible = set(self._visible[dim.key])
        # Ids typed by hand — or selected and then filtered out of view —
        # are absent from ``live``, so carry them through. Computing this
        # against the VISIBLE set rather than the whole fetched set is what
        # stops filtering from dropping a hidden-but-selected id.
        preserved = [i for i in self._parse_ids(
            self._input_value(dim.input_id)) if i not in visible]
        new = allowlist_fetch.dedupe_ids(
            preserved + [i for i in self._visible[dim.key] if i in live])
        self._echo[dim.key] = live
        self._working[key] = new
        self.query_one(f"#{dim.input_id}", Input).value = ", ".join(new)
        self._warned_signature = None

    @on(Input.Changed)
    def _on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "wiz_fetch_filter":
            # Narrowing only changes which rows exist; it never writes an
            # Input or a working list.
            for dim in _DIMENSIONS:
                self._rebuild_list(dim)
            return
        dim = _DIM_BY_INPUT_ID.get(event.input.id)
        if dim is None:
            return
        self._sync_selection_from_input(dim)
        self._warned_signature = None

    def _submits_on_enter(self, widget: Input) -> bool:
        # Enter while narrowing the picker rows must never advance the step.
        return widget.id != "wiz_fetch_filter"

    # ------------------------------ fetch ------------------------------ #

    @on(Button.Pressed, "#btn_wiz_fetch")
    def _on_fetch(self) -> None:
        if self._fetch_running or self.state["provider"] != "discord":
            return
        token = self.state["token"] or self.seams.token_reader()
        if not token:
            self._error("no token to fetch with — enter one on the token "
                        "step (manual entry still works)")
            return
        self._error("")
        self._fetch_running = True
        self._fetch_gen += 1
        gen = self._fetch_gen
        runner = self.seams.allowlist_fetch_runner
        workspace_id = self.state["workspace_id"]
        conversation_id = self.state["conversation_id"]
        thread_id = self.state["thread_id"] or None
        # Identity of THIS run's context, adopted only if the run lands —
        # never recomputed later from possibly-changed state.
        self._pending_key = _fetch_key(self.state, token)
        self.query_one("#wiz_fetch_status", Static).update(
            "… fetching members and roles "
            f"(up to {allowlist_fetch.FETCH_TIMEOUT_S:.0f}s)")

        def work() -> None:
            """Worker thread body — pure (no widget access)."""
            try:
                result = runner(token, workspace_id, conversation_id,
                                thread_id)
            except Exception:
                result = None
            self.app.call_from_thread(self._apply_fetch, gen, result)

        self.run_worker(work, thread=True)

    def _apply_fetch(self, gen: int, result) -> None:
        if gen != self._fetch_gen or not self.is_attached:
            return  # superseded run, or the screen was already dismissed
        self._fetch_running = False
        status = self.query_one("#wiz_fetch_status", Static)
        if result is None:
            status.update("! fetch failed — enter ids manually above "
                          "(Next still works)")
            return
        self._fetch_key = self._pending_key
        self._fetched["user"] = list(result.members)
        self._fetched["role"] = list(result.roles)
        lines = []
        if result.members_error:
            lines.append(f"! members: {result.members_error}")
        if result.roles_error:
            lines.append(f"! roles: {result.roles_error}")
        if result.members_truncated:
            lines.append(f"showing the first {allowlist_fetch.MAX_MEMBERS} "
                         "members — use the filter to narrow")
        if not lines:
            lines.append(f"fetched {len(result.members)} member(s) and "
                         f"{len(result.roles)} role(s)")
        lines.append("manual entry always works — the id boxes stay editable")
        status.update("\n".join(lines))
        self._reveal_picker()

    # ----------------------------- accept ------------------------------ #

    def _commit_state(self) -> None:
        """Persist working values into the shared wizard state dict.

        Used by both :meth:`_accept` and :meth:`_before_back`, so a trip back
        to an earlier step does not throw the picker work away. Only
        ``_accept`` validates first.
        """
        for key in _LIST_KEYS:
            self.state[key] = list(self._working[key])
        for dim in _DIMENSIONS:
            self.state[dim.mode_state] = self._modes[dim.key]
        if self._fetch_key is None:
            return
        fetched = {dim.key: {i for i, _name in self._fetched[dim.key]}
                   for dim in _DIMENSIONS}
        self.state["_fetched"] = {
            "key": self._fetch_key,
            "members": list(self._fetched["user"]),
            "roles": list(self._fetched["role"]),
            # Provenance: which of the operator's ids came from THESE rows.
            # Only these are dropped if the context later changes — typed
            # ids are their own assertion (see :meth:`_restore_cache`).
            **{f"origin_{dim.key}": sorted(
                (set(self._working[f"allowed_{dim.key}_ids"])
                 | set(self._working[f"denied_{dim.key}_ids"]))
                & fetched[dim.key])
               for dim in _DIMENSIONS},
        }

    def _before_back(self) -> None:
        # A live fetch plus a multi-select is expensive to redo, so Back
        # keeps it. Unvalidated by design: SummaryScreen — the only writer —
        # is reachable ONLY by going forward through _accept, so no
        # unchecked value can reach the config file.
        self._commit_state()

    @staticmethod
    def _posture_warning(posture) -> str:
        """Copy for a risky posture, from ``effective_posture`` facts only
        (the same single source preflight renders from)."""
        if posture.kind == "open_members":
            return ("open access: any channel member will be able to open a "
                    "bug report. Press Next again to keep this.")
        if posture.degenerate_dimensions == ("users", "roles"):
            return ("both allowlists empty — deny-by-default: nobody will be "
                    "able to open a bug report. Press Next again to keep "
                    "this.")
        return (f"denylist has no effect — the empty "
                f"{posture.degenerate_dimensions[0]} allowlist denies "
                "everyone. Press Next again to keep this.")

    def _accept(self) -> None:
        for dim in _DIMENSIONS:
            self._sync_active(dim)
        for key in _LIST_KEYS:
            self._working[key] = allowlist_fetch.dedupe_ids(self._working[key])
        if self.state["provider"] == "discord":
            # ACTIVE lists only — those are what the Inputs display, and
            # hard-blocking on a value the operator cannot see would be
            # unactionable. Switching a mode brings the other list into
            # view, and into validation.
            active = [i for dim in _DIMENSIONS
                      for i in self._working[
                          _active_key(dim.key, self._modes[dim.key])]]
            bad = allowlist_fetch.invalid_snowflakes(active)
            if bad:
                self._error("not valid Discord ids (want 15-21 digits): "
                            + ", ".join(bad))
                return
        # The warning is keyed to the exact configuration it was shown for,
        # never a bare one-shot flag: warn on deny_all, flip both modes to
        # denylist, and a second Next would otherwise silently accept
        # open_members — a different risky posture nobody was shown.
        signature = (self._modes["user"], self._modes["role"],
                     *(tuple(self._working[key]) for key in _LIST_KEYS))
        posture = policy.effective_posture(config.ChatlinkConfig(
            user_authorization_mode=self._modes["user"],
            role_authorization_mode=self._modes["role"],
            **{key: self._working[key] for key in _LIST_KEYS}))
        if (posture.kind != "restricted"
                and self._warned_signature != signature):
            self._warned_signature = signature
            self._error(self._posture_warning(posture))
            return
        self._commit_state()
        self.dismiss(NEXT)


class DenyRepoScreen(_WizardStep):
    step_name = "Denied-message handling & repo name"

    def body(self) -> ComposeResult:
        yield Label("Reply to denied users in the intake channel:",
                    classes="wizard-label")
        yield CycleField("Deny message mode",
                         list(config.DENY_MESSAGE_MODES),
                         self.state["deny_message_mode"],
                         "deny_message_mode", id="wiz_deny_mode")
        yield Label("Repo name for audit/display (optional):",
                    classes="wizard-label")
        yield Input(value=self.state["repo_name"], id="wiz_repo_name")

    def _accept(self) -> None:
        self.state["deny_message_mode"] = self.query_one(
            "#wiz_deny_mode", CycleField).current_value
        self.state["repo_name"] = self._input_value("wiz_repo_name")
        self.dismiss(NEXT)


class CeilingsScreen(_WizardStep):
    step_name = "Sandbox resource ceilings"

    def body(self) -> ComposeResult:
        for key, label, rng in _CEILING_FIELDS:
            hint = f" [{rng[0]}-{rng[1]}]" if rng else ""
            yield Label(f"{label}{hint}:", classes="wizard-label")
            yield Input(value=str(self.state[key]), id=f"wiz_{key}")

    def _accept(self) -> None:
        parsed: dict = {}
        for key, label, rng in _CEILING_FIELDS:
            raw = self._input_value(f"wiz_{key}")
            if rng is None:
                if not config.SANDBOX_MEMORY_RE.match(raw):
                    self._error(f"{label}: invalid {raw!r} "
                                "(want e.g. '512m' or '2g')")
                    return
                parsed[key] = raw
                continue
            try:
                val = int(raw)
            except ValueError:
                self._error(f"{label}: {raw!r} is not an integer")
                return
            lo, hi = rng
            if val < lo or val > hi:
                self._error(f"{label}: {val} outside [{lo}, {hi}]")
                return
            parsed[key] = val
        self.state.update(parsed)
        self.dismiss(NEXT)


class TokenScreen(_WizardStep):
    step_name = "Discord bot token"
    needs_seams = True

    def __init__(self, state: dict, seams: WizardSeams, **kwargs):
        super().__init__(state, **kwargs)
        self.seams = seams
        self._token_present = False

    def body(self) -> ComposeResult:
        self._token_present = self.seams.token_reader() is not None
        note = ("token already present — leave empty to keep it"
                if self._token_present
                else "no token stored yet — paste the bot token")
        yield Label(f"Bot token ({note}):", classes="wizard-label")
        yield Input(password=True, id="wiz_token")
        yield Label("Stored in the gitignored per-PC token file (0600); "
                    "never committed, never displayed.",
                    classes="wizard-label")

    def _accept(self) -> None:
        token = self._input_value("wiz_token")
        if not token and not self._token_present:
            self._error("no token stored yet — enter the bot token "
                        "(the gateway cannot start without it)")
            return
        self.state["token"] = token or None
        self.dismiss(NEXT)


class LiveCheckScreen(_WizardStep):
    """Optional live Discord validation (t1149_5) — advisory only.

    "Validate live now" runs the Textual-free
    :func:`chatlink.live_check.run_live_checks` in a thread worker and
    renders its rows; Continue always advances (== skip when never run)
    and the wizard outcome never depends on the results. A generation
    token + ``is_attached`` guard keeps a late worker result from
    touching a dismissed screen (the user may Continue mid-run).
    """

    step_name = "Live validation (optional)"
    next_label = "Continue"
    needs_seams = True

    def __init__(self, state: dict, seams: WizardSeams, **kwargs):
        super().__init__(state, **kwargs)
        self.seams = seams
        self._live_running = False
        self._live_gen = 0

    def body(self) -> ComposeResult:
        yield Label(
            "Optionally connect to Discord now with the entered token to "
            "verify it live: login, privileged intents, intake-channel "
            "visibility, bot permissions.\n"
            "Advisory only — Continue proceeds regardless.",
            classes="wizard-label")
        discord_only = self.state["provider"] != "discord"
        yield Button("Validate live now", id="btn_wiz_live_run",
                     disabled=discord_only)
        if discord_only:
            yield Label("live validation supports Discord only",
                        classes="wizard-label")
        yield Static("", id="wiz_live_results", markup=False)

    @on(Button.Pressed, "#btn_wiz_live_run")
    def _on_validate(self) -> None:
        if self._live_running or self.state["provider"] != "discord":
            return
        token = self.state["token"] or self.seams.token_reader()
        if not token:
            self._error("no token to validate — enter one on the "
                        "previous step (Continue still works)")
            return
        self._error("")
        self._live_running = True
        self._live_gen += 1
        gen = self._live_gen
        runner = self.seams.live_runner
        workspace_id = self.state["workspace_id"]
        conversation_id = self.state["conversation_id"]
        thread_id = self.state["thread_id"] or None
        self.query_one("#wiz_live_results", Static).update(
            "… validating live "
            f"(up to {live_check.LIVE_CHECK_TIMEOUT_S:.0f}s)")

        def work() -> None:
            """Worker thread body — pure (no widget access)."""
            try:
                results = list(runner(token, workspace_id,
                                      conversation_id, thread_id))
            except Exception:
                results = None
            self.app.call_from_thread(self._apply_results, gen, results)

        self.run_worker(work, thread=True)

    def _apply_results(self, gen: int, results) -> None:
        if gen != self._live_gen or not self.is_attached:
            return  # superseded run, or the screen was already dismissed
        self._live_running = False
        if results is None:
            self.query_one("#wiz_live_results", Static).update(
                "! live validation errored — you can Continue "
                "(advisory only)")
            return
        lines = [f"  {preflight_render.format_row(res)}"
                 for res in results]
        self.query_one("#wiz_live_results", Static).update(
            "\n".join(lines))

    def _accept(self) -> None:
        self.dismiss(NEXT)


class _ReplaceConfirmScreen(ModalScreen):
    """Explicit conflict confirmation: the existing config cannot be
    merged (malformed YAML / non-mapping) — replacing it drops whatever
    is in the file. Never silent."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    DEFAULT_CSS = """
    _ReplaceConfirmScreen #wizard_dialog {
        width: 76;
        height: auto;
        background: $surface;
        border: thick $error;
        padding: 1 2;
    }
    _ReplaceConfirmScreen #wizard_buttons { margin-top: 1; height: auto; }
    _ReplaceConfirmScreen #wizard_buttons Button { margin-right: 2; }
    """

    def __init__(self, reason: str):
        super().__init__()
        self.reason = reason

    def compose(self) -> ComposeResult:
        with Container(id="wizard_dialog"):
            yield Label("Existing config file cannot be merged:\n"
                        f"{self.reason}\n\n"
                        "Save will REPLACE the file entirely (its current "
                        "content is lost).")
            with Horizontal(id="wizard_buttons"):
                yield Button("Replace file", variant="error",
                             id="btn_wiz_replace")
                yield Button("Cancel", id="btn_wiz_replace_cancel")

    @on(Button.Pressed, "#btn_wiz_replace")
    def _on_replace(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#btn_wiz_replace_cancel")
    def _on_cancel(self) -> None:
        self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)


class SummaryScreen(_WizardStep):
    """Final step: show the collected values, Save (config via
    config_write, token via the seam — failure-aware, idempotent retry),
    then run preflight and render the results."""

    step_name = "Summary & save"
    next_label = "Save"
    needs_seams = True

    def __init__(self, state: dict, seams: WizardSeams, **kwargs):
        super().__init__(state, **kwargs)
        self.seams = seams
        self._config_written = False
        self._token_written = False
        self._allow_replace = False
        self._probing = False

    # ---------------------------- rendering ---------------------------- #

    def _summary_text(self) -> str:
        st = self.state
        if st["token"]:
            token_line = "(will write)"
        elif self.seams.token_reader() is not None:
            token_line = "(kept)"
        else:
            token_line = "(missing!)"
        lines = [
            f"intake: {st['provider']} "
            f"{st['workspace_id']}/{st['conversation_id']}"
            + (f" thread={st['thread_id']}" if st["thread_id"] else ""),
            *_authorization_lines(st),
            f"deny_message_mode: {st['deny_message_mode']}"
            + (f"   repo_name: {st['repo_name']}" if st["repo_name"] else ""),
            "ceilings: " + "  ".join(
                f"{key.replace('sandbox_', '')}={st[key]}"
                for key, _label, _rng in _CEILING_FIELDS),
            f"token: {token_line}",
            f"config file: {self.seams.config_path}",
        ]
        return "\n".join(lines)

    def body(self) -> ComposeResult:
        yield Static(self._summary_text(), id="wiz_summary", markup=False)
        yield Static("", id="wiz_save_state", markup=False)
        yield Static("", id="wiz_preflight", markup=False)

    def _render_save_state(self, config_error: str | None = None,
                           token_error: str | None = None) -> None:
        lines = []
        if config_error:
            lines.append(f"config: FAILED — {config_error}")
        elif self._config_written:
            lines.append("config: written")
        if self.state["token"]:
            if token_error:
                lines.append(f"token: FAILED — {token_error} "
                             "(config write persisted; Save retries)")
            elif self._token_written:
                lines.append("token: written")
        self.query_one("#wiz_save_state", Static).update("\n".join(lines))

    # ------------------------------ save ------------------------------ #

    def _accept(self) -> None:
        if self._saved():
            self.dismiss(DONE)
            return
        self._do_save()

    def _saved(self) -> bool:
        return (self._config_written
                and (self._token_written or not self.state["token"]))

    def _do_save(self) -> None:
        if not self._config_written:
            try:
                config_write.write_config(
                    self.seams.config_path, build_edits(self.state),
                    allow_replace=self._allow_replace)
            except config_write.ConfigWriteError as exc:
                self.app.push_screen(_ReplaceConfirmScreen(str(exc)),
                                     callback=self._handle_replace)
                return
            except OSError as exc:
                self._render_save_state(config_error=str(exc))
                self._error("config write failed — fix and press Save "
                            "to retry")
                return
            self._config_written = True
        if self.state["token"] and not self._token_written:
            try:
                self.seams.token_writer(self.state["token"])
            except Exception as exc:
                self._render_save_state(token_error=str(exc))
                self._error("token write failed — fix and press Save to "
                            "retry (the config write already persisted)")
                return
            self._token_written = True
        # Fully successful save (config written; token written or none
        # entered) — the resume draft is now obsolete. Not keyed on
        # _token_written: keep-existing-token saves leave it False.
        try:
            wizard_draft.clear_draft()
        except OSError:
            pass
        self._render_save_state()
        self._error("")
        self.query_one("#btn_wiz_next", Button).label = "Close"
        self._start_preflight()

    def _handle_replace(self, confirmed: bool | None) -> None:
        if not confirmed:
            return
        self._allow_replace = True
        self._do_save()

    # ---------------------------- preflight ---------------------------- #

    def _start_preflight(self) -> None:
        cheap = self.seams.cheap_runner()
        lines = ["", "config checks — bug-report intake / explore-relay:"]
        lines += [f"  {preflight_render.format_row(res)}"
                  for res in cheap.results]
        lines.append("  … running expensive checks "
                     "(agent command, docker)")
        commit_hint = self._commit_hint()
        self.query_one("#wiz_preflight", Static).update(
            "\n".join(lines + ["", commit_hint]))
        if self._probing:
            return
        self._probing = True
        self._cheap_lines = lines[:-1]
        self.run_worker(self._run_probes, thread=True)

    def _run_probes(self) -> None:
        """Worker thread body — pure (no widget access)."""
        try:
            results = list(self.seams.expensive_runner())
        except Exception:
            results = None
        self.app.call_from_thread(self._apply_probes, results)

    def _apply_probes(self, results) -> None:
        self._probing = False
        lines = list(self._cheap_lines)
        if results is None:
            lines.append("  ! expensive checks failed — press Save/Close "
                         "after fixing, or re-run preflight from the "
                         "status panel (r)")
        else:
            lines += [f"  {preflight_render.format_row(res)}"
                      for res in results]
        self.query_one("#wiz_preflight", Static).update(
            "\n".join(lines + ["", self._commit_hint()]))

    def _commit_hint(self) -> str:
        try:
            rel = self.seams.config_path.relative_to(paths.project_root())
        except ValueError:
            rel = self.seams.config_path
        return ("review & commit the config when ready:\n"
                f"  ./ait git add {rel} && ./ait git commit\n"
                "(the wizard never commits; the token file stays "
                "uncommitted/gitignored)")


class _ResumeDraftScreen(ModalScreen):
    """Explicit resume offer for an interrupted wizard session: a draft
    of the entered values exists (t1190). Never silently pre-filled —
    the user must be able to tell saved config from abandoned input."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    DEFAULT_CSS = """
    _ResumeDraftScreen #wizard_dialog {
        width: 76;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    _ResumeDraftScreen #wizard_buttons { margin-top: 1; height: auto; }
    _ResumeDraftScreen #wizard_buttons Button { margin-right: 2; }
    """

    def __init__(self, draft: dict, stale: bool):
        super().__init__()
        self.draft = draft
        self.stale = stale

    def compose(self) -> ComposeResult:
        lines = ["An interrupted wizard session left a draft "
                 f"(saved {self.draft['saved_at']}),",
                 f"stopped at: {self.draft['step_name']}."]
        if self.stale:
            lines.append("")
            lines.append("note: the saved config changed after this "
                         "draft was written — resumed values may be "
                         "stale.")
        with Container(id="wizard_dialog"):
            yield Label("\n".join(lines))
            with Horizontal(id="wizard_buttons"):
                yield Button("Resume draft", variant="success",
                             id="btn_wiz_resume")
                yield Button("Start fresh", id="btn_wiz_fresh")

    @on(Button.Pressed, "#btn_wiz_resume")
    def _on_resume(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#btn_wiz_fresh")
    def _on_fresh(self) -> None:
        self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(None)


def _resume_index(step_name: str, token_entered: bool,
                  seams: WizardSeams) -> int:
    """Map a draft's recorded step_name to today's ``_STEPS`` position.

    An unknown name (renamed/removed step) falls back to 0. The token is
    never drafted, so a resume past the token step is capped there when
    the token cannot be what the user last intended: either none is
    stored on disk (Summary would save a config with no token — a broken
    bot, rendered only as "(missing!)"), or the interrupted session had
    a typed token (``token_entered``) that is now lost — an uncapped
    resume would silently keep the old on-disk token instead."""
    idx = next((i for i, cls in enumerate(_STEPS)
                if cls.step_name == step_name), 0)
    token_idx = _STEPS.index(TokenScreen)
    if idx > token_idx and (token_entered
                            or seams.token_reader() is None):
        return token_idx
    return idx


def start_wizard(app, seams: WizardSeams | None = None) -> None:
    """Chain the wizard steps on ``app`` (the running ChatlinkApp).

    Screens mutate a shared state dict (so Back retains entered values)
    and dismiss with ``NEXT`` / ``BACK`` / ``None`` (abort) / ``DONE``.
    Every step transition persists a token-free draft (t1190); a
    pre-existing draft is offered for resume before step 1.
    """
    seams = resolve_seams(seams)
    state = initial_state(seams)
    fingerprint = wizard_draft.config_fingerprint(seams.config_path)

    def make_step(idx: int) -> _WizardStep:
        cls = _STEPS[idx]
        kwargs = dict(first=idx == 0, step_no=idx + 1,
                      step_total=len(_STEPS))
        if cls.needs_seams:
            return cls(state, seams, **kwargs)
        return cls(state, **kwargs)

    def save_draft_for(idx: int) -> None:
        # Best-effort: a failing draft write must never block the wizard.
        try:
            wizard_draft.save_draft(_STEPS[idx].step_name, state,
                                    fingerprint)
        except Exception:
            pass

    def show(idx: int) -> None:
        def handle(result) -> None:
            if result is None or result is DONE:
                return  # abort keeps the draft; save already deleted it
            if result is BACK:
                if idx > 0:
                    save_draft_for(idx - 1)
                    show(idx - 1)
                return
            if result is NEXT and idx + 1 < len(_STEPS):
                save_draft_for(idx + 1)
                show(idx + 1)

        app.push_screen(make_step(idx), callback=handle)

    draft = wizard_draft.load_draft()
    if draft is None:
        show(0)
        return

    def handle_resume(choice) -> None:
        if choice is None:
            return  # abort the wizard; the draft is kept
        if not choice:
            try:
                wizard_draft.clear_draft()
            except OSError:
                pass
            show(0)  # saved-config flow, exactly as without a draft
            return
        state.update(draft["state"])
        show(_resume_index(draft["step_name"], draft["token_entered"],
                           seams))

    app.push_screen(
        _ResumeDraftScreen(draft,
                           stale=draft["config_fingerprint"] != fingerprint),
        callback=handle_resume)


#: Step order AND the source of the rendered ``Step N/7`` numbering.
#: The token + live check precede the allowlist so the allowlist step can
#: fetch live members/roles; ``LiveCheckScreen`` reads only provider /
#: token / workspace_id / conversation_id / thread_id, all set by steps
#: 1-2.
_STEPS = (IntakeChannelScreen, TokenScreen, LiveCheckScreen,
          AllowlistScreen, DenyRepoScreen, CeilingsScreen, SummaryScreen)
