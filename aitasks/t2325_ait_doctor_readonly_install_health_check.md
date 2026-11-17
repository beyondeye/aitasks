---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [ait_setup, installation]
created_at: 2026-11-17 12:52
updated_at: 2026-11-17 12:52
---

Add `ait doctor`: a read-only health check that reports whether the framework is correctly installed and configured in this project and on this machine.

## Why

`ait setup` installs and repairs, but it mutates (installs packages, creates branches, writes and commits config, prompts). There is no way to ask "is this install healthy?" without changing anything. Existing checks are narrow: `ait git-health` (data worktree), the `TESTMAP:<state>` line setup prints, `aitask_skill_verify.sh` (developer check). Several required pieces live outside the project directory even when all framework files are committed in the repo (an "in-repo install"): the `ait-testmap` engine in `$AITASKS_HOME/engine/v<VERSION>/`, the per-user Python venv, CLI tools, the global `ait` shim. A fresh clone therefore has scripts and skills but no engine and no venv.

`ait doctor` is also a prerequisite for the planned "shared install" mode (framework code in a per-machine store instead of the repo), which needs a reliable way to report a missing or mismatched store.

## Requirements

- Read-only. Never installs, writes, commits or prompts.
- Non-zero exit when a required check fails; optional tiers (PyPy, chat, dev) are reported, not failed.
- One parseable line per check (stable prefix, state, detail) so skills and cloud bootstraps can gate on it, plus a human summary.
- Each failure names its fix by verb, following the CLI convention in CLAUDE.md: `ait setup` for missing/broken/repair, `ait upgrade` only for version mismatch.
- Reuse setup's own predicates (the import lists `AIT_IMPORTS_*`, the engine-state probe behind `report_testmap_state`, the CLI tool list) by extracting them into a shared lib. Do not keep a second list that can drift.
- Recognise a framework source checkout (this repo: `goengines/` and `seed/` present) and adjust: do not flag uncommitted framework edits or version drift, accept the `dev` engine slot.

## Checks

1. Framework files: present, matching `.aitask-scripts/VERSION`, no retired scripts/skills left over (`retired_*_manifest.txt`).
2. Engine: slot present for the pinned version; platform supported (release assets exist only for linux/darwin on amd64/arm64).
3. Python: venv exists, required imports succeed, optional tiers reported.
4. CLI tools: required tools, bash version, `gh`/`glab` authentication.
5. Git layout: data branch and worktree, lock branch, gitignore entries, hooks.
6. Agent surfaces: skills present/rendered per configured agent, settings and permission seeds merged.
7. Per-user state: global shim, legacy `~/.aitask` root, project registry entry.

## Notes

- t1364 mentions an "`ait doctor`-style check" for unparseable task filenames; consider whether that check belongs here.
- Tests must never reach a real `~/.aitask` / `$AITASKS_HOME`: run under a scratch `HOME`.
- Add the dispatcher entry, help text and website docs.
