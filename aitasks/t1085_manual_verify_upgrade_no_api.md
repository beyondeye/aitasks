---
priority: medium
effort: medium
depends: [1075]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1075]
anchor: 1075
created_at: 2026-06-28 10:09
updated_at: 2026-06-28 10:09
boardidx: 200
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1075

## Verification Checklist

- [ ] Block api.github.com (e.g. add `127.0.0.1 api.github.com` to /etc/hosts, or firewall it) so the REST API is unreachable.
- [ ] Run `ait upgrade <VERSION>` for a known existing release; confirm it SUCCEEDS (downloads aitasks-v<VERSION>.tar.gz from the release CDN and installs) with NO call to api.github.com.
- [ ] Run `ait upgrade <older-version>` (a real older release) and confirm it installs THAT version's tarball, not latest.
- [ ] Run a standalone `bash install.sh` (no --version) while api.github.com is still blocked; confirm it resolves and installs the latest release via the git-tag fallback.
- [ ] Confirm `bash install.sh --version <VERSION>` (explicit flag) downloads that exact version from the CDN.
- [ ] Confirm the `--local-tarball <path>` install path still works unchanged.
- [ ] Set GH_TOKEN and confirm any remaining REST call (force the fallback) carries the Authorization header (no rate-limit error).
- [ ] Unblock api.github.com afterward.
