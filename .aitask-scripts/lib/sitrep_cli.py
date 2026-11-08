#!/usr/bin/env python3
"""sitrep_cli.py - `ait sitrep`'s read-only verbs (t2175_4): the skill's facts.

`open` (the sitrep window) lives in `monitor/sitrep_open.py`: it orchestrates the
tmux launch stack, and lib/ must not reach up into a TUI package. The wire
contract of every verb is also in `aitask_sitrep.sh`'s header.

  root [--root <path>]
      The canonical project root (a linked or removed `aiwork/` worktree maps to
      the main worktree -- the one store's root), then whether the cwd is it.
        ROOT:<path>  then  CWD_OK | CWD_MISMATCH:<cwd>
        ROOT_FAILED:<reason>                       exit 1

  triage <id> [--root <path>]     one triage item
  triage --open [--root <path>]   every open triage item, then the batch lines
      The mechanical facts of triaging harvested wrap-up items, so they are code
      rather than agent prose. The agent judges; this only reports. Per item:
        ORIGIN:<k=v ...>       the item's origin tokens (agent= task= commit= ...)
        PASSAGE:<ptr>          the first `capture:` source (the closing passage)
        BANNER:<ptr>           a retained canonical banner (identity, not prose)
        KEY:<ptr>              a retained identity key (never point items at it)
        CASE:/ANALYSIS:/REVIEW:<ptr>  a review case's origin, analysis and
                               review records (t2175_6)
        REVIEW_CASE:<hex>|<codes>     the item is an "Analyze unparsed agent
                               output" review of that case: read it with
                               `ait sitrep case show <hex>` / `case read`
        CAPTURE:<ptr>          another retained passage
        TASK:/PLAN:/COMMIT:<v> the copied pointers
        TRAIL_WATCHED:<handle>|c<M>|<state>   a kind=watch item (any state)
                               carries exactly this `trail:` pointer
        TRAIL_UNWATCHED:<handle>              no watch carries it
        DERIVED:c<M>|<kind>|<state>|<title>   a derived=agent item whose
                               `related:` names this item (an earlier triage)
        TRIAGE:c<N>|<state>|<rev>             the item's LAST line
      `--open` then prints, once per distinct handle no watch carries:
        BATCH_TRAIL_UNWATCHED:<handle>|c<a>,c<b>   every open triage item naming it
      or NO_TRIAGE when no triage item is open. A watch is proposed per BATCH
      line, never per item line: two pending wrap-ups naming one trail get one
      watch, related to both (each item is read before anything is written, so
      the per-item lines cannot see each other's proposals).
      NOT_FOUND:c<N> / NOT_TRIAGE:c<N> (not kind=question derived=script) exit 2;
      an unreadable store exits 4.

      A watch counts only when its kind is `watch`: the triage question itself
      carries every `trail:` pointer of its passage (harvest records in-passage
      handles nowhere else), so counting it would suppress every first watch.

`--root` (every verb, here and in `monitor/sitrep_open.py`) is checked by
`root_arg` inside the parser: empty or with a `..` segment -> exit 2, before
anything reads the path. Option abbreviations are disabled, so `--root P` and
`--root=P` are the only spellings.

Exit codes: 0 ok, 1 root failed, 2 usage or bad id, 4 store unusable. Stdlib only.
"""

from __future__ import annotations

import argparse
import os
import sys

_LIB = os.path.dirname(os.path.abspath(__file__))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import sitrep_harvest as sh  # noqa: E402
import sitrep_todo as st  # noqa: E402


def root_arg(value: str) -> str:
    """argparse ``type`` of every ``--root``: the ONE check of the value.

    Runs inside the parser, so it covers every spelling the parser accepts
    (``--root P``, ``--root=P``; abbreviations are disabled) and runs before
    anything reads the path: an empty value and a ``..`` segment exit 2.
    """
    if not value:
        raise argparse.ArgumentTypeError("--root must not be empty")
    if "/../" in f"/{value}/":
        raise argparse.ArgumentTypeError(f"path '{value}' contains a '..' segment")
    return value


