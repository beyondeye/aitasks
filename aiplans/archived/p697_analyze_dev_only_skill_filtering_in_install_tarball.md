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

## Final Implementation Notes

This is the deliverable of t697 — the written analysis. Read this section as the analysis itself; everything above is the planning outline that produced it.

### Part 1 — Inventory of dev-only artifacts

**Method.** Combined exploration of `.claude/skills/`, `.aitask-scripts/`, the four mirror trees (`.agents/skills/`, `.opencode/skills/`, `.opencode/commands/`, `.gemini/commands/`), and the five whitelist surfaces named by the CLAUDE.md "Adding a New Helper Script" checklist (`.claude/settings.local.json`, `seed/claude_settings.local.json`, `.gemini/policies/aitasks-whitelist.toml`, `seed/geminicli_policies/aitasks-whitelist.toml`, `seed/opencode_config.seed.json`). Codex is excluded by the prompt-only convention.

**Inventory table.**

| Skill | Classification | Mirrors (4 trees) | Helper script | Whitelist surfaces today |
|---|---|---|---|---|
| `aitask-add-model` | **Dev-only** (confirmed) | All 4 present | `aitask_add_model.sh` | **0/5** — only `activate_skill` argsPattern in gemini policies (lines 585 / both runtime & seed); no `commandPrefix`/`Bash(...)` entry anywhere |
| `aitask-audit-wrappers` | **Dev-only** (confirmed) | All 4 present | `aitask_audit_wrappers.sh` | **5/5** — landed under t691 |
| `aitask-refresh-code-models` | **Dev-only** (proposed) | All 4 present | `aitask_refresh_code_models.sh` | **0/5** — only `activate_skill` argsPattern in gemini policies (line 669); no `commandPrefix`/`Bash(...)` entry anywhere |
| `aitask-changelog` | **End-user** (proposed) | All 4 present | `aitask_changelog.sh` | **5/5** — already complete |
| `aitask-reviewguide-classify`, `-merge`, `-import` | End-user | All 4 present | `aitask_reviewguide_scan.sh` | n/a (end-user, keep) |
| `aitask-contribute`, `-contribution-review` | End-user | All 4 present | `aitask_contribute.sh`, `aitask_contribution_review.sh`, `aitask_issue_import.sh` | n/a (end-user, keep) |
| All other `aitask-*` skills | End-user | n/a | n/a | n/a |

**Justifications.**

- `aitask-add-model` and `aitask-refresh-code-models` write into `models_*.json` and `DEFAULT_AGENT_STRING` constants that are framework-distribution defaults. End users either inherit those defaults or edit the file directly; nobody outside the framework maintainer's seat will run a workflow whose output is "research the latest models and refresh the framework's seed."
- `aitask-audit-wrappers` audits the cross-agent wrapper trees (`.agents/`, `.opencode/`, `.gemini/`). Those trees only matter as source-of-truth duplications of `.claude/skills/` — they are framework-internal infrastructure, not user-customizable surfaces.
- `aitask-changelog` is **end-user**, not dev-only as initial classification suggested. The helper (`aitask_changelog.sh:20`) drives off `git tag --list 'v*'` and `(tNN)` commit-suffix detection — both project-agnostic. Any project that adopts aitasks and tags releases can use it for its own changelog. Keep in user installs.
- The reviewguide trio and `aitask-contribute*` directly support user workflows (custom review checklists, upstream issue/PR creation against arbitrary repos). Keep in user installs.

**Surprise finding (whitelist gap).** Both `aitask-add-model` and `aitask-refresh-code-models` are missing from all 5 whitelist surfaces today — only the gemini `activate_skill` argsPattern rule exists, which permits the skill to be invoked but does NOT whitelist the underlying helper-script command. Every Claude / OpenCode / Gemini-CLI run hits a permission prompt for these helpers in the source repo. This is independent of the dev-only filter question and surfaces as Follow-up B.

### Part 2 — Choice of dev-only criterion

Compared the four mechanisms named in the task description:

