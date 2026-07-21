---
Task: t1197_drift_guard_wiring_position_check.md
Base branch: main
plan_verified: []
---

# t1197 — Make call *position* part of the seed-wiring contract

## Context

`tests/test_seed_manifest_drift.sh` (added by t1194) guards against seed-metadata
drift between install.sh's `install_seed_*()` family and the source-tree setup
path. It derives the install-side manifest by running only those installers that
`main()` actually calls, detected by grepping the `declare -f main` body for each
function name.

The grep matches a call **anywhere** in `main()`. But `install.sh:1266` runs
`rm -rf "$INSTALL_DIR/seed"` once the installers are done, so an installer wired
*after* that line would:

- **pass** the guard — the test fixture still has a populated `seed/` when the
  derivation invokes the function directly; but
- **deliver nothing** in a real tarball install — `seed/` is already gone by the
  time `main()` reaches the call.

That is a false negative in exactly the drift class the guard exists to catch.
The same gap backs `list_unwired_installers()` (Test 6).

Intended outcome: call **position** becomes part of the wiring contract, so a
post-cleanup installer is reported rather than silently accepted — and the
guard fails **loudly** if the anchor it keys on ever disappears.

### Verified against live source

- `declare -f main` renders the cleanup verbatim as `    rm -rf "$INSTALL_DIR/seed";`
  (the only other `rm -rf` in `main()` is the tmpdir trap, which does not contain
  `$INSTALL_DIR/seed`).
- All 18 `install_seed_*` functions are wired **before** it, each rendering as a
  bare `    install_seed_x;` line — `declare -f` pretty-prints one command per
  line, so command position ≈ line start. Truncation is therefore a no-op for
  the live path and Tests 2/6 stay green.

## Scope

One file: `tests/test_seed_manifest_drift.sh`. No production-code changes.

## Implementation

### 1. Shared seam (`WIRING_SRC`)

Both derivation helpers run in their **own** `bash -c` subprocess (install.sh and
aitask_setup.sh both define `info`/`warn`/`die`, so they are never sourced into
one shell). Duplicating the truncation in both would let it drift out of sync —
the very failure mode this task fixes. Instead define one quoted-heredoc source
string near the other derivation helpers, passed as a positional arg and `eval`'d
inside each subprocess:

```bash
WIRING_SRC="$(cat <<'SRC'
# The cleanup line `declare -f main` renders once every seed installer has run.
# Anything wired after it is too late to deliver a seed file in a real install.
SEED_CLEANUP_ANCHOR='rm -rf "$INSTALL_DIR/seed"'

# main_body_before_cleanup <body> — the portion of <body> preceding the seed
# cleanup. Errors (3) if the anchor is absent rather than falling back to the
# whole body: a silent fallback would restore the position-blind match the
# moment install.sh reworded that line.
main_body_before_cleanup() {
    local body="$1"
    if [[ "$body" != *"$SEED_CLEANUP_ANCHOR"* ]]; then
        printf 'main_body_before_cleanup: seed-cleanup anchor not found in main() body\n' >&2
        return 3
    fi
    printf '%s' "${body%%"$SEED_CLEANUP_ANCHOR"*}"
}

main_body_after_cleanup()  { ... }   # same guard, ${body#*"$ANCHOR"}
splice_probe_wiring()      { ... }   # insert a synthetic call site pre|post anchor

# calls_installer <body> <fn> — <fn> invoked at COMMAND POSITION in <body>.
calls_installer() {
    grep -qE "(^|[;&|{(])[[:space:]]*$2([^[:alnum:]_]|$)" <<< "$1"
}

wired_installers()       { ... }   # installers called before the cleanup
postcleanup_installers() { ... }   # called ONLY after it — the position defect
SRC
)"
```

Pure bash prefix/suffix removal (`${body%%"$ANCHOR"*}`) rather than
`sed`/`grep -P` — no regex escaping of `$` and `/`, and no BSD-vs-GNU divergence
(`aidocs/framework/sed_macos_issues.md`).

