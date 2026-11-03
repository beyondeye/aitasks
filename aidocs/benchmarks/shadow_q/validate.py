"""Trace parsing and trial classification for the shadow ``>q`` experiment.

Pure functions over saved raw streams, so a parser fix never costs a new CLI
invocation: the harness saves every stream, and classification can be re-run
offline (``harness.py classify``).

* :func:`parse_claude` / :func:`parse_codex` turn one turn's raw stream into a
  list of normalised :class:`Event` records, in order.
* :func:`helper_calls` finds replay-helper invocations inside a shell command.
* :func:`read_coverage` decides which lines of the dispatched variant file a
  tool call read.
* :func:`classify_session` applies the three validity rules and assigns every
  ``>q`` answer slot exactly one outcome class.

Every helper-call fact comes from the CLI's own trace (command, exit status,
output). The replay stubs write nothing, so they work under Codex's read-only
sandbox.
"""
from __future__ import annotations

import json
import re
import shlex
from dataclasses import dataclass, field

REPLAY_HELPERS = (
    "aitask_shadow_capture.sh",
    "aitask_shadow_context.sh",
    "aitask_skill_resolve_profile.sh",
    "aitask_skill_render.sh",
    "aitask_explain_context.sh",
)
DISPATCH_SUFFIX = {
    "claude": "aitask-shadow-fast-/SKILL.md",
    "codex": "aitask-shadow-fast-codex-/SKILL.md",
}
DISPATCH_SKILL_NAMES = {
    "claude": {"aitask-shadow-fast-", "aitask-shadow-fast"},
    "codex": {"aitask-shadow-fast-codex-", "aitask-shadow-fast-codex"},
}
SCREEN_FORMS = {"noarg", "deep", "explicit_id", "any_pane"}
DELIVERED = ("full", "head_tail")  # verified delivery of a served helper output
WEB_TOOLS = ("web_search", "open_page", "find_in_page", "WebSearch", "WebFetch")
SHORTCODE_RX = re.compile(r"(?<![\w>])>(?:e|q|t|pd|px|pc|i|r|ps|pa|d|l|f|\?)(?![\w])")
GREETING_MIN_SHORTCODES = 3
_HELPER_RX = re.compile(r"(?:[^\s'\";|&()]*/)?\.aitask-scripts/(aitask_[A-Za-z0-9_]+\.sh)")
_OTHER_SCRIPT_RX = re.compile(r"\.aitask-scripts/(aitask_[A-Za-z0-9_]+\.sh)")
_TMUX_RX = re.compile(r"(?<![\w./-])tmux(?![\w-])")


@dataclass
class Event:
    kind: str  # text | tool | result | denial | final | meta | error
    text: str = ""
    name: str = ""
    tool_id: str = ""
    input: dict = field(default_factory=dict)
    command: str = ""
    output: str = ""
    exit_code: int | None = None
    is_error: bool = False
    meta: dict = field(default_factory=dict)


@dataclass
class Turn:
    index: int  # 1-based turn index within the session
    events: list[Event]
    exit_code: int | None = None
    killed: str = ""  # "" | limit_timeout | limit_tool_calls
    stderr_tail: str = ""

    @property
    def final_text(self) -> str:
        finals = [e.text for e in self.events if e.kind == "final" and e.text.strip()]
        if finals:
            return finals[-1]
        texts = [e.text for e in self.events if e.kind == "text" and e.text.strip()]
        return texts[-1] if texts else ""

    @property
    def has_activity(self) -> bool:
        return any(e.kind in ("text", "tool", "final") for e in self.events)


# --------------------------------------------------------------------------
# Stream parsers
# --------------------------------------------------------------------------

def _json_lines(raw: str):
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            yield json.loads(line)
        except ValueError:
            continue


def _claude_result_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for c in content:
            if isinstance(c, dict) and c.get("type") == "text":
                parts.append(c.get("text", ""))
            elif isinstance(c, str):
                parts.append(c)
        return "\n".join(parts)
    return ""


