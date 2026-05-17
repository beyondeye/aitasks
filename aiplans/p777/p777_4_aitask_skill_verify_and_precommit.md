---
Task: t777_4_aitask_skill_verify_and_precommit.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_10_convert_aitask_fold.md, aitasks/t777/t777_11_convert_aitask_qa.md, aitasks/t777/t777_12_convert_aitask_pr_import.md, aitasks/t777/t777_13_convert_aitask_revert.md, aitasks/t777/t777_14_convert_aitask_pickrem.md, aitasks/t777/t777_15_convert_aitask_pickweb.md, aitasks/t777/t777_16_extract_profile_editor_widget.md, aitasks/t777/t777_17_per_run_profile_edit_in_agentcommandscreen.md, aitasks/t777/t777_18_docs_update_claudemd_and_website.md, aitasks/t777/t777_19_retrospective_evaluation.md, aitasks/t777/t777_20_profile_modification_invalidation.md, aitasks/t777/t777_5_aitask_skillrun_wrapper_dispatcher.md, aitasks/t777/t777_6_convert_aitask_pick_template_and_stubs.md, aitasks/t777/t777_7_convert_task_workflow_shared_procs.md, aitasks/t777/t777_8_convert_aitask_explore.md, aitasks/t777/t777_9_convert_aitask_review.md
Archived Sibling Plans: aiplans/archived/p777/p777_1_minijinja_dep_renderer_paths_resolver.md, aiplans/archived/p777/p777_2_aitask_skill_render_subcommand.md, aiplans/archived/p777/p777_3_stub_skill_design_and_gitignore.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-17 16:35
---

# Plan: t777_4 — `ait skill verify` + tests + CLAUDE.md doc (VERIFIED)

This is a **verify-mode** plan. The skeleton at `aiplans/p777/p777_4_aitask_skill_verify_and_precommit.md` and the task description at `aitasks/t777/t777_4_aitask_skill_verify_and_precommit.md` are the prior canonical. This document refines both based on verification against the current code state and a user clarification on the pre-commit hook.

## Context

t777_4 adds the verifier that protects the rest of the t777 work from broken authoring templates and drifting stubs. Per the design in `.claude/skills/task-workflow/stub-skill-pattern.md` (t777_3), each templated skill has 1 authoring template (`.claude/skills/<skill>/SKILL.md.j2`) + 4 stub surfaces (Claude SKILL.md, Codex SKILL.md, Gemini command TOML, OpenCode command MD). The verifier asserts (a) every `.j2` renders cleanly against `default.yaml` for all 4 agents (no strict-undefined errors, non-empty output) and (b) each stub follows the canonical dispatch pattern.

## Verification Findings (2026-05-17)

1. **No `.j2` authoring templates exist yet** — first lands in t777_6. The verifier must exit cleanly (rc 0, informative message) when zero `.j2` are present, so it is callable today and survives the t777_6+ rollout.

2. **`./ait` `skill)` sub-dispatch already scaffolded** for the new subcommand (`ait:198` carries the comment `# verify and resolve-profile subcommands added in later children`). Only the dispatch line and the `--help` text need to change.

3. **Per-agent stub surfaces are correctly enumerated in `stub-skill-pattern.md` §3g**: `.claude/skills/<skill>/SKILL.md`, `.agents/skills/<skill>/SKILL.md`, `.gemini/commands/<skill>.toml`, `.opencode/commands/<skill>.md`. Canonical markers (resolver call, render call, trailing-hyphen Read path) are documented in §3b–§3d.

4. **Existing stub-surface files today are NOT stubs yet** — Gemini/OpenCode command files `@`-include `.claude/skills/<skill>/SKILL.md`; Claude SKILL.md files contain full skill bodies. Stubs land progressively in t777_6..t777_15. Therefore the verifier must only check stub-pattern compliance for skills *that already have a `.j2`* — driving the verification loop by `.j2` files, not by all skill dirs, is the correct shape.

5. **Pre-commit hook deferred per user direction.** User stated: *"run ait skill verify explicitly for now: document in CLAUDE.md that when working with .j2 template they must be verified before commit; insert in CLAUDE.md the exact instructions on how to do it."* No `.git/hooks/` plumbing, no installer, no seed/ hook source — only documentation. This deviates from the original task description's §3 ("Install pre-commit hook") but matches the user-confirmed scope.

6. **`tests/test_skill_template.sh` is t777_1-scoped; t777_2 deviated** by creating its own `tests/test_skill_render.sh`. Following that precedent, t777_4 creates `tests/test_skill_verify.sh` rather than extending the t777_1 test file.

