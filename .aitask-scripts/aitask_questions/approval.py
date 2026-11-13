"""Approval guard between the question store and the gate ledger.

Used only by the gate scripts, and only for an attended Codex session in a
project that registers the question server (see `codex_attended_approvals` in
aitask_gate.sh). It answers three questions the store alone cannot:

  claim   - may THIS receipt record THIS task's approval gate right now?
  check   - is a recorded approval still the approval of what is on disk?
  commit  - commit the change set a review approved, from the approved bytes
            (commit.py); the only way a review approval becomes recordable.
  merge   - may THIS revision be merged into THIS branch now? (the merge
            broker asks, immediately before it merges)
  settled - is any approval of this task still open, declined, voided or
            stale? (the archive script asks, before it archives)

Every refusal is a line on stdout and a non-zero exit; nothing is recorded by
this module. Spec: aidocs/codeagents/codex_questions.md, "Gate enforcement".
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from . import commit as approved_commit
from . import projection
from .errors import QuestionError
from .projection import PLAN_PROJECTION
from .store import Store, digest, load

# Human approval gates the workflow records from a question. The checkpoint
# name of the occurrence must be the gate name: an answered label filter or
# explanation prompt can never stand in for an approval.
APPROVAL_GATES = ("plan_approved", "review_approved", "merge_approved")
# The approving option's id must start with this. Ids are chosen by the asking
# agent, so this catches an honest mix-up (recording "Revise plan" as a pass),
# not a model that mislabels its own options.
APPROVE_PREFIX = "approve"
# Gates whose approval is OF files: the occurrence must have bound them.
NEEDS_ARTIFACTS = ("plan_approved", "review_approved")

# Verdicts (Store.coverage) under which an approval still permits its action,
# and those under which a finished task may be archived. NOTES is only in the
# second: an approved plan followed by the workflow's closing sections.
STANDS = ("FRESH", "BOOKKEEPING")
ARCHIVABLE = STANDS + ("NOTES",)

EXIT_REFUSED = 3


def consumer_key(task, gate):
    return f"t{task}:{gate}"


def _approving(body):
    """True when the first question was answered with an approving option."""
    first = body["questions"][0]
    answer = body["answers"].get(first["id"])
    if first["kind"] != "choice" or not answer:
        return False
    return isinstance(answer["value"], str) and answer["value"].startswith(APPROVE_PREFIX)


def _bound_as(store, bound, wanted):
    """The bound path that is the same file as `wanted`, or None.

    Compared as resolved files: the ledger side may name the plan by absolute
    path or through the aiplans symlink, the asking side by project-relative
    path.
    """
    try:
        target = (store.project / wanted).resolve(strict=True)
        return next((path for path in bound
                     if (store.project / path).resolve(strict=True) == target), None)
    except OSError:
        return None


def _eligible(store, task, gate, session_id):
    """The occurrence, if it is an approval of this task's gate: (reason, body)."""
    with store.connect() as conn:
        row = conn.execute("SELECT body FROM sessions WHERE id=?", (session_id,)).fetchone()
    if row is None:
        return "unknown_session", None
    body = load(row[0])
    if body["project"] != str(store.project):
        return "foreign_project", None
    if body["workflow"] != f"t{task}":
        return "wrong_workflow", None
    if body["checkpoint"] != gate:
        return "wrong_checkpoint", None
    if not _approving(body):
        return "answer_is_not_an_approval", None
    if gate in NEEDS_ARTIFACTS and not any("projection" not in e for e in body["manifest"]):
        return "nothing_bound", None
    if gate == projection.MERGE_CHECKPOINT and projection.unmet(
            body["workflow"], gate, body["manifest"], body.get("target")):
        return "merge_not_bound", None
    return "", body


