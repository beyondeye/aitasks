"""history_data.py - Data layer for completed task history in codebrowser.

Provides dataclasses and functions for loading, indexing, and navigating
archived/completed tasks, their commits, and associated plan files.
"""

import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

# Import from sibling directories
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "board"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from task_yaml import parse_frontmatter
from archive_iter import iter_all_archived_markdown, iter_archived_frontmatter


@dataclass
class CompletedTask:
    task_id: str  # e.g. "219" or "401_1"
    name: str  # e.g. "rename_aitaskpickremote"
    issue_type: str
    labels: list
    priority: str
    effort: str
    commit_date: str  # ISO format from git log
    commit_hash: str  # short hash of most recent commit
    file_source: str  # "loose" or "tar"
    metadata: dict  # full frontmatter dict


@dataclass
class TaskCommitInfo:
    hash: str
    message: str
    date: str
    affected_files: List[str]


@dataclass
class PlatformInfo:
    platform: str  # "github", "gitlab", "bitbucket"
    base_url: str  # e.g. "https://github.com/owner/repo"
    commit_url_template: str  # e.g. "https://github.com/owner/repo/commit/{hash}"


def _extract_metadata(text: str) -> Optional[dict]:
    """Extract frontmatter dict from task file text."""
    result = parse_frontmatter(text)
    if result is None:
        return None
    return result[0]


def _extract_task_id_from_filename(filename: str) -> Optional[str]:
    """Extract task ID from filename like t219_foo.md or t401_1_bar.md."""
    m = re.match(r"t(\d+(?:_\d+)?)_", filename)
    return m.group(1) if m else None


def _extract_name_from_filename(filename: str) -> str:
    """Extract descriptive name from filename, removing t<id>_ prefix and .md suffix."""
    name = re.sub(r"^t\d+(?:_\d+)?_", "", filename)
    return name.removesuffix(".md")


def load_task_index(project_root: Path) -> List[CompletedTask]:
    """Build an index of completed tasks from git log + archived metadata.

    Returns list of CompletedTask sorted by most recent commit date descending.
    """
    archived_dir = project_root / "aitasks" / "archived"

    # Step 1: Get all task-related commits from git log
    commit_map: dict = {}  # task_id -> (hash, date, message)
    try:
        result = subprocess.run(
            ["git", "log", "--all", "--grep=(t", "--format=%H %aI %s"],
            capture_output=True,
            text=True,
            cwd=project_root,
        )
        if result.returncode == 0:
            task_id_re = re.compile(r"\(t(\d+(?:_\d+)?)\)")
            for line in result.stdout.strip().splitlines():
                if not line:
                    continue
                parts = line.split(" ", 2)
                if len(parts) < 3:
                    continue
                hash_val, date_val, msg = parts
                for match in task_id_re.finditer(msg):
                    tid = match.group(1)
                    if tid not in commit_map or date_val > commit_map[tid][1]:
                        commit_map[tid] = (hash_val[:12], date_val, msg)
    except (OSError, subprocess.SubprocessError):
        pass

    # Step 2: Scan archived frontmatter
    meta_map: dict = {}  # task_id -> (metadata, file_source)
    # Loose + tar files via consolidated iterator
    for filename, metadata in iter_archived_frontmatter(archived_dir, _extract_metadata):
        tid = _extract_task_id_from_filename(filename)
        if tid is not None:
            meta_map[tid] = (metadata, "loose")

    # Step 3: Merge — only tasks with both commit info and metadata
    tasks = []
    for tid, (hash_val, date_val, msg) in commit_map.items():
        if tid not in meta_map:
            continue
        metadata, file_source = meta_map[tid]
        filename_match = None
        for fn, _ in iter_all_archived_markdown(archived_dir):
            if _extract_task_id_from_filename(fn) == tid:
                filename_match = fn
                break
        name = _extract_name_from_filename(filename_match) if filename_match else tid
        tasks.append(
            CompletedTask(
                task_id=tid,
                name=name,
                issue_type=metadata.get("issue_type", ""),
                labels=metadata.get("labels", []),
                priority=metadata.get("priority", ""),
                effort=metadata.get("effort", ""),
                commit_date=date_val,
                commit_hash=hash_val,
                file_source=file_source,
                metadata=metadata,
            )
        )

    # Step 4: Sort by commit date descending
    tasks.sort(key=lambda t: t.commit_date, reverse=True)
    return tasks


def load_task_content(project_root: Path, task_id: str) -> Optional[str]:
    """Load full markdown content for a completed task.

    Checks loose files first, then tar archives.
    """
    archived_dir = project_root / "aitasks" / "archived"
    is_child = "_" in task_id

    if is_child:
        parent_id = task_id.split("_")[0]
        # Check loose child files
        child_dir = archived_dir / f"t{parent_id}"
        if child_dir.exists():
            for path in child_dir.glob(f"t{task_id}_*.md"):
                try:
                    return path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
    else:
        # Check loose parent files
        for path in archived_dir.glob(f"t{task_id}_*.md"):
            try:
                return path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

    # Fall back to tar archives
    for filename, content in iter_all_archived_markdown(archived_dir):
        tid = _extract_task_id_from_filename(filename)
        if tid == task_id:
            return content

    return None


