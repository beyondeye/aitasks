---
Task: t623_1_packaging_strategy_and_shim_extraction.md
Parent Task: aitasks/t623_more_installation_methods.md
Sibling Tasks: aitasks/t623/t623_2_*.md, t623_3_*.md, t623_4_*.md, t623_5_*.md, t623_6_*.md
Archived Sibling Plans: (none yet — this is the first child)
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Implementation Plan: t623_1 — Packaging strategy & shim extraction

## Goal

Produce two artifacts:

1. `aidocs/packaging_strategy.md` — the single source of truth for every downstream packaging child's decisions.
2. `packaging/shim/ait` — the ~87-line global shim extracted as a standalone file, consumed both by `install.sh`'s curl-install flow and every PM package built by t623_2..t623_5.

## Steps

### 1. Extract the shim

1. Read `.aitask-scripts/aitask_setup.sh:555-648` — this is the `install_global_shim()` function containing the heredoc body delimited by `<< 'SHIM'` and `SHIM`.
2. Create `packaging/shim/` directory.
3. Write `packaging/shim/ait` with:
   - Line 1: `#!/usr/bin/env bash`
   - Line 2 onwards: the exact heredoc body (lines 561–647 of `aitask_setup.sh`, everything between the `SHIM` delimiters).
4. `chmod +x packaging/shim/ait`.

### 2. Patch `install_global_shim()` to consume the file

1. In `.aitask-scripts/aitask_setup.sh`, replace the heredoc body (`cat > "$SHIM_DIR/ait" << 'SHIM' ... SHIM`) with:
   ```bash
   # Resolve the shim source: in the curl-install flow, it lives under $INSTALL_DIR;
   # when running from a cloned repo, under the repo root.
   local shim_src
   if [[ -n "${INSTALL_DIR:-}" && -f "$INSTALL_DIR/packaging/shim/ait" ]]; then
       shim_src="$INSTALL_DIR/packaging/shim/ait"
   elif [[ -f "$SCRIPT_DIR/../packaging/shim/ait" ]]; then
       shim_src="$SCRIPT_DIR/../packaging/shim/ait"
   else
       die "Cannot locate shim source (packaging/shim/ait)"
   fi
   cp "$shim_src" "$SHIM_DIR/ait"
   ```
   (The exact `$SCRIPT_DIR` resolution depends on how `aitask_setup.sh` already resolves paths — inspect the file's preamble for existing conventions.)
2. Keep the `chmod +x "$SHIM_DIR/ait"` and `ensure_path_in_profile` calls below.

### 3. Release workflow changes

Modify `.github/workflows/release.yml`:

1. Ensure `packaging/` is included in the release tarball (the existing `tar -czf` step at lines 96–110 uses an explicit file list — add `packaging/` to it).
2. In the `softprops/action-gh-release` step (lines 133–145), add `packaging/shim/ait` to the `files:` list so it's uploaded as a separate release asset named `ait`. This is the raw-file URL that Homebrew/AUR/.deb/.rpm packages reference:
   ```yaml
   files: |
     aitasks-${{ github.ref_name }}.tar.gz
     packaging/shim/ait
   ```

### 4. Write `aidocs/packaging_strategy.md`

Required sections:

- **Packaging model** — shim-only; rationale (release-cycle decoupling); what each PM ships (just the shim file, nothing else).
- **Per-PM manifest skeletons** — one paragraph each for Homebrew / AUR / deb / rpm, showing the 5–10 line manifest each child produces.
- **Dependency name mapping table:**
  | Dependency | Homebrew | Arch (AUR) | Debian/Ubuntu | Fedora/RHEL |
  |------------|----------|------------|---------------|-------------|
  | bash | `bash` | `bash>=4` | `bash (>= 4.0)` | `bash >= 4.0` |
  | python (≥3.9) | `python@3.12` | `python>=3.9` | `python3 (>= 3.9)` | `python3 >= 3.9` |
  | fzf | `fzf` | `fzf` | `fzf` | `fzf` |
  | jq | `jq` | `jq` | `jq` | `jq` |
  | git | `git` | `git` | `git` | `git` |
  | zstd | `zstd` | `zstd` | `zstd` | `zstd` |
  | tar | (built-in) | `tar` | `tar` | `tar` |
  | curl | `curl` | `curl` | `curl` | `curl` |
  | gh (optional) | — | `github-cli: ...` | `gh` | `gh` |
  | glab (optional) | — | `glab: ...` | `glab` | `glab` |
- **Required GitHub Actions secrets:**
  ```bash
  gh secret set HOMEBREW_TAP_TOKEN --repo beyondeye/aitasks  # PAT with `repo` scope on beyondeye/homebrew-aitasks
  gh secret set AUR_USERNAME --repo beyondeye/aitasks        # AUR account username
  gh secret set AUR_EMAIL --repo beyondeye/aitasks           # AUR account email
  gh secret set AUR_SSH_PRIVATE_KEY --repo beyondeye/aitasks # ed25519 private key registered on AUR account
  ```
  SSH key generation: `ssh-keygen -t ed25519 -f aur_key -C aur-deploy` → add `aur_key.pub` to https://aur.archlinux.org/account/ → `cat aur_key | gh secret set AUR_SSH_PRIVATE_KEY`.
- **Release-cadence policy** — all four PMs bump on every tag; hash-based skip-if-unchanged optimization deferred.
- **Version vs. behavior note for user docs** — "The PM version label identifies the shim release. The framework version is whatever `ait setup` downloads into your project at bootstrap time."
- **Deferred follow-ups list:**
  - Official Arch repo submission (for plain `pacman -S aitasks`).
  - Hosted APT repo at `apt.aitasks.io`.
  - Hosted DNF/RPM repo at `rpm.aitasks.io`.
  - Hosted pacman repo at `pacman.aitasks.io`.
  - Nix flake.
  - Scoop (Windows).
  - Chocolatey (Windows).
  - Snap / Flatpak.

### 5. Golden-file parity test

Create `tests/test_shim_extraction_parity.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Run install_global_shim in a temp dir
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

SHIM_DIR="$TMPDIR/bin" source .aitask-scripts/aitask_setup.sh --source-only
install_global_shim

diff -q "$TMPDIR/bin/ait" packaging/shim/ait
echo "PASS: shim extraction parity"
```

Commit this test. It guards against regressions in the heredoc-to-file refactor.

## Verification Checklist

- [ ] `diff <(sed -n '/<< .SHIM./,/^SHIM$/p' .aitask-scripts/aitask_setup.sh | sed '1d;$d') <(tail -n +2 packaging/shim/ait)` — this diff should be empty in the `main` commit before this task; use the pre-refactor version of `aitask_setup.sh` from git history as the reference.
- [ ] `bash install.sh --dir /tmp/ait-test` produces a shim at `~/.local/bin/ait` byte-identical to `packaging/shim/ait`.
- [ ] `bash tests/test_shim_extraction_parity.sh` passes.
- [ ] All existing tests in `tests/` pass.
- [ ] `shellcheck .aitask-scripts/aitask_setup.sh packaging/shim/ait` has no new warnings.
- [ ] `aidocs/packaging_strategy.md` exists with all sections listed above.

## Final Implementation Notes (to be filled in post-implementation)

- **Actual work done:**
- **Deviations from plan:**
- **Issues encountered:**
- **Key decisions:**
- **Notes for sibling tasks:** (critical — every later child reads this)
