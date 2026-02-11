---
priority: high
effort: medium
depends: [t85_2, t85_5]
issue_type: feature
status: Done
labels: [bash, aitasks]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-11 10:00
updated_at: 2026-02-11 13:27
completed_at: 2026-02-11 13:27
---

## Context

This is child task 7 of parent task t85 (Cross-Platform aitask Framework Distribution). The `install.sh` script is the curl-friendly bootstrap that users run to install aitasks into their project. It downloads the latest release tarball from GitHub, extracts framework files into the project directory, and runs `ait setup` to install dependencies.

**Usage**: `curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh | bash`

**File to create**: `~/Work/aitasks/install.sh`

## What to Do

### Script flow

1. **Parse arguments**: `--force` (overwrite existing files), `--dir PATH` (install to specific directory, default `.`)
2. **Check prerequisites**: `curl` or `wget`, `tar` must be available
3. **Safety check**: If `ait` or `aiscripts/` already exist in target dir, warn and exit unless `--force`
4. **Download**: Fetch latest release URL from GitHub API, download tarball
5. **Extract**: Unpack `ait`, `VERSION`, `aiscripts/`, `skills/` into target directory
6. **Install skills**: Copy `skills/aitask-*/SKILL.md` into `.claude/skills/aitask-*/SKILL.md`
7. **Create data directories**: `aitasks/metadata/`, `aitasks/archived/`, `aiplans/archived/`
8. **Set permissions**: `chmod +x ait aiscripts/*.sh`
9. **Run setup**: Execute `./ait setup` for dependency installation
10. **Print summary**: Success message with quick-start commands

### Key implementation details

**GitHub API for latest release:**
```bash
REPO="beyondeye/aitasks"
LATEST_URL=$(curl -sS "https://api.github.com/repos/$REPO/releases/latest" \
  | grep '"browser_download_url".*\.tar\.gz"' \
  | head -1 \
  | sed 's/.*"\(http[^"]*\)".*/\1/')
```

If the API call fails (rate limited, no network), provide a fallback message suggesting manual download from `https://github.com/beyondeye/aitasks/releases`.

**Temp directory with cleanup:**
```bash
TMPDIR=$(mktemp -d)
trap "rm -rf '$TMPDIR'" EXIT
```

**Download with curl or wget fallback:**
```bash
if command -v curl &>/dev/null; then
    curl -sSL "$LATEST_URL" -o "$TMPDIR/aitasks.tar.gz"
elif command -v wget &>/dev/null; then
    wget -q "$LATEST_URL" -O "$TMPDIR/aitasks.tar.gz"
fi
```

**Tarball extraction:**
The tarball (created in t85_8) contains `ait`, `VERSION`, `aiscripts/`, `skills/` at the top level (no parent directory). Extract directly:
```bash
tar -xzf "$TMPDIR/aitasks.tar.gz" -C "$INSTALL_DIR"
```

**Skills installation:**
The skills are in the tarball under `skills/` but need to go into `.claude/skills/`:
```bash
mkdir -p "$INSTALL_DIR/.claude/skills"
for skill_dir in "$INSTALL_DIR/skills"/aitask-*/; do
    [[ -d "$skill_dir" ]] || continue
    skill_name=$(basename "$skill_dir")
    mkdir -p "$INSTALL_DIR/.claude/skills/$skill_name"
    cp "$skill_dir/SKILL.md" "$INSTALL_DIR/.claude/skills/$skill_name/SKILL.md"
done
```

After copying, optionally remove the `skills/` directory from the project root (it was just a staging area from the tarball). Or leave it — the user can gitignore it. Better to remove it to keep the project clean:
```bash
rm -rf "$INSTALL_DIR/skills"
```

**Data directories:**
```bash
mkdir -p "$INSTALL_DIR/aitasks/metadata"
mkdir -p "$INSTALL_DIR/aitasks/archived"
mkdir -p "$INSTALL_DIR/aiplans/archived"
```

**Running with `| bash`:**
When piped via `curl | bash`, there's no terminal for interactive prompts. The script should detect this (`[[ -t 0 ]]`) and default to non-interactive behavior (proceed without confirmation). When run interactively, it can ask "Install aitasks here? [Y/n]".

**--force behavior:**
With `--force`, overwrite `ait`, `VERSION`, `aiscripts/`. Do NOT overwrite `aitasks/` data directories or `.claude/skills/` that may have been customized — only overwrite the aitask-specific skills.

### Color helpers

Use the same pattern as `aitask_setup.sh`:
```bash
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()    { echo -e "${BLUE}[ait]${NC} $1"; }
success() { echo -e "${GREEN}[ait]${NC} $1"; }
warn()    { echo -e "${YELLOW}[ait]${NC} $1"; }
die()     { echo -e "${RED}[ait] Error:${NC} $1" >&2; exit 1; }
```

### Summary output

```
=== aitasks installed successfully ===

Quick start:
  ait create     # Create a new task
  ait ls -v 15   # List top 15 tasks
  ait board      # Open task board
  ait setup      # Re-run dependency setup

Claude Code skills installed to .claude/skills/
```

### Commit

```bash
cd ~/Work/aitasks
chmod +x install.sh
git add install.sh
git commit -m "Add curl-friendly bootstrap installer"
```

## Verification

1. `bash -n ~/Work/aitasks/install.sh` — no syntax errors
2. In a fresh test directory: `bash ~/Work/aitasks/install.sh --dir /tmp/test-project` installs files correctly
3. `ls /tmp/test-project/ait /tmp/test-project/aiscripts/ /tmp/test-project/.claude/skills/` shows expected files
4. `ls /tmp/test-project/aitasks/metadata/` shows the directory was created
5. Running again without `--force` should warn and exit
