#!/usr/bin/env python3
"""sitrep_corpus.py - harvest review cases and the parser-improvement corpus (t2175_6).

When the harvest's confidence check (`sitrep_harvest.assess`) finds a reason
the output was not reliably parsed, the harvest calls :func:`record_case`
BEFORE it writes its receipt. A case keeps the whole raw input verbatim plus
the diagnostics, and queues ONE durable "Analyze unparsed agent output" review
item for the sitrep agent. Every write goes through `aitask_sitrep_todo.sh`
(the store's one writer); this module never writes the store itself, except
`export`, which writes a fixture directory OUTSIDE the store.

THE FILES (all content-addressed and immutable; nothing ever deletes them):
  raw/<16 hex>.txt   the raw input, byte for byte (`retain-raw`); its name is
                     the case id: the first 16 hex of the input's sha256
  cases/ ORIGIN      `sitrep harvest case origin v1` -- one per distinct
                     SOURCE IDENTITY of that input (record, run, source mode,
                     agent, task, capture path, capture time). No harvest
                     timestamp, so a retry of one identity rewrites identical
                     bytes (a no-op), while another record or run with the
                     same bytes keeps its own provenance
  cases/ ANALYSIS    `sitrep harvest analysis v1` -- one per (origin, parser
                     revision): class, reasons with raw-input line ranges,
                     warnings, and the partial items that harvest wrote. The
                     durable link from an origin to its items
  cases/ KEY         `sitrep harvest case key v1` -- the identity (input=sha256)
  cases/ REVIEW      `sitrep harvest review v1` -- append-only review records
  sources/ EXCERPT   the lines around the first reason (a short `PASSAGE:`),
                     under an excerpt header line

TRUST. `cases/` is written only through `retain-case` (case-record headers
only) and is the ONLY place a case is read from. `sources/` also holds
harvested passages whose text an agent controls; the review item's context
points at byte-identical `sources/` copies of its origin, analysis and key
(context pointers must be `sources/`), and a `sources/` file is treated as a
case record only when its trusted `cases/` twin exists. The excerpt starts
with its own header, so no excerpt can equal a case record byte for byte.

IDENTITY. One review item per INPUT: the item's context points at the key, and
a key already owned by the case's review item (any state; recognised by
trusted provenance -- the key plus an origin or analysis of the same case --
never by its editable title) means that item is reported
`exists` -- never a duplicate, and a done or dismissed review stays closed.
Provenance is per ORIGIN: an owned key still gets this origin's files. Write
order is raw, excerpt, origin, analysis, key, then the item LAST, so an
existing item implies its files, and a retry completes a partial attempt.

CASE STATUS (`list`), from the review ITEM: pending (open -- also when a
review record exists but closing the item failed or was stale), dismissed
(always wins), then the item's ACCEPTED outcome -- `reviewed: <outcome>`,
written only by a successful close: resolved (a parser change handles it) or
reviewed. Review records are history and never decide the status.
incomplete: records without a review item (a harvest that failed before its
item; the next harvest of that input completes it).

Verbs (`aitask_sitrep_harvest.sh case <verb>` / `ait sitrep case <verb>`;
every verb takes `--root <path>`, default `.`, mapped to the canonical root):
  list [--pending|--reviewed]      CASE:<hex>|<status>|c<N>|<item state>|
                                   <codes>|origins=<n>|record=|agent=|task=|
                                   captured_at=|parser=<rev>  ...  | NO_CASES
  show <hex>                       INPUT:<raw>|ok|missing|mismatch, then per
                                   origin ORIGIN: / ANALYSIS: / REASON: / ITEM:
                                   lines, EXCERPT:, REVIEW:, REVIEW_ITEM:
  read <hex> [--lines a-b]         the raw input (verified first), decoded
  review <hex> --outcome O [--gap T] [--note T] [--recovered c1,c2]
         [--parser REV] [--fixture PATH] [--item c<N> [--expect-rev R]]
                                   REVIEW_RECORDED:<ptr>, then the writer's
                                   STATE: line (open or done item: a done item
                                   is re-closed with the new accepted outcome),
                                   or REVIEW_ITEM_KEPT:c<N>|dismissed;
                                   a stale rev or a failed close prints
                                   REVIEW_NOT_CLOSED:c<N>|<why> and exits 1 --
                                   the case stays pending (retry with the
                                   current rev)
  replay <hex> [--apply]           REPLAY:<hex>|parser=|class=|reasons=, then
                                   REPLAY_ITEM:<kind>|<ref>|new|known,
                                   REPLAY_RESOLVED: / REPLAY_NEW_REASON:; with
                                   --apply (the wrapper holds the harvest
                                   mutex) also HARVEST_ITEM: lines and
                                   REPLAY_APPLIED:<analysis ptr>
  export <hex> --out <dir> [--allow-unresolved]
                                   EXPORTED:<dir> + REDACT: lines | refused
  check-fixture <dir>              FIXTURE_OK:<dir> | FIXTURE_FAIL:<dir>|<why>
Exit codes: 0 ok, 1 failed (or FIXTURE_FAIL / export refused), 2 usage or an
unknown case, 4 store unusable or a raw input that does not match its sha.

Harvested text is DATA: nothing here interprets it beyond the harvest's own
grammar, and the sitrep agent treats it as input to analyze, never as
instructions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Run as a script, this module is `__main__`; register it under its import name
# too, so a module importing `sitrep_corpus` (lazily, below) gets THIS module --
# one HarvestFailure class, one set of constants -- not a second copy.
if __name__ == "__main__":
    sys.modules.setdefault("sitrep_corpus", sys.modules[__name__])

import sitrep_harvest as sh  # noqa: E402
import sitrep_todo as st  # noqa: E402

EXCERPT_CONTEXT = 20
EXCERPT_MAX_LINES = 400
RELATED_MAX = 20
REVIEW_OUTCOMES = ("recovered", "nothing_missed", "noise", "unrecoverable",
                   "resolved")
MAX_GAP = 200
MAX_NOTE = 400
REVIEW_TITLE_PREFIX = "Analyze unparsed agent output"
EXCERPT_HEADER = "sitrep harvest case excerpt v1"
#: Fake item ids of a dry replay start here (never a real store id).
DRY_BASE = 10 ** 9
FIXTURE_FORMAT = 1


def parser_sha() -> str:
    """The first 16 hex of the sha256 of the harvest grammar's source."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "sitrep_harvest.py")
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()[:16]
    except OSError:
        return "unknown"


