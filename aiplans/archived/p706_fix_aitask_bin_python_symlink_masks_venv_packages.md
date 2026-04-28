---
Task: t706_fix_aitask_bin_python_symlink_masks_venv_packages.md
Worktree: (none — current branch per fast profile)
Branch: main
Base branch: main
---

# Plan: Fix `~/.aitask/bin/python3` venv masking + update-check cache corruption (t706)

## Context

`ait board` (and any other TUI calling `require_ait_python`) currently fails on a fresh setup with:

```
Error: Missing Python packages: textual pyyaml linkify-it-py. Run 'ait setup' to install all dependencies.
```

Two independent regressions, both confirmed by direct on-disk inspection:

1. **Bin symlink masks venv site-packages** — `~/.aitask/bin/python3` is a `ln -sf` to `~/.aitask/venv/bin/python` which itself symlinks to `python3.13 → /opt/homebrew/opt/python@3.13/bin/python3.13`. When Python launches via this two-hop chain, `sys.executable` canonicalizes to the homebrew path, `pyvenv.cfg` is not found adjacent to it, and Python uses the **system** site-packages — which lacks textual/pyyaml/linkify-it-py. Verified live: `~/.aitask/bin/python3 -c "import sys; print(sys.executable)"` → `/opt/homebrew/opt/python@3.13/bin/python3.13`. Introduced by t695_3 (`709380a5`) at `aitask_setup.sh:526-527`. Re-running `ait setup` recreates the broken symlinks.

2. **Update-check cache corruption** — `ait:135-138` parses GitHub's releases JSON with a fragile `grep | sed`. When the substitution does not match (e.g., API error, rate limit), the entire JSON line passes through and is written to `~/.aitask/update_check`. On the next run, `read -r cached_time cached_version < cache_file` populates `cached_version` with the literal JSON token (e.g., `"tag_name":`), and `version_gt` then runs `((n1 > n2))` on non-numeric arrays → arithmetic-syntax errors at every `ait <cmd>` invocation. Verified live: `~/.aitask/update_check` currently contains `1777387840   "tag_name": "v0.19.1",`.

Both surfaced now because t695_3 introduced the bin symlink layer; the update-check noise was a latent bug exposed during this investigation.

Goal: replace the symlinks with a small wrapper script that invokes `venv/bin/python` directly (preserving `pyvenv.cfg` discovery), tighten input validation in the update-check parser, and self-recover from any corrupt cache. Both implemented in a single task — total scope is small (~50 lines code + tests) and the two fixes are tightly co-discovered.

## Files to modify

| File | What changes |
|------|--------------|
| `.aitask-scripts/aitask_setup.sh` | Replace `ln -sf` (lines 526–527) with a `install_python_wrappers` helper that writes wrapper scripts; adjust `find_modern_python` candidate order (line 382–384) to prefer venv path |
| `.aitask-scripts/lib/python_resolve.sh` | Reorder `resolve_python` candidates (lines 39–42) to prefer `~/.aitask/venv/bin/python` over `~/.aitask/bin/python3` (defense-in-depth) |
| `ait` | In `check_for_updates` (lines 100–150): validate `cached_version` after read, validate `latest_version` before write, unlink corrupt cache files |
| `tests/test_setup_python_install.sh` | Replace symlink-target asserts (lines 75–84) with `sys.executable` and import asserts |
| `tests/test_update_check.sh` *(new)* | Black-box integration test: corrupt cache → `ait ls` runs cleanly, cache auto-recovers |

## Implementation

### Step 1 — Replace bin symlinks with wrapper scripts (aitask_setup.sh)

In `setup_python_venv`, replace lines 525–528:

```bash
mkdir -p "$HOME/.aitask/bin"
ln -sf "$VENV_DIR/bin/python" "$HOME/.aitask/bin/python3"
ln -sf "$VENV_DIR/bin/python" "$HOME/.aitask/bin/python"
info "Created framework Python symlinks at ~/.aitask/bin/{python,python3}."
```

with a helper call:

```bash
install_python_wrappers
```

Add the helper near `setup_python_venv`:

```bash
# Write small wrapper scripts at ~/.aitask/bin/{python,python3} that exec the
# venv interpreter directly (NOT a symlink chain). Using a wrapper keeps
# sys.executable adjacent to pyvenv.cfg so the venv site-packages are picked
# up. Migrates over any prior symlinks installed by t695_3.
install_python_wrappers() {
    local bin_dir="$HOME/.aitask/bin"
    mkdir -p "$bin_dir"
    local name path
    for name in python python3; do
        path="$bin_dir/$name"
        # Remove pre-existing symlink or older wrapper
        [[ -e "$path" || -L "$path" ]] && rm -f "$path"
        cat > "$path" <<'WRAPPER'
#!/usr/bin/env bash
exec "$HOME/.aitask/venv/bin/python" "$@"
WRAPPER
        chmod +x "$path"
    done
    info "Installed framework Python wrappers at $bin_dir/{python,python3}."
}
```

