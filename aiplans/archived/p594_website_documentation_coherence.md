---
Task: t594_website_documentation_coherence.md
Worktree: (none — work on current branch)
Branch: main
Base branch: main
---

# t594 — Website documentation coherence sweep

## Context

The Hugo/Docsy site under `website/content/docs/` has grown organically and now spans ~95 user-facing pages across 7 sections (Installation, Commands, Concepts, Skills, TUIs, Workflows, Development) plus 3 root pages (Overview, Getting Started, doc root `_index`).

This planning phase ran **four** parallel Explore passes:
1. **Structural inventory** — page-by-page map across sections.
2. **Docs-vs-docs quality sweep** — repetitions, verbosity, contradictions, navigation gaps.
3. **TUI source-vs-docs verification** — cross-check doc claims against the Python TUI code (`.aitask-scripts/board/`, `.aitask-scripts/monitor/`, `.aitask-scripts/settings/`, `.aitask-scripts/lib/tui_switcher.py`).
4. **Skills/commands source-vs-docs verification** — cross-check against `.claude/skills/<name>/SKILL.md`, `.aitask-scripts/aitask_*.sh` flag parsers, `aitasks/metadata/profiles/*.yaml`, `aitasks/metadata/codeagent_config.json`, and `.claude/skills/task-workflow/profiles.md`.

The verification passes revealed concrete **factual drift** — cases where the docs claim behavior the code contradicts. These are now first-class scope items for each child task below.

### Concrete drift items found during planning (with citations)

**TUIs (in-scope for t594_1):**
- ~~`tuis/board/reference.md:51` claims `Ctrl+Backslash` opens a command palette — no such binding exists.~~ **Corrected during t594_1 verify pass:** `.aitask-scripts/board/aitask_board.py:3218` registers `COMMANDS = App.COMMANDS | {KanbanCommandProvider}`, and Textual's `App` class provides the `Ctrl+Backslash` command-palette binding by default (not in the subclass `BINDINGS`). The doc is correct; keep the entry.
- Settings `t` key opens the Tmux tab (`.aitask-scripts/settings/settings_app.py:346-352`) — **absent from `tuis/settings/reference.md`**.
- Board `p` (pick_task, line 3246) and `b` (brainstorm_task, line 3248) exist but are **not in the `tuis/board/reference.md` keybinding table**.
- Monitor undocumented keys: `t` scroll_preview_tail (line 442), `R` restart_task (line 445), `b` toggle_scrollbar (line 441), `L` open_log (line 448) in `.aitask-scripts/monitor/monitor_app.py` — **none appear in `tuis/monitor/reference.md`**.
- `tuis/_index.md:27` claims the TUI switcher lists Minimonitor + Brainstorm — but `.aitask-scripts/lib/tui_switcher.py:59-65` `KNOWN_TUIS = [board, monitor, codebrowser, settings, diffviewer]` (Minimonitor is not switchable; Brainstorm appears only via dynamic session discovery).
- `tuis/monitor/reference.md:94-102` shows default `capture_lines: 30`; actual `aitasks/metadata/project_config.yaml:11` is `200`.

**Commands (in-scope for t594_6):**
- `commands/task-management.md` documents `ait create` and `ait update` but is missing these flags that the scripts actually accept:
  - `ait create`: `--verifies` (`.aitask-scripts/aitask_create.sh:25`).
  - `ait update`: `--verifies` / `--add-verifies` / `--remove-verifies`, `--file-ref` / `--remove-file-ref`, `--pull-request`, `--contributor` / `--contributor-email`, `--folded-tasks` / `--folded-into`, `--implemented-with`, `--boardcol` / `--boardidx` (`.aitask-scripts/aitask_update.sh:52-82`).
- `commands/codeagent.md:53-59` default model alignment is currently correct vs `aitask_codeagent.sh:27` and `codeagent_config.json` — verify this stays aligned (it drifts fast).

