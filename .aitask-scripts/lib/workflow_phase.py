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

Two live tiers:

- **Tier A** (`WORKFLOW_PROMPTS`) — agent-neutral. These strings are authored by
  *task-workflow*, not by any code agent, so they read identically under every
  supported CLI. Its *currency* evidence is per-agent, though
  (`QUESTION_WIDGET_KINDS` + `QUESTION_BLOCK_BOUNDARIES`), and t1467 measured
  those for Claude Code, Codex CLI and OpenCode.
- **Tier B** (`NATIVE_KIND_PHASE`) — per-agent native dialogs, keyed on the
  monitor's `awaiting_input_kind`. **Claude only, by measurement**: neither Codex
  nor OpenCode has an `ExitPlanMode` analogue, so the only native dialogs they
  render are tool confirmations, which carry no phase. For those two agents the
  phase comes from Tier A or the ledger.

Nothing here may imply live coverage for an agent that has no markers — ask
`live_tiers_available()`, and read `PhaseSignal.resolution` to tell a resolved
agent from a pane whose command could not be mapped at all.

CLI:

    workflow_phase.py signal <task-file> [--screen <file>|-]
                             [--awaiting-input yes|no|unknown]
                             [--kind <awaiting_input_kind>] [--agent <name>]
                             [--pane-command <cmd>] [--profiles-dir <dir>]

Prints one `|`-delimited status line (see `format_signal`).
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gate_ledger as gl  # noqa: E402
import agent_keys  # noqa: E402  (canonical pane→agent mapper, t1467)

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

# How the pane's AGENT was established — orthogonal to the phase, because it
# stays true (and stays worth saying) whatever the phase turned out to be
# (t1467). Folding it into an UNKNOWN-phase cause was tried and rejected: the
# renderer consults those only when the phase is UNKNOWN, so a task with ledger
# history would render a confident `IMPLEMENT ⏸` — with the ⏸ supplied by an
# UNSCOPED match — indistinguishable from a fully resolved pane.
#   scoped      — resolved to a known agent that has live-tier markers
#   no_markers  — resolved, but this agent has no markers (ledger-only)
#   unresolved  — the caller supplied a pane command that maps to no agent
#   absent      — the caller supplied no agent at all (e.g. the plain CLI verb)
RESOLUTIONS = ("scoped", "no_markers", "unresolved", "absent", "unknown")

UNKNOWN_PHASE = "UNKNOWN"
UNKNOWN_LIVENESS = "UNKNOWN"
NO_SOURCE = "none"
UNKNOWN_RESOLUTION = "unknown"

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

# Codex's request-user-input widget renders a "Question N/M (K unanswered)"
# header directly above its question text \u2014 the same role Claude's chip plays,
# and measured (t1467, Codex 0.146.0) to appear once and only while live.
_CODEX_QUESTION_HEADER_RE = re.compile(r"^\s*Question\s+\d+\s*/\s*\d+\b")

# OpenCode has NO header line: its widget renders as a contiguous run of
# `\u2503`-gutter lines. Its block start is therefore found by a scan (see
# _opencode_block_start) rather than by matching one line.
_GUTTER_RE = re.compile(r"^\s*\u2503")

# Per-agent block-start strategies. Regex table for agents whose widget has a
# header line; a scan for those whose widget is delimited by shape instead.
# Two mechanisms rather than one is a real cost, taken deliberately: a regex
# matching the gutter character alone would match EVERY line of the block,
# including lines of an earlier already-answered widget higher in the
# scrollback \u2014 exactly the staleness the boundary exists to exclude.
QUESTION_BLOCK_BOUNDARIES: dict[str, "re.Pattern[str]"] = {
    "claude": _QUESTION_HEADER_RE,
    "codex": _CODEX_QUESTION_HEADER_RE,
}