def commit(store, task, session_id, receipt_id, message):
    """Commit the change set of a review approval. Returns (outcome, commit-or-None)."""
    reason, body = _eligible(store, task, projection.CHANGE_CHECKPOINT, session_id)
    if body is None:
        return reason, None
    try:
        return approved_commit.commit(store, body, receipt_id,
                                      consumer_key(task, projection.CHANGE_CHECKPOINT), message)
    except approved_commit.Refused as exc:
        return str(exc), None


def claim(store, task, gate, session_id, receipt_id, plan_file=None):
    """Claim a receipt for one gate record. Returns (outcome, body-or-None)."""
    reason, body = _eligible(store, task, gate, session_id)
    if body is None:
        return reason, None
    bound = [entry["path"] for entry in body["manifest"] if "sha256" in entry
             and "projection" not in entry]
    tolerates = {}
    if gate == "plan_approved":
        if projection.unmet(body["workflow"], gate, body["manifest"]):
            return "task_requirements_not_bound", None
        if plan_file:
            plan = _bound_as(store, bound, plan_file)
            if plan is None:
                return "plan_file_not_bound", None
            tolerates[plan] = PLAN_PROJECTION
    # Refresh first: the occurrence must be valid NOW. An earlier claim is only
    # a completed action's record - it is reusable for that action's own ledger
    # entry while it still stands, never once revoked (files changed, or the
    # checkpoint was asked again).
    earlier = store.status(session_id)["consumption"]
    if gate == projection.CHANGE_CHECKPOINT:
        # A review approval is recorded only for a commit made from its
        # approved bytes. The receipt alone - or a commit made any other way -
        # does not show that what was committed is what was approved.
        if not earlier or earlier["consumer"] != consumer_key(task, gate) \
                or earlier["receipt_id"] != receipt_id or not earlier.get("effect"):
            return "review_commit_missing", None
        if store.standing(session_id)[0] != "FRESH":
            return "stale_approval", None
        return "duplicate", {"session_id": body["id"], "consumption": earlier}
    if earlier and earlier["consumer"] == consumer_key(task, gate) and earlier["receipt_id"] == receipt_id:
        if earlier.get("revoked") or store.standing(session_id)[0] not in STANDS:
            return "stale_approval", None
        return "duplicate", {"session_id": body["id"], "consumption": earlier}
    result = store.consume(session_id, receipt_id, consumer_key(task, gate), tolerates)
    if result["outcome"] != "claimed":
        return result["outcome"], None
    return "claimed", result


def merge(store, task, source, destination, session_id=None, receipt_id=None):
    """May `source` be merged into `destination` for this task now?

    Returns (outcome, commit-or-None). The commit is the approved revision;
    the caller merges THAT, not whatever the branch name resolves to later.
    The approval is the newest one claimed for the task's merge gate (the
    gate record claims it), or the receipt passed here, claimed now.
    """
    gate = projection.MERGE_CHECKPOINT
    if session_id:
        outcome, _ = claim(store, task, gate, session_id, receipt_id)
        if outcome not in ("claimed", "duplicate"):
            return outcome, None
        body = find_claim(store, task, gate, session_id)
    else:
        body = find_claim(store, task, gate)
    if body is None:
        return "merge_approval_missing", None
    target = body.get("target") or {}
    if target.get("kind") != "merge":
        return "merge_not_bound", None
    if destination.startswith("refs/heads/"):
        destination = destination[len("refs/heads/"):]
    if destination != target["destination"]:
        return "merge_destination_differs", None
    if store._commit_of(source) != target["source"]:
        return "merge_source_differs", None
    if store.standing(body["id"])[0] != "FRESH":
        return "stale_approval", None
    return "approved", target["source"]


