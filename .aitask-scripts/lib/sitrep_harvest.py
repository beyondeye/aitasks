#!/usr/bin/env python3
"""sitrep_harvest.py - turn finished agents' output into sitrep items (t2175_2).

The parse / identity / item-building core behind `aitask_sitrep_harvest.sh`.
It reads a frozen agent's capture (or the closing message + banner an agent
pipes in at workflow end), and writes items and stub context entries into the
repo's sitrep store ONLY through `aitask_sitrep_todo.sh` (the store's one
writer). It never writes the store itself. The wrapper owns argument
validation, the git ignore rule and the harvest mutex; this module is called
twice per harvest: `plan` (resolve, parse, decide whether there is anything to
write -- lock-free) and `apply` (with the harvest mutex held).

WHAT IS PARSED (stdlib only, no transcript reading):
  * the workflow-end banner (`.claude/skills/task-workflow/workflow-end.md`),
    `## Complete` and `## Stopped`. The grammar below is pinned against that
    file by tests/test_sitrep_harvest.py -- a banner change fails that test;
  * the wrap-up passage: the closing message the banner ends. In a capture it
    starts at the nearest `●`/`⏺` message line before the banner (stopping at a
    `❯ `/`> ` prompt line, at the previous banner, and after 200 lines). The
    range is ADVISORY -- a pointer for the sitrep agent, never evidence;
  * `Created: aitasks/<task file>` lines (aitask_create.sh's fixed output),
    because task files do not record the skill that created them;
  * trail handles `art:trail-<id>`, recorded as `trail:` pointers, never copied.

RUN IDENTITY. No text normalization is ever used as proof that two wrap-ups
are the same run: every rendering reduction (glyphs, `**`, backticks, wrapping,
NBSP) can collapse different literal commands. A run is identified by retained,
content-addressed KEY FILES that the triage item's context points at:
  run      `run=<16 hex>` + `banner=<canonical banner hex>`: written by the pipe
           path, whose wrapper prints `HARVEST_RUN:<id>` as its FIRST stdout
           line; a later capture shows that line in the harvest tool call's
           output and confirms the run only if the banner matches too;
  complete `task=t<id>` + `commit=<sha>`: Complete banners, unique per run;
  passage  `record=<id>` + `sha=<sha256 of the exact passage bytes>` + `seq=<k>`.
A run matches when ANY of its keys is already pointed at by any context entry,
whatever that item's state -- identity never depends on dismissal, so
dismissals stick and an unchanged capture is a no-op. Anything uncertain is
ADDED (a linked duplicate), never suppressed.

The canonical banner (fields re-rendered, whitespace collapsed) is used only to
link related triage items and as the marker's consistency check, never as the
identity itself.

CONFIDENCE (t2175_6). `assess` pairs every expected OCCURRENCE with its own
success -- a recognised banner with complete fields, each follow-up token, a
passage within the retain cap, each banner first line with a parsed banner
starting there, each `Created:` reference with a CREATED_RE match at its
offset, each harvest marker with the banner the identity pairing gives it
(`pair_markers`), a piped message with a banner. Any reason classifies the
input `review`: `apply` still writes every item it found, then preserves the
raw input with its diagnostics and one review item (lib/sitrep_corpus.py)
BEFORE the receipt. The receipt carries `cert=HARVEST_CERT`; a receipt
without it (from before the check) is never trusted, so that text is
re-harvested. JOINED banners (no text fence, fields inline) are parsed since
PARSER_REV 2 -- the corpus's first resolved gap.

THE SITREP AGENT'S OWN RECORD (t2175_4) is never harvested: a record whose
window matches SITREP_WINDOW_RE gets its receipt and `HARVEST_NONE:<id>|
sitrep_agent`. Its screen only echoes the store, so harvesting it would feed
the store back into itself; the receipt keeps drop/purge unblocked.

Exit codes: 0 success, 1 harvest failed (nothing promised; no receipt), 2 usage.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Run as a script, this module is `__main__`; register it under its import name
# too, so a module importing `sitrep_harvest` (lazily, below) gets THIS module --
# one HarvestFailure class, one set of constants -- not a second copy.
if __name__ == "__main__":
    sys.modules.setdefault("sitrep_harvest", sys.modules[__name__])

import sitrep_todo as st  # noqa: E402

SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WRITER = os.path.join(SCRIPTS_DIR, "aitask_sitrep_todo.sh")
SESSIONS_SH = os.path.join(SCRIPTS_DIR, "aitask_agent_sessions.sh")
PROJECTS_SH = os.path.join(SCRIPTS_DIR, "aitask_projects.sh")

STORE_NAME = ".aitask-sitrep"
#: Must equal agent_sessions.HARVEST_RECEIPT_SUFFIX (tested).
RECEIPT_SUFFIX = ".harvested"
#: The receipt's certification version (t2175_6). 2 = issued only after the
#: confidence check, with any uncertain output preserved as a review case. A
#: receipt without it (written by the t2175_2 harvest, which certified every
#: parse) authorises nothing: receipt_valid refuses it, so the capture is
#: re-harvested, and agent_sessions.capture_harvested refuses it, so drop and
#: purge keep the text until then. Must equal
#: agent_sessions.HARVEST_RECEIPT_CERT (tested).
HARVEST_CERT = 2

MAX_PASSAGE_LINES = 200
MARKER_LOOKBACK = 80
MAX_CONTINUATION = 6
MAX_RETAIN = st.MAX_RETAIN_BYTES - 1024
WRITER_TIMEOUT = 60

# --- banner grammar (pinned by tests/test_sitrep_harvest.py) -----------------

COMPLETE_KIND = "complete"
STOPPED_KIND = "stopped"
#: Label vocabulary of the banner field lines. The contract test asserts this
#: equals the label set of the workflow-end.md templates.
FIELD_LABELS = ("outcome", "follow-ups created", "reason", "next")
STOPPED_OUTCOMES = ("in-flight", "ready", "aborted", "split", "unchanged", "postponed")
#: The stopped outcomes that leave the task with work pending (an in-flight
#: task, a Ready task, a split parent), so the harvest files a stopped-self
#: item for them. `aborted`, `unchanged` and `postponed` leave nothing to act
#: on in that sense: the run ended the task's activity on purpose.
ACTIONABLE_STOPPED_OUTCOMES = ("in-flight", "ready", "split")

TASK_ID = r"[1-9][0-9]*(?:_[1-9][0-9]*)?"
FIRST_RE = re.compile(
    r"^(?P<ind>[ \t]*)(?:[●⏺][ \t]+)?(?P<glyph>[✔■]) aitask workflow "
    r"(?P<kind>complete|stopped) — t(?P<task>" + TASK_ID + r")"
    r"(?: (?P<name>\S+))?[ \t]*$")
FIELD_RE = re.compile(
    r"^(?P<ind>[ \t]*)(?P<label>outcome|follow-ups created|reason|next):"
    r"(?: (?P<val>.*?))?[ \t]*$")
FENCE_RE = re.compile(r"^[ \t]*```")
COMPLETE_OUTCOME_RE = re.compile(
    r"^archived \(commit (?P<sha>[0-9a-f]{7,40})\)(?P<parent> · parent archived)?$")
PICKWEB_OUTCOME_RE = re.compile(
    r"^implemented on branch (?P<branch>\S+) · archive pending "
    r"\(run aitask-web-merge\)$")
PUSHED_SPLIT = " · pushed: "

#: The JOINED banner (t2175_6): a banner displayed without its ```text fence,
#: whose lines markdown rendering joined into one paragraph (the reason
#: workflow-end.md requires the fence). The first line then carries the fields
#: inline, in template order, possibly terminal-wrapped onto continuation lines.
#: The flag exists so a test can build the PRE-fix parser (a copy with it set
#: to False) and prove a corpus case the old grammar missed; PARSER_REV names
#: the grammar a harvest analysis was produced with.
ACCEPT_JOINED_BANNER = True
PARSER_REV = 2
JOINED_RE = re.compile(
    r"^(?P<ind>[ \t]*)(?:[●⏺][ \t]+)?(?P<glyph>[✔■]) aitask workflow "
    r"(?P<kind>complete|stopped) — t(?P<task>" + TASK_ID + r")"
    r"(?: (?P<name>(?!outcome:)\S+))? (?P<rest>outcome: .*?)[ \t]*$")
JOINED_LABELS = {COMPLETE_KIND: ("outcome", "follow-ups created"),
                 STOPPED_KIND: ("outcome", "reason", "next")}

MSG_RE = re.compile(r"^[●⏺] ")
PROMPT_RE = re.compile(r"^(?:❯|>) ")
MARKER_RE = re.compile(r"HARVEST_RUN:([0-9a-f]{16})\b")

# --- confidence signals (t2175_6) -------------------------------------------
#: Every occurrence of a banner first line, parsed or not. A parsed banner's
#: own first line accounts for exactly one occurrence on its line.
NEAR_BANNER_RE = re.compile(r"[✔■]\s*aitask workflow (?:complete|stopped)\b")
#: Every occurrence of a `Created:` reference. It is valid only when a
#: CREATED_RE match starts at the same offset (\s covers NBSP). A draft
#: (`aitasks/new/draft_*.md`, aitask_create.sh without --commit) has no task id
#: yet, so it is deliberately not an item and not a reason (measured on the
#: explore fixture by the t2175_6 detection baseline).
NEAR_CREATED_RE = re.compile(r"Created:\s*aitasks/(?!new/)")
#: The banner pipe's first output line as the tool-call display shows it --
#: evidence that workflow-end ran, so a banner must follow and claim it.
TOOL_MARKER_RE = re.compile(r"^\s*⎿\s+HARVEST_RUN:([0-9a-f]{16})\s*$")
REASON_CODES = ("banner_incomplete", "bad_followup", "passage_truncated",
                "banner_unparsed", "created_unparsed", "marker_without_banner",
                "pipe_without_banner")
CREATED_RE = re.compile(
    r"Created: (?P<path>aitasks/(?:t(?P<p1>[1-9][0-9]*(?:_[1-9][0-9]*)?)_[^\s/]+\.md"
    r"|t(?P<par>[1-9][0-9]*)/t(?P<p2>[1-9][0-9]*_[1-9][0-9]*)_[^\s/]+\.md))(?=\s|$)")
TRAIL_RE = re.compile(r"(?<![\w:])art:trail-[A-Za-z0-9._-]*[A-Za-z0-9_-]")
LOCAL_TOKEN_RE = re.compile(r"^t?(" + TASK_ID + r")$")
XREF_TOKEN_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)#t?(" + TASK_ID + r")$")
RECORD_RE = re.compile(r"^[0-9a-f]{8}$")
RUN_RE = re.compile(r"^[0-9a-f]{16}$")

#: Line 1 of each retained file harvest writes beside a passage. The canonical
#: banner and the three identity-key kinds; `capture_file_kind` is the one
#: classifier of them (the sitrep skill's `ait sitrep triage` reads it).
BANNER_FILE_HEADER = "sitrep banner v1"
KEY_RUN_HEADER = "sitrep wrap-up run v2"
KEY_COMPLETE_HEADER = "sitrep wrap-up complete v1"
KEY_PASSAGE_HEADER = "sitrep wrap-up passage v1"
#: The identity of a review case (t2175_6): one per raw input sha256.
KEY_CASE_HEADER = st.CASE_KEY_HEADER
KEY_FILE_HEADERS = (KEY_RUN_HEADER, KEY_COMPLETE_HEADER, KEY_PASSAGE_HEADER,
                    KEY_CASE_HEADER)
#: The other retained files of a review case (t2175_6, lib/sitrep_corpus.py).
CASE_ORIGIN_HEADER = st.CASE_ORIGIN_HEADER
CASE_ANALYSIS_HEADER = st.CASE_ANALYSIS_HEADER
CASE_REVIEW_HEADER = st.CASE_REVIEW_HEADER


def capture_file_kind(first_line: str) -> str:
    """``banner`` | ``key`` | ``case`` | ``analysis`` | ``review`` |
    ``passage`` for a retained file's first line.

    Anything that is not a harvest-written header is passage text (a closing
    message, a Created-line window, a review case's excerpt) -- the content a
    context pointer is for.
    """
    line = first_line.rstrip("\n")
    if line == BANNER_FILE_HEADER:
        return "banner"
    if line in KEY_FILE_HEADERS:
        return "key"
    if line == CASE_ORIGIN_HEADER:
        return "case"
    if line == CASE_ANALYSIS_HEADER:
        return "analysis"
    if line == CASE_REVIEW_HEADER:
        return "review"
    return "passage"

#: The sitrep agent's own window (t2175_4): `monitor_core.spawn_sitrep` names it
#: SITREP_WINDOW_BASE, or `<base>-<n>` when the session already holds one
#: (`agent_launch_utils.unique_window_name`). Anchored on both ends: a near-miss
#: (`agent-sitrepx`, `agent-pick-sitrep`) is an ordinary agent and IS harvested.
SITREP_WINDOW_BASE = "agent-sitrep"
SITREP_WINDOW_RE = re.compile(r"\Aagent-sitrep(?:-[1-9][0-9]*)?\Z")


def spawn_test_pause(point: str) -> None:
    """Test seam of `monitor_core.spawn_sitrep` (test-only).

    AITASK_SITREP_SPAWN_PAUSE_FIFO=<fifo> writes ``point`` to ``<fifo>.reached``
    and blocks reading one line from the fifo, so a test can hold one spawn
    inside its lock and prove a second one waits (the `AITASK_SITREP_PAUSE_FIFO`
    pattern of the store writer). Kept here, with the window grammar, so the
    monitor core itself writes no files.
    """
    fifo = os.environ.get("AITASK_SITREP_SPAWN_PAUSE_FIFO", "")
    if not fifo:
        return
    with open(fifo + ".reached", "w", encoding="utf-8") as fh:
        fh.write(point + "\n")
    with open(fifo, encoding="utf-8") as fh:
        fh.readline()


def is_sitrep_window(name) -> bool:
    """True when ``name`` is a sitrep agent window name (the exact grammar).

    Harvest skips such records: the sitrep agent never runs workflow-end, and
    its screen only ECHOES the store (banners it is triaging, trail handles it
    reports), so harvesting it would feed the store back into itself.
    """
    return isinstance(name, str) and SITREP_WINDOW_RE.match(name) is not None


class HarvestFailure(Exception):
    """Harvest cannot complete. The message is the wire reason."""


@dataclass
class Banner:
    kind: str
    task: str
    name: str
    start: int                      # first line index
    end: int                        # exclusive
    fields: dict = field(default_factory=dict)
    commit: str = ""
    pushed: str = ""
    outcome: str = ""
    followups: list = field(default_factory=list)
    bad_followups: list = field(default_factory=list)
    complete_fields: bool = True

    def canonical(self) -> str:
        """Fields re-rendered with whitespace collapsed. For LINKING and the
        marker consistency check only -- never an identity key."""
        def c(v):
            return re.sub(r"\s+", " ", v).strip()
        lines = [BANNER_FILE_HEADER, f"kind={self.kind}", f"task=t{self.task}",
                 f"name={self.name}"]
        for label in FIELD_LABELS:
            if label in self.fields:
                lines.append(f"{label}={c(self.fields[label])}")
        return "\n".join(lines) + "\n"


def _split_joined(kind: str, rest: str) -> dict:
    """The fields of a joined banner's inline remainder.

    Labels must appear in template order, each EXACTLY once; the first
    occurrence of each label after the previous one wins. A missing label
    leaves the fields partial, so `_interpret` marks the banner incomplete (a
    review reason); a repeated label is ambiguous (see `_joined_ambiguous`)."""
    labels = JOINED_LABELS[kind]
    starts = []
    pos = 0
    for n, label in enumerate(labels):
        if n == 0:
            if not rest.startswith(label + ":"):
                break
            k, tok = 0, label + ":"
        else:
            tok = f" {label}:"
            k = rest.find(tok, pos)
            if k < 0:
                break
        starts.append((label, k, k + len(tok)))
        pos = k + len(tok)
    fields = {}
    for n, (label, _k, vstart) in enumerate(starts):
        end = starts[n + 1][1] if n + 1 < len(starts) else len(rest)
        fields[label] = rest[vstart:end].strip()
    return fields


def _joined_ambiguous(kind: str, rest: str) -> bool:
    """Does any template label occur more than once in a joined remainder?
    Then which occurrence is the field is a guess, so the banner is
    classified incomplete (its useful fields are still extracted)."""
    for label in JOINED_LABELS[kind]:
        n = rest.count(f" {label}:") + (1 if rest.startswith(f"{label}:") else 0)
        if n > 1:
            return True
    return False


def _joined_banner(lines: list, i: int, m) -> Banner:
    b = Banner(kind=m.group("kind"), task=m.group("task"),
               name=m.group("name") or "", start=i, end=i + 1)
    first_ind = len(m.group("ind").expandtabs())
    rest = m.group("rest")
    j = i + 1
    cont = 0
    while j < len(lines) and cont < MAX_CONTINUATION:
        line = lines[j]
        if (not line.strip() or FENCE_RE.match(line) or FIRST_RE.match(line)
                or JOINED_RE.match(line) or MSG_RE.match(line)
                or PROMPT_RE.match(line)):
            break
        ind = len(line) - len(line.lstrip(" \t"))
        if ind < first_ind:
            break
        rest = rest + " " + line.strip()
        cont += 1
        j += 1
    b.end = j
    rest = re.sub(r"[ \t]+$", "", rest)
    b.fields = _split_joined(b.kind, rest)
    _interpret(b)
    if _joined_ambiguous(b.kind, rest):
        b.complete_fields = False
    return b


def parse_banners(lines: list) -> list:
    """Every banner in `lines` (a capture or a piped message), in order."""
    out = []
    i = 0
    while i < len(lines):
        m = FIRST_RE.match(lines[i])
        if not m:
            jm = JOINED_RE.match(lines[i]) if ACCEPT_JOINED_BANNER else None
            if jm:
                b = _joined_banner(lines, i, jm)
                out.append(b)
                i = b.end
                continue
            i += 1
            continue
        b = Banner(kind=m.group("kind"), task=m.group("task"),
                   name=m.group("name") or "", start=i, end=i + 1)
        first_ind = len(m.group("ind").expandtabs())
        last = None
        cont = 0
        j = i + 1
        while j < len(lines) and j - i <= len(FIELD_LABELS) + MAX_CONTINUATION + 1:
            line = lines[j]
            if not line.strip() or FENCE_RE.match(line) or FIRST_RE.match(line):
                break
            fm = FIELD_RE.match(line)
            if fm:
                label = fm.group("label")
                if label in b.fields:
                    break
                b.fields[label] = fm.group("val") or ""
                last = label
                cont = 0
                j += 1
                continue
            ind = len(line) - len(line.lstrip(" \t"))
            if last is not None and ind >= first_ind and cont < MAX_CONTINUATION:
                b.fields[last] = (b.fields[last] + " " + line.strip()).strip()
                cont += 1
                j += 1
                continue
            break
        b.end = j
        _interpret(b)
        out.append(b)
        i = j
    return out


def _interpret(b: Banner) -> None:
    outcome = b.fields.get("outcome", "").strip()
    if b.kind == COMPLETE_KIND:
        if PUSHED_SPLIT in outcome:
            outcome, _, pushed = outcome.partition(PUSHED_SPLIT)
            b.pushed = pushed.strip()
        b.outcome = outcome.strip()
        cm = COMPLETE_OUTCOME_RE.match(b.outcome)
        if cm:
            b.commit = cm.group("sha")
        b.complete_fields = ("outcome" in b.fields
                             and "follow-ups created" in b.fields
                             and bool(cm or PICKWEB_OUTCOME_RE.match(b.outcome)))
        raw = b.fields.get("follow-ups created", "").strip()
        if raw and raw != "none":
            for tok in [t for t in re.split(r"[,\s]+", raw) if t]:
                if LOCAL_TOKEN_RE.match(tok) or XREF_TOKEN_RE.match(tok):
                    b.followups.append(tok)
                else:
                    b.bad_followups.append(tok)
    else:
        b.outcome = outcome
        b.complete_fields = (outcome in STOPPED_OUTCOMES
                             and "reason" in b.fields and "next" in b.fields)


def passage_bounds(lines: list, b: Banner, floor: int) -> int:
    """Start index of `b`'s closing message (advisory)."""
    lo = max(floor, b.start - MAX_PASSAGE_LINES)
    for k in range(b.start - 1, lo - 1, -1):
        if PROMPT_RE.match(lines[k]):
            return k + 1
        if MSG_RE.match(lines[k]):
            return k
    return lo


def find_marker_at(lines: list, start: int, floor: int) -> tuple:
    """``(run id, line index)`` of the nearest `HARVEST_RUN:<id>` before a
    passage, bounded by the previous banner and by a user prompt (a new
    turn); ``("", None)`` when there is none."""
    lo = max(floor, start - MARKER_LOOKBACK)
    for k in range(start - 1, lo - 1, -1):
        if PROMPT_RE.match(lines[k]):
            return "", None
        m = MARKER_RE.search(lines[k])
        if m:
            return m.group(1), k
    return "", None


def find_marker(lines: list, start: int, floor: int) -> str:
    """The nearest `HARVEST_RUN:<id>` before a passage (see find_marker_at)."""
    return find_marker_at(lines, start, floor)[0]


@dataclass(frozen=True)
class Pairing:
    """One banner with its passage start and the marker it claims."""
    banner: Banner
    start: int
    marker: str
    marker_line: object   # int line index, or None


def pair_markers(lines: list, banners: list, piped: bool) -> list:
    """The ONE passage/marker pairing, shared by the harvest (run identity)
    and the confidence check (a marker no banner claims), so the two can
    never disagree about which run a marker belongs to."""
    out = []
    floor = 0
    for b in banners:
        start = floor if piped else passage_bounds(lines, b, floor)
        run, k = ("", None) if piped else find_marker_at(lines, start, floor)
        out.append(Pairing(b, start, run, k))
        floor = b.end
    return out


def passage_bytes(lines: list, p: Pairing) -> tuple:
    """``(passage bytes, truncated?)`` -- the exact bytes the harvest retains."""
    passage = ("\n".join(lines[p.start:p.banner.end]) + "\n").encode("utf-8")
    if len(passage) > MAX_RETAIN:
        passage = passage[-MAX_RETAIN:]
        passage = passage[passage.find(b"\n") + 1:]
        return passage, True
    return passage, False


@dataclass(frozen=True)
class Reason:
    """Why a harvest is not reliable: a code from REASON_CODES, a detail
    token, and the 1-based line range of the raw input it concerns."""
    code: str
    detail: str
    a: int
    b: int

    def label(self) -> str:
        return f"{self.code}:{self.detail}" if self.detail else self.code


def assess(lines: list, banners: list, piped: bool) -> list:
    """The confidence check: every reason this input is not reliably parsed.

    Each rule pairs every OCCURRENCE of what it expects with its own success,
    never "any success in scope": a marker is claimed only by the banner the
    shared pairing gives it, a `Created:` reference only by a CREATED_RE
    match at its own offset, a banner first line only by a parsed banner
    starting on that line. Not reasons: no banner at all (an agent frozen
    mid-work), an unresolved foreign task, a missing task file.
    """
    out = []
    pairs = pair_markers(lines, banners, piped)
    for p in pairs:
        b = p.banner
        if not b.complete_fields:
            out.append(Reason("banner_incomplete", f"t{b.task}", b.start + 1, b.end))
        for tok in b.bad_followups:
            out.append(Reason("bad_followup", _one_line(tok), b.start + 1, b.end))
        if passage_bytes(lines, p)[1]:
            out.append(Reason("passage_truncated", f"t{b.task}", p.start + 1, b.end))
    starts = {b.start for b in banners}
    claimed = {p.marker_line for p in pairs if p.marker_line is not None}
    for i, line in enumerate(lines):
        n = len(NEAR_BANNER_RE.findall(line)) - (1 if i in starts else 0)
        if n > 0:
            out.append(Reason("banner_unparsed", f"L{i + 1}", i + 1, i + 1))
        if "Created:" in line:
            valid = {m.start() for m in CREATED_RE.finditer(line)}
            for m in NEAR_CREATED_RE.finditer(line):
                if m.start() not in valid:
                    out.append(Reason("created_unparsed", f"L{i + 1}", i + 1, i + 1))
        if not piped:
            tm = TOOL_MARKER_RE.match(line)
            if tm and i not in claimed:
                out.append(Reason("marker_without_banner", tm.group(1), i + 1, i + 1))
    if piped and not banners and any(ln.strip() for ln in lines):
        out.append(Reason("pipe_without_banner", "", 1, max(1, len(lines))))
    return out


def classify(data: bytes, piped: bool) -> tuple:
    """``(class, reasons)``: ``review`` when any reason fires, else
    ``reliable`` when there is content, else ``empty``."""
    text = data.decode("utf-8", "replace")
    lines = text.split("\n")
    banners = parse_banners(lines)
    reasons = assess(lines, banners, piped)
    if reasons:
        return "review", reasons
    content = bool(banners or created_tasks(lines) or trail_handles(text))
    return ("reliable" if content else "empty"), reasons


def created_tasks(lines: list) -> list:
    """[(task id, repo-relative path, line index)] for `Created:` lines."""
    out = []
    seen = set()
    for i, line in enumerate(lines):
        for m in CREATED_RE.finditer(line):
            tid = m.group("p1") or m.group("p2")
            if tid in seen:
                continue
            seen.add(tid)
            out.append((tid, m.group("path"), i))
    return out


def trail_handles(text: str) -> list:
    out = []
    for m in TRAIL_RE.finditer(text):
        h = m.group(0)
        if h not in out:
            out.append(h)
    return out


def hex16(data: bytes) -> str:
    """The name `aitask_sitrep_todo.sh retain` gives `data` (its first 16 hex)."""
    return hashlib.sha256(data).hexdigest()[:16]


def key_run(run_id: str, banner_hex: str) -> str:
    return f"{KEY_RUN_HEADER}\nrun={run_id}\nbanner={banner_hex}\n"


def key_complete(task: str, commit: str) -> str:
    return f"{KEY_COMPLETE_HEADER}\ntask=t{task}\ncommit={commit}\n"


def key_passage(record: str, passage: bytes, seq: int) -> str:
    sha = hashlib.sha256(passage).hexdigest()
    return f"{KEY_PASSAGE_HEADER}\nrecord={record}\nsha={sha}\nseq={seq}\n"


# --- repository roots -------------------------------------------------------

def _git(path: str, *args: str):
    try:
        p = subprocess.run(["git", "-C", path, *args], capture_output=True,
                           text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return 1, ""
    return p.returncode, p.stdout


def _inside_work_tree(path: str) -> bool:
    rc, out = _git(path, "rev-parse", "--is-inside-work-tree")
    return rc == 0 and out.strip() == "true"


def _main_worktree(path: str) -> str:
    # NUL-terminated records, so a path containing a line break comes back
    # whole (and is then refused by _safe_root) instead of truncated.
    rc, out = _git(path, "worktree", "list", "--porcelain", "-z")
    if rc != 0:
        return ""
    for field in out.split("\0"):
        if field.startswith("worktree "):
            return os.path.realpath(field[len("worktree "):])
    return ""


def _safe_root(root: str) -> str:
    """Refuse a root the wire protocol cannot carry verbatim. Applied to the
    FINAL root -- after realpath and main-worktree resolution -- because a
    safe-looking symlink or worktree record can resolve to a path with a line
    break in it."""
    if any(ord(ch) < 0x20 or ord(ch) == 0x7f for ch in root):
        raise HarvestFailure("root_unsupported")
    return root


def canonical_root(path: str) -> tuple:
    """(canonical root, is_git). One store per REPOSITORY: a linked worktree or
    a removed `aiwork/<task>` maps to the main worktree. Raises HarvestFailure."""
    if not path or not os.path.isabs(path):
        raise HarvestFailure("root_missing")
    if any(ord(ch) < 0x20 or ord(ch) == 0x7f for ch in path):
        # A line break would split the wire protocol; any control character in
        # a project root is refused before anything is created.
        raise HarvestFailure("root_unsupported")
    p = os.path.realpath(path)
    if os.path.isdir(p):
        if _inside_work_tree(p):
            return _safe_root(_main_worktree(p) or p), True
        return _safe_root(p), False
    anc = os.path.dirname(p)
    while anc and anc != os.path.dirname(anc) and not os.path.isdir(anc):
        anc = os.path.dirname(anc)
    if anc and os.path.isdir(anc) and _inside_work_tree(anc):
        main = _main_worktree(anc)
        if main and (p + os.sep).startswith(os.path.join(main, "aiwork") + os.sep):
            return _safe_root(main), True
    raise HarvestFailure("root_missing")


# --- task / plan lookup -----------------------------------------------------

def _task_globs(tid: str, kind: str) -> list:
    pre = "t" if kind == "task" else "p"
    base = "aitasks" if kind == "task" else "aiplans"
    if "_" in tid:
        par, _ = tid.split("_", 1)
        return [f"{base}/{pre}{par}/{pre}{tid}_*.md",
                f"{base}/archived/{pre}{par}/{pre}{tid}_*.md"]
    return [f"{base}/{pre}{tid}_*.md", f"{base}/archived/{pre}{tid}_*.md"]


def find_file(roots: list, tid: str, kind: str) -> tuple:
    """(repo-relative path, name) or ("", "")."""
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for pat in _task_globs(tid, kind):
            hits = sorted(glob.glob(os.path.join(root, pat)))
            if hits:
                rel = os.path.relpath(hits[0], root)
                stem = os.path.basename(rel)[:-3]
                prefix = ("t" if kind == "task" else "p") + tid + "_"
                return rel, stem[len(prefix):] if stem.startswith(prefix) else stem
    return "", ""


def resolve_project(name: str) -> str:
    try:
        p = subprocess.run([PROJECTS_SH, "resolve", name], capture_output=True,
                           text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return ""
    for line in p.stdout.splitlines():
        if line.startswith("RESOLVED:"):
            return line[len("RESOLVED:"):].strip()
    return ""


# --- the store --------------------------------------------------------------

class Store:
    """The writer, plus a read-only index of what the store already points at."""

    def __init__(self, root: str, store_dir: str):
        self.root = root
        self.dir = store_dir
        self.capture_owners = {}     # hex -> [item nums]
        self.trails = set()
        self.items = {}
        self.contexts = {}

    def load(self) -> None:
        try:
            todo = st.load_todo_for_read(self.dir)
        except st.FormatError as e:
            raise HarvestFailure(f"writer:store_unusable:{_one_line(str(e))}") from None
        self.items = dict(todo.items)
        self.contexts = dict(todo.contexts)
        self.capture_owners = {}
        self.trails = set()
        for num, ctx in todo.contexts.items():
            for stype, ptr in ctx.sources:
                if stype == "capture":
                    m = st.CAPTURE_RE.match(ptr)
                    if m:
                        self.capture_owners.setdefault(m.group(1), []).append(num)
                elif stype == "trail":
                    self.trails.add(ptr)

    def owners(self, hexname: str) -> list:
        return self.capture_owners.get(hexname, [])

    def ref_owner(self, ref: str) -> int:
        """The item already holding `ref` (any state), or 0. A local pre-check
        only, so an existing item costs no retain; the writer's own `EXISTS:`
        stays authoritative."""
        want = st.normalize_ref(ref)
        for num, item in self.items.items():
            if item.ref == want:
                return num
        return 0

    def run(self, args: list, stdin: bytes = b"") -> list:
        env = dict(os.environ, AITASK_SITREP_DIR=self.dir)
        try:
            p = subprocess.run([WRITER, *args], input=stdin, capture_output=True,
                               cwd=self.root, env=env, timeout=WRITER_TIMEOUT)
        except subprocess.TimeoutExpired:
            raise HarvestFailure("writer:timeout") from None
        except OSError as e:
            raise HarvestFailure(f"writer:spawn:{e.strerror or e}") from None
        out = p.stdout.decode("utf-8", "replace").splitlines()
        err = p.stderr.decode("utf-8", "replace").strip().splitlines()
        if p.returncode == 0:
            return out
        detail = _one_line(err[-1] if err else (out[-1] if out else ""))
        if p.returncode == 3:
            raise HarvestFailure("writer:lock_busy")
        if p.returncode == 4:
            raise HarvestFailure(f"writer:store_unusable:{detail}")
        if p.returncode == 2:
            raise HarvestFailure(f"writer:request:{detail}")
        raise HarvestFailure(f"writer:exit{p.returncode}:{detail}")

    def retain(self, data: bytes) -> str:
        out = self.run(["retain"], data)
        for line in out:
            if line.startswith("RETAINED:"):
                ptr = line[len("RETAINED:"):]
                if not ptr.startswith(f"sources/{hex16(data)}.txt#"):
                    raise HarvestFailure("writer:retain_name_mismatch")
                return ptr
        raise HarvestFailure("writer:retain_no_result")

    def add(self, kind: str, title: str, *, ref: str = "", group: str,
            state: str = "open", checked_now: bool, context: str) -> tuple:
        args = ["add", "--kind", kind, "--title", title, "--group", group,
                "--state", state, "--derived", "script",
                "--checked-at", "now" if checked_now else "never",
                "--context-file", "-"]
        if ref:
            args += ["--ref", ref]
        for line in self.run(args, context.encode("utf-8")):
            if line.startswith("ADDED:c"):
                self.load()
                return int(line[len("ADDED:c"):]), True
            if line.startswith("EXISTS:c"):
                return int(line[len("EXISTS:c"):]), False
        raise HarvestFailure("writer:add_no_result")


def _one_line(s: str) -> str:
    return re.sub(r"[\r\n|]+", " ", s).strip()[:200]


def _token(v: str) -> str:
    """An origin value: one token, no `|`."""
    return re.sub(r"[\s|]+", "_", v.strip())


def _title(s: str) -> str:
    s = re.sub(r"[\r\n]+", " ", s).strip()
    return s if len(s) <= st.MAX_TITLE else s[: st.MAX_TITLE - 1].rstrip() + "…"


def _lines_of(data: bytes) -> int:
    return data.count(b"\n") + (0 if data.endswith(b"\n") or not data else 1)


def _context(background: str, origin: list, sources: list, related: list) -> str:
    entry = st.ContextEntry(background=background[: st.MAX_BACKGROUND],
                            origin=[(k, v) for k, v in origin if v],
                            sources=list(sources),
                            related=sorted(set(related)))
    text = "\n".join(entry.body_lines()) + "\n"
    while len(text.encode("utf-8")) > st.MAX_CONTEXT_BYTES and entry.sources:
        # Trail pointers are the only unbounded list; drop from the end.
        trail_idx = [i for i, (t, _) in enumerate(entry.sources) if t == "trail"]
        if not trail_idx:
            break
        entry.sources.pop(trail_idx[-1])
        text = "\n".join(entry.body_lines()) + "\n"
    return text


# --- the harvest ------------------------------------------------------------

@dataclass
class Source:
    """One harvest input: a capture or a piped message, plus its provenance."""
    label: str                     # wire <src>
    data: bytes
    root: str                      # canonical root
    worktree: str = ""             # the original (possibly linked) root
    record: str = "none"
    agent: str = ""
    task: str = ""
    skill: str = ""
    pane: str = ""
    date: str = ""
    run_id: str = ""               # pipe path only
    piped: bool = False


class Harvest:
    def __init__(self, src: Source, store: Store):
        self.src = src
        self.store = store
        self.lines_out = []
        self.added = 0
        self.existing = 0
        #: [(cid num, kind, ref)] of every item this harvest added or found,
        #: in order -- the partial items a review case links (t2175_6).
        self.item_ids = []
        self.new_ids = set()
        self.reasons = []

    # wire output
    def emit(self, line: str) -> None:
        self.lines_out.append(line)

    def item(self, num: int, new: bool, kind: str, ref: str) -> None:
        if new:
            self.added += 1
            self.new_ids.add(num)
        else:
            self.existing += 1
        if (num, kind, ref or "") not in self.item_ids:
            self.item_ids.append((num, kind, ref or ""))
        self.emit(f"HARVEST_ITEM:{self.src.label}|c{num}|"
                  f"{'added' if new else 'exists'}|{kind}|{ref or '-'}")

    def origin(self, task: str, commit: str = "") -> list:
        s = self.src
        return [("agent", _token(s.agent) or "unknown"), ("task", f"t{task}" if task else ""),
                ("commit", commit), ("date", s.date), ("skill", _token(s.skill)),
                ("pane", _token(s.pane))]

    def roots(self) -> list:
        return [self.src.root] + ([self.src.worktree] if self.src.worktree
                                  and self.src.worktree != self.src.root else [])

    def run(self) -> None:
        text = self.src.data.decode("utf-8", "replace")
        lines = text.split("\n")
        banners = parse_banners(lines)
        passage_ranges = []
        seq_count = {}
        for p in pair_markers(lines, banners, self.src.piped):
            b, start = p.banner, p.start
            for tok in b.bad_followups:
                self.emit(f"HARVEST_WARN:{self.src.label}|bad_followup:{_one_line(tok)}")
            if not b.complete_fields:
                self.emit(f"HARVEST_WARN:{self.src.label}|banner_incomplete:t{b.task}")
            passage, truncated = passage_bytes(lines, p)
            if truncated:
                self.emit(f"HARVEST_WARN:{self.src.label}|passage_truncated:t{b.task}")
            passage_ranges.append((start, b.end))
            sha = hashlib.sha256(passage).hexdigest()
            seq_count[sha] = seq_count.get(sha, 0) + 1
            self.wrapup(b, passage, p.marker, seq_count[sha], start)
        self.created(lines)
        self.trails(lines, passage_ranges)
        self.reasons = assess(lines, banners, self.src.piped)

    # -- per banner
    def wrapup(self, b: Banner, passage: bytes, marker: str, seq: int,
               start: int) -> None:
        store = self.store
        canon = b.canonical().encode("utf-8")
        canon_hex = hex16(canon)
        keys = []
        if b.kind == COMPLETE_KIND and b.commit:
            keys.append(key_complete(b.task, b.commit))
        run_id = self.src.run_id if self.src.piped else marker
        if run_id:
            keys.append(key_run(run_id, canon_hex))
        if not self.src.piped:
            keys.append(key_passage(self.src.record, passage, seq))
        key_hexes = [hex16(k.encode("utf-8")) for k in keys]

        matched = []
        if self.src.piped:
            # A pipe is always a new run; only the archival commit (a repeated
            # pipe of the same Complete run) can match.
            if b.kind == COMPLETE_KIND and b.commit:
                matched = store.owners(key_hexes[0])
        else:
            for h in key_hexes:
                matched = store.owners(h)
                if matched:
                    break
        siblings = [n for n in store.owners(canon_hex)]
        triage = 0
        if matched:
            triage = min(matched)
            self.item(triage, False, "question", "")
        else:
            ptr_passage = store.retain(passage)
            ptr_canon = store.retain(canon)
            key_ptrs = [store.retain(k.encode("utf-8")) for k in keys]
            sources = [("capture", ptr_passage), ("capture", ptr_canon)]
            sources += [("capture", p) for p in key_ptrs]
            task_rel, _ = find_file(self.roots(), b.task, "task")
            plan_rel, _ = find_file(self.roots(), b.task, "plan")
            if task_rel:
                sources.append(("task", task_rel))
            if plan_rel:
                sources.append(("plan", plan_rel))
            if b.commit:
                sources.append(("commit", b.commit))
            for h in trail_handles(passage.decode("utf-8", "replace")):
                sources.append(("trail", h))
            outcome = b.outcome or "outcome unknown"
            background = (f"Closing message and banner of the t{b.task} run "
                          f"({b.kind}: {_one_line(outcome)[:80]}); its prose may "
                          "name actions to take or things to watch.")
            ctx = _context(background, self.origin(b.task, b.commit), sources, siblings)
            name = f" {b.name}" if b.name else ""
            title = _title(f"Triage wrap-up of t{b.task}{name}: turn its closing "
                           "notes into action/watch items")
            triage, new = store.add("question", title, group="now",
                                    checked_now=False, context=ctx)
            self.item(triage, new, "question", "")

        banner_lines = self._banner_ptr_range(passage, b, start)
        # The passage pointer for the task items: the banner lines inside the
        # retained passage (retained above or by the matching harvest).
        if b.kind == COMPLETE_KIND and b.complete_fields:
            for tok in b.followups:
                self.followup(b, tok, triage, passage, banner_lines)
        if b.kind == STOPPED_KIND and b.outcome in ACTIONABLE_STOPPED_OUTCOMES:
            self.stopped_self(b, triage, passage, banner_lines)

    def _banner_ptr_range(self, passage: bytes, b: Banner, start: int) -> tuple:
        n = _lines_of(passage)
        span = b.end - b.start
        last = n
        first = max(1, last - span + 1)
        return first, last

    def _passage_ptr(self, passage: bytes, rng: tuple) -> str:
        ptr = self.store.retain(passage)
        h = ptr.split("#", 1)[0]
        a, z = rng
        return f"{h}#L{a}-L{z}" if z > a else f"{h}#L{a}"

    def _known(self, ref: str, kind: str) -> bool:
        num = self.store.ref_owner(ref)
        if num:
            self.item(num, False, kind, st.normalize_ref(ref))
        return bool(num)

    def followup(self, b: Banner, tok: str, triage: int, passage: bytes,
                 rng: tuple) -> None:
        xm = XREF_TOKEN_RE.match(tok)
        ref = (f"{xm.group(1)}#t{xm.group(2)}" if xm
               else "t" + LOCAL_TOKEN_RE.match(tok).group(1))
        if self._known(ref, "task"):
            return
        sources = [("capture", self._passage_ptr(passage, rng))]
        if xm:
            project, tid = xm.group(1), xm.group(2)
            path = resolve_project(project)
            rel, name = find_file([path], tid, "task") if path else ("", "")
            state = "open" if rel else "unknown"
            label = f"{ref} {name}".strip() if name else ref
            title = f"{label} — follow-up of t{b.task}"
            if not rel:
                title += " (cross-repo, unverified)"
        else:
            tid = LOCAL_TOKEN_RE.match(tok).group(1)
            rel, name = find_file(self.roots(), tid, "task")
            state = "open" if rel else "unknown"
            label = f"t{tid} {name}".strip()
            title = f"{label} — follow-up of t{b.task}"
            if rel:
                sources.insert(0, ("task", rel))
            else:
                title += " (task file not found)"
        if b.commit:
            sources.append(("commit", b.commit))
        bg = (f"Follow-up task created by the t{b.task} run; listed until it is "
              "picked, folded, archived or dismissed.")
        ctx = _context(bg, self.origin(b.task, b.commit), sources,
                       [triage] if triage else [])
        num, new = self.store.add("task", _title(title), ref=ref, group="next",
                                  state=state, checked_now=True, context=ctx)
        self.item(num, new, "task", ref)

    def stopped_self(self, b: Banner, triage: int, passage: bytes, rng: tuple) -> None:
        ref = f"t{b.task}"
        if self._known(ref, "task"):
            return
        rel, name = find_file(self.roots(), b.task, "task")
        sources = [("capture", self._passage_ptr(passage, rng))]
        if rel:
            sources.insert(0, ("task", rel))
        nm = f" {name or b.name}".rstrip()
        title = _title(f"t{b.task}{nm} — run stopped ({b.outcome})")
        bg = (f"The task's own run stopped with outcome {b.outcome}; it is still "
              "open work.")
        ctx = _context(bg, self.origin(b.task), sources, [triage] if triage else [])
        group = "now" if b.outcome == "in-flight" else "next"
        num, new = self.store.add("task", title, ref=ref, group=group,
                                  state="open" if rel else "unknown",
                                  checked_now=True, context=ctx)
        self.item(num, new, "task", ref)

    # -- per capture
    def created(self, lines: list) -> None:
        for tid, path, i in created_tasks(lines):
            if self._known(f"t{tid}", "task"):
                continue
            window = ("\n".join(lines[max(0, i - 2): i + 3]) + "\n").encode("utf-8")
            ptr = self.store.retain(window)
            rel, name = find_file(self.roots(), tid, "task")
            sources = [("capture", ptr)]
            if rel:
                sources.insert(0, ("task", rel))
            elif not any(s == ".." for s in path.split("/")):
                sources.insert(0, ("task", path))
            who = self.src.agent or "an agent"
            title = _title(f"t{tid} {name}".rstrip() + f" — created by {who}")
            bg = ("Task created by a finished agent; listed until it is picked, "
                  "folded, archived or dismissed.")
            ctx = _context(bg, self.origin(self.src.task), sources, [])
            num, new = self.store.add("task", title, ref=f"t{tid}", group="next",
                                      state="open" if rel else "unknown",
                                      checked_now=True, context=ctx)
            self.item(num, new, "task", f"t{tid}")

    def trails(self, lines: list, ranges: list) -> None:
        inside = set()
        for a, z in ranges:
            inside.update(range(a, z))
        for i, line in enumerate(lines):
            if i in inside:
                continue
            for h in trail_handles(line):
                if h in self.store.trails:
                    self.existing += 1
                    continue
                window = ("\n".join(lines[max(0, i - 2): i + 3]) + "\n").encode("utf-8")
                ptr = self.store.retain(window)
                bg = ("Implementation trail mentioned by a finished agent; its "
                      "status is read from the trail itself.")
                ctx = _context(bg, self.origin(self.src.task),
                               [("trail", h), ("capture", ptr)], [])
                num, new = self.store.add("watch", _title(f"Trail {h}"),
                                          group="waiting", checked_now=False,
                                          context=ctx)
                self.item(num, new, "watch", "")
                self.store.trails.add(h)


def has_content(data: bytes) -> bool:
    """Is there anything to extract? (items only; see needs_apply)"""
    text = data.decode("utf-8", "replace")
    lines = text.split("\n")
    return bool(parse_banners(lines) or created_tasks(lines) or trail_handles(text))


def needs_apply(data: bytes, piped: bool) -> bool:
    """Must `apply` run (and touch a store)? Content to extract, OR a
    confidence reason: a near-miss-only capture has no items but must still
    be preserved for review, never certified as `nothing_found`."""
    return classify(data, piped)[0] != "empty"


# --- records and receipts ---------------------------------------------------

def load_record(record_id: str):
    """The record as a dict, or None when the store has no such record (nothing
    to lose). Any other failure (an unreadable store) raises -- fail closed."""
    try:
        p = subprocess.run([SESSIONS_SH, "show", record_id, "--json"],
                           capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        raise HarvestFailure("record_unreadable") from None
    for line in p.stdout.splitlines():
        if line.startswith("RECORD:"):
            try:
                return json.loads(line[len("RECORD:"):])
            except ValueError:
                raise HarvestFailure("record_unreadable") from None
    if p.returncode == 4 and f"no such record: {record_id}" in (p.stdout + p.stderr):
        return None
    raise HarvestFailure("record_unreadable")


def list_records() -> list:
    try:
        p = subprocess.run([SESSIONS_SH, "list", "--full"], capture_output=True,
                           text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        raise HarvestFailure("records_unreadable") from None
    if p.returncode != 0:
        raise HarvestFailure("records_unreadable")
    out = []
    for line in p.stdout.splitlines():
        if line.startswith("RECORD:"):
            try:
                out.append(json.loads(line[len("RECORD:"):]))
            except ValueError:
                continue
    return out


def read_capture(rec: dict):
    """(path, bytes) of the record's text capture, or (path, None) if absent."""
    path = rec.get("capture_txt") or ""
    if not path:
        return "", None
    try:
        with open(path, "rb") as fh:
            return path, fh.read()
    except FileNotFoundError:
        return path, None
    except OSError as e:
        raise HarvestFailure(f"capture_unreadable:{e.strerror or e}") from None


def receipt_text(data: bytes, store_dir: str) -> str:
    return (f"sha256={hashlib.sha256(data).hexdigest()}\nstore={store_dir}\n"
            f"cert={HARVEST_CERT}\n")


def receipt_valid(path: str, data: bytes, store_dir: str) -> bool:
    try:
        with open(path + RECEIPT_SUFFIX, "r", encoding="utf-8") as fh:
            return fh.read() == receipt_text(data, store_dir)
    except OSError:
        return False


def write_receipt(path: str, data: bytes, store_dir: str) -> None:
    target = path + RECEIPT_SUFFIX
    tmp = f"{target}.{os.getpid()}.tmp"
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(receipt_text(data, store_dir))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)
    except OSError as e:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise HarvestFailure(f"receipt_unwritable:{e.strerror or e}") from None


def fault_point(point: str) -> None:
    """Test seam (test-only): AITASK_SITREP_HARVEST_FAULT=<point> fails the
    harvest at that point, so a test proves a partial case write withholds
    the receipt. Points: case:raw, case:files, case:item, receipt."""
    if os.environ.get("AITASK_SITREP_HARVEST_FAULT", "") == point:
        raise HarvestFailure(f"fault:{point}")


def _today() -> str:
    pinned = os.environ.get("AITASK_SITREP_NOW", "")
    if re.match(r"^\d{4}-\d\d-\d\d", pinned):
        return pinned[:10]
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def record_source(rec: dict, data: bytes, root: str) -> Source:
    date = (rec.get("frozen_at") or rec.get("state_at") or "")[:10] or _today()
    op = rec.get("operation") or ""
    return Source(label=rec["id"], data=data, root=root,
                  worktree=os.path.realpath(rec.get("root") or "") if rec.get("root") else "",
                  record=rec["id"], agent=rec.get("window") or "",
                  task=rec.get("task_id") or "", skill=op if op != "raw" else "",
                  pane=rec.get("pane_id") or "", date=date)


def pane_identity() -> tuple:
    """(record id, window) of $TMUX_PANE, best-effort through the gateway."""
    pane = os.environ.get("TMUX_PANE", "")
    if not pane:
        return "none", ""
    try:
        import agent_frozen_ops as frozen_ops
        facts = frozen_ops.pane_facts(pane)
    except Exception:  # noqa: BLE001 - best-effort identity, never fatal
        return "none", ""
    rec = facts.get("record", "")
    return (rec if RECORD_RE.match(rec) else "none"), facts.get("window", "")


# --- CLI --------------------------------------------------------------------

def _final(line: str, rc: int = 0) -> int:
    print(line)
    return rc


def _work(root: str) -> str:
    """The plan -> wrapper handoff: the canonical root and NOTHING else on the
    line, so the wrapper takes the whole remainder verbatim (a `|` in a path
    is data, not a separator). canonical_root refuses control characters, so
    a root can never break the line itself."""
    return f"WORK:{_safe_root(root)}"


def cmd_plan(args) -> int:
    try:
        if args.source == "record":
            rec = load_record(args.id)
            if rec is None:
                return _final(f"HARVEST_NONE:{args.id}|no_record")
            path, data = read_capture(rec)
            if not data:
                return _final(f"HARVEST_NONE:{args.id}|no_capture")
            if is_sitrep_window(rec.get("window")):
                # The sitrep agent's own screen echoes the store (t2175_4):
                # nothing in it is new information. The receipt still records
                # that the text was read, so store `drop` and `purge` are not
                # blocked by a capture that is deliberately never harvested.
                try:
                    root, _ = canonical_root(rec.get("root") or "")
                except HarvestFailure:
                    root = rec.get("root") or ""
                write_receipt(path, data, os.path.join(root, STORE_NAME))
                return _final(f"HARVEST_NONE:{args.id}|sitrep_agent")
            if not needs_apply(data, piped=False):
                # Nothing to write anywhere -- no items AND no confidence
                # reason (t2175_6): the receipt alone records that the text
                # was read. The store path is informative; use the record
                # root's canonical form when it resolves, else the raw root.
                try:
                    root, _ = canonical_root(rec.get("root") or "")
                except HarvestFailure:
                    root = rec.get("root") or ""
                write_receipt(path, data, os.path.join(root, STORE_NAME))
                return _final(f"HARVEST_NONE:{args.id}|nothing_found")
            root, _ = canonical_root(rec.get("root") or "")
            store_dir = os.path.join(root, STORE_NAME)
            if not args.force and receipt_valid(path, data, store_dir):
                # A cached result still names the preserved-output review of
                # this input (t2175_6), so `h` and the drop show it instead of
                # "nothing to harvest". Read-only; nothing is re-extracted.
                import sitrep_corpus  # noqa: E402 - lazy: it imports this module
                line = sitrep_corpus.cached_review_line(store_dir, data, args.id)
                if line:
                    print(line)
                return _final(f"HARVEST_NONE:{args.id}|already_harvested")
            return _final(_work(root))
        if args.source == "all":
            want = os.path.realpath(args.root) if args.root else ""
            for rec in list_records():
                path = rec.get("capture_txt") or ""
                if not path or not os.path.isfile(path):
                    continue
                if want:
                    try:
                        root, _ = canonical_root(rec.get("root") or "")
                    except HarvestFailure:
                        root = os.path.realpath(rec.get("root") or "/nonexistent")
                    if root != want and os.path.realpath(rec.get("root") or "") != want:
                        continue
                print(f"RECORD:{rec['id']}")
            return 0
        # banner / capture: stdin
        data = sys.stdin.buffer.read()
        label = f"run-{args.run}" if args.source == "banner" else "capture"
        if not needs_apply(data, piped=args.source == "banner"):
            return _final(f"HARVEST_NONE:{label}|nothing_found")
        base = args.root if args.source == "capture" else os.getcwd()
        root, _ = canonical_root(os.path.abspath(base))
        return _final(_work(root))
    except HarvestFailure as e:
        label = getattr(args, "id", None) or ("capture" if args.source == "capture"
                                              else f"run-{getattr(args, 'run', '')}")
        return _final(f"HARVEST_FAILED:{label}|{e}", 1)


def cmd_apply(args) -> int:
    label = args.id if args.source == "record" else (
        f"run-{args.run}" if args.source == "banner" else "capture")
    try:
        root = os.path.realpath(args.root_canonical)
        store = Store(root, os.path.join(root, STORE_NAME))
        capture_path, captured_at = "", ""
        if args.source == "record":
            rec = load_record(args.id)
            if rec is None:
                return _final(f"HARVEST_NONE:{label}|no_record")
            path, data = read_capture(rec)
            if not data:
                return _final(f"HARVEST_NONE:{label}|no_capture")
            src = record_source(rec, data, root)
            capture_path = path
            captured_at = rec.get("frozen_at") or rec.get("state_at") or ""
        else:
            data = sys.stdin.buffer.read()
            if args.source == "banner":
                record, window = pane_identity()
                src = Source(label=label, data=data, root=root,
                             worktree=os.path.realpath(os.getcwd()), record=record,
                             agent=window, task=args.task or "", skill=args.skill or "",
                             pane=os.environ.get("TMUX_PANE", ""), date=_today(),
                             run_id=args.run, piped=True)
            else:
                src = Source(label=label, data=data, root=root,
                             worktree=os.path.realpath(args.root_given or root),
                             agent=args.agent or "", task=args.task or "",
                             skill=args.operation or "", date=_today())
        store.load()
        h = Harvest(src, store)
        review = ""
        try:
            h.run()
            if h.reasons:
                # Uncertain output (t2175_6): preserve it verbatim with its
                # diagnostics and ONE durable review item BEFORE anything can
                # certify it. A failure here raises -> HARVEST_FAILED, no
                # receipt, the capture stays protected; a retry completes it.
                import sitrep_corpus  # noqa: E402 - lazy: it imports this module
                num, new, case = sitrep_corpus.record_case(
                    store, src, h, capture_path=capture_path, captured_at=captured_at)
                h.item(num, new, "question", "")
                review = f"|review=c{num}"
                h.emit(f"HARVEST_REVIEW:{label}|c{num}|{'added' if new else 'exists'}"
                       f"|case={case}|" + ",".join(dict.fromkeys(r.code for r in h.reasons)))
        finally:
            for line in h.lines_out:
                print(line)
        fault_point("receipt")
        if args.source == "record":
            write_receipt(path, data, store.dir)
        return _final(f"HARVESTED:{label}|added={h.added}|existing={h.existing}{review}")
    except HarvestFailure as e:
        return _final(f"HARVEST_FAILED:{label}|{e}", 1)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="sitrep_harvest.py")
    sub = ap.add_subparsers(dest="phase", required=True)
    for phase in ("plan", "apply"):
        p = sub.add_parser(phase)
        s = p.add_subparsers(dest="source", required=True)
        r = s.add_parser("record")
        r.add_argument("id")
        r.add_argument("--force", action="store_true")
        b = s.add_parser("banner")
        b.add_argument("--run", required=True)
        b.add_argument("--task", default="")
        b.add_argument("--skill", default="")
        c = s.add_parser("capture")
        c.add_argument("--root", dest="root", required=True)
        c.add_argument("--agent", default="")
        c.add_argument("--task", default="")
        c.add_argument("--operation", default="")
        if phase == "plan":
            a = s.add_parser("all")
            a.add_argument("--root", default="")
        for q in (r, b, c):
            if phase == "apply":
                q.add_argument("--root-canonical", required=True)
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "run", None) is not None and not RUN_RE.match(args.run):
        print("usage: --run must be 16 lowercase hex", file=sys.stderr)
        return 2
    if getattr(args, "id", None) is not None and not RECORD_RE.match(args.id):
        print("usage: record id must be 8 lowercase hex", file=sys.stderr)
        return 2
    if args.source == "capture":
        args.root_given = args.root
    if args.phase == "plan":
        return cmd_plan(args)
    return cmd_apply(args)


if __name__ == "__main__":
    sys.exit(main())
