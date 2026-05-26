---
Task: t826_7_ait_projects_remove_update_verbs.md
Parent Task: aitasks/t826_brainstorm_cross_repo_project_references.md
Sibling Tasks: aitasks/t826/t826_10_switcher_stale_inline_render_and_race.md, aitasks/t826/t826_3_website_docs_multi_project_workflow.md, aitasks/t826/t826_4_manual_verification_brainstorm_cross_repo_project_references.md, aitasks/t826/t826_8_ait_projects_prune_verb.md, aitasks/t826/t826_9_ait_projects_doctor_verb.md
Archived Sibling Plans: aiplans/archived/p826/p826_1_registry_resolver_projects_cmd_and_create_flag.md, aiplans/archived/p826/p826_2_tui_switcher_show_inactive_projects.md, aiplans/archived/p826/p826_5_brainstorm_stale_registry_ux.md, aiplans/archived/p826/p826_6_status_aware_read_registry_index.md
Base branch: main
---

# t826_7 — `ait projects remove` / `update` verbs

## Context

The t826_5 brainstorm (`aiplans/archived/p826/p826_5_brainstorm_stale_registry_ux.md`) decided that STALE registry entries (rows whose path no longer holds `aitasks/metadata/project_config.yaml`) must be repairable through new `ait projects` verbs. t826_6 has already landed the plumbing (STALE rows are now surfaced rather than silently dropped, and `classify_registry_entry` is a reusable helper).

This child adds the two atomic single-entry mutators that the bulk `prune` (t826_8) and interactive `doctor` (t826_9) verbs will reuse:
- `remove <name> [--force]` — drop a single entry from the registry.
- `update <name> <new_path>` — repoint an existing entry whose project moved on disk.

No bulk operations and no STALE-vs-OK awareness land here — `remove` works on any entry; `update` validates the new path holds the marker.

## Files to Modify

- `.aitask-scripts/aitask_projects.sh`
  - Add `cmd_remove` and `cmd_update` functions in a new `# --- Verb: remove ---` / `# --- Verb: update ---` section between `cmd_add` (line 306) and `# --- Verb: resolve ---` (line 308).
  - Wire `remove|rm` and `update` cases into `main()`'s dispatch (after `add`, before `resolve`).
  - Extend `show_help()`'s verb list and examples.

## Reference Patterns (existing code to reuse)

- `cmd_add` (lines 268-306) — canonical rebuild-via-`awk -F'|'` pattern, paired with `build_registry_yaml` + `atomic_write`. Both new verbs follow this exact shape.
- `list_registry_entries` (lines 124-174) — TSV read helper (pipe-separated). Used as the input to the awk rewrite.
- `atomic_write` (lines 108-117) — `mktemp + mv` writer; always used for registry mutation.
- `read_project_field` (lines 70-94) — used to read `project_config.yaml`; useful if we ever need to refresh `git_remote` on `update` (out of scope per task — keep `git_remote` unchanged).
- `die`/`info` from `lib/terminal_compat.sh` — already sourced.

## Implementation Plan

### 1. `cmd_remove <name> [--force]`

Insert between `cmd_add` and `# --- Verb: resolve ---`:

```bash
# --- Verb: remove -------------------------------------------------------

cmd_remove() {
    local name=""
    local force=0
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --force) force=1; shift ;;
            -h|--help) echo "Usage: ait projects remove <name> [--force]"; return 0 ;;
            -*) die "Unknown flag: $1" ;;
            *)
                [[ -z "$name" ]] || die "Usage: ait projects remove <name> [--force]"
                name="$1"; shift ;;
        esac
    done
    [[ -n "$name" ]] || die "Usage: ait projects remove <name> [--force]"

    local tsv
    tsv=$(list_registry_entries || true)
    if [[ -z "$tsv" ]]; then
        die "No registered projects."
    fi
    # Confirm the entry exists.
    if ! awk -F'|' -v want="$name" '$1 == want { found=1 } END { exit !found }' <<< "$tsv"; then
        die "Project '$name' is not registered."
    fi

    if [[ "$force" -ne 1 ]]; then
        printf "Remove '%s' from registry? [y/N]: " "$name" >&2
        local ans
        read -r ans
        case "$ans" in
            y|Y) ;;
            *) info "Aborted."; return 0 ;;
        esac
    fi

    local tsv_out
    tsv_out=$(awk -F'|' -v skip="$name" '$1 != skip { print }' <<< "$tsv")

    local body
    body=$(printf '%s\n' "$tsv_out" | build_registry_yaml)
    atomic_write "$REGISTRY_FILE" "$body"

    info "Removed $name"
}
```

