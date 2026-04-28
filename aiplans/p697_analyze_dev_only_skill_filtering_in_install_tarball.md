---
Task: t697_analyze_dev_only_skill_filtering_in_install_tarball.md
Worktree: (none — current branch, per profile `fast`)
Branch: main
Base branch: main
---

## Context

Task t697 is **analysis-only**. It produces a written recommendation about whether — and how — `install.sh` should filter framework-development-only skills and helper scripts out of the distribution that lands in user projects.

**Why now:** Two skills that exist *only* to maintain the framework itself (`aitask-add-model`, `aitask-audit-wrappers`, the latter introduced in t691) currently ship to every user install. As more such skills accumulate, the distribution grows noisier (extra skill files, extra whitelist entries triggering permission prompts) for users who will never invoke them. The motivation in the task description names this concern explicitly.

**What this task does NOT do:** modify `install.sh`, change any skill file, or land any filter logic. The deliverable is a written analysis stored as **Final Implementation Notes** of this task's plan, plus a list of tightly-scoped follow-up tasks created via `aitask_create.sh --batch --commit`. Implementation lands in the follow-ups.

## Outline of the Analysis (to be written as Final Implementation Notes)

The Final Implementation Notes section, written in Step 7 and consolidated in Step 8, will contain the four parts below. Outline only — full prose lands at implementation time.

### Part 1 — Inventory of dev-only artifacts (table)

Inventory the four classes the task description names (`.claude/skills/`, `.aitask-scripts/`, mirrors under `.agents/skills/` + `.opencode/skills/` + `.opencode/commands/` + `.gemini/commands/`, and seed/whitelist entries). Initial classification, refined during write-up:

| Skill | Classification | Mirror count | Helper script | Whitelist surfaces today |
|---|---|---|---|---|
| `aitask-add-model` | **Dev-only** (confirmed) | 4 (agents, opencode/skills, opencode/commands, gemini/commands) | `aitask_add_model.sh` | **Missing from all 5** — pre-existing whitelist gap, see "Aside" below |
| `aitask-audit-wrappers` | **Dev-only** (confirmed) | 4 | `aitask_audit_wrappers.sh` | Present in all 5 (landed in t691) |
| `aitask-refresh-code-models` | **Dev-only** (proposed) | 4 | `aitask_refresh_code_models.sh` | Status TBD during write-up |
| `aitask-changelog` | **End-user** (proposed, contra explore-agent classification) | 4 | `aitask_changelog.sh` | n/a — keep |

Justification for `aitask-changelog` as end-user (not dev-only): the helper is **project-agnostic** (`aitask_changelog.sh:20` — `git tag --list 'v*'` + `(tNN)` commit suffix detection), works on any aitasks-using project that tags releases, and produces user-facing release notes from that project's archived plans. Many adopters will want it for their own changelogs.

Justification for `aitask-refresh-code-models` as dev-only: it overwrites `models_*.json` config files with web-researched updates. End users who care about a specific model edit those files directly; the workflow of "research the latest models and seed them" is framework-maintenance scope.

`aitask-reviewguide-*` (classify, merge, import), `aitask-contribute`, `aitask-contribution-review` are end-user — the reviewguide trio supports user-imported review guides; `contribute*` exposes upstream issue/PR creation against arbitrary repos. None are dev-only.

### Part 2 — Choice of dev-only criterion (mechanism)

Compare the four mechanisms named in the task description and recommend one:

1. **Frontmatter flag** in each `SKILL.md` (e.g., `audience: developers` or `distribution: dev-only`). Self-documenting; install-time filter is one `grep "^audience: developers" SKILL.md` per skill dir; new dev-only skills auto-filter as long as authors set the flag; non-breaking for existing skills/whitelists/mirrors.
2. **Naming convention** (e.g., `aitask-dev-*`). Filtering trivial, but renaming `aitask-add-model` → `aitask-dev-add-model` is a breaking change rippling across 5+ whitelist entries × 4 mirrors per skill, plus any user docs/muscle memory. Rejected.
3. **Exclusion list in `install.sh`** (single hardcoded array). Simple but DRIFT-PRONE — the list lives separately from the artifact, and a new dev-only skill is one forgotten edit away from leaking. Acceptable as a *fallback* if frontmatter parsing in bash is judged too brittle.
4. **Separate `dev/` subdirectory** (e.g., `.claude/skills/dev/aitask-add-model/`). Filter trivial (`rm -rf .claude/skills/dev/`), but the directory move is a breaking path change for every mirror, every whitelist entry, and any helper-script reference. High churn; rejected.