def settled(store, task, skip=()):
    """Approvals of this task that are not settled: ["<gate>:<why>", ...].

    For each approval gate, the NEWEST occurrence asked for the task decides
    (an older one was retired when the step was asked again). A gate that was
    never asked is not judged here - whether a task needs that approval is the
    workflow's and the gate ledger's question, not the question store's.

      unanswered    the question is still open (form, prompt or deferred)
      declined      the user cancelled it
      voided        what it was asked about changed before it was used
      not_approved  it was answered, but not with an approving option
      not_recorded  it was approved, and the approval was never claimed
      not_committed a review's commit was built but is not on its branch
      stale         the claimed approval no longer stands, or was revoked

    The workflow writes its closing sections into the plan after the work is
    done. That one shape (verdict NOTES: the approved plan intact, only those
    sections after it) is settled here. Any other change to the plan or to
    the task's requirements, and any revocation, is `stale`.
    """
    open_states = ("pending", "awaiting-chat-answer", "deferred")
    with store.connect() as conn:
        rows = conn.execute("SELECT body FROM sessions ORDER BY rowid").fetchall()
    newest = {}
    for row in rows:
        try:
            body = load(row[0])
        except QuestionError:
            continue
        if body["project"] == str(store.project) and body["workflow"] == f"t{task}" \
                and body["checkpoint"] in APPROVAL_GATES:
            newest[body["checkpoint"]] = body["id"]
    blocking = []
    for gate in APPROVAL_GATES:
        if gate in skip or gate not in newest:
            continue
        view = store.status(newest[gate])  # refreshes: a changed file voids it here
        record = view["consumption"]
        if record and record["consumer"] == consumer_key(task, gate):
            verdict = store.standing(newest[gate])[0]
            why = "" if verdict in ARCHIVABLE else \
                {"PREPARED": "not_committed"}.get(verdict, "stale")
        elif view["state"] in open_states:
            why = "unanswered"
        elif view["state"] == "cancelled":
            why = "declined"
        elif view["state"] == "invalidated":
            why = "voided"
        else:
            with store.connect() as conn:
                body = load(conn.execute("SELECT body FROM sessions WHERE id=?",
                                         (newest[gate],)).fetchone()[0])
            why = "not_recorded" if _approving(body) else "not_approved"
        if why:
            blocking.append(f"{gate}:{why}")
    return blocking


def find_claim(store, task, gate, occurrence=None):
    """The occurrence claimed for the gate: the named one, else the newest."""
    wanted = consumer_key(task, gate)
    found = None
    with store.connect() as conn:
        rows = conn.execute("SELECT body FROM sessions ORDER BY rowid").fetchall()
    for row in rows:
        try:
            body = load(row[0])
        except QuestionError:
            continue
        claim_record = body.get("consumption")
        if body["project"] != str(store.project) or not claim_record or claim_record["consumer"] != wanted:
            continue
        if occurrence is None or body["id"] == occurrence:
            found = body
    return found


def check(store, task, gate, occurrence=None):
    """Compare a recorded approval with the files as they are now.

    Evidence, not a verdict on intent:
      UNBOUND      no claimed receipt for this gate in this checkout's state
      FRESH        every bound entry matches
      BOOKKEEPING  the plan changed only within plan-bookkeeping/v2
      NOTES        the approved plan is intact; only the workflow's closing
                   sections follow it (archivable, not a standing approval)
      PREPARED     a review's commit object exists but is not on its branch
      STALE        anything else; persisted, so reverting does not undo it
    """
    body = find_claim(store, task, gate, occurrence)
    if body is None:
        return "UNBOUND", "-", "no claimed receipt for this gate"
    verdict, detail = store.standing(body["id"])
    return verdict, body["id"], detail


