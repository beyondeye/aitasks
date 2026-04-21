---
title: "Setup & Install"
linkTitle: "Setup & Install"
weight: 10
description: "ait setup and ait install commands"
---

## ait setup

Cross-platform dependency installer and configuration tool. This is typically the first command to run after installing aitasks.

> **Run from the project root.** Both `ait setup` and the curl installer must be executed from the root of your git repository (the directory containing `.git/`). aitasks stores task files, plans, skills, and configuration inside the repo and relies on git for task IDs, locking, and multi-machine synchronization.

```bash
ait setup
```

**Auto-bootstrap:** When run via the global shim (`~/.local/bin/ait`) in a directory without an existing aitasks installation, `ait setup` automatically downloads and installs the latest release before running the setup flow. This lets you bootstrap new projects with a single command — no need to run the `curl | bash` installer separately.

**Guided setup flow:**

1. **OS detection** — Automatically detects: macOS, Arch Linux, Debian/Ubuntu, Fedora/RHEL, WSL
2. **CLI tools** — Installs missing tools (`fzf`, `gh`/`glab`/`bkt`, `jq`, `git`, `zstd`) via the platform's package manager (pacman, apt, dnf, brew). Auto-detects git remote platform to install the right CLI tool (`gh` for GitHub, `glab` for GitLab, `bkt` for Bitbucket). On macOS, requires [Homebrew](https://brew.sh) and also installs bash 5.x, Python 3, and coreutils
3. **Version checks** — Verifies Bash >= 4.0 and Python >= 3.9. On macOS, offers to install/upgrade via Homebrew if versions are too old
4. **Git repo** — Verifies you are inside a git repository. If no `.git/` is found, explains that aitasks is tightly integrated with git and asks to confirm this is the correct project directory before offering to run `git init`
5. **Draft directory** — Creates `aitasks/new/` for local draft tasks and adds it to `.gitignore` so drafts stay local-only
6. **Task ID counter** — Initializes the `aitask-ids` counter branch on the remote for atomic task numbering. This prevents duplicate task IDs when multiple PCs create tasks against the same repo
7. **Python venv** — Creates virtual environment at `~/.aitask/venv/` and installs `textual` (>=8.1), `pyyaml`, `linkify-it-py`, `tomli` with pinned versions. This is also where optional stats-TUI chart support is enabled: setup prompts `Install plotext for 'ait stats-tui' chart panes? [y/N]`. Choosing `y` installs `plotext`; choosing `N` keeps setup complete but leaves `ait stats-tui` running without the chart panes (text stats via `ait stats` still work). Recreates the venv if existing Python is too old
8. **Global shim** — Installs `ait` shim at `~/.local/bin/ait` that finds the nearest project-local `ait` dispatcher by walking up the directory tree. Warns if `~/.local/bin` is not in PATH
9. **Claude Code permissions** — Shows the recommended permission entries, then prompts Y/n to install them into `.claude/settings.local.json`. If settings already exist, merges permissions (union of allow-lists)
10. **Version check** — Compares local version against latest GitHub release and suggests update if newer

Setup also ensures the shared project config file exists at `aitasks/metadata/project_config.yaml`. That file is seeded from `seed/project_config.yaml`, tracked in git, and includes project-wide workflow settings such as:

- `codeagent_coauthor_domain: aitasks.io` — the email domain used for custom code-agent `Co-Authored-By` trailers
- `verify_build` — the post-implementation build verification command or command list

If you re-run `ait setup` after customizing `codeagent_coauthor_domain`, the existing value is preserved.

### Claude Code Permissions

When you run `ait setup`, it offers to install default Claude Code permissions into `.claude/settings.local.json`. These permissions allow aitask skills to execute common operations (file listing, git commands, aiscript invocations) without prompting for manual approval each time.

The default permissions are defined in `seed/claude_settings.local.json` and stored at `aitasks/metadata/claude_settings.seed.json` during installation. If a `.claude/settings.local.json` already exists, the setup merges permissions (union of both allow-lists, preserving any existing entries). You can decline the permissions prompt and configure them manually later.

Re-run `ait setup` at any time to add the default permissions if you skipped them initially.

To enable optional chart rendering for `ait stats-tui` later, re-run `ait setup` and answer `y` to the `plotext` prompt in the Python venv step.

---

## ait install

Update the aitasks framework to a new version.

```bash
ait install                    # Update to latest release
ait install latest             # Same as above
ait install 0.2.1              # Install specific version
```

**How it works:**

1. Resolves the target version (queries GitHub API for latest, or validates the provided version number)
2. Checks if already up to date (skips if versions match)
3. Downloads `install.sh` from the target version's git tag
4. Runs the installer with `--force`, which shows the changelog between current and target versions and asks for confirmation
5. Performs the full installation (tarball download, skill installation, setup)
6. Clears the update check cache

**Automatic update check:**

The `ait` dispatcher checks for new versions once per day (at most). When a newer version is available, it shows a brief notice suggesting `ait install latest`. The check runs in the background to avoid adding latency. It is skipped for `help`, `version`, `install`, and `setup` commands.

---

**Next:** [Task Management]({{< relref "/docs/commands/task-management" >}})
