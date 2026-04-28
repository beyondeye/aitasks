---
Task: t688_3_starter_tmux_conf_in_setup.md
Parent Task: aitasks/t688_board_pick_crash_and_starter_tmux_conf_in_setup.md
Sibling Tasks: aitasks/t688/t688_1_fix_select_set_options_crash_textual_8_0.md, aitasks/t688/t688_2_surface_textual_upgrade_in_setup.md
Archived Sibling Plans: aiplans/archived/p688/p688_*_*.md
Worktree: (none — working on current branch per profile 'fast')
Branch: main
Base branch: main
---

# Plan — t688_3: Add opt-in starter `~/.tmux.conf` to `ait setup`

## Context

`ait setup` configures `aitasks/metadata/project_config.yaml`'s `tmux:` block (default session name, git_tui) but never touches `~/.tmux.conf`. On a fresh macOS install the user gets no mouse mode, no right-click menu, and the default bottom status bar — none of the affordances aitasks TUIs assume.

This child adds an opt-in step that offers a small starter config when no existing tmux config is detected. Always opt-in. Never overwrite an existing user file.

## Approach

Three-piece change: a new seed asset, an install.sh hook to relocate it to a stable runtime location (because `install.sh` deletes `seed/` at line 1030), and a setup-time helper that prompts the user and copies the template into `$HOME` on consent.

## Critical Files

- **NEW** `seed/tmux.conf` — small (~30 lines), well-commented starter.
- `install.sh` — add `install_seed_tmux_conf()` that copies `seed/tmux.conf` → `.aitask-scripts/templates/tmux.conf` at install time. Wire into `main()` BEFORE `rm -rf "$INSTALL_DIR/seed"` at line 1030.
- `.aitask-scripts/aitask_setup.sh` — add `setup_starter_tmux_conf()` reading from `$SCRIPT_DIR/templates/tmux.conf`. Slot into `main()` immediately after `setup_tmux_default_session` (current line 3040), before `setup_userconfig`.

## Reference Files for Patterns

- `install.sh:285` — `install_seed_profiles()`: precedent for the seed→stable-location copy pattern.
- `install.sh:317` — `install_seed_project_config()`: another seed installer.
- `install.sh:976–1027` — main install sequence (where to wire the new call).
- `aitask_setup.sh:558` — `install_global_shim()`: precedent for writing under `$HOME` with `mkdir -p`.
- `aitask_setup.sh:2886` — `setup_tmux_default_session`: adjacent function with `if [[ -t 0 ]]; then read -r ...` interactive pattern.
- `aitask_setup.sh:3040` — exact insertion point inside `main()`.
- CLAUDE.md "Test the full install flow for setup helpers" — verification MUST exercise `bash install.sh --dir <scratch>` first, NOT a hand-dropped seed.

## Implementation Steps

### Step 1 — Create `seed/tmux.conf`

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

### Step 2 — Add `install_seed_tmux_conf()` to `install.sh`

Insert after `install_seed_project_config()` (around line 327):

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

Wire into `main()` between `install_seed_project_config` (line 988–989) and `install_seed_reviewtypes` (line 991–992):

```bash
    info "Installing project config..."
    install_seed_project_config

    info "Installing starter tmux.conf template..."
    install_seed_tmux_conf

    info "Installing review types..."
    install_seed_reviewtypes
```

### Step 3 — Add `setup_starter_tmux_conf()` to `.aitask-scripts/aitask_setup.sh`

Insert immediately after `setup_tmux_default_session()` (after the current closing `}` at line 2932):

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

Wire into `main()` between `setup_tmux_default_session` (line 3040) and `setup_userconfig`:

```bash
    setup_tmux_default_session
    echo ""

    setup_starter_tmux_conf
    echo ""

    setup_userconfig
```

### Step 4 — CLAUDE.md compliance

- **Whitelisting (5-touchpoint):** N/A — `setup_starter_tmux_conf` is a function inside the existing `aitask_setup.sh`, not a new helper script under `.aitask-scripts/`. None of the 5 settings files need updates.
- **Setup vs upgrade verb:** All user-facing strings frame this as first-run setup; never use "upgrade" wording.
- **Test full install flow:** Verification MUST exercise `bash install.sh --dir <scratch>` first; NOT a hand-dropped seed in scratch.

## Verification

CLAUDE.md mandates the full install flow for setup helpers (because `install.sh` deletes `seed/` at line 1030, runtime helpers must read from a post-install location).

1. **Fresh install (golden):**

   ```bash
   bash install.sh --dir /tmp/scratch_t688_3
   diff /tmp/scratch_t688_3/seed/tmux.conf \
        /tmp/scratch_t688_3/.aitask-scripts/templates/tmux.conf 2>&1 || true
   # seed/ was deleted; first arg fails — that's expected.
   # The relevant assertion is that templates/tmux.conf exists:
   test -f /tmp/scratch_t688_3/.aitask-scripts/templates/tmux.conf && echo OK
   ```

   Then exercise the helper:

   ```bash
   mkdir -p /tmp/fakehome_t688_3
   HOME=/tmp/fakehome_t688_3 bash -c 'cd /tmp/scratch_t688_3 && ./ait setup'
   ```

   Answer `y` at the tmux.conf prompt. Verify:

   ```bash
   diff /tmp/scratch_t688_3/.aitask-scripts/templates/tmux.conf \
        /tmp/fakehome_t688_3/.tmux.conf
   # Should produce no output (byte-for-byte identical).
   ```

2. **Decline path:** Same scratch, fresh `HOME=/tmp/fakehome_t688_3b`. Re-run setup; answer `N` (or just press enter). Verify `/tmp/fakehome_t688_3b/.tmux.conf` does NOT exist.

3. **Pre-existing `~/.tmux.conf`:** Pre-create `/tmp/fakehome_t688_3c/.tmux.conf` with arbitrary contents. Run setup with `HOME=/tmp/fakehome_t688_3c`. Verify the prompt is NOT shown and the file is byte-for-byte unchanged.

4. **Pre-existing `~/.config/tmux/tmux.conf`:** Same as 3 but at `~/.config/tmux/tmux.conf`. Verify the prompt is NOT shown and the file is unchanged.

5. **`~/.config/tmux/` exists, no config inside:** Pre-create empty dir `/tmp/fakehome_t688_3e/.config/tmux/`. Run setup; answer `y`. Verify the file lands at `~/.config/tmux/tmux.conf`, NOT `~/.tmux.conf`.

6. **Non-interactive run:** `HOME=/tmp/fakehome_t688_3f ./ait setup < /dev/null`. Confirm no prompt is emitted, no file is written, and setup exits 0.

## Step 9 (Post-Implementation) reference

After Step 8 (commit code + plan separately), run:

```bash
./.aitask-scripts/aitask_archive.sh 688_3
./ait git push
```
