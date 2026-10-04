---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Done
labels: [testmap, go_engine, release_scripts]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
assigned_to: dario-e@beyond-eye.com
anchor: 1852
followup_kind: risk_mitigation
created_at: 2026-09-25 11:45
updated_at: 2026-10-04 16:41
completed_at: 2026-10-04 16:41
---

## Origin

Risk-mitigation ("after") follow-up for t1852_3, created at Step 8d after implementation landed.

## Risk addressed

release wiring unverifiable before a real tag — The release wiring cannot be exercised end to end before a real `v*` tag: the artifact hand-off between jobs, the `goengines/dist/*` glob in both release steps, `fail_on_unmatched_files`, and setup-go's toolchain behaviour on the runner. If any of these is wrong, the assets M1.5 fetches are missing from the next release · severity: medium

## Goal

Pick this task only **after the first `v*` tag cut after t1852_3 landed** (commit `c1095fff6`): nothing before a real release exercises `.github/workflows/release.yml`. Then confirm on that release:

- The Release workflow run shows the `goengines` job green (`go version` log names go1.27.1; vet, test, `build.sh all`, `sha256sum -c` all passed) and `release` ran after it.
- The GitHub release carries the four assets `ait-testmap_<V>_{linux,darwin}_{amd64,arm64}` and `ait-testmap_<V>_SHA256SUMS.txt`, next to the tarball and `packaging/shim/ait`.
- Downloading all five and running `sha256sum -c ait-testmap_<V>_SHA256SUMS.txt` passes.
- On a Linux host, the downloaded `ait-testmap_<V>_linux_amd64` (chmod +x) prints `"version":"<V>"` and a 40-hex commit from `version --json`.
- The `packaging` job (release-packaging.yml) still ran and succeeded.

Reference: `aidocs/framework/go_engine.md` ("Release assets", "Release job wiring").

## Verification Checklist

- [x] Release workflow run: goengines job green (go version shows go1.27.1; vet, test, build.sh all, sha256sum -c passed) and release ran after it — PASS 2026-10-04 16:41 auto: Release run 36150619092 (v0.36.0): goengines job success, go version → go1.27.1 (GOTOOLCHAIN=auto from setup-go 1.26.0), vet/test ok, build.sh all + sha256sum -c 4×OK; release needs [plan, goengines], ran after
- [x] GitHub release carries ait-testmap_<V>_{linux,darwin}_{amd64,arm64} and ait-testmap_<V>_SHA256SUMS.txt beside the tarball and packaging/shim/ait — PASS 2026-10-04 16:41 auto: gh release view v0.36.0 lists ait-testmap_0.36.0_{linux,darwin}_{amd64,arm64} + ait-testmap_0.36.0_SHA256SUMS.txt beside aitasks-v0.36.0.tar.gz and ait (byte-identical to packaging/shim/ait)
- [x] sha256sum -c ait-testmap_<V>_SHA256SUMS.txt passes on the five downloaded files — PASS 2026-10-04 16:41 auto: downloaded the five files; sha256sum -c → 4×OK, rc=0
- [x] Downloaded ait-testmap_<V>_linux_amd64 prints "version":"<V>" and a 40-hex commit from version --json — PASS 2026-10-04 16:41 auto: linux_amd64 version --json → version 0.36.0, commit f8a049f3c99e2ef6429e9e220ddca1d6210d1763 (= v0.36.0^{commit}), rc=0
- [x] packaging job (release-packaging.yml) still ran and succeeded — PASS 2026-10-04 16:41 auto: packaging reusable workflow (release.yml packaging job → release-packaging.yml) ran in the same run: build-deb/rpm, test-deb×3, test-rpm×3, publish-aur, publish-homebrew all success
