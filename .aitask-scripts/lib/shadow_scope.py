"""shadow_scope.py - ownership EVIDENCE for the shadow's implementation review (t1873).

A shadow following a coding agent reviews the changes that agent made. In a
checkout shared by several concurrent sessions, "every dirty file" is not that
set. This module reports, for every changed file PART in the followed checkout,
the evidence bearing on whose change it is. It never decides. The shadow reads
the changes and makes the ownership judgement (impl-challenge.md, "Ownership
judgement"). That split is deliberate: plan file lists are neither complete nor
reliable, and whether an unlisted file belongs to the task depends on its
content, which is the reviewer's job, not a table's.

PARTS. A path yields up to two parts, reported separately because they can
belong to different sessions:
  committed  the path in the followed task's own tagged commits `(t<id>)`
  dirty      whatever of staged / unstaged / untracked the path has now
A later foreign edit to a file the followed task committed is a dirty part of
its own, never folded into the committed one.

EVIDENCE TOKENS (each keeps its source; none is a verdict):
  f_commits:<n>          committed part: followed-task commits touching it
  f_commit_earlier:<n>   dirty part: the followed task committed this path
                         earlier, so the dirty change is NEWER than that work
  f_plan:<heading>       the followed task's plan references the path, under
                         that section heading (slug; `top` = no heading)
  f_task:<heading>       the followed task's description references it
  f_plan_suffix:<heading> / f_task_suffix:<heading>
                         referenced only by a trailing sub-path (>= 2
                         components) -- the module-relative form a sub-project
                         plan uses; weaker, since short suffixes are ambiguous
  f_plan_dir:<dir>       the plan references an ancestor directory `<dir>/`
  baseline_dirty         the path was already dirty when the task was claimed
  other_plan:t<X>        another active task's plan references it
  other_task:t<X>        another active task's description references it
  other_commit:t<X>      another active task has a tagged commit touching it
  other_plan_suffix:t<X> / other_task_suffix:t<X>
                         another active task references it by a trailing
                         sub-path only
  -                      no evidence at all

References are found with `plan_paths.find_references` -- the inverted,
language-agnostic search -- over the exact paths git reported. The claim
baseline is read through `aitask_change_surface.sh baseline`, and tagged commits
through `aitask_revert_analyze.sh --task-commits`. The only scan logic
this module owns is the per-part assembly.

Invoked by `aitask_shadow_scope.sh`, which resolves the checkout. Run it from
the repository root that holds the task data (`aitasks/`, `aiplans/`).
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import plan_paths  # noqa: E402

SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASK_ID_RE = re.compile(r"^t?(\d+(?:_\d+)?)$")
# Task/plan data is never part of a code review; `.aitask-gates/` is framework
# bookkeeping (claim baselines, gate logs) that `ait setup` normally gitignores.
DATA_PREFIXES = ("aitasks/", "aiplans/", ".aitask-data/", ".aitask-gates/")
EXCLUDE_SPECS = [":(exclude)aitasks", ":(exclude)aiplans", ":(exclude).aitask-data",
                 ":(exclude).aitask-gates"]
GIT_TIMEOUT_S = 30


# --- small helpers ------------------------------------------------------------

def _dec(raw: bytes) -> str:
    return raw.decode("utf-8", "surrogateescape")


def _git(checkout: str, *args: str) -> "bytes | None":
    """stdout of a git call in `checkout`, or None when git could not answer."""
    try:
        res = subprocess.run(
            ["git", "-C", checkout, "-c", "core.quotePath=false", *args],
            capture_output=True, timeout=GIT_TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return res.stdout if res.returncode == 0 else None


def _z_paths(raw: "bytes | None") -> "list[str]":
    if not raw:
        return []
    return [_dec(p) for p in raw.split(b"\0") if p]


def _run_lines(cmd: "list[str]", cwd: str, env=None) -> "list[str]":
    try:
        res = subprocess.run(cmd, cwd=cwd, capture_output=True, timeout=GIT_TIMEOUT_S,
                             env=env)
    except (OSError, subprocess.TimeoutExpired):
        return []
    return _dec(res.stdout).splitlines()


def _is_data_path(path: str) -> bool:
    return path.startswith(DATA_PREFIXES)


def slug(heading: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", heading.lower()).strip("_")[:40].strip("_")
    return s or "top"


def _read(path: "str | None") -> "str | None":
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8", errors="surrogateescape") as fh:
            return fh.read()
    except OSError:
        return None


# --- task / plan resolution ---------------------------------------------------

def task_and_plan(task_id: str, repo: str) -> "tuple[str | None, str | None]":
    """(task_file, plan_file) via aitask_shadow_context.sh, plus the archived-plan
    fallback that helper deliberately does not do."""
    task_file = plan_file = None
    for line in _run_lines([os.path.join(SCRIPTS_DIR, "aitask_shadow_context.sh"),
                            task_id], repo):
        if line.startswith("TASK_FILE:") and line != "TASK_FILE:NOT_FOUND":
            task_file = line[len("TASK_FILE:"):]
        elif line.startswith("PLAN_FILE:") and line != "PLAN_FILE:NOT_FOUND":
            plan_file = line[len("PLAN_FILE:"):]
    if plan_file is None:
        archived = os.environ.get("ARCHIVED_PLAN_DIR", "aiplans/archived")
        if "_" in task_id:
            parent, child = task_id.split("_", 1)
            pat = os.path.join(archived, f"p{parent}", f"p{parent}_{child}_*.md")
        else:
            pat = os.path.join(archived, f"p{task_id}_*.md")
        hits = sorted(glob.glob(os.path.join(repo, pat)))
        if hits:
            plan_file = os.path.relpath(hits[-1], repo)
    return task_file, plan_file


def _frontmatter_status(text: str) -> str:
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    head = text[:end] if end != -1 else ""
    m = re.search(r"^status:\s*(\S+)", head, re.MULTILINE)
    return m.group(1) if m else ""


def active_other_tasks(task_id: str, repo: str) -> "list[tuple[str, str]]":
    """[(id, task_file)] for every `status: Implementing` task other than the
    followed one, its parent, and its children."""
    task_dir = os.environ.get("TASK_DIR", "aitasks")
    parent = task_id.split("_", 1)[0]
    excluded = {task_id}
    if "_" in task_id:
        excluded.add(parent)
    out = []
    files = glob.glob(os.path.join(repo, task_dir, "t*.md")) + \
        glob.glob(os.path.join(repo, task_dir, "t*", "t*.md"))
    for path in sorted(files):
        m = re.match(r"^t(\d+(?:_\d+)?)_", os.path.basename(path))
        if not m:
            continue
        tid = m.group(1)
        if tid in excluded or ("_" not in task_id and tid.startswith(task_id + "_")):
            continue
        text = _read(path) or ""
        if _frontmatter_status(text) == "Implementing":
            out.append((tid, path))
    return out


# --- evidence sources ---------------------------------------------------------

def task_commits(task_id: str, repo: str, checkout: str) -> "dict[str, list[str]]":
    """{path: [hash, ...]} for commits tagged exactly `(t<task_id>)`.

    `--task-commits` of a parent id also returns its children's commits (the
    last field names which id matched), so the filter is on that field."""
    by_path: "dict[str, list[str]]" = {}
    for line in _run_lines([os.path.join(SCRIPTS_DIR, "aitask_revert_analyze.sh"),
                            "--task-commits", task_id], repo):
        fields = line.split("|")
        if len(fields) < 7 or fields[0] != "COMMIT" or fields[-1] != task_id:
            continue
        sha = fields[1]
        for path in _z_paths(_git(checkout, "diff-tree", "--root", "-r",
                                  "--no-commit-id", "--name-only", "-z", sha)):
            if _is_data_path(path):
                continue
            hashes = by_path.setdefault(path, [])
            if sha not in hashes:
                hashes.append(sha)
    return by_path


def claim_baseline(task_id: str, repo: str, checkout: str) -> "tuple[str, set[str]]":
    """(state, already-dirty paths) from the task's claim-time baseline."""
    env = dict(os.environ)
    env.setdefault("AIT_CHANGE_SURFACE_DIR", os.path.join(os.path.abspath(repo),
                                                          ".aitask-gates"))
    state, dirty = "missing", set()
    for line in _run_lines([os.path.join(SCRIPTS_DIR, "aitask_change_surface.sh"),
                            "baseline", task_id], checkout, env=env):
        if line.startswith("BASELINE:"):
            state = line[len("BASELINE:"):]
        elif line.startswith("DIRTY_AT_CLAIM:"):
            dirty.add(line[len("DIRTY_AT_CLAIM:"):])
    return state, dirty


