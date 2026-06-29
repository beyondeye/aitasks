#!/usr/bin/env python3
"""attachment_meta.py - per-blob attachment metadata ledger (t1030_2).

Canonical refcount ledger: ONE JSON file per blob at
<meta-dir>/<first2hex>/<rest62hex>.json. NOT a single global index.json.

Schema (blob-intrinsic fields + the refcount set only; per-task display fields
such as name/added_at stay authoritative in the task frontmatter, since the same
bytes can be attached to two tasks under different names):

    {"hash": "sha256:<hex>", "refs": ["1030_2", "42"],
     "mime": "image/png", "size": 12345, "backend": "local"}

LOCK-FREE PRIMITIVE: this script NEVER takes a lock -- callers own concurrency.
`ait attach add/rm` run the whole transaction under the single global
attachments/.attach.lock; standalone/administrative callers (t1030_3 gc/fold)
MUST wrap any MUTATION subcommand (incref/decref/rebind) in that same global
lock. Read-only subcommands (refs/zero-refcount) are safe lock-free because every
write is atomic (temp + os.replace). zero-refcount output is ADVISORY -- a
destructive consumer (gc/delete) MUST re-acquire the global lock and re-read refs
to confirm it is still empty before deleting the blob+meta.

incref/decref are set-based and idempotent: re-applying after a cross-host
task_sync rebase is safe (refs is a set, not a counter).
"""

import json
import os
import re
import sys
import tempfile

HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def die(msg):
    sys.stderr.write("attachment_meta.py: " + msg + "\n")
    sys.exit(1)


def meta_path(meta_dir, h):
    if not HASH_RE.match(h):
        die("invalid hash: " + h)
    hex_ = h[len("sha256:"):]
    return os.path.join(meta_dir, hex_[:2], hex_[2:] + ".json")


def load(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return None
    except (ValueError, OSError) as exc:
        die("cannot read %s: %s" % (path, exc))


def atomic_write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".meta.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True, ensure_ascii=False)
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


def cmd_incref(meta_dir, h, task, kv):
    path = meta_path(meta_dir, h)
    rec = load(path)
    if rec is None:
        rec = {"hash": h, "refs": [], "mime": None, "size": None, "backend": None}
    # Blob-intrinsic fields: set on first write, verify-don't-overwrite after.
    for field in ("mime", "size", "backend"):
        if field not in kv:
            continue
        new = kv[field]
        if field == "size":
            try:
                new = int(new)
            except ValueError:
                die("size must be an integer: " + kv[field])
        cur = rec.get(field)
        if cur is None:
            rec[field] = new
        elif cur != new:
            die("blob-intrinsic %s mismatch for %s: stored=%r new=%r "
                "(hash collision or caller bug)" % (field, h, cur, new))
    refs = set(rec.get("refs") or [])
    refs.add(task)
    rec["refs"] = sorted(refs)
    atomic_write(path, rec)


def cmd_decref(meta_dir, h, task):
    path = meta_path(meta_dir, h)
    rec = load(path)
    if rec is None:
        return  # nothing to do (idempotent)
    refs = set(rec.get("refs") or [])
    refs.discard(task)
    rec["refs"] = sorted(refs)
    atomic_write(path, rec)


def cmd_refs(meta_dir, h):
    rec = load(meta_path(meta_dir, h))
    if rec is None:
        return
    for task in sorted(set(rec.get("refs") or [])):
        print(task)


def iter_meta_files(meta_dir):
    if not os.path.isdir(meta_dir):
        return
    for shard in sorted(os.listdir(meta_dir)):
        shard_dir = os.path.join(meta_dir, shard)
        if len(shard) != 2 or not os.path.isdir(shard_dir):
            continue
        for name in sorted(os.listdir(shard_dir)):
            if name.endswith(".json"):
                yield os.path.join(shard_dir, name)


def cmd_zero_refcount(meta_dir):
    for path in iter_meta_files(meta_dir):
        rec = load(path)
        if rec is None:
            continue
        if not (rec.get("refs") or []):
            print(rec.get("hash") or "")


def cmd_rebind(meta_dir, old_task, new_task):
    for path in iter_meta_files(meta_dir):
        rec = load(path)
        if rec is None:
            continue
        refs = set(rec.get("refs") or [])
        if old_task in refs:
            refs.discard(old_task)
            refs.add(new_task)
            rec["refs"] = sorted(refs)
            atomic_write(path, rec)


def main(argv):
    if len(argv) < 3 or argv[0] != "--meta-dir":
        die("usage: attachment_meta.py --meta-dir <dir> "
            "<incref|decref|refs|zero-refcount|rebind> ...")
    meta_dir = argv[1]
    cmd = argv[2]
    rest = argv[3:]
    if cmd == "incref":
        if len(rest) < 2:
            die("incref <hash> <task> [k=v ...]")
        cmd_incref(meta_dir, rest[0], rest[1], parse_kv(rest[2:]))
    elif cmd == "decref":
        if len(rest) != 2:
            die("decref <hash> <task>")
        cmd_decref(meta_dir, rest[0], rest[1])
    elif cmd == "refs":
        if len(rest) != 1:
            die("refs <hash>")
        cmd_refs(meta_dir, rest[0])
    elif cmd == "zero-refcount":
        if rest:
            die("zero-refcount takes no arguments")
        cmd_zero_refcount(meta_dir)
    elif cmd == "rebind":
        if len(rest) != 2:
            die("rebind <old_task> <new_task>")
        cmd_rebind(meta_dir, rest[0], rest[1])
    else:
        die("unknown subcommand: " + cmd)


if __name__ == "__main__":
    main(sys.argv[1:])