#: The exit-0 `open` wire lines and their toast wording (t2211_2 added the two
#: repair outcomes of the agent + TUI window).
_OPEN_SUCCESS = {
    "SITREP_SPAWNED": "Sitrep window opened",
    "SITREP_FOCUSED": "Switched to the sitrep window",
    "SITREP_ADDED_TUI": "Sitrep TUI added to the sitrep window",
    "SITREP_RESPAWNED_AGENT": "Sitrep agent restarted beside its TUI",
}


def sitrep_open_message(rc: int, out: str) -> "tuple[str, str]":
    """``(message, severity)`` for `aitask_sitrep.sh open` output (t2175_5).

    The one reading of the `open` wire lines for the TUIs that run it — the
    monitor and minimonitor `S` key and the TUI switcher's `S` quick-jump.
    """
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    warn = ", ".join(ln.partition(":")[2] for ln in lines
                     if ln.startswith("SITREP_WARN:"))
    for ln in lines:
        head, _, rest = ln.partition(":")
        if head in _OPEN_SUCCESS:
            msg = _OPEN_SUCCESS[head]
            if warn:
                return f"{msg} ({warn})", "warning"
            return msg, "information"
        if head == "SITREP_FOCUS_FAILED":
            return ("The sitrep window exists but switching to it failed",
                    "warning")
        if head in ("SITREP_REFUSED", "ERROR"):
            return f"Sitrep not opened: {rest}", "error"
    return f"Sitrep not opened (exit {rc})", "error"


def _canonical(path: str) -> str:
    root, _ = sh.canonical_root(os.path.abspath(path))
    return root


def cmd_root(args) -> int:
    try:
        root = _canonical(args.root)
    except sh.HarvestFailure as e:
        print(f"ROOT_FAILED:{e}")
        return 1
    print(f"ROOT:{root}")
    cwd = os.path.realpath(os.getcwd())
    print("CWD_OK" if cwd == root else f"CWD_MISMATCH:{cwd}")
    return 0


def _capture_kind(store_dir: str, pointer: str) -> str:
    path = os.path.join(store_dir, pointer.split("#", 1)[0])
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            first = f.readline()
    except OSError:
        return "passage"
    kind = sh.capture_file_kind(first)
    if kind in ("case", "analysis", "review") and _trusted_text(store_dir, pointer) is None:
        # Harvested text that merely starts with a case-record header: it has
        # no trusted cases/ twin, so it is plain passage text (t2175_6).
        return "passage"
    return kind


def _trusted_text(store_dir: str, pointer: str):
    """The TRUSTED cases/ record a sources/ pointer is a copy of, or None."""
    name = os.path.basename(pointer.split("#", 1)[0])
    return st.read_case_record(store_dir, name[:-4] if name.endswith(".txt") else "")


_KIND_LABEL = {"banner": "BANNER", "key": "KEY", "passage": "CAPTURE",
               "case": "CASE", "analysis": "ANALYSIS", "review": "REVIEW"}


def _review_case(store_dir: str, pointers: list) -> str:
    """``<case hex>|<reason codes>`` when one of ``pointers`` is a review case's
    TRUSTED analysis (t2175_6; its cases/ twin exists), else ``""``. Facts
    only: the codes are the analysis's own reason lines."""
    import sitrep_corpus as sc  # noqa: E402 - lazy: sitrep_corpus imports this module
    for ptr in pointers:
        text = _trusted_text(store_dir, ptr)
        if text is None:
            continue
        head, first, multi = sc.parse_kv(text)
        if head == sh.CASE_ANALYSIS_HEADER and first.get("case"):
            codes = dict.fromkeys(v.split("|", 1)[0] for v in multi.get("reason", []))
            return f"{first['case']}|{','.join(codes) or '-'}"
    return ""


#: Public names (t2211_1): the sitrep TUI labels the same capture pointers and
#: finds the same review case, so it calls these rather than re-deriving trust.
capture_kind = _capture_kind
review_case = _review_case
KIND_LABEL = _KIND_LABEL


def is_triage(item) -> bool:
    return item.kind == "question" and item.derived == "script"


def _ctx(store, num):
    return store.contexts.get(num) or st.ContextEntry()


