#!/usr/bin/env python3
"""trail_discovery_cache - the on-disk, content-keyed cache behind
``trail_discovery.discover_trails`` (t2173_1).

A cold trail scan re-reads every active and archived task's frontmatter (most of
the archive decompressed from ``_b*/old*.tar.zst``) and spawns one
``artifact get`` per trail — seconds per open. This module lets a warm open cost
hashing plus re-parsing only what changed. Pure (no Textual), imported by
``trail_discovery`` only.

Two independent layers, one JSON file each, under
``${AIT_TRAIL_CACHE_DIR:-.aitask-cache/trail_discovery}`` (cwd-relative: cwd is
the project root, the module's invocation contract). ``AIT_TRAIL_CACHE=0``
disables both — nothing is read and nothing is written.

``owners.json`` — owner-record layer
    Key ``active:<path under the task dir>`` / ``archived:<path under the
    archived dir>``; value ``(sha256 of the unit's bytes, its owner records)``.
    A unit is one task file, one loose archived file or one archive bundle. The
    path is part of the key because the owner id comes from the file NAME; the
    content hash covers everything else a record says (archived is the key's
    layer, folded/status/artifacts are frontmatter). Files that own no trail —
    almost all of them — are cached as empty record lists. Entries the scan did
    not see are dropped on save, so a vanished file drops out.

    **Only clean units are cached**, and "clean" is decided by the caller from
    diagnostics collected for that unit on EVERY scan, whatever the scan's own
    ``scan_errors`` / ``unreadable`` arguments were. A best-effort scan must not
    be able to cache an empty result for a corrupt bundle that a later
    diagnostic scan would then hit and never report.

``docs.json`` — document layer
    Key the trail handle; value ``(blob, raw)`` where ``blob`` is the content
    address (``sha256:<hex>``) of the bytes ``artifact get`` wrote and ``raw``
    those bytes (as UTF-8 text) — never a parsed document. A lookup reads the
    handle's manifest and hits only when ALL of these hold: its ``current``
    equals ``blob``; ``raw`` hashes to that same address (so it IS the blob
    ``get`` verified, not merely an entry claiming to be); and ``raw``
    validates with ``FROZEN_SCHEMA``. The document is then parsed fresh from
    ``raw``, so a hit returns exactly what ``get`` + validation returns
    whenever the store can serve the blob, and a corrupted or forged entry —
    any shape — is a miss that falls back to the real ``get``. Failures are
    never stored: an unresolved artifact is retryable and stays fail-closed (a
    real ``get``, and the ``versions`` fallback, every time).

    The manifest is read through ``artifact_manifest.read_manifest``, the same
    invariants ``artifact get`` enforces, so a warmed cache never serves a
    document for a manifest ``get`` would reject. Its directory is used only
    for layouts this module can PROVE (``proven_manifest_dir``); anywhere else
    the layer is off — slower, never wrong.

    Stated boundary: a hit re-proves the manifest but not blob AVAILABILITY
    (backend activation, the store/cache lookup of ``artifact_resolve``). The
    entry is keyed by the content address of bytes ``get`` already verified, so
    the document served is the one ``get`` returns whenever it can resolve the
    blob; an unreachable store shows the last verified document rather than an
    error card.

Identities. Each layer file carries an identity; a mismatch discards the whole
layer. The owner identity hashes the sources of the record producers
(``trail_discovery``, ``archive_iter``, ``task_yaml``, ``topic_semantics``); the
doc identity hashes ``trail_schema``'s source, the schema file and
``trail_schema.VALIDATOR_REVISION``. PyYAML's version is deliberately left out:
the board can run on PyPy and ``ait trails`` on CPython with different builds,
and including it would make the two hosts thrash the cache.

**Both identities are frozen at import**, from the files the loaded modules came
from, and the schema used for validation is frozen with them (``FROZEN_SCHEMA``;
``trail_schema.load_schema`` would otherwise re-read the file on every call). A
board or ``ait trails`` left running across an upgrade therefore writes entries
only under its OWN import-time identity, which a process started on the new code
sees as a mismatch — it cannot populate entries the new implementation accepts.
Residual boundary: an upgrade landing during the import chain itself
(milliseconds) is not covered. The record producers read no data files, so their
source hash covers their whole behaviour.

Robustness. A torn, corrupt or foreign cache file is a miss, never an error; a
malformed entry is a miss. Saves are atomic (``atomic_write``), happen only when
the layer changed, and swallow ``OSError`` — the cache is optional, and the
board and ``ait trails`` may both write it (last writer wins; both are valid).
"""

import hashlib
import json
import os
import sys
import threading
from pathlib import Path

import archive_iter
import artifact_manifest
import task_yaml
import topic_semantics
import trail_schema
from atomic_write import atomic_write_text

#: On-disk format of both layer files.
FORMAT = 1
#: Bump when the owner records' meaning changes without a source change in the
#: hashed producers.
OWNER_LAYER_VERSION = 1