def parse_claude(raw: str) -> list[Event]:
    """Claude Code ``-p --output-format stream-json --verbose``."""
    events: list[Event] = []
    tools: dict[str, Event] = {}
    for obj in _json_lines(raw):
        t = obj.get("type")
        if t == "system" and obj.get("subtype") == "init":
            events.append(Event("meta", meta={
                "session_id": obj.get("session_id", ""),
                "model": obj.get("model", ""),
                "cwd": obj.get("cwd", ""),
                "permission_mode": obj.get("permissionMode", ""),
                "version": obj.get("claude_code_version", ""),
                "tools": obj.get("tools", []),
            }))
        elif t == "assistant":
            for c in (obj.get("message") or {}).get("content", []) or []:
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "text" and c.get("text", "").strip():
                    events.append(Event("text", text=c["text"]))
                elif c.get("type") == "tool_use":
                    inp = c.get("input") or {}
                    ev = Event("tool", name=c.get("name", ""), tool_id=c.get("id", ""),
                               input=inp, command=inp.get("command", "") if isinstance(inp, dict) else "")
                    events.append(ev)
                    tools[ev.tool_id] = ev
        elif t == "user":
            content = (obj.get("message") or {}).get("content", [])
            if not isinstance(content, list):
                continue
            for c in content:
                if isinstance(c, dict) and c.get("type") == "text" and c.get("text", "").strip():
                    events.append(Event("injected", text=c["text"]))
                if isinstance(c, dict) and c.get("type") == "tool_result":
                    tid = c.get("tool_use_id", "")
                    out = _claude_result_text(c.get("content"))
                    is_err = bool(c.get("is_error"))
                    events.append(Event("result", tool_id=tid, output=out, is_error=is_err,
                                        name=tools.get(tid, Event("x")).name))
                    if tid in tools:
                        tools[tid].output = out
                        tools[tid].is_error = is_err
                        tools[tid].exit_code = 1 if is_err else 0
        elif t == "result":
            for d in obj.get("permission_denials", []) or []:
                inp = d.get("tool_input") or {}
                events.append(Event("denial", name=d.get("tool_name", ""), tool_id=d.get("tool_use_id", ""),
                                    input=inp, command=inp.get("command", "") if isinstance(inp, dict) else ""))
            events.append(Event("final", text=obj.get("result", "") or "", is_error=bool(obj.get("is_error")),
                                meta={
                                    "subtype": obj.get("subtype", ""),
                                    "session_id": obj.get("session_id", ""),
                                    "cost_usd": obj.get("total_cost_usd"),
                                    "usage": obj.get("usage") or {},
                                    "model_usage_keys": sorted((obj.get("modelUsage") or {}).keys()),
                                    "num_turns": obj.get("num_turns"),
                                }))
    return events


def _codex_command(item: dict) -> str:
    cmd = item.get("command", "")
    if isinstance(cmd, list):
        cmd = " ".join(shlex.quote(str(c)) for c in cmd)
    return str(cmd)


