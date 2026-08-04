---
priority: medium
effort: medium
depends: [1075]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [1075]
assigned_to: dario-e@beyond-eye.com
anchor: 1075
created_at: 2026-06-28 10:09
updated_at: 2026-08-04 17:30
boardidx: 162816
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1075

## Verification Checklist

- [x] Block api.github.com (e.g. add `127.0.0.1 api.github.com` to /etc/hosts, or firewall it) so the REST API is unreachable. — PASS 2026-08-04 17:26 auto: PATH shim (curl) blocks api.github.com with exit 6 and logs every call; github.com CDN probe still returns 200 -- targeted block, not an outage. No wget on this box (install.sh:99 selects curl).
- [x] Run `ait upgrade <VERSION>` for a known existing release; confirm it SUCCEEDS (downloads aitasks-v<VERSION>.tar.gz from the release CDN and installs) with NO call to api.github.com. — PASS 2026-08-04 17:29 auto: ait upgrade 0.30.0 in sandbox exit 0; VERSION 0.29.0 -> 0.30.0. Exactly 2 curl calls logged, ZERO to api.github.com: raw.githubusercontent.com/.../v0.30.0/install.sh then releases/download/v0.30.0/aitasks-v0.30.0.tar.gz (CDN).
- [x] Run `ait upgrade <older-version>` (a real older release) and confirm it installs THAT version's tarball, not latest. — PASS 2026-08-04 17:29 auto: ait upgrade 0.28.0 from 0.30.0 exit 0; VERSION is exactly 0.28.0 (NOT latest 0.30.0); asset downloaded was aitasks-v0.28.0.tar.gz. Zero api.github.com calls.
- [x] Run a standalone `bash install.sh` (no --version) while api.github.com is still blocked; confirm it resolves and installs the latest release via the git-tag fallback. — PASS 2026-08-04 17:29 auto: standalone 'bash install.sh' (no --version), api.github.com blocked: exit 0, 'Resolving latest aitasks release...' -> git-tag fallback resolved 0.30.0 -> CDN download. VERSION 0.30.0. No 'Fetching latest release via the GitHub API' line; only 1 curl call (the CDN); git ls-remote bypasses curl entirely.
- [x] Confirm `bash install.sh --version <VERSION>` (explicit flag) downloads that exact version from the CDN. — PASS 2026-08-04 17:29 auto: 'bash install.sh --version 0.27.1' exit 0; VERSION exactly 0.27.1; only network call is the v0.27.1 CDN URL; no 'Resolving latest' line (explicit version short-circuits resolution); zero api.github.com.
- [x] Confirm the `--local-tarball <path>` install path still works unchanged. — PASS 2026-08-04 17:30 auto: 'bash install.sh --local-tarball aitasks-v0.30.0.tar.gz' exit 0; VERSION 0.30.0; netlog EMPTY (zero network calls of any kind) - install.sh:260 returns before any resolution.
- [x] Set GH_TOKEN and confirm any remaining REST call (force the fallback) carries the Authorization header (no rate-limit error). — PASS 2026-08-04 17:30 auto: forced the REST fallback (git ls-remote starved) with GH_TOKEN set. install.sh:234 emitted exactly ONE api.github.com call carrying 'Authorization: Bearer' (AUTH=yes); token never written to disk. Live confirmation of the no-rate-limit-error clause: unauthenticated /rate_limit = limit 60, same header form authenticated = limit 5000.
- [x] Unblock api.github.com afterward. — PASS 2026-08-04 17:30 auto: shim dirs removed; curl resolves to /usr/bin/curl again; api.github.com/rate_limit returns http 200 in a clean shell. /etc/hosts has no api.github.com entry - the block was process-local PATH state, so nothing system-wide needed reverting.