def watches_of(store, handle: str) -> list:
    """Ids of the kind=watch items whose own context carries ``trail: handle``."""
    return [n for n in sorted(store.items)
            if store.items[n].kind == "watch" and ("trail", handle) in _ctx(store, n).sources]


def triage_block(store, store_dir: str, num: int) -> tuple:
    """``(lines, unwatched handles)`` for one triage item (see the module doc)."""
    item = store.items[num]
    ctx = _ctx(store, num)
    out = []
    if ctx.origin:
        out.append("ORIGIN:" + " ".join(f"{k}={v}" for k, v in ctx.origin))
    captures = [p for t, p in ctx.sources if t == "capture"]
    if captures:
        out.append(f"PASSAGE:{captures[0]}")
    for ptr in captures[1:]:
        out.append(f"{_KIND_LABEL[_capture_kind(store_dir, ptr)]}:{ptr}")
    review = _review_case(store_dir, captures[1:])
    if review:
        out.append(f"REVIEW_CASE:{review}")
    for kind in ("task", "plan", "commit"):
        out.extend(f"{kind.upper()}:{p}" for t, p in ctx.sources if t == kind)
    unwatched = []
    for handle in dict.fromkeys(p for t, p in ctx.sources if t == "trail"):
        watches = [n for n in watches_of(store, handle) if n != num]
        if watches:
            out.extend(f"TRAIL_WATCHED:{handle}|c{n}|{store.items[n].state}"
                       for n in watches)
        else:
            out.append(f"TRAIL_UNWATCHED:{handle}")
            unwatched.append(handle)
    for n in sorted(store.items):
        other = store.items[n]
        if n != num and other.derived == "agent" and num in _ctx(store, n).related:
            out.append(f"DERIVED:c{n}|{other.kind}|{other.state}|{other.title}")
    out.append(f"TRIAGE:c{num}|{item.state}|{item.rev}")
    return out, unwatched


def cmd_triage(args) -> int:
    if (args.id is None) == (not args.open):
        print("Error: give one item id, or --open", file=sys.stderr)
        return 2
    num = None
    if args.id is not None:
        try:
            num = st.parse_id(args.id)
        except st.RequestError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 2
    try:
        root = _canonical(args.root)
    except sh.HarvestFailure as e:
        print(f"ROOT_FAILED:{e}")
        return 1
    store_dir = os.path.join(root, sh.STORE_NAME)
    try:
        store = st.load_todo_for_read(store_dir)
    except (st.FormatError, OSError) as e:
        print(f"Error: store unusable: {e}", file=sys.stderr)
        return 4
    if num is not None:
        item = store.items.get(num)
        if item is None:
            print(f"NOT_FOUND:c{num}")
            return 2
        if not is_triage(item):
            print(f"NOT_TRIAGE:c{num}")
            return 2
        print("\n".join(triage_block(store, store_dir, num)[0]))
        return 0
    open_ids = [n for n in sorted(store.items)
                if is_triage(store.items[n]) and store.items[n].state == "open"]
    if not open_ids:
        print("NO_TRIAGE")
        return 0
    batch: dict = {}
    for n in open_ids:
        lines, unwatched = triage_block(store, store_dir, n)
        print("\n".join(lines))
        for handle in unwatched:
            batch.setdefault(handle, []).append(n)
    for handle, ids in batch.items():
        print(f"BATCH_TRAIL_UNWATCHED:{handle}|" + ",".join(f"c{n}" for n in ids))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="ait sitrep", allow_abbrev=False)
    sub = ap.add_subparsers(dest="verb", required=True)
    p_root = sub.add_parser("root", allow_abbrev=False)
    p_root.add_argument("--root", default=".", type=root_arg)
    p_tri = sub.add_parser("triage", allow_abbrev=False)
    p_tri.add_argument("id", nargs="?")
    p_tri.add_argument("--open", action="store_true")
    p_tri.add_argument("--root", default=".", type=root_arg)
    args = ap.parse_args(argv)
    return {"root": cmd_root, "triage": cmd_triage}[args.verb](args)


if __name__ == "__main__":
    sys.exit(main())
