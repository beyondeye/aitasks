---
Task: t777_2_aitask_skill_render_subcommand.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_*_*.md
Archived Sibling Plans: aiplans/archived/p777/p777_*_*.md
Parent Plan: aiplans/p777_modular_pick_skill.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-17 14:17
---

# Plan: t777_2 — `ait skill render` subcommand + whitelist + automated tests (VERIFIED)

This is a **verify-mode** plan. The external plan at `aiplans/p777/p777_2_aitask_skill_render_subcommand.md` and the task description at `aitasks/t777/t777_2_aitask_skill_render_subcommand.md` remain canonical. This document records verification findings, refinements, and adds a full automated test deliverable per user feedback.

## Context

t777_2 adds the `ait skill render` subcommand — the per-`(skill, profile, agent)` rendering entry point used by:
- The stub SKILL.md (when `/aitask-pick` runs inside a live agent session)
- The `ait skillrun` wrapper (t777_5)
- The `AgentCommandScreen` per-run UI (t777_17)

It builds atop the t777_1 foundation (`lib/skill_template.py`, `lib/agent_skills_paths.sh`, `aitask_skill_resolve_profile.sh`).

## Verification Findings (2026-05-17)

- **t777_1 foundations present:**
  - `.aitask-scripts/lib/skill_template.py` exposes `render_skill(template_path, profile, agent_name)` with strict-undefined behavior. Loader scoped to template's parent dir only.
  - `.aitask-scripts/lib/agent_skills_paths.sh` exports `agent_skill_root`, `agent_skill_dir`, `agent_authoring_template <skill>` → `.claude/skills/<skill>/SKILL.md.j2`.
  - `.aitask-scripts/aitask_skill_resolve_profile.sh` resolves precedence userconfig → project_config → `"default"`.
- **`aitask_skill_render.sh` is absent — clean slate.**
- **`./ait` dispatcher is NOT strictly alphabetical.** Relevant slots: L185 `settings)`, L191 `setup)`, L199 `crew)` (sub-dispatch), L235 `brainstorm)` (sub-dispatch). Place `skill)` immediately after `setup)` (between L191 and L192) for ergonomic grouping.
- **minijinja Python API** (live-checked): exports `Environment`, `Markup`, `TemplateError`, `load_from_path`, `render_str`, etc. **No `__version__`, no public parser AST.** Includes detectable only by source-level regex.
- **Whitelist state — IMPORTANT DEVIATION from original plan:** `aitask_skill_resolve_profile.sh` is **already whitelisted** in all 5 touchpoints (verified by grep). The t777_1 implementation already did this — t777_2 only needs entries for the new `aitask_skill_render.sh`.
- **`realpath -m` is GNU-only.** macOS BSD `realpath` does NOT support `-m`. Use plain `realpath` and gate via `[[ -f ... ]]` instead (existing-file requirement is fine here — we only follow valid `.j2` include targets).
- **Existing test pattern** (`tests/test_skill_template.sh`): inline `assert_eq`/`assert_contains` helpers, PASS/FAIL/TOTAL counters, SKIPs cleanly if minijinja isn't installed. Cd's to `$PROJECT_DIR`, uses `mktemp -d` + EXIT trap. Mirror this exactly for `test_skill_render.sh`.
- **No `stat_mtime` helper exists** in `terminal_compat.sh` today — `sed_inplace` is present but `stat` portability is not yet centralized. Inline the `stat -c %Y 2>/dev/null || stat -f %m` fallback in this script. (Refactoring into terminal_compat is out of scope; if pattern recurs in t777_4 / t777_5, a follow-up sibling can extract it.)

## Refinements over Original Plan

### R1 — Whitelist scope narrowed
`aitask_skill_resolve_profile.sh` is already whitelisted from t777_1. Drop it from t777_2's deliverables. Only `aitask_skill_render.sh` is added.