**Recommendation: (1) frontmatter flag**, with the field named `audience` and value `developers` (mirroring widely-understood npm/Cargo conventions like `private: true` / `publish = false`). Filter logic added to `install.sh` reads each `SKILL.md`, omits the dev-only ones, and *also* omits the corresponding helper-script files and whitelist entries. The same flag works for `.claude/skills/`, `.agents/skills/`, `.opencode/skills/` (they all use `SKILL.md`); `.opencode/commands/<n>.md` and `.gemini/commands/<n>.toml` files don't have SKILL.md but their inclusion is keyed on the underlying skill — derive from the skill, not the wrapper.

### Part 3 — Survey of current packaging

Notes that will be expanded during write-up, anchored to file:line references:

- `install.sh` has **no opt-in/exclusion mechanism** today beyond `rm -rf "$INSTALL_DIR/seed"` (install.sh:1030). All `.claude/skills/*` ship via `install_skills()` (install.sh:214–233) without filtering.
- `seed/` is deleted at the end of install (per t624 — `aiplans/archived/p624*.md`), so any runtime path that still reads from `$project_dir/seed/...` silently fails on fresh installs. The same risk applies to a filter that *forgets* to mirror seed-side exclusions.
- `t691_1` archived plan establishes the canonical 5-touchpoint whitelist checklist (CLAUDE.md "Adding a New Helper Script" lines 82–96). The dev-only filter has to consume that same matrix and *omit* the helper-script entry from claude/gemini/opencode whitelists at install time.
- Codex exception (CLAUDE.md:94): prompt-only model, no allow entry, so no Codex-side filter is needed.

### Part 4 — Follow-up implementation tasks (created via `aitask_create.sh --batch --commit`)

Two tasks, sized to slot into the next `/aitask-pick` round:

**Follow-up A — "Define `audience` frontmatter field and filter dev-only skills in install.sh"**
- Add `audience` field documentation to CLAUDE.md "Skill / Workflow Authoring Conventions".
- Mark the confirmed dev-only set (`aitask-add-model`, `aitask-audit-wrappers`, `aitask-refresh-code-models`) — including their mirrors under `.agents/skills/`, `.opencode/skills/`, `.opencode/commands/`, `.gemini/commands/` — with `audience: developers`.
- Extend `install.sh` to:
  - Skip skill directories whose `SKILL.md` declares `audience: developers`.
  - Skip the matching helper scripts under `.aitask-scripts/`.
  - Filter the whitelist entries for those helpers from `claude_settings.local.json`, `geminicli_policies/aitasks-whitelist.toml`, and `opencode_config.seed.json` at install time (deriving the helper-script names from the skill's metadata, or from a small companion table).
- Add `--include-dev` opt-in flag for power users.
- Test via the install-flow harness (`bash install.sh --dir /tmp/scratchXY` — per CLAUDE.md "Test the full install flow for setup helpers", lines around the t624/t628 lessons).

**Follow-up B — "Fix pre-existing whitelist gap for `aitask-add-model`"**
- Independent of t697's main thrust but surfaced here. `aitask-add-model` has CLI argsPattern rules in the gemini policies but no permission entry in `.claude/settings.local.json`, `seed/claude_settings.local.json`, `seed/opencode_config.seed.json`. (Run `aitask-audit-wrappers` to confirm the precise gap before scoping.)
- Apply the 5-touchpoint update from CLAUDE.md "Adding a New Helper Script".
- Even though Follow-up A will eventually filter this skill OUT of user installs, framework developers in source still hit the missing-whitelist prompts.

These are submitted via `aitask_create.sh --batch --commit` per the task description's requirement.

## Aside (not a deliverable, just noted in Part 1)

`aitask-add-model`'s whitelist gap (Follow-up B) is independent of the dev-only filter question and could be picked even if t697's recommendation is rejected.

## Verification

- This is an analysis-only task. No build runs, no tests run, no code is modified.
- Verification at Step 8 = the user reads the Final Implementation Notes and confirms the inventory + recommendation + follow-up scope match their intent.
- Confirm the two follow-up tasks were created (`./.aitask-scripts/aitask_ls.sh -v 5` should show them) and committed (last commit message contains the new task IDs).

## Step 9 (Post-Implementation)

Standard archival flow. Plan-file commit is the single output of this task (in addition to the two new follow-up task files committed by `aitask_create.sh`).