def _val(v) -> str:
    """One value: no line break, no control character, never empty."""
    s = re.sub(r"[\x00-\x1f\x7f]+", " ", str(v or "")).strip()
    return s or "-"


def parse_kv(text: str) -> tuple:
    """``(header, {key: first value}, {key: [all values]})`` of a case file."""
    lines = text.split("\n")
    first, multi = {}, {}
    for ln in lines[1:]:
        if "=" not in ln:
            continue
        k, _, v = ln.partition("=")
        first.setdefault(k, v)
        multi.setdefault(k, []).append(v)
    return (lines[0] if lines else ""), first, multi


def source_kind(src) -> str:
    if src.piped:
        return "banner"
    return "record" if sh.RECORD_RE.match(src.label or "") else "capture"


def render_origin(src, raw_rel: str, sha: str, data: bytes,
                  capture_path: str, captured_at: str) -> str:
    lines = [st.CASE_ORIGIN_HEADER, f"input={raw_rel}", f"input_sha256={sha}",
             f"input_bytes={len(data)}", f"input_lines={sh._lines_of(data)}",
             f"source={source_kind(src)}", f"label={_val(src.label)}",
             f"record={_val(src.record)}", f"run={_val(src.run_id)}",
             f"agent={_val(src.agent)}",
             f"task={'t' + src.task if src.task else '-'}",
             f"skill={_val(src.skill)}", f"pane={_val(src.pane)}",
             f"project={_val(src.root)}", f"worktree={_val(src.worktree)}",
             f"capture_path={_val(capture_path)}",
             f"captured_at={_val(captured_at)}"]
    return "\n".join(lines) + "\n"


def render_analysis(case: str, origin: str, cls: str, reasons: list,
                    warns: list, items: list) -> str:
    lines = [sh.CASE_ANALYSIS_HEADER, f"case={case}", f"origin={origin}",
             f"parser={sh.PARSER_REV}", f"parser_sha={parser_sha()}",
             f"class={cls}"]
    lines += [f"reason={r.code}|L{r.a}-L{r.b}|{_val(r.detail)}" for r in reasons]
    lines += [f"warn={_val(w)}" for w in warns]
    lines += [f"item=c{n}|{kind}|{ref or '-'}" for n, kind, ref in items]
    return "\n".join(lines) + "\n"


def key_case(sha: str) -> str:
    return f"{sh.KEY_CASE_HEADER}\ninput={sha}\n"


def render_review(case: str, at: str, by: str, outcome: str, gap: str,
                  note: str, recovered: list, parser: str, fixture: str) -> str:
    lines = [sh.CASE_REVIEW_HEADER, f"case={case}", f"at={at}", f"by={_val(by)}",
             f"outcome={outcome}", f"gap={_val(gap)}", f"note={_val(note)}",
             "recovered=" + (",".join(f"c{n}" for n in recovered) or "-"),
             f"parser={_val(parser)}", f"fixture={_val(fixture)}"]
    return "\n".join(lines) + "\n"


def excerpt_bytes(data: bytes, reason) -> bytes:
    """The raw lines around ``reason`` as a retainable passage (UTF-8, no NUL,
    within the retain cap). A convenience pointer only: the raw input is
    complete."""
    lines = data.decode("utf-8", "replace").replace("\0", "�").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    lo = max(1, reason.a - EXCERPT_CONTEXT)
    hi = min(max(1, len(lines)), reason.b + EXCERPT_CONTEXT)
    hi = min(hi, lo + EXCERPT_MAX_LINES - 1)
    chunk = lines[lo - 1:hi] or [""]
    head = f"{EXCERPT_HEADER} lines={lo}-{lo + len(chunk) - 1}"
    out = ("\n".join([head] + chunk) + "\n").encode("utf-8")
    while len(out) > sh.MAX_RETAIN and len(chunk) > 1:
        chunk.pop()
        out = ("\n".join([head] + chunk) + "\n").encode("utf-8")
    if len(out) > sh.MAX_RETAIN:
        out = out[:sh.MAX_RETAIN].decode("utf-8", "ignore").encode("utf-8") + b"\n"
    return out