def _opencode_block_start(lines: list[str]) -> int | None:
    """Top of the contiguous gutter run that reaches the LAST gutter line.

    A gap of non-gutter lines ends the run, so an earlier, already-answered
    widget higher in the tail is a *different* run and is excluded \u2014 the same
    property Claude's chip and Codex's header give for free.
    """
    last = None
    for idx in range(len(lines) - 1, -1, -1):
        if _GUTTER_RE.match(lines[idx]):
            last = idx
            break
    if last is None:
        return None
    start = last
    while start - 1 >= 0 and _GUTTER_RE.match(lines[start - 1]):
        start -= 1
    return start


QUESTION_BLOCK_STRATEGIES = {
    "opencode": _opencode_block_start,
}

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
# `claude_trust_folder`, `codex_yes_proceed`): absence-safety is a property of
# the table, not of a code path that must remember to check. A workspace-trust
# dialog is a pre-work gate, not a workflow phase, which is why
# `claude_trust_folder` joins that list rather than getting a row (t1474).
#
# Codex/OpenCode rows are empty by design — t1467 owns inventorying their real
# prompt surfaces. An agent with neither entry degrades to the ledger-derived
# phase, never to a guess.

QUESTION_WIDGET_KINDS: dict[str, tuple[str, ...]] = {
    "claude": ("claude_askuserquestion",),
    "codex": ("codex_question",),        # request-user-input widget (t1467)
    "opencode": ("opencode_question",),  # interactive question widget (t1467)
}

NATIVE_KIND_PHASE: dict[str, dict[str, tuple[str, str]]] = {
    "claude": {"claude_plan_approval": ("PLAN", "WAITING")},
    # Codex and OpenCode are empty BY MEASUREMENT, not by omission (t1467
    # inventoried both live): neither CLI has an ExitPlanMode analogue, so the
    # only native dialogs either renders are tool confirmations — which carry no
    # workflow phase, for the same reason `claude_proceed` has no row here.
    # Do not "fill these in" without a new measurement finding a phase-bearing
    # dialog. Consequence: for these two agents the phase comes from Tier A or
    # the ledger, never Tier B.
    "codex": {},
    "opencode": {},
}