def load_plan_content(project_root: Path, task_id: str) -> Optional[str]:
    """Load associated plan file content for a completed task.

    Checks loose files in aiplans/archived/ first, then tar archives.
    """
    archived_plans = project_root / "aiplans" / "archived"
    is_child = "_" in task_id

    if is_child:
        parent_id = task_id.split("_")[0]
        plan_dir = archived_plans / f"p{parent_id}"
        if plan_dir.exists():
            for path in plan_dir.glob(f"p{task_id}_*.md"):
                try:
                    return path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
    else:
        for path in archived_plans.glob(f"p{task_id}_*.md"):
            try:
                return path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

    return None


def load_completed_tasks_chunk(
    task_index: List[CompletedTask], offset: int, limit: int = 10
) -> Tuple[List[CompletedTask], bool]:
    """Return a paginated slice of the task index.

    Returns (chunk, has_more) tuple.
    """
    chunk = task_index[offset : offset + limit]
    has_more = offset + limit < len(task_index)
    return chunk, has_more


def find_commits_for_task(
    task_id: str, project_root: Path
) -> List[TaskCommitInfo]:
    """Find all commits related to a task ID.

    Returns list of TaskCommitInfo with affected files for each commit.
    """
    commits = []
    try:
        result = subprocess.run(
            [
                "git",
                "log",
                "--all",
                f"--grep=(t{task_id})",
                "--format=%H %aI %s",
            ],
            capture_output=True,
            text=True,
            cwd=project_root,
        )
        if result.returncode != 0:
            return commits

        for line in result.stdout.strip().splitlines():
            if not line:
                continue
            parts = line.split(" ", 2)
            if len(parts) < 3:
                continue
            hash_val, date_val, msg = parts

            # Get affected files
            files_result = subprocess.run(
                ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", hash_val],
                capture_output=True,
                text=True,
                cwd=project_root,
            )
            affected = []
            if files_result.returncode == 0:
                affected = [
                    f for f in files_result.stdout.strip().splitlines() if f
                ]

            commits.append(
                TaskCommitInfo(
                    hash=hash_val[:12],
                    message=msg,
                    date=date_val,
                    affected_files=affected,
                )
            )
    except (OSError, subprocess.SubprocessError):
        pass

    return commits


def find_child_tasks(
    parent_id: str, task_index: List[CompletedTask]
) -> List[CompletedTask]:
    """Find all child tasks of a parent in the index."""
    return [t for t in task_index if t.task_id.startswith(f"{parent_id}_")]


def find_sibling_tasks(
    task_id: str, task_index: List[CompletedTask]
) -> List[CompletedTask]:
    """Find sibling tasks (same parent, excluding self)."""
    if "_" not in task_id:
        return []
    parent_id = task_id.split("_")[0]
    return [
        t
        for t in task_index
        if t.task_id.startswith(f"{parent_id}_") and t.task_id != task_id
    ]


def detect_platform_info(project_root: Path) -> Optional[PlatformInfo]:
    """Detect git hosting platform from remote URL.

    Supports GitHub, GitLab, and Bitbucket. Returns None for unknown hosts.
    """
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            cwd=project_root,
        )
        if result.returncode != 0:
            return None
        url = result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None

    # Parse owner/repo from SSH or HTTPS URLs
    # SSH: git@github.com:owner/repo.git
    # HTTPS: https://github.com/owner/repo.git
    ssh_match = re.match(r"git@([^:]+):(.+?)(?:\.git)?$", url)
    https_match = re.match(r"https?://([^/]+)/(.+?)(?:\.git)?$", url)

    if ssh_match:
        host = ssh_match.group(1)
        path = ssh_match.group(2)
    elif https_match:
        host = https_match.group(1)
        path = https_match.group(2)
    else:
        return None

    if "github.com" in host:
        base = f"https://github.com/{path}"
        return PlatformInfo(
            platform="github",
            base_url=base,
            commit_url_template=f"{base}/commit/{{hash}}",
        )
    elif "gitlab.com" in host:
        base = f"https://gitlab.com/{path}"
        return PlatformInfo(
            platform="gitlab",
            base_url=base,
            commit_url_template=f"{base}/-/commit/{{hash}}",
        )
    elif "bitbucket.org" in host:
        base = f"https://bitbucket.org/{path}"
        return PlatformInfo(
            platform="bitbucket",
            base_url=base,
            commit_url_template=f"{base}/commits/{{hash}}",
        )

    return None
