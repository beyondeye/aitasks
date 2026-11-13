"""Commit a reviewed change set from its approved snapshots.

The commit boundary of a review approval. `git commit` reads the working tree,
so a claim followed by `git commit` leaves a window in which another writer's
bytes are committed under the approval. This module never reads the working
tree: the tree it commits is the branch's current tree with each approved path
replaced by the bytes stored when the question was asked (or removed, for a
path bound as deleted).

What is enforced, and where:

  content   every committed path comes from `Store._blob`; a path that was not
            bound cannot enter the commit.
  form      the stored bytes are working-tree bytes. They are converted the
            way `git add` would (clean filters, line endings) for their path,
            and the result must be the object id bound when the question was
            asked (`blob`): a filter or attribute that changed since refuses
            the commit instead of committing another representation.
  target    the occurrence bound the branch and, per path, the tree entry the
            branch held (`base`: mode, type and object). Both are re-read from
            the commit's actual parent; a branch that moved under an approved
            path - its content, its mode or its type - refuses the commit.
  hooks     the tree is the one checked above. A `pre-commit` hook that
            changes the index refuses the commit: what it would add or drop
            was not approved.
  ref       the branch is advanced with a compare-and-swap on that same
            parent, so the verified parent is the one committed onto.
  claim     the commit object is built first and recorded in the transaction
            that proves the approval fresh (`Store.consume(effect=...)`).

Not done here: `prepare-commit-msg` and `post-commit` hooks do not run (the
commit is made with plumbing); `pre-commit` and `commit-msg` do.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile

from .errors import QuestionError
from .store import tree_entry

ATTEMPTS = 3  # rebuilds when the branch advances between read and update


class Refused(Exception):
    """The commit must not be made; str() is the machine-readable reason."""


def _git(project, *args, data=None, env=None, check=True):
    try:
        done = subprocess.run(["git", "-C", str(project), *args], input=data,
                              capture_output=True, timeout=120, check=False,
                              env={**os.environ, **(env or {})})
    except (OSError, subprocess.SubprocessError) as exc:
        raise Refused("git_unavailable") from exc
    if check and done.returncode != 0:
        raise Refused(f"git_failed:{args[0]}")
    return done


def _entry_at(project, commit, path):
    """The tree entry `commit` holds at `path` ("<mode> <type> <id>"), or None."""
    return tree_entry(_git(project, "ls-tree", "-z", commit, "--", path).stdout, path)


def _hook(project, name, env, *args):
    """Run a client hook the way `git commit` would; absent hooks pass."""
    done = _git(project, "hook", "run", "--ignore-missing", name, *(["--", *args] if args else []),
                env=env, check=False)
    if done.returncode != 0:
        raise Refused(f"hook_rejected:{name}")


def build(store, body, parent, message):
    """Create the commit object for `body`'s manifest on top of `parent`."""
    project = store.project
    files = [e for e in body["manifest"] if "projection" not in e]
    for entry in files:
        if "base" not in entry:
            raise Refused("target_not_bound")
        if not entry.get("absent") and not entry.get("blob"):
            raise Refused("target_not_bound")
        if _entry_at(project, parent, entry["path"]) != entry["base"]:
            raise Refused(f"target_changed:{entry['path']}")
    with tempfile.TemporaryDirectory(prefix="aitask-approved-commit-") as tmp:
        env = {"GIT_INDEX_FILE": str(Path(tmp) / "index")}
        _git(project, "read-tree", parent, env=env)
        for entry in files:
            if entry.get("absent"):
                _git(project, "update-index", "--force-remove", "--", entry["path"], env=env)
                continue
            try:
                data = store._blob(entry["sha256"])
            except QuestionError as exc:
                raise Refused("approved_snapshot_unavailable") from exc
            how = ["--no-filters"] if entry["mode"] == "120000" else [f"--path={entry['path']}"]
            oid = _git(project, "hash-object", "-w", *how, "--stdin",
                       data=data).stdout.decode().strip()
            if oid != entry["blob"]:
                raise Refused(f"conversion_changed:{entry['path']}")
            _git(project, "update-index", "--add", "--cacheinfo",
                 f"{entry['mode']},{oid},{entry['path']}", env=env)
        tree = _git(project, "write-tree", env=env).stdout.decode().strip()
        if tree == _git(project, "rev-parse", f"{parent}^{{tree}}").stdout.decode().strip():
            raise Refused("nothing_to_commit")
        _hook(project, "pre-commit", env)
        if _git(project, "write-tree", env=env).stdout.decode().strip() != tree:
            raise Refused("hook_changed_index:pre-commit")
        message_file = Path(tmp) / "COMMIT_EDITMSG"
        message_file.write_bytes(message)
        _hook(project, "commit-msg", env, str(message_file))
        sign = _git(project, "config", "--bool", "commit.gpgsign", check=False).stdout.strip() == b"true"
        return _git(project, "commit-tree", tree, "-p", parent, *(["-S"] if sign else []),
                    "-F", str(message_file)).stdout.decode().strip()


def commit(store, body, receipt_id, consumer, message):
    """Claim `body`'s receipt and commit its change set. Returns (outcome, commit id).

    Idempotent for one consumer: a repeat after success returns `duplicate`
    with the same commit; a repeat after a crash finishes the interrupted run.
    """
    project = store.project
    if not message.strip():
        raise Refused("empty_message")
    top = _git(project, "rev-parse", "--show-toplevel", check=False)
    if top.returncode != 0 or Path(os.fsdecode(top.stdout.strip())).resolve() != project:
        raise Refused("project_is_not_a_git_work_tree")
    target = body.get("target")
    if not target:
        raise Refused("target_not_bound")
    ref, session = target["ref"], body["id"]

    claim = store.status(session)["consumption"]
    if claim:
        if claim["consumer"] != consumer or claim["receipt_id"] != receipt_id:
            raise Refused("conflict")
        if claim.get("revoked"):
            raise Refused("stale_approval")
        effect = claim.get("effect")
        if effect and _git(project, "merge-base", "--is-ancestor", effect["commit"], ref,
                           check=False).returncode == 0:
            if not effect.get("applied"):
                store.record_effect(session, claim["id"], {**effect, "applied": True})
            return "duplicate", effect["commit"]

    for _ in range(ATTEMPTS):
        parent = _git(project, "rev-parse", "--verify", f"{ref}^{{commit}}").stdout.decode().strip()
        oid = build(store, body, parent, message)
        effect = {"commit": oid, "ref": ref, "applied": False}
        if claim is None:
            result = store.consume(session, receipt_id, consumer, effect=effect)
            if result["outcome"] != "claimed":
                raise Refused(result["outcome"])
            claim = result["consumption"]
        elif store.record_effect(session, claim["id"], effect)["outcome"] != "recorded":
            raise Refused("stale_approval")
        subject = message.decode("utf-8", "replace").strip().splitlines()[0]
        moved = _git(project, "update-ref", "-m", f"commit (approved): {subject}",
                     ref, oid, parent, check=False)
        if moved.returncode != 0:
            continue  # the branch advanced: verify and build again on the new tip
        store.record_effect(session, claim["id"], {**effect, "applied": True})
        # Bring the index to the commit for these paths only, as `git commit
        # -- <paths>` would. Best effort: a failure leaves a correct commit and
        # an index that still shows the old entries.
        paths = [e["path"] for e in body["manifest"] if "projection" not in e]
        synced = _git(project, "reset", "-q", oid, "--", *paths, check=False).returncode == 0
        store.acknowledge(session, claim["id"])
        return ("committed" if synced else "committed_index_not_refreshed"), oid
    raise Refused("target_kept_moving")
