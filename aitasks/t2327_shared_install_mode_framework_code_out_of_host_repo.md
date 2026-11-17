---
priority: medium
effort: high
depends: [2325]
issue_type: feature
status: Ready
labels: [ait_setup, installation, install_scripts]
created_at: 2026-11-17 13:01
updated_at: 2026-11-17 13:09
artifacts:
  - handle: art:trail-install-setup
    kind: implementation_trail
    name: Installation and setup improvements
---

Add a "shared install" mode: the framework's code lives in a per-machine, per-version store instead of being committed into every host repository. The repository commits only which framework version it uses, plus its own data and configuration.

This is a complex task and must be decomposed into child tasks at planning time.

## Why

Today every host repo commits the whole framework (an "in-repo install"). Measured in this repo: `.aitask-scripts/` 569 files / 12.4 MB, `.claude/skills/` 171 files, `.agents/skills/` 82, `.opencode/` 120 — about 950 files and 15 MB. Consequences: every upgrade is a large commit, framework files pollute grep/review/agent context, local edits drift, branches at different framework versions conflict, and each repo on a machine carries its own copy.

The pattern already exists in three places: the `ait-testmap` engine installs to `$AITASKS_HOME/engine/v<V>/` keyed off the committed `VERSION`; the Python venv is per-user; rendered per-profile skill variants are gitignored and regenerated.

## Decisions already taken (2026-11-17, with the user)

1. **Two install modes, one layout.** "In-repo install" (today's behaviour) and "shared install". The in-repo layout is the single canonical layout; the store holds an unmodified copy of the same tree at `$AITASKS_HOME/framework/v<V>/`, and a shared-install project gets a gitignored `.aitask-scripts` symlink into it. No path in any script, skill, permission list or doc gets a second form.
2. **Resolution rule.** A real `.aitask-scripts/` directory in the project always wins; the store is used only when the project has a symlink or nothing.
3. **This repository (framework source) keeps the current layout.** `ait setup` / `ait upgrade` run here must refuse to convert it or replace the real directory with a symlink — explicit refusal, with a test.
4. **Rollout.** Shared is opt-in at first (`ait setup --shared` or equivalent); in-repo stays the default. Conversion works in both directions by explicit command only. The end goal is shared as the default for new projects, flipped once it has run on real projects.
5. **Skills.** In a shared install the framework's skill files still sit in the project's skill directories (`.claude/skills/`, `.agents/skills/`, `.opencode/`) because agents discover them only there, but they are not committed: `ait setup` writes them from the store and they are gitignored. The ignore rules list only framework-owned skill directories, generated from a manifest in the store, so a host project's own skills stay committed. No exception for headless/cloud skills (see 7).
6. **Fresh clone.** `./ait` in a shared-install project whose pinned version is not in the store stops and tells the user to run `ait setup`. No automatic download on first run.
7. **Cloud sessions** (`aitask-pickweb`, `aitask-pickrem`) require an in-repo install for now.
8. **Local edits to framework files** are supported only in an in-repo install. No overlay mechanism.

## What stays committed in a shared install

- Task data and `aitasks/metadata/` configuration (task types, labels, gates, profiles, project config).
- User-customised content: `aireviewguides/`, the doc-update guide, agent settings merges.
- The version pin (`VERSION`, ideally with a checksum) and a thin `ait` shim that resolves it.

## To investigate during planning

- **Runtime writes into `.aitask-scripts/`** (bytecode caches, generated files, anything setup writes there). A store shared between projects must be safe to treat as read-only.
- **Where the pin lives.** `VERSION` is currently inside `.aitask-scripts/`, which becomes a symlink; the pin and the `ait` shim need a committed home outside it.
- **Framework data in `aitasks/metadata/`.** The installer copies Codex/OpenCode skill staging (`codex_skills/`, `opencode_skills/`, `opencode_commands/`) and model lists there; decide which of it stays committed.
- **Store lifecycle.** Publication locking and atomic replace (reuse the engine slot mechanics in `lib/engine_install.sh`), pruning unused versions (`ait engine prune` analogue), checksum verification of the downloaded tarball.
- **`ait upgrade` in shared mode** becomes a pin bump plus store population; retired-file pruning no longer touches the repo.
- **Symlink portability** on the supported platforms, and behaviour of git worktrees (`aiwork/`, crews) that need the same symlink.
- **Permission allowlists and hooks** that name `./.aitask-scripts/...` paths: confirm they resolve through the symlink in each supported agent.
- **`ait doctor` (t2325)** must report store missing / version mismatch / mode, and recognise the source checkout.
- Website docs: installation pages, and a page explaining the two modes and how to switch.

## Related

- t2325 `ait doctor` (dependency), t2326 unattended `ait setup` (the cloud path for in-repo installs).
- t623 more installation methods (brew, Linux packages): how the framework reaches the machine; complementary.