def parse_codex(raw: str) -> list[Event]:
    """Codex ``exec --json`` (and ``exec resume --json``)."""
    events: list[Event] = []
    for obj in _json_lines(raw):
        t = obj.get("type")
        if t == "thread.started":
            events.append(Event("meta", meta={"thread_id": obj.get("thread_id", "")}))
        elif t == "item.started":
            item = obj.get("item") or {}
            if item.get("type") == "command_execution":
                events.append(Event("tool", name="shell", tool_id=item.get("id", ""),
                                    command=_codex_command(item)))
        elif t == "item.completed":
            item = obj.get("item") or {}
            it = item.get("type")
            if it == "agent_message":
                txt = item.get("text", "")
                if txt.strip():
                    events.append(Event("text", text=txt))
            elif it == "command_execution":
                tid = item.get("id", "")
                started = next((e for e in reversed(events) if e.kind == "tool" and e.tool_id == tid), None)
                if started is None:
                    started = Event("tool", name="shell", tool_id=tid, command=_codex_command(item))
                    events.append(started)
                started.output = item.get("aggregated_output", "") or ""
                started.exit_code = item.get("exit_code")
                status = item.get("status", "")
                started.is_error = status in ("failed", "declined") or (
                    started.exit_code not in (None, 0))
                if status == "declined":
                    events.append(Event("denial", name="shell", tool_id=tid, command=started.command))
                events.append(Event("result", tool_id=tid, output=started.output,
                                    is_error=started.is_error, exit_code=started.exit_code))
            elif it in ("file_change", "mcp_tool_call", "web_search", "open_page", "find_in_page"):
                events.append(Event("tool", name=it, tool_id=item.get("id", ""), input=item))
        elif t == "turn.completed":
            events.append(Event("final", text="", meta={"usage": obj.get("usage") or {}}))
        elif t in ("turn.failed", "error"):
            err = obj.get("error") or {}
            msg = err.get("message") if isinstance(err, dict) else str(err)
            events.append(Event("error", text=msg or obj.get("message", ""), is_error=True))
    # Codex has no separate "result" text: the final answer is the last agent message.
    texts = [e.text for e in events if e.kind == "text"]
    for e in events:
        if e.kind == "final" and not e.text and texts:
            e.text = texts[-1]
    return events


def parse(agent: str, raw: str) -> list[Event]:
    return parse_claude(raw) if agent == "claude" else parse_codex(raw)


# --------------------------------------------------------------------------
# Command analysis
# --------------------------------------------------------------------------

def unwrap_shell(command: str) -> str:
    """Strip ``bash -lc '…'`` / ``/bin/zsh -c "…"`` wrappers (repeatedly)."""
    cmd = command.strip()
    for _ in range(3):
        try:
            parts = shlex.split(cmd)
        except ValueError:
            return cmd
        if len(parts) >= 3 and parts[0].rsplit("/", 1)[-1] in ("bash", "sh", "zsh", "dash") \
                and parts[1] in ("-lc", "-c", "-l", "-ic"):
            idx = 2 if parts[1] != "-l" else 3
            if parts[1] == "-l" and len(parts) > 3 and parts[2] == "-c":
                cmd = parts[3]
            else:
                cmd = parts[idx]
            continue
        return cmd
    return cmd


@dataclass
class HelperCall:
    helper: str
    args: list[str]
    form: str
    piped: bool  # output post-processed by a later pipeline stage


def _capture_form(args: list[str]) -> str:
    if "--phase" in args:
        return "phase"
    if "-" in args:
        return "stdin"
    if "--deep" in args:
        return "deep"
    if "--any-pane" in args:
        return "any_pane"
    if any(not a.startswith("-") for a in args):
        return "explicit_id"
    return "noarg"


def helper_calls(command: str) -> tuple[list[HelperCall], list[str]]:
    """Replay-helper calls in ``command``, plus any other ``.aitask-scripts`` scripts named."""
    inner = unwrap_shell(command)
    calls: list[HelperCall] = []
    others: list[str] = []
    for m in _HELPER_RX.finditer(inner):
        name = m.group(1)
        rest = inner[m.end():]
        seg_end = len(rest)
        for op in ("|", ";", "&&", "||", "\n", ")", "&"):
            i = rest.find(op)
            if i != -1:
                seg_end = min(seg_end, i)
        seg = rest[:seg_end]
        piped = rest[seg_end:seg_end + 1] == "|" and rest[seg_end:seg_end + 2] != "||"
        try:
            args = shlex.split(seg)
        except ValueError:
            args = seg.split()
        args = [a for a in args if not re.fullmatch(r"\d?>&?\d?|2>/dev/null|>/dev/null", a)]
        if name not in REPLAY_HELPERS:
            others.append(name)
            continue
        form = _capture_form(args) if name == "aitask_shadow_capture.sh" else "default"
        calls.append(HelperCall(name, args, form, piped))
    return calls, others


