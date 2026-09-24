#!/usr/bin/env python3
"""Reopen coordinator for frozen agents whose stand-in viewer is gone (t1847).

After a machine shutdown the tmux server dies and every frozen stand-in viewer
with it. The records survive as `frozen` with a pane that no longer exists, and
`reconcile` deliberately leaves them alone (`_reconcile_frozen` →
``KEEP:<id>|pane_gone``). This module brings their viewers back — as viewers:
the agent stays frozen — so `ait ide` can offer that instead of a fresh session
with no sign of them.

Two verbs, reached through `aitask_frozen.sh`:

* ``gone --root <p>``              — read-only listing of this project's records
  whose viewer is not tracked;
* ``reopen <id> | --root <p>``     — recreate (or adopt) their viewers; both take
  ``--session <name>`` to pin the tmux session, exactly as `ait ide` resolved it.

CLASSIFICATION. One ``list-panes -a`` pass collects every live pane that
*claims* a record: ``@aitask_frozen == id``, OR ``@aitask_standin_ready == id``
(the viewer self-stamps it from ``$TMUX_PANE`` on mount), OR a window name of the
attempt form :data:`ATTEMPT_RE`. Then per `frozen` record:

* a claim on the record's own ``pane_id`` carrying the stamp → **tracked**
  (nothing to do; a dead one is reconcile's to respawn);
* any other claim → **stranded**: an untracked survivor of an earlier failed or
  uncertain reopen. It is **adopted**, never duplicated;
* no claim at all → **gone**: a fresh viewer window is created.

The classification that DECIDES is always the one taken again after
``lease-take``: two runs can both observe `gone`, and the second may get its
lease only after the first has committed and released. A pre-lease reading is
a cheap early exit, never the basis for creating or adopting anything.

THE IDENTITY PROTOCOL of a fresh window. The pane is claimed at every instant
from creation to commit, which is what makes every failure recoverable:

1. it is created detached under the ATTEMPT NAME ``aitask-reopen-<id>-<nonce>``.
   tmux sets the name atomically with the window, so there is no moment at which
   the window exists unclaimed. The record id makes it discoverable by any later
   run with no stored state; the lease nonce makes it unique per attempt, so one
   attempt's guards never match another attempt's survivor. The name is hex and
   dashes only, so it is safe inside a ``#{==:…}`` format — the recorded window
   name is not (a `,` or `}` would break the comparison);
2. the first write is a NAME-GUARDED stamp (one ``if-shell -F`` dispatch), then
   verified by a re-read;
3. the rename to the recorded name is STAMP-GUARDED and verified, and it happens
   BEFORE the store commit — so a failure after the commit is impossible except
   for the best-effort companion, and a store failure leaves a survivor that
   already carries its final name;
4. ``standin-respawned`` records the pane (``frozen → frozen``, lease cleared).

Cleanup before the stamp is verified is a name-guarded kill; after it,
`frozen_ops.kill_if_stamped(..., window=True)`. Both are check-and-kill in ONE
dispatch plus an after-read, so a tmux restart that recycles the ``%N`` cannot
hand the kill a stranger's pane. **The code never unstamps before killing**: a
kill that is not verified leaves a stamped survivor, which the next run adopts —
an unstamped one would be an orphan nobody can identify.

UNCERTAIN LAUNCH. A non-zero ``new-window`` rc is not read as "nothing was
created": the gateway's ``-1`` also covers a timeout after which the server may
have completed the command. The attempt name is looked up first.

SESSION TARGETING. With ``--session S`` every launch and every adoption lands in
S, and only when discovery attributes S to the record's root
(`agent_restore._resolve_target_session`); otherwise it fails closed with
``session_not_for_root:<S>`` — two sessions can share a project, and a viewer in
the one the user is not looking at is the failure this exists to prevent.

Seam rule, as for the sibling engines: shared helpers are called THROUGH the
module (``frozen_ops.store(...)``, ``frozen_ops.run(...)``) and never
import-aliased, because the tests swap ``agent_frozen_ops.store`` / ``._TMUX``
in place. Every store write goes through the shell wrapper; every tmux call
through the gateway. This module may import `agent_restore` (both are
coordinators); `agent_freeze` must still import neither.

Test seam, honoured only under ``AITASKS_TEST_MODE=1``:
``AITASKS_REOPEN_FAIL_AT`` is a COMMA-SEPARATED stage set (unlike the siblings'
single-stage seams, a live test needs pairs such as ``store,cleanup``):

* ``launch`` — skip the ``new-window`` dispatch and report rc 1;
* ``launch_uncertain`` — dispatch it, then report rc -1 with no output;
* ``identify`` — discard the ``-P`` output (forces the name lookup);
* ``lookup`` — the name lookup reports tmux unreachable;
* ``stamp`` / ``rename`` / ``store`` — that step does not take effect;
* ``cleanup`` — the guarded kill is skipped and reported ``present``;
* ``move`` — the cross-session move of an adoption does not take effect.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

_LIB_DIR = Path(__file__).resolve().parent
_SCRIPTS_DIR = _LIB_DIR.parent
for _p in (str(_SCRIPTS_DIR), str(_LIB_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import agent_frozen_ops as frozen_ops  # noqa: E402
import agent_restore  # noqa: E402
import agent_sessions  # noqa: E402
# Re-exported names only — never swapped, so an import alias is safe.
from agent_frozen_ops import EXIT_LEASE_HELD, TMUX_UNREACHABLE  # noqa: E402
from agent_launch_utils import (  # noqa: E402
    tmux_window_target,
    unique_window_name,
)
from monitor.monitor_core import FROZEN_OPTION, STANDIN_READY_OPTION  # noqa: E402

FAIL_ENV = "AITASKS_REOPEN_FAIL_AT"

#: The attempt name of a fresh viewer window: record id, then the lease nonce.
ATTEMPT_RE = re.compile(r"^aitask-reopen-([0-9a-f]{8})-([0-9a-f]{8})$")

#: Fallback window name for a record that recorded none.
DEFAULT_WINDOW = "agent-frozen"

_CLAIM_FORMAT = "\t".join([
    "#{pane_id}", "#{pane_pid}", "#{pane_dead}", "#{session_name}",
    "#{window_name}", f"#{{{FROZEN_OPTION}}}", f"#{{{STANDIN_READY_OPTION}}}",
])
_CLAIM_ARITY = 7

_FACTS_FORMAT = "\t".join([
    "#{pane_id}", "#{pane_pid}", "#{session_name}", "#{window_name}",
    "#{window_id}", f"#{{{FROZEN_OPTION}}}",
])
_FACTS_KEYS = ("pane_id", "pane_pid", "session", "window", "window_id", "frozen")


def attempt_name(record_id: str, nonce: str) -> str:
    return f"aitask-reopen-{record_id}-{nonce[:8]}"


def _seam(stage: str) -> bool:
    if not frozen_ops.test_mode():
        return False
    stages = {s.strip() for s in os.environ.get(FAIL_ENV, "").split(",")}
    return stage in stages


# --- observation -------------------------------------------------------------


@dataclass
class Claim:
    """A pane that claims a record, and how."""

    pane_id: str
    pane_pid: int
    dead: bool
    session: str
    window: str
    frozen: str
    ready: str
    via: str          # "stamp" | "ready" | "name"


def _claimed_panes() -> dict[str, list[Claim]] | None:
    """Every pane claiming some record, keyed by record id; None if unreachable.

    Fails CLOSED on any non-zero rc: a listing that could not be read is not
    evidence that no viewer exists, and reading it that way would create a
    duplicate of one that does.
    """
    rc, out = frozen_ops.run(["list-panes", "-a", "-F", _CLAIM_FORMAT])
    if rc != 0:
        return None
    claims: dict[str, list[Claim]] = {}
    # NOT `out.strip().splitlines()`: the trailing fields are options that are
    # empty on most panes, and a whole-buffer strip eats the last row's tabs.
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) != _CLAIM_ARITY:
            continue
        pane_id, pid, dead, session, window, frozen, ready = (
            p.strip() for p in parts)
        try:
            pane_pid = int(pid)
        except ValueError:
            pane_pid = 0
        match = ATTEMPT_RE.match(window)
        keyed: list[tuple[str, str]] = []
        if agent_sessions.valid_id(frozen):
            keyed.append((frozen, "stamp"))
        if agent_sessions.valid_id(ready) and ready != frozen:
            keyed.append((ready, "ready"))
        if match and match.group(1) not in (frozen, ready):
            keyed.append((match.group(1), "name"))
        for record_id, via in keyed:
            claims.setdefault(record_id, []).append(Claim(
                pane_id, pane_pid, dead == "1", session, window, frozen, ready,
                via))
    return claims


_VIA_RANK = {"stamp": 0, "ready": 1, "name": 2}


def classify_record(rec: dict, claims: list[Claim]) -> tuple[str, Claim | None]:
    """``("tracked"|"stranded"|"gone", claim)`` for one `frozen` record."""
    record_id = rec.get("id", "")
    own_pane = rec.get("pane_id", "")
    for claim in claims:
        if own_pane and claim.pane_id == own_pane and claim.frozen == record_id:
            return "tracked", claim
    live = [c for c in claims if not c.dead]
    if live:
        live.sort(key=lambda c: _VIA_RANK[c.via])
        return "stranded", live[0]
    return "gone", None


def _frozen_records(root: str) -> list[dict] | None:
    """Full records of ``root``'s `frozen` records; None if the store failed."""
    rc, out = frozen_ops.store("list", "--state", "frozen", "--root", root)
    if rc != 0:
        return None
    records = []
    for line in out.splitlines():
        if not line.startswith("SESSION:"):
            continue
        record_id = line[len("SESSION:"):].split("|", 1)[0].strip()
        if not agent_sessions.valid_id(record_id):
            continue
        rec = frozen_ops.store_show(record_id)
        if rec.get("state") == agent_sessions.STATE_FROZEN:
            records.append(rec)
    return records


