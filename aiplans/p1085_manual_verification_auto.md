---
Task: t1085_manual_verify_upgrade_no_api.md
Worktree: (none — current-branch mode, profile 'fast')
Branch: main
Base branch: main
Output branch: main
---

# Auto-Execution Plan — t1085 manual verification (upgrade without api.github.com)

Verifies the t1075 change: `ait upgrade` and `install.sh` must reach the
release-assets CDN deterministically, with **no** `api.github.com` REST call
except as an explicitly-forced last resort (which must carry the
`Authorization` header when a token is set).

Code under verification:
- `install.sh:214` `resolve_latest_version_gittags()` — git-tag resolution
- `install.sh:228` `github_api_tarball_url()` — token-aware REST last resort
- `install.sh:257` `download_tarball()` — the 4-way strategy
- `.aitask-scripts/aitask_upgrade.sh:44` `resolve_version()` — explicit version
  skips the API entirely
- `.aitask-scripts/aitask_upgrade.sh:152` — threads `AIT_TARGET_VERSION`

Release tags available upstream (via `git ls-remote`): … 0.28.0, 0.29.0, **0.30.0 (latest)**.
This repo's `.aitask-scripts/VERSION` is `0.30.0`.

---

## Two safety decisions that shape this plan

### A. Never run `ait upgrade` against this repo

`aitask_upgrade.sh:8` sets `AIT_DIR="$SCRIPT_DIR/.."`, and line 152 runs the
downloaded installer with `--force --dir "$AIT_DIR"`. Running `./ait upgrade`
from `/home/ddt/Work/aitasks` would **overwrite this development repo's
`.aitask-scripts/` with a released tarball**, destroying in-flight work.

→ Every install/upgrade in this plan runs inside a throwaway sandbox under
`${TMPDIR:-/tmp}/auto_verify_1085/`. A real release is installed there first,
and `ait upgrade` is invoked from *that* copy, so its `AIT_DIR` is the sandbox.

### B. How `api.github.com` gets blocked — proposed deviation from the checklist

The checklist says "add `127.0.0.1 api.github.com` to /etc/hosts, or firewall
it". That needs root, and it is **unobservable**: a passing run proves only
that nothing broke, not that no call was attempted.

→ Proposed instead: a **PATH shim** for `curl` / `wget` that (a) hard-fails any
invocation whose argv mentions `api.github.com`, exactly as an unresolvable
host would, and (b) appends one line per invocation to a log. Everything else
passes through to the real binary untouched. This is root-free and *stronger*
evidence: item 2's pass criterion becomes "the log contains zero
`api.github.com` lines" rather than "nothing visibly broke".

The shim never writes a token to disk — an `Authorization:` value is recorded
only as `AUTH=yes`.

**If you prefer the literal `/etc/hosts` route, say so at approval** and I will
run the same steps with a sudo-added hosts line instead; items 2/4/5 then pass
on "install succeeded" alone and item 7 becomes non-observable (defer).

