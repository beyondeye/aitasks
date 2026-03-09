#!/usr/bin/env python3

import argparse
import re
import subprocess
import sys
from pathlib import Path


FRAMEWORK_DIRS = {
    ".aitask-scripts",
    "aitasks",
    "aiplans",
    "aireviewguides",
    ".claude",
    ".gemini",
    ".agents",
    ".opencode",
    "seed",
}

SAFETY_EXCLUDES = {".git", "node_modules", "__pycache__"}


def run_git_command(args: list[str], cwd: Path) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return [line for line in result.stdout.splitlines() if line]


def clean_description(name: str) -> str:
    return name.replace("-", " ").replace("_", " ")


def extract_existing_paths(path: Path) -> set[str]:
    if not path.is_file():
        return set()

    paths = set()
    pattern = re.compile(r"^\s+path:\s*(\S.*?)\s*$")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            paths.add(match.group(1))
    return paths


def build_tracked_directory_index(tracked_files: list[str]) -> dict[str, set[str]]:
    index: dict[str, set[str]] = {}
    for tracked in tracked_files:
        parts = tracked.split("/")
        if len(parts) < 2:
            continue

        top = parts[0]
        index.setdefault("", set()).add(top)

        for depth in range(1, len(parts) - 1):
            parent = "/".join(parts[:depth])
            child = parts[depth]
            index.setdefault(parent, set()).add(child)

    return index


def resolve_ignored_dirs(repo_root: Path, candidates: list[str], ignore_file: str | None) -> set[str]:
    if not ignore_file:
        return set()

    ignore_path = Path(ignore_file)
    if not ignore_path.is_absolute():
        ignore_path = repo_root / ignore_path
    if not ignore_path.is_file():
        raise FileNotFoundError(f"Ignore file not found: {ignore_file}")

    stdin = "".join(f"{candidate}/\n" for candidate in candidates)
    result = subprocess.run(
        [
            "git",
            "-c",
            f"core.excludesFile={ignore_path}",
            "check-ignore",
            "--no-index",
            "--stdin",
        ],
        cwd=repo_root,
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr.strip() or "git check-ignore failed")

    ignored = set()
    for line in result.stdout.splitlines():
        line = line.rstrip("/")
        if line:
            ignored.add(line)
    return ignored


def should_exclude(path: str, include_framework_dirs: bool, ignored_dirs: set[str]) -> bool:
    parts = path.split("/")
    name = parts[-1]

    if name in SAFETY_EXCLUDES:
        return True

    if len(parts) == 1 and not include_framework_dirs and name in FRAMEWORK_DIRS:
        return True

    if path in ignored_dirs:
        return True

    return False


def render_yaml(
    repo_root: Path,
    existing_file: str | None,
    include_framework_dirs: bool,
    ignore_file: str | None,
) -> str:
    tracked_files = run_git_command(["ls-files"], repo_root)
    index = build_tracked_directory_index(tracked_files)

    top_dirs = sorted(index.get("", set()))
    all_candidates: list[str] = []
    for top_dir in top_dirs:
        all_candidates.append(top_dir)
        for subdir in sorted(index.get(top_dir, set())):
            all_candidates.append(f"{top_dir}/{subdir}")

    ignored_dirs = resolve_ignored_dirs(repo_root, all_candidates, ignore_file)

    existing_paths = set()
    if existing_file:
        existing_path = Path(existing_file)
        if not existing_path.is_absolute():
            existing_path = repo_root / existing_path
        existing_paths = extract_existing_paths(existing_path)

    visible_top_dirs = [
        top_dir
        for top_dir in top_dirs
        if not should_exclude(top_dir, include_framework_dirs, ignored_dirs)
    ]

    if not visible_top_dirs:
        return "version: 1\n\nareas: []\n"

    lines = ["version: 1", "", "areas:"]
    wrote_area = False

    for top_dir in visible_top_dirs:
        top_path = f"{top_dir}/"
        if existing_paths and top_path in existing_paths:
            continue

        wrote_area = True
        lines.append(f"  - name: {top_dir}")
        lines.append(f"    path: {top_path}")
        lines.append(f"    description: {clean_description(top_dir)}")

        subdirs = [
            subdir
            for subdir in sorted(index.get(top_dir, set()))
            if not should_exclude(f"{top_dir}/{subdir}", include_framework_dirs, ignored_dirs)
        ]
        if len(subdirs) > 2:
            child_lines = []
            for subdir in subdirs:
                sub_path = f"{top_dir}/{subdir}/"
                if existing_paths and sub_path in existing_paths:
                    continue
                child_lines.extend(
                    [
                        f"      - name: {subdir}",
                        f"        path: {sub_path}",
                        f"        description: {clean_description(subdir)}",
                    ]
                )

            if child_lines:
                lines.append("    children:")
                lines.extend(child_lines)

    if not wrote_area:
        return "version: 1\n\nareas:\n  []\n"

    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--existing")
    parser.add_argument("--include-framework-dirs", action="store_true")
    parser.add_argument("--ignore-file")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path.cwd()

    try:
        sys.stdout.write(
            render_yaml(
                repo_root=repo_root,
                existing_file=args.existing,
                include_framework_dirs=args.include_framework_dirs,
                ignore_file=args.ignore_file,
            )
        )
        return 0
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