### R2 — Recursive include semantics (cross-skill only)
Minijinja `{% include %}` **inlines** at render time. The "recursive render" step is about **cross-skill** `.j2` references — files under a *different* skill subdir that should exist as standalone rendered SKILL files.

Concrete algorithm:
1. Scan template source via bash regex (no PCRE per CLAUDE.md "grep portability"): `{%-?[[:space:]]*include[[:space:]]+["'\'']([^"'\'']+\.j2)["'\'']`.
2. For each match, resolve via plain `realpath` (no `-m`) relative to template's parent.
3. **Skip** if path resolves *inside the same skill directory* — minijinja inlines natively.
4. **Skip** if path does not exist or is not a `.j2` file.
5. For each remaining cross-skill `.j2`, derive its skill name (the dir under `.claude/skills/`) and recursively invoke `aitask_skill_render.sh <other_skill> --profile <name> --agent <agent>`.

At t777_2 completion no `.j2` templates exist yet (t777_6 introduces the first). The recursive-include codepath is therefore exercised by automated tests against hand-crafted smoke templates only — see Test Plan below.

### R3 — Skip-if-fresh tracks template + profile YAML mtimes only
A change to an inlined include will NOT auto-retrigger re-render. Documented limitation; wrappers pass `--force` when uncertain.

### R4 — Drop `realpath -m`; use plain `realpath`
GNU-only flag. Plain `realpath` is portable on Linux and macOS ≥12.3 (BSD). Gate output with `[[ -f ... ]]`.

## Critical Files

**Create:**
- `.aitask-scripts/aitask_skill_render.sh` — the helper
- `tests/test_skill_render.sh` — automated tests (see Test Plan)

**Modify:**
- `./ait` — add `skill)` sub-dispatch after `setup)` (L191)
- `.claude/settings.local.json` — +1 permission entry
- `.gemini/policies/aitasks-whitelist.toml` — +1 rule block
- `seed/claude_settings.local.json` — +1 permission entry
- `seed/geminicli_policies/aitasks-whitelist.toml` — +1 rule block
- `seed/opencode_config.seed.json` — +1 permission entry

## Step Order

### 1. Write `.aitask-scripts/aitask_skill_render.sh`

Standard header:
```bash
#!/usr/bin/env bash
# aitask_skill_render.sh - Render a (skill, profile, agent) into per-profile dir.
# Usage: aitask_skill_render.sh <skill> --profile <name> --agent <name> [--force]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"
# shellcheck source=lib/agent_skills_paths.sh
source "$SCRIPT_DIR/lib/agent_skills_paths.sh"
```

**Argument parse:** positional `<skill>` first, then flags. Fail with usage on missing required values, unknown flag, or extras.

**Portable mtime helper** (inlined — no `terminal_compat.sh` addition):
```bash
_get_mtime() {
    stat -c %Y "$1" 2>/dev/null || stat -f %m "$1"
}
```
This is the single point where `stat` portability is exercised. All four `stat` call-sites in the script go through `_get_mtime`.

**Profile YAML resolution** via `aitask_scan_profiles.sh`:
```bash
profile_filename="$("$REPO_ROOT/.aitask-scripts/aitask_scan_profiles.sh" \
    | awk -F'|' -v n="$profile_name" '$1=="PROFILE" && $3==n {print $2; exit}')"
[[ -z "$profile_filename" ]] && { echo "skill_render: profile '$profile_name' not found" >&2; exit 1; }
profile_yaml="$REPO_ROOT/aitasks/metadata/profiles/$profile_filename"
```

**Authoring template + target paths** via t777_1 helpers:
```bash
template_path="$REPO_ROOT/$(agent_authoring_template "$skill")"
[[ -f "$template_path" ]] || { echo "skill_render: template not found: $template_path" >&2; exit 1; }
target_dir="$REPO_ROOT/$(agent_skill_dir "$agent" "$skill" "$profile_name")"
target_file="$target_dir/SKILL.md"
```

