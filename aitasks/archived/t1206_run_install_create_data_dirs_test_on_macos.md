---
priority: low
effort: low
depends: []
issue_type: manual_verification
status: Done
labels: []
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [1193]
assigned_to: dario-e@beyond-eye.com
anchor: 1199
followup_kind: manual_verification
created_at: 2026-07-21 17:54
updated_at: 2026-09-08 17:12
completed_at: 2026-09-08 17:12
boardcol: tests
boardidx: 2118
---

Run `bash tests/test_install_create_data_dirs.sh` on a macOS/BSD host. Carried over from t1201 (verifies t1193, the dangling data-symlink guard in install.sh `ensure_data_root`), where it was left unverified because no macOS host was available.

Substitute evidence already gathered on Linux (see `aiplans/archived/p1201_manual_verification_auto.md`):

- 40/40 assertions pass on Linux.
- No bash-4-only constructs (`mapfile`, `readarray`, `declare -A`, case-conversion expansions) in the test, `tests/lib/asserts.sh`, or `ensure_data_root` — so it should run under macOS system bash 3.2.
- No GNU-only tool flags (`readlink -f`, `stat -c`, `sed -i`, `grep -P`, `timeout`); the guard uses only plain `readlink`, `mkdir -p`, `rm -f`, and `git`.

What actually needs a real host: Test 3 is the negative control asserting that an unguarded `mkdir -p` through a dangling symlink exits non-zero. BSD `mkdir(1)`'s `build()` does `stat()` → `ENOENT` → `mkdir()` → `EEXIST` → error, so the same failure is expected, but it has never been executed on BSD userland. If that assumption is wrong, Test 3 passes vacuously on macOS and stops attributing Test 2 to the guard.

Low priority: the fix itself is verified on Linux and by a real branch-mode reproduction (t1201 item 2); this only closes the BSD-portability assumption.

## Verification Checklist

- [x] Run `bash tests/test_install_create_data_dirs.sh` on a macOS/BSD host — expect 40/40 pass, and in particular confirm Test 3 (negative control) still exits non-zero, i.e. BSD `mkdir -p` also fails through a dangling symlink — PASS 2026-09-08 17:11 auto: macOS 15.7.3 (Darwin 24.6.0, arm64) -- 40/40 pass, exit 0, under both PATH bash 5.3.9 and system bash 3.2.57. Test 3 negative control non-vacuous: BSD mkdir -p through a dangling symlink exits 1 (ENOENT 'No such file or directory', not the predicted EEXIST 'File exists' -- non-zero either way, which is all T3 asserts).
