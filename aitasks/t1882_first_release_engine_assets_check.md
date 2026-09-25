---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Ready
labels: [testmap, go_engine, release_scripts]
anchor: 1852
followup_kind: risk_mitigation
created_at: 2026-09-25 11:45
updated_at: 2026-09-25 11:45
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