# Re-exported, NOT reimplemented: `lib/agent_keys.py` owns the mapping so this
# module and `monitor/prompt_patterns.py` cannot drift (t1467). The public name
# and behaviour here are unchanged, so every existing caller is untouched.
agent_key_from_command = agent_keys.agent_key_from_command
agent_key_from_pane = agent_keys.agent_key_from_pane


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
    resolution: str = UNKNOWN_RESOLUTION


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
    resolution = (sig.resolution if sig.resolution in RESOLUTIONS
                  else UNKNOWN_RESOLUTION)
    consulted = ",".join(_sanitize(c) for c in sig.consulted) or "-"
    return _DELIM.join([
        f"PHASE{_FIELD_SEP}{phase}",
        f"WAITING{_FIELD_SEP}{waiting}",
        f"SOURCE{_FIELD_SEP}{source}",
        f"CONSULTED{_FIELD_SEP}{consulted}",
        f"RECORDING{_FIELD_SEP}{_sanitize(sig.recording) or 'unknown'}",
        f"RESOLUTION{_FIELD_SEP}{resolution}",
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
    # A line written before t1467 carries no RESOLUTION key at all; defaulting it
    # to the unknown member (rather than raising or guessing) is what keeps a
    # stale minimonitor's `@aitask_shadow_phase` stamp readable (t1116).
    resolution = fields.get("RESOLUTION", "")
    consulted = [c for c in fields.get("CONSULTED", "").split(",") if c and c != "-"]
    return PhaseSignal(
        phase=phase if phase in PHASES else UNKNOWN_PHASE,
        waiting=waiting if waiting in LIVENESS else UNKNOWN_LIVENESS,
        source=source if source in SOURCES else NO_SOURCE,
        consulted=consulted,
        recording=fields.get("RECORDING", "") or "unknown",
        detail=fields.get("DETAIL", ""),
        resolution=resolution if resolution in RESOLUTIONS else UNKNOWN_RESOLUTION,
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


def current_question_block(lines: list[str], agent: str = "claude") -> int | None:
    """Index of the line that STARTS the currently-rendered question widget, or
    ``None``.

    Per agent, because each CLI delimits its widget differently (t1467):

    * **Claude** — the header chip `` ☐ <Header> ``, rendered directly under the
      widget's top rule and above the question text. Measured against 2.1.226:
      it occurs exactly once, only in that widget, and only for the *live* one
      (an answered question collapses to a one-line summary carrying no chip).
    * **Codex** — the ``Question N/M`` header, the same shape and the same
      once-only property (measured, 0.146.0).
    * **OpenCode** — no header at all; the block is the contiguous ``┃``-gutter
      run (see :func:`_opencode_block_start`).

    An agent with neither a boundary nor a strategy returns ``None``, so Tier A
    suppresses and the ledger wins — absence degrades, never guesses.

    Whatever the mechanism, the question asked is the same one, and it is why
    this is a real block boundary rather than a distance heuristic: a proximity
    bound cannot work, because the widget's own inner rule sits *below* the
    question and a stale anchor can sit within any fixed number of lines of the
    bottom once a later, unrelated question renders under it. Only "is the anchor
    inside the current widget" is decidable, so that is what is asked.

    The ``agent="claude"`` default keeps every pre-t1467 caller behaving
    identically.
    """
    key = (agent or "").strip().lower()
    strategy = QUESTION_BLOCK_STRATEGIES.get(key)
    if strategy is not None:
        return strategy(lines)
    boundary = QUESTION_BLOCK_BOUNDARIES.get(key)
    if boundary is None:
        return None
    for idx in range(len(lines) - 1, -1, -1):
        if boundary.match(lines[idx]):
            return idx
    return None


def phase_from_screen(screen_text: str,
                      agent: str = "claude") -> tuple[str, str, str] | None:
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
    start = current_question_block(lines, agent)
    if start is None:
        return None
    n = len(lines)
    best: tuple[str, str, str] | None = None
    # INCLUSIVE of the boundary line: it is the first line *of* the block, and
    # for OpenCode it is the question text itself (that widget has no separate
    # header line). Claude's chip and Codex's `Question N/M` header cannot carry
    # an anchor, so including them costs nothing there.
    for idx in range(start, n):
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
            recording: tuple[str, str] = ("unknown", ""),
            current_command: str | None = None) -> PhaseSignal:
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

    agent_given = bool((agent or "").strip())
    if agent_given:
        resolution = "scoped" if live_tiers_available(agent) else "no_markers"
    elif current_command is not None:
        # The caller TRIED and the pane's command mapped to nothing. Distinct
        # from "absent" because the cause, and therefore the fix, is different.
        resolution = "unresolved"
    else:
        resolution = "absent"

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
            resolution=resolution,
        )

    if not agent_given:
        if current_command is not None:
            # Blaming the caller here would be wrong: it is the pane's command
            # that could not be mapped, and the fix is agent identity (§7's
            # @aitask_agent stamp), not the call site.
            return _ledger(
                f"live tiers unavailable: pane command "
                f"'{_sanitize(current_command) or 'unknown'}' does not resolve "
                f"to a known agent")
        # The caller simply did not say. Naming a fix here would promise one for
        # what is a caller-side omission.
        return _ledger("live tiers unavailable: no agent supplied")
    if not live_tiers_available(agent):
        return _ledger(
            f"live tiers unavailable: no prompt markers for agent '{agent}'")

    consulted.append("screen")

    if awaiting_input is not True:
        why = ("pane not awaiting input" if awaiting_input is False
               else "cannot tell whether the pane is awaiting input")
        return _ledger(f"screen tiers suppressed: {why}")

    if _is_question_widget(agent, awaiting_input_kind):
        found = phase_from_screen(screen_text or "", agent)
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
                 profiles_dir: str | None = None,
                 current_command: str | None = None) -> PhaseSignal:
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
                   agent=agent, recording=rec,
                   current_command=current_command)


UNKNOWN_LINE = format_signal(PhaseSignal(
    detail="phase signal unavailable"))