DEFAULT_CACHE_DIR = Path(".aitask-cache") / "trail_discovery"
OWNERS_FILE = "owners.json"
DOCS_FILE = "docs.json"


def _module_source(name):
    """The path of the file module ``name`` was loaded from.

    ``trail_discovery`` imports this module during its own import, so it is in
    ``sys.modules`` (partially initialised, ``__file__`` set) at that point; a
    standalone import of this module falls back to its sibling path."""
    module = sys.modules.get(name)
    path = getattr(module, "__file__", None)
    if path:
        return path
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        name + ".py")


def _digest(parts):
    """sha256 over labelled byte parts (labels keep a split point unambiguous)."""
    h = hashlib.sha256()
    for label, data in parts:
        h.update(label.encode("utf-8") + b"\0")
        h.update(str(len(data)).encode("ascii") + b"\0")
        h.update(data)
    return h.hexdigest()


def _freeze_owner_identity():
    parts = [("version", str(OWNER_LAYER_VERSION).encode("ascii"))]
    for name in ("trail_discovery", "archive_iter", "task_yaml",
                 "topic_semantics"):
        with open(_module_source(name), "rb") as fh:
            parts.append((name, fh.read()))
    return _digest(parts)


def _freeze_doc_layer():
    with open(_module_source("trail_schema"), "rb") as fh:
        source = fh.read()
    with open(trail_schema.DEFAULT_SCHEMA_PATH, "rb") as fh:
        schema_bytes = fh.read()
    schema = trail_schema.parse_schema(schema_bytes,
                                       trail_schema.DEFAULT_SCHEMA_PATH)
    identity = _digest([
        ("trail_schema", source),
        ("schema", schema_bytes),
        ("revision", str(trail_schema.VALIDATOR_REVISION).encode("ascii")),
    ])
    return identity, schema


# Frozen ONCE, here, at import (see the module docstring). A source that cannot
# be read disables its layer; a broken schema leaves FROZEN_SCHEMA None, so
# validation falls back to load_schema and fails exactly as it did uncached.
try:
    OWNER_IDENTITY = _freeze_owner_identity()
except OSError:
    OWNER_IDENTITY = None
try:
    DOC_IDENTITY, FROZEN_SCHEMA = _freeze_doc_layer()
except (OSError, ValueError, RuntimeError):
    DOC_IDENTITY, FROZEN_SCHEMA = None, None


def owner_identity():
    """The owner layer's import-time identity (None ⇒ layer off)."""
    return OWNER_IDENTITY


def doc_identity():
    """The doc layer's import-time identity (None ⇒ layer off)."""
    return DOC_IDENTITY


def cache_dir():
    """The cache directory, read from the environment per call; None when
    ``AIT_TRAIL_CACHE=0`` disables the cache."""
    if os.environ.get("AIT_TRAIL_CACHE", "") == "0":
        return None
    return Path(os.environ.get("AIT_TRAIL_CACHE_DIR") or DEFAULT_CACHE_DIR)


def proven_manifest_dir():
    """The artifact manifest directory, for the two layouts provable without
    git; None for every other layout (the doc layer is then off).

    Mirrors ``_ait_detect_data_worktree`` (lib/task_utils.sh) +
    ``artifact_manifest_dir`` (lib/artifact_manifest.sh): rung 1 — a
    ``.aitask-data/.git`` dir or file in cwd → ``.aitask-data``; and a primary
    legacy checkout — ``.git`` is a directory in cwd (so cwd is its own
    toplevel and main worktree, and rungs 2-3 find no ``.aitask-data/.git``
    either) → ``.``. A ``.git`` FILE (linked worktree, ``--separate-git-dir``,
    absorbed submodule) or an explicit ``GIT_DIR`` / ``GIT_WORK_TREE`` is not
    provable here, and neither is no repository at all."""
    data_git = Path(".aitask-data") / ".git"
    if data_git.is_dir() or data_git.is_file():
        return os.path.join(".aitask-data", "artifacts", "manifests")
    if os.environ.get("GIT_DIR") or os.environ.get("GIT_WORK_TREE"):
        return None
    if Path(".git").is_dir():
        return os.path.join(".", "artifacts", "manifests")
    return None


def manifest_current(handle, manifest_dir=None):
    """The handle's manifest ``current``, or None when the manifest is absent,
    unreadable or violates any invariant ``artifact get`` enforces."""
    manifest_dir = manifest_dir or proven_manifest_dir()
    if manifest_dir is None:
        return None
    if not isinstance(handle, str) or not artifact_manifest.HANDLE_RE.match(
            handle):
        return None
    try:
        rec = artifact_manifest.read_manifest(
            artifact_manifest.manifest_path(manifest_dir, handle))
    except artifact_manifest.ManifestError:
        return None
    return rec["current"] if rec is not None else None


