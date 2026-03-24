"""archive_iter.py - Python archive iteration for numbered archive scheme.

Provides iterator functions that yield (filename, text_content) tuples from
numbered _bN/oldM.tar.gz archives, legacy old.tar.gz, and loose markdown files.

Usage:
    from archive_iter import iter_all_archived_markdown
    for name, content in iter_all_archived_markdown(Path("aitasks/archived")):
        process(name, content)
"""

import os
import re
import tarfile
from pathlib import Path
from typing import Iterable, Tuple


def archive_path_for_id(task_id: int, archived_dir: Path) -> Path:
    """Compute the numbered archive path for a given task ID."""
    bundle = task_id // 100
    dir_num = bundle // 10
    return archived_dir / f"_b{dir_num}" / f"old{bundle}.tar.gz"


def iter_numbered_archives(archived_dir: Path) -> Iterable[Tuple[str, str]]:
    """Yield (filename, text_content) from all numbered archives."""
    for bdir in sorted(archived_dir.glob("_b*")):
        if not bdir.is_dir():
            continue
        for archive in sorted(bdir.glob("old*.tar.gz")):
            yield from _iter_single_archive(archive)


def iter_legacy_archive(archived_dir: Path) -> Iterable[Tuple[str, str]]:
    """Yield (filename, text_content) from legacy old.tar.gz if it exists."""
    legacy = archived_dir / "old.tar.gz"
    if legacy.exists():
        yield from _iter_single_archive(legacy)


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
) -> Iterable[Tuple[str, str]]:
    """Yield (filename, text_content) from loose files + numbered archives.

    Scans in order: loose parent files, loose child files (in subdirs),
    then numbered tar.gz archives. Does NOT scan legacy old.tar.gz.
    """
    if archived_dir.exists():
        # Loose parent tasks
        for path in sorted(archived_dir.glob("t*_*.md")):
            if _is_child_filename(path.name):
                continue
            try:
                yield path.name, path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
        # Loose child tasks in subdirectories
        for path in sorted(archived_dir.glob("t*/t*_*_*.md")):
            try:
                yield path.name, path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
    # Numbered archives only (no legacy)
    yield from iter_numbered_archives(archived_dir)


def iter_archived_frontmatter(
    archived_dir: Path,
    parse_fn,
) -> Iterable[Tuple[str, dict]]:
    """Yield (filename, metadata_dict) using parse_fn on frontmatter only.

    parse_fn should accept a string (full file text) and return a dict
    of metadata (the YAML frontmatter). This avoids loading full body content.
    """
    for name, text in iter_all_archived_markdown(archived_dir):
        try:
            metadata = parse_fn(text)
            if metadata is not None:
                yield name, metadata
        except Exception:
            continue


def _is_child_filename(name: str) -> bool:
    """Check if filename matches child task pattern t<N>_<M>_*.md."""
    return bool(re.match(r"t\d+_\d+_", name))


def _iter_single_archive(archive_path: Path) -> Iterable[Tuple[str, str]]:
    """Yield (filename, text_content) for .md files in a single tar.gz."""
    try:
        with tarfile.open(archive_path, "r:gz") as tf:
            for member in tf.getmembers():
                if not member.isfile() or not member.name.endswith(".md"):
                    continue
                extracted = tf.extractfile(member)
                if extracted is None:
                    continue
                raw = extracted.read()
                text = raw.decode("utf-8", errors="replace")
                yield os.path.basename(member.name), text
    except (tarfile.TarError, OSError):
        return