def touches_tmux(command: str) -> bool:
    return bool(_TMUX_RX.search(unwrap_shell(command)))


def peeks_replay(command: str) -> bool:
    return ".replay" in command


_OUTSIDE_RX = re.compile(r"(?:^|[\s'\"=])(?:/home/|~/|\$HOME\b|/root/)|shadow_q_store")


def reaches_outside(command: str) -> bool:
    """Names a path outside the sandbox (home dirs, the private store). Flag only."""
    return bool(_OUTSIDE_RX.search(command))


def match_output(expected: str, observed: str, piped: bool) -> str:
    """``full`` | ``head_tail`` | ``transformed`` | ``head_only`` | ``mismatch``."""
    exp = expected.strip()
    obs = observed or ""
    if not exp:
        return "full"
    if exp in obs:
        return "full"
    head, tail = exp[:512].strip(), exp[-512:].strip()
    if head in obs and tail in obs:
        return "head_tail"
    if piped:
        return "transformed"
    if exp[:200].strip() in obs:
        return "head_only"
    return "mismatch"


# --------------------------------------------------------------------------
# Variant read coverage
# --------------------------------------------------------------------------

def _int(s: str) -> int | None:
    try:
        return int(s)
    except (TypeError, ValueError):
        return None


def _sed_ranges(script: str, nlines: int) -> list[tuple[int, int]] | None:
    out = []
    for part in re.split(r"[;\n]", script):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"(\d+)(?:,(\d+|\$))?p", part)
        if not m:
            return None
        a = int(m.group(1))
        b = nlines if m.group(2) == "$" else int(m.group(2) or a)
        out.append((a, b))
    return out


