#!/usr/bin/env python3
"""orphan_ref_store.py - git plumbing for a flat JSON store on an orphan ref.

Reusable, policy-free layer under ``relations_store.py`` (t1981_1). It builds
trees through a temporary ``GIT_INDEX_FILE`` (the store layout has
subdirectories, which ``mktree`` cannot build in one call), commits with
``commit-tree``, and offers two compare-and-swap primitives: a leased push and
a local ``update-ref``. ``aitask_lock.sh`` / ``aitask_claim_id.sh`` are NOT
built on it; whether they adopt it is a retrospective question
(aidocs/framework/task_relations.md D1, D13).

Every function takes ``repo`` (a directory inside the repository) and passes it
as ``cwd=``; nothing here calls ``os.chdir``. Local plumbing runs through
``subprocess.run`` with its status checked; the network steps (``ls-remote``,
``fetch``, ``push``) run through ``bounded_run.run_bounded`` with
``noninteractive_env()`` so no credential or SSH prompt can wait on a terminal.
No shell pipelines are used, and git path output is read ``-z``.

Observed git behaviour (git 2.56.0, pinned by the t1981_1 pre-phase probe)
--------------------------------------------------------------------------
=====================================================  ====  ==============================================
operation                                              exit  output used for classification
=====================================================  ====  ==============================================
fetch of an absent remote ref                          128   "couldn't find remote ref" -> never used: probe first
ls-remote --heads, branch absent                       0     empty stdout                    -> ABSENT
ls-remote, missing path / file:// to a missing repo    128   (transport)                     -> ERROR
push --porcelain, accepted                             0     ``*`` / `` `` flag line          -> OK
push --porcelain --force-with-lease, base moved        1     ``!`` line, "(stale info)"      -> CONFLICT
push --porcelain --force-with-lease=<ref>: (empty),
  branch exists                                        1     ``!`` line, "(stale info)"      -> CONFLICT
push --porcelain, plain non-fast-forward               1     ``!`` line, "(non-fast-forward)" -> CONFLICT
push to an unreachable remote                          128   (transport)                     -> ERROR
update-ref <ref> <new> <old>, stale <old>              128   same status as any other failure -> classified
                                                             by RE-READING the ref, not stderr
update-ref <ref> <new> <zero-oid>, ref exists          128   ditto
merge-base --is-ancestor  a b                          0 / 1 / 128 (bad object)              -> True / False / raise
merge-base --all, unrelated histories                  1     empty stdout                    -> []
git remote remove origin                               -     deletes refs/remotes/origin/*;
                                                             keeps refs/heads/* and refs/aitask-relations/*
=====================================================  ====  ==============================================

A ``!`` porcelain line with any OTHER reason (a hook's "remote rejected", a
protected branch) is an ERROR, never a CONFLICT: retrying cannot fix it.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import uuid

_LIB = os.path.dirname(os.path.abspath(__file__))
import sys  # noqa: E402

if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

from bounded_run import noninteractive_env, run_bounded  # noqa: E402

ZERO_OID = "0" * 40
TMP_REF_PREFIX = "refs/aitask-relations/tmp/"
_CONFLICT_REASONS = ("stale info", "non-fast-forward", "fetch first")
_FALLBACK_IDENT = {
    "GIT_AUTHOR_NAME": "ait relations",
    "GIT_AUTHOR_EMAIL": "ait-relations@localhost",
    "GIT_COMMITTER_NAME": "ait relations",
    "GIT_COMMITTER_EMAIL": "ait-relations@localhost",
}


class GitError(RuntimeError):
    """A local git plumbing command failed (status checked, stderr kept)."""


def git(repo, *args, input=None, env=None, check=True):
    """Run one local git command; return its CompletedProcess (bytes)."""
    proc = subprocess.run(
        ["git", *args], cwd=str(repo), input=input, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if check and proc.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed ({proc.returncode}): "
                       f"{proc.stderr.decode('utf-8', 'replace').strip()}")
    return proc


def _out(repo, *args, **kw) -> str:
    return git(repo, *args, **kw).stdout.decode("utf-8", "replace").strip()


def toplevel(repo) -> str:
    """The working tree root containing ``repo``."""
    return _out(repo, "rev-parse", "--show-toplevel")


def git_common_dir(repo) -> str:
    """Absolute ``--git-common-dir`` (shared by every worktree of the clone)."""
    path = _out(repo, "rev-parse", "--git-common-dir")
    if not os.path.isabs(path):
        path = os.path.join(_out(repo, "rev-parse", "--show-toplevel"), path)
    return os.path.realpath(path)


def remote_url(repo, remote="origin"):
    """The remote's URL, or None when it is not configured."""
    proc = git(repo, "remote", "get-url", remote, check=False)
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("utf-8", "replace").strip() or None


def _bounded(repo, args, timeout):
    """(returncode, stdout, stderr) of a network git command; 124 = timed out."""
    try:
        res = run_bounded(["git", *args], timeout, env=noninteractive_env(),
                          cwd=str(repo))
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    return res.returncode, res.stdout or "", res.stderr or ""