7. **Whitelist precedent**: `aitask_skill_render.sh` (t777_2) is whitelisted in all 5 touchpoints. The verifier mirrors that pattern exactly (single new entry per file, immediately after the render entry).

8. **Render path: use `skill_template.py` directly, not `aitask_skill_render.sh`.** Calling `./ait skill render` would write rendered output to gitignored dirs as a side effect (fine, but unnecessary on a verify-only path). Calling `skill_template.py` writes to stdout, allowing pure-functional verification with zero disk side effects.

## Refinements over Original Plan

- **R1 — Drive loop by `.j2` files** (skeleton plan implied "walk every `.j2`"; this finding makes it explicit). Skills without a `.j2` are unconverted; their stub-surface files are not yet stubs and must not trip stub-pattern checks.
- **R2 — No pre-commit hook.** Replaced with a CLAUDE.md doc step.
- **R3 — Use `skill_template.py` for render check, not `aitask_skill_render.sh`.** Zero disk side effects; bypasses skip-if-fresh + cross-skill-include recursion (neither is wanted for verification).
- **R4 — Verify only against `default.yaml`**, not every profile. Matches task description; tests the canonical "schema" because `default.yaml` is the minimum set every template must support.
- **R5 — New test file `tests/test_skill_verify.sh`** mirroring t777_2's deviation.

## Critical Files

**Create:**
- `.aitask-scripts/aitask_skill_verify.sh` — the verifier
- `tests/test_skill_verify.sh` — verifier tests

**Modify:**
- `ait` — extend `skill)` case (add `verify` dispatch + `--help` line)
- `CLAUDE.md` — add a "Verifying `.j2` Templates Before Commit" subsection
- `.claude/settings.local.json` — +1 whitelist entry
- `.gemini/policies/aitasks-whitelist.toml` — +1 `[[rule]]` block
- `seed/claude_settings.local.json` — +1 whitelist entry
- `seed/geminicli_policies/aitasks-whitelist.toml` — +1 `[[rule]]` block
- `seed/opencode_config.seed.json` — +1 allow entry

## Step Order

### Step 1 — Write `.aitask-scripts/aitask_skill_verify.sh`

Standard header mirroring `aitask_skill_render.sh`:

```bash
#!/usr/bin/env bash
# aitask_skill_verify.sh — Verify all .j2 authoring templates render cleanly
# across the 4 supported agents (default profile) and that each stub surface
# follows the canonical pattern documented in
# .claude/skills/task-workflow/stub-skill-pattern.md.
#
# Usage:
#   aitask_skill_verify.sh
#
# Exit codes:
#   0  - all checks pass (or no .j2 templates found yet)
#   1  - one or more failures (render error, empty output, missing/bad stub)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=.aitask-scripts/lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"
# shellcheck source=.aitask-scripts/lib/agent_skills_paths.sh
source "$SCRIPT_DIR/lib/agent_skills_paths.sh"

cd "$REPO_ROOT"
```

**Find all authoring templates:**

```bash
mapfile -t templates < <(
    find ".claude/skills" -mindepth 2 -maxdepth 3 -name 'SKILL.md.j2' -type f 2>/dev/null | sort
)

if [[ ${#templates[@]} -eq 0 ]]; then
    echo "ait skill verify: no .j2 templates found — nothing to verify."
    exit 0
fi
```

**Resolve interpreter + profile YAML:**

```bash
DEFAULT_PROFILE_YAML="aitasks/metadata/profiles/default.yaml"
if [[ ! -f "$DEFAULT_PROFILE_YAML" ]]; then
    echo "ait skill verify: default profile not found at $DEFAULT_PROFILE_YAML" >&2
    exit 1
fi

PYTHON="$(require_ait_python)"
SKILL_TEMPLATE_PY="$SCRIPT_DIR/lib/skill_template.py"
```

**Verification loop:**

