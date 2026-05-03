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

## Final Implementation Notes

- **Actual work done:** Five concrete deliverables landed:
  1. `packaging/shim/ait` — extracted 87-line shim (byte-identical to the old heredoc body), `chmod +x`.
  2. `.aitask-scripts/aitask_setup.sh` — `install_global_shim()` body collapsed from a 89-line heredoc to a 4-line guarded `cp` from `$SCRIPT_DIR/../packaging/shim/ait`; line-9 `SHIM_DIR=` made overrideable (`${SHIM_DIR:-$HOME/.local/bin}`).
  3. `.github/workflows/release.yml` — added `packaging/` to the `tar -czf` file list; converted both `softprops/action-gh-release` `files:` blocks to multi-line and added `packaging/shim/ait` so the raw shim is uploaded as a release asset (the URL Homebrew/AUR/.deb/.rpm formulas curl from).
  4. `aidocs/packaging_strategy.md` — single source of truth for downstream packaging children. All sections per plan: rationale, per-PM manifest skeletons (Homebrew Ruby formula, AUR PKGBUILD, debian/control, RPM spec), dependency mapping table with `gh`/`glab` "at least one strongly recommended" footnote, GitHub Actions secrets + AUR SSH key generation, release-cadence policy, version-vs-behavior note for user docs, deferred-follow-ups table.
  5. `tests/test_shim_extraction_parity.sh` — golden-file regression test sandboxing `SHIM_DIR` to a tempdir, sourcing `aitask_setup.sh --source-only`, calling `install_global_shim`, and `diff -q`-ing against `packaging/shim/ait`. 3/3 assertions pass.

- **Deviations from plan:**
  - The plan's resolution snippet contained a two-branch `INSTALL_DIR`/`SCRIPT_DIR` fallback. I collapsed it to a single `$SCRIPT_DIR/..` branch after verifying both invocation paths (curl-install via `install.sh` and cloned-repo `ait setup`) resolve to the same file via that single expression. The plan's stated rationale already justified this.
  - The optional CLAUDE.md note (Step 7 in the plan, "scoped minimally") was skipped — no value at this stage. The `packaging/` directory's purpose is self-evident from `aidocs/packaging_strategy.md`; CLAUDE.md will get a one-line bullet later (e.g., during t623_6 docs work) once the directory has more than just the shim subdir.
  - Plan-vs-reality: the plan's referenced line ranges (`aitask_setup.sh:555-648`, `release.yml:96-145`) had drifted by ~190 lines and ~30 lines respectively due to commits between plan authoring and execution. Verified actual ranges (742-844, 96-110, 133-145) and proceeded — the *content* was unchanged, only line numbers.
  - Plan said `release.yml` has one `softprops/action-gh-release` step; reality has two (with-changelog and auto-generated-notes branches, mutually exclusive via `if:`). Both got the asset addition.

- **Issues encountered:**
  - **Plan's golden-file test was buggy as written.** The `SHIM_DIR=$TMPDIR/bin source ...` form silently lost the override because `aitask_setup.sh:9` was unconditional `SHIM_DIR="$HOME/.local/bin"`. Fixed at the source by switching to `${SHIM_DIR:-$HOME/.local/bin}`; the test exports `SHIM_DIR` *before* sourcing and asserts it survived. One-line, fully backward-compatible (no caller currently sets `SHIM_DIR` before sourcing).
  - **No real-world `bash install.sh --dir <tmp>` integration test was practical.** That path downloads a release tarball from GitHub, which doesn't yet contain `packaging/`. Substituted a direct integration test that stages a fake "release-stage" dir with `.aitask-scripts/`, `packaging/`, and `aitask_setup.sh`, sources from there, calls `install_global_shim`, and `diff`s the output. Confirmed byte-identical. The full `install.sh` flow will be exercised end-to-end after the next tagged release rebuilds a tarball that includes `packaging/`.
  - **Pre-existing test failures (14/112) confirmed unrelated** to this task's changes. Verified via `grep -l "install_global_shim\|SHIM_DIR\|packaging/shim\|release.yml"` against all 14 failing test files: zero matches. Failing tests touch brainstorm CLI, codex model detection, contribute, explain context, gemini setup, init data, archive migration, multi-session minimonitor, python_resolve helpers, t167/t644 integration, task_push, tui switcher — all in unrelated subsystems.

