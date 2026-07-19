"""Config wizard for the ``ait chatlink`` TUI (t1149_3).

Textual ModalScreens stepping through: intake channel → allowlist →
deny mode / repo name → ceilings → token → summary (write + final
preflight). Imported ONLY by ``chatlink_app.py`` — the daemon stays
Textual-free (guard-tested).

Contracts (pinned in aiplans/p1149/p1149_3_config_wizard_flow.md):

- Files are written ONLY at the summary step; Back/Escape/Cancel before
  that abort cleanly with zero writes.
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
from textual.widgets import Button, Input, Label, Static

try:
    from profile_editor import CycleField
except ImportError:  # entrypoint did not pre-insert .aitask-scripts/lib
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
    from profile_editor import CycleField

from . import config, config_write, paths, preflight, preflight_render

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
    carries them through)."""
    return {
        "intake_channel": {
            "provider": state["provider"],
            "workspace_id": state["workspace_id"],
            "conversation_id": state["conversation_id"],
            "thread_id": state["thread_id"] or None,
        },
        "allowed_user_ids": list(state["allowed_user_ids"]),
        "allowed_role_ids": list(state["allowed_role_ids"]),
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

    step_title = ""
    next_label = "Next"

    def __init__(self, state: dict, *, first: bool = False):
        super().__init__()
        self.state = state
        self._first = first

    def compose(self) -> ComposeResult:
        with Container(id="wizard_dialog"):
            yield Label(self.step_title, id="wizard_title")
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

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._accept()

    @on(Button.Pressed, "#btn_wiz_next")
    def _on_next(self) -> None:
        self._accept()

    @on(Button.Pressed, "#btn_wiz_back")
    def _on_back(self) -> None:
        self.dismiss(BACK)

    @on(Button.Pressed, "#btn_wiz_cancel")
    def _on_cancel(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _accept(self) -> None:  # pragma: no cover - abstract
        raise NotImplementedError


class IntakeChannelScreen(_WizardStep):
    step_title = ("Step 1/6 — Bug-report intake channel "
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
    step_title = "Step 2/6 — Who may open a bug report (deny-by-default)"

    def __init__(self, state: dict, **kwargs):
        super().__init__(state, **kwargs)
        self._warned_empty = False

    def body(self) -> ComposeResult:
        yield Label("Allowed user ids (comma/space separated):",
                    classes="wizard-label")
        yield Input(value=", ".join(self.state["allowed_user_ids"]),
                    id="wiz_user_ids")
        yield Label("Allowed role ids (comma/space separated):",
                    classes="wizard-label")
        yield Input(value=", ".join(self.state["allowed_role_ids"]),
                    id="wiz_role_ids")

    @staticmethod
    def _parse_ids(raw: str) -> list[str]:
        return [part for part in _ID_SPLIT_RE.split(raw) if part]

    def _accept(self) -> None:
        users = self._parse_ids(self._input_value("wiz_user_ids"))
        roles = self._parse_ids(self._input_value("wiz_role_ids"))
        if not users and not roles and not self._warned_empty:
            self._warned_empty = True
            self._error("both allowlists empty — deny-by-default: nobody "
                        "can open a bug report. Press Next again to keep "
                        "them empty.")
            return
        self.state["allowed_user_ids"] = users
        self.state["allowed_role_ids"] = roles
        self.dismiss(NEXT)


class DenyRepoScreen(_WizardStep):
    step_title = "Step 3/6 — Denied-message handling & repo name"

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
    step_title = "Step 4/6 — Sandbox resource ceilings"

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
    step_title = "Step 5/6 — Discord bot token"

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

    step_title = "Step 6/6 — Summary & save"
    next_label = "Save"

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
        ids = ", ".join(st["allowed_user_ids"] + st["allowed_role_ids"])
        lines = [
            f"intake: {st['provider']} "
            f"{st['workspace_id']}/{st['conversation_id']}"
            + (f" thread={st['thread_id']}" if st["thread_id"] else ""),
            f"allowlist: {ids or '(empty — deny-by-default)'}",
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


def start_wizard(app, seams: WizardSeams | None = None) -> None:
    """Chain the wizard steps on ``app`` (the running ChatlinkApp).

    Screens mutate a shared state dict (so Back retains entered values)
    and dismiss with ``NEXT`` / ``BACK`` / ``None`` (abort) / ``DONE``.
    """
    seams = resolve_seams(seams)
    state = initial_state(seams)

    def make_step(idx: int) -> _WizardStep:
        first = idx == 0
        cls = _STEPS[idx]
        if cls in (TokenScreen, SummaryScreen):
            return cls(state, seams, first=first)
        return cls(state, first=first)

    def show(idx: int) -> None:
        def handle(result) -> None:
            if result is None or result is DONE:
                return
            if result is BACK:
                if idx > 0:
                    show(idx - 1)
                return
            if result is NEXT and idx + 1 < len(_STEPS):
                show(idx + 1)

        app.push_screen(make_step(idx), callback=handle)

    show(0)


_STEPS = (IntakeChannelScreen, AllowlistScreen, DenyRepoScreen,
          CeilingsScreen, TokenScreen, SummaryScreen)
