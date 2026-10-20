#!/usr/bin/env python3
"""Reopen coordinator for frozen agents whose stand-in viewer is gone (t1847).

After a machine shutdown the tmux server dies and every frozen stand-in viewer
with it. The records survive as `frozen` with a pane that no longer exists, and
`reconcile` deliberately leaves them alone (`_reconcile_frozen` →
``KEEP:<id>|pane_gone``). This module brings their viewers back — as viewers:
the agent stays frozen — so `ait ide` can offer that instead of a fresh session
with no sign of them.

Three verbs, reached through `aitask_frozen.sh`:

* ``gone --root <p> | --all-roots`` — read-only listing of the records whose
  viewer is not tracked, for one project or for every project in the store
  (grouped by root, each group headed by the root's state — see
  :func:`root_states`; `ait ide` offers them all, t2039);
* ``reopen <id> | --root <p>``     — recreate (or adopt) their viewers; takes
  ``--session <name>`` to pin the tmux session, exactly as `ait ide` resolved it;
* ``companions --root <p> | --all-roots`` — give every TRACKED viewer the
  minimonitor companion its window should have (t2039). Idempotent:
  `maybe_spawn_minimonitor` refuses a live or booting companion under its
  per-server lock. Never creates, moves or adopts a window.

CLASSIFICATION. One ``list-panes -a`` pass collects every live pane that
*claims* a record: ``@aitask_frozen == id``, OR ``@aitask_standin_ready == id``
(the viewer self-stamps it from ``$TMUX_PANE`` on mount), OR a window name of the
attempt form :data:`ATTEMPT_RE`, OR a gone-pane RESTORE attempt's name or mark
(`agent_frozen_ops.restore_attempt_record`). Then per `frozen` record:

* a live restore-attempt claim without ``@aitask_standin_ready == id`` →
  **survivor** (t1875), decided FIRST, the record's own ``pane_id`` included:
  it is an agent an earlier restore left running, not a viewer, so it is never
  adopted and never duplicated — `reopen` refuses it and names the pane;
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
    _parse_registry_records_strict,
    tmux_session_scope_target,
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
    f"#{{{frozen_ops.RESTORE_ATTEMPT_OPTION}}}",
])
_CLAIM_ARITY = 8

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
    via: str          # "stamp" | "ready" | "name" | "restore"
    mark: str = ""


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
        pane_id, pid, dead, session, window, frozen, ready, mark = (
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
        # A restore attempt (t1875) claims its record IN ADDITION to any stamp
        # claim: the stamp alone would read the agent as a viewer to adopt.
        restore_of = frozen_ops.restore_attempt_record(window, mark)
        if restore_of:
            keyed.append((restore_of, "restore"))
        for record_id, via in keyed:
            claims.setdefault(record_id, []).append(Claim(
                pane_id, pane_pid, dead == "1", session, window, frozen, ready,
                via, mark))
    return claims


_VIA_RANK = {"stamp": 0, "ready": 1, "name": 2, "restore": 3}


def classify_record(rec: dict, claims: list[Claim]) -> tuple[str, Claim | None]:
    """``("survivor"|"tracked"|"stranded"|"gone", claim)`` for one `frozen` record.

    ``survivor`` is decided FIRST, ahead of ``tracked`` (t1875): a live pane
    claiming the record through a restore attempt is an AGENT no record
    tracks, unless its own ready mark proves a stand-in of this record is
    mounted there. The record's `pane_id` exempts nothing — after a server
    restart a survivor can hold exactly that `%N`, stamped like the viewer.
    """
    record_id = rec.get("id", "")
    own_pane = rec.get("pane_id", "")
    for claim in claims:
        if claim.via == "restore" and frozen_ops.is_restore_survivor(
                record_id, claim.window, claim.mark, claim.ready, claim.dead):
            return "survivor", claim
    for claim in claims:
        if own_pane and claim.pane_id == own_pane and claim.frozen == record_id:
            return "tracked", claim
    # A restore claim that is not a survivor is a settled viewer's stale mark;
    # its stamp / ready claim speaks for it.
    live = [c for c in claims if not c.dead and c.via != "restore"]
    if live:
        live.sort(key=lambda c: _VIA_RANK[c.via])
        return "stranded", live[0]
    return "gone", None


def _frozen_records(root: str | None) -> list[dict] | None:
    """Full `frozen` records of ``root`` (every root for None); None if the store failed."""
    # ONE store read for the whole listing (t2041): `ait ide` runs this over
    # every project twice per start, and a `show` per record was a subprocess
    # and a full store reload each. `reopen_one` still re-reads its own record.
    scope = ("--root", root) if root is not None else ()
    records = frozen_ops.store_records("--state", "frozen", *scope)
    if records is None:
        return None
    return [rec for rec in records
            if agent_sessions.valid_id(rec.get("id", ""))
            and rec.get("state") == agent_sessions.STATE_FROZEN]


def _classified(root: str | None) -> tuple[
        list[tuple[dict, str, Claim | None]], list[tuple[dict, str]]] | None:
    """``(items, errors)``: EVERY `frozen` record of ``root`` (every root for
    None) with its kind, ``tracked`` included.

    None when the store could not be listed. When tmux cannot be listed, no
    record is classified and each one becomes an ``(rec, "tmux_unreachable")``
    error instead — a listing that could not be read is not evidence of anything.
    """
    records = _frozen_records(root)
    if records is None:
        return None
    if not records:
        return [], []
    claims = _claimed_panes()
    if claims is None:
        return [], [(r, "tmux_unreachable") for r in records]
    items = []
    for rec in records:
        kind, claim = classify_record(rec, claims.get(rec["id"], []))
        items.append((rec, kind, claim))
    return items, []


def classify(root: str) -> tuple[list[tuple[dict, str, Claim | None]], list[str]] | None:
    """``(items, errors)`` for ``root``: every gone / stranded record.

    None when the store could not be listed. When tmux cannot be listed, no
    record is classified and each one yields a ``GONE_ERROR`` line instead.
    """
    result = _classified(root)
    if result is None:
        return None
    items, errors = result
    return ([item for item in items if item[1] != "tracked"],
            [f"GONE_ERROR:{rec['id']}|{reason}" for rec, reason in errors])


# --- every project's records (t2039) -----------------------------------------

#: A root `ait ide` may act on: registered in `ait projects`, marker present.
ROOT_OK = "ok"
#: The directory no longer holds the aitasks marker (gone, or not a project).
ROOT_MISSING = "missing"
#: Still a project, but not in the registry — the user removed or never added it.
ROOT_UNREGISTERED = "unregistered"
#: The registry could not be read, so registration cannot be decided.
ROOT_UNVERIFIED = "unverified"
#: The root's own marker could not be looked up (e.g. no search permission).
ROOT_INACCESSIBLE = "inaccessible"


def _project_marker(root: str) -> bool | None:
    """The registry's own OK/STALE rule (`agent_launch_utils._read_registry_index`).

    None when the lookup itself failed. Before Python 3.14 `Path.is_file()`
    re-raises every error but a missing path, so a directory without search
    permission raises `PermissionError`; letting it escape would abort the
    listing — and so `ait ide`'s offer — for every healthy project too.
    """
    try:
        return (Path(root) / "aitasks" / "metadata" / "project_config.yaml").is_file()
    except OSError:
        return None


def root_states(roots) -> dict[str, tuple[str, str]]:
    """``{root: (state, name)}`` for each root, against ONE registry read.

    ``name`` is the registry's name for the root, else its basename. The strict
    reader is used because this decides whether `ait ide` may create a tmux
    session for the root: a registry that could not be read is ``unverified``,
    never read as "not registered" and never as "registered".
    """
    try:
        registry: dict[str, str] | None = {}
        for entry in _parse_registry_records_strict():
            if entry.name and entry.path:
                registry.setdefault(os.path.realpath(entry.path), entry.name)
    except (OSError, ValueError):
        registry = None
    states: dict[str, tuple[str, str]] = {}
    for root in roots:
        name = os.path.basename(root.rstrip("/")) or root
        if registry and root in registry:
            name = registry[root]
        marker = _project_marker(root)
        if marker is None:
            state = ROOT_INACCESSIBLE
        elif not marker:
            state = ROOT_MISSING
        elif registry is None:
            state = ROOT_UNVERIFIED
        elif root in registry:
            state = ROOT_OK
        else:
            state = ROOT_UNREGISTERED
        states[root] = (state, name)
    return states


def gone_all_roots() -> list[str] | None:
    """The ``gone --all-roots`` wire lines; None when the store failed.

    Per root, sorted by ``(name, root)``: ``GONE_ROOT:<state>|<name>|<root>``,
    then its ``GONE:`` lines with ``|<root>`` appended, then its ``GONE_ERROR:``
    lines (``<id>|<reason>|<root>``). The root is always the LAST field and is
    printed verbatim, so a reader that splits on ``|`` into a fixed number of
    fields keeps any ``|`` inside it. A root containing a newline cannot be one
    wire line: its records become ``GONE_ERROR:<id>|root_unprintable`` with no
    group. Trailing ``GONE_COUNT:<n>`` counts the ``GONE:`` lines.
    """
    result = _classified(None)
    if result is None:
        return None
    items, errors = result
    groups: dict[str, tuple[list, list]] = {}
    unprintable: list[str] = []

    def group(rec: dict) -> tuple[list, list] | None:
        root = rec.get("root", "")
        if "\n" in root or "\r" in root:
            unprintable.append(rec["id"])
            return None
        return groups.setdefault(root, ([], []))

    for rec, kind, _claim in items:
        if kind == "tracked":
            continue
        g = group(rec)
        if g is not None:
            g[0].append((rec, kind))
    for rec, reason in errors:
        g = group(rec)
        if g is not None:
            g[1].append((rec, reason))

    states = root_states(groups)
    lines: list[str] = []
    for root in sorted(groups, key=lambda r: (states[r][1], r)):
        state, name = states[root]
        lines.append(f"GONE_ROOT:{state}|{_field(name)}|{root}")
        gones, errs = groups[root]
        lines.extend(f"{gone_line(rec, kind)}|{root}" for rec, kind in gones)
        lines.extend(f"GONE_ERROR:{rec['id']}|{reason}|{root}" for rec, reason in errs)
    lines.extend(f"GONE_ERROR:{rid}|root_unprintable" for rid in unprintable)
    lines.append(f"GONE_COUNT:{sum(len(g[0]) for g in groups.values())}")
    return lines


def companions(root: str | None) -> tuple[list[str], int]:
    """Give every tracked viewer of ``root`` (every root for None) its companion.

    ``(lines, exit_status)``. One ``COMPANION_SPAWNED:<id>|<session>:<window>|<pane>``
    per companion actually split, then ``COMPANION_COUNT:<n>``. A live or booting
    companion already in the window, a gate (auto-spawn off, overcrowding) or a
    failure spawns nothing and prints nothing: `maybe_spawn_minimonitor` decides,
    under its per-server lock, so two concurrent calls cannot both split. A store
    or tmux that cannot be read is ``COMPANION_ERROR:`` and exit 1.
    """
    result = _classified(root)
    if result is None:
        return ["COMPANION_ERROR:*|store unreadable", "COMPANION_COUNT:0"], 1
    items, errors = result
    if errors:
        return ["COMPANION_ERROR:*|tmux unreachable", "COMPANION_COUNT:0"], 1
    lines: list[str] = []
    status = 0
    for rec, kind, claim in items:
        if kind != "tracked" or claim is None or claim.dead:
            continue
        facts = frozen_ops.window_facts(claim.pane_id)
        if facts is None:
            lines.append(f"COMPANION_ERROR:{rec['id']}|tmux unreachable")
            status = 1
            continue
        if not facts:
            continue                    # the viewer went away meanwhile
        session, window = facts.get("session", ""), facts.get("window", "")
        pane = agent_restore._spawn_companion(session, window, claim.pane_id,
                                              rec.get("root", ""))
        if pane:
            lines.append(f"COMPANION_SPAWNED:{rec['id']}|"
                         f"{_field(session)}:{_field(window)}|{pane}")
    spawned = sum(1 for line in lines if line.startswith("COMPANION_SPAWNED:"))
    lines.append(f"COMPANION_COUNT:{spawned}")
    return lines, status


def _field(value: str) -> str:
    """A wire field: no `|`, no line break of any kind.

    Every `str.splitlines` break, not just `\n`: record values reach these lines
    verbatim (t2067), and a reader that splits on `\r` or `\u2028` would
    otherwise see one record as two lines.
    """
    return " ".join((value or "").replace("|", "/").splitlines())


def gone_line(rec: dict, kind: str) -> str:
    resume = agent_restore.resume_blocker(rec) or "ok"
    repick = agent_restore.repick_blocker(rec) or "ok"
    return "GONE:" + "|".join([
        rec["id"], kind, _field(rec.get("window", "")),
        _field(rec.get("task_id", "")), _field(rec.get("frozen_at", "")),
        resume, repick,
    ])


# --- tmux primitives ---------------------------------------------------------


def _find_by_window_name(session: str, name: str) -> tuple[str, str, int]:
    """`frozen_ops.find_pane_by_window_name`, behind the ``lookup`` seam."""
    if _seam("lookup"):
        return "unknown", "", 0
    return frozen_ops.find_pane_by_window_name(session, name)


def _kill_if_named(pane_id: str, name: str) -> tuple[str, str]:
    """`kill-window` on ``pane_id``'s window only if it is still named ``name``.

    The shared `frozen_ops.kill_window_read`, behind the ``cleanup`` seam. A
    window that survives is labelled by what the after-read saw: still ``name``
    → ``kill-failed``, renamed meanwhile → ``name-mismatch``. ``name`` is a
    per-attempt name, so a recycled ``%N`` in a restarted server cannot match it.
    """
    if _seam("cleanup"):
        return "present", "seam"
    verdict, reason, after = frozen_ops.kill_window_read(
        pane_id, frozen_ops.window_name_condition(name))
    if verdict != "present":
        return verdict, reason
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
    facts = frozen_ops.window_facts(pane_id) or {}
    own = facts.get("window_id", "")
    rc, out = frozen_ops.run(["list-windows", "-t", tmux_session_scope_target(session),
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
    facts = frozen_ops.window_facts(pane_id)
    if not facts or facts.get("frozen") != record_id:
        return False
    if facts.get("window") == final:
        return True                 # already right: no rename issued
    return frozen_ops.rename_window_if_stamped(pane_id, record_id, final,
                                               dispatch=not _seam("rename"))


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
    facts = frozen_ops.window_facts(pane_id) or {}
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
    facts = frozen_ops.window_facts(pane_id)
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
        facts = frozen_ops.window_facts(pane_id)
        if not facts or facts.get("frozen") != record_id:
            return fail("stamp")

    # --- 2. into the selected session --------------------------------------
    facts = frozen_ops.window_facts(pane_id)
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
        facts = frozen_ops.window_facts(pane_id)
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


def _survivor_line(record_id: str, claim: Claim) -> str:
    """A restore survivor (t1875) is neither adopted nor duplicated.

    Adopting it would commit a running AGENT as the record's viewer — the record
    says `frozen` while the agent is live, and the next restore `respawn-pane
    -k`s it as a stand-in. Creating a fresh viewer beside it would leave that
    agent untracked. The pane is named so the user can close it.
    """
    return f"REOPEN_FAILED:{record_id}|" + frozen_ops.survivor_detail({
        "session": claim.session, "window": claim.window, "pane_id": claim.pane_id})


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
    if kind == "survivor" and claim is not None:
        return _survivor_line(record_id, claim)
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
    if kind == "survivor" and claim is not None:
        _release(record_id, nonce)
        return _survivor_line(record_id, claim)
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

    A ``survivor`` record is listed too, and `reopen_one` refuses it with a
    ``REOPEN_FAILED:`` line naming the pane — it is reported, never acted on.
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

_USAGE = ("Usage: aitask_frozen.sh gone --root <path> | --all-roots\n"
          "       aitask_frozen.sh reopen <id> [--session NAME]\n"
          "       aitask_frozen.sh reopen --root <path> [--session NAME]\n"
          "       aitask_frozen.sh companions --root <path> | --all-roots")


def _take_root(args: list[str]) -> tuple[list[str], str | None, str]:
    if "--root" not in args:
        return args, None, ""
    i = args.index("--root")
    if i + 1 >= len(args) or not args[i + 1]:
        return args, None, "--root requires a path"
    root = args[i + 1]
    return args[:i] + args[i + 2:], os.path.realpath(root), ""


def _take_all_roots(args: list[str]) -> tuple[list[str], bool]:
    if "--all-roots" not in args:
        return args, False
    i = args.index("--all-roots")
    return args[:i] + args[i + 1:], True


def main(argv: list[str]) -> int:
    args = list(argv)
    if not args or args[0] not in ("gone", "reopen", "companions"):
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
    args, all_roots = _take_all_roots(args)

    if verb in ("gone", "companions"):
        # Exactly one scope, and nothing else: neither verb targets a session.
        if (root is None) == (not all_roots) or args or session is not None:
            print(_USAGE, file=sys.stderr)
            return 2
        if verb == "companions":
            lines, status = companions(None if all_roots else root)
            for line in lines:
                print(line)
            return status
        if all_roots:
            lines = gone_all_roots()
            if lines is None:
                print("GONE_ERROR:*|store unreadable")
                return 1
            for line in lines:
                print(line)
            return 0
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

    if all_roots:
        print(_USAGE, file=sys.stderr)
        return 2
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
