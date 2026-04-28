---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [macos]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-28 10:01
updated_at: 2026-04-28 11:45
---

## Context

Today `ait setup` only writes `tmux.default_session` and `git_tui` keys into `aitasks/metadata/project_config.yaml` (`setup_tmux_default_session()`, `aitask_setup.sh:2886`). It never touches `~/.tmux.conf`. On fresh macOS installs that means: no mouse mode, no right-click menu, default bottom status bar — none of the affordances aitasks TUIs assume the user has.

This child adds an opt-in step to `ait setup` that offers a small starter `~/.tmux.conf` ONLY when no existing tmux config is detected. Always opt-in; never overwrite an existing user file.

## Why split here

Bigger surface than the other two children: touches `seed/tmux.conf` (new file), `install.sh` (new `install_seed_tmux_conf()`), and `aitask_setup.sh` (new `setup_starter_tmux_conf()`). It also requires the full install-flow integration test described in CLAUDE.md "Test the full install flow for setup helpers" — `install.sh` deletes `seed/` at line 1030, so the helper must read from a post-install location, not from `seed/` directly.

## Key Files to Modify

1. **NEW** `seed/tmux.conf` — small (~30 lines), well-commented starter config.
2. `install.sh` — add `install_seed_tmux_conf()` that copies `seed/tmux.conf` → `.aitask-scripts/templates/tmux.conf`. Wire it into the `main()` install flow alongside the other `install_seed_*` calls, BEFORE the `rm -rf "$INSTALL_DIR/seed"` cleanup at line 1030.
3. `.aitask-scripts/aitask_setup.sh` — add `setup_starter_tmux_conf()` reading from `$SCRIPT_DIR/templates/tmux.conf`. Slot it into `main()` immediately after `setup_tmux_default_session` (current line 3040), before `setup_userconfig`.

## Reference Files for Patterns

- `install.sh:285` — `install_seed_profiles()`: precedent for the seed→stable-location copy pattern.
- `install.sh:317` — `install_seed_project_config()`: another `merge_seed`-using example.
- `install.sh:976–1027` — main install sequence; the new call slots in before line 1030 (`rm -rf "$INSTALL_DIR/seed"`).
- `aitask_setup.sh:558–598` — `install_global_shim()`: precedent for writing files under `$HOME` (uses `mkdir -p`, idempotent re-runs OK).
- `aitask_setup.sh:2886` (`setup_tmux_default_session`) — adjacent function, similar interactive-prompt pattern (`if [[ -t 0 ]]; then read -r ...`).
- `aitask_setup.sh:3040` (call to `setup_tmux_default_session` inside `main()`) — exact insertion point.
- CLAUDE.md "Test the full install flow for setup helpers" section — REQUIRED reading; verification MUST follow the `bash install.sh --dir /tmp/scratch` pattern.

## Implementation Plan

### Step 1 — `seed/tmux.conf` (new file)

```
# aitasks-recommended starter tmux.conf
# Installed by `ait setup` only when no existing ~/.tmux.conf or
# ~/.config/tmux/tmux.conf is present. Safe to edit or replace.

# --- Mouse and right-click menu ---
set -g mouse on

# --- Status bar at top with window names ---
set -g status-position top
set -g status-interval 5
set -g status-left-length 30
set -g status-right-length 60
set -g status-left  "#[bold]#S#[default] | "
set -g status-right "%Y-%m-%d %H:%M"

# --- Sensible defaults ---
set -g base-index 1
setw -g pane-base-index 1
set -g renumber-windows on
set -g history-limit 10000
set -g default-terminal "screen-256color"
set -ga terminal-overrides ",*256col*:Tc"

# --- Window/pane status hints ---
set -g window-status-current-format " #I:#W "
set -g window-status-format " #I:#W "
```

### Step 2 — `install.sh::install_seed_tmux_conf()`

Add next to other `install_seed_*` definitions (after line 327, before `install_seed_reviewtypes`):

```bash
# --- Install starter tmux.conf template ---
install_seed_tmux_conf() {
    local src="$INSTALL_DIR/seed/tmux.conf"
    local dest_dir="$INSTALL_DIR/.aitask-scripts/templates"
    local dest="$dest_dir/tmux.conf"
    if [[ ! -f "$src" ]]; then
        warn "No seed/tmux.conf in tarball — skipping starter tmux.conf"
        return
    fi
    mkdir -p "$dest_dir"
    cp "$src" "$dest"
    info "  Installed starter tmux.conf template"
}
```

Wire into `main()` alongside the other seed installs, e.g. after `install_seed_project_config` and before the `rm -rf "$INSTALL_DIR/seed"` cleanup:

```bash
info "Installing starter tmux.conf template..."
install_seed_tmux_conf
```

### Step 3 — `.aitask-scripts/aitask_setup.sh::setup_starter_tmux_conf()`