**Tightened matcher (was: name anywhere).** The old
`(^|[^[:alnum:]_])<fn>([^[:alnum:]_]|$)` matched the function *name* anywhere, so
a mention inside a string — e.g. `info "Storing install_seed_models seeds..."` —
counted as a call. `calls_installer` requires the name at command position:
line start, or right after `;` / `&&` / `||` / `|` / `{` / `(`. Verified: all 18
current installers still match, `x && install_seed_y` and `{ install_seed_y; }`
match, and an `info "…install_seed_y…"` mention no longer does. Failures in this
matcher are **fail-loud** (a missed call is reported as *unwired*, never silently
accepted). Residual limitation, accepted and commented in the source: a mention
inside a single-line quoted string that happens to follow one of those separator
characters would still match.

### 2. Rewire the two derivation helpers — with failure propagation

- **`derive_install_manifest <fixture> [probe_fn_src] [probe_wiring]
  [probe_position]`** — new 4th param, default `pre`. The probe call site is now
  **spliced relative to the anchor** via `splice_probe_wiring` instead of being
  appended to `$(declare -f main)` (which lands after the closing `}`, i.e.
  effectively post-cleanup).

  Failure must not be masked at either level:
  - *Inside the subprocess:* capture, then check —
    `wired="$(wired_installers "$main_body")" || exit 3`, then `for fn in $wired`.
    Iterating `$(wired_installers …)` directly would turn a nonzero status into a
    harmless empty loop.
  - *In the outer helper:* stop swallowing the subprocess result. Redirect stdout
    to `/dev/null` but stderr to a temp file; capture `rc`. On `rc != 0`, dump the
    captured stderr (so the `anchor not found` diagnostic is visible), print the
    poison line `DERIVATION_FAILED` **as the manifest**, and `return "$rc"` —
    **without** snapshotting. The poison line makes any downstream
    `compare_manifests` report `INSTALL_ONLY:DERIVATION_FAILED` instead of the
    broad, easily-misread drift an empty manifest would produce.

- **`list_unwired_installers [probe_fn_src] [probe_wiring] [probe_position]`** —
  same splice + `wired_installers` complement, so a post-cleanup installer is
  reported by name. On subprocess failure emit the sentinel `ANCHOR_MISSING`
  (plus the captured stderr) rather than dumping all 18 installers as unwired.

- Amend the `derive_install_manifest` doc comment: `probe_fn_src` must not
  redefine `main()` **except** for the anchor-control probes in §3, which do so
  deliberately to exercise the missing-anchor path.

### 3. Position diagnostics (developer-facing)

A post-cleanup wiring mistake otherwise surfaces as ordinary `SETUP_ONLY` drift,
which reads as "you forgot the installer" when in fact it exists. So:

- Test 2's `SETUP_ONLY` hint gains: *"…or it IS defined and called, but **after**
  the `rm -rf $INSTALL_DIR/seed` cleanup — see the post-cleanup list below."*
  followed by `list_postcleanup_installers` output when non-empty.
- Test 6's failure message names post-cleanup-wired installers separately from
  never-called ones, with the explicit instruction that the call must precede the
  seed cleanup.

### 4. New tests (appended as 9–11; existing 1–8 keep their numbers)

- **T9 — position flip on the manifest surface.** Reuses the real setup-side
  `*_instructions.seed.md` glob (as Test 4 does) so no synthetic setup code is
  needed: a fixture carrying `seed/probe_instructions.seed.md` plus a synthetic
  `install_seed_postcleanup_probe` that copies it into `aitasks/metadata/`.
  - wired `pre`  → manifest matches `$TESTROOT/m_setup_probe`, **no drift**
    (proves the truncation did not cut too early);
  - wired `post` → `SETUP_ONLY:probe_instructions.seed.md` is reported
    (the real-world drift: both sides were added, but the install side is dead
    code — pre-fix the guard called this parity).
