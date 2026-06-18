---
Task: t1016_2_anchor_doc_consolidation.md
Parent Task: aitasks/t1016_anchor_task_topic_grouping.md
Sibling Tasks: aitasks/t1016/t1016_1_*.md, aitasks/t1016/t1016_3_*.md, aitasks/t1016/t1016_4_*.md
Archived Sibling Plans: aiplans/archived/p1016/p1016_*_*.md
Worktree: aiwork/t1016_2_anchor_doc_consolidation
Branch: aitask/t1016_2_anchor_doc_consolidation
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-18 12:32
---

# Plan — t1016_2 Schema doc consolidation (anchor)

## Context

t1016_1 (archived) added the scalar `anchor: <task_id>` frontmatter field plus
the `--anchor` / `--followup-of` creation flags and an editable `--anchor` in
`aitask_update.sh`. The field is now live in code but documented **nowhere**.
This task documents it in every surface that enumerates the task schema, so
agents/users don't drift, and fixes the `aitasks_extension_points.md` new-field
checklist (which is itself incomplete — it omits `aitask_merge.py` and the doc
surfaces). Excludes the board "by-topic" VIEW doc (ships in t1016_4).

**Verified 2026-06-18 (verify path):** all 6 surfaces exist; `anchor` is
documented in none of them yet; implemented semantics confirmed against current
code (mutual exclusion, `--parent` rejection, follow-up flatten + legacy-child
parent fallback, child auto-inherit, bare-id normalization, roots emit no
`anchor:` line, merge newer-wins). The canonical contract uses an `## Input`
table; `aitask-create/SKILL.md` uses a bullet list that already references the
contract; the extension-points checklist has exactly 3 numbered layers.

## Authoritative semantics to document (from t1016_1, verified)

- **Group key = `anchor` if set, else own id.** Roots emit **no** `anchor:` line.
- **Child of `--parent P`** auto-inherits `anchor = P.anchor` if set, else `P`
  (bare). `--anchor`/`--followup-of` are **rejected** alongside `--parent`.
- **`--followup-of S`** resolves to S's topic root: `S.anchor` if set; else if S
  is an anchorless child `<p>_<c>` → `<p>`; else → `S`. **Flattened — never
  chains.**
- `--anchor` and `--followup-of` are **mutually exclusive**.
- All ids normalized to **bare** form (leading `t` stripped; `N` or `N_M`),
  validated to exist (archived-inclusive). `--anchor ""` clears the field.
- Merge: newer `updated_at` wins (scalar; NOT in `_LIST_UNION_FIELDS`/`BOARD_KEYS`).

## Surfaces (6) + checklist

1. **`.claude/skills/task-workflow/task-creation-batch.md`** (canonical `## Input`
   table) — add two `optional` rows: `anchor` (explicit topic root id) and
   `followup_of` (anchor to source task's root), plus a short inheritance-rule
   prose block (child inherits root; follow-up flattens to root; root = no
   anchor; the three rules are mutually exclusive with `--parent`). This is the
   single source of truth; other surfaces point here, never re-specify.
2. **`.claude/skills/aitask-create/SKILL.md`** (~L268-286 bullet list) — add
   `--anchor ID` and `--followup-of ID` bullets, keeping the existing pointer to
   the canonical contract (no semantics duplication).
3. **`CLAUDE.md`** "### Task File Format" (L57-73 YAML block) — add an `anchor:
   <task_id>   # topic-group key (see anchor docs)` line. **Verify first** that
   this section is hand-maintained (not regenerated): grep `CLAUDE.md` for the
   aitasks-instruction insert markers used by `insert_aitasks_instructions()`. If
   the `### Task File Format` block is OUTSIDE the markers (expected — it is the
   framework's own hand-written dev doc, distinct from the generic seed `## Task
   File Format`), edit directly. If it turns out to be inside the marker block,
   edit the seed instead and regenerate. (Resolves the verify-flag that
   `update_claudemd()` references the seed.)
4. **`seed/aitasks_agent_instructions.seed.md`** "## Task File Format" (L10-25
   YAML block) — add `anchor:`. Then REGENERATE the mirrors `AGENTS.md`,
   `.codex/instructions.md`, `.opencode/instructions.md` via the `ait setup` path
   (`aitask_setup.sh::assemble_aitasks_instructions` → `update_agentsmd` /
   `setup_codex_cli` / `setup_opencode_cli`). Do **NOT** hand-edit the generated
   mirrors — `test_agent_instructions.sh` fails on divergence.
5. **`website/content/docs/development/task-format.md`** (Frontmatter Fields table
   L30-59) — add an `| `anchor` | task id (`42`, `42_1`) | … |` row, mirroring the
   `boardcol` / `folded_tasks` row format.
6. **`aidocs/framework/aitasks_extension_points.md`** (new-field checklist L10-16)
   — (a) record `anchor` as a worked example against the checklist; (b) EXTEND
   the 3-item checklist to add the missing layers: a `aitask_merge.py` scalar/
   list-merge rule item, and a doc-surface item enumerating seed→mirrors,
   CLAUDE.md, website task-format, canonical batch contract, SKILL.md flag list,
   board reference.

Then regenerate skill goldens: `./.aitask-scripts/aitask_skill_rerender.sh`
(the canonical contract edit in #1 re-renders into Codex/OpenCode variants —
no separate port task).

## Implementation order

1. Edit canonical `task-creation-batch.md` (#1) — source of truth first.
2. Edit `aitask-create/SKILL.md` bullet list (#2).
3. Verify + edit `CLAUDE.md` (#3).
4. Edit seed (#4); regenerate the 3 mirrors via `ait setup`; confirm markers
   preserved + `anchor:` present in each.
5. Add website table row (#5).
6. Update + extend extension-points checklist (#6).
7. Regenerate skill goldens (`aitask_skill_rerender.sh`).

## Verification

- `bash tests/test_agent_instructions.sh` — generated mirrors match the seed.
- `bash tests/test_skill_render_task_workflow.sh` + `./.aitask-scripts/aitask_skill_verify.sh` — clean after the canonical-contract edit + goldens regen.
- `grep -n anchor AGENTS.md .codex/instructions.md .opencode/instructions.md` — present post-regen.
- `grep -n anchor` the canonical contract and `aitask-create/SKILL.md` → flag names agree (`--anchor`, `--followup-of`).
- `cd website && hugo build --gc --minify` — succeeds.

## Risk

### Code-health risk: low
- Documentation-only; no runtime logic changes. Bounded blast radius (6 doc
  surfaces + 3 generated mirrors + skill goldens), all changes test-verified
  (`test_agent_instructions.sh`, `test_skill_render_task_workflow.sh`). · severity: low · → mitigation: TBD
- Hand-editing a generated mirror (instead of the seed) or skipping a goldens
  regen would diverge — caught by the named tests; the CLAUDE.md grep guard
  (#3) prevents clobbering a seed-managed block. · severity: low · → mitigation: TBD

### Goal-achievement risk: low
- None identified. All 6 surfaces and the implemented semantics were verified
  against current code (zero drift); requirement coverage is complete; semantics
  are defined once (canonical contract) with other surfaces pointing to it.

(No `### Planned mitigations` — both dimensions are low and documentation-scoped;
before/after mitigation tasks would be redundant.)

## Post-Implementation
Step 9 applies on completion. In Final Implementation Notes, record the exact
`ait setup` invocation used to regenerate the mirrors (useful to siblings/future
field additions), and the resolved CLAUDE.md mechanism (hand vs seed).