def classify(root: str) -> tuple[list[tuple[dict, str, Claim | None]], list[str]] | None:
    """``(items, errors)`` for ``root``: every gone / stranded record.

    None when the store could not be listed. When tmux cannot be listed, no
    record is classified and each one yields a ``GONE_ERROR`` line instead.
    """
    records = _frozen_records(root)
    if records is None:
        return None
    if not records:
        return [], []
    claims = _claimed_panes()
    if claims is None:
        return [], [f"GONE_ERROR:{r['id']}|tmux_unreachable" for r in records]
    items = []
    for rec in records:
        kind, claim = classify_record(rec, claims.get(rec["id"], []))
        if kind != "tracked":
            items.append((rec, kind, claim))
    return items, []


def _field(value: str) -> str:
    """A wire field: no `|`, no newline."""
    return (value or "").replace("|", "/").replace("\n", " ")


def gone_line(rec: dict, kind: str) -> str:
    resume = agent_restore.resume_blocker(rec) or "ok"
    repick = agent_restore.repick_blocker(rec) or "ok"
    return "GONE:" + "|".join([
        rec["id"], kind, _field(rec.get("window", "")),
        _field(rec.get("task_id", "")), _field(rec.get("frozen_at", "")),
        resume, repick,
    ])


# --- tmux primitives ---------------------------------------------------------