- **T10 — wiring surface.** `list_unwired_installers` with the probe wired `pre`
  reports nothing; wired `post` reports `install_seed_postcleanup_probe` and
  nothing else, and `list_postcleanup_installers` names it. Plus a **mention
  probe**: an installer whose name appears only inside a pre-cleanup
  `info "…"` string is still reported unwired (the tightened matcher).
- **T11 — missing-anchor controls, unit *and* integration.**
  - Direct: `main_body_before_cleanup` / `splice_probe_wiring` given an anchorless
    body exit `3` with the `anchor not found` diagnostic.
  - Integration through `derive_install_manifest` with a main-redefining probe:
    nonzero return, `DERIVATION_FAILED` manifest, diagnostic on stderr.
  - Integration through `list_unwired_installers` likewise: `ANCHOR_MISSING`.

  These are the ones that matter — the direct helper test alone can pass while
  the real guard path degrades quietly, which is exactly what happens when
  install.sh rewords or moves the cleanup line.

## Risk

### Code-health risk: low

- Restructuring the guard's own derivation helpers could weaken the guard
  silently (a truncation that cuts too early would drop real installers and
  still "pass") · severity: low · → mitigation: covered in-change by the T9
  `pre` leg, the unchanged T2 live-parity assertion, and the verified 18/18
  pre-cleanup wiring count.
- The tightened command-position matcher could miss a future call form and
  report a wired installer as unwired · severity: low · → mitigation: none
  needed — the failure direction is loud (a false "unwired" report fails Test 6
  visibly), never a silent pass; all 18 current forms verified matching.
- The shared `eval`'d source string adds one level of indirection versus inline
  code · severity: low · → mitigation: none needed — it is the alternative to
  duplicating the truncation across two subprocesses, which is the drift the
  task is fixing.

### Goal-achievement risk: low

- "Assert the guard reports it" is interpreted as the `SETUP_ONLY` flip (the
  install side goes dead while the setup side still delivers), rather than a
  bare "probe absent from the manifest" check · severity: low · → mitigation:
  the flip is asserted in both directions on both surfaces (T9/T10), so either
  reading is covered.

## Verification

- `bash tests/test_seed_manifest_drift.sh` — all existing 28 assertions plus the
  new ones pass; Tests 2, 3, 6, 7 unchanged in verdict.
- **Simulate the future change** (the defect this task exists to catch):
  temporarily move an `install_seed_*` call in `install.sh` `main()` to after
  `rm -rf "$INSTALL_DIR/seed"` and confirm the guard now fails, naming it in the
  post-cleanup diagnostic; revert.
- **Simulate anchor loss:** temporarily reword the cleanup line in `install.sh`
  and confirm the run fails with the anchor diagnostic (not empty/broad drift);
  revert.
- `shellcheck tests/test_seed_manifest_drift.sh`.

## Step 9 (Post-Implementation)

Merge, gate run (`risk_evaluated`), archival per the shared workflow.

## Post-Review Changes

### Change Request 1 (2026-07-21 11:40) — pre-implementation, on the plan

- **Requested by user:** three concerns on the draft plan — (1) the missing-anchor
  failure could still be masked by the helper wrapper (`set +eu`, unconditional
  `snapshot`, and `for fn in $(wired_installers …)` swallowing a nonzero status);
  (2) the fix kept the old name-anywhere grep, so it was still not a true
  call-site check; (3) no developer-facing diagnostic naming the position
  contract.
- **Changes made:** all three verified valid against live source and folded into
  the plan before implementation — capture-then-check inside the subprocess plus
  rc/stderr propagation and a `DERIVATION_FAILED` poison manifest in the wrapper;
  a tightened command-position matcher (`calls_installer`); and
  `list_postcleanup_installers` feeding explicit position text into the Test 2
  and Test 6 failure messages. Integration-level anchor controls were added
  alongside the direct helper controls.