**Skills / profiles (in-scope for t594_4):**
- `skills/aitask-pick/execution-profiles.md` field table is missing `plan_verification_required`, `plan_verification_stale_after_hours` — both present in `aitasks/metadata/profiles/fast.yaml:8-9` and documented in `.claude/skills/task-workflow/profiles.md:31-32`.
- `skills/aitask-pick/execution-profiles.md` does not reference the remote-only fields (`force_unlock_stale`, `done_task_action`, `orphan_parent_action`, `complexity_action`, `review_action`, `issue_action`, `abort_plan_action`, `abort_revert_status`) even though they are listed in `skills/aitask-pickrem.md:79-104`.
- **Contradiction:** `skills/aitask-pick/_index.md:24` and `execution-profiles.md:14` describe the shipped `fast` profile as "stops after plan approval" — but `aitasks/metadata/profiles/fast.yaml:10` has `post_plan_action: ask`, so the profile **asks** rather than auto-stopping. Either the YAML or the docs are wrong; planning here confirmed the behavior matches the YAML (the planning session itself was prompted).
- `skills/aitask-explore.md` does not document the `--profile <name>` argument present in `.claude/skills/aitask-explore/SKILL.md:6-12`.

**Development / frontmatter (in-scope for t594_6):**
- `development/task-format.md:29-49` lists ~13 frontmatter fields but is missing `verifies` (added with t583_2, commit `b17f8c54`).

**Docs-vs-docs repetitions (in-scope for t594_2):**
- TUI switcher `j` key explained in 4+ pages: `getting-started.md:41`, `tuis/_index.md:27`, `installation/terminal-setup.md:38`, `workflows/tmux-ide.md:33`.
- Install curl command + `ait setup` repeated verbatim: `installation/_index.md:8-26`, `getting-started.md:10-26`, `installation/windows-wsl.md:40-52`.
- "Run from project root" warning in: `installation/_index.md:12`, `getting-started.md:20`, `skills/_index.md:14`.
- Task file format in `concepts/tasks.md:8-10` and `development/task-format.md:7-10`.
- `/aitask-pick` / `/aitask-pickrem` / `/aitask-pickweb` step-by-step workflows 90%+ overlap; `aitask-pickweb.md` has the comparison table twice.
- Narrative contradiction around profile optional-vs-required in `aitask-pickrem.md`.

**Verbose sections (in-scope for the per-section children):**
- `tuis/board/how-to.md` — 438 lines, 8 repetitive "1. 2. 3." micro-sections.
- `commands/codeagent.md` — 280 lines, "agent string" redefined 4 times.
- `skills/aitask-pickweb.md` — comparison table duplicated within one page.

**Navigation gaps:**
- No "Next:" pointers anywhere — users land in a tree with no forward flow.
- `installation/_index.md` ends without bridging into `getting-started.md`.
- `concepts/_index.md` lists concepts but doesn't explain when/why to read them.
- `skills/_index.md` lists 27 skills without a "start here" path.
- `concepts/tasks.md:22-27` references `development/task-format.md` without saying which to read first.

### User scoping decisions

- **Split:** Hybrid — one systemic-cleanup child + per-section children.
- **Dedup stance:** Conservative — keep repetitions where they aid the reader; ensure wording/values match. Do not aggressively replace repeated content with links.
- **Edit scope (in-bounds):** (a) content rewrites to shorten verbose prose; (b) factual fixes for contradictions/drift/broken references; (c) new bridging content (Next/Prev pointers, section intros). **Structural edits are out of scope** — no page splits/merges, no heading-hierarchy rewrites.
- **First child priority:** TUIs section — acts as the pilot.
- **Source-vs-docs verification is mandatory** for every child task. Each child must treat the relevant source code (TUI Python files, SKILL.md files, script flag parsers, profile YAMLs) as the authority, not adjacent doc pages.

## Goal

A doc site that reads coherently end-to-end: repeated concepts say the same thing, verbose sections are tightened, factual drift vs source is fixed, and each section has a forward-reading flow. No page restructuring.

## Approach — 6 child tasks

`t594_1` (TUIs) establishes the sweep pattern. `t594_2` (systemic consistency) finalizes canonical wording so `t594_4/5/6` don't re-fix the same lines. `t594_3` (onboarding flow) is independent.

| # | Title | Pages | Depends on |
|---|---|---|---|
| t594_1 | TUIs section sweep (pilot) | `tuis/` — 15 pages | — |
| t594_2 | Systemic consistency sweep | cross-cuts ~20 pages | — |
| t594_3 | Onboarding flow sweep | `_index`, `overview`, `getting-started`, `installation/` (5), `concepts/_index`, `skills/_index` — ~10 | — |
| t594_4 | Skills section sweep | `skills/` — 27 | t594_2 |
| t594_5 | Workflows section sweep | `workflows/` — 21 | t594_2 |
| t594_6 | Concepts + Commands + Development sweep | `concepts/` (14), `commands/` (10), `development/` (3) — 27 | t594_2 |