def _session_scope(session: str) -> str:
    """``=<session>:`` — a session target that cannot resolve as a window.

    A bare ``=<session>`` is looked up as a WINDOW first: from a client whose
    current session has a window of that name (`ait ide` runs from inside the
    session it opens), ``list-panes -s -t =B`` lists the CURRENT session's
    panes instead of B's (measured on tmux 3.7c). The trailing colon makes the
    session part explicit.
    """
    return tmux_window_target(session, "")



def _facts(pane_id: str) -> dict[str, str] | None:
    """The pane's facts; ``{}`` when it is gone; None when tmux is unreachable."""
    rc, out = frozen_ops.run(["display-message", "-p", "-t", pane_id, _FACTS_FORMAT])
    if rc == TMUX_UNREACHABLE:
        return None
    if rc != 0:
        return {}
    parts = (out.splitlines() or [""])[0].split("\t")
    if len(parts) != len(_FACTS_KEYS) or not parts[0].strip():
        return {}
    return {k: v.strip() for k, v in zip(_FACTS_KEYS, parts)}


def _find_by_window_name(session: str, name: str) -> tuple[str, str, int]:
    """``(verdict, pane_id, pane_pid)``: ``found`` / ``none`` / ``unknown``.

    Filtered in Python rather than by a ``session:window`` target, because a
    window target cannot address a name containing `.` or `:`. More than one
    pane under a per-attempt name is not a state this module produces; it is
    reported ``unknown`` rather than guessed.
    """
    if _seam("lookup"):
        return "unknown", "", 0
    rc, out = frozen_ops.run([
        "list-panes", "-s", "-t", _session_scope(session),
        "-F", "#{window_name}\t#{pane_id}\t#{pane_pid}"])
    if rc == TMUX_UNREACHABLE:
        return "unknown", "", 0
    if rc != 0:
        return "none", "", 0
    hits = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[0] == name:
            hits.append(parts)
    if not hits:
        return "none", "", 0
    if len(hits) > 1:
        return "unknown", "", 0
    try:
        return "found", hits[0][1].strip(), int(hits[0][2].strip())
    except ValueError:
        return "unknown", "", 0