```bash
failures=0
agents=(claude codex gemini opencode)

# Per-skill stub-surface map (mirrors stub-skill-pattern.md §3g)
_stub_path_for() {
    local agent="$1" skill="$2"
    case "$agent" in
        claude)   echo ".claude/skills/$skill/SKILL.md" ;;
        codex)    echo ".agents/skills/$skill/SKILL.md" ;;
        gemini)   echo ".gemini/commands/$skill.toml" ;;
        opencode) echo ".opencode/commands/$skill.md" ;;
    esac
}

for tpl in "${templates[@]}"; do
    skill="$(basename "$(dirname "$tpl")")"

    # --- Render check: render against default.yaml for each agent ---
    for agent in "${agents[@]}"; do
        if ! out="$("$PYTHON" "$SKILL_TEMPLATE_PY" "$tpl" "$DEFAULT_PROFILE_YAML" "$agent" 2>&1)"; then
            printf 'VERIFY_FAIL: %s agent=%s render error:\n%s\n' "$skill" "$agent" "$out" >&2
            failures=$((failures + 1))
            continue
        fi
        # Strip whitespace; non-empty check.
        if [[ -z "${out//[[:space:]]/}" ]]; then
            printf 'VERIFY_FAIL: %s agent=%s rendered output is empty\n' "$skill" "$agent" >&2
            failures=$((failures + 1))
        fi
    done

    # --- Stub-pattern check: 4 surfaces per skill ---
    for agent in "${agents[@]}"; do
        stub_path="$(_stub_path_for "$agent" "$skill")"
        if [[ ! -f "$stub_path" ]]; then
            printf 'STUB_FAIL: %s: missing stub for %s\n' "$stub_path" "$agent" >&2
            failures=$((failures + 1))
            continue
        fi
        # Canonical markers from stub-skill-pattern.md §3b-§3d:
        #   1) resolver call referencing this skill
        #   2) render call referencing this skill
        #   3) trailing-hyphen Read path with <profile>- placeholder
        if ! grep -q "aitask_skill_resolve_profile\.sh ${skill}" "$stub_path"; then
            printf 'STUB_FAIL: %s: missing resolver call ("aitask_skill_resolve_profile.sh %s")\n' \
                "$stub_path" "$skill" >&2
            failures=$((failures + 1))
        fi
        if ! grep -q "ait skill render ${skill}" "$stub_path"; then
            printf 'STUB_FAIL: %s: missing render call ("ait skill render %s")\n' \
                "$stub_path" "$skill" >&2
            failures=$((failures + 1))
        fi
        if ! grep -q "${skill}-<profile>-/SKILL\.md" "$stub_path"; then
            printf 'STUB_FAIL: %s: missing trailing-hyphen Read path ("%s-<profile>-/SKILL.md")\n' \
                "$stub_path" "$skill" >&2
            failures=$((failures + 1))
        fi
    done
done

if (( failures > 0 )); then
    echo "ait skill verify: $failures failure(s)" >&2
    exit 1
fi

echo "ait skill verify: OK (${#templates[@]} template(s) verified across ${#agents[@]} agents)"
```

**Notes:**
- Uses `require_ait_python` (one-shot CLI) per CLAUDE.md "TUI Conventions".
- Uses extended regex–compatible plain `grep -q` (no PCRE).
- Skill name derived from the parent directory of each `.j2` — matches `agent_authoring_template <skill>` convention.
- Render-check goes through `skill_template.py` directly (stdout) to avoid writing gitignored dirs.

### Step 2 — Extend `./ait` `skill)` case

Locate the existing block at `ait:192-213`. Add `verify` dispatch and update the `--help` listing:

```bash
    skill)
        shift
        subcmd="${1:-}"
        shift || true
        case "$subcmd" in
            render)            exec "$SCRIPTS_DIR/aitask_skill_render.sh" "$@" ;;
            verify)            exec "$SCRIPTS_DIR/aitask_skill_verify.sh" "$@" ;;
            # resolve-profile subcommand added in later children
            --help|-h|"")
                echo "Usage: ait skill <subcommand> [options]"
                echo ""
                echo "Available subcommands:"
                echo "  render   Render a skill template into a per-profile directory"
                echo "  verify   Verify all .j2 templates render cleanly + stubs follow canonical pattern"
                echo ""
                echo "Run 'ait skill <subcommand> --help' for subcommand-specific help."
                exit 0
                ;;
            *) echo "ait skill: unknown subcommand '$subcmd'" >&2
               echo "Available: render, verify" >&2
               exit 1
               ;;
        esac
        ;;
```

Concretely 3 edits: insert the `verify)` line after the `render)` line; replace the comment to drop `verify`; add the help-line for verify; update the available-list in the `*)` branch.

### Step 3 — Whitelist `aitask_skill_verify.sh` in 5 touchpoints

Mirror the t777_2 pattern exactly. Place each entry adjacent to the existing `aitask_skill_render.sh` entry.