| Mechanism | Pros | Cons | Verdict |
|---|---|---|---|
| **Frontmatter flag** (e.g., `audience: developers` in SKILL.md) | Self-documenting on the artifact; install-time filter is a one-line grep per skill dir; new dev-only skills auto-filter as long as authors set the flag; non-breaking for existing skills/whitelists/mirrors; mirrors npm `private: true` / Cargo `publish = false` conventions. | Authors must remember to set the flag for new dev-only skills (mitigated by a CI lint that flags candidates); install.sh has to parse YAML frontmatter (mitigated — a literal `^audience: developers` grep works in bash). | **Recommended** |
| **Naming convention** (`aitask-dev-*`) | Filtering trivial. | Renaming the four confirmed dev-only skills is breaking across 5 whitelist files × 4 mirror trees × per-skill = ~25–30 entry rewrites; user-visible slash-command names change. | **Rejected** |
| **Hardcoded exclusion list** in install.sh | Simplest. | Drift-prone — a new dev-only skill is one forgotten edit away from leaking; the list lives separately from the artifact. | Acceptable as fallback only |
| **Separate `dev/` subdirectory** | Filter trivial (`rm -rf .claude/skills/dev/`). | Path move breaks every mirror reference, every whitelist entry, every helper-script reference; high churn. | **Rejected** |

**Recommendation: frontmatter flag, field name `audience`, value `developers`.** Filter logic in `install.sh` reads each `SKILL.md`, omits skills whose frontmatter declares `audience: developers`, *and* omits the corresponding helper-script files plus their whitelist entries. The same field works for `.claude/skills/`, `.agents/skills/`, `.opencode/skills/` (all use `SKILL.md`); `.opencode/commands/<n>.md` and `.gemini/commands/<n>.toml` wrappers don't have SKILL.md, but their inclusion is keyed off the underlying skill — derive from the skill, not the wrapper.

**Filter behavior at install time:**

1. For each `.claude/skills/*/SKILL.md`: if `^audience: developers$` matches, exclude the directory and record the helper-script names referenced in its body.
2. Same scan for `.agents/skills/`, `.opencode/skills/`.
3. Exclude `.opencode/commands/<name>.md` and `.gemini/commands/<name>.toml` whose `<name>` matches an excluded skill.
4. Exclude the recorded helper scripts under `.aitask-scripts/`.
5. Strip the corresponding whitelist entries from `claude_settings.local.json`, the gemini `aitasks-whitelist.toml`, and `opencode_config.seed.json` *before* they are written into the user project (so users don't even see allow rules for helpers they don't have).
6. Add `--include-dev` opt-in flag for power users / framework maintainers who want everything.

### Part 3 — Survey of current packaging

Anchored to file:line references confirmed during this analysis:

- `install.sh` has **no opt-in / exclusion mechanism** for skills today. The single broad exclusion is `rm -rf "$INSTALL_DIR/seed"` at install.sh:1030. Skills copy unconditionally via `install_skills()` (install.sh:214–233).
- `seed/` is deleted at end of install (per t624 — `aiplans/archived/p624*.md`), so any runtime path that still reads from `$project_dir/seed/...` silently fails on fresh installs. Per CLAUDE.md "Test the full install flow for setup helpers", the dev-only filter MUST be tested via the full `bash install.sh --dir /tmp/scratchXY` flow, not just by exercising a helper in isolation against a hand-crafted seed.
- The 5-touchpoint whitelist matrix in CLAUDE.md "Adding a New Helper Script" (lines 82–96) is current and matches the runtime files. The dev-only filter has to consume the *same* matrix and *omit* the helper-script entry from the relevant whitelists at install time.
- Codex exception (CLAUDE.md:94): prompt-only, no allow entry exists, so no Codex-side filter is needed.
- `t691_1` archived plan establishes the canonical helper-whitelisting workflow that any new helper passes through; the dev-only filter is the inverse operation (suppress the same entries at distribution time).

### Part 4 — Follow-up implementation tasks

Two follow-up tasks were created via `aitask_create.sh --batch --commit`:
- **t700** — Follow-up A (audience flag + install.sh filter)
- **t701** — Follow-up B (whitelist gap fix for `aitask_add_model.sh` and `aitask_refresh_code_models.sh`)

