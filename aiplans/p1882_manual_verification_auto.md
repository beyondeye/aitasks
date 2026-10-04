---
Task: t1882_first_release_engine_assets_check.md
Base branch: main
Output branch: main
---

# t1882 — First-release check of the Go engine release assets (t1852_3): auto-execution record

Strategy: autonomous. Release under test: `v0.36.0` (published 2026-09-25), the
first `v*` tag containing t1852_3's commit `c1095fff6`
(`git tag --contains c1095fff6 --list 'v*'` → `v0.36.0`). Everything was read via
`gh` against the published release and run logs; the assets were downloaded into
the session scratchpad. No repository or task data was mutated beyond the
checklist itself.

## Execution Log

### Item 1
- Item text: Release workflow run: goengines job green (go version shows go1.27.1; vet, test, build.sh all, sha256sum -c passed) and release ran after it
- Approach: CLI invocation (`gh run view`, job log grep) + file inspection of `.github/workflows/release.yml`
- Action run: `gh run list --workflow release.yml`; `gh run view 36150619092 --json jobs`; `gh run view 36150619092 --log --job <goengines>`; `grep -n needs: .github/workflows/release.yml`
- Output (trimmed): run 36150619092 (`v0.36.0`, push) success. Jobs: `plan` → `goengines` success (14:54:37–14:55:05Z) → `release` success (14:55:08–14:55:27Z). `release.needs: [plan, goengines]`. Log: setup-go installed go1.26.0, then `GOTOOLCHAIN=auto` switched to the toolchain: the `go version` step prints `go version go1.27.1 linux/amd64`; `go vet ./...` produced no output (pass); `go test ./...` → 9 packages `ok`; `./build.sh all` built the four targets and wrote `SUMS:…/ait-testmap_0.36.0_SHA256SUMS.txt`; `sha256sum -c` → 4× `OK`.
- Verdict: pass

### Item 2
- Item text: GitHub release carries ait-testmap_<V>_{linux,darwin}_{amd64,arm64} and ait-testmap_<V>_SHA256SUMS.txt beside the tarball and packaging/shim/ait
- Approach: CLI invocation (`gh release view`)
- Action run: `gh release view v0.36.0 --json assets`; `cmp <downloaded ait> packaging/shim/ait`
- Output (trimmed): assets `ait` (3744), `ait-testmap_0.36.0_darwin_amd64`, `…_darwin_arm64`, `…_linux_amd64`, `…_linux_arm64`, `ait-testmap_0.36.0_SHA256SUMS.txt` (390), `aitasks-v0.36.0.tar.gz`, plus the packaging job's `.deb` / `.rpm`. The `ait` asset is byte-identical to `packaging/shim/ait`.
- Verdict: pass

### Item 3
- Item text: sha256sum -c ait-testmap_<V>_SHA256SUMS.txt passes on the five downloaded files
- Approach: CLI invocation
- Action run: `gh release download v0.36.0 -p 'ait-testmap_*' -p ait`; `sha256sum -c ait-testmap_0.36.0_SHA256SUMS.txt`
- Output (trimmed): `darwin_amd64: OK`, `darwin_arm64: OK`, `linux_amd64: OK`, `linux_arm64: OK`; rc=0
- Verdict: pass

### Item 4
- Item text: Downloaded ait-testmap_<V>_linux_amd64 prints "version":"<V>" and a 40-hex commit from version --json
- Approach: CLI invocation on this Linux host
- Action run: `chmod +x ait-testmap_0.36.0_linux_amd64 && ./ait-testmap_0.36.0_linux_amd64 version --json`; `git rev-parse v0.36.0^{commit}`
- Output (trimmed): `{"version":"0.36.0","commit":"f8a049f3c99e2ef6429e9e220ddca1d6210d1763","contract":1,…}`, rc=0. The commit equals `v0.36.0^{commit}`.
- Verdict: pass

### Item 5
- Item text: packaging job (release-packaging.yml) still ran and succeeded
- Approach: CLI invocation (`gh run view --json jobs`) + file inspection
- Action run: `gh run view 36150619092 --json jobs`; `grep uses: .github/workflows/release.yml`
- Output (trimmed): `packaging` is a reusable-workflow job (`uses: ./.github/workflows/release-packaging.yml`, `needs: [plan, release]`). It therefore appears inside the Release run rather than as a separate `release-packaging.yml` run, and `gh run list --workflow release-packaging.yml` is empty by design. Sub-jobs: build-deb, build-rpm, test-deb (debian:12, ubuntu:22.04, ubuntu:24.04), test-rpm (fedora:41, fedora:42, rockylinux:9), publish-aur, publish-homebrew all succeeded.
- Verdict: pass

## Cleanup
- Scratch directory `<scratchpad>/auto_verify_1882/` (goengines job log + downloaded assets): removed.
- No tmux sessions were created.
