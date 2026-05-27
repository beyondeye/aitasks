---
Task: t812_3_remove_geminicli_setup_install_release_tests.md
Parent Task: aitasks/t812_remove_gemini_support.md
Sibling Tasks: aitasks/t812/t812_1_*.md, aitasks/t812/t812_2_*.md, aitasks/t812/t812_4_*.md, aitasks/t812/t812_5_*.md
Archived Sibling Plans: aiplans/archived/p812/p812_1_*.md, aiplans/archived/p812/p812_2_*.md
Worktree: (current branch — fast profile)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-27 17:24
---

# Plan: Remove geminicli from setup/install/release + tests (t812_3)

## Context

Third child of t812. Strips geminicli from the **setup / install /
release pipeline and tests**. After t812_1 (agent identity) and t812_2
(skill rendering & templating) landed, the remaining geminicli footprint
lives in the install/setup orchestration layer and the release pipeline.
The codex equivalent functions (`setup_codex_cli`, `install_codex_*`)
are the nearest analogue — note codex's lighter footprint (no policy
install) because codex (like agy) uses global sandboxing.

## Plan-verification findings (2026-05-27, claudecode/opus4_7_1m)

Plan claims verified against `main`. All line numbers in
`aitask_setup.sh` and `install.sh` match exactly. Two drifts:

| Plan claim | Reality |
|------------|---------|
| `aitask_setup.sh` orchestration calls at lines 976, 2070, 2266 | Line **976** is a docstring comment (`# agent_type: claude, codex, geminicli, opencode …`); line **2070** is a comment (`# Copy shared helper docs (codex + gemini)`) with the actual `geminicli_*` copy-loop tuple on line **2071**; line **2266**/2268 is the real `_is_agent_installed gemini → setup_gemini_cli` orchestration. **All three regions still need cleanup**, just labeled correctly. |
| Plan §"Files to delete" lists `tests/test_gemini_setup.sh` | File **already deleted** in t812_2 (commit 245240bd). Step 5 is a no-op — skip. |

Additional in-function call sites (cleaned automatically when parent
functions are deleted, listed here for completeness):
- `merge_gemini_policies` invocations at lines **1618**, **1822**.
- `install_gemini_global_policy` invocation at line **1851**.
- `merge_gemini_settings` invocation at line **1866**.

`release.yml` references confirmed at lines **56–57** (doc copy loop)
and **85–120** (build/package gemini skills, commands, policies,
settings). All in scope.

All four `seed/` items exist as the plan claims. No out-of-scope
references were discovered.

## Key files to modify

### `.aitask-scripts/aitask_setup.sh` — delete

- `setup_gemini_cli()` — line **1716** region (multi-line function body
  through ~line 1880).
- `merge_gemini_policies()` — line **1525** region.
- `merge_gemini_settings()` — line **1623** region.
- `install_gemini_global_policy()` — line **1602** region.
- `_is_agent_installed()` gemini case branch — line **103**.
- The `.gemini/` gitignore-skip entry — line **2656**.
- **Line 976 docstring comment** — drop `geminicli` from the
  `agent_type: claude, codex, geminicli, opencode` list.
- **Lines 2070–2071 copy loop** — drop `geminicli_tool_mapping.md` and
  `geminicli_planmode_prereqs.md` from the doc-copy tuple; rewrite the
  preceding comment from "Copy shared helper docs (codex + gemini)" to
  "Copy shared helper docs (codex)".
- **Lines 2266–2268 orchestration** — delete the
  `_is_agent_installed gemini → setup_gemini_cli` invocation block.

In-function call sites (lines 1618, 1822, 1851, 1866) disappear with
their containing functions.

### `install.sh` — delete

- `install_gemini_staging()` — line **563** region.
- `install_seed_gemini_config()` — line **623** region.
- The `.gemini/` gitignore-skip entry — line **776**.
- Orchestration calls — lines **1051** (`install_gemini_staging`) and
  **1054** (`install_seed_gemini_config`).
- **Line 481–482 copy loop** — drop `geminicli_tool_mapping.md` and
  `geminicli_planmode_prereqs.md` from the doc-copy tuple; rewrite the
  preceding comment to drop "+ gemini".

### `.github/workflows/release.yml`

- Lines **56–57** — strip geminicli docs from the shared helper-docs
  copy loop and its comment.