**Follow-up A — `t700` — "Define `audience` frontmatter field and filter dev-only skills in install.sh"**
- Document the `audience` frontmatter field in CLAUDE.md "Skill / Workflow Authoring Conventions".
- Mark the three confirmed dev-only skills (`aitask-add-model`, `aitask-audit-wrappers`, `aitask-refresh-code-models`) and their mirrors (`.agents/skills/`, `.opencode/skills/`, plus the wrapper files `.opencode/commands/<name>.md` and `.gemini/commands/<name>.toml`) with `audience: developers`.
- Extend `install.sh` to filter dev-only skills, their helper scripts, and their whitelist entries from the user install. Include `--include-dev` opt-in.
- Test via `bash install.sh --dir /tmp/scratchXY` — verify the four filtered files are absent and the three whitelist surfaces have no entries for the filtered helpers.

**Follow-up B — `t701` — "Whitelist `aitask_add_model.sh` and `aitask_refresh_code_models.sh` across the 5 helper-script touchpoints"**
- Independent of t697's main thrust. Both helpers currently lack `commandPrefix` / `Bash(...)` entries in all 5 surfaces; framework developers in source hit prompts on every invocation.
- Apply the 5-touchpoint update from CLAUDE.md "Adding a New Helper Script" (mirror what t691 did for `aitask_audit_wrappers.sh`).
- Even though Follow-up A will eventually filter both skills out of *user* installs, source-repo developers still need the whitelist coverage.

### Part 5 — What does NOT belong in scope

Per the task description:
- Anything that needs `aitask-audit-wrappers` to function (it is itself dev-only).
- Test files in `tests/` — already absent from the user install pipeline.
- The `aireviewguides/` content — orthogonal and already handled by `install_seed_reviewguides()`.

---

- **Actual work done:** Inventoried the four candidate dev-only artifacts, confirmed three (`aitask-add-model`, `aitask-audit-wrappers`, `aitask-refresh-code-models`) and rejected one (`aitask-changelog` is end-user). Surveyed `install.sh`, the seed pipeline, and the 5-touchpoint whitelist matrix. Recommended the `audience: developers` frontmatter flag mechanism with explicit trade-offs vs. the three alternatives. Created two follow-up tasks via `aitask_create.sh --batch --commit`. No `install.sh` / skill / whitelist edits made by t697 itself.
- **Deviations from plan:** None of substance. The plan outline anticipated "Status TBD during write-up" for `aitask-refresh-code-models`'s whitelist — write-up confirmed it is in the same 0/5 state as `aitask-add-model`, so Follow-up B was widened to cover both helpers (plan originally listed only `aitask-add-model`).
- **Issues encountered:** Initial explore-agent classification of `aitask-changelog` as dev-only was wrong (the helper is project-agnostic). Caught by reading `aitask_changelog.sh` directly and noting the `git tag --list 'v*'` driver. Re-classified to end-user before plan finalization.
- **Key decisions:**
  - `audience: developers` (frontmatter) over the three alternatives; rationale in Part 2.
  - Recommend filter in `install.sh` (single source-of-truth tarball) rather than a build-time tarball-shaping step, with `--include-dev` opt-in.
  - Surface the pre-existing whitelist gap as a separate follow-up (B) rather than rolling it into A — Follow-up B is useful to source-repo developers even if Follow-up A is rejected.
- **Upstream defects identified:**
  - `seed/geminicli_policies/aitasks-whitelist.toml` and `.gemini/policies/aitasks-whitelist.toml` — both contain `activate_skill` argsPattern rules for `aitask-add-model` (line 585) and `aitask-refresh-code-models` (line 669) but no matching `commandPrefix` rules for the underlying helper scripts. Same gap mirrored in `.claude/settings.local.json`, `seed/claude_settings.local.json`, `seed/opencode_config.seed.json`. This is the pre-existing whitelist gap that Follow-up B addresses; surfaced here per the upstream-defect-followup convention, separate from t697's analysis-only deliverable.