| File | Entry |
|------|-------|
| `.claude/settings.local.json` | `"Bash(./.aitask-scripts/aitask_skill_verify.sh:*)"` in `permissions.allow` (after the render entry, currently at line 34) |
| `.gemini/policies/aitasks-whitelist.toml` | new `[[rule]]` block: `toolName = "run_shell_command"`, `commandPrefix = "./.aitask-scripts/aitask_skill_verify.sh"`, `decision = "allow"`, `priority = 100` (after the render block, currently at line 213) |
| `seed/claude_settings.local.json` | mirror of Claude runtime (after line 37) |
| `seed/geminicli_policies/aitasks-whitelist.toml` | mirror of Gemini runtime (after line 183) |
| `seed/opencode_config.seed.json` | `"./.aitask-scripts/aitask_skill_verify.sh *": "allow"` (after line 26) |

Codex exempt per CLAUDE.md "Adding a New Helper Script".

### Step 4 — Write `tests/test_skill_verify.sh`

Pattern-match `tests/test_skill_render.sh`: inline `assert_eq`/`assert_contains`, PASS/FAIL/TOTAL counters, EXIT-trap cleanup, scratch skill prefix `_t777_4_test_`, SKIP gracefully if minijinja missing, `cd "$PROJECT_DIR"`.

**Test cases:**

