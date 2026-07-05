#!/usr/bin/env python3
"""artifact_manifest.py - per-artifact manifest store (t1076_1).

The MUTABLE resolution layer of the unified artifact model
(aidocs/unified_artifact_design.md par.4b): ONE JSON file per artifact at
<manifest-dir>/<id>.json, where <id> is the stable handle minus its "art:"
prefix. Settled t1076_1 decision: manifests are COMMITTED per-artifact files in
the data worktree (artifacts/manifests/) -- they travel with the aitask-data
branch, so any configured PC resolves the handle; per-file granularity avoids a
global write-hotspot (same rationale as the per-blob attachment meta ledger).
Updating a manifest NEVER touches a task file.

Schema (all fields required; invariants enforced on every load AND before
every write):

    {"handle": "art:t774-htmlplan",
     "current": "sha256:<64hex>",
     "versions": ["sha256:<hexA>", "sha256:<hexB>"],
     "backend": "local",
     "created_at": 1750000000,
     "updated_at": 1750000500}

Invariants: handle matches HANDLE_RE and the filename; versions is non-empty,
ordered oldest->newest, duplicate-free, every entry matches HASH_RE;
current is a member of versions; backend matches BACKEND_RE (conservative
name-shape validation -- registry membership / configuration is t1076_3's
concern; this only stops typos from persisting to fail far away at
resolution); timestamps are integer epochs.

MALFORMED-MANIFEST POLICY (fail-closed, named): every subcommand that reads a
manifest -- including the tree-scanning `list` / `referenced-hashes` -- dies on
invalid JSON or an invariant violation, naming the offending FILE PATH and the
violated invariant. No skip-and-continue: `referenced-hashes` is consumed by
`ait attach gc` as its blocking set, and a scan that silently drops an
unreadable member could greenlight deleting a still-referenced blob.

LOCK-FREE PRIMITIVE: this script NEVER takes a lock -- callers own concurrency.
MUTATION subcommands (create/set-current/set-backend) must run under the global
attachments/.attach.lock (see attachment_lock.sh) -- manifests share the blob
store with attachments and gc unions manifest references into its blocking
set, so one lock serializes both ledgers against the sweep. Read-only
subcommands are safe lock-free because every write is atomic (temp +
os.replace).

Substrate only: artifact-level semantics (handle minting, `artifacts:`
frontmatter, update-in-place operations, version pruning / deletion) belong to
t1076_2 and are built ON these primitives. There is deliberately no `delete`.
"""

import json
import os
import re
import sys
import tempfile
import time

HANDLE_RE = re.compile(r"^art:[a-z0-9][a-z0-9._-]{0,127}$")
HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
BACKEND_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")

REQUIRED_FIELDS = ("handle", "current", "versions", "backend",
                   "created_at", "updated_at")


def die(msg):
    sys.stderr.write("artifact_manifest.py: " + msg + "\n")
    sys.exit(1)


def manifest_path(manifest_dir, handle):
    # Lowercase-only HANDLE_RE: the filename is derived from the handle, and a
    # case-insensitive filesystem (macOS/Windows) would collide art:Foo/art:foo.
    # First char alnum forbids a leading '.'; the charset forbids '/', so path
    # traversal is impossible by construction.
    if not HANDLE_RE.match(handle):
        die("invalid handle: %r (want art:<id>, id = [a-z0-9][a-z0-9._-]{0,127})"
            % handle)
    return os.path.join(manifest_dir, handle[len("art:"):] + ".json")


def validate(rec, path):
    """Enforce every schema invariant; die naming the file and the violation."""
    def bad(reason):
        die("malformed manifest %s: %s -- repair or remove it" % (path, reason))

    if not isinstance(rec, dict):
        bad("top-level value is not an object")
    for field in REQUIRED_FIELDS:
        if field not in rec:
            bad("missing required field %r" % field)
    handle = rec["handle"]
    if not isinstance(handle, str) or not HANDLE_RE.match(handle):
        bad("invalid handle %r" % (handle,))
    expected = handle[len("art:"):] + ".json"
    if os.path.basename(path) != expected:
        bad("handle %r does not match filename (expected %s)" % (handle, expected))
    versions = rec["versions"]
    if not isinstance(versions, list) or not versions:
        bad("versions must be a non-empty list")
    for v in versions:
        if not isinstance(v, str) or not HASH_RE.match(v):
            bad("invalid version hash %r" % (v,))
    if len(set(versions)) != len(versions):
        bad("duplicate entries in versions")
    if rec["current"] not in versions:
        bad("current not in versions")
    backend = rec["backend"]
    if not isinstance(backend, str) or not BACKEND_RE.match(backend):
        bad("invalid backend name %r (want [a-z0-9][a-z0-9_-]{0,31})" % (backend,))
    for field in ("created_at", "updated_at"):
        if not isinstance(rec[field], int):
            bad("%s must be an integer epoch" % field)


