---
priority: medium
effort: high
depends: [t1647_3]
issue_type: feature
status: Ready
labels: [trails, skills, codeagent]
gates: [risk_evaluated]
anchor: 1647
created_at: 2026-09-01 18:50
updated_at: 2026-09-01 18:50
---

## Context

Fourth child of t1647 (trail-to-trail merge). Build the user-facing surface:
the profile-aware `/aitask-merge-trails` skill and the `merge-trails`
codeagent operation. Consumes t1647_3's `aitask_trail_merge.sh` protocol and
t1647_2's `merged_from` provenance.

**All three agent surfaces MUST land in this one child**:
`tests/test_skill_dispatch_contract.sh` discovers templated skills at runtime
(`find .claude/skills -name SKILL.md.j2`) and immediately requires every
stub + rendered closure — deferring the codex/opencode stubs to a follow-up
fails the suite. (Deliberate exception to the CLAUDE.md "separate aitasks for
other agents" rule.)

## Skill surface (per aidocs/framework/skill_authoring_conventions.md +
stub-skill-pattern.md §3g — read both before editing)

- `.claude/skills/aitask-merge-trails/SKILL.md` — stub (resolver key
  `merge-trails`; model: `.claude/skills/aitask-trail/SKILL.md`).
- `.claude/skills/aitask-merge-trails/SKILL.md.j2` — authoring template.
- `.agents/skills/aitask-merge-trails/SKILL.md` — codex stub (rendered
  variant carries the `-codex-` segment).
- `.opencode/commands/aitask-merge-trails.md` + skill-dir stub
  `.opencode/skills/aitask-merge-trails/SKILL.md`.
- Goldens `tests/golden/skills/aitask-merge-trails/SKILL-{default,fast,remote}-claude.md`
  regenerated via `.aitask-scripts/lib/skill_template.py` in the SAME commit
  as the template (regen loop in skill_authoring_conventions.md
  "Regenerate goldens").
- Run `./.aitask-scripts/aitask_skill_verify.sh` before committing.

## Skill flow (the template body; NON-SKIPPABLE markers are literal)

0. Parse `[--lite|--deep] <base_ref> [<folded_ref>]` (refs whitespace-free —
   the codeagent launch guard enforces this).
1. One ref → `./.aitask-scripts/aitask_trail_merge.sh candidates -- <ref>`.
   `BASE_CANDIDATE:` lines (approximate match) → AskUserQuestion to pick the
   surviving base FIRST (an approximate name never silently selects the
   survivor of a destructive merge), then re-run candidates with the chosen
   handle. Then AskUserQuestion over `CANDIDATE:` lines to pick the folded
   trail ("no merge" always offered; candidates are advisory — RFC §13-A6).
   Two refs (the board's argument shape) → skip the scan; approximate
   two-ref input still gets the pick-the-base treatment.
   `RESUME:retirement_pending` at any point → offer ONLY "complete the
   retirement" (run the remaining rms) / "abort"; never re-author.
2. `aitask_trail_merge.sh preflight -- <base> <folded> [depth-flag]` →
   display depth pair, RESULT_DEPTH, OVERLAP/BASE_ONLY/FOLDED_ONLY,
   FOLDED_REF owners; RECORD both current_version values as the stale-base
   baseline; DOWNGRADE → NON-SKIPPABLE confirmation naming the dropped
   counts; ERROR → stop.
3. Fetch both docs: `ait artifact get <handle> --out <scratch>` × 2.
4. Author the merged document — **agent re-authoring, never mechanical
   union** (a lite union is schema-invalid: lite = exactly 1 evidence
   record, NO observations/relations/exclusions). Rules: dedup entries by
   canonical task ref; renumber wave ordinals and per-wave positions
   strictly increasing; reconcile waves; merge
   narrative/exclusions/observations per RESULT_DEPTH; `trail_id` + handle =
   base's; `merged_from` records BOTH sources (handle@version from the
   Step-2 baseline, merged_at now); `generation.inputs` gains one
   `{"kind": "other", "ref": "<handle>@<version>"}` per source;
   `generator.skill: "aitask-merge-trails"`; freshness current. Adapt the
   "Trail JSON authoring rules" section of
   `.claude/skills/aitask-trail/SKILL.md.j2` (~L799) inline — sentinel
   rules (omit unknown/invalid snapshot fields), hard_depends provenance,
   overview non-blank, etc. all apply.
