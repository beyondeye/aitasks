#!/usr/bin/env python3
"""atomic_write.py - temp-file + os.replace file writes (t1371).

A plain ``open(path, "w")`` truncates the target BEFORE any bytes are written,
so a concurrent reader can observe the file empty or half-written. That window
is not theoretical: ``ait board``'s trail discovery reads live task frontmatter,
and a scan racing ``ait artifact new`` saw the owning task file either cut
mid-YAML (``parse_frontmatter`` raises) or truncated to zero bytes (it returns
``None``). t1365 hardened that reader; this module closes the write side.

SCOPE -- reader-visible atomicity, NOT writer serialization. ``os.replace``
guarantees a reader sees either the whole old file or the whole new one. It does
NOT serialize a read-modify-write cycle: two concurrent mutations can each render
from the same old text, and the second replace silently discards the first.
Atomicity makes that loss clean rather than corrupt -- it does not prevent it.
A caller that read-modify-writes a shared file must hold its own mutex; ``ait
artifact`` / ``ait attach`` / ``ait fold`` run their whole transaction under the
global attach lock (``lib/attachment_lock.sh``).

Atomic *visibility*, not crash durability: there is no ``fsync``, matching
``gate_ledger``, ``attachment_meta``, ``config_utils`` and ``agent_marks``. A
crash between the write and the rename leaves the ORIGINAL file intact, which is
the property that matters for git-tracked task data.

Stdlib only, on purpose: ``frontmatter_patch.py`` is deliberately yaml-free (it
is line-based precisely to avoid a YAML round-trip), so it cannot import
``config_utils``, whose semantics this mirrors.

This module is the consolidation target for the framework's other open-coded
atomic writers -- t1281 tracks re-pointing them here. Until that lands this is an
ADDITIONAL implementation rather than a replacement, so treat the public API
(``atomic_write``, ``atomic_write_text``, ``prepare``, ``commit``,
``target_mode``, ``discard``) as stable.

Callers (t1379 routed the remaining task/plan-file writers here): ``board``'s
``Task.save`` and ``aitask_merge``, ``diffviewer.merge_engine.write_merged_plan``,
``brainstorm_session``, and ``frontmatter_patch``.

``lib/atomic_write.sh`` is the shell sibling, with the same contract and the
same ``resolve once -> stage beside the target -> rename`` shape; every shell
script that replaces a task or plan file routes through it. Its one extra
concern has no Python analogue: because bash disables ``errexit`` inside a
function whose status is being tested, its renderers must guard each fallible
command explicitly -- see the note at the top of that file. Keep the two in
step when changing the semantics here.
"""

import os
import stat
import tempfile
from os import replace as _os_replace

# Probed once at import: reading the umask requires os.umask(0) followed by a
# restore, which is process-global -- doing it per write could hand another
# thread a mode-0 window, and the Textual TUIs run worker threads. New files get
# 0o666 & ~umask, matching what open(path, "w") produced before writes became
# atomic.
_UMASK = os.umask(0)
os.umask(_UMASK)


def target_mode(path):
    """The mode a rewrite of ``path`` must land with.

    Its current mode when it exists, else the umask default. ``mkstemp`` creates
    0600, so without an explicit ``fchmod`` an atomic rewrite would silently
    downgrade a 0644 task file.
    """
    try:
        return stat.S_IMODE(os.stat(path).st_mode)
    except OSError:
        return 0o666 & ~_UMASK


def discard(tmp):
    """Best-effort removal of a staged temp file. Never raises."""
    try:
        os.unlink(tmp)
    except OSError:
        pass


def prepare(path, render):
    """Write ``render(fh)``'s output to a temp file beside ``path``; return it.

    ``path`` must already be resolved (see :func:`atomic_write`) -- prepare does
    not follow symlinks itself. Pairs with :func:`commit`; splitting prepare from
    commit lets a caller stage several files and make none of them visible until
    all have validated.

    The temp lives in the target's own directory, so the later rename is
    same-filesystem and cannot degrade into a non-atomic copy.
    """
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    mode = target_mode(path)
    fd, tmp = tempfile.mkstemp(
        dir=directory, prefix="." + os.path.basename(path) + ".", suffix=".tmp")
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            render(fh)
    except BaseException:
        discard(tmp)
        raise
    return tmp


def commit(tmp, path):
    """Move a prepared temp file into place. Never leaves the temp behind."""
    try:
        _os_replace(tmp, path)
    except BaseException:
        discard(tmp)
        raise


def atomic_write(path, render):
    """Atomically replace ``path`` with the text ``render(fh)`` writes.

    ``path`` is resolved with ``realpath`` first: ``open(path, "w")`` follows a
    symlink, but ``os.replace`` would replace the LINK itself, orphaning the real
    backing file while reads kept succeeding. ``aitasks/`` and ``aiplans/`` are
    symlinks into ``.aitask-data/`` on data-branch checkouts.
    """
    resolved = os.path.realpath(path)
    commit(prepare(resolved, render), resolved)


def atomic_write_text(path, text):
    """One-shot :func:`atomic_write` for callers that already have the text."""
    atomic_write(path, lambda fh: fh.write(text))