### Per-child scope

#### t594_1 — TUIs section sweep (pilot)

**Pages:** all 15 under `website/content/docs/tuis/` — Board, Monitor, Minimonitor, Codebrowser, Settings with their `_index`/how-to/reference subpages.

**Authoritative sources:**
- Board: `.aitask-scripts/board/aitask_board.py` (`BINDINGS`, action methods)
- Monitor: `.aitask-scripts/monitor/monitor_app.py` (`BINDINGS`, lines ~432-449)
- Minimonitor: source file under `.aitask-scripts/` (resolve via glob)
- Codebrowser: `.aitask-scripts/board/aitask_codebrowser.py` or similar
- Settings: `.aitask-scripts/settings/settings_app.py` (tab bindings lines 346-353, 1504-1516)
- Switcher: `.aitask-scripts/lib/tui_switcher.py:59-65` (`KNOWN_TUIS`)
- Config defaults: `aitasks/metadata/project_config.yaml`

**Required fixes (from verification):**
- Remove the fabricated `Ctrl+Backslash` command-palette claim from `tuis/board/reference.md:51`.
- Add the Settings `t` (Tmux tab) shortcut to `tuis/settings/reference.md`.
- Add Board `p` (pick_task) and `b` (brainstorm_task) to `tuis/board/reference.md` keybinding table.
- Add Monitor `t` / `R` / `b` / `L` keys to `tuis/monitor/reference.md`.
- Fix `tuis/_index.md:27` to reflect what the switcher actually lists at startup vs which TUIs appear via auto-spawn / dynamic discovery. Per `CLAUDE.md`, diffviewer stays switchable but is not documented on the site — keep that exclusion explicit in the docs text.
- Align the default `capture_lines` value in `tuis/monitor/reference.md:94-102` with `project_config.yaml:11` (or explain schema-default vs current-config).

**Coherence fixes (no structural edits):**
- Collapse the 8 repetitive "1. 2. 3." micro-how-tos in `tuis/board/how-to.md` (438 lines) into a keybinding reference table + one narrative per operation. No page split.
- Add "Next:" footers: each TUI flows `_index → how-to → reference → next TUI's _index`.
- Polish the `tuis/_index.md` intro to describe each of the 5 TUIs in one sentence.

**Out-of-bounds:** merging how-to + reference, reshaping Settings to match other TUIs, splitting pages.

**Verification:**
- `cd website && hugo build --gc --minify` succeeds without warnings.
- Manually run each TUI and confirm every documented keybinding actually fires.
- `tuis/board/how-to.md` line count reduced by ≥30% (target ≤ 310 lines).
- Every "Next:" link resolves.

#### t594_2 — Systemic consistency sweep (cross-cutting)

**Scope:** fix the 5 cross-cutting wording inconsistencies and the one narrative contradiction, without removing any repeated content (conservative dedup).

