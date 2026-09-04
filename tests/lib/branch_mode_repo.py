"""Shared branch-mode destination fixture (t1704).

Why this exists
---------------
`cross_repo_settings.apply_push` writes **another** repo's tracked
`codeagent_config.json` and now commits there. Testing that needs a destination
in the real production topology — an `aitask-data` orphan branch checked out as
a `.aitask-data` worktree, an `aitasks` symlink pointing into it, and that
repo's **own** `aitask_metadata_commit.sh` — because the seam deliberately runs
the *destination's* copy of the helper.

It lives in `tests/lib/` rather than inside one test module because two modules
need the same topology: `test_cross_repo_push_commit.py` (the new matrix) and
the three `test_cross_repo_settings.py` cases that pin the `clear_mask` ordering
contract, which can only run against a destination the push will actually write
to. Two copies of a git topology is exactly the shape that silently drifts.

Not shared with `tests/test_settings_commit_on_save.py`'s fixture, and that is
deliberate: that one `chdir`s into the repo under test, while the whole point
here is that **cwd stays elsewhere** and the seam targets a foreign root by
path. A fixture that moves the process cannot test that.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

#: The framework files a destination needs for the commit seam to work there.
#: Only these — a destination is NOT a full framework checkout, and pretending
#: otherwise would hide a real dependency.
_HELPER = "aitask_metadata_commit.sh"


def _git(cwd, *args, check=True):
    return subprocess.run(
        ["git", *args], cwd=str(cwd), check=check,
        capture_output=True, text=True,
    )


def make_branch_mode_repo(
    root: Path,
    *,
    project: dict | None = None,
    local: dict | None = None,
    models: dict[str, list[str]] | None = None,
    commit_config: bool = True,
    install_helper: bool = True,
) -> Path:
    """Build a committable branch-mode aitasks repo at `root`.

    Layout (mirrors what `ait setup` produces):

        <root>/.git
        <root>/.aitask-data/            worktree on the `aitask-data` branch
        <root>/.aitask-data/aitasks/metadata/...
        <root>/aitasks -> .aitask-data/aitasks
        <root>/.aitask-scripts/aitask_metadata_commit.sh   (the real one)
        <root>/.aitask-scripts/lib -> <this repo>/.aitask-scripts/lib

    `commit_config=False` leaves the config files written but **untracked**,
    which is one of the states the push must refuse.

    `install_helper=False` omits `aitask_metadata_commit.sh` entirely — the
    version-skew case, where a destination predates the commit seam.
    """
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)

    _git(root, "init", "-q", ".")
    _git(root, "config", "user.email", "test@test.com")
    _git(root, "config", "user.name", "Test")
    _git(root, "config", "commit.gpgsign", "false")
    (root / "README.md").write_text("# dest\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")

    # The orphan data branch, built with plumbing exactly as `ait setup` does —
    # an empty tree, a commit with no parent, then a worktree on it.
    empty_tree = subprocess.run(
        ["git", "mktree"], cwd=str(root), input="", capture_output=True,
        text=True, check=True,
    ).stdout.strip()
    branch_commit = subprocess.run(
        ["git", "commit-tree", empty_tree], cwd=str(root),
        input="ait: Initialize aitask-data branch", capture_output=True,
        text=True, check=True,
    ).stdout.strip()
    _git(root, "update-ref", "refs/heads/aitask-data", branch_commit)
    _git(root, "worktree", "add", "-q", ".aitask-data", "aitask-data")
    _git(root / ".aitask-data", "config", "user.email", "test@test.com")
    _git(root / ".aitask-data", "config", "user.name", "Test")
    _git(root / ".aitask-data", "config", "commit.gpgsign", "false")

    meta = root / ".aitask-data" / "aitasks" / "metadata"
    meta.mkdir(parents=True, exist_ok=True)
    (root / "aitasks").symlink_to(Path(".aitask-data") / "aitasks")

    # The user layer is gitignored on the data branch, exactly as in production
    # — the push relies on that to report `user_layer_only` rather than trying
    # to commit someone's private override.
    (root / ".aitask-data" / ".gitignore").write_text(
        "aitasks/metadata/userconfig.yaml\n"
        "aitasks/metadata/*.local.json\n"
        "aitasks/metadata/profiles/local/\n",
        encoding="utf-8",
    )

    if project is not None:
        (meta / "codeagent_config.json").write_text(
            json.dumps({"defaults": project}, indent=2) + "\n", encoding="utf-8"
        )
    if local is not None:
        (meta / "codeagent_config.local.json").write_text(
            json.dumps({"defaults": local}, indent=2) + "\n", encoding="utf-8"
        )
    for agent, names in (models or {"claudecode": ["opus5", "sonnet5", "haiku4_5"]}).items():
        (meta / f"models_{agent}.json").write_text(
            json.dumps(
                {"models": [{"name": n, "cli_id": n} for n in names]}, indent=2
            ) + "\n",
            encoding="utf-8",
        )

    _git(root / ".aitask-data", "add", "-A")
    _git(root / ".aitask-data", "commit", "-q", "-m", "data init")

    if not commit_config and (meta / "codeagent_config.json").is_file():
        # Untrack it while leaving the bytes on disk: the "present but
        # untracked" state, which is unclassified foreign content.
        _git(root / ".aitask-data", "rm", "-q", "--cached", "--",
             "aitasks/metadata/codeagent_config.json")
        _git(root / ".aitask-data", "commit", "-q", "-m", "untrack config")

    scripts = root / ".aitask-scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    if install_helper:
        # The REAL helper, not a stub: the seam runs the destination's own copy,
        # so a stub would test our idea of it rather than the thing that runs.
        src = REPO_ROOT / ".aitask-scripts" / _HELPER
        dst = scripts / _HELPER
        dst.write_bytes(src.read_bytes())
        dst.chmod(0o755)
        lib = scripts / "lib"
        if not lib.exists():
            lib.symlink_to(REPO_ROOT / ".aitask-scripts" / "lib")

    install_resolver_stub(root)
    return root


def install_resolver_stub(root: Path) -> None:
    """A faithful `aitask_codeagent.sh`, honouring the same env overrides.

    THE one definition of this stub — `tests/test_cross_repo_settings.py`'s
    `make_repo` calls it rather than carrying a second copy. Two copies of a
    resolver whose whole job is to be faithful is precisely the pair that
    silently stops matching `lib/agent_string.sh`.

    It must:
      * honour METADATA_DIR / TASK_DIR / DEFAULT_AGENT_STRING, because those are
        documented caller overrides that outrank cwd — the env-scrubbing
        contract is untestable against a stub that ignores them; and
      * answer in the real `AGENT_STRING:<value>` protocol, which is what
        `agent_launch_utils.resolve_agent_string` actually parses. A stub that
        echoes a bare value makes every `effective` read as None.
    """
    scripts = root / ".aitask-scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    sh = scripts / "aitask_codeagent.sh"
    sh.write_text(
        '#!/usr/bin/env bash\n'
        'set -u\n'
        '# Mirrors lib/agent_string.sh: these are caller overrides.\n'
        'METADATA_DIR="${METADATA_DIR:-${TASK_DIR:-aitasks}/metadata}"\n'
        'DEFAULT_AGENT_STRING="${DEFAULT_AGENT_STRING:-claudecode/opus5}"\n'
        'op="$2"\n'
        'for f in "$METADATA_DIR/codeagent_config.local.json" '
        '"$METADATA_DIR/codeagent_config.json"; do\n'
        '  if [[ -f "$f" ]]; then\n'
        '    v=$(python3 -c "import json,sys;'
        'd=json.load(open(sys.argv[1]));'
        'print(d.get(\'defaults\',{}).get(sys.argv[2],\'\'))" '
        '"$f" "$op" 2>/dev/null) || true\n'
        '    if [[ -n "$v" ]]; then echo "AGENT_STRING:$v"; exit 0; fi\n'
        '  fi\n'
        'done\n'
        'echo "AGENT_STRING:$DEFAULT_AGENT_STRING"\n',
        encoding="utf-8",
    )
    sh.chmod(0o755)


# --- Inspection helpers (used by the assertions, not the build) --------------

def data_git(root: Path, *args) -> str:
    return subprocess.run(
        ["git", "-C", str(Path(root) / ".aitask-data"), *args],
        capture_output=True, text=True,
    ).stdout.strip()


def head_files(root: Path) -> list[str]:
    out = data_git(root, "show", "--name-only", "--format=", "HEAD")
    return [ln for ln in out.splitlines() if ln.strip()]


def head_subject(root: Path) -> str:
    return data_git(root, "log", "-1", "--format=%s")


def data_head(root: Path) -> str:
    return data_git(root, "rev-parse", "HEAD")


def staged_paths(root: Path) -> list[str]:
    out = data_git(root, "diff", "--cached", "--name-only")
    return [ln for ln in out.splitlines() if ln.strip()]


def worktree_clean(root: Path) -> bool:
    return data_git(root, "status", "--porcelain") == ""


def install_failing_pre_commit(root: Path) -> None:
    """Make `git commit` fail through the documented seam.

    Same one `tests/test_metadata_commit_seam.sh` and `tests/test_fold_mark.sh`
    use: no commit site passes `--no-verify`, and git releases the index lock on
    hook failure, so the index stays readable afterwards. The hook lives in the
    COMMON git dir, which the `.aitask-data` worktree shares.
    """
    hooks = Path(root) / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    hook = hooks / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)


def plant_inprogress_state(root: Path, state: str) -> None:
    """Wedge the data worktree mid-operation, as git itself would.

    `state` is one of `lib/task_utils.sh::AIT_GIT_INPROGRESS_STATES`.
    """
    gitdir = Path(root) / ".git" / "worktrees" / "-aitask-data"
    gitdir.mkdir(parents=True, exist_ok=True)
    target = gitdir / state
    if state in ("rebase-merge", "rebase-apply"):
        target.mkdir(exist_ok=True)
    else:
        target.write_text("", encoding="utf-8")


def detach_data_head(root: Path) -> None:
    """Put the data worktree on a detached HEAD."""
    head = data_git(root, "rev-parse", "HEAD")
    subprocess.run(
        ["git", "-C", str(Path(root) / ".aitask-data"), "checkout", "-q",
         "--detach", head],
        capture_output=True, text=True,
    )


def make_legacy_repo(root: Path, *, project: dict | None = None) -> Path:
    """A destination with NO data branch — task data on the code branch.

    Committing there would land on whatever code branch happens to be checked
    out, which is why the push refuses it outright.
    """
    root = Path(root)
    (root / "aitasks" / "metadata").mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q", ".")
    _git(root, "config", "user.email", "test@test.com")
    _git(root, "config", "user.name", "Test")
    _git(root, "config", "commit.gpgsign", "false")
    if project is not None:
        (root / "aitasks" / "metadata" / "codeagent_config.json").write_text(
            json.dumps({"defaults": project}, indent=2) + "\n", encoding="utf-8"
        )
    (root / "aitasks" / "metadata" / "models_claudecode.json").write_text(
        json.dumps({"models": [{"name": n, "cli_id": n}
                               for n in ("opus5", "sonnet5", "haiku4_5")]},
                   indent=2) + "\n",
        encoding="utf-8",
    )
    scripts = root / ".aitask-scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    dst = scripts / _HELPER
    dst.write_bytes((REPO_ROOT / ".aitask-scripts" / _HELPER).read_bytes())
    dst.chmod(0o755)
    lib = scripts / "lib"
    if not lib.exists():
        lib.symlink_to(REPO_ROOT / ".aitask-scripts" / "lib")
    install_resolver_stub(root)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    return root