**Skip-if-fresh** (unless `--force`):
```bash
if [[ "$force" == false && -f "$target_file" ]]; then
    target_mtime=$(_get_mtime "$target_file")
    tpl_mtime=$(_get_mtime "$template_path")
    yaml_mtime=$(_get_mtime "$profile_yaml")
    if (( target_mtime > tpl_mtime && target_mtime > yaml_mtime )); then
        exit 0
    fi
fi
```

**Atomic render:**
```bash
PYTHON="$(require_ait_python)"
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT
tmpfile="$tmpdir/SKILL.md.tmp"
"$PYTHON" "$SCRIPT_DIR/lib/skill_template.py" \
    "$template_path" "$profile_yaml" "$agent" > "$tmpfile"
mkdir -p "$target_dir"
mv "$tmpfile" "$target_file"
```

**Cross-skill recursive include scan** (per R2):
```bash
parent_dir="$(dirname "$template_path")"
template_skill_root="$(dirname "$parent_dir")"
include_regex='\{%-?[[:space:]]*include[[:space:]]+["'\'']([^"'\'']+\.j2)["'\'']'
grep -oE "$include_regex" "$template_path" 2>/dev/null \
    | sed -E "s|.*[\"']([^\"']+\\.j2)[\"'].*|\\1|" \
    | sort -u \
    | while read -r inc_rel; do
        inc_abs="$(cd "$parent_dir" && realpath "$inc_rel" 2>/dev/null || true)"
        [[ -z "$inc_abs" || ! -f "$inc_abs" ]] && continue
        case "$inc_abs" in "$parent_dir"/*) continue ;; esac
        rel_to_root="${inc_abs#"$template_skill_root"/}"
        other_skill="${rel_to_root%%/*}"
        [[ -z "$other_skill" || "$other_skill" == "$rel_to_root" ]] && continue
        local_args=("$other_skill" --profile "$profile_name" --agent "$agent")
        [[ "$force" == true ]] && local_args+=(--force)
        "$0" "${local_args[@]}"
    done
```

### 2. Add `skill)` to `./ait` (after L191 `setup)`)

```bash
    skill)
        shift
        subcmd="${1:-}"
        shift || true
        case "$subcmd" in
            render)            exec "$SCRIPTS_DIR/aitask_skill_render.sh" "$@" ;;
            # verify and resolve-profile subcommands added in later children
            --help|-h|"")
                echo "Usage: ait skill <subcommand> [options]"
                echo ""
                echo "Available subcommands:"
                echo "  render   Render a skill template into a per-profile directory"
                echo ""
                echo "Run 'ait skill <subcommand> --help' for subcommand-specific help."
                exit 0
                ;;
            *) echo "ait skill: unknown subcommand '$subcmd'" >&2
               echo "Available: render" >&2
               exit 1 ;;
        esac
        ;;
```

### 3. 5-touchpoint whitelist for `aitask_skill_render.sh` ONLY

| File | Entry |
|---|---|
| `.claude/settings.local.json` | `"Bash(./.aitask-scripts/aitask_skill_render.sh:*)"` in `permissions.allow` (place right after `aitask_skill_resolve_profile.sh`) |
| `.gemini/policies/aitasks-whitelist.toml` | new `[[rule]]` block: `toolName = "run_shell_command"`, `commandPrefix = "./.aitask-scripts/aitask_skill_render.sh"`, `decision = "allow"`, `priority = 100` |
| `seed/claude_settings.local.json` | mirror of Claude runtime |
| `seed/geminicli_policies/aitasks-whitelist.toml` | mirror of Gemini runtime |
| `seed/opencode_config.seed.json` | `"./.aitask-scripts/aitask_skill_render.sh *": "allow"` |

Codex exempt per CLAUDE.md "Adding a New Helper Script".

### 4. Write `tests/test_skill_render.sh`

