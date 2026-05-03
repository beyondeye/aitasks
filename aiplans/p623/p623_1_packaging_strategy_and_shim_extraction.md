---
Task: t623_1_packaging_strategy_and_shim_extraction.md
Parent Task: aitasks/t623_more_installation_methods.md
Sibling Tasks: aitasks/t623/t623_2_*.md, t623_3_*.md, t623_4_*.md, t623_5_*.md, t623_6_*.md
Archived Sibling Plans: (none yet — this is the first child)
Worktree: (none — working on current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-03 12:12
---

# Implementation Plan: t623_1 — Packaging strategy & shim extraction

## Context

Child 1 of the multi-installer effort (t623). All other children
(t623_2..t623_6) reference outputs of this one. We make the cross-cutting
packaging decisions once, write them to `aidocs/packaging_strategy.md`, and
extract the global-shim heredoc into a standalone `packaging/shim/ait` file
that every downstream packaging child consumes as a single source of truth.

## Goal

Produce three artifacts:

1. `aidocs/packaging_strategy.md` — single source of truth for downstream packaging children's decisions.
2. `packaging/shim/ait` — the 87-line global shim extracted as a standalone executable, consumed both by `install_global_shim()` in `aitask_setup.sh` and by every PM package built by t623_2..t623_5.
3. `tests/test_shim_extraction_parity.sh` — golden-file regression test guarding the heredoc-to-file refactor.

## Plan-vs-reality verification (2026-05-03)

The original plan referenced `.aitask-scripts/aitask_setup.sh:555-648` for
`install_global_shim()`. The function has shifted in the file due to other
commits. **Current locations on `main` (commit `01430974`):**

- `install_global_shim()` — `.aitask-scripts/aitask_setup.sh:742-844`
- Heredoc opener `cat > "$SHIM_DIR/ait" << 'SHIM'` — line 747
- Heredoc body — lines **748-834** (87 lines: starts with `#!/usr/bin/env bash`, ends with `exit 1` of the "no project found" branch)
- Heredoc closer `SHIM` — line 835
- Caller from `install.sh` — line 1059 (after `source "$INSTALL_DIR/.aitask-scripts/aitask_setup.sh" --source-only` at line 1058; `seed/` is deleted at line 1050 BEFORE the shim install — `packaging/` is NOT deleted, so it remains available)
- `release.yml` tarball file list — lines 96-110
- `release.yml` has **two** `softprops/action-gh-release` steps (with-changelog at 133-138 and auto-generated-notes at 140-145) — **both** need `packaging/shim/ait` added to their `files:` lists

The shim *content* is unchanged from when the plan was authored; only the
line numbers shifted. No structural surprises.

## Steps

### 1. Extract the shim

1. Create `packaging/shim/` directory.
2. Write `packaging/shim/ait`:
   - Line 1: `#!/usr/bin/env bash`
   - Lines 2-87: byte-for-byte copy of `aitask_setup.sh:749-834` (the heredoc body without its own `#!/usr/bin/env bash` line — that becomes line 1 of the new file).
3. `chmod +x packaging/shim/ait`.

### 2. Patch `install_global_shim()` to read the file

In `.aitask-scripts/aitask_setup.sh`, replace the heredoc body
(lines 747-835: from `cat > "$SHIM_DIR/ait" << 'SHIM'` through the closing
`SHIM` delimiter) with a `cp` that resolves the source via `$SCRIPT_DIR`:

```bash
local shim_src="$SCRIPT_DIR/../packaging/shim/ait"
[[ -f "$shim_src" ]] || die "Cannot locate shim source ($shim_src)"
cp "$shim_src" "$SHIM_DIR/ait"
```

**Why `$SCRIPT_DIR/..` is sufficient** (no separate `INSTALL_DIR` branch
needed): `SCRIPT_DIR` is set on line 7 of `aitask_setup.sh` to the absolute
directory of the script itself.

- **Curl-install path:** `install.sh:1058` does `source "$INSTALL_DIR/.aitask-scripts/aitask_setup.sh" --source-only` → `SCRIPT_DIR=$INSTALL_DIR/.aitask-scripts` → `$SCRIPT_DIR/../packaging/shim/ait = $INSTALL_DIR/packaging/shim/ait`. ✓
- **Cloned-repo path (`ait setup`):** `SCRIPT_DIR=<repo>/.aitask-scripts` → `$SCRIPT_DIR/../packaging/shim/ait = <repo>/packaging/shim/ait`. ✓

The `chmod +x "$SHIM_DIR/ait"`, `success` log, and
`ensure_path_in_profile "$SHIM_DIR"` lines below the heredoc are kept
unchanged.

### 3. Make `SHIM_DIR` overrideable for tests

The current line 9 is unconditional:

```bash
SHIM_DIR="$HOME/.local/bin"
```

This silently overwrites any pre-set `SHIM_DIR` env var, which prevents the
parity test from redirecting the shim install to a temp dir. Change to:

```bash
SHIM_DIR="${SHIM_DIR:-$HOME/.local/bin}"
```

One-line, fully backward-compatible (no caller currently sets `SHIM_DIR`
before sourcing).

### 4. Release workflow changes (`.github/workflows/release.yml`)

1. **Tarball file list (lines 96-110):** add `packaging/` to the explicit list passed to `tar -czf`:
   ```yaml
   tar -czf aitasks-${{ github.ref_name }}.tar.gz \
       ait \
       CHANGELOG.md \
       .aitask-scripts/ \
       packaging/ \                    # ← new
       skills/ \
       seed/ \
       …
   ```

2. **Both release-asset steps:** add `packaging/shim/ait` to the `files:` block of *each* `softprops/action-gh-release` step so the raw shim is uploaded as an asset named `ait` (the URL Homebrew/AUR/.deb/.rpm formulas curl from):

   - `Create GitHub Release (with changelog)` step at line 133-138:
     ```yaml
     files: |
       aitasks-${{ github.ref_name }}.tar.gz
       packaging/shim/ait
     ```
   - `Create GitHub Release (auto-generated notes)` step at line 140-145: same change.

   (The two steps are mutually exclusive via `if:`, but both must be patched so the asset is present regardless of which path runs.)

### 5. Write `aidocs/packaging_strategy.md`

Required sections (verbatim plan from the task description):

- **Packaging model** — shim-only; rationale (release-cycle decoupling); each PM ships only the shim file, nothing else.
- **Per-PM manifest skeletons** — one short paragraph each for Homebrew / AUR / Debian-deb / Fedora-rpm, showing the 5-10 line manifest each downstream child produces.
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
  | gh¹ | — | `github-cli` | `gh` | `gh` |
  | glab¹ | — | `glab` | `glab` | `glab` |

  ¹ `gh` and `glab` are individually optional, but **at least one is strongly recommended**: aitasks integrates with the user's git host (issue/PR open/close, contribution flows), and a fresh install with neither tool present will degrade to manual-only workflows for those features. Document this in the strategy doc as "optional dependency, choose by host: GitHub users → `gh`, GitLab users → `glab`; users with both hosts may install both." Each PM child (t623_2..t623_5) lists `gh` and `glab` as `recommended`/`suggests`/etc., not `requires`.

- **Required GitHub Actions secrets:**
  ```bash
  gh secret set HOMEBREW_TAP_TOKEN --repo beyondeye/aitasks  # PAT with `repo` scope on beyondeye/homebrew-aitasks
  gh secret set AUR_USERNAME --repo beyondeye/aitasks        # AUR account username
  gh secret set AUR_EMAIL --repo beyondeye/aitasks           # AUR account email
  gh secret set AUR_SSH_PRIVATE_KEY --repo beyondeye/aitasks # ed25519 private key registered on AUR account
  ```
  SSH key generation: `ssh-keygen -t ed25519 -f aur_key -C aur-deploy` → add `aur_key.pub` at https://aur.archlinux.org/account/ → `cat aur_key | gh secret set AUR_SSH_PRIVATE_KEY --repo beyondeye/aitasks`.

- **Release-cadence policy** — all four PMs bump on every tag; hash-based skip-if-unchanged optimization deferred.
- **Version vs. behavior note for user docs** — "The PM version label identifies the shim release. The framework version is whatever `ait setup` downloads into your project at bootstrap time."
- **Deferred follow-ups list:** Official Arch repo submission (plain `pacman -S aitasks`), hosted APT repo at `apt.aitasks.io`, hosted DNF/RPM repo at `rpm.aitasks.io`, hosted pacman repo at `pacman.aitasks.io`, Nix flake, Scoop (Windows), Chocolatey (Windows), Snap / Flatpak.

### 6. Golden-file parity test (`tests/test_shim_extraction_parity.sh`)

Match the existing test conventions (see `tests/test_claim_id.sh` for the
canonical pattern):

```bash
#!/usr/bin/env bash
# test_shim_extraction_parity.sh — guard the heredoc-to-file shim refactor.
# Verifies install_global_shim() writes a file byte-identical to packaging/shim/ait.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

PASS=0; FAIL=0; TOTAL=0
assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if [[ "$expected" == "$actual" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected '$expected', got '$actual')"
    fi
}

# Sandbox SHIM_DIR so the test does not touch ~/.local/bin
TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT
export SHIM_DIR="$TMPROOT/bin"

# Source aitask_setup.sh in source-only mode (won't run main)
# shellcheck disable=SC1091
source .aitask-scripts/aitask_setup.sh --source-only

# Sanity: SHIM_DIR override survived sourcing (Step 3 fix)
assert_eq "SHIM_DIR overrideable" "$TMPROOT/bin" "$SHIM_DIR"

# Run the shim install
install_global_shim >/dev/null 2>&1 || true

# Compare bytes
if diff -q "$SHIM_DIR/ait" packaging/shim/ait >/dev/null; then
    PASS=$((PASS + 1))
    TOTAL=$((TOTAL + 1))
else
    FAIL=$((FAIL + 1))
    TOTAL=$((TOTAL + 1))
    echo "FAIL: installed shim differs from packaging/shim/ait"
    diff "$SHIM_DIR/ait" packaging/shim/ait | head -30
fi

echo "Total: $TOTAL, Pass: $PASS, Fail: $FAIL"
[[ $FAIL -eq 0 ]]
```

### 7. (Optional, scoped minimally) CLAUDE.md note

Add a single bullet to CLAUDE.md under "Key Directories" mentioning
`packaging/shim/ait` as the source-of-truth for the global shim. Only if
diff stays under 5 lines; skip otherwise.

## Verification Checklist

- [ ] `packaging/shim/ait` exists, is executable, starts with `#!/usr/bin/env bash`.
- [ ] `diff <(sed -n '/<< .SHIM./,/^SHIM$/p' <pre-refactor aitask_setup.sh from git> | sed '1d;$d') packaging/shim/ait | tail -n +2` shows only the leading `#!/usr/bin/env bash` line addition (heredoc body had no shebang).
- [ ] `bash tests/test_shim_extraction_parity.sh` passes.
- [ ] `bash install.sh --dir /tmp/ait-install-test-$$` produces a shim at `/tmp/ait-install-test-$$/.local/bin/ait` (or `~/.local/bin/ait` if `--dir` is the user's home — easier: run with default and compare against `packaging/shim/ait`) byte-identical to `packaging/shim/ait`.
- [ ] All existing tests in `tests/` still pass: `for t in tests/test_*.sh; do bash "$t" || echo "FAIL: $t"; done`.
- [ ] `shellcheck .aitask-scripts/aitask_setup.sh packaging/shim/ait tests/test_shim_extraction_parity.sh` reports no NEW warnings (pre-existing warnings on `aitask_setup.sh` are out of scope).
- [ ] `aidocs/packaging_strategy.md` exists with all sections listed in Step 5.
- [ ] `.github/workflows/release.yml` includes `packaging/` in the tarball file list AND `packaging/shim/ait` in BOTH `softprops/action-gh-release` `files:` blocks.

## Out of scope

- Implementing the actual Homebrew tap, AUR PKGBUILD, .deb / .rpm recipes — those are t623_2..t623_5.
- Updating user docs / website — t623_6.
- Hash-based skip-if-unchanged optimization for the four PM bump CI flows — listed in `aidocs/packaging_strategy.md`'s deferred follow-ups.

## Final Implementation Notes (filled in post-implementation)

- **Actual work done:**
- **Deviations from plan:**
- **Issues encountered:**
- **Key decisions:**
- **Upstream defects identified:**
- **Notes for sibling tasks:** (critical — every later child reads this)