def dirty_channels(checkout: str) -> "dict[str, list[str]]":
    """{path: [channel, ...]} across staged / unstaged / untracked."""
    chans: "dict[str, list[str]]" = {}
    sources = (
        ("staged", ("diff", "--cached", "--name-only", "-z", "--", ".", *EXCLUDE_SPECS)),
        ("unstaged", ("diff", "--name-only", "-z", "--", ".", *EXCLUDE_SPECS)),
        ("untracked", ("ls-files", "--others", "--exclude-standard", "-z", "--", ".",
                       *EXCLUDE_SPECS)),
    )
    for name, args in sources:
        for path in _z_paths(_git(checkout, *args)):
            if _is_data_path(path):
                continue
            chans.setdefault(path, []).append(name)
    return chans


def dedicated_worktree(checkout: str, source: str, task_name: "str | None") -> str:
    if source == "worktree_record":
        return "yes|worktree_record"
    git_dir = _git(checkout, "rev-parse", "--path-format=absolute", "--git-dir")
    common = _git(checkout, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if git_dir is None or common is None or git_dir.strip() == common.strip():
        return "no"
    branch = _git(checkout, "symbolic-ref", "--quiet", "--short", "HEAD")
    if task_name and branch is not None and _dec(branch).strip() == f"aitask/{task_name}":
        return "yes|branch"
    return "no"


# --- assembly -----------------------------------------------------------------

def _ancestors(path: str) -> "list[str]":
    parts = path.split("/")[:-1]
    return ["/".join(parts[:i]) for i in range(len(parts), 0, -1)]


def _mention_tokens(prefix: str, refs) -> "list[str]":
    seen: "list[str]" = []
    for _line, heading in refs:
        tok = f"{prefix}:{slug(heading)}"
        if tok not in seen:
            seen.append(tok)
    return seen


def build(task_id: str, repo: str, checkout: str, checkout_source: str) -> "list[str]":
    out = [f"TASK:{task_id}", f"CHECKOUT:{checkout}|{checkout_source}"]
    task_file, plan_file = task_and_plan(task_id, repo)
    task_name = os.path.splitext(os.path.basename(task_file))[0] if task_file else None

    out.append(f"SIGNAL:dedicated_worktree|{dedicated_worktree(checkout, checkout_source, task_name)}")
    plan_text = _read(os.path.join(repo, plan_file)) if plan_file else None
    out.append(f"SIGNAL:plan|ok|{plan_file}" if plan_text is not None else "SIGNAL:plan|missing")
    task_raw = _read(os.path.join(repo, task_file)) if task_file else None
    task_text = plan_paths.task_body_text(task_raw) if task_raw is not None else None
    out.append("SIGNAL:task|ok" if task_text is not None else "SIGNAL:task|missing")

    f_commits = task_commits(task_id, repo, checkout)
    all_hashes = sorted({h for hs in f_commits.values() for h in hs})
    out.append(f"SIGNAL:commits|{len(all_hashes)}|{','.join(all_hashes)}")

    base_state, base_dirty = claim_baseline(task_id, repo, checkout)
    out.append(f"SIGNAL:baseline|{base_state}")

    others = active_other_tasks(task_id, repo)
    out.append(f"SIGNAL:other_tasks|{len(others)}|{','.join(t for t, _ in others)}")

    dirty = dirty_channels(checkout)
    paths = sorted(set(dirty) | set(f_commits))
    unrepresentable = [p for p in paths if "\n" in p]
    paths = [p for p in paths if "\n" not in p]

    plan_refs = plan_paths.find_references(plan_text, paths) if plan_text else {}
    task_refs = plan_paths.find_references(task_text, paths) if task_text else {}
    plan_sfx = plan_paths.find_suffix_references(plan_text, paths) if plan_text else {}
    task_sfx = plan_paths.find_suffix_references(task_text, paths) if task_text else {}
    dirs = sorted({d for p in paths for d in _ancestors(p)})
    dir_refs = plan_paths.find_dir_references(plan_text, dirs) if plan_text else {}

    other_ev: "dict[str, list[str]]" = {}
    for oid, ofile in others:
        otask_raw = _read(ofile)
        otext = plan_paths.task_body_text(otask_raw) if otask_raw else ""
        _unused, oplan = task_and_plan(oid, repo)
        oplan_text = _read(os.path.join(repo, oplan)) if oplan else ""
        for p in plan_paths.find_references(oplan_text or "", paths):
            other_ev.setdefault(p, []).append(f"other_plan:t{oid}")
        for p in plan_paths.find_references(otext, paths):
            other_ev.setdefault(p, []).append(f"other_task:t{oid}")
        for p in plan_paths.find_suffix_references(oplan_text or "", paths):
            other_ev.setdefault(p, []).append(f"other_plan_suffix:t{oid}")
        for p in plan_paths.find_suffix_references(otext, paths):
            other_ev.setdefault(p, []).append(f"other_task_suffix:t{oid}")
        for p in task_commits(oid, repo, checkout):
            if p in paths:
                other_ev.setdefault(p, []).append(f"other_commit:t{oid}")

    def shared_tokens(p: str) -> "list[str]":
        toks = _mention_tokens("f_plan", plan_refs.get(p, []))
        toks += _mention_tokens("f_task", task_refs.get(p, []))
        toks += _mention_tokens("f_plan_suffix", plan_sfx.get(p, []))
        toks += _mention_tokens("f_task_suffix", task_sfx.get(p, []))
        if p not in plan_refs:
            for d in _ancestors(p):
                if d in dir_refs:
                    toks.append(f"f_plan_dir:{d}")
                    break
        return toks

    for p in paths:
        others_here = other_ev.get(p, [])
        if p in f_commits:
            toks = [f"f_commits:{len(f_commits[p])}"] + shared_tokens(p) + others_here
            out.append(f"PART|committed|{','.join(f_commits[p])}|{','.join(toks)}|{p}")
        if p in dirty:
            toks = []
            if p in f_commits:
                toks.append(f"f_commit_earlier:{len(f_commits[p])}")
            toks += shared_tokens(p)
            if p in base_dirty:
                toks.append("baseline_dirty")
            toks += others_here
            out.append(f"PART|dirty|{','.join(dirty[p])}|{','.join(toks) or '-'}|{p}")

    if unrepresentable:
        out.append(f"WARN:unrepresentable_paths|{len(unrepresentable)}")
    return out


def main(argv) -> int:
    ap = argparse.ArgumentParser(prog="shadow_scope.py")
    ap.add_argument("task_id")
    ap.add_argument("--checkout", required=True)
    ap.add_argument("--checkout-source", default="explicit")
    args = ap.parse_args(argv[1:])
    m = TASK_ID_RE.match(args.task_id)
    if not m:
        sys.stderr.write(f"shadow_scope: malformed task id: {args.task_id}\n")
        return 2
    if not os.path.isdir(args.checkout):
        sys.stderr.write(f"shadow_scope: checkout is not a directory: {args.checkout}\n")
        return 2
    lines = build(m.group(1), os.getcwd(), os.path.abspath(args.checkout),
                  args.checkout_source)
    out = "".join(line + "\n" for line in lines)
    sys.stdout.buffer.write(out.encode("utf-8", "surrogateescape"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