def _warns(h) -> list:
    out = []
    for line in h.lines_out:
        if line.startswith("HARVEST_WARN:"):
            out.append(line.split("|", 1)[1] if "|" in line else line)
    return out


def _codes(reasons) -> str:
    return ",".join(dict.fromkeys(r.code for r in reasons))


# --- recording a case (called by sitrep_harvest.cmd_apply) -------------------

def retain_raw(store, data: bytes) -> str:
    """Retain ``data`` verbatim; ``raw/<hex>.txt``. Raises HarvestFailure."""
    if len(data) > st._raw_max():
        raise sh.HarvestFailure("case_input_too_large")
    if b"\0" in data:
        # Bash (the writer's stdin buffer) cannot carry NUL: refuse rather
        # than retain bytes that are not the input.
        raise sh.HarvestFailure("case_input_has_nul")
    want = hashlib.sha256(data).hexdigest()
    for line in store.run(["retain-raw"], data):
        if line.startswith("RETAINED_RAW:"):
            rel, _, rest = line[len("RETAINED_RAW:"):].partition("|")
            sha, _, _n = rest.partition("|")
            if sha != want or rel != f"raw/{want[:16]}.txt":
                raise sh.HarvestFailure("case_raw_mismatch")
            return rel
    raise sh.HarvestFailure("writer:retain_raw_no_result")


def is_review_owner(item, ctx, store_dir: str, case: str, keyhex: str) -> bool:
    """Is ``item`` the review item of ``case``? By TRUSTED PROVENANCE, never by
    its (user-editable) title: a script-derived question whose context points
    at the case key AND at an origin or analysis record of this case, both
    with their trusted cases/ twins. Harvested passages cannot pose as one:
    no retained passage is byte-identical to a case record (each carries a
    banner, Created, trail or excerpt line a record never has)."""
    if item is None or ctx is None or item.kind != "question" or item.derived != "script":
        return False
    hexes = []
    for stype, ptr in ctx.sources:
        if stype == "capture":
            m = st.CAPTURE_RE.match(ptr)
            if m:
                hexes.append(m.group(1))
    if keyhex not in hexes or st.read_case_record(store_dir, keyhex) is None:
        return False
    for h in hexes:
        text = st.read_case_record(store_dir, h)
        if text is None:
            continue
        head, first, _ = parse_kv(text)
        if head == sh.CASE_ANALYSIS_HEADER and first.get("case") == case:
            return True
        if head == st.CASE_ORIGIN_HEADER and first.get("input_sha256", "")[:16] == case:
            return True
    return False


def retain_case(store, data: bytes) -> str:
    """Retain a TRUSTED case record; ``cases/<hex>.txt``."""
    want = f"cases/{sh.hex16(data)}.txt"
    for line in store.run(["retain-case"], data):
        if line.startswith("RETAINED_CASE:"):
            if line[len("RETAINED_CASE:"):] != want:
                raise sh.HarvestFailure("writer:retain_case_name_mismatch")
            return want
    raise sh.HarvestFailure("writer:retain_case_no_result")


def retain_record(store, data: bytes) -> str:
    """A case record in BOTH namespaces: trusted (cases/) and the byte-identical
    sources/ copy a context pointer needs. Returns the sources/ pointer."""
    retain_case(store, data)
    return store.retain(data)


def review_owners(store, keyhex: str, case: str) -> list:
    """The review items of ``case`` (whose key file is ``keyhex``)."""
    return [n for n in store.owners(keyhex)
            if is_review_owner(store.items.get(n), store.contexts.get(n), store.dir,
                               case, keyhex)]


def record_case(store, src, h, capture_path: str = "",
                captured_at: str = "") -> tuple:
    """Preserve ``src.data`` as a review case; ``(item num, new?, case hex)``.

    Always writes this origin's files (provenance is per origin); adds the
    review item only when no item owns the case key yet. Raises
    HarvestFailure on any failure, so the caller withholds its receipt."""
    data = src.data
    sha = hashlib.sha256(data).hexdigest()
    case = sha[:16]
    reasons = list(h.reasons)
    sh.fault_point("case:raw")
    raw_rel = retain_raw(store, data)
    sh.fault_point("case:files")
    ptr_excerpt = store.retain(excerpt_bytes(data, reasons[0]))
    ptr_origin = retain_record(store, render_origin(src, raw_rel, sha, data, capture_path,
                                                    captured_at).encode("utf-8"))
    origin_file = "cases/" + ptr_origin.split("#", 1)[0].split("/", 1)[1]
    ptr_analysis = retain_record(store, render_analysis(
        case, origin_file, "review", reasons, _warns(h), h.item_ids).encode("utf-8"))
    key = key_case(sha).encode("utf-8")
    ptr_key = retain_record(store, key)
    sh.fault_point("case:item")
    owners = review_owners(store, sh.hex16(key), case)
    if owners:
        return min(owners), False, case
    codes = _codes(reasons)
    who = src.agent or src.label
    background = ("Raw output of a finished agent that the harvest could not "
                  f"parse reliably ({codes}); the whole input and its "
                  "diagnostics are retained for review.")
    sources = [("capture", ptr_excerpt), ("capture", ptr_origin),
               ("capture", ptr_analysis), ("capture", ptr_key)]
    related = sorted({n for n, _k, _r in h.item_ids})[:RELATED_MAX]
    ctx = sh._context(background, h.origin(src.task), sources, related)
    task = f" of t{src.task}" if src.task else ""
    title = sh._title(f"{REVIEW_TITLE_PREFIX}{task} ({who}): {codes}")
    num, new = store.add("question", title, group="now", checked_now=False,
                         context=ctx)
    return num, new, case


