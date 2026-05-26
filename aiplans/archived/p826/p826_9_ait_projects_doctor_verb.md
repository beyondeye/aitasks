---
Task: t826_9_ait_projects_doctor_verb.md
Parent Task: aitasks/t826_brainstorm_cross_repo_project_references.md
Sibling Tasks: aitasks/t826/t826_3_*.md, aitasks/t826/t826_4_*.md, aitasks/t826/t826_10_*.md
Archived Sibling Plans: aiplans/archived/p826/p826_1_*.md, p826_2_*.md, p826_5_*.md, p826_6_*.md, p826_7_*.md, p826_8_*.md
Worktree: (none — fast profile, current branch)
Branch: main
Base branch: main
---

## Context

Spun off from t826_5 brainstorm (`aiplans/archived/p826/p826_5_brainstorm_stale_registry_ux.md`,
decisions #2 and #3). The cross-repo project registry now has atomic
verbs `remove`, `update`, and bulk `prune` (children B and C, archived).
What is missing is the **interactive scan-and-repair front-end**:
`ait projects doctor` walks every STALE entry and offers a per-entry
choice (prune / update / clone / keep / skip-all), composing the
existing atomic verbs internally. The clone branch is gated behind an
opt-in `--clone` flag (brainstorm decision #3) because surprise
`git clone` into an absolute path is the wrong default.

Goal: ship `cmd_doctor` in `.aitask-scripts/aitask_projects.sh`,
register it on the verb dispatcher + help text, and cover the branches
with a new bash test alongside `test_aitask_projects_prune.sh`.

## Key Files to Modify

- `.aitask-scripts/aitask_projects.sh` — add `cmd_doctor` function +
  `doctor` dispatch case + `--help` entry + module-header verb-list
  entry.
- `tests/test_aitask_projects_doctor.sh` (new) — coverage modelled on
  `tests/test_aitask_projects_prune.sh` for setup/teardown style.

## Reference Patterns Reused

- `cmd_prune` (lines 430-495) — registry iteration over STALE entries
  via `classify_registry_entry`; for-loop with per-entry `read -r ans`.
- `cmd_remove --force` (lines 332-383) — internal helper for the prune
  branch.
- `cmd_update` (lines 387-426) — internal helper for the update
  branch. Already validates marker presence and exits on mismatch.
- `classify_registry_entry` (lines 224-238) — STALE detection.
- `list_registry_entries` (lines 146-196) — pipe-separated registry
  iteration; produces `name|path|git_remote|last_opened`.
- `tests/test_aitask_projects_prune.sh::seed_stale_entry` — the
  add-then-rm-rf trick to inject a STALE row with metadata intact.

## Implementation Plan

### 1. `cmd_doctor` function

Add after `cmd_prune` (before `cmd_resolve`).

**Argument parsing:**

```bash
cmd_doctor() {
    local enable_clone=0
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --clone) enable_clone=1; shift ;;
            -h|--help)
                echo "Usage: ait projects doctor [--clone]"
                return 0
                ;;
            *) die "Unknown argument: $1" ;;
        esac
    done
    ...
}
```

**Collect STALE entries** (preserving `git_remote` and `last_opened`):

```bash
local tsv
tsv=$(list_registry_entries || true)

local stale_names=() stale_paths=() stale_remotes=() stale_lasts=()
if [[ -n "$tsv" ]]; then
    while IFS='|' read -r name path remote last; do
        [[ -z "$name" ]] && continue
        local status
        status=$(classify_registry_entry "$name" "$path")
        if [[ "$status" == "STALE" ]]; then
            stale_names+=("$name")
            stale_paths+=("$path")
            stale_remotes+=("$remote")
            stale_lasts+=("$last")
        fi
    done <<< "$tsv"
fi

local total=${#stale_names[@]}
echo "Found $total stale entries."
[[ "$total" -eq 0 ]] && return 0
```

**Per-entry loop** with index `i/total`:

```bash
local i
for ((i = 0; i < total; i++)); do
    local idx=$((i + 1))
    local name="${stale_names[i]}"
    local path="${stale_paths[i]}"
    local remote="${stale_remotes[i]}"
    local last="${stale_lasts[i]}"

    printf '\n[%d/%d] STALE: %s → %s\n' "$idx" "$total" "$name" "$path"
    [[ -n "$last"   ]] && printf '         last opened: %s\n' "$last"
    [[ -n "$remote" ]] && printf '         git_remote:  %s\n' "$remote"

    # Build prompt — include `c` only when --clone AND remote is set.
    local prompt actions
    local can_clone=0
    if [[ "$enable_clone" -eq 1 && -n "$remote" ]]; then
        can_clone=1
        actions="[p]rune / [u]pdate / [c]lone / [k]eep / [s]kip-all"
    else
        actions="[p]rune / [u]pdate / [k]eep / [s]kip-all"
    fi
    printf '\n         Action? %s : ' "$actions" >&2

    local ans=""
    read -r ans || true

    case "$ans" in
        p|P)
            cmd_remove "$name" --force
            ;;
        u|U)
            printf '         New path: ' >&2
            local new_path=""
            read -r new_path || true
            if [[ -z "$new_path" ]]; then
                warn "No path given — skipping."
                continue
            fi
            # cmd_update validates marker presence; on failure it
            # dies(), which would abort the whole doctor loop. Run in
            # a subshell so we can recover.
            if ( cmd_update "$name" "$new_path" ); then
                :
            else
                warn "Update failed — entry left as-is."
            fi
            ;;
        c|C)
            if [[ "$can_clone" -ne 1 ]]; then
                warn "Clone not available (use --clone and ensure git_remote is set)."
                continue
            fi
            printf '         Clone %s into %s? [y/N]: ' "$remote" "$path" >&2
            local confirm=""
            read -r confirm || true
            case "$confirm" in
                y|Y) ;;
                *) info "Clone declined."; continue ;;
            esac
            if git clone "$remote" "$path"; then
                if [[ -f "$path/aitasks/metadata/project_config.yaml" ]]; then
                    info "Cloned and now OK."
                else
                    warn "Cloned but no aitasks/metadata/project_config.yaml — entry remains STALE."
                fi
            else
                warn "git clone failed — entry remains STALE."
            fi
            ;;
        k|K)
            info "Keeping $name."
            ;;
        s|S)
            info "Skipping remaining entries."
            break
            ;;
        *)
            warn "Unrecognized action '$ans' — keeping entry."
            ;;
    esac
done
```

**Key design notes:**

- `cmd_update` calls `die()` on a missing-marker error. We invoke it
  inside a subshell `( cmd_update ... )` so its `set -e` exit does
  not kill the doctor loop. The doctor reports `"Update failed —
  entry left as-is."` and moves on.
- After a successful `git clone`, we **don't write to the registry**:
  the marker file's presence flips classification on the next run
  automatically (per task description). This means doctor's clone
  branch is effectively idempotent and self-healing.
- Index `i/total` is 1-based for display (`[1/N]`) — matches the
  brainstorm prompt mockup.

### 2. Verb dispatcher

In `main()`, add after the `prune` case:

```bash
doctor)
    shift
    cmd_doctor "$@"
    ;;
```

### 3. `--help` block

Append after the `prune` row in `show_help()` (line 57):

```
  doctor [--clone]           Interactive scan: walk every STALE entry
                             and offer prune / update / clone / keep /
                             skip-all per entry. Clone is opt-in via
                             --clone and only offered for entries that
                             have a git_remote.
```

Also add an example line at the bottom (line 81):

```
  ait projects doctor
  ait projects doctor --clone
```

### 4. Module-header verb-list comment

Lines 10-27 of the script document the verb set in a comment block.
Add doctor after prune:

```
#   doctor [--clone]
#                          - Interactive scan: per-entry prune /
#                            update / clone / keep / skip-all.
#                            Clone branch is opt-in via --clone.
```

### 5. Test file `tests/test_aitask_projects_doctor.sh`

Model after `tests/test_aitask_projects_prune.sh`. Use the same
`seed_stale_entry` helper. Tests:

- **T1 — no stale entries** → `Found 0 stale entries.`, no prompts.
- **T2 — prune branch**: 1 STALE + 1 OK; stdin `p\n` → STALE removed
  from registry; OK preserved.
- **T3 — keep branch**: 1 STALE; stdin `k\n` → registry unchanged.
- **T4 — skip-all**: 2 STALE; stdin `s\n` → both still present (loop
  broke before second iteration).
- **T5 — `--clone` disabled hides `c` option**: 1 STALE with
  git_remote set (use the `OK` project itself as the `file://`
  source). Run without `--clone`. The action prompt line MUST NOT
  contain `[c]lone`. Stdin `c\n` → falls into "unrecognized" branch,
  entry kept.
- **T6 — `--clone` enabled but entry has no git_remote**: the
  `seed_stale_entry` helper writes `project_config.yaml` without
  `git_remote`, so the registry row has empty remote. Even with
  `--clone`, the prompt MUST NOT contain `[c]lone`.
- **T7 — `--clone` happy path**: extend `seed_stale_entry` (locally
  in the test, not in production code) to also set `git_remote` to
  a `file://$OK_ROOT` URL before deletion. Run with `--clone`; stdin
  `c\ny\n`. Verify:
  - Target path now exists.
  - Marker file is present (since OK project carries one).
  - Output contains `Cloned and now OK.`
- **T8 — update branch**: 1 STALE. Pre-create a fresh dir holding a
  marker file at `$TMPROOT/projects/new_loc`. Stdin
  `u\n$TMPROOT/projects/new_loc\n`. Verify registry now points
  there.
- **T9 — unknown flag fails fast** (mirrors prune's T5).

### 6. Help-block + module-header changes are non-functional but the
test should also assert `doctor` appears in `ait projects --help`
output (smoke-style assert; just `grep -F 'doctor'`).

## Verification

Run from repo root:

```bash
bash tests/test_aitask_projects_doctor.sh
shellcheck .aitask-scripts/aitask_projects.sh
ait projects --help | grep -F doctor   # smoke
```

Manual spot-check (optional, after tests pass):

```bash
# Seed a stale entry by hand.
mkdir -p /tmp/doctor_test/aitasks/metadata
echo "project:" > /tmp/doctor_test/aitasks/metadata/project_config.yaml
echo "  name: doctor_test" >> /tmp/doctor_test/aitasks/metadata/project_config.yaml
AITASKS_PROJECTS_INDEX=/tmp/dt_reg.yaml ait projects add /tmp/doctor_test
rm -rf /tmp/doctor_test
AITASKS_PROJECTS_INDEX=/tmp/dt_reg.yaml ait projects doctor   # press k, then check `list`
```

## Out of Scope

- Top-level `ait projects clone <name>` — brainstorm decision #3
  rejected this; clone stays gated through doctor.
- Auto-prune by `last_opened` age — display only (brainstorm Open
  Questions resolution).
- Race-condition handling in the TUI switcher — child E (t826_10).

## Step 9 reference

No worktree to clean (fast profile, current branch). After approval
and commit, archive via `./.aitask-scripts/aitask_archive.sh 826_9`,
which also drops `t826_9` from the parent's `children_to_implement`.

## Final Implementation Notes

- **Actual work done:** Added `cmd_doctor` (~110 lines), dispatcher
  case, `--help` block entry, and module-header verb-list entry in
  `.aitask-scripts/aitask_projects.sh`. New `tests/test_aitask_projects_doctor.sh`
  (10 tests, all passing) using the same `seed_stale_entry` pattern
  as the prune test. The `--clone` happy-path test initialises
  `OK_ROOT` as a real git repo and uses `file://$OK_ROOT` as the
  clone source, so the test runs entirely hermetically (no network).
- **Deviations from plan:** One — when `--clone` is *not* active and
  the user types `c`, the plan said "falls into 'unrecognized' branch".
  The implemented behavior is **more helpful**: the `c|C)` case arm
  matches first, checks `can_clone`, and warns "Clone not available
  (requires --clone and a git_remote)." rather than the generic
  "Unrecognized action" message. The test was updated to assert the
  helpful warning. Net behavior (entry kept, registry unchanged) is
  identical.
- **Issues encountered:** Initial test for the clone-disabled `c`
  input asserted the generic "Unrecognized action" warning per the
  plan; updated assertion to match the implemented helpful warning
  (a more user-friendly path than what the plan literally specified).
- **Key decisions:**
  - `cmd_update` is called inside a subshell `( cmd_update ... )`
    so its `die()` on missing-marker does not abort the whole doctor
    loop. The doctor warns "Update failed - entry left as-is." and
    moves on.
  - After a successful `git clone`, no registry write happens — the
    marker-file presence flips classification on the next run
    automatically. Idempotent and self-healing.
  - Test uses a local `file://` git source rather than mocking
    `git clone` via PATH override, which is hermetic and avoids the
    portability quirks of PATH-stubbing.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:** Doctor uses the established
  pattern of arrays (`stale_names=()`, `stale_paths=()`, etc.) for
  per-entry state, matching `cmd_prune`. The subshell wrapper around
  `cmd_update` is the right pattern any time a doctor-like
  orchestrator wraps a `die()`-on-error atomic verb — extend this to
  child E (t826_10) if its StaleEntryModal calls `cmd_update`.
