"""Advisory workflow-phase signal for the shadow companion (t1420).

Answers "which task-workflow phase is the followed agent in, and is it waiting
inside that phase?" as a **hint that changes a default** — never a check that
changes what is permitted. Every consumer must treat an `UNKNOWN` or an outright
wrong phase as costing the user at most one extra keystroke. See
`aidocs/framework/shadow_agent.md` ("Phase detection (advisory)") for the
anti-gating rule this exists under.

Stdlib only, matching `gate_ledger.py`: no PyYAML, no tmux, no Textual. The
live half is supplied *by the caller* as already-captured pane text plus the
monitor's own classification result, so this module stays pure and testable.

Two live tiers, and the split is the t1420/t1467 ownership seam:

- **Tier A** (`WORKFLOW_PROMPTS`) — agent-neutral. These strings are authored by
  *task-workflow*, not by any code agent, so they read identically under every
  supported CLI. Complete here.
- **Tier B** (`NATIVE_KIND_PHASE`) — per-agent native dialogs, keyed on the
  monitor's `awaiting_input_kind`. Ships with the **Claude row only**; Codex and
  OpenCode are explicit empty placeholders owned by **t1467**, which inventories
  their real prompt surfaces. Nothing here may imply live coverage for an agent
  before its markers land — ask `live_tiers_available()`.

CLI:

    workflow_phase.py signal <task-file> [--screen <file>|-]
                             [--awaiting-input yes|no|unknown]
                             [--kind <awaiting_input_kind>] [--agent <name>]
                             [--profiles-dir <dir>]

Prints one `|`-delimited status line (see `format_signal`).
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gate_ledger as gl  # noqa: E402

# --- Vocabulary -----------------------------------------------------------
#
# ONE canonical value set per field. The dataclass documents itself by naming
# these; format_signal validates against them and parse_signal degrades a
# non-member to the unknown value, so serialization cannot drift from runtime
# semantics. Never re-list the members in a comment or a docstring — cite the
# constant instead (t1420).

PHASES = ("PLAN", "IMPLEMENT", "POSTIMPL", "UNKNOWN")
LIVENESS = ("WAITING", "RUNNING", "UNKNOWN")
SOURCES = ("workflow-prompt", "native-prompt", "ledger", "none")

UNKNOWN_PHASE = "UNKNOWN"
UNKNOWN_LIVENESS = "UNKNOWN"
NO_SOURCE = "none"

# --- Tier A: framework-authored checkpoint prompts (agent-neutral) ---------
#
# Each anchor is a literal authored in `.claude/skills/task-workflow/`; the
# drift guard `tests/test_workflow_phase_prompt_drift.sh` fails if one stops
# existing there. Do NOT paraphrase an anchor to "improve" it — the canonical
# site is the skill text, this table only mirrors it.


@dataclass(frozen=True)
class WorkflowPrompt:
    name: str
    regex: "re.Pattern[str]"
    phase: str
    waiting: str


WORKFLOW_PROMPTS: tuple[WorkflowPrompt, ...] = (
    WorkflowPrompt("plan_checkpoint",
                   re.compile(r"Plan saved to"), "PLAN", "WAITING"),
    WorkflowPrompt("step8_review",
                   re.compile(r"Implementation complete\. Please review and "
                              r"test the changes"), "IMPLEMENT", "WAITING"),
    WorkflowPrompt("merge_approval",
                   re.compile(r"Proceed with merge of code changes into"),
                   "POSTIMPL", "WAITING"),
    WorkflowPrompt("archive_offer",
                   re.compile(r"has all gates passing and is ready to archive"),
                   "POSTIMPL", "WAITING"),
)

# Measured 2026-08-10 against Claude Code 2.1.226 in a 163x64 pane: a 4-option
# AskUserQuestion renders its question text 14 lines above the pane bottom, and
# a live prompt exists ONLY in the visible region (zero live markers survived in
# 3352 lines of real scrollback). 40 covers the question text with headroom for
# a longer/wrapped one. Whether an anchor belongs to the CURRENT widget is
# decided structurally by current_question_block, not by distance.
_WORKFLOW_PROMPT_TAIL_LINES = 40

# The header chip an AskUserQuestion renders above its question text — the START
# of the current question block (see current_question_block). Measured, not
# assumed: it appears exactly once and only in that widget.
_QUESTION_HEADER_RE = re.compile(r"^\s*[\u2610\u2611]\s+\S")

# --- Per-agent live-tier tables -------------------------------------------
#
# QUESTION_WIDGET_KINDS: which `awaiting_input_kind` values mean "the pane is
# blocked on a numbered-option question widget". This is Tier A's *currency*
# evidence: a workflow checkpoint is always an AskUserQuestion, so requiring
# this kind makes the stale-anchor case structurally impossible — a live
# tool-permission dialog reports `claude_help_bar`, never this.
#
# NATIVE_KIND_PHASE: Tier B. A generic confirmation carries NO phase and is
# therefore a deliberately ABSENT key (`claude_proceed`, `claude_help_bar`,
# `codex_yes_proceed`): absence-safety is a property of the table, not of a code
# path that must remember to check.
#
# Codex/OpenCode rows are empty by design — t1467 owns inventorying their real
# prompt surfaces. An agent with neither entry degrades to the ledger-derived
# phase, never to a guess.

QUESTION_WIDGET_KINDS: dict[str, tuple[str, ...]] = {
    "claude": ("claude_askuserquestion",),
    "codex": (),      # t1467
    "opencode": (),   # t1467
}

NATIVE_KIND_PHASE: dict[str, dict[str, tuple[str, str]]] = {
    "claude": {"claude_plan_approval": ("PLAN", "WAITING")},
    "codex": {},      # t1467
    "opencode": {},   # t1467
}


def agent_key_from_command(current_command: str) -> str:
    """Map a pane's running command to a per-agent table key, or ``""``.

    ``""`` is the honest answer for anything unrecognised (a wrapper process, a
    shell, a future CLI) and degrades to ledger-only via
    :func:`live_tiers_available` — never to a guessed phase. Deliberately an
    exact match on the known CLI names rather than a substring test: a pane
    running ``claude-something-else`` is not Claude Code.
    """
    cmd = os.path.basename((current_command or "").strip()).lower()
    return cmd if cmd in QUESTION_WIDGET_KINDS else ""


def live_tiers_available(agent: str) -> bool:
    """Can this agent's screen tiers ever contribute a phase?

    ``False`` means permanently ledger-only until t1467 adds the agent's prompt
    markers — a *structural* absence, not an ambiguous read, and consumers must
    render it as such rather than as "broken".
    """
    key = (agent or "").strip().lower()
    return bool(QUESTION_WIDGET_KINDS.get(key)) or bool(NATIVE_KIND_PHASE.get(key))


# --- Signal ---------------------------------------------------------------


@dataclass(frozen=True)
class PhaseSignal:
    """Derived phase plus the provenance that makes a surprising answer
    explainable. ``phase`` is one of :data:`PHASES`, ``waiting`` one of
    :data:`LIVENESS`, ``source`` one of :data:`SOURCES`.

    ``phase`` and ``waiting`` are independent: a pane can be ``WAITING`` with an
    ``UNKNOWN`` phase, and that is a legitimate state, not a defect.
    """

    phase: str = UNKNOWN_PHASE
    waiting: str = UNKNOWN_LIVENESS
    source: str = NO_SOURCE
    consulted: list[str] = field(default_factory=list)
    recording: str = "unknown"
    detail: str = ""


_DELIM = "|"
_FIELD_SEP = ":"


def _sanitize(text: str) -> str:
    """Strip the delimiter and newlines AT THE WRITE SITE.

    A delimiter inside the payload is undecidable on read, so it never gets
    written. Collapses runs of whitespace so a wrapped detail stays one line.
    """
    return " ".join(str(text).replace(_DELIM, "/").split())


def format_signal(sig: PhaseSignal) -> str:
    """Serialize to the single-line wire format used by the CLI verb and the
    ``@aitask_shadow_phase`` pane option. Validates every vocabulary field
    against its constant — an out-of-set value is a programming error and is
    emitted as the unknown member rather than propagated."""
    phase = sig.phase if sig.phase in PHASES else UNKNOWN_PHASE
    waiting = sig.waiting if sig.waiting in LIVENESS else UNKNOWN_LIVENESS
    source = sig.source if sig.source in SOURCES else NO_SOURCE
    consulted = ",".join(_sanitize(c) for c in sig.consulted) or "-"
    return _DELIM.join([
        f"PHASE{_FIELD_SEP}{phase}",
        f"WAITING{_FIELD_SEP}{waiting}",
        f"SOURCE{_FIELD_SEP}{source}",
        f"CONSULTED{_FIELD_SEP}{consulted}",
        f"RECORDING{_FIELD_SEP}{_sanitize(sig.recording) or 'unknown'}",
        f"DETAIL{_FIELD_SEP}{_sanitize(sig.detail)}",
    ])


def parse_signal(line: str) -> PhaseSignal:
    """Total inverse of :func:`format_signal` — never raises. Anything
    unparseable, and any field outside its vocabulary, degrades to the unknown
    member so a corrupt pane option can only ever cost the hint."""
    fields: dict[str, str] = {}
    for chunk in (line or "").strip().split(_DELIM):
        key, sep, value = chunk.partition(_FIELD_SEP)
        if sep:
            fields[key.strip().upper()] = value.strip()
    phase = fields.get("PHASE", "")
    waiting = fields.get("WAITING", "")
    source = fields.get("SOURCE", "")
    consulted = [c for c in fields.get("CONSULTED", "").split(",") if c and c != "-"]
    return PhaseSignal(
        phase=phase if phase in PHASES else UNKNOWN_PHASE,
        waiting=waiting if waiting in LIVENESS else UNKNOWN_LIVENESS,
        source=source if source in SOURCES else NO_SOURCE,
        consulted=consulted,
        recording=fields.get("RECORDING", "") or "unknown",
        detail=fields.get("DETAIL", ""),
    )


# --- Derivation: ledger half ----------------------------------------------


def phase_from_ledger_text(text: str) -> tuple[str, str]:
    """``(phase, detail)`` from the task body alone.

    The load-bearing distinction: **no ledger at all is `UNKNOWN`, not `PLAN`.**
    ``gate_ledger.resume_point_from_text`` answers ``PLAN`` for an empty ledger
    because that is the correct *re-entry* default (plan from scratch), but "I
    cannot tell" and "in planning" are different states and every consumer must
    render them differently. Needs no profile: an absent ledger is unknowable
    whatever the profile says.
    """
    if not gl.has_gate_markers(text or ""):
        return UNKNOWN_PHASE, "no ## Gate Runs ledger recorded"
    phase = gl.resume_point_from_text(text)
    return phase, f"ledger checkpoints resolve to {phase}"


def recording_from_text(text: str, profiles_dir: str | None) -> tuple[str, str]:
    """``(state, detail)`` where state is ``on`` / ``off`` / ``unknown``.

    Explains an ``UNKNOWN`` phase — it never changes one. A profile without
    ``record_gates`` never writes a ledger, so "nothing recorded yet" and
    "recording is disabled" look identical on disk and must not read alike.
    Honours the ``local/`` over shared precedence `aitask_run_gates.sh` sets.
    """
    if not profiles_dir:
        return "unknown", "no profiles dir supplied"
    name = gl.read_active_gates_profile_from_text(text or "")
    if not name:
        return "unknown", "task carries no active_gates_profile stamp"
    for candidate in (os.path.join(profiles_dir, "local", f"{name}.yaml"),
                      os.path.join(profiles_dir, f"{name}.yaml")):
        try:
            with open(candidate, encoding="utf-8") as fh:
                ptext = fh.read()
        except OSError:
            continue
        value = _read_profile_scalar(ptext, "record_gates")
        if value == "":
            return "off", f"profile '{name}' does not set record_gates"
        return ("on" if value.lower() in ("true", "yes", "1") else "off",
                f"profile '{name}' sets record_gates: {value}")
    return "unknown", f"profile '{name}' not found under {profiles_dir}"


def _read_profile_scalar(ptext: str, key: str) -> str:
    """Read one unfenced top-level scalar from a profile YAML.

    Local rather than borrowed from `gate_ledger`: that module's equivalent is
    private, and importing an underscore name across modules is exactly the
    coupling `resume_point_from_text` / `read_active_gates_profile_from_text`
    were promoted to remove (t1420).
    """
    m = re.search(rf"(?m)^{re.escape(key)}:\s*(.*?)\s*$", ptext or "")
    return m.group(1).strip().strip("'\"") if m else ""


# --- Derivation: live half -------------------------------------------------


def _tail(text: str, n: int) -> list[str]:
    lines = (text or "").splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    return lines[-n:] if len(lines) > n else lines


def current_question_block(lines: list[str]) -> int | None:
    """Index of the line that STARTS the currently-rendered question widget, or
    ``None``.

    The delimiter is the widget's header chip — `` ☐ <Header> `` — which an
    ``AskUserQuestion`` always renders directly under its top rule and above its
    question text. Measured against Claude Code 2.1.226: it occurs exactly once,
    only in that widget, and only for the *live* one (an answered question
    collapses to a one-line summary carrying no chip).

    That is what makes this a real block boundary rather than a distance
    heuristic. A proximity bound cannot work: the widget's own inner rule sits
    *below* the question, and a stale anchor can sit within any fixed number of
    lines of the bottom once a later, unrelated question is rendered under it.
    Only "is the anchor inside the current widget" is decidable, so that is what
    is asked.
    """
    for idx in range(len(lines) - 1, -1, -1):
        if _QUESTION_HEADER_RE.match(lines[idx]):
            return idx
    return None


def phase_from_screen(screen_text: str) -> tuple[str, str, str] | None:
    """``(phase, waiting, detail)`` for the last Tier A anchor **inside the
    current question block**, or ``None``.

    Anything above the block start belongs to an earlier, already-answered
    prompt and is ignored — that is the whole defence against
    `capture-pane -S` handing back answered checkpoints forever. No block ⇒ no
    answer: ambiguity suppresses rather than guessing.

    Last-anchor-wins within the block, for the case where a question's own text
    quotes an earlier one.
    """
    lines = _tail(screen_text, _WORKFLOW_PROMPT_TAIL_LINES)
    start = current_question_block(lines)
    if start is None:
        return None
    n = len(lines)
    best: tuple[str, str, str] | None = None
    for idx in range(start + 1, n):
        for prompt in WORKFLOW_PROMPTS:
            if prompt.regex.search(lines[idx]):
                best = (prompt.phase, prompt.waiting,
                        f"{prompt.name} anchor inside the current question block "
                        f"({n - 1 - idx} line(s) above bottom)")
    return best


def phase_from_native_kind(agent: str, kind: str) -> tuple[str, str, str] | None:
    """``(phase, waiting, detail)`` for a per-agent native dialog, or ``None``.

    ``None`` for an unmapped kind is the whole absence-safety story: a generic
    confirmation is simply not a key, so it contributes nothing.
    """
    row = NATIVE_KIND_PHASE.get((agent or "").strip().lower(), {})
    hit = row.get(kind or "")
    if hit is None:
        return None
    return hit[0], hit[1], f"native dialog '{kind}' implies {hit[0]}"


def _is_question_widget(agent: str, kind: str) -> bool:
    return (kind or "") in QUESTION_WIDGET_KINDS.get((agent or "").strip().lower(), ())


# --- Composition -----------------------------------------------------------


def compose(ledger_half: tuple[str, str],
            *,
            screen_text: str | None = None,
            awaiting_input: bool | None = None,
            awaiting_input_kind: str = "",
            agent: str = "",
            recording: tuple[str, str] = ("unknown", "")) -> PhaseSignal:
    """Combine an already-derived ledger half with the live half.

    Precedence: ``awaiting_input is True`` ? (Tier A > Tier B) : (nothing)
    > ledger > none.

    The currency gate is two conditions, both necessary. ``awaiting_input``
    proves *a* prompt is live; it does not prove the *matched* one is — an
    answered checkpoint survives in scrollback indefinitely (`capture-pane -S`
    reads history). So Tier A additionally requires the current prompt to be a
    question widget and the anchor to sit INSIDE that widget's block (see
    :func:`current_question_block`). A live tool-permission dialog reports a
    different kind, and a stale anchor above a later unrelated question sits
    outside its block — so neither can fire.

    Ambiguity always suppresses in favour of the ledger — and says which
    condition failed, because an override that silently did not happen is worse
    than one that explains itself.
    """
    ledger_phase, ledger_detail = ledger_half
    rec_state, rec_detail = recording
    consulted = ["ledger"]
    if rec_state != "unknown" or rec_detail:
        consulted.append("profile")

    def _ledger(extra: str) -> PhaseSignal:
        detail = "; ".join(p for p in (ledger_detail, extra, rec_detail) if p)
        waiting = ("WAITING" if awaiting_input is True
                   else "RUNNING" if awaiting_input is False
                   else UNKNOWN_LIVENESS)
        return PhaseSignal(
            phase=ledger_phase,
            waiting=waiting,
            source="ledger" if ledger_phase != UNKNOWN_PHASE else NO_SOURCE,
            consulted=consulted,
            recording=rec_state,
            detail=detail,
        )

    if not (agent or "").strip():
        # Not the same thing as an agent without markers: the caller simply did
        # not say. Naming t1467 here would promise a fix for a caller error.
        return _ledger("live tiers unavailable: no agent supplied")
    if not live_tiers_available(agent):
        return _ledger(
            f"live tiers unavailable: no prompt markers for agent "
            f"'{agent}' (t1467)")

    consulted.append("screen")

    if awaiting_input is not True:
        why = ("pane not awaiting input" if awaiting_input is False
               else "cannot tell whether the pane is awaiting input")
        return _ledger(f"screen tiers suppressed: {why}")

    if _is_question_widget(agent, awaiting_input_kind):
        found = phase_from_screen(screen_text or "")
        if found is not None:
            phase, waiting, detail = found
            return PhaseSignal(
                phase=phase, waiting=waiting, source="workflow-prompt",
                consulted=consulted, recording=rec_state,
                detail="; ".join(p for p in (detail, rec_detail) if p),
            )
        # A question IS live, but no workflow anchor sits inside its block —
        # it is somebody else's question (or an answered checkpoint is merely
        # still visible above it). Either way Tier A has nothing to say.
        return _ledger(
            "screen tiers suppressed: no workflow anchor inside the current "
            "question block")

    native = phase_from_native_kind(agent, awaiting_input_kind)
    if native is not None:
        phase, waiting, detail = native
        return PhaseSignal(
            phase=phase, waiting=waiting, source="native-prompt",
            consulted=consulted, recording=rec_state,
            detail="; ".join(p for p in (detail, rec_detail) if p),
        )

    return _ledger(
        f"screen tiers suppressed: no anchor and no native mapping for "
        f"kind '{awaiting_input_kind or 'none'}'")


def default_profiles_dir(task_file: str) -> str | None:
    """`<root>/aitasks/metadata/profiles` derived from the SUPPLIED task path.

    Walks up to the `aitasks/` ancestor rather than consulting cwd or env, so a
    cross-project monitor resolves the right project's profiles.
    """
    path = os.path.abspath(task_file or "")
    while True:
        parent = os.path.dirname(path)
        if parent == path:
            return None
        if os.path.basename(parent) == "aitasks":
            return os.path.join(parent, "metadata", "profiles")
        path = parent


def phase_signal(task_file: str | None = None,
                 *,
                 task_text: str | None = None,
                 screen_text: str | None = None,
                 awaiting_input: bool | None = None,
                 awaiting_input_kind: str = "",
                 agent: str = "",
                 profiles_dir: str | None = None) -> PhaseSignal:
    """The one entry point. Supply ``task_text`` to stay pure, or ``task_file``
    to have it read. An unreadable task file is not fatal — it yields an
    all-unknown ledger half, because this signal must never break its caller."""
    if task_text is None:
        try:
            with open(task_file or "", encoding="utf-8") as fh:
                task_text = fh.read()
        except OSError:
            task_text = ""
    ledger_half = phase_from_ledger_text(task_text)
    rec = recording_from_text(task_text, profiles_dir)
    return compose(ledger_half, screen_text=screen_text,
                   awaiting_input=awaiting_input,
                   awaiting_input_kind=awaiting_input_kind,
                   agent=agent, recording=rec)


UNKNOWN_LINE = format_signal(PhaseSignal(
    detail="phase signal unavailable"))


def render_phase(sig: PhaseSignal) -> str:
    """Compact one-line label for a TUI column. ``""`` when there is nothing
    honest to say, so an ungated task adds no noise.

    Shared by both monitor TUIs so the phase reads identically wherever it
    appears, and kept short because minimonitor's rows are narrow. ``UNKNOWN``
    is rendered explicitly rather than hidden — "cannot tell" is a real state,
    and a blank would read as "no phase" instead.
    """
    if sig.phase == UNKNOWN_PHASE:
        if sig.recording == "off":
            return "phase: unknown (gate recording off)"
        if "no prompt markers" in sig.detail:
            return "phase: unknown (ledger only)"
        if sig.waiting == "WAITING":
            return "phase: unknown ⏸"
        return ""
    glyph = " ⏸" if sig.waiting == "WAITING" else ""
    return f"phase: {sig.phase}{glyph}"


# --- CLI -------------------------------------------------------------------


def _cli(argv: list[str]) -> int:
    if not argv or argv[0] != "signal":
        sys.stderr.write(__doc__ or "")
        return 2
    args = argv[1:]
    if not args:
        sys.stderr.write("usage: workflow_phase.py signal <task-file> [...]\n")
        return 2
    task_file = args[0]
    screen_path = None
    awaiting = None
    kind = ""
    agent = ""
    profiles_dir = None
    rest = args[1:]
    i = 0
    while i < len(rest):
        flag = rest[i]
        value = rest[i + 1] if i + 1 < len(rest) else ""
        if flag == "--screen":
            screen_path = value
        elif flag == "--awaiting-input":
            awaiting = {"yes": True, "no": False}.get(value.lower())
        elif flag == "--kind":
            kind = value
        elif flag == "--agent":
            agent = value
        elif flag == "--profiles-dir":
            profiles_dir = value
        else:
            sys.stderr.write(f"unknown flag: {flag}\n")
            return 2
        i += 2
    screen_text = None
    if screen_path:
        try:
            screen_text = (sys.stdin.read() if screen_path == "-"
                           else open(screen_path, encoding="utf-8").read())
        except OSError:
            screen_text = None
    if profiles_dir is None:
        profiles_dir = default_profiles_dir(task_file)
    sig = phase_signal(task_file, screen_text=screen_text,
                       awaiting_input=awaiting, awaiting_input_kind=kind,
                       agent=agent, profiles_dir=profiles_dir)
    sys.stdout.write(format_signal(sig) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