def cached_review_line(store_dir: str, data: bytes, label: str) -> str:
    """For a cached (`already_harvested`) result: the `HARVEST_REVIEW:` line of
    this input's preserved-output review, or ``""``. Read-only, lock-free."""
    sha = hashlib.sha256(data).hexdigest()
    keyhex = sh.hex16(key_case(sha).encode("utf-8"))
    if st.read_case_record(store_dir, keyhex) is None:
        return ""
    try:
        c = scan_cases(store_dir).get(sha[:16])
    except (st.FormatError, OSError):
        return ""
    if c is None or c.item is None:
        return ""
    codes = ",".join(dict.fromkeys(l.split(":")[0] for l in _reason_labels(c.latest_analysis())))
    return f"HARVEST_REVIEW:{label}|c{c.item.num}|exists|case={c.hex}|{codes or '-'}"


# --- reading the corpus ------------------------------------------------------

@dataclass
class Case:
    hex: str
    sha: str = ""
    origins: list = field(default_factory=list)    # [(ptr, first)]
    analyses: list = field(default_factory=list)   # [(ptr, first, multi)]
    reviews: list = field(default_factory=list)    # [(ptr, first)]
    keys: list = field(default_factory=list)       # [key file hex]
    excerpt: str = ""
    item: object = None                            # sitrep_todo.Item or None

    def raw_rel(self) -> str:
        return f"raw/{self.hex}.txt"

    def latest_analysis(self):
        if not self.analyses:
            return None
        return max(self.analyses, key=lambda a: (_int(a[1].get("parser")),
                                                 a[1].get("origin") == "replay"))

    def first_analysis(self):
        if not self.analyses:
            return None
        return min(self.analyses, key=lambda a: (_int(a[1].get("parser")),
                                                 a[1].get("origin") == "replay"))

    def accepted_outcome(self) -> str:
        """The outcome of the ACCEPTED completion: the one `case review` wrote
        into the item's own outcome when its close succeeded (the writer's
        record, `reviewed: <outcome>`). Review records are history: a stale or
        failed attempt leaves one, but never this."""
        m = re.match(r"reviewed: ([a-z_]+)", (self.item.outcome if self.item else "") or "")
        return m.group(1) if m else ""

    def status(self) -> str:
        """From the review ITEM: its state, then its accepted outcome."""
        if self.item is None:
            return "incomplete"
        if self.item.state in ("open", "unknown"):
            return "pending"
        if self.item.state == "dismissed":
            return "dismissed"
        return "resolved" if self.accepted_outcome() == "resolved" else "reviewed"


def _int(v) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def scan_cases(store_dir: str) -> dict:
    """Every case in the store: ``{case hex: Case}``. A scan of the TRUSTED
    `cases/` namespace only -- never `sources/`, where harvested text could
    pose as a record -- and never the item contexts, so a case is
    discoverable whatever its item says."""
    cases = {}
    sdir = os.path.join(store_dir, "cases")
    try:
        names = sorted(os.listdir(sdir))
    except OSError:
        names = []
    headers = set(st.CASE_RECORD_HEADERS)
    for name in names:
        m = re.fullmatch(r"([0-9a-f]{16})\.txt", name)
        path = os.path.join(sdir, name)
        if not m or os.path.islink(path):
            continue
        try:
            with open(path, "rb") as fh:
                data = fh.read(st.MAX_RETAIN_BYTES + 1)
        except OSError:
            continue
        text = data.decode("utf-8", "replace")
        head, first, multi = parse_kv(text)
        if head not in headers:
            continue
        if head == st.CASE_ORIGIN_HEADER:
            sha = first.get("input_sha256", "")
        elif head == sh.KEY_CASE_HEADER:
            sha = first.get("input", "")
        else:
            sha = ""
        hexname = sha[:16] if re.fullmatch(r"[0-9a-f]{64}", sha) else first.get("case", "")
        if not re.fullmatch(r"[0-9a-f]{16}", hexname or ""):
            continue
        c = cases.setdefault(hexname, Case(hexname))
        if sha:
            c.sha = sha
        ptr = f"cases/{m.group(1)}.txt"
        if head == st.CASE_ORIGIN_HEADER:
            c.origins.append((ptr, first))
        elif head == sh.CASE_ANALYSIS_HEADER:
            c.analyses.append((ptr, first, multi))
        elif head == sh.CASE_REVIEW_HEADER:
            c.reviews.append((ptr, first))
        else:
            c.keys.append(m.group(1))
    if cases:
        todo = st.load_todo_for_read(store_dir)
        owner = {}
        for num, ctx in todo.contexts.items():
            for stype, p in ctx.sources:
                if stype == "capture":
                    cm = st.CAPTURE_RE.match(p)
                    if cm:
                        owner.setdefault(cm.group(1), []).append(num)
        for c in cases.values():
            nums = sorted({n for k in c.keys for n in owner.get(k, [])
                           if is_review_owner(todo.items.get(n), todo.contexts.get(n),
                                              store_dir, c.hex, k)})
            if nums:
                c.item = todo.items.get(nums[0])
                ctx = todo.contexts.get(nums[0])
                caps = [p for t, p in ctx.sources if t == "capture"] if ctx else []
                c.excerpt = caps[0] if caps else ""
            c.reviews.sort(key=lambda r: r[1].get("at", ""))
    return cases