**Target passages:**
- TUI switcher `j`: `getting-started.md:41`, `tuis/_index.md:27`, `installation/terminal-setup.md:38`, `workflows/tmux-ide.md:33`, plus any other `grep -rn "TUI switcher" website/content` hits.
- Install curl command: `installation/_index.md:8-26`, `getting-started.md:10-26`, `installation/windows-wsl.md:40-52`. **Source of truth:** the actual `install.sh` in the repo root — verify the exact curl URL and any flags.
- "Run from project root" warning: `installation/_index.md:12`, `getting-started.md:20`, `skills/_index.md:14` — unify to one sentence shape.
- Task file format sentence in `concepts/tasks.md:8-10` vs `development/task-format.md:7-10` — keep both; ensure they agree on location, naming, frontmatter language and explicitly designate `development/task-format.md` as the full-schema authority.
- Pick variants: `skills/aitask-pick/_index.md`, `skills/aitask-pickrem.md`, `skills/aitask-pickweb.md` — unify step names; remove the duplicate comparison table inside `aitask-pickweb.md` (one of the two identical tables at lines 26-48 and 38-46).
- Fix the `aitask-pickrem.md` prose contradiction so narrative matches the comparison table ("Required, auto-selected").
- **Fast profile behavior contradiction:** either update `skills/aitask-pick/_index.md:24` and `execution-profiles.md:14` to say "pauses for confirmation after plan approval" (matches `fast.yaml: post_plan_action: ask`), or change `fast.yaml` to `post_plan_action: start_implementation`. **Default choice:** update the docs (the YAML's observed behavior is what this planning session just experienced). If the user prefers the YAML change, flip the fix direction.

**Verification:**
- `grep -rn "TUI switcher" website/content/docs/` hits show one canonical phrasing.
- `diff` the curl command across the 3 install pages — must match verbatim.
- Invoke `/aitask-pick --profile fast` and confirm the doc's description matches observed behavior.

#### t594_3 — Onboarding flow sweep

**Pages:** `docs/_index.md`, `overview.md`, `getting-started.md`, `installation/{_index,windows-wsl,terminal-setup,known-issues,git-remotes}.md`, `concepts/_index.md`, `skills/_index.md`.

**Fixes:**
- Add "Next:" footers along `_index → overview → getting-started → installation → workflows/tmux-ide`.
- Section intro for `concepts/_index.md` — which concepts are required reading, which are reference.
- "Start here" marker in `skills/_index.md` pointing to `/aitask-pick`.
- Verify install commands against `install.sh`, first-run examples against `aitask_setup.sh` behavior.
- Tighten overview/getting-started prose where redundant with Installation, but preserve self-contained completeness (conservative dedup).

**Verification:** walk the path from `_index.md` forward — every Next link resolves; Hugo build passes.

#### t594_4 — Skills section sweep

**Pages:** all 27 under `website/content/docs/skills/`.

**Authoritative sources:**
- Each skill's `SKILL.md` in `.claude/skills/<name>/`
- `.claude/skills/task-workflow/*.md` (planning.md, profiles.md, execution-profile-selection.md, etc.)
- `aitasks/metadata/profiles/*.yaml`
- `aitasks/metadata/codeagent_config.json` and `.aitask-scripts/aitask_codeagent.sh` for default-model claims

**Required fixes (from verification):**
- Add `plan_verification_required` and `plan_verification_stale_after_hours` to the `skills/aitask-pick/execution-profiles.md` field table.
- Add the remote-only profile fields (`force_unlock_stale`, `done_task_action`, `orphan_parent_action`, `complexity_action`, `review_action`, `issue_action`, `abort_plan_action`, `abort_revert_status`) with a pointer to `/aitask-pickrem` for details.
- Document the `--profile <name>` argument on `skills/aitask-explore.md` (present in `.claude/skills/aitask-explore/SKILL.md:6-12`).
- Diff each skill page's step list against its `SKILL.md` — focus on `/aitask-pick`, `/aitask-pickrem`, `/aitask-pickweb`, `/aitask-explore`, `/aitask-qa`, `/aitask-review`, `/aitask-fold`, `/aitask-wrap`, `/aitask-revert`.
- Fix any default-model drift vs `codeagent_config.json`.
- Add "Related skills" cross-links where the skills naturally chain (e.g., explore → create → pick).

**Verification:**
- For each verified skill, the website step list names match the `SKILL.md` step structure (no invented or missing major steps).
- Every profile field documented on the website exists in at least one shipped profile YAML or in `profiles.md`.
- Hugo build passes.

#### t594_5 — Workflows section sweep

**Pages:** all 21 under `website/content/docs/workflows/`.

**Fixes:**
- Identify workflow pages that duplicate a Skill page's content (e.g., `workflows/qa-testing.md` ↔ `skills/aitask-qa.md`); keep both but add bi-directional links and unify step names.
- Write a category intro for `workflows/_index.md` (Daily / Decomposition / Patterns / Integrations / Advanced) — without reassigning weights.
- Trim repetitions of "how to launch `ait ide`" across `tmux-ide.md`, `parallel-development.md`, `capture-ideas.md` — keep self-contained but canonicalize wording.
- Add "Next:" footers in the suggested reading path.
- Verify command sequences against the actual scripts (e.g., the `ait ide` flow against `aitask_ide.sh` if present).

**Verification:** Hugo build passes; open the 5 top workflow pages by weight and confirm the flow feels coherent.

#### t594_6 — Concepts + Commands + Development sweep

**Pages:** `concepts/` (14), `commands/` (10), `development/` (3).

**Required fixes (from verification):**
- **`development/task-format.md`:** add the `verifies` frontmatter field (missing from lines 29-49; source of truth is `aitask_create.sh` / `aitask_update.sh` flag lists and the `CLAUDE.md` frontmatter table).
- **`commands/task-management.md`:** add missing `ait update` flags (`--verifies`, `--add-verifies`, `--remove-verifies`, `--file-ref`, `--remove-file-ref`, `--pull-request`, `--contributor`, `--contributor-email`, `--folded-tasks`, `--folded-into`, `--implemented-with`, `--boardcol`, `--boardidx`). Add `--verifies` to `ait create` documentation. Source: `.aitask-scripts/aitask_create.sh` and `aitask_update.sh` flag parsers.
- **`commands/codeagent.md`:** tighten by defining "agent string" once upfront; keep the "pick: claudecode/opus4_7_1m" default and verify against `aitask_codeagent.sh:27` and `codeagent_config.json`.
- **Concepts:** align `concepts/tasks.md` overview vs `development/task-format.md` schema — explicit cross-link. Verify the 14 concept pages (locks, git branching, agent attribution, etc.) against current source (`.aitask-scripts/aitask_lock.sh`, lock diag scripts, etc.).
- **Development:** confirm `task-format.md` against `CLAUDE.md`'s authoritative table; confirm `review-guide-format.md` against actual `aireviewguides/` files.
- Add "Next:" footers within each section.

**Verification:**
- `diff <(grep -E 'BATCH_|--[a-z-]+' .aitask-scripts/aitask_create.sh) <(...task-management.md...)` — every script flag has a doc mention.
- Same for `aitask_update.sh`.
- `development/task-format.md` frontmatter list matches the `CLAUDE.md` schema table.
- Hugo build passes.

### Post-planning workflow (after this plan is approved)

1. Create each child task file:
   ```bash
   .aitask-scripts/aitask_create.sh --batch --parent 594 --name <name> \
     --priority <p> --effort <e> --issue-type documentation --depends <if any>
   ```
   See `.claude/skills/task-workflow/task-creation-batch.md` for exact flags.
2. Revert parent `t594` status → `Ready` and clear `assigned_to`.
3. Release parent lock: `.aitask-scripts/aitask_lock.sh --unlock 594`.
4. Write each child plan to `aiplans/p594/p594_<n>_<name>.md` using the per-child scope above as the seed. Each child plan must include the specific drift citations from this parent plan so the implementer does not need to re-discover them.
5. Commit: `./ait git add aitasks/t594/ aiplans/p594/ && ./ait git commit -m "ait: Add t594 children and implementation plans"`.
6. Ask the user whether to start the first child (`/aitask-pick 594_1`) or stop.

### Child priorities and efforts

| Child | Priority | Effort | Rationale |
|---|---|---|---|
| t594_1 | high | medium | Pilot, 15 pages, concrete drift list already assembled |
| t594_2 | high | low | Focused wording alignment across ~20 pages |
| t594_3 | high | low | Entry path — highest impact per page for new users |
| t594_4 | medium | high | 27 pages, must diff each against SKILL.md |
| t594_5 | medium | high | 21 pages, moderate dedup + source verification |
| t594_6 | medium | medium | 27 pages but smaller per-page changes |

### Step 9 (Post-Implementation) reference

Each child follows the standard Step 9 archival. No worktree (`create_worktree: false`), so merge is implicit. `verify_build` per `project_config.yaml` is null, so the `hugo build` check is the child's own verification responsibility (not framework-driven). Archive via `./.aitask-scripts/aitask_archive.sh 594_<n>`. The parent `t594` auto-archives when the last child completes.

## Out-of-scope

- No page splitting, merging, or heading-hierarchy rewrites.
- No aggressive deduplication / replace-with-link refactors.
- No changes to `hugo.toml`, Docsy theme, weight values, or navigation structure.
- No new TUI/skill/command documentation — only coherence + factual-drift work on existing pages.
- No changes to source code (TUI Python, scripts, SKILL.md files, profile YAMLs) — **unless** the planning-surfaced contradictions require it. Currently the only candidate is the `fast.yaml: post_plan_action` question; default resolution is to change the docs, not the YAML. Flag to user if a YAML change feels preferable.
