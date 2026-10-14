"""archive_iter.py - Python archive iteration for numbered archive scheme.

Provides iterator functions that yield (filename, text_content) tuples from
numbered _bN/oldM.tar.zst archives, legacy old.tar.zst, and loose markdown files.

Usage:
    from archive_iter import iter_all_archived_markdown
    for name, content in iter_all_archived_markdown(Path("aitasks/archived")):
        process(name, content)

Failure reporting is opt-in. By default every reader is best-effort: a
directory that cannot be listed, an unreadable loose file, a corrupt or
truncated bundle, a missing ``zstd`` binary and an unparseable frontmatter are
skipped without a trace, so "no record" and "could not read" look alike. A
caller that must tell them apart (a scan that reports itself complete, t1957_3)
passes a list as the keyword-only ``errors`` argument; every failure that could
hide a record is then appended to it as ``"<path>: <reason>"``. Leaving
``errors`` unset keeps every reader best-effort.
"""

import fnmatch
import os
import re
import subprocess
import tarfile
from pathlib import Path
from typing import Iterable, Tuple

#: A task file name (``t42_x.md``, ``t42_3_x.md``) — only these are reported
#: when their frontmatter does not parse; any other ``.md`` is not a task.
_TASK_NAME_RE = re.compile(r"t\d+(?:_\d+)?_")


def _note(errors, path, reason) -> None:
    """Record one read failure when the caller asked for them (once: several
    globs list the same directory)."""
    if errors is not None:
        entry = f"{path}: {reason}"
        if entry not in errors:
            errors.append(entry)


def _scan_dir(directory: Path, errors) -> list:
    """The entries of ``directory``: ``[]`` when it does not exist, reported
    when it exists but cannot be listed."""
    try:
        with os.scandir(directory) as entries:
            return list(entries)
    except (FileNotFoundError, NotADirectoryError):
        return []
    except OSError as exc:
        _note(errors, directory, exc)
        return []


def _entry_is_dir(entry, errors) -> bool:
    try:
        return entry.is_dir()
    except OSError as exc:
        _note(errors, entry.path, exc)
        return False


def checked_glob(directory: Path, pattern: str,
                 errors: list | None = None) -> list:
    """``sorted(directory.glob(pattern))`` for a ``<file>`` or
    ``<dir>/<file>`` pattern.

    ``Path.glob`` swallows a ``PermissionError``, so a directory that exists
    but cannot be listed matches nothing — exactly like an empty one. With
    ``errors``, every directory the pattern has to enter is listed explicitly
    and one that cannot be listed is reported; an absent directory is still
    just empty. Without ``errors`` this IS ``Path.glob``."""
    if errors is None:
        return sorted(directory.glob(pattern))
    dir_pattern, _, file_pattern = pattern.rpartition("/")
    parents = [directory]
    if dir_pattern:
        parents = [Path(entry.path) for entry in _scan_dir(directory, errors)
                   if fnmatch.fnmatchcase(entry.name, dir_pattern)
                   and _entry_is_dir(entry, errors)]
    matches = []
    for parent in parents:
        matches.extend(Path(entry.path) for entry in _scan_dir(parent, errors)
                       if fnmatch.fnmatchcase(entry.name, file_pattern))
    return sorted(matches)


def _checked_exists(path: Path, errors) -> bool:
    """``path.exists()``; with ``errors``, a path whose existence cannot be
    determined (an unsearchable parent directory) is reported, not absent."""
    if errors is None:
        return path.exists()
    try:
        os.stat(path)
        return True
    except (FileNotFoundError, NotADirectoryError):
        return False
    except OSError as exc:
        _note(errors, path, exc)
        return False


def archive_path_for_id(task_id: int, archived_dir: Path) -> Path:
    """Compute the numbered archive path for a given task ID."""
    bundle = task_id // 100
    dir_num = bundle // 10
    return archived_dir / f"_b{dir_num}" / f"old{bundle}.tar.zst"


