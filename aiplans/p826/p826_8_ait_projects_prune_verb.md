---
Task: t826_8_ait_projects_prune_verb.md
Parent Task: aitasks/t826_brainstorm_cross_repo_project_references.md
Sibling Tasks: aitasks/t826/t826_10_switcher_stale_inline_render_and_race.md, aitasks/t826/t826_3_website_docs_multi_project_workflow.md, aitasks/t826/t826_4_manual_verification_brainstorm_cross_repo_project_references.md, aitasks/t826/t826_9_ait_projects_doctor_verb.md
Archived Sibling Plans: aiplans/archived/p826/p826_1_registry_resolver_projects_cmd_and_create_flag.md, aiplans/archived/p826/p826_2_tui_switcher_show_inactive_projects.md, aiplans/archived/p826/p826_5_brainstorm_stale_registry_ux.md, aiplans/archived/p826/p826_6_status_aware_read_registry_index.md, aiplans/archived/p826/p826_7_ait_projects_remove_update_verbs.md
Base branch: main
---

# t826_8 — `ait projects prune` verb

## Context

The t826_5 brainstorm
(`aiplans/archived/p826/p826_5_brainstorm_stale_registry_ux.md`) decided
that STALE registry entries — rows whose `path` no longer holds the
`aitasks/metadata/project_config.yaml` marker — must be repairable
through new `ait projects` verbs. The plumbing is in place from earlier
children:

- **t826_6** added `classify_registry_entry <name> <path> [<live>]` (OK
  / STALE / LIVE) and stopped silently dropping STALE rows in the Python
  reader.
- **t826_7** added `cmd_remove <name> [--force]` and `cmd_update <name>
  <new_path>` as the single-entry mutators.

This child adds the **bulk** verb that composes those two helpers:
`ait projects prune [--dry-run] [--yes]` — find every STALE row and
either dry-list, prompt per row, or force-remove them. Out of scope:
the interactive triage `doctor` verb (t826_9).

## Files to Modify

- `.aitask-scripts/aitask_projects.sh` — add a new `cmd_prune` handler
  between `cmd_update` and `# --- Verb: resolve ---`, wire a
  `prune` case into `main()`'s dispatch, and extend both the file-top
  verb summary comment block (lines 10–24) and the `show_help()` body
  (lines 36–76) with the new verb and an example.

## Reference Patterns (existing code to reuse)

All in `.aitask-scripts/aitask_projects.sh`:

- `classify_registry_entry` (lines 214–228) — call with **two args**
  (no live-names) to get `OK` / `STALE` only.
- `list_registry_entries` (lines 136–186) — emits one
  `name|path|git_remote|last_opened` line per registry row.
- `cmd_remove` (lines 322–373) — invoked as `cmd_remove "$name" --force`
  per STALE entry. Each call independently rewrites the registry via
  `build_registry_yaml` + `atomic_write`, which is fine for the
  expected registry size (a handful of entries per user).
- `cmd_add` flag-parsing loop is the closest stylistic match; mirror
  its `while/case` shape for `cmd_prune`'s arg parser. Same `die`
  on unknown flags.
- `info` / `die` from `lib/terminal_compat.sh` — already sourced.

## Implementation Plan

### 1. `cmd_prune [--dry-run] [--yes]`

Insert immediately after `cmd_update` (around line 416, before the
`# --- Verb: resolve ---` banner):

