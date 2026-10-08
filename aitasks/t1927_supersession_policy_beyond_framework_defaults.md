---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [codeagent, models, model_selection]
gates: [risk_evaluated]
anchor: 1916
followup_kind: carry_over
created_at: 2026-10-08 23:40
updated_at: 2026-10-08 23:40
---

## Origin

Carried over from t1916. t1910 (6126268ff) shipped model supersession restricted
to models that were once **framework defaults**. Its plan lists "models never a
framework default (opus4_5, haiku, fable, gpt5_x, all opencode)" as **Not
recorded**, treating a user on such a model as a deliberate choice. The user
judged that restriction wrong: limiting obsolete-model upgrade offers to the
models the framework ships as defaults is too limiting.

## Already done in t1916 (do not redo)

- Edge `claudecode: haiku4_5 → haiku5_5` recorded via `record-supersession`.
- `tests/test_install_superseded_models.sh`: the never-offered control moved
  from `haiku4_5` to `haiku5_5`; new positive case `explore: haiku4_5` → offered
  `haiku5_5`.
- Policy statements rewritten (supersession is not limited to defaults):
  `website/content/docs/commands/codeagent.md` (Superseded model defaults),
  `website/content/docs/commands/setup-install.md`,
  `website/content/docs/skills/aitask-add-model.md`,
  `.claude/skills/aitask-add-model/SKILL.md` Notes.

## Goal — make the policy systematic

1. **Fix the Step 6 commit condition in `.claude/skills/aitask-add-model/SKILL.md`**
   (review finding on t1916, CONFIRMED, low). The Notes now say to declare a
   non-default model's successor and "commit the table as in Step 6". But Step 6's
   "Supersession table" commit block applies only in "promote mode, when
   `promote-config` printed `NOTE: commit .aitask-scripts/lib/model_supersessions.json`".
   `record-supersession` prints the same `NOTE:` line, yet an add-only run that
   follows the Notes meets a contradictory condition and can leave the table
   uncommitted. Broaden the condition: "whenever `promote-config` **or
   `record-supersession`** printed the NOTE".
2. **Offer the lineage at registration time.** When `add-json` (or the skill's
   add mode) registers a model that is the successor of an already-registered
   model in the same family (e.g. `haiku4_5` → `haiku5_5`), the skill should
   propose a `record-supersession` edge (`--dry-run` preview, user confirms),
   instead of relying on the agent reading a Note. Decide how the predecessor is
   identified (user-named in the skill flow is fine; avoid name-parsing
   heuristics that assert lineage).
3. **Backfill missing lineages** that the old policy excluded. Review, at least:
   claudecode `fable5 → fable5_1` and older opus/sonnet/haiku models that never
   were defaults (e.g. `opus4_5`), codex `gpt5_x` lines. Record each with
   `record-supersession`, with a dry-run review and user confirmation per edge.
   Mind `seed_invariant` (an old model that is still a seed default is refused),
   and keep `_1m` siblings consistent.
4. **OpenCode.** t1910 excludes "all opencode", and `aitask-add-model` refuses
   opencode. Decide whether opencode lineages are in scope; it may depend on the
   OpenCode refresh in t1919.
5. **Port to the other agent trees.** `.agents/skills/aitask-add-model/SKILL.md`
   and `.opencode/skills/aitask-add-model/SKILL.md` (plus
   `.opencode/commands/aitask-add-model.md`) contain **no** supersession content
   (0 mentions as of 2026-10-08): port t1910's promote-config/record-supersession
   steps along with this policy (per CLAUDE.md, Claude Code is the source of
   truth; split per-agent ports into their own tasks if large).

## Verification

- `bash tests/test_add_model.sh`, `python3 tests/test_model_supersession.py`,
  `bash tests/test_install_superseded_models.sh`,
  `python3 tests/test_install_superseded_prompt_pty.py` pass.
- `cd website && python3 check_links.py --build` passes if docs change.
- Step 6 of the add-model SKILL names `record-supersession` in its commit condition.