def raw_state(store_dir: str, c: Case) -> str:
    path = os.path.join(store_dir, c.raw_rel())
    if not os.path.isfile(path) or os.path.islink(path):
        return "missing"
    return "ok" if c.sha and st.raw_input_ok(store_dir, c.raw_rel(), c.sha) else "mismatch"


def read_raw(store_dir: str, c: Case) -> bytes:
    if raw_state(store_dir, c) != "ok":
        raise st.FormatError(os.path.join(store_dir, c.raw_rel()), 0,
                             "raw input is missing or does not match its sha256")
    with open(os.path.join(store_dir, c.raw_rel()), "rb") as fh:
        return fh.read()


# --- replay ------------------------------------------------------------------

class DryStore(sh.Store):
    """A read-only store for replays: the real index (or an empty one), with
    retain and add simulated in memory. Nothing is ever written."""

    def __init__(self, root: str, store_dir):
        super().__init__(root, store_dir or "")
        self._next = DRY_BASE
        self._refs = {}

    def load(self) -> None:
        if self.dir and os.path.isdir(self.dir):
            super().load()

    def run(self, args, stdin=b""):  # pragma: no cover - never reached
        raise sh.HarvestFailure("dry:write_attempted")

    def retain(self, data: bytes) -> str:
        return f"sources/{sh.hex16(data)}.txt#L1-L{max(1, sh._lines_of(data))}"

    def ref_owner(self, ref: str) -> int:
        return super().ref_owner(ref) or self._refs.get(st.normalize_ref(ref), 0)

    def add(self, kind, title, *, ref="", group, state="open", checked_now,
            context) -> tuple:
        if ref:
            owner = self.ref_owner(ref)
            if owner:
                return owner, False
        self._next += 1
        if ref:
            self._refs[st.normalize_ref(ref)] = self._next
        # The real Store.add reloads its index, so the context's capture and
        # trail pointers own their files from now on (a repeated commit, run
        # or passage key in the same input then matches). Mirror that.
        try:
            entry = st.validate_context_input(context, None)
        except st.RequestError:
            entry = st.ContextEntry()
        for stype, ptr in entry.sources:
            if stype == "capture":
                m = st.CAPTURE_RE.match(ptr)
                if m:
                    self.capture_owners.setdefault(m.group(1), []).append(self._next)
            elif stype == "trail":
                self.trails.add(ptr)
        self.items[self._next] = st.Item(self._next, 1, kind, state, group, "never",
                                         st.normalize_ref(ref or ""), "script", "", title)
        self.contexts[self._next] = entry
        return self._next, True


def source_from_origin(first: dict, data: bytes, root: str):
    task = first.get("task", "-")
    run = first.get("run", "-")
    return sh.Source(
        label=first.get("label", "capture"), data=data, root=root,
        worktree="" if first.get("worktree", "-") == "-" else first["worktree"],
        record=first.get("record", "none"),
        agent="" if first.get("agent", "-") == "-" else first["agent"],
        task="" if task in ("-", "") else task.lstrip("t"),
        skill="" if first.get("skill", "-") == "-" else first["skill"],
        pane="" if first.get("pane", "-") == "-" else first["pane"],
        date=sh._today(), run_id="" if run == "-" else run,
        piped=first.get("source") == "banner")


def dry_harvest(data: bytes, piped: bool, root: str, store_dir=None,
                first=None):
    """``(Harvest, class)`` of a replay that writes nothing."""
    first = dict(first or {})
    first.setdefault("source", "banner" if piped else "capture")
    src = source_from_origin(first, data, root)
    store = DryStore(root, store_dir)
    store.load()
    h = sh.Harvest(src, store)
    h.run()
    cls, _ = sh.classify(data, src.piped)
    return h, cls


# --- CLI ---------------------------------------------------------------------

def _store_dir(args) -> tuple:
    root = getattr(args, "root_canonical", None)
    if root:
        root = os.path.realpath(root)
    else:
        try:
            root, _ = sh.canonical_root(os.path.abspath(args.root))
        except sh.HarvestFailure as e:
            print(f"ROOT_FAILED:{e}")
            raise SystemExit(1) from None
    return root, os.path.join(root, sh.STORE_NAME)