def load(path):
    """Read + validate a manifest. None if absent; die (named) if malformed."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            rec = json.load(fh)
    except FileNotFoundError:
        return None
    except ValueError as exc:
        die("malformed manifest %s: invalid JSON (%s) -- repair or remove it"
            % (path, exc))
    except OSError as exc:
        die("cannot read %s: %s" % (path, exc))
    validate(rec, path)
    return rec


def atomic_write(path, rec):
    validate(rec, path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".manifest.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(rec, fh, indent=2, sort_keys=True, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def parse_kv(args):
    out = {}
    for arg in args:
        if "=" not in arg:
            die("expected key=value, got: " + arg)
        key, val = arg.split("=", 1)
        out[key] = val
    return out


def resolve_now(kv):
    """Integer epoch from now=<epoch> kv (testability) or wall clock."""
    if "now" in kv:
        try:
            return int(kv["now"])
        except ValueError:
            die("now must be an integer epoch: " + kv["now"])
    return int(time.time())


def check_hash(h):
    if not HASH_RE.match(h):
        die("invalid hash: %r (want sha256:<64-lowercase-hex>)" % (h,))


def cmd_create(manifest_dir, handle, h, kv):
    path = manifest_path(manifest_dir, handle)
    check_hash(h)
    if os.path.exists(path):
        die("manifest already exists for %s: %s (creation is explicit; use "
            "set-current to add a version)" % (handle, path))
    backend = kv.get("backend", "local")
    now = resolve_now(kv)
    rec = {"handle": handle, "current": h, "versions": [h],
           "backend": backend, "created_at": now, "updated_at": now}
    atomic_write(path, rec)


def cmd_get(manifest_dir, handle):
    rec = load(manifest_path(manifest_dir, handle))
    if rec is None:
        return
    json.dump(rec, sys.stdout, indent=2, sort_keys=True, ensure_ascii=False)
    sys.stdout.write("\n")


def cmd_current(manifest_dir, handle):
    rec = load(manifest_path(manifest_dir, handle))
    if rec is not None:
        print(rec["current"])


def cmd_versions(manifest_dir, handle):
    rec = load(manifest_path(manifest_dir, handle))
    if rec is None:
        return
    for v in rec["versions"]:
        print(v)


def cmd_set_current(manifest_dir, handle, h, kv):
    path = manifest_path(manifest_dir, handle)
    check_hash(h)
    rec = load(path)
    if rec is None:
        die("no manifest for %s (create it first)" % handle)
    # Append-only versions: a new hash is appended; repointing to an already-
    # recorded version moves `current` without a duplicate append.
    if h not in rec["versions"]:
        rec["versions"].append(h)
    rec["current"] = h
    rec["updated_at"] = resolve_now(kv)
    atomic_write(path, rec)


def cmd_set_backend(manifest_dir, handle, backend, kv):
    path = manifest_path(manifest_dir, handle)
    if not BACKEND_RE.match(backend):
        die("invalid backend name %r (want [a-z0-9][a-z0-9_-]{0,31})" % (backend,))
    rec = load(path)
    if rec is None:
        die("no manifest for %s (create it first)" % handle)
    rec["backend"] = backend
    rec["updated_at"] = resolve_now(kv)
    atomic_write(path, rec)


def iter_manifest_files(manifest_dir):
    if not os.path.isdir(manifest_dir):
        return
    for name in sorted(os.listdir(manifest_dir)):
        if name.endswith(".json"):
            yield os.path.join(manifest_dir, name)


def cmd_list(manifest_dir):
    for path in iter_manifest_files(manifest_dir):
        rec = load(path)  # dies (named) on any malformed member -- fail closed
        print(rec["handle"])


def cmd_referenced_hashes(manifest_dir):
    """Union of every hash in every manifest's versions (not just current --
    design par.9 version-awareness: an old version's blob must survive until
    that version is itself pruned). Consumed by gc as its blocking set; a
    malformed member dies (named) rather than shrinking the set."""
    hashes = set()
    for path in iter_manifest_files(manifest_dir):
        rec = load(path)
        hashes.update(rec["versions"])
    for h in sorted(hashes):
        print(h)


def main(argv):
    if len(argv) < 3 or argv[0] != "--manifest-dir":
        die("usage: artifact_manifest.py --manifest-dir <dir> "
            "<create|get|current|versions|set-current|set-backend|list|"
            "referenced-hashes> ...")
    manifest_dir = argv[1]
    cmd = argv[2]
    rest = argv[3:]
    if cmd == "create":
        if len(rest) < 2:
            die("create <handle> <hash> [backend=<name>] [now=<epoch>]")
        cmd_create(manifest_dir, rest[0], rest[1], parse_kv(rest[2:]))
    elif cmd == "get":
        if len(rest) != 1:
            die("get <handle>")
        cmd_get(manifest_dir, rest[0])
    elif cmd == "current":
        if len(rest) != 1:
            die("current <handle>")
        cmd_current(manifest_dir, rest[0])
    elif cmd == "versions":
        if len(rest) != 1:
            die("versions <handle>")
        cmd_versions(manifest_dir, rest[0])
    elif cmd == "set-current":
        if len(rest) < 2:
            die("set-current <handle> <hash> [now=<epoch>]")
        cmd_set_current(manifest_dir, rest[0], rest[1], parse_kv(rest[2:]))
    elif cmd == "set-backend":
        if len(rest) < 2:
            die("set-backend <handle> <backend> [now=<epoch>]")
        cmd_set_backend(manifest_dir, rest[0], rest[1], parse_kv(rest[2:]))
    elif cmd == "list":
        if rest:
            die("list takes no arguments")
        cmd_list(manifest_dir)
    elif cmd == "referenced-hashes":
        if rest:
            die("referenced-hashes takes no arguments")
        cmd_referenced_hashes(manifest_dir)
    else:
        die("unknown subcommand: " + cmd)


if __name__ == "__main__":
    main(sys.argv[1:])