def _kill_if_named(pane_id: str, name: str) -> tuple[str, str]:
    """`kill-window` on ``pane_id``'s window only if it is still named ``name``.

    The same check-and-kill-in-one-dispatch shape and verdict contract as
    `frozen_ops.kill_if_stamped`, for the window of an attempt whose stamp was
    never verified. ``name`` is a per-attempt name, so a recycled ``%N`` in a
    restarted server cannot match it.
    """
    if _seam("cleanup"):
        return "present", "seam"
    before = _facts(pane_id)
    if before is None:
        return "unknown", "tmux unreachable"
    if not before:
        return "gone", "pane-gone"
    frozen_ops.run(["if-shell", "-F", "-t", pane_id,
                    f"#{{==:#{{window_name}},{name}}}",
                    f"kill-window -t {pane_id}"])
    after = _facts(pane_id)
    if after is None:
        return "unknown", "tmux unreachable"
    if not after:
        return "gone", ""
    return "present", "kill-failed" if after["window"] == name else "name-mismatch"


def _kill_if_stamped(pane_id: str, record_id: str) -> tuple[str, str]:
    if _seam("cleanup"):
        return "present", "seam"
    return frozen_ops.kill_if_stamped(pane_id, option=FROZEN_OPTION,
                                      expect=record_id, window=True)


def _final_name(session: str, pane_id: str, base: str) -> str:
    """The recorded name, suffixed only against OTHER windows of ``session``.

    The window being named is excluded from the collision set, so a window that
    already carries its final name keeps it rather than being pushed to `-2` by
    its own name, and the result is stable across reruns.
    """
    facts = _facts(pane_id) or {}
    own = facts.get("window_id", "")
    rc, out = frozen_ops.run(["list-windows", "-t", _session_scope(session),
                              "-F", "#{window_id}\t#{window_name}"])
    if rc != 0:
        return base
    others = set()
    for line in out.splitlines():
        wid, _, name = line.partition("\t")
        if wid.strip() != own:
            others.add(name)
    return unique_window_name(others, base)


def _rename(pane_id: str, record_id: str, final: str) -> bool:
    """Stamp-guarded rename of ``pane_id``'s window, verified by a re-read."""
    facts = _facts(pane_id)
    if not facts or facts.get("frozen") != record_id:
        return False
    if facts.get("window") == final:
        return True                 # already right: no rename issued
    if not _seam("rename"):
        frozen_ops.run(["if-shell", "-F", "-t", pane_id,
                        f"#{{==:#{{{FROZEN_OPTION}}},{record_id}}}",
                        f"rename-window -t {pane_id} {frozen_ops.tmux_quote(final)}"])
    after = _facts(pane_id)
    return bool(after) and after.get("window") == final


# --- the transaction ---------------------------------------------------------


def _release(record_id: str, nonce: str) -> None:
    frozen_ops.store("lease-release", record_id, "--nonce", nonce)


def _cleanup_suffix(verdict: str, reason: str, pane_id: str) -> str:
    if verdict == "gone":
        return ""
    return f"|cleanup:{verdict}:{reason}|pane:{pane_id}"


