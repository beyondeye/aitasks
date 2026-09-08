---
Task: t1397_atomic_write_macos_portability.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1397 — macOS portability of `lib/atomic_write.sh` (auto-verification)

Autonomous auto-execution record for the manual-verification checklist. The plan
was written retroactively; every command below was actually run.

**Environment:** macOS 15.7.3 (Darwin 24.6.0), arm64 (Apple M-series),
bash 5.3.9(1) `aarch64-apple-darwin24.6.0`, BSD `stat` / `mktemp` / `readlink`.
`stat -c '%a'` exits 1 on this box, so the BSD fallback branch is genuinely the
one under test rather than merely present.

## Execution Log

### Item 1 — `bash tests/test_atomic_write_sh.sh` on macOS (30 assertions)

- Item text: Run `bash tests/test_atomic_write_sh.sh` on macOS — 30 assertions, all must pass.
- Approach: CLI invocation.
- Action run: `bash tests/test_atomic_write_sh.sh`
- Output (trimmed): sections `staged beside the resolved destination` / `mode` /
  `symlinks` / `retarget between stage and commit` / `directory destination` /
  `render failures` / `commit failure` / `ait_atomic_write_text round trip`;
  `Total: 30  Pass: 30  Fail: 0  PASS`.
- Verdict: **pass**

### Item 2 — `bash tests/test_atomic_task_file_writes.sh` on macOS (62 assertions)

- Item text: Run `bash tests/test_atomic_task_file_writes.sh` on macOS — 62 assertions.
- Approach: CLI invocation.
- Action run: `bash tests/test_atomic_task_file_writes.sh` (with `set -o pipefail`)
- Output (trimmed): all seven call-site sections green
  (`aitask_update.sh`, `aitask_create.sh`, `aitask_plan_verified.sh`,
  `aitask_issue_import.sh`, `aitask_gate_pass.sh`, `aitask_plan_externalize.sh`,
  `aitask_projects.sh`); `Total: 62  Pass: 62  Fail: 0  PASS`, exit 0.
- Verdict: **pass**

### Item 3 — the converted scripts' own suites

- Item text: Run the converted scripts' own suites: `test_plan_verified.sh`,
  `test_plan_externalize.sh`, `test_issue_import_contributor.sh`,
  `test_update_risk.sh`, `test_create_silent_stdout.sh`, `test_projects_cmd.sh`.
- Approach: CLI invocation, looped, capturing exit code and verdict line per suite.
- Action run: `for t in test_plan_verified test_plan_externalize
  test_issue_import_contributor test_update_risk test_create_silent_stdout
  test_projects_cmd; do bash "tests/$t.sh"; done`
- Output (trimmed): all six exit 0 —
  `test_plan_verified` 49/49 PASS;
  `test_plan_externalize` ALL TESTS PASSED;
  `test_issue_import_contributor` ALL TESTS PASSED;
  `test_update_risk` `Results: 21/21 passed, 0 failed`;
  `test_create_silent_stdout` All tests PASSED;
  `test_projects_cmd` `Passed: 42 / 42`.
  (The last two verdict lines are ASCII rules, so each was re-run with `tail -8`
  to read the real counts rather than trusting the final line.)
- Verdict: **pass**

### Item 4 — mode assertions through the BSD `stat -f` branch

- Item text: Confirm the mode assertions specifically: an existing 0640 file stays
  0640, a new file is `0666 & ~umask`, and the same under `umask 0077` (catches a
  hardcoded 0644; goes through `stat -f` on macOS).
- Approach: source `lib/atomic_write.sh` under `bash -c` in a scratch dir and
  exercise `ait_file_mode` / `ait_atomic_write_text` directly, reading modes back
  with `stat -f '%Lp'`.
- Action run: `bash -c 'source .aitask-scripts/lib/atomic_write.sh; …'` in
  `$(mktemp -d "${TMPDIR:-/tmp}/auto_verify_1397_4_XXXXXX")`.
- Output (trimmed):
  - BSD-branch proof: `stat -c '%a'` exit=1; `stat -f '%Lp'` → `640`;
    `ait_file_mode` → `640`. The fallback is the branch that answers.
  - (a) existing 0640 file → `mode=640`, content rewritten to `y`.
  - (b) new file at `umask 0022` → expected `644`, actual `644`.
  - (c) new file under `umask 0077` → expected `600`, actual `600` — so the
    default is derived, not a hardcoded `0644`.