def read_coverage(event: Event, agent: str, nlines: int) -> tuple[str, list[tuple[int, int]]]:
    """How a tool call read the dispatched variant file.

    Returns ``(kind, ranges)``: kind ``none`` (does not touch the file),
    ``covered`` (``ranges`` lists 1-based inclusive line ranges read) or
    ``uncertain`` (names the file, but the read form is not understood).
    """
    suffix = DISPATCH_SUFFIX[agent]
    if event.kind != "tool":
        return "none", []
    if event.name == "Skill":
        skill = str(event.input.get("skill", "")).strip().lstrip("/")
        if skill in DISPATCH_SKILL_NAMES[agent]:
            return "covered", [(1, nlines)]
        return "none", []
    if event.name == "Read":
        path = str(event.input.get("file_path", ""))
        if not path.endswith(suffix):
            return "none", []
        off = _int(event.input.get("offset")) or 1
        lim = _int(event.input.get("limit")) or 2000
        return "covered", [(max(1, off), min(nlines, off + lim - 1))]
    command = event.command
    if not command or suffix not in command:
        return "none", []
    inner = unwrap_shell(command)
    ranges: list[tuple[int, int]] = []
    understood = False
    for stage_text in re.split(r"&&|;|\n", inner):
        if suffix not in stage_text and "|" not in stage_text:
            continue
        stages = [s.strip() for s in stage_text.split("|")]
        try:
            toks0 = shlex.split(stages[0]) if stages[0] else []
        except ValueError:
            continue
        if not toks0 or not any(t.endswith(suffix) for t in toks0):
            continue
        prog = toks0[0].rsplit("/", 1)[-1]
        rng: list[tuple[int, int]] | None = None
        if prog in ("cat", "less", "more", "bat", "batcat"):
            rng = [(1, nlines)]
        elif prog == "nl":
            rng = [(1, nlines)]
        elif prog == "sed" and "-n" in toks0:
            script = next((t for t in toks0[1:] if not t.startswith("-") and not t.endswith(suffix)), "")
            rng = _sed_ranges(script, nlines)
        elif prog == "head":
            n = 10
            for i, t in enumerate(toks0):
                if t == "-n" and i + 1 < len(toks0):
                    n = _int(toks0[i + 1]) or n
                elif re.fullmatch(r"-n?\d+", t):
                    n = int(t.lstrip("-n"))
            rng = [(1, min(nlines, n))]
        elif prog == "tail":
            for i, t in enumerate(toks0):
                if t == "-n" and i + 1 < len(toks0):
                    v = toks0[i + 1]
                    if v.startswith("+"):
                        rng = [(_int(v[1:]) or 1, nlines)]
                    elif _int(v) is not None:
                        rng = [(max(1, nlines - int(v) + 1), nlines)]
        elif prog == "awk":
            script = next((t for t in toks0[1:] if "NR" in t), "")
            m = re.search(r"NR\s*>=?\s*(\d+)\s*&&\s*NR\s*<=?\s*(\d+)", script)
            if m:
                rng = [(int(m.group(1)), int(m.group(2)))]
            elif re.fullmatch(r"\{?\s*print\s*\}?", script.strip("'")) or not script:
                rng = [(1, nlines)]
        if rng is None:
            continue
        # A downstream `sed -n 'a,bp'` / head narrows a full read.
        for st in stages[1:]:
            try:
                toks = shlex.split(st)
            except ValueError:
                rng = None
                break
            if not toks:
                continue
            p = toks[0].rsplit("/", 1)[-1]
            if p == "sed" and "-n" in toks:
                script = next((t for t in toks[1:] if not t.startswith("-")), "")
                sub = _sed_ranges(script, nlines)
                rng = sub if sub is not None else None
            elif p == "head":
                n = 10
                for i, t in enumerate(toks):
                    if t == "-n" and i + 1 < len(toks):
                        n = _int(toks[i + 1]) or n
                    elif re.fullmatch(r"-n?\d+", t):
                        n = int(t.lstrip("-n"))
                rng = [(rng[0][0], min(rng[0][0] + n - 1, nlines))] if rng else None
            elif p in ("grep", "rg", "wc", "awk", "cut", "tr"):
                rng = None  # filtered: not a read of the span
            if rng is None:
                break
        if rng is None:
            continue
        understood = True
        ranges.extend(rng)
    if understood:
        return "covered", ranges
    if re.search(r"(?:^|[\s|;&])(grep|rg|wc|ls|stat|sha256sum|md5sum|file)\b", inner):
        return "none", []
    return "uncertain", []


def covers(ranges: list[tuple[int, int]], span: tuple[int, int]) -> bool:
    lo, hi = span
    need = set(range(lo, hi + 1))
    for a, b in ranges:
        need -= set(range(a, b + 1))
        if not need:
            return True
    return not need


# --------------------------------------------------------------------------
# Classification
# --------------------------------------------------------------------------

@dataclass
class SessionSpec:
    agent: str
    condition: str  # smoke | fresh | repeated | minimal
    q_turns: list[int]  # turn indices that are `>q` answers
    span: tuple[int, int]  # the >q bullet in the dispatched file (1-based, inclusive)
    nlines: int
    variant_sha_ok: bool  # file hash unchanged before/after
    # expected[turn][(helper, form)] -> stdout the stub serves at that turn
    expected: dict[int, dict[tuple[str, str], str]]
    model_reported: bool = True
    setup_failed: str = ""
    # The dispatched `>q` bullet's non-blank lines, stripped: the delivery evidence a read must show.
    q_lines: list[str] = field(default_factory=list)