def main(argv=None):
    parser = argparse.ArgumentParser(prog="aitask_questions.approval")
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--state-dir", required=True, type=Path)
    sub = parser.add_subparsers(dest="verb", required=True)
    for name in ("claim", "ack"):
        p = sub.add_parser(name)
        p.add_argument("--task", required=True)
        p.add_argument("--gate", required=True, choices=APPROVAL_GATES)
        p.add_argument("--session", required=True)
        p.add_argument("--receipt", required=True)
        p.add_argument("--plan-file", default=None)
    p = sub.add_parser("commit")
    p.add_argument("--task", required=True)
    p.add_argument("--session", required=True)
    p.add_argument("--receipt", required=True)
    p.add_argument("--message-file", required=True,
                   help="commit message file; - reads stdin")
    p = sub.add_parser("check")
    p.add_argument("--task", required=True)
    p.add_argument("--gate", required=True, choices=APPROVAL_GATES)
    p.add_argument("--occurrence", default=None)
    p = sub.add_parser("merge")
    p.add_argument("--task", required=True)
    p.add_argument("--source", required=True)
    p.add_argument("--into", required=True)
    p.add_argument("--session", default=None)
    p.add_argument("--receipt", default=None)
    p = sub.add_parser("settled")
    p.add_argument("--task", required=True)
    p.add_argument("--skip", default="", help="comma-separated gates settled by a profile")
    args = parser.parse_args(argv)

    try:
        if args.verb == "check" and not (args.state_dir / "questions.sqlite3").exists():
            # Never create state just to say there is none.
            print("APPROVAL:UNBOUND|-|no question state for this user")
            return 0
        if args.verb == "settled" and not (args.state_dir / "questions.sqlite3").exists():
            print("APPROVALS:settled|no question state for this user")
            return 0
        store = Store(args.state_dir, args.project)
        if args.verb == "settled":
            blocking = settled(store, args.task, [g for g in args.skip.split(",") if g])
            if blocking:
                print("APPROVALS:blocked|" + ",".join(blocking))
                return EXIT_REFUSED
            print("APPROVALS:settled|-")
            return 0
        if args.verb == "merge":
            if bool(args.session) != bool(args.receipt):
                print("MERGE_REFUSED:approval_must_be_session_and_receipt")
                return EXIT_REFUSED
            outcome, oid = merge(store, args.task, args.source, args.into, args.session, args.receipt)
            if oid is None:
                print(f"MERGE_REFUSED:{outcome}")
                return EXIT_REFUSED
            print(f"MERGE:approved|{oid}|{args.into}")
            return 0
        if args.verb == "check":
            verdict, occurrence, detail = check(store, args.task, args.gate, args.occurrence)
            print(f"APPROVAL:{verdict}|{occurrence}|{detail}")
            return 0
        if args.verb == "commit":
            message = (sys.stdin.buffer.read() if args.message_file == "-"
                       else Path(args.message_file).read_bytes())
            outcome, oid = commit(store, args.task, args.session, args.receipt, message)
            if oid is None:
                print(f"COMMIT_REFUSED:{outcome}")
                return EXIT_REFUSED
            print(f"COMMIT:{outcome}|{oid}")
            return 0
        if args.verb == "claim":
            outcome, result = claim(store, args.task, args.gate, args.session,
                                    args.receipt, args.plan_file)
            if result is None:
                print(f"CLAIM_REFUSED:{outcome}")
                return EXIT_REFUSED
            print(f"CLAIM:{outcome}|{result['session_id']}|{args.receipt}|"
                  f"{digest(result['consumption']['manifest'])[:16]}|"
                  f"{result['consumption']['id']}|"
                  f"{'acknowledged' if result['consumption']['acknowledged'] else 'open'}")
            return 0
        body = find_claim(store, args.task, args.gate)
        if body is None or body["id"] != args.session:
            print("ACK_REFUSED:unknown_claim")
            return EXIT_REFUSED
        print("ACK:" + store.acknowledge(args.session, body["consumption"]["id"])["outcome"])
        return 0
    except QuestionError as exc:
        # Unknown session, foreign project, corrupt or locked state: refuse.
        prefix = {"check": "APPROVAL:STALE|-|", "commit": "COMMIT_REFUSED:",
                  "merge": "MERGE_REFUSED:", "settled": "APPROVALS:blocked|"}.get(args.verb, "CLAIM_REFUSED:")
        print(f"{prefix}{exc}")
        return 0 if args.verb == "check" else EXIT_REFUSED
    except OSError:
        print("COMMIT_REFUSED:message_unreadable")
        return EXIT_REFUSED


if __name__ == "__main__":
    sys.exit(main())