def _find(store_dir: str, hexname: str) -> Case:
    if not re.fullmatch(r"[0-9a-f]{16}", hexname or ""):
        print(f"Error: a case id is 16 lowercase hex: {hexname!r}", file=sys.stderr)
        raise SystemExit(2)
    c = scan_cases(store_dir).get(hexname)
    if c is None:
        print(f"NOT_FOUND:{hexname}")
        raise SystemExit(2)
    return c


def _reason_labels(analysis) -> list:
    if analysis is None:
        return []
    out = []
    for v in analysis[2].get("reason", []):
        code, _, rest = v.partition("|")
        _rng, _, detail = rest.partition("|")
        out.append(f"{code}:{detail}" if detail and detail != "-" else code)
    return out


def cmd_list(args) -> int:
    _root, store_dir = _store_dir(args)
    cases = scan_cases(store_dir)
    rows = []
    for hexname in sorted(cases):
        c = cases[hexname]
        status = c.status()
        if args.pending and status not in ("pending", "incomplete"):
            continue
        if args.reviewed and status not in ("reviewed", "resolved", "dismissed"):
            continue
        o = c.origins[0][1] if c.origins else {}
        la = c.latest_analysis()
        codes = ",".join(dict.fromkeys(l.split(":")[0] for l in _reason_labels(la))) or "-"
        item = (f"c{c.item.num}|{c.item.state}" if c.item else "-|-")
        rows.append(f"CASE:{hexname}|{status}|{item}|{codes}|origins={len(c.origins)}"
                    f"|record={o.get('record', '-')}|agent={o.get('agent', '-')}"
                    f"|task={o.get('task', '-')}|captured_at={o.get('captured_at', '-')}"
                    f"|parser={la[1].get('parser', '-') if la else '-'}")
    print("\n".join(rows) if rows else "NO_CASES")
    return 0


def cmd_show(args) -> int:
    _root, store_dir = _store_dir(args)
    c = _find(store_dir, args.case)
    print(f"CASE:{c.hex}|{c.status()}")
    print(f"INPUT:{c.raw_rel()}|{raw_state(store_dir, c)}")
    by_origin = {}
    for a in c.analyses:
        by_origin.setdefault(a[1].get("origin", "-"), []).append(a)
    for ptr, o in c.origins:
        print(f"ORIGIN:{ptr}|source={o.get('source', '-')}|record={o.get('record', '-')}"
              f"|run={o.get('run', '-')}|agent={o.get('agent', '-')}"
              f"|task={o.get('task', '-')}|captured_at={o.get('captured_at', '-')}")
        _print_analyses(by_origin.pop(ptr.split("#", 1)[0], []))
    for orphan in by_origin.values():
        _print_analyses(orphan)
    if c.excerpt:
        print(f"EXCERPT:{c.excerpt}")
    for ptr, r in c.reviews:
        print(f"REVIEW:{ptr}|{r.get('outcome', '-')}|{r.get('at', '-')}|{r.get('gap', '-')}")
    if c.item is not None:
        print(f"REVIEW_ITEM:c{c.item.num}|{c.item.state}|{c.item.rev}")
    return 0


def _print_analyses(analyses) -> None:
    for ptr, a, multi in sorted(analyses, key=lambda x: _int(x[1].get("parser"))):
        print(f"ANALYSIS:{ptr}|origin={a.get('origin', '-')}|parser={a.get('parser', '-')}"
              f"|class={a.get('class', '-')}")
        for v in multi.get("reason", []):
            print(f"REASON:{v}")
        for v in multi.get("item", []):
            print(f"ITEM:{v}")


def cmd_read(args) -> int:
    _root, store_dir = _store_dir(args)
    c = _find(store_dir, args.case)
    try:
        data = read_raw(store_dir, c)
    except st.FormatError:
        print(f"INPUT_MISMATCH:{c.raw_rel()}")
        return 4
    lines = data.decode("utf-8", "replace").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    a, b = 1, len(lines)
    if args.lines:
        m = re.fullmatch(r"([1-9][0-9]*)(?:-([1-9][0-9]*))?", args.lines)
        if not m:
            print("Error: --lines takes a or a-b (1-based)", file=sys.stderr)
            return 2
        a = int(m.group(1))
        b = min(len(lines), int(m.group(2) or a))
    sys.stdout.write("".join(ln + "\n" for ln in lines[a - 1:b]))
    return 0


def _one(name: str, value: str, limit: int) -> str:
    if re.search(r"[\x00-\x1f\x7f]", value or ""):
        raise st.RequestError(f"{name} must be a single line without control characters")
    value = (value or "").strip()
    if len(value) > limit:
        raise st.RequestError(f"{name} is longer than {limit} characters")
    return value