def _turn_helper_facts(turn: Turn, spec: SessionSpec) -> dict:
    facts = {"calls": [], "others": [], "tmux": False, "replay_peek": False, "outside_path": False,
             "web_tools": 0, "delivery": {},
             "stub_error": False, "mismatch": False, "denied_helper": False,
             "denied_other": False, "match_kinds": [], "tool_calls": 0}
    exp = spec.expected.get(turn.index, {})
    denied_ids = {e.tool_id for e in turn.events if e.kind == "denial" and e.tool_id}
    for e in turn.events:
        if e.kind == "tool":
            facts["tool_calls"] += 1
            if e.name in WEB_TOOLS:
                facts["web_tools"] += 1
        if e.kind == "tool" and e.tool_id in denied_ids:
            continue  # reported through its denial event, never as a stub error
        if e.kind == "denial":
            calls, _others = helper_calls(e.command) if e.command else ([], [])
            if calls:
                facts["denied_helper"] = True
            else:
                facts["denied_other"] = True
            continue
        if e.kind != "tool" or not e.command:
            continue
        if touches_tmux(e.command):
            facts["tmux"] = True
        if peeks_replay(e.command):
            facts["replay_peek"] = True
        if reaches_outside(e.command):
            facts["outside_path"] = True
        calls, others = helper_calls(e.command)
        facts["others"].extend(others)
        for c in calls:
            facts["calls"].append((c.helper, c.form))
            if e.exit_code not in (0, None) or (e.is_error and e.exit_code is None):
                facts["stub_error"] = True
                continue
            if c.form == "stdin":
                facts["match_kinds"].append("stdin")
                continue
            want = exp.get((c.helper, c.form))
            if want is None:
                continue
            kind = match_output(want, e.output, c.piped)
            facts["match_kinds"].append(kind)
            if c.helper == "aitask_shadow_capture.sh":
                facts["delivery"].setdefault("phase" if c.form == "phase" else "screen", []).append(kind)
            if kind == "mismatch":
                facts["mismatch"] = True
    return facts


def greeting_index(turn: Turn) -> int | None:
    for i, e in enumerate(turn.events):
        if e.kind in ("text", "final") and len(set(SHORTCODE_RX.findall(e.text))) >= GREETING_MIN_SHORTCODES:
            return i
    return None


def capture_before_greeting(turn: Turn) -> bool:
    g = greeting_index(turn)
    for i, e in enumerate(turn.events):
        if g is not None and i >= g:
            break
        if e.kind == "tool" and e.command:
            calls, _ = helper_calls(e.command)
            if any(c.helper in ("aitask_shadow_capture.sh", "aitask_shadow_context.sh") for c in calls):
                return True
    return False


def _succeeded(e: Event) -> bool:
    """The tool call returned, without error (exit 0 / not is_error)."""
    return e.exit_code == 0 and not e.is_error


def delivered(corpus: str, q_lines: list[str]) -> bool:
    """Every line of the `>q` bullet appears in what the reads actually returned."""
    flat = " ".join(corpus.split())
    return all(" ".join(ln.split()) in flat for ln in q_lines)


def variant_load(turns: list[Turn], spec: SessionSpec) -> str:
    """``loaded`` | ``not_loaded`` | ``uncertain`` (from turn 1's reads).

    A read counts only if it **succeeded** (exit 0 / no error), and the bullet
    counts as loaded only if the successful reads' returned text **contains every
    line of it**. A covering read whose output does not show the bullet (CLI
    truncation, an unparseable form) is ``uncertain``, never ``loaded``.
    """
    if not turns:
        return "not_loaded"
    ranges: list[tuple[int, int]] = []
    corpus: list[str] = []
    uncertain = False
    skill_loaded = False
    for e in turns[0].events:
        if e.kind == "injected" and skill_loaded:
            corpus.append(e.text)
            continue
        kind, rng = read_coverage(e, spec.agent, spec.nlines)
        if kind == "none":
            continue
        if not _succeeded(e):
            continue  # a failed or unanswered read delivers nothing
        if kind == "uncertain":
            uncertain = True
            continue
        ranges.extend(rng)
        corpus.append(e.output)
        if e.name == "Skill":
            skill_loaded = True
    if not covers(ranges, spec.span):
        return "uncertain" if uncertain else "not_loaded"
    if spec.q_lines and not delivered("\n".join(corpus), spec.q_lines):
        return "uncertain"
    return "loaded"