def _commit(record_id: str, nonce: str, pane_id: str) -> tuple[int, str]:
    if _seam("store"):
        return 1, "seam"
    facts = _facts(pane_id) or {}
    try:
        pane_pid = int(facts.get("pane_pid", "0"))
    except ValueError:
        pane_pid = 0
    if not pane_pid:
        return 1, "pane vanished before commit"
    return frozen_ops.store("standin-respawned", record_id, "--nonce", nonce,
                            "--pane", pane_id, "--pane-pid", str(pane_pid))


def _fresh(rec: dict, nonce: str, session: str) -> str:
    record_id = rec["id"]
    root = rec.get("root", "")
    name = attempt_name(record_id, nonce)

    def fail(detail: str) -> str:
        _release(record_id, nonce)
        return f"REOPEN_FAILED:{record_id}|{detail}"

    try:
        command = agent_sessions.standin_command(record_id)
    except ValueError as exc:
        return fail(f"launch:{exc}")

    # --- 1. create, under the attempt name ---------------------------------
    if _seam("launch"):
        rc, out = 1, ""
    else:
        argv = ["new-window", "-d", "-P", "-F", "#{pane_id}\t#{pane_pid}",
                "-t", tmux_window_target(session, ""), "-n", name]
        if root:
            argv += ["-c", root]
        rc, out = frozen_ops.run(argv + [command])
        if _seam("launch_uncertain"):
            rc, out = TMUX_UNREACHABLE, ""
    pane_id = ""
    if rc == 0 and not _seam("identify"):
        pane_id = (out.splitlines() or [""])[0].split("\t")[0].strip()

    # --- 2. identify: an unparsed or uncertain result is looked up by name -
    if not pane_id:
        verdict, pane_id, _pid = _find_by_window_name(session, name)
        if verdict == "none":
            # tmux answered and holds no window of this attempt.
            return fail(f"launch:rc={rc}")
        if verdict != "found":
            # Could not establish whether a window exists. If one does, it is
            # claimed by its attempt name from its first instant, so the next
            # run adopts it rather than duplicating it.
            return fail("launch:uncertain")

    # --- 3. name-guarded stamp, verified -----------------------------------
    if not _seam("stamp"):
        frozen_ops.run(["if-shell", "-F", "-t", pane_id,
                        f"#{{==:#{{window_name}},{name}}}",
                        f"set-option -p -t {pane_id} {FROZEN_OPTION} {record_id}"])
    facts = _facts(pane_id)
    if not facts or facts.get("frozen") != record_id:
        verdict, reason = _kill_if_named(pane_id, name)
        return fail("stamp" + _cleanup_suffix(verdict, reason, pane_id))

    # --- 4. rename to the recorded name BEFORE the commit ------------------
    final = _final_name(session, pane_id, rec.get("window") or DEFAULT_WINDOW)
    if not _rename(pane_id, record_id, final):
        verdict, reason = _kill_if_stamped(pane_id, record_id)
        return fail("rename" + _cleanup_suffix(verdict, reason, pane_id))

    # --- 5. commit ----------------------------------------------------------
    rc, out = _commit(record_id, nonce, pane_id)
    if rc != 0:
        # Never unstamp first: a kill that does not take must leave a stamped
        # survivor the next run can adopt.
        verdict, reason = _kill_if_stamped(pane_id, record_id)
        return fail(f"store:{_field(out.strip())}"
                    + _cleanup_suffix(verdict, reason, pane_id))

    agent_restore._spawn_companion(session, final, pane_id, root)
    return f"REOPENED:{record_id}|fresh|{session}:{final}|{pane_id}"


def _claim_condition(claim: Claim, record_id: str) -> str:
    """The ``if-shell -F`` condition that re-checks the claim that was observed."""
    if claim.via == "stamp":
        return f"#{{==:#{{{FROZEN_OPTION}}},{record_id}}}"
    if claim.via == "ready":
        return f"#{{==:#{{{STANDIN_READY_OPTION}}},{record_id}}}"
    return f"#{{==:#{{window_name}},{claim.window}}}"