```bash
setup_starter_tmux_conf() {
    local template="$SCRIPT_DIR/templates/tmux.conf"

    if [[ ! -f "$template" ]]; then
        # Template not installed (e.g. dev tree without install.sh run); silent skip.
        return
    fi

    # Detect existing tmux config — never overwrite.
    if [[ -f "$HOME/.tmux.conf" ]]; then
        info "tmux config already present at ~/.tmux.conf — leaving untouched."
        return
    fi
    if [[ -f "$HOME/.config/tmux/tmux.conf" ]]; then
        info "tmux config already present at ~/.config/tmux/tmux.conf — leaving untouched."
        return
    fi

    # Decide install path: prefer ~/.config/tmux/ if that dir already exists,
    # else default to ~/.tmux.conf.
    local target=""
    if [[ -d "$HOME/.config/tmux" ]]; then
        target="$HOME/.config/tmux/tmux.conf"
    else
        target="$HOME/.tmux.conf"
    fi

    # Non-interactive: skip silently — never write to $HOME without consent.
    if [[ ! -t 0 ]]; then
        return
    fi

    info "No tmux config detected at $target."
    printf "  Install aitasks-recommended starter tmux.conf? Enables: mouse on, right-click menu, top status bar, sensible defaults. [y/N] "
    local answer=""
    read -r answer
    case "${answer:-N}" in
        [Yy]*) ;;
        *) info "Skipped starter tmux.conf."; return ;;
    esac

    mkdir -p "$(dirname "$target")"
    cp "$template" "$target"
    success "Installed starter tmux.conf at $target"
}
```

Add the call inside `main()` directly after `setup_tmux_default_session` and before `setup_userconfig`:

```bash
    setup_tmux_default_session
    echo ""

    setup_starter_tmux_conf
    echo ""

    setup_userconfig
```

### Step 4 — CLAUDE.md compliance

- **Whitelisting (5-touchpoint):** N/A — `setup_starter_tmux_conf` is a function inside the existing `aitask_setup.sh`, not a new helper script under `.aitask-scripts/`. No claude/gemini/opencode/codex permission entries are needed.
- **Setup vs upgrade verb:** All user-facing strings use "ait setup" framing (this is first-run setup), never "ait upgrade".

## Verification Steps

CLAUDE.md mandates the full install flow for setup helpers. Do NOT shortcut by hand-dropping `seed/tmux.conf` into a scratch — `install.sh` deletes `seed/` so the helper must read from `.aitask-scripts/templates/tmux.conf`.

1. **Fresh install path (golden):**
   ```bash
   bash install.sh --dir /tmp/scratch_t688_3
   ```
   Confirm `/tmp/scratch_t688_3/.aitask-scripts/templates/tmux.conf` exists and matches `seed/tmux.conf` byte-for-byte.

   ```bash
   mkdir -p /tmp/fakehome_t688_3
   HOME=/tmp/fakehome_t688_3 bash -c 'cd /tmp/scratch_t688_3 && ./ait setup'
   ```
   Answer `y` at the tmux.conf prompt. Verify `/tmp/fakehome_t688_3/.tmux.conf` is created and matches the template byte-for-byte (`diff /tmp/scratch_t688_3/.aitask-scripts/templates/tmux.conf /tmp/fakehome_t688_3/.tmux.conf` returns no diff).

2. **Decline path:** Same scratch + fresh fake HOME. Re-run setup; answer `N` (or just press enter). Verify NO `~/.tmux.conf` was created.

3. **Already-configured ~/.tmux.conf:** Pre-create `/tmp/fakehome_t688_3b/.tmux.conf` with arbitrary contents. Run setup with `HOME=/tmp/fakehome_t688_3b`. Verify the prompt is NOT shown and the file is byte-for-byte unchanged.

4. **Already-configured ~/.config/tmux/tmux.conf:** Same as 3 but `~/.config/tmux/tmux.conf`. Verify prompt skipped and file untouched.

5. **~/.config/tmux/ exists but no config inside:** Pre-create empty dir `/tmp/fakehome_t688_3c/.config/tmux/`. Run setup; answer `y`. Verify the file lands at `~/.config/tmux/tmux.conf`, NOT `~/.tmux.conf`.

6. **Non-interactive run:** `HOME=/tmp/fakehome_t688_3d ./ait setup < /dev/null`. Confirm no prompt is emitted, no file is written, and setup exits 0.

7. **Bash portability:** The function uses `[[ ]]`, `local`, `printf`, `read -r`, and `mkdir -p` — all bash 4+ compatible. Shebang is `#!/usr/bin/env bash` (already correct in the parent file).

## Acceptance Criteria

- After `bash install.sh --dir <scratch>`, `<scratch>/.aitask-scripts/templates/tmux.conf` exists.
- After `HOME=<fake> ./ait setup` on a fresh fake HOME with NO tmux config, the user is offered the prompt; on `y`, the file lands at `~/.tmux.conf` byte-for-byte equal to the template.
- Pre-existing `~/.tmux.conf` or `~/.config/tmux/tmux.conf` is NEVER overwritten and the prompt is silent.
- `~/.config/tmux/` directory presence routes the install path to `~/.config/tmux/tmux.conf` instead of `~/.tmux.conf`.
- Non-interactive runs produce no prompt and no file write.
- No new helper scripts under `.aitask-scripts/` (so no 5-touchpoint whitelisting required).

## Notes for sibling tasks

- t688_1 (bug fix) and t688_2 (textual upgrade visibility) are independent of this child; this child neither blocks nor is blocked by them.
- The new directory `.aitask-scripts/templates/` may be reused by future template-based setup helpers; keep its purpose narrow (runtime-read assets the helper copies into `$HOME` or other user-owned locations).