def cmd_review(args) -> int:
    root, store_dir = _store_dir(args)
    c = _find(store_dir, args.case)
    try:
        gap = _one("--gap", args.gap, MAX_GAP)
        note = _one("--note", args.note, MAX_NOTE)
        parser = _one("--parser", args.parser, 40)
        fixture = _one("--fixture", args.fixture, 200)
        if fixture and (fixture.startswith(("/", "~")) or ".." in fixture.split("/")):
            raise st.RequestError("--fixture must be a repo-relative path without '..'")
        recovered = [st.parse_id(t.strip()) for t in args.recovered.split(",") if t.strip()]
        item_num = st.parse_id(args.item) if args.item else None
    except st.RequestError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    if item_num is not None and (c.item is None or c.item.num != item_num):
        print(f"Error: c{item_num} is not the review item of case {c.hex}", file=sys.stderr)
        return 2
    store = sh.Store(root, store_dir)
    try:
        ptr = retain_case(store, render_review(c.hex, st.now_ts(), args.by, args.outcome,
                                               gap, note, recovered, parser,
                                               fixture).encode("utf-8"))
    except sh.HarvestFailure as e:
        print(f"REVIEW_FAILED:{c.hex}|{e}")
        return 1
    # Recording the interpretation is NOT completing the review: the case
    # stays pending until the item is actually closed below.
    print(f"REVIEW_RECORDED:{ptr}")
    if item_num is None:
        return 0
    if c.item.state == "dismissed":
        # A dismissal is the user's: it stays; the record above is history.
        print(f"REVIEW_ITEM_KEPT:c{item_num}|dismissed")
        return 0
    # Open -> done, or done -> done with a NEW accepted outcome (e.g. a later
    # `resolved` once a parser change handles the case). The item's outcome is
    # the accepted result; only a successful close changes it.
    outcome = f"reviewed: {args.outcome}" + (f"; gap: {gap}" if gap else "")
    outcome = outcome.replace("|", "/")[: st.MAX_OUTCOME].rstrip()
    cmd = ["set-state", f"c{item_num}", "done", "--outcome", outcome]
    if args.expect_rev is not None:
        cmd += ["--expect-rev", str(args.expect_rev)]
    try:
        sh.fault_point("review:close")
        out = store.run(cmd)
    except sh.HarvestFailure as e:
        print(f"REVIEW_NOT_CLOSED:c{item_num}|{e}")
        return 1
    for line in out:
        print(line)
    if not any(ln.startswith(f"STATE:c{item_num}|done|") for ln in out):
        stale = next((ln for ln in out if ln.startswith("STALE:")), "")
        why = f"stale:{stale.rsplit('|', 1)[-1]}" if stale else "not_closed"
        print(f"REVIEW_NOT_CLOSED:c{item_num}|{why}")
        return 1
    return 0


def cmd_replay(args) -> int:
    root, store_dir = _store_dir(args)
    c = _find(store_dir, args.case)
    try:
        data = read_raw(store_dir, c)
    except st.FormatError:
        print(f"INPUT_MISMATCH:{c.raw_rel()}")
        return 4
    first = c.origins[0][1] if c.origins else {}
    piped = first.get("source") == "banner"
    before = _reason_labels(c.latest_analysis())
    if args.apply:
        if not getattr(args, "root_canonical", None):
            print("Error: replay --apply runs through aitask_sitrep_harvest.sh "
                  "(it holds the harvest mutex)", file=sys.stderr)
            return 2
        src = source_from_origin(first, data, root)
        store = sh.Store(root, store_dir)
        try:
            store.load()
            h = sh.Harvest(src, store)
            try:
                h.run()
            finally:
                for line in h.lines_out:
                    print(line)
            cls, _ = sh.classify(data, piped)
            ptr = retain_case(store, render_analysis(
                c.hex, "replay", cls, h.reasons, _warns(h), h.item_ids).encode("utf-8"))
        except sh.HarvestFailure as e:
            print(f"REPLAY_FAILED:{c.hex}|{e}")
            return 1
    else:
        h, cls = dry_harvest(data, piped, root, store_dir, first)
        ptr = ""
    new_ids = h.new_ids
    now = [r.label() for r in h.reasons]
    print(f"REPLAY:{c.hex}|parser={sh.PARSER_REV}|class={cls}|reasons={','.join(now) or '-'}")
    for n, kind, ref in h.item_ids:
        print(f"REPLAY_ITEM:{kind}|{ref or '-'}|{'new' if n in new_ids else 'known'}")
    for label in before:
        if label not in now:
            print(f"REPLAY_RESOLVED:{label}")
    for label in now:
        if label not in before:
            print(f"REPLAY_NEW_REASON:{label}")
    if ptr:
        print(f"REPLAY_APPLIED:{ptr}")
    return 0


def _expectations(h, cls: str) -> dict:
    refs = sorted({ref for _n, _k, ref in h.item_ids if ref})
    kinds = {}
    for _n, kind, _r in h.item_ids:
        kinds[kind] = kinds.get(kind, 0) + 1
    return {"expect_class": cls, "expect_refs": refs, "expect_kinds": kinds}


