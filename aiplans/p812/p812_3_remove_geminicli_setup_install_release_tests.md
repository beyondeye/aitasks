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

## Final Implementation Notes (template)

- **Actual work done:** …
- **Deviations from plan:** …
- **Issues encountered:** …
- **Key decisions:** …
- **Upstream defects identified:** None (or list)
- **Notes for sibling tasks:** …

### For t814 (add-agy): inverse instructions

- **Files re-touched by agy:** (file list + line ranges of deletions).
- **Pattern removed (anchor example):** function names removed
  (`setup_gemini_cli`, `install_gemini_staging`, etc.).
- **Inverse instruction:** to add agy, implement `setup_agy_cli()`
  modeled on `setup_codex_cli()` (lighter — no policy install
  because agy handles policies globally). In `install.sh`, mirror
  `install_codex_*` for agy. In `release.yml`, mirror codex
  packaging steps. Add `seed/agy_instructions.seed.md` (adapt
  geminicli's Layer-2 instructions with the tool-name updates per
  `aidocs/geminicli_to_agy.md`) and `seed/models_agy.json`.
- **Hidden coupling discovered during removal:** ordering
  constraints, gitignore-skip entries, agent-install markers
  (`.aitask-installed-<agent>`), etc.