Pattern-match `tests/test_skill_template.sh`: inline `assert_eq`/`assert_contains`, PASS/FAIL/TOTAL, SKIP gracefully if minijinja is missing, `mktemp -d` scratch + EXIT trap, `cd "$PROJECT_DIR"`. The tests use **scratch skill names prefixed `_t777_2_test_`** under `.claude/skills/` so they don't collide with real skills. All scratch dirs are cleaned in the EXIT trap.

**Test cases (each one PASS/FAIL counted):**

| # | Case | Mechanism |
|---|------|-----------|
| 1 | Basic render: template + profile → `<target>/SKILL.md` exists and renders profile values | Hand-crafted template & profile; assert target file present and content matches |
| 2 | Skip-if-fresh: second run is no-op | Capture `_get_mtime` on target; re-run; assert mtime unchanged |
| 3 | Newer **template** mtime → re-render fires | `touch` the template (or `sleep 1 && touch` to clear coarse 1-sec resolution); re-run; assert target mtime advanced |
| 4 | Newer **profile YAML** mtime → re-render fires | `touch` the profile YAML; re-run; assert target mtime advanced |
| 5 | `--force` re-renders unconditionally even when fresh | Re-run with `--force`; assert target mtime advanced |
| 6 | Cross-skill include recursion: A includes B (`.j2`, different skill dir) → both rendered | Create `_t777_2_test_a` and `_t777_2_test_b`; B's template `{% include "../_t777_2_test_a/SKILL.md.j2" %}`; render B; assert both `_t777_2_test_a-<prof>/SKILL.md` and `_t777_2_test_b-<prof>/SKILL.md` present |
| 7 | Same-skill `.j2` include is inlined natively (NOT recursively rendered as a separate skill) | Create a single skill with two `.j2` files in same dir; render parent; assert single output, no spurious sibling-skill dir created |
| 8 | Plain `.md` includes are skipped (no `.j2` extension) | Create a template referencing `something.md`; assert no recursive call |
| 9 | Negative: missing template (`.j2` not found at expected path) → non-zero exit + stderr match | Use unknown skill name; assert exit ≠ 0 and stderr contains "template not found" |
| 10 | Negative: unknown profile name → non-zero exit + stderr match | Pass profile name not in `aitask_scan_profiles.sh` output; assert "profile … not found" |
| 11 | Negative: missing required arg (no `--profile`) → non-zero exit + usage message | Run without `--profile`; assert exit ≠ 0 and stderr contains "Usage" |
| 12 | Unknown agent → non-zero exit (propagated from `agent_skill_root`) | Pass `--agent bogus`; assert exit ≠ 0 |
| 13 | **Portability — Linux branch (`stat -c %Y`)** active in current run | Verify `_get_mtime` resolves on the current host (touched file mtime is positive integer that increases on `touch`) |
| 14 | **Portability — BSD branch (`stat -f %m`)** code path | Create a PATH-shadowing dir with a `stat` shim that errors on `-c` (forcing the `||` fallback to `-f`); re-run scenario from test 1 with PATH-shadow active; assert render still produces correct output and skip-if-fresh still works |
| 15 | `realpath` portability (plain, no `-m`) — include-target file existence is the gate | Reference a missing `.j2` from a template; assert renderer does NOT crash and does NOT recurse on the missing target |
| 16 | `./ait skill --help` prints subcommand listing | `./ait skill --help`; assert stdout contains "render" |
| 17 | `./ait skill bogus` exits 1 with "unknown subcommand" | Capture stderr; assert exit ≠ 0 and stderr contains "unknown subcommand 'bogus'" |
| 18 | Whitelist files contain exactly one `aitask_skill_render.sh` entry each (5 files) | `grep -c aitask_skill_render` per touchpoint; assert each is 1 |

