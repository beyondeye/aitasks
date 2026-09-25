"""Merge / check the aitasks SessionStart hook in a Claude Code settings.json (t1849).

The one definition of "is the aitasks session hook installed", shared by the
installer (`aitask_setup.sh::merge_claude_hooks`) and the status probe
(`lib/claude_hook_status.sh`). "Installed" means exactly "merging the seed would
change nothing", so the two can never disagree about identity.

Usage:
    claude_hooks_merge.py merge <dest> <seed>   print the merged JSON (exit 0),
                                                or exit non-zero with a message
    claude_hooks_merge.py check <dest> <seed>   exit 0 installed, 1 missing
                                                (including an absent <dest>),
                                                2 invalid <dest> or seed

Merges ONLY hooks.SessionStart, deduping by (matcher, command). Every other key
-- other hook events, permissions, env, anything the user added -- is preserved
verbatim. Kept to syntax any python3 the framework may meet can run: the
installer falls back to a bare `python3`.
"""

import copy
import json
import os
import sys

EXIT_INSTALLED = 0
EXIT_MISSING = 1
EXIT_INVALID = 2


class InvalidSettings(Exception):
    pass


def norm(cmd):
    # Identity of a hook command = which script it runs, not how it spells the
    # path. $CLAUDE_PROJECT_DIR is expanded by the agent, and a user may have
    # hardcoded an absolute path to the SAME script -- installing a second copy
    # would run the hook twice per session. Collapse every spelling that ends in
    # the same repo-relative .aitask-scripts/ path.
    cmd = (cmd or "").replace("$CLAUDE_PROJECT_DIR", "").replace("${CLAUDE_PROJECT_DIR}", "").strip()
    marker = ".aitask-scripts/"
    idx = cmd.rfind(marker)
    if idx != -1:
        return cmd[idx:]
    return cmd.lstrip("/")


def merge(existing, seed):
    """Merge ``seed``'s SessionStart groups into ``existing`` in place."""
    if not isinstance(existing, dict):
        raise InvalidSettings("settings is not an object")
    hooks = existing.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise InvalidSettings("hooks is not an object")
    groups = hooks.setdefault("SessionStart", [])
    if not isinstance(groups, list):
        raise InvalidSettings("hooks.SessionStart is not an array")

    for seed_group in seed.get("hooks", {}).get("SessionStart", []):
        matcher = seed_group.get("matcher")
        target = None
        for g in groups:
            if isinstance(g, dict) and g.get("matcher") == matcher:
                target = g
                break
        if target is None:
            groups.append(copy.deepcopy(seed_group))
            continue
        entries = target.setdefault("hooks", [])
        if not isinstance(entries, list):
            raise InvalidSettings("a SessionStart group's hooks is not an array")
        have = {norm(h.get("command")) for h in entries if isinstance(h, dict)}
        for h in seed_group.get("hooks", []):
            if norm(h.get("command")) not in have:
                entries.append(copy.deepcopy(h))
                have.add(norm(h.get("command")))
    return existing


def _load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        raise InvalidSettings("%s: %s" % (path, e))


def _load_seed(path):
    seed = _load(path)
    if not isinstance(seed, dict):
        raise InvalidSettings("%s: seed is not an object" % path)
    return seed


def cmd_merge(dest, seed_path):
    try:
        merged = merge(_load(dest), _load_seed(seed_path))
    except InvalidSettings as e:
        sys.stderr.write("%s\n" % e)
        return EXIT_INVALID
    print(json.dumps(merged, indent=2))
    return 0


def cmd_check(dest, seed_path):
    try:
        seed = _load_seed(seed_path)
        if not os.path.exists(dest):
            return EXIT_MISSING
        existing = _load(dest)
        merged = merge(copy.deepcopy(existing), seed)
    except InvalidSettings as e:
        sys.stderr.write("%s\n" % e)
        return EXIT_INVALID
    return EXIT_INSTALLED if merged == existing else EXIT_MISSING


def main(argv):
    if len(argv) != 4 or argv[1] not in ("merge", "check"):
        sys.stderr.write("usage: claude_hooks_merge.py merge|check <dest> <seed>\n")
        return EXIT_INVALID
    if argv[1] == "merge":
        return cmd_merge(argv[2], argv[3])
    return cmd_check(argv[2], argv[3])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