| # | Case | Mechanism |
|---|------|-----------|
| 1 | No `.j2` templates yet → `ait skill verify` exits 0 with "no .j2 templates found" | The current checkout has zero `.j2` files (assuming no test scratch is leftover); assert exit 0 + stdout contains "no .j2 templates found". For robustness against test-leftover scratch dirs from t777_2's `test_skill_render.sh`, pre-clean `.claude/skills/_t777_*_test_*` at test start before running this case. |
| 2 | Broken `.j2` (strict-undefined) → exit non-zero, stderr contains `VERIFY_FAIL` | Plant `.claude/skills/_t777_4_test_broken/SKILL.md.j2` referencing `{{ profile.no_such_field }}`. Need 4 minimal stub surfaces too (otherwise STUB_FAIL drowns out the VERIFY_FAIL signal we're testing). Or assert stderr contains `VERIFY_FAIL` regardless of additional STUB_FAILs. |
| 3 | Well-formed `.j2` with no stub surfaces → exit non-zero, stderr contains `STUB_FAIL: ... missing` | Plant only `.j2`, no stub files; assert all 4 missing-stub messages present. |
| 4 | Well-formed `.j2` with valid stubs in all 4 surfaces → exit 0 | Plant `.j2` + 4 stub files containing the canonical markers. Verifies happy path. |
| 5 | Stub missing resolver call → `STUB_FAIL: ... missing resolver call` | Plant `.j2` + 4 stubs where one omits the `aitask_skill_resolve_profile.sh <skill>` marker; assert specific failure message. |
| 6 | Stub missing render call → `STUB_FAIL: ... missing render call` | Mirror of #5 for the render-call marker. |
| 7 | Stub missing trailing-hyphen Read path → `STUB_FAIL: ... missing trailing-hyphen Read path` | Mirror of #5 for the Read-path marker. |
| 8 | `./ait skill --help` mentions `verify` | Assert stdout contains "verify". |
| 9 | `./ait skill bogus` (after this task lands) lists `verify` in "Available" | Assert stderr contains "Available: render, verify". |
| 10 | Whitelist files contain exactly one `aitask_skill_verify.sh` entry each (5 files) | `grep -c aitask_skill_verify` per touchpoint; assert each = 1. |

**Scratch-dir EXIT cleanup:** explicit `rm -rf .claude/skills/_t777_4_test_* .agents/skills/_t777_4_test_* .gemini/commands/_t777_4_test_* .opencode/commands/_t777_4_test_*` in the cleanup function (NOT just relying on `mktemp -d` cleanup, since scratch skills go under tracked dirs). Matches the upstream-defect fix proposed in t777_2's Final Implementation Notes ("Recommended fix: extend cleanup() to rm -rf .claude/skills/${TEST_SKILL_PREFIX}*").

### Step 5 — Document `.j2` verify workflow in CLAUDE.md

Insert under the "WORKING ON SKILLS / CUSTOM COMMANDS" section (after the existing intro paragraph about the source-of-truth implementation, before "### Skill / Workflow Authoring Conventions"). Concrete text:

```markdown
### Verifying `.j2` Templates Before Commit

When you add or modify a `.j2` authoring template (`.claude/skills/<skill>/SKILL.md.j2`) or a per-agent stub surface (`.claude/skills/<skill>/SKILL.md`, `.agents/skills/<skill>/SKILL.md`, `.gemini/commands/<skill>.toml`, `.opencode/commands/<skill>.md`), run `ait skill verify` before committing:

```bash
./ait skill verify
```

This renders every `.j2` against `default.yaml` for all 4 supported agents and asserts each stub surface contains the canonical markers from `.claude/skills/task-workflow/stub-skill-pattern.md` (resolver call, render call, trailing-hyphen Read path). The script exits non-zero on any render error or stub-pattern violation; address every failure before committing.

If no `.j2` templates exist yet, the command prints "no .j2 templates found — nothing to verify." and exits 0. That is the expected state until the first authoring template lands in t777_6.

`ait skill verify` writes nothing to disk (it pipes the render through `skill_template.py` to stdout). It is safe to run anytime.
```

(Note: the inner code fence uses 3 backticks but is escaped in the plan listing because the plan file is itself markdown. At edit time, the inner block is a plain ```bash fence.)

## Pitfalls

- **Render check via `skill_template.py`, NOT `aitask_skill_render.sh`** — render-via-render-script would write to gitignored dirs as a side effect, but more importantly would invoke the cross-skill recursive include scan, which double-counts failures and obscures origins. Direct CLI invocation is the verification primitive.
- **Strict-undefined error messages name the template file** — verified by t777_1's `test_skill_template.sh` line 135. Stdin-passing `2>&1` capture preserves that detail in the failure log.
- **The trailing-hyphen Read path grep is angle-bracket-literal** — `<profile>-/SKILL.md`. Stub authors must use the literal `<profile>` placeholder, NOT `{{ profile.name }}` or `$profile` etc. This is the convention documented in §3b-§3d and is what enables a single uniform grep across all 4 surfaces.
- **Test scratch-dir leakage** — Claude auto-discovers skill dirs under `.claude/skills/`, so leftover `_t777_4_test_*` dirs become visible as skills after a failed test run. EXIT trap MUST clean them, AND the test start should pre-clean in case a prior run aborted. Matches t777_2's lesson.
- **No `.git/hooks/` write-access** — per user direction, no pre-commit installation. Future task may revisit once `.j2` files exist and we have evidence the manual workflow is insufficient.
- **`set -o pipefail` interaction** — the verifier itself doesn't pipe shell-output to early-exit awk, so the SIGPIPE-141 issue from t777_2 R7 does not recur here. Mentioned only for awareness.

## Verification Steps

1. `bash tests/test_skill_verify.sh` — all cases PASS (or SKIP on systems without minijinja).
2. `bash tests/test_skill_template.sh` — still 20/20 PASS (no regression from t777_1).
3. `bash tests/test_skill_render.sh` — still 32/32 PASS (no regression from t777_2).
4. `shellcheck -x .aitask-scripts/aitask_skill_verify.sh tests/test_skill_verify.sh` — clean.
5. `./ait skill --help` lists `verify` alongside `render`.
6. `./ait skill verify` on the current checkout (no `.j2`) → exit 0, message "no .j2 templates found".
7. `./ait skill bogus` → exit 1, stderr `Available: render, verify`.
8. `grep -c aitask_skill_verify` on each of the 5 whitelist files → exactly 1 each.
9. `CLAUDE.md` contains the new "Verifying `.j2` Templates Before Commit" subsection with the verbatim command `./ait skill verify`.

## Step 9 (Post-Implementation)

Standard child-task archival via `./.aitask-scripts/aitask_archive.sh 777_4`. Final Implementation Notes (in the archived plan) MUST document:
- Pre-commit hook explicitly deferred per user direction; CLAUDE.md doc is the substitute mechanism.
- Render-check uses `skill_template.py` directly (NOT `aitask_skill_render.sh`); rationale for sibling implementers.
- Verification-driven-by-`.j2`-files convention (skills without `.j2` are skipped — not yet stubs).
- Whether the stub-marker greps (resolver, render, Read-path) need refinement after t777_6's pilot stub authoring.

## Reuse Notes

- `lib/skill_template.py` is the render primitive (writes to stdout). Strict-undefined behavior + filename in error already verified by t777_1.
- `lib/agent_skills_paths.sh` provides `agent_skill_root`, `agent_skill_dir`, `agent_authoring_template`.
- `aitask_scan_profiles.sh` is the canonical profile enumerator; not needed here (default.yaml path is fixed).
- `tests/test_skill_render.sh` is the canonical test-style template for verifier-class tests (scratch skill dirs, EXIT trap cleanup, PASS/FAIL counters).
- `stub-skill-pattern.md` §3g table is the single source of truth for per-agent stub paths.