def _reason(stderr: str, fallback: str) -> str:
    lines = [ln.strip() for ln in stderr.splitlines() if ln.strip()]
    text = lines[0] if lines else fallback
    return text.replace("|", "/").replace("\n", " ")[:200]


def probe_remote_branch(repo, ref, timeout, remote="origin") -> str:
    """``PRESENT`` | ``ABSENT`` | ``ERROR:<reason>`` (``ls-remote --heads``)."""
    rc, out, err = _bounded(repo, ["ls-remote", "--heads", remote, ref], timeout)
    if rc == 124:
        return "ERROR:timeout"
    if rc != 0:
        return f"ERROR:{_reason(err, f'ls-remote exit {rc}')}"
    want = f"refs/heads/{ref}"
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) == 2 and parts[1].strip() == want:
            return "PRESENT"
    return "ABSENT"


def fetch_pinned(repo, ref, timeout, remote="origin"):
    """Fetch ``refs/heads/<ref>`` into a private temp ref; return (sha, error).

    The shared refs are never written by a fetch (a forced ``+src:dst`` into a
    shared ref could rewind a newer local publish). The temp ref is deleted
    before returning, and the caller works only with the returned sha.
    """
    tmp = f"{TMP_REF_PREFIX}{os.getpid()}-{uuid.uuid4().hex[:12]}"
    try:
        rc, _out_, err = _bounded(
            repo, ["fetch", "--no-tags", "--no-write-fetch-head", remote,
                   f"+refs/heads/{ref}:{tmp}"], timeout)
        if rc == 124:
            return None, "timeout"
        if rc != 0:
            return None, _reason(err, f"fetch exit {rc}")
        sha = resolve(repo, tmp)
        if sha is None:
            return None, "fetch produced no ref"
        return sha, None
    finally:
        git(repo, "update-ref", "-d", tmp, check=False)


def resolve(repo, refname):
    """The commit a ref points at, or None."""
    proc = git(repo, "rev-parse", "--verify", "-q", f"{refname}^{{commit}}",
               check=False)
    if proc.returncode != 0:
        return None
    return proc.stdout.decode().strip() or None


def is_ancestor(repo, a, b) -> bool:
    """``a`` is an ancestor of (or equal to) ``b``. Raises on a bad object."""
    proc = git(repo, "merge-base", "--is-ancestor", a, b, check=False)
    if proc.returncode == 0:
        return True
    if proc.returncode == 1:
        return False
    raise GitError(f"merge-base --is-ancestor {a} {b} failed ({proc.returncode})")


def merge_bases(repo, a, b) -> list:
    """Every best common ancestor (``merge-base --all``); [] when unrelated."""
    proc = git(repo, "merge-base", "--all", a, b, check=False)
    if proc.returncode == 1 and not proc.stdout.strip():
        return []
    if proc.returncode != 0:
        raise GitError(f"merge-base --all {a} {b} failed ({proc.returncode})")
    return proc.stdout.decode().split()


def tree_of(repo, commit):
    return _out(repo, "rev-parse", f"{commit}^{{tree}}")


def read_tree(repo, commit) -> dict:
    """``{path: blob_sha}`` of a commit (``ls-tree -r -z``); {} for None."""
    if commit is None:
        return {}
    raw = git(repo, "ls-tree", "-r", "-z", "--full-tree", commit).stdout
    result = {}
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        meta, _, path = entry.partition(b"\t")
        fields = meta.split()
        if len(fields) != 3 or fields[1] != b"blob":
            continue
        result[path.decode("utf-8", "surrogateescape")] = fields[2].decode()
    return result


def cat_blobs(repo, shas) -> dict:
    """``{sha: bytes}`` through one ``cat-file --batch`` run."""
    wanted = [s for s in dict.fromkeys(shas) if s]
    if not wanted:
        return {}
    raw = git(repo, "cat-file", "--batch",
              input=("\n".join(wanted) + "\n").encode()).stdout
    result, pos = {}, 0
    for sha in wanted:
        nl = raw.index(b"\n", pos)
        header = raw[pos:nl].decode().split()
        pos = nl + 1
        if len(header) < 2 or header[1] == "missing":
            raise GitError(f"cat-file: object {sha} missing")
        size = int(header[2])
        result[header[0]] = raw[pos:pos + size]
        pos += size + 1  # the LF after the content
    return result


def read_file(repo, commit, path):
    """The bytes of one path in a commit, or None when it is absent.

    One ``ls-tree`` of that path plus one blob read, so the cost does not grow
    with the size of the store (used while the outbox lock is held).
    """
    if commit is None:
        return None
    raw = git(repo, "ls-tree", "-z", "--full-tree", commit, "--", path).stdout
    for entry in raw.split(b"\0"):
        meta, _, name = entry.partition(b"\t")
        fields = meta.split()
        if len(fields) == 3 and fields[1] == b"blob" and name.decode("utf-8", "surrogateescape") == path:
            sha = fields[2].decode()
            return cat_blobs(repo, [sha])[sha]
    return None


