---
Task: t673_improve_install_already_installed_error.md
Worktree: (none — current branch)
Branch: main
Base branch: main
---

# Plan: Improve install.sh "already installed" error and add interactive overwrite prompt

## Context

When a user re-runs the documented one-liner from the website on a project that already has aitasks installed, `install.sh` dies with:

```
[ait] Error: aitasks already installed in <DIR> (found ait or .aitask-scripts/). Use --force to overwrite.
```

The error tells the user to "use --force", but does not tell curl-pipe users that they need the `bash -s --` plumbing to actually pass it through. Most website entry points (`getting-started.md:18`, `_index.md:42`, `installation/_index.md:17`, `windows-wsl.md:44`) show only the bare `curl … | bash`. Only `installation/_index.md:31` shows the `bash -s -- --force` form, deep on the page. The error also fails to mention that for an existing install the recommended path is `ait upgrade latest`, not the curl bootstrap.

Locally (`bash install.sh`) the same error happens — `confirm_install()` already gates a Y/N prompt on `[[ -t 0 ]]`, but no overwrite-confirmation prompt exists, so the local user also hits a fatal die instead of an offer to overwrite.

## Goal

1. Replace the bare `die()` at `install.sh:95` with a clearer message that names **all three** recovery paths.
2. **TTY-only convenience:** when stdin is a terminal AND `--force` was not passed AND an existing install is detected, prompt `Overwrite framework files? [y/N]`. On `y` → set `FORCE=true` and proceed. Otherwise → exit cleanly (`exit 0`, not error) with `Aborted.`.
3. Curl-pipe (non-TTY) behavior stays a clean fatal die, just with a better message.

No website changes in this task — the improved error spells out the recovery paths inline, which is more discoverable than a doc cross-reference. Website cross-linking is deferred (out of scope per the task description).

## Files to modify

- `install.sh` — only `check_existing_install()` (`install.sh:90-98`).

## Implementation

Replace `check_existing_install()` (current lines 90-98):

```bash
# --- Safety check ---
check_existing_install() {
    if [[ -f "$INSTALL_DIR/ait" || -d "$INSTALL_DIR/.aitask-scripts" ]]; then
        if $FORCE; then
            warn "Existing installation found. --force specified, overwriting framework files..."
            return
        fi

        # Existing install detected and --force was NOT passed.
        # If running in an interactive terminal, offer to overwrite.
        # Otherwise (curl|bash and similar non-TTY invocations), die with
        # a message that spells out all three recovery paths.
        if [[ -t 0 ]]; then
            warn "Existing aitasks installation found in $INSTALL_DIR (found ait or .aitask-scripts/)."
            info "  Recommended for existing installs: 'ait upgrade latest'"
            printf "  Overwrite framework files anyway? [y/N] "
            local answer
            read -r answer
            case "${answer:-N}" in
                [Yy]*)
                    FORCE=true
                    warn "Proceeding with overwrite (FORCE=true)..."
                    ;;
                *)
                    info "Aborted. To upgrade an existing install, run: ait upgrade latest"
                    exit 0
                    ;;
            esac
        else
            die "aitasks already installed in $INSTALL_DIR (found ait or .aitask-scripts/).
  To upgrade an existing install (recommended), run:
      ait upgrade latest
  To force a fresh re-install via curl-pipe:
      curl -fsSL https://raw.githubusercontent.com/$REPO/main/install.sh | bash -s -- --force
  To force a fresh re-install from a local file:
      bash install.sh --force"
        fi
    fi
}
```

### Notes on the diff

- The control flow is restructured so the success-on-FORCE path returns early. This keeps the new TTY/non-TTY branches at one indentation level and avoids deeply nested conditionals.
- The TTY prompt uses the same `printf … read -r answer; case "${answer:-N}"` shape already used in `confirm_install()` (`install.sh:116-121, 133-138`), so it stays stylistically consistent.
- On a "y" answer the function sets `FORCE=true` (script-global) and falls through to the rest of `main()`. All downstream `merge_seed`, profile install, and skill install code already keys on `$FORCE`, so flipping the flag at this point matches the same code path as if `--force` had been passed at invocation time.
- On "N"/empty/anything-else, the script exits **`0`** (clean cancel), not `1`. This matches the pattern used at `install.sh:120` and `install.sh:137` for user-initiated cancels in `confirm_install()`.
- The non-TTY `die()` message embeds `$REPO` (`install.sh:8`) so the curl URL stays in sync if the repo is ever forked/renamed.
- The multi-line `die()` message is fine — `die()` (`install.sh:18`) uses `echo -e "${RED}[ait] Error:${NC} $1" >&2` so embedded newlines render correctly with leading-whitespace continuation lines.

## Verification

Five manual scenarios (all run from a scratch directory; no automated test added — `install.sh` has no test harness):

1. **TTY, no existing install:** `mkdir -p /tmp/ait-fresh && cd /tmp/ait-fresh && bash /home/ddt/Work/aitasks/install.sh --local-tarball <tarball>`. Expected: standard install flow, no overwrite prompt (`check_existing_install` short-circuits when neither `ait` nor `.aitask-scripts/` exists).
2. **TTY, existing install, answer "y":** Re-run the same `bash install.sh --local-tarball <tarball>` in `/tmp/ait-fresh`. Expected: prompt `Overwrite framework files? [y/N]` appears, "y" → `Proceeding with overwrite (FORCE=true)...` warn, install completes (idempotent merge of seeds).
3. **TTY, existing install, answer "n" (or empty):** Re-run again, answer "n" or just press Enter. Expected: `Aborted. To upgrade an existing install, run: ait upgrade latest`, `$?` is `0`.
4. **Non-TTY (curl-pipe simulation), existing install, no --force:** `bash /home/ddt/Work/aitasks/install.sh --local-tarball <tarball> < /dev/null`. Expected: dies with the new multi-line message naming `ait upgrade latest`, `bash -s -- --force`, and `bash install.sh --force`. `$?` is `1`.
5. **Existing install, --force passed:** `bash /home/ddt/Work/aitasks/install.sh --local-tarball <tarball> --force`. Expected: `Existing installation found. --force specified, overwriting framework files...` warn (unchanged behavior), install completes. No prompt.

Where `<tarball>` is `~/Work/aitasks/aitasks-*.tar.gz` from a `make tar` build, or simply skip `--local-tarball` and let the script hit GitHub for the latest release if network is available.

(Reference: see Step 9 — Post-Implementation — for archive/merge handling. No worktree to remove.)