5. Validate: `./.aitask-scripts/aitask_trail_depth.sh validate <file>
   --expect-depth <RESULT_DEPTH>` (already whitelisted).
6. NON-SKIPPABLE confirmation naming the FULL write set: `ait artifact
   update <base_handle> <merged.json>` AND one `ait artifact rm <owner>
   <folded_handle>` per FOLDED_REF line — retirement removes EVERY
   reference (the substrate keeps the manifest while any remains); the
   confirmation enumerates each owner with its active/archived/folded
   state. All recoverable from data-branch history. The confirmation comes
   BEFORE the stale-base guard: the user can deliberate here indefinitely,
   so any earlier version check would be stale by the time they answer.
7. Stale-base guard (both handles) AFTER confirmation, coupled directly to
   execution: re-read both current versions (`ait artifact versions` × 2 or
   re-run preflight) vs the Step-2 baseline. Unchanged → execute
   immediately, no further prompt. Either moved → NON-SKIPPABLE
   AskUserQuestion: "Reload and re-author" (redo 3–6 on current content,
   fresh confirmation) / "Overwrite anyway" (named as stale) / "Abort".
   State the residual in the skill notes: no CAS — the re-read→write gap
   remains; the guard shrinks the window, it does not eliminate it.
8. Writes: `update` the base FIRST, then the rm sequence — never retire
   first. `update` fails → nothing to compensate; report and stop. Any rm
   fails / partial → report exactly which owners' references remain + the
   completing commands, and note that re-running the skill with the same
   pair resumes via `RESUME:retirement_pending` (complete-retirement only).
9. Run summary + board pointer (By-Trail `z` / `s`), mirroring the trail
   skill's run-summary structure.

## Codeagent operation (`.aitask-scripts/aitask_codeagent.sh`)

- `SUPPORTED_OPERATIONS` (:26): add `merge-trails`.
- Per-agent prompt branches (case arms near :426, :476, :545, :575):
  claudecode → `/aitask-merge-trails <args>`; codex →
  `build_skill_prompt "$aitask-merge-trails" ...`; opencode →
  `--prompt "/aitask-merge-trails <args>"`. Usage text (:644).
- `defaults."merge-trails"` entry in BOTH
  `aitasks/metadata/codeagent_config.json` AND `seed/codeagent_config.json`
  (project convention: new ops need `.defaults` in both; value: same agent
  string as `trail`).

## Tests

- `tests/test_skill_render_aitask_merge_trails.sh` — model:
  `tests/test_skill_render_aitask_trail.sh` (goldens ×3 profiles, Test 1b
  agent invariance, no Jinja markers, walk-write reference rewrites, stub
  markers ×3 agents).
- `tests/test_merge_trails_skill_contract.sh` — model:
  `tests/test_trail_skill_contract.sh`; pins across ALL 3 goldens:
  one-confirmation-covers-the-full-write-set (update + every FOLDED_REF rm);
  rm-targets-each-referencing-owner; preflight-before-author;
  validate-with-expect-depth; advisory candidates;
  approximate-base-requires-explicit-selection; stale-base guard AFTER the
  final confirmation with reload/overwrite/abort; update-before-rm order;
  rm-failure guidance naming completing commands + resumable re-invocation;
  RESUME path never re-authors.
- `tests/test_codeagent_merge_trails.sh` — model:
  `tests/test_codeagent_trail.sh` (resolve + dry-run per agent).
- `bash tests/test_skill_dispatch_contract.sh` — covers the new skill
  automatically; must pass.

## Verification

- All four test files above green; `aitask_skill_verify.sh` clean;
  `shellcheck .aitask-scripts/aitask_codeagent.sh` clean.
- `./.aitask-scripts/aitask_codeagent.sh resolve merge-trails` →
  AGENT_STRING line; `... invoke merge-trails --dry-run <two handles>`
  prints the expected command.

Parent plan: `aiplans/p1647_merge_trails_skill_shared_helpers_board_command_docs.md`.