- Lines **85–120** — remove the entire "Build gemini commands,
  policies, and helper docs" step plus the four staging-artifact
  references (`gemini_skills/`, `gemini_commands/`, `gemini_policies/`,
  `gemini_settings.json`) wherever the release artifact is assembled.

## Files / directories to delete

- `seed/geminicli_policies/` (entire dir).
- `seed/geminicli_settings.seed.json`.
- `seed/geminicli_instructions.seed.md`.
- `seed/models_geminicli.json`.
- ~~`tests/test_gemini_setup.sh`~~ — **already removed in t812_2; skip.**

## `aidocs/adding_a_new_codeagent.md` updates (in scope)

t812_1 (agent identity) added §2–§11; t812_2 (skill rendering) added
§12–§16 and cleaned §1's gemini examples. t812_3 owns the
**setup/install/release pipeline layer** and must extend the doc
correspondingly — both as **direct cleanup** of any remaining gemini
mentions and as **inverse-direction extension** (document the new
touchpoints t812_3 discovers so t814 has a complete checklist).

The doc currently ends at §16 (Shared helper docs) and the "More
sections to be added" stub at lines 34–35 explicitly calls out
"setup/install" as TODO. Add §17–§20 covering this layer.

### Direct cleanup (lines confirmed by grep on `aidocs/adding_a_new_codeagent.md`)

Strip any residual gemini/geminicli mentions tied to the
setup/install/release layer. After t812_2 the doc no longer references
gemini in §1–§16 directly (those were cleaned), so the direct-cleanup
footprint here is small — primarily the "More sections" stub and any
new examples about setup/install/release that this child writes from
scratch (use `codex` as the worked example, not `gemini`).

- **Line 4** intro: drop `Gemini CLI` from the parenthetical
  "(Claude Code, Codex CLI, Gemini CLI, OpenCode, agy, …)" → "(Claude
  Code, Codex CLI, OpenCode, agy, …)".
- **Lines 34–35** "More sections to be added" stub: rewrite to reflect
  that §17–§20 now cover setup/install/release, leaving only
  "contributor docs, website docs" as TODO (or remove the stub entirely
  if all known layers are now covered).

### New §17 — Setup CLI orchestration (`aitask_setup.sh`)

Document the per-agent functions and orchestration sites in
`.aitask-scripts/aitask_setup.sh`. Use **`setup_codex_cli`** as the
canonical worked example (codex has the lighter footprint analogous to
what agy will need: no policy install, no global merge).

Cover:

- **`setup_<agent>_cli()`** — main per-agent installer. Resolves staging
  directories under `aitasks/metadata/<agent>_*`, copies them into
  `.<agent>/` runtime dirs (skills, commands, settings), writes the
  assembled Layer-2 instructions, and (for agents with policy support)
  invokes `merge_<agent>_policies` / `install_<agent>_global_policy` /
  `merge_<agent>_settings`. Agents without policy support (codex, agy)
  skip those helpers.
- **`merge_<agent>_policies()` / `merge_<agent>_settings()` /
  `install_<agent>_global_policy()`** — optional policy helpers. Only
  needed for agents that support per-agent policy files (Gemini CLI
  did; Codex CLI does not; agy will not). Document the convention so
  future authors know which helpers to omit.
- **`_is_agent_installed()` case branch** (around line 100) — must add
  a `<agent>)` clause that runs the `command -v <cli>` check.
- **Orchestration block** (currently around line 2266 for gemini) — at
  the end of the per-agent setup loop, add `if _is_agent_installed
  <agent>; then setup_<agent>_cli; fi`.
- **Doc copy-loop tuple** (currently around line 2070) — if the agent
  ships shared helper docs in `.agents/skills/<agent>_*.md`, add them
  to the `for doc in ...; do` tuple here. This is the **same tuple
  that appears in `install.sh:482` and `release.yml:57`** — see §21.
- **`.<agent>/` gitignore-skip entry** (currently line 2656 for
  gemini) — add `.<agent>/` to the gitignore-skip list so the per-agent
  runtime dir is preserved by setup's gitignore management.
- **Agent_type docstring comment** (currently line 976) — add the new
  agent to the `agent_type: claude, codex, ...` enumerated comment so
  the docstring stays in sync.