- Verdict: **pass**

### Item 5 — symlink + symlink-cycle cases (`ait_atomic_resolve` chain walk)

- Item text: Confirm the symlink and symlink-cycle cases pass — those exercise
  `ait_atomic_resolve`'s manual chain walk.
- Approach: source the lib under `bash -c` and build relative-symlink, multi-hop,
  cycle, and hop-bound fixtures in a scratch dir.
- Action run: `bash -c 'source .aitask-scripts/lib/atomic_write.sh; …'` in
  `$(mktemp -d "${TMPDIR:-/tmp}/auto_verify_1397_5_XXXXXX")`.
- Output (trimmed):
  - Relative symlink: link survives (`-L` still true), write reaches the backing
    file (`NEW`); resolved to `/private/var/…/sym/real/backing.md` — the walk also
    resolved the `/var` → `/private/var` directory-prefix link.
  - 3-hop chain `h3 → h2 → h1 → target.md`: resolves to `target.md`, write lands
    there (`CHAINED`), `h3` still a symlink.
  - Cycle `a.md → b.md → a.md`: exit 1, `atomic_write: too many symlink levels: …`
    — fails explicitly instead of looping.
  - 40-hop bound: 44 hops → exit 1 with the same message; 30 hops → exit 0.
  - Context: `readlink -f` *is* available on this macOS 15 box; the manual walk is
    retained deliberately for macOS < 12.3.
- Verdict: **pass**

### Item 6 — record BSD-vs-GNU divergence in `sed_macos_issues.md`

- Item text: Record any BSD-vs-GNU divergence in
  `aidocs/framework/sed_macos_issues.md` following the "Files Fixed in tNNN" table
  convention.
- Approach: file inspection + documentation edit.
- Action run: audited the doc's existing sections; `grep` confirmed it carried **no**
  `stat` and no `readlink` guidance at all (the only mention was one bullet inside
  the t926 audit record). Edited `aidocs/framework/sed_macos_issues.md`.
- Output (trimmed): three additions —
  - `## stat Portability` — the `-c` vs `-f` split with a format-string table
    (`%a`/`%s` vs `%Lp`/`%z`), why `%Lp` not `%p`, and the repo's fallback-chain
    idiom with the reason it is safe in both directions.
  - `## readlink Portability` — no BSD `-f` before macOS 12.3, the three things a
    hand-walked chain must get right (hop bound, relative targets resolved against
    the *link's* directory, `cd -P` on the final directory), and the non-symlink
    behavioural difference that makes `-f` a non-drop-in even where it exists.
  - `## Files Audited in t1397` — clean-audit record following the t926 precedent
    (no fixes to list, so "Audited" rather than "Fixed"), covering the environment,
    the three BSD branches, the suite results, and the zsh sourcing caveat below.
- Verdict: **pass** (no divergence to fix; the gap recorded was the documentation's
  own silence on `stat` / `readlink`)

## Finding (recorded, not a defect)

`ait_atomic_tmp` derives its default mode with `$(( 0666 & ~0$(umask) ))`, which is
**bash** arithmetic. Sourced from zsh — where a leading `0` is not octal unless
`setopt octalzeroes` — that yields `1210` instead of `644`, and the file lands with
the wrong permissions. The first hand-probe of item 4 hit exactly this and briefly
looked like a real mode bug; re-running under `bash -c` gave `644`/`600`.

Not a code defect: every framework caller is `#!/usr/bin/env bash`, so the zsh path
is unreachable in production. Recorded in the t1397 audit section because the next
agent verifying by hand in an interactive zsh will reproduce it and misread it.
No follow-up task created.

## Cleanup

- `${TMPDIR}/auto_verify_1397_4_*` — scratch dir for the mode probes. Removed.
- `${TMPDIR}/auto_verify_1397_5_*` — scratch dir for the symlink probes. Removed.
- `${TMPDIR}/verify_seed_*` — checklist seed input. Removed.
- No tmux sessions were created.