```bash
# --- Verb: prune --------------------------------------------------------

cmd_prune() {
    local dry_run=0
    local assume_yes=0
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dry-run) dry_run=1; shift ;;
            --yes|-y)  assume_yes=1; shift ;;
            -h|--help)
                echo "Usage: ait projects prune [--dry-run] [--yes]"
                return 0
                ;;
            *) die "Unknown argument: $1" ;;
        esac
    done

    local tsv
    tsv=$(list_registry_entries || true)

    # Collect STALE entries into parallel arrays. classify_registry_entry
    # is called WITHOUT the live-names arg so the result is OK or STALE.
    local stale_names=()
    local stale_paths=()
    if [[ -n "$tsv" ]]; then
        while IFS='|' read -r name path _remote _last; do
            [[ -z "$name" ]] && continue
            local status
            status=$(classify_registry_entry "$name" "$path")
            if [[ "$status" == "STALE" ]]; then
                stale_names+=("$name")
                stale_paths+=("$path")
            fi
        done <<< "$tsv"
    fi

    local total=${#stale_names[@]}
    echo "Found $total stale entries."
    if [[ "$total" -eq 0 ]]; then
        return 0
    fi

    if [[ "$dry_run" -eq 1 ]]; then
        local i
        for ((i = 0; i < total; i++)); do
            printf '  %s → %s\n' "${stale_names[i]}" "${stale_paths[i]}"
        done
        return 0
    fi

    local pruned=0
    local i
    for ((i = 0; i < total; i++)); do
        local name="${stale_names[i]}"
        local path="${stale_paths[i]}"
        if [[ "$assume_yes" -ne 1 ]]; then
            printf "Prune '%s' (path: %s)? [y/N]: " "$name" "$path" >&2
            local ans=""
            read -r ans || true
            case "$ans" in
                y|Y) ;;
                *) continue ;;
            esac
        fi
        cmd_remove "$name" --force
        pruned=$((pruned + 1))
    done

    echo "Pruned $pruned of $total stale entries."
}
```

**Design notes:**

- `Found <N> stale entries.` is printed unconditionally (including when
  `N=0`) so callers and the test suite can match a single canonical
  header line. This matches the brainstorm's "summary header" decision
  in t826_5.
- `--dry-run` and `--yes` are independent flags; if both are passed,
  `--dry-run` short-circuits before any prompt or mutation (dry-run
  wins, matching standard CLI convention).
- Per-entry `cmd_remove --force` is preferred over a single bulk awk
  rewrite. The t826_7 final notes mention the bulk approach as a
  possible optimization but the registry is expected to hold only a
  handful of entries, so the readability of "prune composes remove"
  outweighs the atomicity gain.
- `read -r ans || true` keeps the prompt safe under `set -euo pipefail`
  when stdin is closed (matches the pattern established in
  `cmd_remove`, line 355).

### 2. Dispatch + help

In `main()` (between `update` and `resolve`):

```bash
        prune)
            shift
            cmd_prune "$@"
            ;;
```

In `show_help()` (after the `update <name> <new_path>` block), insert:

```
  prune [--dry-run] [--yes]  Drop every STALE registry entry (path no
                             longer holds the aitasks marker). Prompts
                             per entry unless --yes; --dry-run lists
                             matches without modifying the registry.
```

…and add one example to the Examples block:

```
  ait projects prune --dry-run
  ait projects prune --yes
```

Also extend the file-top verb summary comment block (lines 10–24) with
a matching `prune [--dry-run] [--yes]` line so the in-file documentation
stays in sync with `show_help`.

## Verification

### New: `tests/test_aitask_projects_prune.sh`

Modeled on `tests/test_aitask_projects_remove.sh` (same `assert_eq` /
`assert_contains` / `assert_not_contains` helpers; same TMPROOT
scaffolding with `AITASKS_PROJECTS_INDEX` overridden).

Setup:
- Three entries seeded by calling `ait projects add` against:
  - `ok` — a real dir with `aitasks/metadata/project_config.yaml`.
  - `stale_a`, `stale_b` — seeded against real dirs with markers, then
    have the marker files (or directories) removed *after* seeding so
    the registry retains the rows but `classify_registry_entry`
    classifies them STALE. Simplest implementation: after each `add`,
    `rm -rf "$STALE_ROOT"`.

Test cases:

1. **No stale**: registry containing only `ok` →
   `ait projects prune --yes` prints `Found 0 stale entries.`, exits 0,
   registry body unchanged (byte-for-byte compare via
   `assert_eq before_body after_body`).

2. **`--dry-run`**: with two stale rows present → output contains both
   `Found 2 stale entries.` and the two `name → path` lines; registry
   body unchanged.

3. **`--yes`**: with two stale rows + one OK row → output contains
   `Found 2 stale entries.` and `Pruned 2 of 2 stale entries.`;
   registry retains `ok` and no longer contains `stale_a` or
   `stale_b`.