### New §18 — Install staging (`install.sh`)

Document the per-agent staging dance in the top-level `install.sh`.
This script runs **before** `aitask_setup.sh` and is responsible for
moving downloaded release artifacts from the install directory into
`aitasks/metadata/<agent>_*` staging slots. Use `install_codex_*` as
the worked analogue.

Cover:

- **`install_<agent>_staging()`** (currently `install_gemini_staging`
  at line 563) — pulls `<agent>_skills/`, `<agent>_commands/`,
  `<agent>_policies/`, and `<agent>_settings.json` from
  `$INSTALL_DIR/` into `aitasks/metadata/<agent>_*` staging dirs.
  Agents without policies/settings skip the corresponding clauses.
- **`install_seed_<agent>_config()`** (currently
  `install_seed_gemini_config` at line 623) — copies bundled seed
  files (`seed/<agent>_instructions.seed.md`,
  `seed/<agent>_policies/`, `seed/<agent>_settings.seed.json`) into
  the user's `aitasks/metadata/` so first-run setup has defaults.
- **Orchestration calls** (currently lines 1051, 1054) — add
  `install_<agent>_staging` and `install_seed_<agent>_config`
  invocations to the main install flow.
- **`.<agent>/` gitignore-skip entry** (currently line 776) — mirror
  of §17's `aitask_setup.sh` entry; both files manage the same
  gitignore-skip list independently and must stay in lockstep.
- **Helper-doc copy loop** (currently line 482) — see §21.

### New §19 — Release packaging (`.github/workflows/release.yml`)

Document the release-pipeline build steps that bundle per-agent
artifacts into the install tarball. Use the codex step (if present;
otherwise show the gemini step as a template before it is removed) as
the worked example.

Cover:

- **"Build `<agent>` commands, policies, and helper docs" step**
  (currently lines 85–120 for gemini) — copies `.<agent>/commands/`,
  selected `.<agent>/skills/<agent>_*.md` helper docs,
  `.<agent>/policies/`, and `.<agent>/settings.json` into staging dirs
  (`<agent>_commands/`, `<agent>_skills/`, etc.) that `install.sh` will
  later consume.
- **Artifact-bundling references** — wherever the workflow assembles
  the release tarball (e.g., `tar` calls that list staging dirs), the
  per-agent staging dirs must be enumerated.
- **Helper-doc copy loop** (currently lines 56–57) — see §21.

### New §20 — Seed assets (`seed/<agent>_*`)

Document the per-agent seed assets that ship in the framework repo
under `seed/` and are copied into user projects during install.

Cover:

- **`seed/<agent>_instructions.seed.md`** — the Layer-2 system prompt
  / instructions that `setup_<agent>_cli` assembles and writes to the
  user's `.<agent>/` directory.
- **`seed/models_<agent>.json`** — the per-agent model registry seed
  consumed by the stats/picker code (also referenced in §3, §4, §5).
- **`seed/<agent>_settings.seed.json`** *(optional)* — settings
  defaults; only for agents with per-agent settings (Gemini CLI had
  one; Codex CLI does not).
- **`seed/<agent>_policies/`** *(optional)* — policy seed directory;
  only for agents with policy support (same scoping as §17's
  `merge_<agent>_policies`).

### New §21 — Helper-doc copy-loop fan-out (3 sites in lockstep)

The shared helper docs in `.agents/skills/<agent>_tool_mapping.md`
and `.agents/skills/<agent>_planmode_prereqs.md` are copied to release
staging by **three independent copy loops** that all carry the same
tuple. Adding a new agent that ships helper docs requires editing all
three; removing one requires the inverse.

- `.aitask-scripts/aitask_setup.sh` ~ line 2071.
- `install.sh` ~ line 482.
- `.github/workflows/release.yml` ~ line 57.

Each loop has a preceding comment ("Copy shared helper docs (codex +
gemini)") that must be kept in sync with the tuple.

### New §22 — `.gemini/` (per-agent runtime dir) gitignore-skip

If an agent has a top-level runtime directory (e.g., `.gemini/`,
`.claude/`) that should survive aitasks-managed gitignore cleanup,
two scripts maintain parallel gitignore-skip lists and must be
updated in lockstep:

- `.aitask-scripts/aitask_setup.sh` ~ line 2656.
- `install.sh` ~ line 776.