Note: `read -r ans` reads from stdin, matching the framework convention for interactive confirmation (no other prompt patterns are in use in `aitask_projects.sh`; behavior under non-TTY stdin is the same as `cmd_add`'s lack of confirmation — the caller should use `--force` for non-interactive scripts).

### 2. `cmd_update <name> <new_path>`

Insert immediately after `cmd_remove`:

```bash
# --- Verb: update -------------------------------------------------------

cmd_update() {
    local name="${1:-}"
    local new_path="${2:-}"
    [[ -n "$name" && -n "$new_path" ]] || die "Usage: ait projects update <name> <new_path>"

    if [[ ! -d "$new_path" ]]; then
        die "Path does not exist: $new_path"
    fi
    if [[ ! -f "$new_path/aitasks/metadata/project_config.yaml" ]]; then
        die "Not an aitasks project (no aitasks/metadata/project_config.yaml under $new_path)"
    fi
    new_path=$(cd "$new_path" && pwd)

    local tsv
    tsv=$(list_registry_entries || true)
    if [[ -z "$tsv" ]]; then
        die "No registered projects."
    fi
    if ! awk -F'|' -v want="$name" '$1 == want { found=1 } END { exit !found }' <<< "$tsv"; then
        die "Project '$name' is not registered."
    fi

    local today
    today=$(date -u +"%Y-%m-%d")

    local tsv_out
    tsv_out=$(awk -F'|' \
        -v name="$name" \
        -v new_path="$new_path" \
        -v today="$today" \
        '$1 == name { print $1 "|" new_path "|" $3 "|" today; next } { print }' \
        <<< "$tsv")

    local body
    body=$(printf '%s\n' "$tsv_out" | build_registry_yaml)
    atomic_write "$REGISTRY_FILE" "$body"

    info "Updated $name → $new_path"
}
```

`git_remote` (field `$3`) is preserved verbatim — the brainstorm explicitly decided not to refresh it on `update`. The user can re-run `ait projects add` to refresh `git_remote` from `project_config.yaml`.

### 3. Dispatch + help

In `main()` (after `add` case, before `resolve`):

```bash
        remove|rm)
            shift
            cmd_remove "$@"
            ;;
        update)
            shift
            cmd_update "$@"
            ;;
```

In `show_help()`, extend the verb list:

```
  remove <name> [--force]    Drop the named entry from the registry.
                             Prompts for confirmation unless --force.
  update <name> <new_path>   Repoint <name> to a new on-disk root
                             (refreshes last_opened, keeps git_remote).
```

…and add two examples to the Examples block:

```
  ait projects remove old_project --force
  ait projects update aitasks_mobile /new/path/to/aitasks_mobile
```

## Verification

### New: `tests/test_aitask_projects_remove.sh`

Modeled on `tests/test_projects_cmd.sh` (same scaffolding: `assert_eq` / `assert_contains`, `AITASKS_PROJECTS_INDEX` overridden to a temp file, two fake projects with `aitasks/metadata/project_config.yaml`).

- Setup: register `alpha` and `beta` via `ait projects add`.
- `remove alpha --force` → registry contains `beta` only; `name: alpha` is gone.
- `remove missing` (no entry) → exit 1, message "is not registered", registry unchanged.
- Interactive `n` answer (`printf 'n\n' | "$PROJECTS_SH" remove beta`) → registry unchanged, exit 0, "Aborted" emitted.
- Interactive `y` answer (`printf 'y\n' | "$PROJECTS_SH" remove beta`) → registry empty (or "alpha only", depending on order).

### New: `tests/test_aitask_projects_update.sh`

- Setup: register `alpha` at one path, then build a second fake project root containing the marker file.
- Happy path: `update alpha <new_path>` → registry row for `alpha` has the new path, `last_opened` matches today's UTC date, `git_remote` is preserved.
- Missing-marker path (a bare dir without `aitasks/metadata/project_config.yaml`) → exit 1 with the "Not an aitasks project" message, registry unchanged.
- Missing entry (`update ghost <new_path>`) → exit 1 with "is not registered", registry unchanged.

### Existing tests

- `bash tests/test_projects_cmd.sh` — must still pass unchanged (pure-additive verbs).
- `shellcheck .aitask-scripts/aitask_projects.sh` — clean.

## Out of Scope

- Bulk `prune` (drop every STALE entry) — child C (t826_8).
- Interactive `doctor` flow — child D (t826_9).
- STALE-vs-OK awareness — `remove` works on any entry; `update` validates the new path itself.
- Refreshing `git_remote` on `update` — preserved verbatim; users re-run `ait projects add` if they need a remote refresh.
- Mobile/website docs — child t826_3 will pick up the new verbs.

## Step 9 reference

Follow shared workflow Step 9 after Step 8 approval. Profile `fast` works on the current branch; no worktree to clean up. Archival closes t826_7 and leaves t826_8 / t826_9 / t826_10 / t826_3 / t826_4 pickable as siblings.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned.
  - `aitask_projects.sh` gained two new verb handlers: `cmd_remove` (with `--force` flag, interactive confirmation when omitted) and `cmd_update` (rebuild-via-`awk -F'|'` row-replace that refreshes `last_opened` and preserves `git_remote`).
  - `main()` dispatcher learned `remove|rm` and `update` cases (placed between `add` and `resolve`, matching the verb order in `show_help`).
  - `show_help()` and the file-top verb summary list were both extended with the two new verbs and two new examples.
  - Test scaffolding: `tests/test_aitask_projects_remove.sh` (11 assertions) and `tests/test_aitask_projects_update.sh` (14 assertions), both modeled on `tests/test_projects_cmd.sh` for a consistent feel.
- **Deviations from plan:** None. Minor cosmetic adjustment: the `cmd_remove` flag-parsing loop follows a slightly more verbose `while/case` layout than the inline plan example to keep multi-token arg handling readable.
- **Issues encountered:** None.
- **Key decisions:**
  - `read -r ans || true` (with `|| true`) makes the interactive prompt safe under `set -euo pipefail` when stdin is closed (CI / piped contexts). It defaults to the `*` branch ("Aborted").
  - `cmd_remove` validates entry existence **before** the `--force` / interactive split, so a typo on a non-existent name fails fast without prompting.
  - `cmd_update` preserves `git_remote` verbatim (per the brainstorm). Users who need to refresh `git_remote` after a move can re-run `ait projects add` — which is idempotent and rewrites the row from the project's own `project_config.yaml`.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - **t826_8 (`prune`)** should call `list_registry_entries`, filter STALE via `classify_registry_entry "$name" "$path"` (no third arg), then for each STALE name either invoke `cmd_remove "$name" --force` directly (cheap) or rebuild the registry once with a single awk `$1 != skip1 && $1 != skip2 && ...` pass (one atomic write instead of N). The single-awk approach is preferable for atomicity.
  - **t826_9 (`doctor`)** is the interactive wrapper: list STALE rows, prompt per-row with options that map to `cmd_remove`, `cmd_update <new_path>`, or skip. The two new verbs are the building blocks; doctor only needs the orchestration layer.
  - The `awk -F'|'` row-replace pattern in `cmd_update` is also the right template for any future "edit one field of one row" verb (e.g., renaming a registry entry).
- **Build verification:** N/A (`verify_build` is unset in this project).
