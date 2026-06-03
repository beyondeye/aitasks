# Shell Conventions

General shell style for the aitasks framework's bash scripts. Read this when
writing or editing any shell script under `.aitask-scripts/`. Shell-specific
portability quirks (BSD vs GNU tooling) live in
`aidocs/framework/sed_macos_issues.md`; language-agnostic code style lives in
`aidocs/framework/code_conventions.md`.

- **Shebang:** Always `#!/usr/bin/env bash`, never `#!/bin/bash`. macOS system
  bash is 3.2; `env bash` picks up brew-installed bash 5.x from PATH.
- All scripts use `set -euo pipefail`.
- Error helpers: `die()` (fatal), `warn()`, `info()` from `terminal_compat.sh`.
- Guard against double-sourcing with `_AIT_*_LOADED` variables.
- Platform detection: `detect_platform()` returns `github|gitlab|bitbucket`
  from git remote URL.
- Task/plan resolution functions live in `task_utils.sh`.
- **Platform-specific CLIs (gh/glab/bitbucket):** encapsulate in bash scripts
  that route via `detect_platform()`. `SKILL.md` must call a script
  subcommand, never `gh`, `glab`, or the Bitbucket API directly.
- **Archive format details (tar.gz/tar.zst/zstd):** encapsulate in bash
  scripts. `SKILL.md` must call a script subcommand — never raw archive
  tooling. Format migrations then happen in one place.
- Use `sed_inplace()` from `terminal_compat.sh` — never `sed -i`.
- **System libs added to `./ait`'s source-on-startup chain must also be added
  to `tests/lib/test_scaffold.sh::setup_fake_aitask_repo()` in the same PR.**
  43 tests scaffold a fake `.aitask-scripts/lib/` via that helper; a missing
  entry crashes every one of them with `No such file or directory` the next
  time `./ait` (or a helper that learns to source the new lib) is invoked
  from the fake repo. Current baseline: `aitask_path.sh`, `terminal_compat.sh`,
  `python_resolve.sh`, `yaml_utils.sh`, `cross_repo_reexec.sh`.
- **Avoid `claude -p` / `claude --print` (headless print mode) in scripts and
  skills.** Claude Code bills headless print mode at a higher per-token rate
  than interactive invocations against an existing session. Default to
  interactive mode; gate any genuinely non-interactive need (e.g. CI) behind an
  explicit opt-in flag (as `ait codeagent --headless` does for `batch-review`).
  This applies to skill `.md` files too. See
  `aidocs/framework/skill_authoring_conventions.md` ("Do not route skill
  invocation through `claude -p`") for the skill-rendering rationale.

> **macOS portability quirks** (BSD sed vs GNU sed, `grep -P` unavailable,
> `wc -l` padding, `mktemp --suffix`, `base64 -D` vs `-d`): see
> `aidocs/framework/sed_macos_issues.md`.