(Agents that share `.agents/skills/` via the shared-root mechanism
in §1 typically do **not** need their own dotdir here.)

### Layout

Insert §17–§22 after §16 (Shared helper docs). Update the Index at
the top of the doc to include the new sections. Update or remove the
"More sections to be added" stub at lines 34–35.

## Step-by-step

1. **`aitask_setup.sh`** — delete each `*_gemini_*` function and the
   three non-function gemini sites (line 103 case, line 976 comment,
   line 2070–2071 copy loop, line 2266–2268 orchestration, line 2656
   gitignore-skip). Run `shellcheck` after each chunk to catch orphans.
2. **`install.sh`** — delete the two staging/install functions, their
   orchestration calls (1051, 1054), the gitignore-skip (776), and the
   doc-copy entries on line 482 (with comment fix on 481).
3. **`.github/workflows/release.yml`** — strip lines 56–57 (helper-doc
   copy), 85–120 (gemini build step), and any downstream artifact
   references. Confirm YAML still parses:
   ```bash
   python3 -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))"
   ```
4. Delete the seed directory and the three seed files via `./ait git rm`.
5. Final grep check:
   ```bash
   grep -n 'gemini\|geminicli' \
     .aitask-scripts/aitask_setup.sh \
     install.sh \
     .github/workflows/release.yml
   ls seed/ | grep -i gemini  # expect empty
   ```
6. **Update `aidocs/adding_a_new_codeagent.md`** — apply the direct
   cleanup (intro line 4 + lines 34–35 stub) and add §17–§22 covering
   the setup/install/release/seed layer, the helper-doc copy-loop
   fan-out, and the dotdir gitignore-skip pair. Update the Index.

## Verification

1. `shellcheck .aitask-scripts/aitask_setup.sh install.sh` — no new
   warnings.
2. Remaining `tests/test_*setup*.sh` (codex setup, claude setup) pass:
   ```bash
   for t in tests/test_*setup*.sh; do bash "$t" || echo "FAIL: $t"; done
   ```
3. Spot-check setup script syntax: `bash -n .aitask-scripts/aitask_setup.sh`
   and `bash -n install.sh`.
4. `.github/workflows/release.yml` parses successfully (Python YAML
   check above).
5. `ls seed/ | grep -i gemini` — empty.
6. Final grep across the scoped files returns empty (per Step 5).
7. `aidocs/adding_a_new_codeagent.md` — Index lists §17–§22; intro line
   no longer mentions "Gemini CLI"; "More sections to be added" stub
   reflects current coverage.

## Step 9 (Post-Implementation)

Standard archival. Final Implementation Notes **must** include the
`### For t814 (add-agy): inverse instructions` subsection per parent
plan's binding requirement.

## Final Implementation Notes

- **Actual work done:**
  - `.aitask-scripts/aitask_setup.sh`: deleted `setup_gemini_cli`,
    `merge_gemini_policies`, `merge_gemini_settings`,
    `install_gemini_global_policy` (4 functions, ~340 lines). Removed
    the `_is_agent_installed gemini` case branch, the
    `_is_agent_installed gemini → setup_gemini_cli` orchestration
    block, the shared-helper-doc copy-loop entries for
    `geminicli_tool_mapping.md` / `geminicli_planmode_prereqs.md`
    (with comment fix), the `agent_type` docstring comment, and the
    `.gemini/` + `GEMINI.md` entries from
    `commit_framework_files()::check_paths`. Also fixed an inline
    comment that mentioned `GEMINI.md`.
  - `install.sh`: deleted `install_gemini_staging` and
    `install_seed_gemini_config` (~75 lines). Removed their
    orchestration calls in the main install flow, the shared-helper-doc
    copy-loop entries (with comment fix), and the `.gemini/` +
    `GEMINI.md` entries from
    `commit_installed_files()::check_paths`.
  - `.github/workflows/release.yml`: removed the entire "Build gemini
    commands, policies, and helper docs" step (~20 lines), the four
    `gemini_*` references from the release-tarball `tar -czf` args,
    and the shared-helper-doc copy-loop entries from the codex build
    step (with comment fix).
  - `seed/`: deleted `geminicli_instructions.seed.md`,
    `geminicli_settings.seed.json`, `geminicli_policies/`,
    `models_geminicli.json`.
  - `aidocs/adding_a_new_codeagent.md`: dropped `Gemini CLI` from the
    intro example list. Extended the Index. Added §17 (Setup CLI
    orchestration) with sub-sections 17a–17g covering
    `_is_agent_installed`, `setup_<agent>_cli`, optional policy
    helpers, orchestration block, helper-doc copy-loop tuple,
    `agent_type` docstring, and the `check_paths` framework-paths
    list. Added §18 (Install staging) with 18a–18e. Added §19
    (Release packaging) with 19a–19c. Added §20 (Seed assets) with
    20a–20d. Added §21 (Helper-doc copy-loop fan-out across the 3
    lockstep sites with a touchpoint table). Added §22 (Per-agent
    runtime dotdir / framework-paths). Updated the "More sections"
    stub to reflect new coverage.