def _load_entries(path, identity):
    """``(entries, ok)``: the layer's entries, and whether the file on disk was
    an acceptable one (absent counts as acceptable — there is nothing to fix)."""
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return {}, True
    except OSError:
        return {}, False
    try:
        data = json.loads(raw)
    except ValueError:
        return {}, False
    if (not isinstance(data, dict) or data.get("format") != FORMAT
            or data.get("identity") != identity
            or not isinstance(data.get("entries"), dict)):
        return {}, False
    return data["entries"], True


def _save_entries(path, identity, entries):
    text = json.dumps({"format": FORMAT, "identity": identity,
                       "entries": entries},
                      sort_keys=True, separators=(",", ":"))
    try:
        atomic_write_text(str(path), text + "\n")
    except OSError:
        pass


class _Layer:
    """Shared load/prune/save mechanics: ``_kept`` collects the entries this
    scan confirmed or produced; ``save`` writes them when they differ from what
    was loaded (or the file needed replacing)."""

    FILE = ""

    def __init__(self, identity, enabled):
        self._identity = identity
        directory = cache_dir()
        self.enabled = bool(enabled and identity and directory is not None)
        self._path = directory / self.FILE if self.enabled else None
        self._loaded = {}
        self._loaded_ok = True
        if self.enabled:
            self._loaded, self._loaded_ok = _load_entries(self._path, identity)
        self._kept = {}
        self._lock = threading.Lock()

    def save(self):
        if not self.enabled:
            return
        with self._lock:
            kept = dict(self._kept)
        if self._loaded_ok and kept == self._loaded:
            return
        _save_entries(self._path, self._identity, kept)


def _valid_record(rec):
    return (isinstance(rec, list) and len(rec) == 5
            and isinstance(rec[0], str) and isinstance(rec[1], str)
            and isinstance(rec[2], bool) and isinstance(rec[3], bool)
            and isinstance(rec[4], str))


class OwnerCache(_Layer):
    """The owner-record layer. Records are plain tuples
    ``(handle, owner_id, owner_archived, owner_folded, name)``; the caller
    builds fresh ``TrailInfo`` objects from them on every lookup."""

    FILE = OWNERS_FILE

    def __init__(self):
        super().__init__(OWNER_IDENTITY, True)

    @classmethod
    def open(cls):
        return cls()

    def lookup(self, key, sha):
        """The cached records for unit ``key`` with content hash ``sha``, or
        None (miss). A hit keeps the entry for this scan's save."""
        if not self.enabled:
            return None
        entry = self._loaded.get(key)
        if not (isinstance(entry, dict) and entry.get("sha") == sha
                and isinstance(entry.get("records"), list)
                and all(_valid_record(r) for r in entry["records"])):
            return None
        with self._lock:
            self._kept[key] = entry
        return [tuple(r) for r in entry["records"]]

    def store(self, key, sha, records):
        """Cache a CLEAN unit's records (the caller decides cleanliness)."""
        if not self.enabled:
            return
        entry = {"sha": sha, "records": [
            [str(h), str(o), bool(a), bool(f), str(n)]
            for h, o, a, f, n in records]}
        with self._lock:
            self._kept[key] = entry


class DocCache(_Layer):
    """The document layer (see the module docstring). Thread-safe: the cold
    path loads several handles in parallel."""

    FILE = DOCS_FILE

    def __init__(self):
        self._manifest_dir = proven_manifest_dir()
        super().__init__(DOC_IDENTITY, self._manifest_dir is not None)

    @classmethod
    def open(cls):
        return cls()

    def lookup(self, handle):
        """The document for ``handle``, parsed fresh from the cached blob, or
        None (miss).

        Reads the manifest first — the caller runs this inside the per-handle
        read lock, before the read is sequenced. Then proves the entry: its
        blob must be the manifest's ``current``, its bytes must hash to it, and
        they must validate (module docstring) — any failure is a miss."""
        if not self.enabled:
            return None
        current = manifest_current(handle, self._manifest_dir)
        entry = self._loaded.get(handle)
        if (current is None or not isinstance(entry, dict)
                or entry.get("blob") != current
                or not isinstance(entry.get("raw"), str)):
            return None
        try:
            raw = entry["raw"].encode("utf-8")
        except UnicodeError:          # a lone surrogate: not a blob's text
            return None
        if "sha256:" + hashlib.sha256(raw).hexdigest() != current:
            return None
        try:
            doc = trail_schema.load_trail(raw, schema=FROZEN_SCHEMA)
        except (trail_schema.TrailValidationError, RecursionError):
            return None
        with self._lock:
            self._kept[handle] = entry
        return doc

    def store(self, handle, blob_hash, raw):
        """Cache the bytes ``raw`` of blob ``blob_hash``, which ``get`` wrote
        and which validated (the caller stores only successful loads)."""
        if not self.enabled or not blob_hash or not isinstance(raw, bytes):
            return
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return
        with self._lock:
            self._kept[handle] = {"blob": blob_hash, "raw": text}