def cmd_export(args) -> int:
    root, store_dir = _store_dir(args)
    c = _find(store_dir, args.case)
    try:
        data = read_raw(store_dir, c)
    except st.FormatError:
        print(f"INPUT_MISMATCH:{c.raw_rel()}")
        return 4
    out = os.path.abspath(args.out)
    if os.path.lexists(out):
        print(f"EXPORT_REFUSED:{c.hex}|exists:{out}")
        return 1
    first = c.origins[0][1] if c.origins else {}
    piped = first.get("source") == "banner"
    h, cls = dry_harvest(data, piped, "/nonexistent")
    if cls == "review" and not args.allow_unresolved:
        print(f"EXPORT_REFUSED:{c.hex}|unresolved:"
              + ",".join(r.label() for r in h.reasons))
        return 1
    gap = c.reviews[-1][1].get("gap", "-") if c.reviews else "-"
    doc = {"format": FIXTURE_FORMAT, "case": c.hex, "piped": piped,
           "reasons_before": _reason_labels(c.first_analysis()), "gap": gap,
           "parser": sh.PARSER_REV}
    doc.update(_expectations(h, cls))
    os.makedirs(out)
    with open(os.path.join(out, "input.txt"), "wb") as fh:
        fh.write(data)
    with open(os.path.join(out, "case.json"), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"EXPORTED:{out}")
    print("REDACT:input.txt is a verbatim agent capture -- remove other projects' "
          "content and conversation text before committing; then re-run "
          "check-fixture on the redacted copy")
    print("REDACT:the raw case stays in the gitignored store; only a reviewed, "
          "redacted copy belongs under tests/fixtures/")
    return 0


def check_fixture(path: str) -> tuple:
    """``(ok, why)``: does the CURRENT parser extract what the fixture expects?"""
    try:
        with open(os.path.join(path, "case.json"), encoding="utf-8") as fh:
            doc = json.load(fh)
        with open(os.path.join(path, "input.txt"), "rb") as fh:
            data = fh.read()
    except (OSError, ValueError) as e:
        return False, f"unreadable:{e}"
    if doc.get("format") != FIXTURE_FORMAT:
        return False, f"format:{doc.get('format')}"
    h, cls = dry_harvest(data, bool(doc.get("piped")), "/nonexistent")
    if cls != doc.get("expect_class"):
        return False, (f"class:{cls}!={doc.get('expect_class')}:"
                       + ",".join(r.label() for r in h.reasons))
    got = {ref for _n, _k, ref in h.item_ids if ref}
    missing = [r for r in doc.get("expect_refs", []) if r not in got]
    if missing:
        return False, "missing_refs:" + ",".join(missing)
    kinds = {}
    for _n, kind, _r in h.item_ids:
        kinds[kind] = kinds.get(kind, 0) + 1
    for kind, n in sorted(doc.get("expect_kinds", {}).items()):
        if kinds.get(kind, 0) < n:
            return False, f"kind:{kind}:{kinds.get(kind, 0)}<{n}"
    return True, ""


def cmd_check_fixture(args) -> int:
    ok, why = check_fixture(args.dir)
    print(f"FIXTURE_OK:{args.dir}" if ok else f"FIXTURE_FAIL:{args.dir}|{why}")
    return 0 if ok else 1


def cmd_lockroot(args) -> int:
    root, _ = _store_dir(args)
    print(f"LOCK_ROOT:{sh._safe_root(root)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    import sitrep_cli  # noqa: E402 - lazy: sitrep_cli imports this module
    ap = argparse.ArgumentParser(prog="ait sitrep case", allow_abbrev=False)
    sub = ap.add_subparsers(dest="verb", required=True)

    def mk(name):
        p = sub.add_parser(name, allow_abbrev=False)
        p.add_argument("--root", default=".", type=sitrep_cli.root_arg)
        p.add_argument("--root-canonical", default=None, help=argparse.SUPPRESS)
        return p

    p = mk("list")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--pending", action="store_true")
    g.add_argument("--reviewed", action="store_true")
    mk("show").add_argument("case")
    p = mk("read")
    p.add_argument("case")
    p.add_argument("--lines", default="")
    p = mk("review")
    p.add_argument("case")
    p.add_argument("--outcome", required=True, choices=REVIEW_OUTCOMES)
    p.add_argument("--gap", default="")
    p.add_argument("--note", default="")
    p.add_argument("--recovered", default="")
    p.add_argument("--parser", default="")
    p.add_argument("--fixture", default="")
    p.add_argument("--item", default="")
    p.add_argument("--expect-rev", type=int, default=None)
    p.add_argument("--by", default="sitrep")
    p = mk("replay")
    p.add_argument("case")
    p.add_argument("--apply", action="store_true")
    p = mk("export")
    p.add_argument("case")
    p.add_argument("--out", required=True)
    p.add_argument("--allow-unresolved", action="store_true")
    sub.add_parser("check-fixture", allow_abbrev=False).add_argument("dir")
    return ap


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    lockroot = bool(argv) and argv[0] == "lockroot"
    if lockroot:
        argv = argv[1:]
    args = build_parser().parse_args(argv)
    try:
        if lockroot:
            return cmd_lockroot(args)
        return {"list": cmd_list, "show": cmd_show, "read": cmd_read,
                "review": cmd_review, "replay": cmd_replay, "export": cmd_export,
                "check-fixture": cmd_check_fixture}[args.verb](args)
    except st.FormatError as e:
        print(f"Error: store unusable: {e}", file=sys.stderr)
        return 4
    except BrokenPipeError:
        return 1


if __name__ == "__main__":
    sys.exit(main())