def read_files(repo, commit) -> dict:
    """``{path: bytes}`` of every blob in a commit."""
    tree = read_tree(repo, commit)
    blobs = cat_blobs(repo, tree.values())
    return {path: blobs[sha] for path, sha in tree.items()}


def _commit_env(repo, extra=None):
    env = dict(os.environ)
    if extra:
        env.update(extra)
    for key in ("user.name", "user.email"):
        if git(repo, "config", "--get", key, check=False).returncode != 0:
            env.update({k: v for k, v in _FALLBACK_IDENT.items()
                        if k not in os.environ})
            break
    return env


def build_commit(repo, base, changes: dict, message: str,
                 extra_parents=()) -> str:
    """Commit ``base``'s tree with ``changes`` applied ({path: bytes|None}).

    ``base`` None starts from the empty tree. ``extra_parents`` add merge
    parents (the relations store's replay and absorb merges). Uses a private
    temporary index, so the repository's own index is never touched.
    """
    with tempfile.TemporaryDirectory(prefix="ait-orphan-idx-") as tmpdir:
        env = _commit_env(repo, {"GIT_INDEX_FILE": os.path.join(tmpdir, "index")})
        if base is not None:
            git(repo, "read-tree", base, env=env)
        else:
            git(repo, "read-tree", "--empty", env=env)
        for path in sorted(changes):
            data = changes[path]
            if data is None:
                git(repo, "update-index", "--force-remove", "--", path, env=env)
                continue
            sha = git(repo, "hash-object", "-w", "--stdin",
                      input=data).stdout.decode().strip()
            git(repo, "update-index", "--add", "--cacheinfo",
                f"100644,{sha},{path}", env=env)
        tree = _out(repo, "write-tree", env=env)
        args = ["commit-tree", tree]
        for parent in ([base] if base is not None else []) + list(extra_parents):
            args += ["-p", parent]
        return git(repo, *args, input=message.encode(), env=env).stdout.decode().strip()


def commit_tree_from_files(repo, files: dict, message: str, parents=()) -> str:
    """Commit exactly ``files`` ({path: bytes}) with the given parents.

    ``build_commit`` from the empty tree: with ``base=None`` its only parents
    are ``extra_parents``, in order, so the parent list is exactly ``parents``.
    """
    if any(data is None for data in files.values()):
        raise ValueError("commit_tree_from_files takes contents only (no deletions)")
    return build_commit(repo, None, files, message, extra_parents=tuple(parents))


def cas_push(repo, commit, ref, base, timeout, remote="origin") -> str:
    """Leased push: ``OK`` | ``CONFLICT`` | ``ERROR:<reason>``.

    ``--force-with-lease=refs/heads/<ref>:<base>`` (empty when ``base`` is
    None: the branch must not exist) protects the exact base the commit was
    built on, whatever its other parents contain.
    """
    lease = f"refs/heads/{ref}:{base or ''}"
    rc, out, err = _bounded(
        repo, ["push", "--porcelain", f"--force-with-lease={lease}", remote,
               f"{commit}:refs/heads/{ref}"], timeout)
    if rc == 124:
        return "ERROR:timeout"
    if rc == 0:
        return "OK"
    for line in out.splitlines():
        if line.startswith("!") and f"refs/heads/{ref}" in line:
            if any(reason in line for reason in _CONFLICT_REASONS):
                return "CONFLICT"
            return f"ERROR:{_reason(line, 'push rejected')}"
    return f"ERROR:{_reason(err, f'push exit {rc}')}"


def cas_local(repo, ref, new, old) -> str:
    """``update-ref <ref> <new> <old|zero-oid>``: ``OK`` | ``CONFLICT``.

    git gives a CAS miss the same exit status as any other failure, so a
    failure is classified by re-reading the ref: a value different from
    ``old`` is a CONFLICT, anything else re-raises.
    """
    proc = git(repo, "update-ref", ref, new, old or ZERO_OID, check=False)
    if proc.returncode == 0:
        return "OK"
    if resolve(repo, ref) != old:
        return "CONFLICT"
    raise GitError(f"update-ref {ref} failed: "
                   f"{proc.stderr.decode('utf-8', 'replace').strip()}")


def advance_ref(repo, ref, new, attempts=8) -> str:
    """Fast-forward-only CAS: ``ADVANCED`` | ``ALREADY_NEWER`` | ``DIVERGED``."""
    for _ in range(attempts):
        cur = resolve(repo, ref)
        if cur == new:
            return "ALREADY_NEWER"
        if cur is not None and is_ancestor(repo, new, cur):
            return "ALREADY_NEWER"
        if cur is not None and not is_ancestor(repo, cur, new):
            return "DIVERGED"
        if cas_local(repo, ref, new, cur) == "OK":
            return "ADVANCED"
    return "DIVERGED"


def reset_ref(repo, ref, new) -> None:
    """Unconditional local ref write — only for advisory refs (never data)."""
    git(repo, "update-ref", ref, new)