def _adopt(rec: dict, nonce: str, claim: Claim, session: str | None) -> str:
    """Record a stranded viewer instead of creating a second one.

    No kill on any failure: the pane pre-existed this run, it may be the only
    viewer the user has, and the record not being committed keeps it stranded —
    so the next run retries exactly this.
    """
    record_id = rec["id"]
    pane_id = claim.pane_id

    def fail(detail: str) -> str:
        _release(record_id, nonce)
        return f"REOPEN_FAILED:{record_id}|adopt:{detail}|pane:{pane_id}"

    # --- 1. the stamp, when the claim is only the ready mark or the name ---
    if claim.frozen != record_id:
        if not _seam("stamp"):
            frozen_ops.run(["if-shell", "-F", "-t", pane_id,
                            _claim_condition(claim, record_id),
                            f"set-option -p -t {pane_id} {FROZEN_OPTION} {record_id}"])
        facts = _facts(pane_id)
        if not facts or facts.get("frozen") != record_id:
            return fail("stamp")

    # --- 2. into the selected session --------------------------------------
    facts = _facts(pane_id)
    if not facts:
        return fail("gone")
    current = facts.get("session", "")
    if session is not None and current != session:
        if not _seam("move"):
            frozen_ops.run([
                "if-shell", "-F", "-t", pane_id,
                f"#{{==:#{{{FROZEN_OPTION}}},{record_id}}}",
                f"move-window -s {pane_id} -t "
                f"{frozen_ops.tmux_quote(tmux_window_target(session, ''))}"])
        facts = _facts(pane_id)
        if not facts or facts.get("session") != session:
            return fail("move")
        current = session

    # --- 3. the recorded name, then the commit -----------------------------
    final = _final_name(current, pane_id, rec.get("window") or DEFAULT_WINDOW)
    if not _rename(pane_id, record_id, final):
        return fail("rename")
    rc, out = _commit(record_id, nonce, pane_id)
    if rc != 0:
        return fail(f"store:{_field(out.strip())}")

    agent_restore._spawn_companion(current, final, pane_id, rec.get("root", ""))
    return f"REOPENED:{record_id}|adopted|{current}:{final}|{pane_id}"


def reopen_one(record_id: str, *, session: str | None = None) -> str:
    """Bring back one record's viewer. Returns the wire line."""
    rec = frozen_ops.store_show(record_id)
    if not rec:
        return f"REOPEN_FAILED:{record_id}|no_record"
    state = rec.get("state", "")
    if state != agent_sessions.STATE_FROZEN:
        return f"REOPEN_SKIPPED:{record_id}|state:{state}"
    rec.setdefault("id", record_id)

    claims = _claimed_panes()
    if claims is None:
        return f"REOPEN_FAILED:{record_id}|preflight:tmux unreachable"
    kind, claim = classify_record(rec, claims.get(record_id, []))
    if kind == "tracked":
        return f"REOPEN_SKIPPED:{record_id}|pane_present"

    rc, out = frozen_ops.store("lease-take", record_id,
                               "--owner-pid", str(os.getpid()))
    if rc == EXIT_LEASE_HELD:
        return f"REOPEN_SKIPPED:{record_id}|lease_held"
    if rc != 0:
        return f"REOPEN_FAILED:{record_id}|lease:{_field(out.strip())}"
    nonce = frozen_ops.nonce_from(out.splitlines()[-1])

    # RE-CLASSIFY UNDER THE LEASE. The observation above is only a cheap
    # pre-check: two runs can both see `gone`, and once the first commits and
    # releases, the second takes a fresh lease. Acting on its stale reading
    # would create a second viewer and repoint the record away from the first.
    # Everything this transaction does is decided from what is true now.
    rec = frozen_ops.store_show(record_id)
    if not rec:
        # `store_show` answers {} for an unreadable store as well as for a
        # dropped record. Neither may pass as a harmless skip: the viewer was
        # not recovered, and the caller has to hear about it.
        _release(record_id, nonce)
        return f"REOPEN_FAILED:{record_id}|reread:record unreadable"
    state = rec.get("state", "")
    if state != agent_sessions.STATE_FROZEN:
        _release(record_id, nonce)
        return f"REOPEN_SKIPPED:{record_id}|state:{state}"
    rec.setdefault("id", record_id)
    claims = _claimed_panes()
    if claims is None:
        _release(record_id, nonce)
        return f"REOPEN_FAILED:{record_id}|preflight:tmux unreachable"
    kind, claim = classify_record(rec, claims.get(record_id, []))
    if kind == "tracked":
        _release(record_id, nonce)
        return f"REOPEN_SKIPPED:{record_id}|pane_present"

    if kind == "stranded" and claim is not None:
        if session is not None:
            target, error = agent_restore._resolve_target_session(
                rec.get("root", ""), session)
            if target is None:
                _release(record_id, nonce)
                return f"REOPEN_FAILED:{record_id}|{error}"
        return _adopt(rec, nonce, claim, session)

    target, error = agent_restore._resolve_target_session(rec.get("root", ""), session)
    if target is None:
        _release(record_id, nonce)
        return f"REOPEN_FAILED:{record_id}|{error}"
    return _fresh(rec, nonce, target.session)