4. **Interactive `y\nn\n`**: pipe two answers (`y` then `n`) into
   `ait projects prune` (no flags) with two stale rows → exactly one
   of the two stale entries is removed; the other remains; OK
   preserved; output contains `Pruned 1 of 2 stale entries.`

5. **Unknown flag**: `ait projects prune --bogus` → exits non-zero,
   stderr/stdout mentions `Unknown argument`.

### Existing tests must still pass

- `bash tests/test_projects_cmd.sh`
- `bash tests/test_aitask_projects_remove.sh`
- `bash tests/test_aitask_projects_update.sh`

### Lint

- `shellcheck .aitask-scripts/aitask_projects.sh` — clean. (Watch for
  SC2155 on the `local status=$(...)` line; the example above uses a
  separate `local status` + assignment to avoid masking return codes,
  matching the pattern used elsewhere in this file.)

## Out of Scope

- **Interactive `doctor` verb** (prune/update/clone per entry) —
  child D, t826_9.
- **Single bulk `awk` rewrite** instead of per-entry `cmd_remove`
  calls — possible micro-optimization, not warranted at the current
  registry scale.
- **Website / mobile docs** — covered by t826_3.
- **TUI switcher rendering of STALE entries** — t826_10.

## Step 9 reference

Follow shared workflow Step 9 after Step 8 approval. Profile `fast`
works on the current branch; no worktree to clean up. Archival closes
t826_8 and leaves t826_9 / t826_10 / t826_3 / t826_4 pickable.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned.
  - `.aitask-scripts/aitask_projects.sh` gained `cmd_prune` (with
    `--dry-run`, `--yes`/`-y`, `-h`/`--help`, and an explicit
    "Unknown argument" `die` for everything else). It composes
    `list_registry_entries` + `classify_registry_entry "$name"
    "$path"` (two-arg form, OK/STALE only) into parallel
    `stale_names` / `stale_paths` arrays, then either dry-lists,
    prompts per entry, or force-removes via `cmd_remove "$name"
    --force`.
  - `main()` learned a `prune` case (placed between `update` and
    `resolve` to match the verb order in `show_help`).
  - `show_help()`, the file-top verb summary comment, and the
    Examples block were all extended with the new verb and two
    example invocations (`--dry-run`, `--yes`).
  - `tests/test_aitask_projects_prune.sh` (18 assertions) covers
    no-stale, `--dry-run`, `--yes`, interactive `y\nn\n`, and
    unknown-flag rejection. Modeled on
    `tests/test_aitask_projects_remove.sh` for a consistent feel.
- **Deviations from plan:** None.
- **Issues encountered:** None.
- **Key decisions:**
  - The "Found N stale entries." header is always printed —
    including when N=0 — so the test suite and any future
    automation can match a single canonical line. The "Pruned K
    of N stale entries." summary fires on every mutating path
    (interactive or `--yes`); `--dry-run` skips it (nothing to
    summarize).
  - Per-entry `cmd_remove --force` chosen over a single bulk `awk`
    rewrite. The t826_7 final notes flagged the bulk-awk approach
    as an atomicity win; at the expected registry size (handful
    of entries per user) the readability of "prune composes
    remove" is the more valuable property. Each `cmd_remove` call
    still goes through `build_registry_yaml` + `atomic_write`, so
    each step is independently atomic on disk.
  - `read -r ans || true` mirrors `cmd_remove` (line 355) and
    keeps the prompt safe under `set -euo pipefail` when stdin is
    closed.
  - Test scaffolding nukes the seeded project root after `add`
    succeeds — the cleanest way to manufacture STALE rows: the
    registry retains the entry, but the marker file is gone so
    `classify_registry_entry` returns `STALE`.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - **t826_9 (`doctor`)** can reuse the exact `stale_names` /
    `stale_paths` collection loop in `cmd_prune` as the input to
    its interactive triage. The branching changes — instead of
    a `y/N` confirm-then-remove, doctor's per-entry prompt routes
    to `cmd_remove`, `cmd_update <new_path>`, or skip.
  - The `name → path` line format used by `--dry-run` (`  %s → %s`
    with two-space indent) is a good template for any future
    "preview before mutate" output in this script.
- **Build verification:** N/A (`verify_build` is unset in this
  project).
