#!/usr/bin/env python3
"""Report remote desync state for aitasks-managed git refs."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


STATUSES = {
    "ok",
    "missing_local",
    "missing_remote",
    "no_remote",
    "fetch_error",
    "missing_worktree",
}


@dataclass
class RefState:
    name: str
    worktree: str
    local_ref: str
    remote_ref: str
    status: str
    ahead: int = 0
    behind: int = 0
    remote_commits: list[str] | None = None
    remote_changed_paths: list[str] | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f"Invalid status: {self.status}")
        if self.remote_commits is None:
            self.remote_commits = []
        if self.remote_changed_paths is None:
            self.remote_changed_paths = []


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def run_git(worktree: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(worktree),
        text=True,
        capture_output=True,
        check=False,
    )


def has_remote(worktree: Path) -> bool:
    return run_git(worktree, ["remote", "get-url", "origin"]).returncode == 0


def ref_exists(worktree: Path, ref: str) -> bool:
    return run_git(worktree, ["rev-parse", "--verify", "--quiet", ref]).returncode == 0


def fetch_ref(worktree: Path, branch: str) -> subprocess.CompletedProcess[str]:
    return run_git(worktree, ["fetch", "--quiet", "origin", branch])


def short_error(proc: subprocess.CompletedProcess[str]) -> str:
    text = (proc.stderr or proc.stdout or "").strip()
    if text:
        return text.splitlines()[-1]
    return f"git exited with code {proc.returncode}"


def count_ahead_behind(worktree: Path, local_ref: str, remote_ref: str) -> tuple[int, int]:
    proc = run_git(worktree, ["rev-list", "--left-right", "--count", f"{local_ref}...{remote_ref}"])
    if proc.returncode != 0:
        return 0, 0
    parts = proc.stdout.strip().split()
    if len(parts) != 2:
        return 0, 0
    return int(parts[0]), int(parts[1])


def remote_commit_subjects(worktree: Path, local_ref: str, remote_ref: str) -> list[str]:
    proc = run_git(worktree, ["log", "--format=%s", f"{local_ref}..{remote_ref}"])
    if proc.returncode != 0:
        return []
    return [line for line in proc.stdout.splitlines() if line]


def remote_changed_paths(worktree: Path, local_ref: str, remote_ref: str) -> list[str]:
    proc = run_git(worktree, ["diff", "--name-only", f"{local_ref}..{remote_ref}"])
    if proc.returncode != 0:
        return []
    return sorted({line for line in proc.stdout.splitlines() if line})


def snapshot_ref(name: str, fetch: bool, root: Path) -> RefState:
    if name == "main":
        worktree = root
        worktree_label = "."
        local_ref = "main"
        remote_ref = "origin/main"
    elif name == "aitask-data":
        worktree = root / ".aitask-data"
        worktree_label = ".aitask-data"
        local_ref = "aitask-data"
        remote_ref = "origin/aitask-data"
    else:
        raise ValueError(f"Unsupported ref: {name}")

    if not worktree.exists() or run_git(worktree, ["rev-parse", "--is-inside-work-tree"]).returncode != 0:
        return RefState(name, worktree_label, local_ref, remote_ref, "missing_worktree")

    if not has_remote(worktree):
        return RefState(name, worktree_label, local_ref, remote_ref, "no_remote")

    if fetch:
        fetch_proc = fetch_ref(worktree, local_ref)
        if fetch_proc.returncode != 0:
            if not ref_exists(worktree, remote_ref):
                return RefState(name, worktree_label, local_ref, remote_ref, "missing_remote")
            return RefState(
                name,
                worktree_label,
                local_ref,
                remote_ref,
                "fetch_error",
                error=short_error(fetch_proc),
            )

    if not ref_exists(worktree, local_ref):
        return RefState(name, worktree_label, local_ref, remote_ref, "missing_local")

    if not ref_exists(worktree, remote_ref):
        return RefState(name, worktree_label, local_ref, remote_ref, "missing_remote")

    ahead, behind = count_ahead_behind(worktree, local_ref, remote_ref)
    return RefState(
        name=name,
        worktree=worktree_label,
        local_ref=local_ref,
        remote_ref=remote_ref,
        status="ok",
        ahead=ahead,
        behind=behind,
        remote_commits=remote_commit_subjects(worktree, local_ref, remote_ref),
        remote_changed_paths=remote_changed_paths(worktree, local_ref, remote_ref),
    )


def snapshot(ref_filter: str | None, fetch: bool) -> dict[str, list[dict[str, object]]]:
    names = [ref_filter] if ref_filter else ["main", "aitask-data"]
    root = repo_root()
    return {"refs": [asdict(snapshot_ref(name, fetch, root)) for name in names]}


def emit_json(data: dict[str, list[dict[str, object]]]) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def emit_lines(data: dict[str, list[dict[str, object]]]) -> None:
    first = True
    for ref in data["refs"]:
        if not first:
            print()
        first = False
        print(f"REF:{ref['name']}")
        print(f"STATUS:{ref['status']}")
        print(f"AHEAD:{ref['ahead']}")
        print(f"BEHIND:{ref['behind']}")
        error = ref.get("error")
        if error:
            print(f"ERROR:{error}")
        for subject in ref.get("remote_commits", []):
            print(f"REMOTE_COMMIT:{subject}")
        for path in ref.get("remote_changed_paths", []):
            print(f"REMOTE_CHANGED_PATH:{path}")


def emit_text(data: dict[str, list[dict[str, object]]]) -> None:
    for ref in data["refs"]:
        name = ref["name"]
        status = ref["status"]
        if status == "ok":
            ahead = int(ref["ahead"])
            behind = int(ref["behind"])
            if ahead == 0 and behind == 0:
                print(f"{name}: up to date")
            else:
                print(f"{name}: behind {behind}, ahead {ahead}")
        elif status == "missing_worktree":
            print(f"{name}: missing worktree")
        elif status == "no_remote":
            print(f"{name}: no origin remote")
        elif status == "missing_local":
            print(f"{name}: missing local ref")
        elif status == "missing_remote":
            print(f"{name}: missing remote ref")
        elif status == "fetch_error":
            print(f"{name}: fetch error")
        else:
            print(f"{name}: {status}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report aitasks remote desync state.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    snapshot_parser = subparsers.add_parser("snapshot", help="Snapshot tracked refs.")
    snapshot_parser.add_argument("--fetch", action="store_true", help="Fetch origin before computing state.")
    snapshot_parser.add_argument("--ref", choices=["main", "aitask-data"], dest="ref_filter")
    snapshot_parser.add_argument("--format", choices=["json", "text", "lines"], default="text")
    snapshot_parser.add_argument("--json", action="store_true", help="Alias for --format json.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.command == "snapshot":
        output_format = "json" if args.json else args.format
        data = snapshot(args.ref_filter, args.fetch)
        if output_format == "json":
            emit_json(data)
        elif output_format == "lines":
            emit_lines(data)
        else:
            emit_text(data)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
