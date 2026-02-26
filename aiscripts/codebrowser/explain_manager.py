"""Explain data manager for the codebrowser TUI.

Generates, caches, and parses explain data for files browsed in the codebrowser.
Uses aitask_explain_extract_raw_data.sh + aitask_explain_process_raw_data.py
pipeline, directing output to aiexplains/codebrowser/ with directory-based naming.
"""

import glob
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import yaml

from annotation_data import AnnotationRange, ExplainRunInfo, FileExplainData

CODEBROWSER_DIR = "aiexplains/codebrowser"
EXTRACT_SCRIPT = "./aiscripts/aitask_explain_extract_raw_data.sh"


class ExplainManager:
    def __init__(self, project_root: Path):
        self._root = project_root
        self._cb_dir = project_root / CODEBROWSER_DIR
        os.makedirs(self._cb_dir, exist_ok=True)
        self.cleanup_stale_runs()

    def _dir_to_key(self, directory: Path) -> str:
        """Convert a directory path (relative to project root) to a cache key."""
        rel = str(directory)
        if rel in (".", ""):
            return "_root_"
        return rel.replace("/", "__")

    def _find_run_dir(self, dir_key: str) -> Path | None:
        """Find the most recent run directory for a given directory key."""
        pattern = str(self._cb_dir / f"{dir_key}__[0-9]*")
        matches = sorted(glob.glob(pattern))
        if not matches:
            return None
        # Most recent is last when sorted alphabetically (timestamp suffix)
        return Path(matches[-1])

    def get_cached_data(self, file_path: Path) -> FileExplainData | None:
        """Get cached explain data for a file, or None if not cached."""
        rel_path = file_path.relative_to(self._root)
        directory = rel_path.parent
        dir_key = self._dir_to_key(directory)

        run_dir = self._find_run_dir(dir_key)
        if run_dir is None:
            return None

        ref_yaml = run_dir / "reference.yaml"
        if not ref_yaml.exists():
            return None

        all_data = self.parse_reference_yaml(ref_yaml)
        return all_data.get(str(rel_path))

    def generate_explain_data(self, directory: Path) -> dict[str, FileExplainData]:
        """Generate explain data for direct children of a directory.

        Returns dict of file_path -> FileExplainData for all files in the directory.
        """
        rel_dir = directory.relative_to(self._root) if directory != self._root else Path(".")

        # List direct children only (filter out files in subdirectories)
        result = subprocess.run(
            ["git", "ls-files", str(rel_dir) + "/"],
            capture_output=True, text=True, cwd=str(self._root),
        )
        all_files = [f for f in result.stdout.strip().split("\n") if f]
        direct_files = [
            f for f in all_files
            if os.path.dirname(f) == str(rel_dir)
        ]

        if not direct_files:
            return {}

        # Run extract script with env override and source-key for auto-naming
        dir_key = self._dir_to_key(rel_dir)
        env = os.environ.copy()
        env["AIEXPLAINS_DIR"] = CODEBROWSER_DIR
        subprocess.run(
            [EXTRACT_SCRIPT, "--gather", "--source-key", dir_key] + direct_files,
            env=env, check=True, capture_output=True,
            cwd=str(self._root),
        )

        run_dir = self._find_run_dir(dir_key)
        if run_dir is None:
            return {}

        ref_yaml = run_dir / "reference.yaml"
        if not ref_yaml.exists():
            return {}

        return self.parse_reference_yaml(ref_yaml)

    def cleanup_stale_runs(self) -> int:
        """Remove stale run directories, keeping only the newest per dir_key."""
        if not self._cb_dir.exists():
            return 0

        groups: dict[str, list[Path]] = {}
        for entry in self._cb_dir.iterdir():
            if not entry.is_dir():
                continue
            name = entry.name
            # Parse <key>__<YYYYMMDD_HHMMSS>
            if "__" in name:
                last_sep = name.rfind("__")
                ts_part = name[last_sep + 2:]
                if len(ts_part) == 15 and ts_part[8] == "_" and ts_part.replace("_", "").isdigit():
                    key = name[:last_sep]
                    groups.setdefault(key, []).append(entry)
                    continue
            # Bare timestamp
            if len(name) == 15 and name[8] == "_" and name.replace("_", "").isdigit():
                groups.setdefault("_bare_timestamp_", []).append(entry)

        removed = 0
        for key, dirs in groups.items():
            if len(dirs) <= 1:
                continue
            dirs.sort(key=lambda p: p.name)
            for stale_dir in dirs[:-1]:
                shutil.rmtree(stale_dir)
                removed += 1
        return removed

    def parse_reference_yaml(self, yaml_path: Path) -> dict[str, FileExplainData]:
        """Parse a reference.yaml file into per-file FileExplainData."""
        with open(yaml_path) as f:
            data = yaml.safe_load(f)

        if not data or "files" not in data:
            return {}

        # Extract generated_at from the run directory name (timestamp suffix)
        run_dir_name = yaml_path.parent.name
        # Timestamp is the last 15 chars: YYYYMMDD_HHMMSS
        ts_str = run_dir_name[-15:] if len(run_dir_name) >= 15 else ""
        generated_at = ""
        if len(ts_str) == 15 and ts_str[8] == "_":
            try:
                dt = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
                generated_at = dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass

        result = {}
        for file_entry in data["files"]:
            file_path = file_entry["path"]
            is_binary = file_entry.get("binary", False)

            annotations = []
            commit_map = {}

            if not is_binary:
                for lr in file_entry.get("line_ranges", []):
                    annotations.append(AnnotationRange(
                        start_line=lr["start"],
                        end_line=lr["end"],
                        task_ids=[str(t) for t in lr.get("tasks", [])],
                        commit_hashes=[],
                        commit_messages=[],
                    ))

                # Build commit hash/message lists from commit timeline
                for commit in file_entry.get("commits", []):
                    commit_map[commit["num"]] = commit

                # Enrich annotations with commit details
                for ann in annotations:
                    for lr in file_entry.get("line_ranges", []):
                        if lr["start"] == ann.start_line and lr["end"] == ann.end_line:
                            for cnum in lr.get("commits", []):
                                if cnum in commit_map:
                                    c = commit_map[cnum]
                                    if c["hash"] not in ann.commit_hashes:
                                        ann.commit_hashes.append(c["hash"])
                                        ann.commit_messages.append(c.get("message", ""))
                            break

            commit_timeline = file_entry.get("commits", [])
            result[file_path] = FileExplainData(
                file_path=file_path,
                annotations=annotations,
                commit_timeline=commit_timeline,
                generated_at=generated_at,
                is_binary=is_binary,
            )

        return result

    def refresh_data(self, directory: Path) -> dict[str, FileExplainData]:
        """Delete cached data for a directory and regenerate."""
        rel_dir = directory.relative_to(self._root) if directory != self._root else Path(".")
        dir_key = self._dir_to_key(rel_dir)

        run_dir = self._find_run_dir(dir_key)
        if run_dir is not None:
            shutil.rmtree(run_dir)

        return self.generate_explain_data(directory)

    def get_run_info(self, file_path: Path) -> ExplainRunInfo | None:
        """Get metadata about the explain run covering a file."""
        rel_path = file_path.relative_to(self._root)
        directory = rel_path.parent
        dir_key = self._dir_to_key(directory)

        run_dir = self._find_run_dir(dir_key)
        if run_dir is None:
            return None

        # Parse timestamp from directory name
        ts_str = run_dir.name[-15:] if len(run_dir.name) >= 15 else ""
        timestamp = ""
        if len(ts_str) == 15 and ts_str[8] == "_":
            try:
                dt = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
                timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass

        # Count files from files.txt
        file_count = 0
        files_txt = run_dir / "files.txt"
        if files_txt.exists():
            file_count = sum(1 for line in files_txt.read_text().splitlines() if line.strip())

        return ExplainRunInfo(
            run_dir=str(run_dir),
            directory_key=dir_key,
            timestamp=timestamp,
            file_count=file_count,
        )