- **Files affected:** the plan only (this change request predates implementation).

### Change Request 2 (2026-07-21 12:05) — at Step 8 review

- **Requested by user:** (1) blocking — `.claude/settings.local.json` was modified
  and must not land in a test-only commit; (2) follow-up — Test 2 still compared
  the poisoned manifest against the full setup manifest, so an anchor loss also
  emitted ~19 spurious `SETUP_ONLY` lines, weakening the plan's "not broad drift"
  claim.
- **Changes made:** (1) verified the settings diff is pre-existing (already `M` at
  session start, unrelated permission-allowlist entries) — deliberately **not**
  reverted, and excluded from the commit by staging `tests/` by explicit path;
  (2) upgraded from follow-up to in-change: Test 2 now captures
  `derive_install_manifest`'s rc and short-circuits, skipping the comparison
  entirely on derivation failure.
- **Files affected:** `tests/test_seed_manifest_drift.sh`.

## Final Implementation Notes

- **Actual work done:** `tests/test_seed_manifest_drift.sh` only (+~290/−35); no
  production code changed. Added the shared `WIRING_SRC` seam (anchor constant,
  `require_anchor`, `main_body_before_cleanup` / `main_body_after_cleanup`,
  `splice_probe_wiring`, `calls_installer`, `all_installers`,
  `wired_installers`, `postcleanup_installers`), rewired
  `derive_install_manifest` (new `probe_position` param, splice instead of
  append, rc + stderr propagation, `DERIVATION_FAILED` poison manifest) and
  `list_unwired_installers` / new `list_postcleanup_installers` (both via a
  shared `_installer_wiring_report`), added position diagnostics to the Test 2
  and Test 6 failure messages, and added Tests 9–11. Assertions went 28 → 44.

- **Deviations from plan:** none in substance. Two additions made during
  implementation: the Test 2 rc short-circuit (Change Request 2), and suppressing
  the `ANCHOR_MISSING` sentinel from the post-cleanup diagnostic blocks so a
  failed wiring check is not restated as a finding.

- **Issues encountered:**
  - *A first defect simulation gave a false pass.* The python edit that was
    supposed to **move** `install_seed_tmux_conf` past the cleanup only
    **added** a second call site (the original block did not match), leaving it
    wired both pre- and post-cleanup; and `install_seed_tmux_conf` writes to
    `.aitask-scripts/templates/`, not `aitasks/metadata/`, so it cannot move the
    manifest at all. Redone with `install_seed_task_types` and assertion-guarded
    string replacement (`assert s.count(old)==1`) so a non-matching edit fails
    loudly instead of silently no-op'ing.
  - *Subprocess exit status.* The installer loop's last command determines the
    subprocess status, so a benign installer returning nonzero would have been
    misreported as `DERIVATION_FAILED`. Fixed with an explicit `exit 0` after the
    loop, leaving `exit 3` as the sole failure signal.

- **Key decisions:**
  - One shared `eval`'d source string rather than duplicating the truncation in
    the two `bash -c` subprocesses — duplication is precisely the drift this
    guard exists to catch.
  - Bash prefix/suffix removal (`${body%%"$ANCHOR"*}`) rather than `sed`: no
    escaping of the `$` and `/` in the anchor, and no BSD-vs-GNU divergence.
  - Tightened the matcher to command position rather than merely documenting the
    limitation. Verified all 18 current installers still match and that an
    `info "…install_seed_x…"` mention no longer does. The failure direction is
    loud (a missed call reports as *unwired*), never a silent pass. Residual
    limitation is commented in the source.
  - Verified with **independent ground truth**: the same broken `install.sh`
    (with `install_seed_task_types` wired post-cleanup) makes the pre-fix guard
    report *28 passed / 0 failed* and the fixed guard report 12 failures naming
    the installer — proving the fix, not the fixture, is what catches it.

- **Upstream defects identified:** None