# Long / narrow wording per UNKNOWN cause. One constant per value set: both
# renderers below read this table, so a cause can never render on one surface
# and silently vanish on the other (t1479).
_UNKNOWN_TEXT: dict[str, tuple[str, str]] = {
    "recording_off": ("unknown (gate recording off)", "unknown (rec off)"),
    "ledger_only": ("unknown (ledger only)", "unknown (ledger)"),
    "waiting": ("unknown ⏸", "unknown ⏸"),
}


# Resolution qualifier, wide and narrow. Rendered OUTSIDE the UNKNOWN branch, so
# it survives a confident phase — `IMPLEMENT ⏸ (agent unresolved)` is exactly the
# case that would otherwise render clean while its ⏸ came from an unscoped match.
# Narrow gets a bare `?`, not a word: that row is ~36 cells shared with the gate
# summary (t1479), and a qualifier that pushes the counts off the line is present
# but not readable. `scoped` and `absent` add nothing — `absent` is a caller that
# never asked, and marking it would qualify every plain CLI invocation.
_RESOLUTION_SUFFIX: dict[str, tuple[str, str]] = {
    "unresolved": (" (agent unresolved)", "?"),
    "no_markers": (" (no prompt markers)", "~"),
}


def _phase_body(sig: PhaseSignal, *, narrow: bool) -> str:
    """The label-free phase text shared by both renderers; ``""`` when there is
    nothing honest to say."""
    suffix = _RESOLUTION_SUFFIX.get(sig.resolution, ("", ""))[1 if narrow else 0]
    if sig.phase == UNKNOWN_PHASE:
        if sig.recording == "off":
            cause = "recording_off"
        elif sig.resolution == "no_markers":
            # Reads the explicit field, NOT a substring of `detail`: the wording
            # of that message is human-readable prose and has already been
            # reworded once (t1467), which would have silently killed this
            # branch had it stayed a phrase match.
            cause = "ledger_only"
        elif sig.waiting == "WAITING":
            cause = "waiting"
        else:
            return f"{UNKNOWN_PHASE.lower()}{suffix}" if suffix else ""
        body = _UNKNOWN_TEXT[cause][1 if narrow else 0]
        # `ledger_only` already says why in words; a second qualifier for the
        # same cause would stutter.
        return body if cause == "ledger_only" else f"{body}{suffix}"
    glyph = " ⏸" if sig.waiting == "WAITING" else ""
    return f"{sig.phase}{glyph}{suffix}"


def render_phase(sig: PhaseSignal) -> str:
    """Compact one-line label for a TUI column. ``""`` when there is nothing
    honest to say, so an ungated task adds no noise.

    The canonical, labelled form — what ``ait monitor`` renders on its status
    row. ``UNKNOWN`` is rendered explicitly rather than hidden — "cannot tell"
    is a real state, and a blank would read as "no phase" instead.
    """
    body = _phase_body(sig, narrow=False)
    return f"phase: {body}" if body else ""


def render_phase_narrow(sig: PhaseSignal) -> str:
    """Label-free, shortened phase for a **narrow** surface (t1479).

    ``ait minimonitor`` renders the phase on the same ~36-cell line as the gate
    summary, where the ``phase: `` label costs 7 of those cells and the counts
    beside it already say what the line is about. Dropping the label and
    shortening the ``unknown (…)`` variants is what makes the merge fit; the
    labelled :func:`render_phase` stays canonical for the full monitor, which is
    why this is a second renderer rather than a shortening of the shared one.
    Both read :data:`_UNKNOWN_TEXT`, so the two forms cannot drift apart.
    """
    return _phase_body(sig, narrow=True)


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
    current_command = None
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
        elif flag == "--pane-command":
            # The pane's raw command, resolved here rather than by the caller so
            # a shell caller gets the same two-rung ladder the monitor uses.
            current_command = value
            if not agent:
                agent = agent_keys.agent_key_from_command(value)
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
                       agent=agent, profiles_dir=profiles_dir,
                       current_command=current_command)
    sys.stdout.write(format_signal(sig) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
