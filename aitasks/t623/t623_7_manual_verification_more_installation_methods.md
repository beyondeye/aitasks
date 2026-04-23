---
priority: medium
effort: medium
depends: [t623_6]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [623_1, 623_2, 623_3, 623_4, 623_5, 623_6]
created_at: 2026-04-23 08:56
updated_at: 2026-04-23 08:56
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t623_1] diff <(extract heredoc body from pre-refactor aitask_setup.sh) packaging/shim/ait — must be empty
- [ ] [t623_1] bash install.sh --dir /tmp/ait-test produces ~/.local/bin/ait byte-identical to packaging/shim/ait
- [ ] [t623_1] bash tests/test_shim_extraction_parity.sh passes
- [ ] [t623_1] shellcheck .aitask-scripts/aitask_setup.sh packaging/shim/ait — no new warnings
- [ ] [t623_1] aidocs/packaging_strategy.md present with all required sections
- [ ] [t623_2] brew install --build-from-source /tmp/aitasks.rb succeeds on a fresh macOS VM
- [ ] [t623_2] brew test aitasks passes
- [ ] [t623_2] which ait after brew install points at $(brew --prefix)/bin/ait; ait setup in a fresh empty git repo bootstraps successfully
- [ ] [t623_2] After tagging a prerelease, beyondeye/homebrew-aitasks receives a formula-bump commit within 2 minutes
- [ ] [t623_2] actionlint clean on release-packaging.yml and release.yml
- [ ] [t623_3] makepkg -si on a clean Arch container using rendered PKGBUILD succeeds; which ait resolves to /usr/bin/ait
- [ ] [t623_3] namcap PKGBUILD — zero errors
- [ ] [t623_3] After tagging, AUR page at https://aur.archlinux.org/packages/aitasks shows the new pkgver within 2 minutes
- [ ] [t623_3] yay -S aitasks on a fresh Manjaro VM installs cleanly; ait setup works
- [ ] [t623_3] Documented note that plain `pacman -S aitasks` does NOT work — verify this note is present in arch-aur.md
- [ ] [t623_4] VERSION=<v> nfpm package --packager deb produces a valid .deb; dpkg-deb --contents lists only /usr/bin/ait
- [ ] [t623_4] lintian on the built .deb — zero errors
- [ ] [t623_4] CI matrix passes on ubuntu:22.04, ubuntu:24.04, debian:12 after prerelease tag
- [ ] [t623_4] Manual: WSL2 Ubuntu 24.04 download .deb from release, sudo apt install ./aitasks_*.deb, run ait setup in fresh project, create + archive a test task
- [ ] [t623_4] sudo apt remove aitasks cleanly removes /usr/bin/ait
- [ ] [t623_5] VERSION=<v> nfpm package --packager rpm produces a valid .rpm; rpm -qpl shows only /usr/bin/ait
- [ ] [t623_5] rpmlint on built .rpm — zero errors
- [ ] [t623_5] CI matrix passes on fedora:40, fedora:41, rockylinux:9 after prerelease tag
- [ ] [t623_5] Manual: on Fedora 40 VM, sudo dnf install ./aitasks-*.noarch.rpm, run ait setup, create + archive test task
- [ ] [t623_5] sudo dnf remove aitasks cleanly removes /usr/bin/ait
- [ ] [t623_6] cd website && ./serve.sh — each new installation page renders; Docsy sidebar shows all 4 per-platform entries
- [ ] [t623_6] markdown-link-check on all new/modified installation pages passes with zero broken links
- [ ] [t623_6] Every per-platform page contains: What you get / Install / First project / Upgrade / Uninstall sections
- [ ] [t623_6] Each page explains the shim-only model in its What you get section
- [ ] [t623_6] arch-aur.md explicitly warns that plain `pacman -S aitasks` does NOT work and shows the makepkg -si alternative
- [ ] [t623_6] README.md renders correctly on GitHub (PR preview); per-platform install table visible
- [ ] [t623_6] `curl -fsSL …/install.sh | bash` appears only in the Other/fallback sections across README.md + website/
- [ ] [Cross-PM] Tag a patch release after all children merged; verify all four PM channels (brew tap, AUR, .deb asset, .rpm asset) receive updates automatically within 5 minutes
- [ ] [Cross-PM] Install via each PM on a fresh VM, then trigger another release; run the PM's upgrade command — verify it picks up the new version without manual intervention
