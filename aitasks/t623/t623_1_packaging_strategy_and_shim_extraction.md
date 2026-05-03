---
priority: high
effort: medium
depends: []
issue_type: chore
status: Implementing
labels: [install_scripts, installation, packaging]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-22 18:56
updated_at: 2026-05-03 11:16
---

## Context

This is the design-spike child for the multi-installer effort (t623). All other children (t623_2..t623_6) reference the outputs of this one.

**Why it exists.** Adding Homebrew, AUR, .deb, and .rpm packaging in one commit would be unreviewable. Each channel also has decisions that would otherwise be re-litigated per child (packaging model, release-cycle policy, dep name mapping, secret provisioning). This child makes those decisions once, commits them to `aidocs/packaging_strategy.md`, and extracts the global-shim heredoc into a standalone file so every downstream packaging child consumes the same source of truth.

**Chosen packaging model.** Shim-only (confirmed by user during parent-task planning). Each PM ships only the ~87-line global shim — the body of `install_global_shim()` in `.aitask-scripts/aitask_setup.sh:555-648`. Framework files are never bundled into PM packages; `ait setup` still downloads the tarball on demand. This fully decouples framework release cadence from PM release cadence.

## Key Files to Modify

- `aidocs/packaging_strategy.md` (new) — the strategy document.
- `packaging/shim/ait` (new) — standalone shim extracted from the heredoc in `.aitask-scripts/aitask_setup.sh`.
- `.aitask-scripts/aitask_setup.sh` (modified) — `install_global_shim()` reads from `packaging/shim/ait` instead of embedding the body as a heredoc.
- `.github/workflows/release.yml` (modified) — include `packaging/shim/ait` in the release tarball AND upload it as a separate `ait` release asset (needed for Homebrew/AUR/.deb/.rpm to `curl` the raw shim).
- `install.sh` (modified only if needed) — verify the curl-install path still finds the shim after refactor.

## Reference Files for Patterns

- `.aitask-scripts/aitask_setup.sh:555-648` — source of the shim body (heredoc between `<< 'SHIM'` and `SHIM`). Copy verbatim into `packaging/shim/ait`; change only the `#!/usr/bin/env bash` preamble stays, and remove the outer function wrapping.
- `.github/workflows/release.yml:96-145` — tarball + release-asset upload pattern; extend `files:` list in the `softprops/action-gh-release` step to include the shim.
- `sinelaw/fresh/.github/workflows/release.yml` "plan" job — clean pattern for extracting version once and exposing as a job output for downstream packaging jobs. Worth adopting.

## Implementation Plan

1. Create `packaging/shim/` directory.
2. Extract the heredoc body from `.aitask-scripts/aitask_setup.sh:560-648` into `packaging/shim/ait`. The file should start with `#!/usr/bin/env bash` and contain the shim logic unmodified.
3. Modify `install_global_shim()` in `.aitask-scripts/aitask_setup.sh` to replace the heredoc with `cp` or `cat` from a resolved path. The install.sh flow must still find the shim source: when run via `curl | bash`, `packaging/shim/ait` is inside the freshly-extracted tarball in a temp dir, so resolve the path relative to the install root (e.g., `$INSTALL_DIR/packaging/shim/ait`). When run from a cloned repo, resolve relative to repo root.
4. Extend `.github/workflows/release.yml`:
   - Add `packaging/` to the tarball's file list (already works if `tar -czf` uses a flat list — confirm).
   - Upload `packaging/shim/ait` as a separate release asset named `ait` (this is the raw-file URL that brew/AUR/.deb/.rpm will reference).
5. Write `aidocs/packaging_strategy.md` covering all the decisions listed below.
6. Update `CLAUDE.md` briefly to reference the new `packaging/` directory structure (optional — scope it minimally).

**Content required in `aidocs/packaging_strategy.md`:**

- Why shim-only (release-cycle decoupling, referenced from this task's description).
- Per-PM manifest skeletons (just the deps list + shim path — one paragraph each).
- Dependency name mapping table: columns = PM (Brew/AUR/deb/rpm), rows = (bash, python, fzf, jq, git, zstd, tar, curl, gh, glab). Table fills in the exact package name per distro.
- Required GitHub Actions secrets: `HOMEBREW_TAP_TOKEN` (PAT with repo scope on `beyondeye/homebrew-aitasks`), `AUR_USERNAME`, `AUR_EMAIL`, `AUR_SSH_PRIVATE_KEY`. Include the exact `gh secret set` commands + SSH key generation steps.
- Release-cadence policy: all four PMs bump on every tag regardless of shim-hash change (keeps availability visible; optimization for hash-based skip deferred).
- Version-vs-behavior note for user docs: "The PM version label identifies the shim release. The framework version is downloaded fresh by `ait setup` in your project."
- Deferred follow-ups: official Arch repo submission, AUR/APT/DNF hosted repos at `apt.aitasks.io` / `pacman.aitasks.io`, nix/scoop/chocolatey/snap/flatpak — list each as a future task so they don't get lost.

## Verification Steps

1. Diff the shim content before/after extraction:
   - Before: `grep -A 200 "install_global_shim" .aitask-scripts/aitask_setup.sh | grep -A 200 "<< 'SHIM'" | ...` to extract the heredoc body.
   - After: `cat packaging/shim/ait`.
   - They must be byte-identical except the `#!/usr/bin/env bash` preamble.
2. Run `bash install.sh --dir /tmp/ait-install-test` on a fresh empty directory. The global shim at `~/.local/bin/ait` must be byte-identical to `packaging/shim/ait`. Compare with `diff ~/.local/bin/ait packaging/shim/ait`.
3. Run existing tests: `for t in tests/test_*.sh; do bash "$t"; done`. All must pass.
4. Run `shellcheck .aitask-scripts/aitask_setup.sh packaging/shim/ait` — no new warnings.
5. `tar -tzf` the built tarball (after a dry-run of the release workflow, e.g., `act` or manual simulation) and confirm `packaging/shim/ait` is present.
6. Golden-file test: add `tests/test_shim_extraction_parity.sh` that runs `install_global_shim` in a temp dir and byte-compares the output to `packaging/shim/ait`. Commit this test.
