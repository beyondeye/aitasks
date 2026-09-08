---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Implementing
labels: [script-performance]
assigned_to: dario-e@beyond-eye.com
followup_kind: risk_mitigation
created_at: 2026-08-03 22:42
updated_at: 2026-09-08 16:59
boardidx: 3584
---

## Origin

Risk-mitigation ("after") follow-up for t1379, created at Step 8d after implementation landed.

## Risk addressed

Code-health risk (severity: low), from `aiplans/archived/p1379_*.md`:

> `ait_file_mode` depends on the `stat -c` / `stat -f` fallback and the BSD-safe
> `mktemp` template form. Both are the established repo idioms, but the helper
> will not be exercised on macOS in this session.

Also covers the related low-severity bullet:

> `ait_atomic_resolve` is new bespoke code (`readlink -f` is GNU-only, so the
> chain is walked by hand) on the path of every task-file write. Bounded at 40
> hops with an explicit failure, and covered by symlink + cycle tests.

## Goal

Run t1379's suites on macOS and record the results, exercising the BSD branches
that Linux never reaches in `.aitask-scripts/lib/atomic_write.sh`:
`stat -f '%Lp'` (the `ait_file_mode` fallback), the `mktemp …XXXXXX` template
form, and the hand-walked `readlink` chain in `ait_atomic_resolve` (BSD
`readlink` had no `-f` before macOS 12.3, which is why the chain is walked
manually).

## Verification Steps

- Run `bash tests/test_atomic_write_sh.sh` on macOS — 30 assertions, all must pass.
- Run `bash tests/test_atomic_task_file_writes.sh` on macOS — 62 assertions.
- Run the converted scripts' own suites: `test_plan_verified.sh`,
  `test_plan_externalize.sh`, `test_issue_import_contributor.sh`,
  `test_update_risk.sh`, `test_create_silent_stdout.sh`, `test_projects_cmd.sh`.
- Confirm the mode assertions specifically: an existing 0640 file stays 0640, a
  new file is `0666 & ~umask`, and the same under `umask 0077` (this is the
  assertion that catches a hardcoded 0644, and it goes through `stat -f` on macOS).
- Confirm the symlink and symlink-cycle cases pass — those exercise
  `ait_atomic_resolve`'s manual chain walk.
- Record any BSD-vs-GNU divergence in `aidocs/framework/sed_macos_issues.md`
  following the "Files Fixed in tNNN" table convention.

## Verification Checklist

- [x] Run `bash tests/test_atomic_write_sh.sh` on macOS — 30 assertions, all must pass. — PASS 2026-09-08 16:56 auto: macOS 15.7.3 arm64, bash 5.3.9 -- 30/30 assertions PASS, exit 0
- [x] Run `bash tests/test_atomic_task_file_writes.sh` on macOS — 62 assertions. — PASS 2026-09-08 16:56 auto: macOS 15.7.3 arm64 -- 62/62 assertions PASS, exit 0
- [x] Run the converted scripts' own suites: `test_plan_verified.sh`, `test_plan_externalize.sh`, `test_issue_import_contributor.sh`, `test_update_risk.sh`, `test_create_silent_stdout.sh`, `test_projects_cmd.sh`. — PASS 2026-09-08 16:57 auto: all six suites exit 0 on macOS -- plan_verified 49/49, plan_externalize ALL PASSED, issue_import_contributor ALL PASSED, update_risk 21/21, create_silent_stdout ALL PASSED, projects_cmd 42/42
- [x] Confirm the mode assertions specifically: an existing 0640 file stays 0640, a new file is `0666 & ~umask`, and the same under `umask 0077` (catches a hardcoded 0644; goes through `stat -f` on macOS). — PASS 2026-09-08 16:58 auto: on macOS stat -c exits 1 so the BSD stat -f '%Lp' fallback is what answers; 0640 file stays 640, new file = 0666&~umask (644 @ umask 022), and 600 under umask 0077 -- no hardcoded 0644
- [x] Confirm the symlink and symlink-cycle cases pass — those exercise `ait_atomic_resolve`'s manual chain walk. — PASS 2026-09-08 16:58 auto: relative symlink survives + write reaches backing file; 3-hop chain resolves via manual walk; cycle exits 1 with 'too many symlink levels'; 40-hop bound holds (44 fails, 30 passes)
- [x] Record any BSD-vs-GNU divergence in `aidocs/framework/sed_macos_issues.md` following the "Files Fixed in tNNN" table convention. — PASS 2026-09-08 16:59 auto: no BSD-vs-GNU divergence found; added '## stat Portability' + '## readlink Portability' footgun sections (both were undocumented) and a 'Files Audited in t1397' record to aidocs/framework/sed_macos_issues.md