def find_archived_markdown_by_id(
    task_id: str,
    archived_dir: Path,
    *,
    errors: list | None = None,
) -> Tuple[str, str] | None:
    """Return ``(filename, text)`` for one archived task ID, if present.

    The lookup mirrors the shell resolver's precedence: loose archived files,
    then the numbered bundle for the parent ID, then legacy ``old.tar.*``. It
    avoids scanning every numbered bundle for each lookup.

    ``None`` with ``errors`` still empty means the task is not archived; with
    ``errors`` non-empty it means the lookup could not rule that out.
    """
    normalized = str(task_id).lstrip("t")
    match = re.fullmatch(r"(\d+)(?:_(\d+))?", normalized)
    if not match:
        return None
    parent_id = int(match.group(1))

    if errors is not None or archived_dir.exists():
        if match.group(2):
            child_dir = archived_dir / f"t{match.group(1)}"
            loose = checked_glob(child_dir, f"t{normalized}_*.md", errors)
        else:
            loose = [
                path for path in checked_glob(archived_dir,
                                              f"t{normalized}_*.md", errors)
                if not _is_child_filename(path.name)
            ]
        for path in loose:
            try:
                return path.name, path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                _note(errors, path, exc)
                continue

    zst_path = archive_path_for_id(parent_id, archived_dir)
    archive_paths = [zst_path, zst_path.with_suffix("").with_suffix(".tar.gz")]
    for archive_path in archive_paths:
        if not _checked_exists(archive_path, errors):
            continue
        found = _find_in_archive_iter(
            normalized, _iter_single_archive(archive_path, errors=errors))
        if found:
            return found

    return _find_in_archive_iter(
        normalized, iter_legacy_archive(archived_dir, errors=errors))


def iter_numbered_archives(
    archived_dir: Path,
    *,
    errors: list | None = None,
) -> Iterable[Tuple[str, str]]:
    """Yield (filename, text_content) from all numbered archives."""
    # Primary: .tar.zst
    zst_archives = checked_glob(archived_dir, "_b*/old*.tar.zst", errors)
    # Fallback: .tar.gz (only those without a .tar.zst counterpart)
    gz_archives = checked_glob(archived_dir, "_b*/old*.tar.gz", errors)

    seen_stems = set()
    for archive in zst_archives:
        seen_stems.add(archive.with_suffix("").with_suffix(""))  # strip .tar.zst
        yield from _iter_single_archive(archive, errors=errors)
    for archive in gz_archives:
        stem = archive.with_suffix("").with_suffix("")  # strip .tar.gz
        if stem not in seen_stems:
            yield from _iter_single_archive(archive, errors=errors)


def iter_legacy_archive(
    archived_dir: Path,
    *,
    errors: list | None = None,
) -> Iterable[Tuple[str, str]]:
    """Yield (filename, text_content) from legacy old.tar.zst/old.tar.gz if it exists."""
    zst_path = archived_dir / "old.tar.zst"
    gz_path = archived_dir / "old.tar.gz"
    if _checked_exists(zst_path, errors):
        yield from _iter_single_archive(zst_path, errors=errors)
    elif _checked_exists(gz_path, errors):
        yield from _iter_single_archive(gz_path, errors=errors)


def iter_all_archived_tar_files(
    archived_dir: Path,
) -> Iterable[Tuple[str, str]]:
    """Yield (filename, text_content) from all archives (numbered + legacy).

    This is the direct replacement for the ARCHIVE_TAR block in
    aitask_stats.py iter_archived_markdown_files().
    """
    yield from iter_numbered_archives(archived_dir)
    yield from iter_legacy_archive(archived_dir)


def iter_all_archived_markdown(
    archived_dir: Path,
    *,
    errors: list | None = None,
) -> Iterable[Tuple[str, str]]:
    """Yield (filename, text_content) from loose files + numbered archives.

    Scans in order: loose parent files, loose child files (in subdirs),
    then numbered tar.gz archives. Does NOT scan legacy old.tar.gz.
    """
    if errors is not None or archived_dir.exists():
        # Loose parent tasks
        for path in checked_glob(archived_dir, "t*_*.md", errors):
            if _is_child_filename(path.name):
                continue
            try:
                yield path.name, path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                _note(errors, path, exc)
                continue
        # Loose child tasks in subdirectories
        for path in checked_glob(archived_dir, "t*/t*_*_*.md", errors):
            try:
                yield path.name, path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                _note(errors, path, exc)
                continue
    # Numbered archives only (no legacy)
    yield from iter_numbered_archives(archived_dir, errors=errors)