def classify_session(turns: list[Turn], spec: SessionSpec) -> dict:
    """Return ``{"session": {...}, "trials": [ {turn_index, outcome, flags}, ... ]}``."""
    flags: dict = {}
    session_outcome = "ok"
    trials = []
    by_index = {t.index: t for t in turns}
    first = by_index.get(1)
    load = variant_load(turns, spec) if first else "not_loaded"
    if first is not None:
        flags["capture_before_greeting"] = capture_before_greeting(first)
        flags["greeting_seen"] = greeting_index(first) is not None
    flags["variant_load"] = load
    cumulative_infra = ""
    helpers_seen: set[str] = set()
    others_seen: set[str] = set()
    for turn in sorted(turns, key=lambda t: t.index):
        facts = _turn_helper_facts(turn, spec)
        helpers_seen.update(f"{h}:{f}" for h, f in facts["calls"])
        others_seen.update(facts["others"])
        if facts["tmux"]:
            flags["tmux"] = True
        if facts["replay_peek"]:
            flags["replay_peek"] = True
        if facts["denied_other"]:
            flags["denied_off_path"] = True
        if facts["outside_path"]:
            flags["outside_path"] = True
        if facts["match_kinds"]:
            flags.setdefault("match_kinds", [])
            flags["match_kinds"] = sorted(set(flags["match_kinds"]) | set(facts["match_kinds"]))
        if not cumulative_infra:
            if facts["stub_error"]:
                cumulative_infra = "stub_error"
            elif facts["mismatch"]:
                cumulative_infra = "stub_output_mismatch"
            elif facts["denied_helper"]:
                cumulative_infra = "permission_denied"
        if turn.index not in spec.q_turns:
            continue
        trials.append(_classify_q_turn(turn, facts, spec, load, cumulative_infra, by_index))
    flags["off_path_helpers"] = sorted(others_seen)
    flags["helper_infra"] = cumulative_infra
    if spec.setup_failed:
        session_outcome = f"infra_failure:{spec.setup_failed}"
    return {"session": {"outcome": session_outcome, "flags": flags,
                        "helpers_called": sorted(helpers_seen)},
            "trials": trials}


def _classify_q_turn(turn: Turn, facts: dict, spec: SessionSpec, load: str,
                     cumulative_infra: str, by_index: dict[int, Turn]) -> dict:
    flags: dict = {"web_tools": facts.get("web_tools", 0)}

    def out(cls: str) -> dict:
        return {"turn_index": turn.index, "outcome": cls, "flags": flags}

    if spec.setup_failed:
        return out(f"infra_failure:{spec.setup_failed}")
    # Any earlier turn that died before output is an infra failure for every later slot.
    for i in range(1, turn.index):
        prev = by_index.get(i)
        if prev is None:
            return out("infra_failure:launch_error")
        if prev.killed == "limit_timeout" and not prev.has_activity:
            return out("infra_failure:limit_timeout")
        if prev.exit_code not in (0, None) and not prev.has_activity:
            return out("infra_failure:launch_error")
    if not spec.variant_sha_ok:
        return out("infra_failure:sha_mismatch")
    if not spec.model_reported:
        return out("infra_failure:model_unverified")
    if turn.killed == "limit_timeout" and not turn.has_activity:
        return out("infra_failure:limit_timeout")
    if turn.exit_code not in (0, None) and not turn.has_activity:
        return out("infra_failure:launch_error")
    if cumulative_infra:
        return out(f"infra_failure:{cumulative_infra}")
    if facts["tmux"]:
        return out("subject_noncompliance:advisory_violation")
    if turn.killed == "limit_tool_calls":
        return out("subject_noncompliance:limit_tool_calls")
    if turn.killed == "limit_timeout":
        return out("subject_noncompliance:limit_timeout")
    if load == "uncertain":
        return out("uncertain_load")
    if load == "not_loaded":
        return out("subject_noncompliance:variant_not_loaded")
    forms = {f for h, f in facts["calls"] if h == "aitask_shadow_capture.sh"}
    if not (forms & SCREEN_FORMS) or "phase" not in forms:
        flags["capture_forms"] = sorted(forms)
        return out("subject_noncompliance:no_fresh_capture")
    screen_kinds = facts["delivery"].get("screen", [])
    phase_kinds = facts["delivery"].get("phase", [])
    if not any(k in DELIVERED for k in screen_kinds) or not any(k in DELIVERED for k in phase_kinds):
        flags["capture_delivery"] = sorted(set(screen_kinds + phase_kinds))
        if "transformed" in screen_kinds + phase_kinds:
            return out("subject_noncompliance:capture_not_delivered")
        return out("uncertain_delivery")
    if not turn.final_text.strip():
        return out("subject_noncompliance:no_answer")
    return out("valid")