def reopen_all(root: str, *, session: str | None = None) -> list[str]:
    """Every gone / stranded record of ``root``, sequentially.

    One record's failure never stops the batch. The trailing
    ``REOPEN_ALL:<ok>/<n>`` counts ``REOPENED`` lines.
    """
    result = classify(root)
    if result is None:
        return ["REOPEN_FAILED:*|store unreadable", "REOPEN_ALL:0/0"]
    items, errors = result
    lines = [e.replace("GONE_ERROR:", "REOPEN_FAILED:", 1) for e in errors]
    for rec, _kind, _claim in items:
        try:
            lines.append(reopen_one(rec["id"], session=session))
        except Exception as exc:        # never abandon the rest of the batch
            lines.append(f"REOPEN_FAILED:{rec['id']}|{_field(str(exc))}")
    ok = sum(1 for line in lines if line.startswith("REOPENED:"))
    total = len(items) + len(errors)
    lines.append(f"REOPEN_ALL:{ok}/{total}")
    return lines


# --- CLI ---------------------------------------------------------------------

_USAGE = ("Usage: aitask_frozen.sh gone --root <path>\n"
          "       aitask_frozen.sh reopen <id> [--session NAME]\n"
          "       aitask_frozen.sh reopen --root <path> [--session NAME]")


def _take_root(args: list[str]) -> tuple[list[str], str | None, str]:
    if "--root" not in args:
        return args, None, ""
    i = args.index("--root")
    if i + 1 >= len(args) or not args[i + 1]:
        return args, None, "--root requires a path"
    root = args[i + 1]
    return args[:i] + args[i + 2:], os.path.realpath(root), ""


def main(argv: list[str]) -> int:
    args = list(argv)
    if not args or args[0] not in ("gone", "reopen"):
        print(_USAGE, file=sys.stderr)
        return 2
    verb, args = args[0], args[1:]
    # `--session` leaves first: its value is verbatim and may start with `-`.
    args, session, err = agent_restore.take_session_arg(args)
    if not err:
        args, root, err = _take_root(args)
    if err:
        print(f"ERROR:{err}", file=sys.stderr)
        return 2

    if verb == "gone":
        if root is None or args or session is not None:
            print(_USAGE, file=sys.stderr)
            return 2
        result = classify(root)
        if result is None:
            print("GONE_ERROR:*|store unreadable")
            return 1
        items, errors = result
        for rec, kind, _claim in items:
            print(gone_line(rec, kind))
        for line in errors:
            print(line)
        print(f"GONE_COUNT:{len(items)}")
        return 0

    if root is not None:
        if args:
            print(_USAGE, file=sys.stderr)
            return 2
        lines = reopen_all(root, session=session)
        for line in lines:
            print(line)
        return 0 if all(not ln.startswith("REOPEN_FAILED:") for ln in lines) else 1

    if len(args) != 1 or not agent_sessions.valid_id(args[0]):
        print(_USAGE, file=sys.stderr)
        return 2
    line = reopen_one(args[0], session=session)
    print(line)
    return 1 if line.startswith("REOPEN_FAILED:") else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