`rm -f` handles the t695_3 migration scenario: if the file is a symlink, `[[ -L ]]` matches and we remove it before writing. If it's already the wrapper, we overwrite (idempotent).

### Step 2 — Defense-in-depth: reorder Python resolution candidates

Even with the wrapper fix, the explicit `resolve_python` callers should prefer the canonical venv path so a future regression on `bin/python3` cannot silently mask the venv again. PATH-based resolution (via `aitask_path.sh` prepending `~/.aitask/bin`) still hits the wrapper for subprocesses spelled as `python3`, so this only affects explicit lookups.

In `.aitask-scripts/lib/python_resolve.sh:39-42`:

```bash
# Before:
for cand in \
    "${AIT_PYTHON:-}" \
    "$HOME/.aitask/bin/python3" \
    "$HOME/.aitask/venv/bin/python"; do

# After:
for cand in \
    "${AIT_PYTHON:-}" \
    "$HOME/.aitask/venv/bin/python" \
    "$HOME/.aitask/bin/python3"; do
```

Update the header comment block (lines 14–17) to match the new order.

In `.aitask-scripts/aitask_setup.sh:382-384` (`find_modern_python`'s `candidates` array), apply the same reorder:

```bash
local cand resolved candidates=(
    "$HOME/.aitask/venv/bin/python"
    "$HOME/.aitask/bin/python3"
    "$HOME/.aitask/python/$AIT_VENV_PYTHON_PREFERRED/bin/python3"
    python3.13 python3.12 python3.11 python3
)
```

### Step 3 — Validate update-check cache (`ait`)

In `check_for_updates` (lines 100–150), introduce a regex constant and apply at both ends:

```bash
local version_re='^[0-9]+(\.[0-9]+)*$'
```

After `read -r cached_time cached_version < "$cache_file"` (line 118), add validation:

```bash
if [[ -n "$cached_version" && ! "$cached_version" =~ $version_re ]]; then
    # Corrupt cache (e.g., from a prior buggy parse) — discard.
    rm -f "$cache_file"
    cached_time=0
    cached_version=""
fi
```

Also harden `cached_time` against non-numeric corruption — `(( now - cached_time ))` would error if it picked up a token. Add right after the read:

```bash
[[ "$cached_time" =~ ^[0-9]+$ ]] || cached_time=0
```

After the curl/sed pipeline (line 138), validate before writing:

```bash
if [[ -n "$latest_version" && "$latest_version" =~ $version_re ]]; then
    mkdir -p "$(dirname "$cache_file")"
    echo "$now $latest_version" > "$cache_file"
else
    # Parse miss or invalid version — keep timestamp fresh, reuse last good version
    mkdir -p "$(dirname "$cache_file")"
    echo "$now ${cached_version:-$local_version}" > "$cache_file"
fi
```

The existing `else` branch already handles network failure by falling back to `cached_version:-local_version`; we extend the validation gate so a successful curl that returns an unparseable body is treated identically.

### Step 4 — Update integration test (tests/test_setup_python_install.sh)

Replace lines 75–84 (the symlink-target check) with:

```bash
echo ""
echo "--- Verifying ~/.aitask/bin/python3 wrappers (t706) ---"
[[ -f "$FAKE_HOME/.aitask/bin/python3" ]] || { echo "FAIL: ~/.aitask/bin/python3 missing"; exit 1; }
[[ -f "$FAKE_HOME/.aitask/bin/python"  ]] || { echo "FAIL: ~/.aitask/bin/python missing"; exit 1; }
[[ -L "$FAKE_HOME/.aitask/bin/python3" ]] && { echo "FAIL: ~/.aitask/bin/python3 is still a symlink (expected wrapper script)"; exit 1; }
[[ -x "$FAKE_HOME/.aitask/bin/python3" ]] || { echo "FAIL: ~/.aitask/bin/python3 not executable"; exit 1; }

# Wrapper must execute inside the venv (sys.executable points at venv path,
# NOT the system python it links into).
exe="$("$FAKE_HOME/.aitask/bin/python3" -c 'import sys; print(sys.executable)')"
[[ "$exe" == "$FAKE_HOME/.aitask/venv/bin/python" ]] \
    || { echo "FAIL: bin/python3 sys.executable is $exe (expected $FAKE_HOME/.aitask/venv/bin/python)"; exit 1; }

# Critical packages must import via bin/python3 — was the original failure mode.
"$FAKE_HOME/.aitask/bin/python3" -c "import textual, yaml, linkify_it" \
    || { echo "FAIL: textual/yaml/linkify_it not importable via bin/python3"; exit 1; }
echo "PASS: bin wrappers route through venv (sys.executable + import check)"
```

The symlink-existence check is replaced by a behavioral check (execution path + imports). The existing scoped-PATH check (lines 86–112) remains unchanged.

### Step 5 — Add update-check regression test (tests/test_update_check.sh)

New file. Black-box test that runs the real `ait` dispatcher with controlled `HOME` and a deliberately corrupt cache:

```bash
#!/usr/bin/env bash
# test_update_check.sh - regression for t706 update-check cache validation
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/test_update_check.XXXXXX")"
trap 'rm -rf "$SCRATCH"' EXIT

PASS=0; FAIL=0; TOTAL=0
assert_eq() { ... ; }
assert_no_match() { ... ; }   # asserts pattern NOT present in haystack

mkdir -p "$SCRATCH/.aitask"

# Case 1: corrupt cached_version (the live-observed failure)
printf '%s\n' '1777387840   "tag_name": "v0.19.1",' > "$SCRATCH/.aitask/update_check"
err="$(HOME="$SCRATCH" "$PROJECT_DIR/ait" ls -h 2>&1 1>/dev/null || true)"
assert_no_match "no arithmetic-syntax noise on corrupt cached_version" \
    "syntax error" "$err"
assert_no_match "no arithmetic noise on corrupt cached_version" \
    "value too great" "$err"
# Cache must auto-recover (file removed or rewritten with valid format)
if [[ -f "$SCRATCH/.aitask/update_check" ]]; then
    line="$(head -1 "$SCRATCH/.aitask/update_check")"
    [[ "$(echo "$line" | awk '{print $2}')" =~ ^[0-9]+(\.[0-9]+)*$ ]] \
        || { echo "FAIL: corrupt cache not recovered: $line"; FAIL=$((FAIL+1)); }
fi

# Case 2: corrupt cached_time (non-numeric)
printf '%s\n' 'notatime 0.18.1' > "$SCRATCH/.aitask/update_check"
err="$(HOME="$SCRATCH" "$PROJECT_DIR/ait" ls -h 2>&1 1>/dev/null || true)"
assert_no_match "no arithmetic noise on corrupt cached_time" \
    "syntax error" "$err"

# Case 3: empty cache file
: > "$SCRATCH/.aitask/update_check"
err="$(HOME="$SCRATCH" "$PROJECT_DIR/ait" ls -h 2>&1 1>/dev/null || true)"
assert_no_match "no noise on empty cache" "syntax error" "$err"

echo ""
echo "Tests: $TOTAL  Pass: $PASS  Fail: $FAIL"
(( FAIL == 0 ))
```

`ait ls -h` is a fast, side-effect-free invocation that DOES trigger `check_for_updates` (the case statement at line 153–156 only excludes meta-commands; `ls` is not excluded). The background curl child is harmless — we only care about the foreground stderr.

### Step 6 — One-time user cleanup

The fix in Step 3 self-recovers any corrupt cache on the next `ait <cmd>` run (validation gate removes the file). No separate migration script needed for end users — running any `ait` command after upgrade fixes both the cache and the bin wrappers (the latter via `ait setup` re-run, which we surface in the changelog).

## Verification

Run locally before commit:

```bash
# Lint
shellcheck .aitask-scripts/aitask_setup.sh
shellcheck .aitask-scripts/lib/python_resolve.sh
shellcheck ait

# Fast unit tests (no network)
bash tests/test_python_resolve.sh
bash tests/test_update_check.sh

# Live verification on the dev machine that originally reproduced the bug
./ait setup                                         # rewrites bin wrappers
~/.aitask/bin/python3 -c "import sys; print(sys.executable)"   # → ~/.aitask/venv/bin/python
~/.aitask/bin/python3 -c "import textual, yaml, linkify_it"    # no error
ait ls 2>&1 | grep -E 'syntax error|value too great' && echo BAD || echo OK
ait board                                            # launches TUI cleanly

# Heavy integration test (downloads brew/uv — minutes-scale, opt-in)
AIT_RUN_INTEGRATION_TESTS=1 bash tests/test_setup_python_install.sh
```

## Acceptance (from task description)

- After `ait setup`, `~/.aitask/bin/python3 --version` succeeds and `~/.aitask/bin/python3 -c "import textual, yaml, linkify_it"` succeeds. ✓ Step 1 + Step 4 test
- `ait board` launches the TUI cleanly with no missing-package error and no arithmetic-syntax noise. ✓ Step 1 + Step 3 (live verification)
- Cache file at `~/.aitask/update_check` is robust against corrupt entries (auto-recovers on next run). ✓ Step 3 + Step 5 test
- New tests in `tests/test_setup_python_install.sh` cover both regressions. ✓ Step 4 + Step 5

## Step 9 — Post-Implementation

After approval and implementation: run the verification checklist above, then follow the standard archival flow (commit code with `bug: Fix bin/python3 venv masking and update-check cache corruption (t706)`, update plan, archive, push). No worktree to clean up — fast profile keeps us on the current branch.

## Final Implementation Notes

- **Actual work done:** Implemented all five planned steps without deviation.
  - `aitask_setup.sh`: replaced the two `ln -sf` calls (lines 526–527) with a new `install_python_wrappers()` helper that writes regular wrapper scripts (`#!/usr/bin/env bash; exec "$HOME/.aitask/venv/bin/python" "$@"`). The helper removes any prior symlink/file via `[[ -e || -L ]] && rm -f` before writing, making it idempotent and migrating existing t695_3 installs. Also reordered `find_modern_python`'s `candidates` array to put `venv/bin/python` ahead of `bin/python3`.
  - `lib/python_resolve.sh`: reordered the `resolve_python` candidate loop and updated the header comment to document the new order plus the rationale (defense-in-depth: PATH-based subprocess resolution still hits the wrapper, but explicit lookups now prefer the canonical interpreter).
  - `ait`: added a `version_re='^[0-9]+(\.[0-9]+)*$'` regex constant to `check_for_updates`; validate `cached_time` (numeric only) and `cached_version` (matches regex) after the `read`, unlinking the cache and resetting both fields if either is corrupt; gate the cache-write branch behind the same regex on `latest_version`.
  - `tests/test_setup_python_install.sh`: replaced the symlink-existence + `readlink` target check with a behavioral assertion: `bin/python3 -c "import sys; print(sys.executable)"` must equal `$FAKE_HOME/.aitask/venv/bin/python`, and `import textual, yaml, linkify_it` must succeed via that wrapper. Also explicitly fail if the file is still a symlink.
  - `tests/test_update_check.sh` (new): 5 test cases exercising corrupt cached_version (the live-observed failure), corrupt cached_time, empty cache, missing cache, and a valid cache that must be preserved. All 7 sub-assertions pass.
- **Deviations from plan:** None.
- **Issues encountered:** `bash tests/test_python_resolve.sh` fails on this Apple Silicon Mac with `/usr/bin/bash: No such file or directory` — the test hard-codes `/usr/bin/bash` (line 97 etc.) which doesn't exist on Apple Silicon (bash lives at `/opt/homebrew/bin/bash`). This is a pre-existing test-infra bug unrelated to t706, kept out of scope. May warrant a follow-up task to switch the test to `command -v bash` or `${BASH:-bash}`.
- **Key decisions:**
  - Single-task implementation (not split into two child tasks as the task description suggested) — total scope is small (~75 lines net) and the two fixes were tightly co-discovered by the same investigation. Splitting would add archive ceremony without engineering benefit.
  - Reordered both `python_resolve.sh` AND `aitask_setup.sh:find_modern_python` candidate lists, keeping the two in sync. Failing to reorder `find_modern_python` would mean re-running `setup_python_venv` on a fresh `~/.aitask/` could pick up a stale `bin/python3` from a partial install before the venv is recreated, defeating the defense-in-depth.
  - Hardened `cached_time` (not just `cached_version`) against non-numeric corruption — `(( now - cached_time ))` would also throw under `set -euo pipefail` if cached_time picked up a JSON token in a future similar bug. Cheap insurance.
  - Cache validation removes the file (`rm -f`) instead of just zeroing the in-memory fields, so the next run sees a clean fresh-fetch state and doesn't carry forward any latent badness if the read path changes again.
- **Live verification on originally-broken machine:**
  - `~/.aitask/bin/python3 -c "import sys; print(sys.executable)"` → `/Users/daelyasy/.aitask/venv/bin/python` ✓
  - `~/.aitask/bin/python3 -c "import textual, yaml, linkify_it"` → no error ✓
  - `cat ~/.aitask/update_check` after one `ait ls` invocation → `1777392205 0.19.1` (was `1777387840   "tag_name": "v0.19.1",`) ✓
  - `ait board` → TUI launches cleanly ✓
- **Build verification:** `shellcheck` against changed files reports only pre-existing findings (SC2015/SC2016/SC2034/SC2129/SC1091 in unrelated lines); no new findings introduced.
