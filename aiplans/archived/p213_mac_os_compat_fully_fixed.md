---
Task: t213_mac_os_compat_fully_fixed.md
Branch: main
Base branch: main
---

## Context

Tasks t209, t211, and t212 fixed the majority of macOS compatibility issues (sed, date, shebangs). Task t213 is a final audit to confirm full compatibility and update the website documentation accordingly.

The audit found **2 remaining HIGH issues** in bash scripts and **1 LOW issue** in a skill file. Everything else is clean.

## Fixes Required

### 1. Fix `grep -oP` with `\K` in `aitask_own.sh:159`

macOS grep does not support `-P` (PCRE). The `\K` keep-out pattern will fail.

**Fix:** Replace with `grep -o` + `sed` pipe.

### 2. Fix `mktemp --suffix=.md` in `aitask_update.sh:926`

macOS BSD `mktemp` does not support `--suffix`.

**Fix:** Use template pattern `mktemp "${TMPDIR:-/tmp}/aitask_XXXXXX.md"`.

### 3. Fix `base64 -d` in skill file (LOW priority)

In `.claude/skills/aitask-reviewguide-import/SKILL.md` lines 41 and 303.

**Fix:** Add a note: `base64 -d` (Linux) or `base64 -D` (macOS).

## Documentation Updates

### 4. Update `aidocs/sed_macos_issues.md` — add mktemp, base64 sections and t213 tracking table
### 5. Update `CLAUDE.md` — add mktemp and base64 portability notes to Shell Conventions
### 6. Update `website/content/docs/installation/_index.md` — macOS → Fully supported, remove Known Issues

## Verification

1. `shellcheck aiscripts/aitask_own.sh aiscripts/aitask_update.sh`
2. `cd website && hugo build --gc --minify`

## Final Implementation Notes
- **Actual work done:** Full audit of all bash scripts (18+ scripts, 2 lib files, 12+ test files) and all Claude skill files (15 SKILL.md files). Found and fixed 2 HIGH issues (grep -oP, mktemp --suffix) and 1 LOW issue (base64 -d). Updated CLAUDE.md and aidocs/sed_macos_issues.md with new portability sections (mktemp, base64) and t213 tracking table. Updated website to mark macOS as "Fully supported" and removed the Known Issues section. Added 4 new tests to test_sed_compat.sh covering the grep-pipe and mktemp patterns.
- **Deviations from plan:** The grep fallback pattern was improved during testing — `|| echo "unknown"` at the end of a pipe doesn't work reliably (sed exits 0 with empty input), so changed to `[[ -z "$owner" ]] && owner="unknown"` which is robust.
- **Issues encountered:** The test for "fallback to unknown on no match" initially failed because `grep -o | sed || echo fallback` doesn't trigger the fallback when grep returns empty — sed still succeeds. Fixed both the production code and test to use explicit empty-check instead.
- **Key decisions:** For base64, documented both platform flags in skill file rather than adding a wrapper function, since base64 is only used in skill instructions (not scripts). For mktemp, used `${TMPDIR:-/tmp}` to respect macOS temp directory conventions.