- **Key decisions:**
  - **Single resolution branch via `$SCRIPT_DIR/..`** instead of the plan's two-branch `INSTALL_DIR`-then-fallback. Cleaner, equivalent in both invocation paths, and one fewer place to maintain when path conventions change.
  - **Both `softprops/action-gh-release` blocks patched** instead of just one. Even though only one runs per release (the changelog presence selects), missing one would silently produce releases without the `ait` asset depending on which branch fires.
  - **`gh`/`glab` documented as "individually optional, at least one strongly recommended"** in the strategy doc (per user feedback during plan review). Each PM declares them at the recommends/suggests/optdepends tier, never as hard requires.
  - **No CHANGELOG.md update** for this task. The work is internal refactoring with no user-visible behavior change in framework releases — the user-visible change (PM availability) lands in t623_2..t623_5 and gets a CHANGELOG entry then.

- **Upstream defects identified:** None. The pre-existing test failures (14/112) were not diagnosed in scope of this task — they don't *seed* the work here, they're parallel pre-existing issues in unrelated subsystems. They belong in their own issue/task tracking, not as upstream defects of this task.

- **Notes for sibling tasks:** (critical — every later child reads this)
  - **`packaging/shim/ait` is the canonical shim.** Every downstream PM child (t623_2 Homebrew, t623_3 AUR, t623_4 deb, t623_5 rpm) MUST `curl` or reference `https://github.com/beyondeye/aitasks/releases/download/v<X.Y.Z>/ait` (the release asset uploaded by `release.yml`'s `softprops/action-gh-release` step). DO NOT bundle `aitask_setup.sh` or any framework files into PM packages.
  - **For local development of the PM manifests:** the file is at `packaging/shim/ait` in the repo. CI flows can refer to either the local file (during testing) or the release asset URL (in the published manifest).
  - **The release asset URL is stable per tag.** Format: `https://github.com/beyondeye/aitasks/releases/download/v<X.Y.Z>/ait` (no `.sh` extension, no version suffix in filename — just `ait`). The shim's SHA-256 must be regenerated and substituted into each PM manifest on every tag (this is the per-tag bump CI does).
  - **`gh`/`glab` semantics:** Each PM child should declare them as recommends/suggests/optdepends with the rationale text from `aidocs/packaging_strategy.md` (host integration features degrade without one). Do NOT treat them as hard requirements.
  - **GitHub Actions secrets are already documented in the strategy doc** (Section "Required GitHub Actions secrets"). t623_2 (Homebrew) needs `HOMEBREW_TAP_TOKEN`; t623_3 (AUR) needs `AUR_USERNAME`/`AUR_EMAIL`/`AUR_SSH_PRIVATE_KEY`. The user must set these via `gh secret set` BEFORE the corresponding child's CI flow runs for the first time. t623_4 (deb) and t623_5 (rpm) need only the default `GITHUB_TOKEN` for the initial release-attached-package phase.
  - **Release cadence is "every tag bumps every PM"** — no hash-based skip. Each PM child's CI workflow should fire on the same `tag push v*` trigger that the main `release.yml` uses.
  - **`SHIM_DIR` is now overrideable.** If a future test or helper needs to install the shim to a non-default location, set `export SHIM_DIR=<path>` before sourcing `aitask_setup.sh`. The test in `tests/test_shim_extraction_parity.sh` is the canonical pattern.
  - **`aitask_setup.sh` line numbers WILL drift further** — every child should re-grep for `install_global_shim` rather than trust the line numbers in this plan.