- **Deviations from plan:**
  - Plan called for `.gemini/` "gitignore-skip" entries. Closer
    reading showed these are actually entries in `check_paths=(...)`
    arrays inside `commit_framework_files()` /
    `commit_installed_files()` — used for auto-staging framework
    paths to git, not literal gitignore-skip lists. Same effect
    (preserving `.gemini/` in user repos); plan terminology
    corrected to "framework-paths list" in the new §17g / §18e.
  - Plan also missed `GEMINI.md` in both `check_paths` arrays —
    removed in lockstep.
  - Plan missed an inline reference to `GEMINI.md` in the
    `update_agentsmd()` comment block (~line 1053) — also cleaned.
  - `tests/test_gemini_setup.sh` already deleted by t812_2 (noted in
    verify-mode pass; Step 5 was a no-op as predicted).

- **Issues encountered:** None — all line-number claims in the
  verified plan held up, and the function-body deletions composed
  cleanly with no orphaned references.

- **Key decisions:**
  - For §21 (Helper-doc copy-loop fan-out) the cross-site touchpoint
    is now documented as a table with file/line/loop-variable
    columns. This is the same pattern used in §13 (Policy/whitelist
    touchpoints) and §1c's "Hardcoded agent enums" subsection — they
    are the project's preferred shape for cross-file lockstep lists.
  - §17 was split into 7 sub-sections (17a–17g) instead of one block
    because the touchpoints are independent (case branch vs.
    function body vs. orchestration vs. comment) and each one is the
    natural anchor a future author would search for when adding /
    removing an agent.
  - §22 was kept separate from §17g / §18e (instead of folded into
    them) because the `check_paths` lists touch **two** files in
    lockstep — pulling the convention out into a numbered section
    makes the duplication discoverable and gives a single canonical
    home for the "shared-root agents don't need their own dotdir"
    rule.

- **Upstream defects identified:** None.

- **Notes for sibling tasks:**
  - **t812_4 (docs):** the website docs and the `aidocs/` files
    flagged as t812_4 scope by t812_2 are still pending. Specifically
    `aidocs/aitasks_extension_points.md`,
    `aidocs/stub-skill-pattern.md`,
    `aidocs/skill_authoring_conventions.md`,
    `aidocs/issue_type_vocabulary_duplication.md`, and
    `.claude/skills/task-workflow/model-self-detection.md` (plus the
    `satisfaction-feedback.md` source and its associated goldens).
    `aidocs/geminicli_to_agy.md` stays (t814 input).
  - **t812_5 (cleanup):** any pending geminicli aitasks themselves
    are out of scope for this child — handled by t812_5.

### For t814 (add-agy): inverse instructions