Note: `git ls-remote` (item 4's fallback) does not go through `curl`, so the
shim correctly leaves it working — which is exactly the property under test.

---

## Sandbox layout

```
${TMPDIR:-/tmp}/auto_verify_1085/
  shim/curl   shim/wget      # block + log api.github.com
  shim_nogit/git             # item 7 only: makes ls-remote return empty
  netlog.txt                 # one line per intercepted invocation
  up/                        # items 2,3 — ait upgrade sandbox (git init'd)
  inst_latest/               # item 4
  inst_ver/                  # item 5
  inst_local/                # item 6
  inst_token/                # item 7
  aitasks-v0.30.0.tar.gz     # fixture for item 6
```

All installer invocations use `--force` and `< /dev/null` so the interactive
prompts at `install.sh:121` and `install.sh:152` never fire.

---

## Pre-built Auto-Execution Plan

1. `[pass]` Block api.github.com so the REST API is unreachable.
   - Strategy: CLI invocation + PATH shim (see deviation B above).
   - Action: create `shim/curl` and `shim/wget` wrapping the real binaries
     (paths baked in from `command -v` at creation time); export
     `PATH="$SCRATCH/shim:$PATH"`. Probe both hosts:
     `curl -sS https://api.github.com/rate_limit` and
     `curl -fsSI https://github.com`.
   - Pass criterion: the api probe fails (exit 6) **and** logs `BLOCKED=yes`,
     while the github.com probe still succeeds — i.e. the block is targeted,
     not a blanket network outage.
   - Fail / defer fallback: real network unreachable at all → **defer** the
     whole checklist (nothing below is meaningful offline).

2. `[pass]` `ait upgrade <VERSION>` succeeds via the CDN with NO api.github.com call.
   - Strategy: CLI invocation in the sandbox.
   - Action: `bash install.sh --force --dir $SCRATCH/up --version 0.29.0` (this
     bootstrap runs with the shim active too), `git init $SCRATCH/up`, truncate
     `netlog.txt`, then `$SCRATCH/up/ait upgrade 0.30.0`.
   - Pass criterion: exit 0; `$SCRATCH/up/.aitask-scripts/VERSION` reads
     `0.30.0`; **`netlog.txt` contains zero `api.github.com` lines**; the output
     names the CDN URL `…/releases/download/v0.30.0/aitasks-v0.30.0.tar.gz`.
   - Fail / defer fallback: any `api.github.com` line → **fail** (this is the
     defect t1075 removed). Network flake on the CDN → defer.

3. `[pass]` `ait upgrade <older-version>` installs THAT version, not latest.
   - Strategy: CLI invocation, continuing in `$SCRATCH/up` (now at 0.30.0).
   - Action: truncate `netlog.txt`; `$SCRATCH/up/ait upgrade 0.28.0`.
   - Pass criterion: `$SCRATCH/up/.aitask-scripts/VERSION` reads exactly
     `0.28.0` (**not** `0.30.0`), and the downloaded asset named in the output is
     `aitasks-v0.28.0.tar.gz`. Zero `api.github.com` lines.
   - Fail / defer fallback: VERSION lands on 0.30.0 → **fail** (silent
     degrade-to-latest, the exact `install.sh:294` guard under test).

4. `[pass]` Standalone `bash install.sh` (no `--version`) resolves latest via the git-tag fallback.
   - Strategy: CLI invocation, api still blocked.
   - Action: truncate `netlog.txt`;
     `bash install.sh --force --dir $SCRATCH/inst_latest < /dev/null`.
   - Pass criterion: exit 0; stdout shows `Resolving latest aitasks release...`
     then `Downloading aitasks v0.30.0`; installed VERSION is `0.30.0`; zero
     `api.github.com` lines in the log.
   - Fail / defer fallback: falls through to `Fetching latest release via the
     GitHub API...` → **fail** (git-tag resolution did not work).

5. `[pass]` `bash install.sh --version <VERSION>` downloads that exact version from the CDN.
   - Strategy: CLI invocation.
   - Action: truncate `netlog.txt`;
     `bash install.sh --force --dir $SCRATCH/inst_ver --version 0.27.1 < /dev/null`.
   - Pass criterion: installed VERSION is exactly `0.27.1`; the log's only
     download line is the `releases/download/v0.27.1/` CDN URL; zero
     `api.github.com` lines; **no** `Resolving latest` line (explicit version
     must short-circuit resolution entirely).
   - Fail / defer fallback: any other installed version → **fail**.

6. `[pass]` `--local-tarball <path>` still works unchanged.
   - Strategy: CLI invocation with a fixture.
   - Action: fetch the fixture once
     (`curl -fsSL …/releases/download/v0.30.0/aitasks-v0.30.0.tar.gz -o $SCRATCH/aitasks-v0.30.0.tar.gz`),
     truncate `netlog.txt`, then
     `bash install.sh --force --dir $SCRATCH/inst_local --local-tarball $SCRATCH/aitasks-v0.30.0.tar.gz < /dev/null`.
   - Pass criterion: exit 0; installed VERSION is `0.30.0`; **`netlog.txt` is
     empty** — the local path must make zero network calls of any kind.
   - Fail / defer fallback: any logged call during the local install → **fail**
     (regression: `install.sh:260` should return before any resolution).

7. `[pass]` A forced REST fallback carries the `Authorization` header when a token is set.
   - Strategy: CLI invocation with a second shim that starves the git-tag path.
   - Action: create `shim_nogit/git` that prints nothing for `ls-remote` and
     delegates every other subcommand to the real `git`; prepend it to PATH.
     Truncate `netlog.txt`. Run with a **dummy** token so no real credential is
     used or logged:
     `GH_TOKEN=AUTHPROBE bash install.sh --force --dir $SCRATCH/inst_token < /dev/null`.
   - Pass criterion: the run reaches `Fetching latest release via the GitHub
     API...` and `netlog.txt` shows exactly one `api.github.com` line with
     `AUTH=yes`. The install itself is **expected to die** ("Could not find
     release tarball") because the API is blocked — that failure is the
     scenario, not a defect.
   - Fail / defer fallback: `AUTH=no` on that line → **fail** (the
     `install.sh:234` auth array did not thread the token). If a *real*
     `GH_TOKEN`/`GITHUB_TOKEN` is present in the environment, additionally run
     one unblocked live probe of `https://api.github.com/rate_limit` and confirm
     an authenticated 5000/hour limit rather than a 60/hour rate-limit error;
     with no real token available, record that sub-check as covered-by-proxy in
     the note rather than deferring the item.

8. `[pass]` Unblock api.github.com afterward.
   - Strategy: cleanup + CLI probe.
   - Action: remove `$SCRATCH/shim` and `$SCRATCH/shim_nogit` from PATH and
     from disk; probe `curl -sS -o /dev/null -w '%{http_code}'
     https://api.github.com/rate_limit` in a fresh shell.
   - Pass criterion: the probe returns an HTTP status (200 or 403 — both prove
     reachability) and no shim remains on disk. Because the block was
     process-local PATH state, nothing system-wide was ever modified, so there
     is no host file to repair.
   - Fail / defer fallback: shim files still present → **fail** until removed.

---

## Execution Log

Executed 2026-08-04 under the approved pre-built plan (PATH-shim block, real
network). Final state: **8 items, 8 pass, 0 fail, 0 skip, 0 defer.**

Environment notes:
- No `wget` on this box, so only a `curl` shim was needed (`install.sh:99`
  selects curl when both are probed).
- **Plan adaptation (see "Blocking defect" below):** fresh-directory installs
  dropped `--force`. `ait upgrade` still passes `--force` internally
  (`aitask_upgrade.sh:152`), so items 2 and 3 exercised the real forced path
  unchanged; only the sandbox *bootstraps* were adapted.

### Item 1 — Block api.github.com
- Item text: Block api.github.com so the REST API is unreachable.
- Approach: PATH shim (CLI invocation) — `shim/curl` wrapping `/usr/bin/curl`.
- Action run: probe `https://api.github.com/rate_limit` and `https://github.com`
  with the shim on PATH.
- Output (trimmed): `curl: (6) Could not resolve host: api.github.com` exit 6,
  logged `BLOCKED=yes`; github.com returned `http=200`, logged `BLOCKED=no`.
- Verdict: **pass** — targeted block, not a network outage.

### Item 2 — `ait upgrade <VERSION>` succeeds with no API call
- Item text: Run `ait upgrade <VERSION>` for a known existing release; confirm it
  SUCCEEDS with NO call to api.github.com.
- Approach: CLI invocation in the sandbox (bootstrapped at 0.29.0).
- Action run: `$SCRATCH/up/ait upgrade 0.30.0` with the shim active.
- Output (trimmed): exit 0; `Current version: 0.29.0` → `Target version: 0.30.0`;
  `Downloading aitasks v0.30.0: …/releases/download/v0.30.0/aitasks-v0.30.0.tar.gz`;
  resulting `VERSION` = `0.30.0`. netlog held exactly two lines —
  `raw.githubusercontent.com/…/v0.30.0/install.sh` and the release CDN — and
  **zero** `api.github.com` lines.
- Verdict: **pass**.

### Item 3 — Older version installs that version, not latest
- Item text: Run `ait upgrade <older-version>` and confirm it installs THAT
  version's tarball, not latest.
- Approach: CLI invocation, continuing in the same sandbox (now 0.30.0).
- Action run: `$SCRATCH/up/ait upgrade 0.28.0`.
- Output (trimmed): exit 0; `Current version: 0.30.0` → `Target version: 0.28.0`;
  asset `aitasks-v0.28.0.tar.gz`; resulting `VERSION` = `0.28.0`. Zero
  `api.github.com` lines.
- Verdict: **pass** — no silent degrade-to-latest; the `install.sh:294` guard holds.

### Item 4 — Standalone `install.sh` resolves latest via the git-tag fallback
- Item text: Run a standalone `bash install.sh` (no --version) while
  api.github.com is still blocked; confirm it resolves and installs the latest
  release via the git-tag fallback.
- Approach: CLI invocation into a fresh sandbox dir.
- Action run: `bash install.sh --dir $SCRATCH/inst_latest < /dev/null`.
- Output (trimmed): exit 0; `Resolving latest aitasks release...` then
  `Downloading aitasks v0.30.0: …/download/v0.30.0/…`; `VERSION` = `0.30.0`.
  No `Fetching latest release via the GitHub API` line. netlog held a **single**
  line (the CDN download) — `git ls-remote` never goes through curl, which is
  precisely the rate-limit exemption under test.
- Verdict: **pass**.

### Item 5 — `install.sh --version <V>` downloads that exact version
- Item text: Confirm `bash install.sh --version <VERSION>` downloads that exact
  version from the CDN.
- Approach: CLI invocation into a fresh sandbox dir.
- Action run: `bash install.sh --dir $SCRATCH/inst_ver --version 0.27.1 < /dev/null`.
- Output (trimmed): exit 0; `Downloading aitasks v0.27.1: …/download/v0.27.1/…`;
  `VERSION` = `0.27.1`; **no** `Resolving latest` line (explicit version
  short-circuits resolution entirely); zero `api.github.com` lines.
- Verdict: **pass**.

### Item 6 — `--local-tarball` unchanged
- Item text: Confirm the `--local-tarball <path>` install path still works
  unchanged.
- Approach: CLI invocation with a CDN-fetched fixture (2,154,145 bytes).
- Action run: `bash install.sh --dir $SCRATCH/inst_local --local-tarball
  $SCRATCH/aitasks-v0.30.0.tar.gz < /dev/null`, with netlog truncated
  immediately before the run.
- Output (trimmed): exit 0; `VERSION` = `0.30.0`; no download/resolve lines;
  **netlog empty — zero network calls of any kind**, confirming
  `install.sh:260` returns before any resolution.
- Verdict: **pass**.

### Item 7 — Forced REST fallback carries the Authorization header
- Item text: Set GH_TOKEN and confirm any remaining REST call (force the
  fallback) carries the Authorization header (no rate-limit error).
- Approach: CLI invocation + a second shim (`shim_nogit/git`) that returns
  nothing for `ls-remote`, starving the git-tag path so `download_tarball()`
  must fall through to `github_api_tarball_url()`.
- Action run: `GH_TOKEN=AUTHPROBE bash install.sh --dir $SCRATCH/inst_token
  < /dev/null`; then an unblocked live probe of `/rate_limit` with and without
  a real token.
- Output (trimmed): run reached `Fetching latest release via the GitHub API...`
  and produced exactly one netlog line —
  `BLOCKED=yes|AUTH=yes|-sS --max-time 15 -H Authorization: Bearer *** https://api.github.com/repos/beyondeye/aitasks/releases/latest`.
  The install then died with `Could not find release tarball` (expected: the API
  is blocked). Token never written to disk (`grep -c AUTHPROBE netlog` = 0).
  Live probe: unauthenticated `limit=60`, authenticated with the same header
  form `limit=5000 remaining=4980`.
- Verdict: **pass** — both clauses covered: `install.sh:234` threads the token,
  and that header form demonstrably lifts the 60/hour cap.

### Item 8 — Unblock afterward
- Item text: Unblock api.github.com afterward.
- Approach: cleanup + CLI probe in a clean shell.
- Action run: `rm -rf $SCRATCH/shim $SCRATCH/shim_nogit`; probe `/rate_limit`.
- Output (trimmed): no shim dirs remain; `command -v curl` = `/usr/bin/curl`;
  `api.github.com/rate_limit` returns `http=200`; `/etc/hosts` contains no
  `api.github.com` entry.
- Verdict: **pass** — the block was process-local PATH state, so nothing
  system-wide needed reverting.

---

## Blocking defect found (pre-existing, unrelated to t1075)

`install.sh:894-895` — in `show_upgrade_changelog()`, the `else` branch's **bare
`return`** inherits the exit status of the immediately preceding failed
`[[ -f "$install_dir/.aitask-scripts/VERSION" ]]` test, i.e. **1**. Under the
script's `set -euo pipefail`, the caller treats that as a fatal error and the
install aborts **silently** — right after the tarball downloads, with nothing
installed and no message printed.

Trigger: `bash install.sh --force` into a directory that has no
`VERSION` / `.aitask-scripts/VERSION`. `FORCE=true` skips the line-885 early
return, and the version lookup then falls through to line 895. Observed here as
`exit=1` with the log ending at the `Downloading aitasks v0.29.0:` line.

Minimal repro:
```bash
bash -c 'set -euo pipefail
f() { local d=/nonexistent
  if   [[ -f "$d/VERSION" ]]; then :
  elif [[ -f "$d/.aitask-scripts/VERSION" ]]; then :
  else return; fi          # inherits status 1
}
f; echo "REACHED-AFTER-f"'   # never prints; exit 1
```

Not a t1075 regression: `git log -L 894,896:install.sh` attributes the line to
`485b7bd17` ("Add ait install command and automatic update check (t85_11)").

Real-user impact: this is the exact command `install.sh:142` recommends for a
forced fresh re-install (`curl -fsSL … | bash -s -- --force`). Normal
`ait upgrade` is unaffected — it targets a directory that already has a
`VERSION` file, so the lookup succeeds and the function proceeds.

Fix: make the early return explicit — `return 0` at line 895 (and audit the
other bare `return`s in the same function at lines 886 and 912, which are
currently safe only by accident of what precedes them).

- **Upstream defects identified:** `install.sh:894-895 — bare 'return' in
  show_upgrade_changelog() inherits status 1 from the preceding failed [[ -f ]]
  test, silently aborting any 'install.sh --force' into a directory with no
  existing VERSION file (set -e); needs 'return 0'`

## Cleanup

- `rm -rf ${TMPDIR:-/tmp}/auto_verify_1085/` — removes the shims, the four
  sandbox installs, the upgrade sandbox, the tarball fixture, and `netlog.txt`.
- No tmux sessions are created.
- No `/etc/hosts` or firewall change is made (under deviation B), so nothing
  system-wide needs reverting. If the `/etc/hosts` alternative is chosen at
  approval, cleanup additionally removes the added line under sudo.
- Nothing outside the scratch directory is written. In particular this repo's
  `.aitask-scripts/` is never a `--dir` target. `ait upgrade` does delete
  `$HOME/.aitask/update_check` (`aitask_upgrade.sh:155`); that is a
  regenerated cache file and is left as-is.
