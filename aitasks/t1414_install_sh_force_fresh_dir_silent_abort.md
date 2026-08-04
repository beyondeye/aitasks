---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [install, shell]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1075
implemented_with: claudecode/opus5
created_at: 2026-08-04 17:33
updated_at: 2026-08-04 18:58
---

## Problem

`install.sh:894-895` — in `show_upgrade_changelog()`, the `else` branch uses a
**bare `return`**, which inherits the exit status of the immediately preceding
failed test:

```bash
    local current_version=""
    if [[ -f "$install_dir/VERSION" ]]; then
        current_version="$(cat "$install_dir/VERSION")"
    elif [[ -f "$install_dir/.aitask-scripts/VERSION" ]]; then
        current_version="$(cat "$install_dir/.aitask-scripts/VERSION")"
    else
        return  # Can't determine current version, skip   <-- returns 1
    fi
```

When neither VERSION file exists, the last command evaluated is the failed
`[[ -f "$install_dir/.aitask-scripts/VERSION" ]]` test, so `return` propagates
status **1**. `install.sh` runs under `set -euo pipefail`, so the caller treats
that as fatal and the script **aborts silently** — right after the tarball has
downloaded, with nothing installed and no error message printed.

## Trigger

`bash install.sh --force` into a directory that has no `VERSION` and no
`.aitask-scripts/VERSION`. `FORCE=true` skips the early return at
`install.sh:885`, so the version lookup runs and falls through to line 895.

Observed during t1085 verification:

```
$ bash install.sh --force --dir /tmp/fresh --version 0.29.0 < /dev/null
[ait] aitask framework installer
[ait] Downloading aitasks v0.29.0: https://github.com/.../aitasks-v0.29.0.tar.gz
$ echo $?
1
$ ls /tmp/fresh
(empty — nothing installed, no error shown)
```

`bash -x` shows the abort precisely: `show_upgrade_changelog` →
`[[ -f .../VERSION ]]` (false) → `return` → EXIT trap fires.

## Minimal repro (no network, no aitasks)

```bash
bash -c 'set -euo pipefail
f() { local d=/nonexistent
  if   [[ -f "$d/VERSION" ]]; then :
  elif [[ -f "$d/.aitask-scripts/VERSION" ]]; then :
  else return; fi          # inherits status 1
}
f; echo "REACHED-AFTER-f"'
# prints nothing, exits 1
```

## Impact

This is the exact command `install.sh:142` recommends to users for a forced
fresh re-install:

```
  To force a fresh re-install via curl-pipe:
      curl -fsSL https://raw.githubusercontent.com/<repo>/main/install.sh | bash -s -- --force
```

Anyone following that hint against a directory whose `.aitask-scripts/VERSION`
is missing (fresh dir, or a partially-removed install where `ait` survives but
VERSION does not) gets a silent no-op exit 1.

Normal `ait upgrade` is **not** affected: `aitask_upgrade.sh:152` targets a
directory that already carries a `VERSION` file, so the lookup succeeds and the
function proceeds past line 895.

## Provenance

Pre-existing, not a recent regression:

```
$ git log --oneline -1 -L 894,896:install.sh
485b7bd17 Add ait install command and automatic update check (t85_11)
```

## Fix

Make the early return explicit:

```bash
        return 0  # Can't determine current version, skip
```

Also audit the two sibling bare `return`s in the same function
(`install.sh:886` and `install.sh:912`). Both are currently safe only by
accident of what precedes them (`[[ "$FORCE" != true ]]` succeeded; `rm -rf`
succeeded) — a later edit reordering either would reintroduce the same class of
bug. Prefer explicit `return 0` at all three sites.

## Suggested regression test

`tests/test_install_tarball_download.sh` already stubs curl/wget for install.sh.
Add a case asserting `bash install.sh --force --dir <empty-dir>` exits 0 and
installs, and confirm the assertion fails against the unfixed line 895 (a
negative control — the test must be shown to discriminate).

## Discovery

Found while running the t1085 manual-verification checklist (auto-execution
mode). It blocked items 2/4/5/6/7 until the sandbox installs were adapted to
drop `--force`; t1085 itself passed 8/8 after that adaptation. See
`aiplans/archived/p1085_manual_verification_auto.md`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-04T15:59:16Z status=pass attempt=1 type=human