- **Files re-touched by agy (exact list + ranges where geminicli was
  removed):**
  - `.aitask-scripts/aitask_setup.sh`:
    - `_is_agent_installed()` case (was line 103) — add `agy)
      command -v <cli> &>/dev/null ;;`.
    - `assemble_aitasks_instructions()` docstring (line ~974) — add
      `agy` to the `agent_type:` enumeration.
    - `update_agentsmd()` doc comment (line ~1053) — add agy's
      project-level instructions file to the list if applicable.
    - `setup_codex_cli()` helper-doc copy-loop tuple (line ~1766) —
      add `agy_tool_mapping.md` / `agy_planmode_prereqs.md` if
      applicable (see §21 in `adding_a_new_codeagent.md`).
    - "Other agents" orchestration block (line ~1960) — add `if
      _is_agent_installed agy; then setup_agy_cli; fi`.
    - `commit_framework_files()::check_paths` array (line ~2340) —
      add `.agy/` and (if any) `AGY.md`. Note agy shares
      `.agents/skills/` with codex via the shared-root mechanism,
      so the dotdir may not be needed (see §22).
    - **New function `setup_agy_cli()`** modeled on `setup_codex_cli()`.
  - `install.sh`:
    - Shared-helper-doc copy loop in `install_codex_staging()` (line
      ~482) — mirror the §21 tuple update.
    - **New functions `install_agy_staging()` and
      `install_seed_agy_config()`** modeled on the codex equivalents.
    - Orchestration calls in main install flow (line ~975) — add
      `install_agy_staging` + `install_seed_agy_config`.
    - `commit_installed_files()::check_paths` (line ~700) — mirror
      the `aitask_setup.sh` array changes.
  - `.github/workflows/release.yml`:
    - Helper-doc copy loop in the codex build step (line ~57) —
      mirror the §21 tuple update.
    - Tarball `tar -czf` args (line ~105) — add any new agy staging
      dirs if agy introduces its own (most likely it reuses
      `codex_skills/` via the shared root and needs no new entry).
  - `seed/`:
    - **New `seed/agy_instructions.seed.md`** (Layer-2 instructions
      — adapt geminicli's content with the tool-name updates per
      `aidocs/geminicli_to_agy.md`: `run_shell_command` →
      `run_command`, `web_fetch` → `read_url_content`).
    - **New `seed/models_agy.json`** (per-agent model registry seed).
    - `seed/agy_settings.seed.json` / `seed/agy_policies/` only if
      agy ships per-agent settings or policies — `aidocs/geminicli_to_agy.md`
      says it does not, so skip both.

- **Pattern removed (anchor examples):**
  - Function family deleted: `setup_gemini_cli`,
    `merge_gemini_policies`, `merge_gemini_settings`,
    `install_gemini_global_policy`, `install_gemini_staging`,
    `install_seed_gemini_config`. agy will need
    `setup_agy_cli` + `install_agy_staging` +
    `install_seed_agy_config` (the three merge helpers can be
    skipped per the global-sandboxing scoping in §17c).
  - `.gemini/` and `GEMINI.md` entries removed from both
    `check_paths` arrays — agy mirror lives in §22's "Per-agent
    runtime dotdir" guidance.
  - "Build gemini commands, policies, and helper docs" release-yml
    step removed entirely — agy will reuse the codex build step
    via the shared-root mechanism (no new step needed if agy ships
    no `.agy/`).

- **Inverse instruction:** to add agy, implement `setup_agy_cli()`
  modeled on `setup_codex_cli()` (lighter — no policy install
  because agy handles policies globally). In `install.sh`, mirror
  `install_codex_*` for agy. In `release.yml`, the codex build step
  already covers agy via the shared-root mechanism — only the
  helper-doc copy-loop tuple in that step needs the agy entries.
  Add `seed/agy_instructions.seed.md` and `seed/models_agy.json`.
  Follow the §17–§22 checklist in `adding_a_new_codeagent.md` for
  the full touchpoint list.

- **Hidden coupling discovered during removal:**
  - **`check_paths` array is duplicated across two files** by
    intent (`aitask_setup.sh::commit_framework_files()` and
    `install.sh::commit_installed_files()` cannot source a shared
    helper because `install.sh` runs stand-alone via `curl|bash`
    before extraction). Cataloged as the §17g/§18e/§22
    cross-reference.
  - **Helper-doc copy-loop tuple is duplicated across three files**
    (`aitask_setup.sh`, `install.sh`, `release.yml`) — same reason:
    one runs at user-setup time, one at install time, one at
    build time, and none can source a shared helper. Cataloged as
    §21.
  - The `_is_agent_installed gemini → setup_gemini_cli`
    orchestration block (and its codex / opencode siblings) is
    **not** generated by any helper — it is a hand-written
    if-block per agent. Adding agy means adding a new block;
    removing the gemini variant required a precise delete.
  - The `agent_type` enumeration in the
    `assemble_aitasks_instructions()` docstring is a comment, not
    a runtime check, and is easy to miss. Cataloged as §17f.