ADEQUATE_MIN_COULD_CHOOSE = 2


def adequate(judgments: list[dict]) -> bool | None:
    """Pre-registered adequacy of one valid answer from its **calibrated** judgments.

    Adequate iff every calibrated judgment has ``failure_flag`` false **and** the mean
    ``could_choose`` over them is >= 2. A flag from either judge makes the answer
    inadequate (conservative). Returns None when no calibrated judgment exists.
    """
    usable = [j for j in judgments if j.get("calibrated")]
    if not usable:
        return None
    if any(j.get("failure_flag") for j in usable):
        return False
    mean_cc = sum(float(j["could_choose"]) for j in usable) / len(usable)
    return mean_cc >= ADEQUATE_MIN_COULD_CHOOSE


def summarise(trials: list[dict], judgments: dict[str, list[dict]] | None = None) -> dict:
    """Compliance, overall success and the conditional-quality n, side by side.

    * ``compliance_rate`` = ``valid`` / (attempted − infra − uncertain − not_run).
    * ``overall_success`` = valid **and adequate** (see :func:`adequate`) over the same
      denominator. Only computed when ``judgments`` (trial_id -> judgments) are given. A
      valid answer without a calibrated judgment counts as not adequate and is reported as
      ``adequacy_unknown``.
    * the sensitivity lines repeat both with every attempted (launched or refused) slot.
    * ``conditional_quality_n`` = number of ``valid`` answers (quality is reported over them).
    """
    n = len(trials)
    counts: dict[str, int] = {}
    for t in trials:
        key = t["outcome"].split(":", 1)[0]
        counts[key] = counts.get(key, 0) + 1
    valid = counts.get("valid", 0)
    not_run = counts.get("not_run", 0)
    excluded = (counts.get("infra_failure", 0) + counts.get("uncertain_load", 0)
                + counts.get("uncertain_delivery", 0) + not_run)
    denom = n - excluded
    sens = n - not_run
    out = {
        "attempted": n,
        "counts": counts,
        "compliance_rate": (valid / denom) if denom else None,
        "denominator": denom,
        "compliance_sensitivity": (valid / sens) if sens else None,
        "conditional_quality_n": valid,
    }
    if judgments is not None:
        good = unknown = 0
        for t in trials:
            if t["outcome"] != "valid":
                continue
            a = adequate(judgments.get(t.get("trial_id", ""), []))
            if a is None:
                unknown += 1
            elif a:
                good += 1
        out.update({"overall_success": (good / denom) if denom else None,
                    "overall_success_sensitivity": (good / sens) if sens else None,
                    "adequate": good, "adequacy_unknown": unknown})
    return out