def iter_archived_frontmatter(
    archived_dir: Path,
    parse_fn,
    *,
    errors: list | None = None,
) -> Iterable[Tuple[str, dict]]:
    """Yield (filename, metadata_dict) using parse_fn on frontmatter only.

    parse_fn should accept a string (full file text) and return a dict
    of metadata (the YAML frontmatter). This avoids loading full body content.

    With ``errors``, a task-named file whose ``parse_fn`` raises or returns
    anything but a dict is reported (a non-dict that is not ``None`` is still
    yielded, as before).
    """
    for name, text in iter_all_archived_markdown(archived_dir, errors=errors):
        try:
            metadata = parse_fn(text)
        except Exception:
            metadata = None
        if not isinstance(metadata, dict) and _TASK_NAME_RE.match(name):
            _note(errors, name, "unparseable frontmatter")
        if metadata is not None:
            yield name, metadata


def _is_child_filename(name: str) -> bool:
    """Check if filename matches child task pattern t<N>_<M>_*.md."""
    return bool(re.match(r"t\d+_\d+_", name))


def _filename_matches_task_id(name: str, task_id: str) -> bool:
    if "_" in task_id:
        return bool(re.match(rf"^t{re.escape(task_id)}_", name))
    return (
        bool(re.match(rf"^t{re.escape(task_id)}_", name))
        and not _is_child_filename(name)
    )


def _find_in_archive_iter(
    task_id: str,
    entries: Iterable[Tuple[str, str]],
) -> Tuple[str, str] | None:
    for filename, text in entries:
        if _filename_matches_task_id(filename, task_id):
            return filename, text
    return None


def _iter_single_archive(
    archive_path: Path,
    *,
    errors: list | None = None,
) -> Iterable[Tuple[str, str]]:
    """Yield (filename, text_content) for .md files in a single archive.

    With ``errors``, a failure to open or read the archive is reported, and so
    is a non-zero ``zstd`` exit after a complete read: a truncated stream can
    end on a tar block boundary, which tarfile takes for a clean end of archive.
    The exit status is checked only when the read ran to completion — a caller
    that stops early (``find_archived_markdown_by_id``) closes the pipe on a
    still-running ``zstd``, and the SIGPIPE that follows is not a failure.
    """
    try:
        if archive_path.name.endswith(".tar.zst"):
            proc = subprocess.Popen(
                ["zstd", "-dc", str(archive_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            completed = False
            try:
                with tarfile.open(fileobj=proc.stdout, mode="r|") as tf:
                    for member in tf:
                        if not member.isfile() or not member.name.endswith(".md"):
                            continue
                        extracted = tf.extractfile(member)
                        if extracted is None:
                            continue
                        text = extracted.read().decode("utf-8", errors="replace")
                        yield os.path.basename(member.name), text
                completed = True
            finally:
                if completed and errors is not None:
                    # Drain the tar padding: closing the pipe on a zstd that is
                    # still writing it would fail a clean read with EPIPE.
                    try:
                        while proc.stdout.read(65536):
                            pass
                    except OSError:
                        pass
                proc.stdout.close()
                returncode = proc.wait()
                if completed and returncode != 0:
                    _note(errors, archive_path, f"zstd exited {returncode}")
        else:
            with tarfile.open(archive_path, "r:gz") as tf:
                for member in tf.getmembers():
                    if not member.isfile() or not member.name.endswith(".md"):
                        continue
                    extracted = tf.extractfile(member)
                    if extracted is None:
                        continue
                    text = extracted.read().decode("utf-8", errors="replace")
                    yield os.path.basename(member.name), text
    except (tarfile.TarError, OSError, subprocess.SubprocessError,
            EOFError) as exc:
        # EOFError: a truncated .tar.gz — gzip raises it and tarfile does not
        # convert it to a TarError.
        _note(errors, archive_path, exc)
        return