**Test 14 BSD-fallback shim** (concrete pattern — drop in `$TMP_DIR/shim/stat`):
```bash
SHIM_DIR="$TMP_DIR/shim"
mkdir -p "$SHIM_DIR"
cat > "$SHIM_DIR/stat" <<'SHIM'
#!/usr/bin/env bash
# Reject -c flag (forces script's || fallback to -f %m branch)
if [[ "$1" == -c* ]]; then
    echo "stat: -c not supported (shim)" >&2
    exit 1
fi
exec /usr/bin/stat "$@"
SHIM
chmod +x "$SHIM_DIR/stat"
PATH="$SHIM_DIR:$PATH" bash .aitask-scripts/aitask_skill_render.sh ...
```
Probe `/usr/bin/stat` existence at test entry; if missing (rare), SKIP test 14 with a clear note rather than failing.

**Test 18 expansion** runs `grep -c` against:
- `.claude/settings.local.json`
- `.gemini/policies/aitasks-whitelist.toml`
- `seed/claude_settings.local.json`
- `seed/geminicli_policies/aitasks-whitelist.toml`
- `seed/opencode_config.seed.json`

Each must contain exactly `1` matching line. (Verifies no duplicate entries from accidental double-edit.)

## Pitfalls

- **Atomic mv** — render to a tempfile in `$(mktemp -d)` and `mv` into place. Live agent sessions may be re-reading SKILL.md (see [[feedback_skills_reread_during_execution]]) — partial writes are unacceptable.
- **`stat` portability** — Centralize via inline `_get_mtime` helper; cover both branches in tests (`stat -c %Y` on Linux, `stat -f %m` fallback via PATH-shadow shim).
- **`realpath -m` is GNU-only** — Use plain `realpath` + `[[ -f ]]` gate.
- **Skip-if-fresh ignores included files** — Documented limitation; wrappers pass `--force` when uncertain.
- **`require_ait_python` (not `_fast`)** — One-shot CLI per CLAUDE.md "TUI Conventions".
- **Recursive include regex avoids PCRE** — Use `grep -oE` (extended regex) per CLAUDE.md "grep portability".
- **Coarse-resolution mtimes** — On filesystems with 1-second mtime granularity, immediate-back-to-back `touch` may not register. Use `sleep 1` before mtime-bumping touches in tests 3 and 4.
- **Test scratch dirs under `.claude/skills/`** — Prefix `_t777_2_test_` so they're easily filterable. EXIT trap cleans them; also pre-clean at test start in case a prior run aborted mid-flight.

## Verification Steps

1. `bash tests/test_skill_render.sh` — all 18 cases PASS (or test 14 SKIP with rationale on systems without `/usr/bin/stat`).
2. `shellcheck -x .aitask-scripts/aitask_skill_render.sh tests/test_skill_render.sh` — clean.
3. `./ait skill --help` and `./ait skill bogus` produce expected output (also exercised by tests 16/17).
4. Manual sanity: `grep aitask_skill_render` across all 5 whitelist files — exactly one entry each (test 18).

## Post-Implementation (Step 9)

Standard child-task archival via `./.aitask-scripts/aitask_archive.sh 777_2`. Update Final Implementation Notes with:
- Confirmed regex for recursive include detection (so t777_5/t777_17 wrappers reproduce it correctly).
- Any `stat`/`realpath` quirks discovered during implementation or CI.
- Whether the `_get_mtime` inline helper should be extracted into `terminal_compat.sh` (only if t777_4 or t777_5 also needs it — propose as a sibling refactor if so, per [[feedback_single_source_of_truth_for_versions]]).

## Reuse Notes

- **t777_1 final notes** are canonical for the minijinja API contract.
- `aitask_scan_profiles.sh` is the single source for profile-file enumeration (incl. `local/*` overrides) — call it, do not reimplement.
- `agent_authoring_template <skill>` is the single source of truth for authoring template paths.
- The `crew)` / `brainstorm)` blocks in `./ait` are the canonical sub-dispatch pattern.
- `tests/test_skill_template.sh` is the canonical test-style template for this project.
