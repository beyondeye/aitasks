---
Task: t1940_opencode_model_supersession_lineages.md
Base branch: main
Output branch: main
---

# t1940 — OpenCode model supersession lineages

## Context

t1927 made model supersession systematic for `claudecode` and `codex`, but
OpenCode was deferred for three reasons:

- `model_supersessions.json` has no `opencode` section.
- `aitask_add_model.sh` `validate_agent` refuses `opencode` for every
  subcommand.
- `model_supersession.family()` takes only the leading letters of a name, so
  every OpenCode model is family `opencode` or `openai`. Neither `WARN:family`
  nor the shipped contract test protects anything.

The result is that an operation configured with an OpenCode model is never
offered its successor.

Decisions made during planning:

- **Unavailable old models are allowed.** An edge may start from a model that
  is now `status: unavailable`.
- **Goal 4.** Add a lineage-proposal step to `aitask-refresh-code-models` for
  all agents, framework repo only. The discovery script stays unchanged.
- **Plan review concerns (all verified valid and addressed here):**
  1. Variants after the version token must be distinguished. Variant changes
     need an explicit, recorded exception.
  2. One policy for the recorder, the backfill and the contract. No candidate
     may be offered that the shipped contract would reject.
  3. The contract checks registration structurally, independent of status, so
     a refresh that marks an intermediate model unavailable does not break it.
     Runtime already skips such a model.

All consumers of the table are already agent-agnostic: `load_registries`,
`find_offers`, settings, `install.sh` and `ait codeagent check-superseded`.

## Policy (one rule, three enforcers)

For an edge `old → new` of one agent:

- **Line**: same provider and same model line.
  - Recorder: `BLOCKED:family` for opencode. For claudecode/codex it stays
    `WARN:family`, because `promote-config` behaviour is unchanged.
  - Contract: required for every agent (as today).
- **Variant**: opencode only, `""` for other agents. It must be equal, unless
  the edge carries a non-empty `variant_change` reason.
  - Recorder: `BLOCKED:variant` without `--variant-change <reason>`.
  - Contract: `variant_change` is required exactly when the variants differ.
- **Registration**:
  - Recorder: the new model must be **offerable** (active-target guard,
    unchanged).
  - Recorder, strict agents only: the old model must be **listed** in the
    registry (any status, so unavailable predecessors still pass), else
    `BLOCKED:unlisted_old`. This applies on the dry-run and apply paths
    alike. claudecode/codex keep their legacy behaviour (no check).
  - Contract: old and new must be **listed** in the seed registry, any status.

## Implementation

### 1. Library — `.aitask-scripts/lib/model_supersession.py`

`family(name, agent=None)` returns the line:

- unchanged leading letters for non-opencode agents (`opus5_5` → `opus`);
- for opencode, `<provider>_<words>`: split the provider at the first `_`,
  take the following purely alphabetic tokens, and stop at the first token
  containing a digit. If that is the very first token, take its leading
  letters instead (`qwen3` → `qwen`).

New `variant(name, agent=None)`:

- returns `""` for non-opencode agents;
- for opencode, returns the alphabetic tokens after the first digit-bearing
  token, joined with `_`.

| name | family | variant |
|---|---|---|
| `opencode_claude_opus_4_5` | `opencode_claude_opus` | `` |
| `opencode_gemini_3_1_pro` / `_3_8_flash` | `opencode_gemini` | `pro` / `flash` (differ) |
| `opencode_gemini_3_5_flash_lite` | `opencode_gemini` | `flash_lite` (≠ `flash`) |
| `opencode_gpt_5_4_mini` / `_5_5_pro` | `opencode_gpt` | `mini` / `pro` (differ) |
| `opencode_gpt_5_6_sol` / `opencode_gpt_5_5` | `opencode_gpt` | `sol` / `` (differ) |
| `opencode_qwen3_6_plus` | `opencode_qwen` | `plus` |
| `opencode_kimi_k2_5` / `_k3` | `opencode_kimi` | `` |
| `opencode_grok_build_0_1` | `opencode_grok_build` | `` |
| `openai_codex_mini_latest` | `openai_codex_mini_latest` | `` (≠ `openai_gpt`) |
| `opencode_claude_3_5_haiku` | `opencode_claude` | `haiku` (≠ `opencode_claude_haiku`) |

Other changes:

- Constant `STRICT_AGENTS = ("opencode",)`, with a comment explaining why:
  opencode has no promotion path (record-supersession only), so anything that
  would violate the shipped contract — line, variant or an unlisted
  predecessor — is refused when it is recorded.
- `validate_table`: an optional `variant_change` must be a non-empty string.
- `_declare(..., variant_change=None, listed=None)`:
  - Strict agent with `old` not in `listed` → `BLOCKED:unlisted_old:<agent>/<old>`.
    This is checked first, before the seed and conflict checks. For a strict
    agent, `listed=None` is a programming error: raise `SupersessionError`
    rather than skip the check silently.
  - Line mismatch → `BLOCKED:family:<edge>` when the agent is strict, else
    the existing `WARN:family`.
  - Variant mismatch:
    - without a reason → `BLOCKED:variant:<edge>|<v_old>-><v_new>`;
    - with a reason → record `"variant_change": reason` on the entry and emit
      `NOTE:variant_change:<edge>|<v_old>-><v_new>`.
  - A reason given when the variants are equal is not stored, and the
    recorder emits `NOTE:variant_change_ignored:<edge>`.
  - All checks run before the write, next to `unregistered` and `cycle`.
- `plan_explicit(..., variant_change=None, listed=None)` passes the reason
  and the listed names through. `plan_promotion` passes `listed` too, because
  it shares `_declare`; opencode never reaches it anyway.
- New `edge_contract_problems(table, listed)`. `listed` maps each agent to all
  registry names, any status. It returns one string per violation:
  - `unlisted_old`;
  - `unlisted_new`;
  - `cycle`;
  - `family`;
  - `variant` (variants differ and there is no reason);
  - `stray_variant_change` (a reason on an equal-variant edge).

  It is the single statement of the contract (concerns 2 and 3), and it can be
  tested with fixtures.
- New `load_registry_names(path)`: all names regardless of status. It shares
  JSON parsing with `load_registry`.
- Docstring: add the line, variant and exception semantics in the "Semantics,
  in one place" block.

### 2. CLI — `.aitask-scripts/aitask_model_supersession.py` and `.aitask-scripts/aitask_add_model.sh`

- Python `record` subparser: `--variant-change REASON`, passed to
  `plan_explicit`. `record` also loads `load_registry_names(--models)` and
  passes it as `listed`. `--assume-registered` (dry-run only) adds `--new` to
  the offerable set only; it never vouches for `--old`.
- `aitask_add_model.sh`:
  - `validate_agent <a> [--allow-opencode]`;
  - only `cmd_record_supersession` passes the flag; `add-json`,
    `promote-config` and `promote-default-agent-string` stay refused with the
    unchanged message.
  - `record-supersession --variant-change "<reason>"` is forwarded to the
    Python CLI.
  - Header comment and `usage()`: opencode is accepted by
    `record-supersession` (lineages declared, not registered), and
    `--variant-change` is explained.

### 3. Tests

`tests/test_model_supersession.py`:

- `FamilyTests`: the table above as positive cases. Negative boundaries:
  - gemini `pro` vs `flash`;
  - `flash` vs `flash_lite`;
  - gpt `mini` vs `pro`;
  - `openai_*` vs `opencode_*`;
  - `codex_mini_latest` vs `gpt`.

  Non-opencode regression: `family("opus5_5", "claudecode") == "opus"`,
  `variant` is `""`, and `gpt5_3codex` → `gpt`.
- `plan_explicit` with opencode:
  - same line and variant → `RECORDED`;
  - `gpt_5_4_mini → gpt_5_5_pro` → `BLOCKED:variant`, and the table is
    unchanged;
  - the same edge with a reason → `RECORDED` plus `NOTE:variant_change`, and
    the entry carries the reason;
  - `openai_codex_mini_latest → openai_gpt_5_4` → `BLOCKED:family`, even with
    a reason;
  - `openai_gpt_5_4 → opencode_gpt_5_5` → `BLOCKED:family`;
  - an unavailable old model → `RECORDED`;
  - an unlisted predecessor with a valid family, variant and offerable target
    (`opencode_gpt_5_55 → opencode_gpt_5_5`) → `BLOCKED:unlisted_old`, and the
    table is unchanged;
  - the same typo for claudecode still records (legacy behaviour pinned).
  - a reason on an equal-variant edge → `NOTE:variant_change_ignored`, and
    nothing is stored.
- claudecode: the existing `test_family_warning_and_cross_agent_skip` stays
  unchanged (WARN, not BLOCKED).
- `EdgeContractTests` on fixture tables, one case per problem kind. It also
  includes a controlled **valid** variant-changing fixture: opencode
  `gpt_5_5 → gpt_5_6_sol` carrying a `variant_change` reason. The contract
  reports nothing for it. This is the case mutant (b) in the post-phase must
  break, whatever the backfill choices were.
  Availability-drift fixture: chain `a → b → c` with `b` marked unavailable.
  - `edge_contract_problems` reports nothing (b is still listed);
  - `offer_target` from `a` gives `c`.
- `ShippedTableTests`:
  - replace the body of the registered/acyclic/same-family test with
    `assertEqual(ms.edge_contract_problems(table, listed_seed_names), [])`;
  - rename it to `test_every_edge_meets_the_contract`;
  - keep the seed-invariant and sibling test.
- CLI `CheckReportTests`: the project uses
  `opencode/opencode_claude_opus_4_8`; the fixture `models_opencode.json` has
  4_8 unavailable and 5_5 active, and the check reports
  `opencode/opencode_claude_opus_5_5`. This is the task's
  `check-superseded --report` verification. A second case covers drift:
  table `opus_4_8 → 5 → 5_5` with `5` unavailable still offers `5_5`.
- `test_validate_rejects_bad_shapes`: add an empty `variant_change`.

`tests/test_add_model.sh`:

- New Test 15. The fixture gains `models_opencode.json`.
  - `record-supersession --agent opencode --dry-run` prints `RECORDED`, shows
    the diff, and writes nothing.
  - The apply run persists an `opencode` section; seed and project config are
    unchanged.
  - A variant jump without `--variant-change` is refused ("Refused" plus
    `BLOCKED:variant`); with it, the run records and the table has
    `variant_change`.
  - An unlisted predecessor (`--old opencode_gpt_5_55 --new opencode_gpt_5_5`)
    is refused with `BLOCKED:unlisted_old`, both with `--dry-run` and
    without. Nothing is written.
  - `promote-config --agent opencode` is still refused with the pointer.

### 4. Backfill (every option passes the contract; each is previewed and confirmed)

The flow follows t1927: dry-run each candidate, show the lines, then confirm
with `AskUserQuestion` (multiSelect, at most 4 options per question). A
confident chain is one option whose description lists every edge.
Variant-change edges and uncertain edges get their own option, and the option
names the reason that will be recorded. Apply only the confirmed edges, in
chain order. `(u)` marks an unavailable old model. `⇄ "<reason>"` marks a
variant change applied with `--variant-change`.

**opencode, same line and variant:**

- claude_opus 4_1(u)→4_5→4_6→4_7→4_8→5→5_5
- claude_sonnet 4→4_5→4_6→5→5_5
- claude_haiku 4_5→5_5
- claude_fable 5→5_1
- gpt 5→5_1→5_2→5_4→5_5
- gpt 5_6_sol→6_sol→6_1_sol
- gpt_*_codex 5→5_1→5_2→5_3
- gpt 5_6_luna→6_luna
- gpt nano 5→5_4
- gpt pro 5_4→5_5
- glm 4_6(u)→5, 4_7(u)→5, 5→5_1→5_2→5_3
- gemini pro 3(u)→3_1
- gemini flash 3→3_5→3_6→3_7→3_8
- grok 4_5→4_6→4_7
- minimax m2_1(u)→m2_5→m2_7→m3
- qwen plus 3_5→3_6
- deepseek flash v4→v4_1
- muse_spark 1_2→1_3, contributor_free 1_2(u)→1_3

**opencode, variant changes that mirror shipped codex edges:**

- gpt_5_5 → gpt_5_6_sol ⇄ "flagship → sol tier (mirrors codex/gpt5_5)"
- gpt_5_3_codex → gpt_5_4 ⇄ "codex → flagship (mirrors codex/gpt5_3codex)"
- gpt_5_4_mini → gpt_5_6_luna ⇄ "mini → luna tier (mirrors codex/gpt5_4_mini)"

**openai, same line and variant:**

- gpt 5_2(u)→5_4→5_5
- gpt 5_6_sol→6_sol→6_1_sol
- fast: 5_4_fast→5_5_fast, 5_6_sol_fast→6_sol_fast→6_1_sol_fast
- luna 5_6→6
- luna_fast 5_6→6

**openai, variant changes that mirror codex:**

- 5_5→5_6_sol
- 5_5_fast→5_6_sol_fast
- 5_3_codex(u)→5_4
- 5_4_mini→5_6_luna

**Uncertain (one option each; the user decides):**

- opencode kimi k2_5→k2_6→k3 (same variant; is k3 the successor line?)
- opencode gpt_5_1_codex_max→gpt_5_2_codex ⇄ "codex_max → codex"
- opencode gpt_5_1_codex_mini→gpt_5_4_mini ⇄ "codex_mini → mini"
- opencode ling_3_0_flash_fin_free→ling_3_1_flash_free ⇄ "fin → general"
- opencode mimo_v2_5_free(u)→mimo_v2_6_flash_free ⇄ "free → flash free"
- openai gpt_5_4_mini_fast→5_6_luna_fast ⇄ "mini → luna tier"
- openai gpt_5_codex(u), 5_1_codex(u), 5_2_codex(u)→gpt_5_4 ⇄ "codex → flagship"
- openai gpt_5_1_codex_max(u)→gpt_5_4 ⇄ "codex_max → flagship"
- openai gpt_5_1_codex_mini(u)→gpt_5_4_mini ⇄ "codex_mini → mini"

**Not offered, because the contract would reject them:**

- `openai_codex_mini_latest` (different line)
- `opencode_claude_3_5_haiku` (different line)

**Not offered, because no successor is evident:**

- terra, astra, codex_spark, flash_lite, glm_5_3_flash, mini_flex,
  openai 5_5_pro(u)
- free and preview one-offs

The seed has no opencode defaults, so the seed invariant cannot block
anything.

### 5. Refresh flow proposes lineages (goal 4) — `.claude/skills/aitask-refresh-code-models/SKILL.md`

New **Step 6b: Propose supersession lineages for new models**:

- It runs only if `seed/codeagent_config.json` exists (framework repo);
  otherwise it is skipped silently.
- It covers models added in Step 6, for any agent. For OpenCode, that means
  the names added relative to the Step 1 snapshot.
- By default, a predecessor candidate is a registered model with the **same
  line and variant**.
- A variant change (e.g. to a new tier) is proposed only as an explicit
  exception, with a stated reason that goes into `--variant-change`. Never
  propose a cross-line edge.
- Every candidate gets a `record-supersession --dry-run`. `BLOCKED` lines are
  reported and nothing is written. Confirmation uses `AskUserQuestion`
  (multiSelect, at most 4 per question), and the confirmed edges are applied
  in chain order.
- Step 8 commits the table when it changed, e.g.
  `git commit -m "ait: Record model supersession lineages" -- .aitask-scripts/lib/model_supersessions.json`
  followed by `git show --stat <sha>`.

The `.agents/` and `.opencode/` wrappers are 17–18-line pointers; confirm
during implementation that no port is needed.

### 6. Docs

- `.claude/skills/aitask-add-model/SKILL.md` Notes, around line 364:
  - opencode is refused for registration but accepted by
    `record-supersession`;
  - its lineages stay within one provider and line;
  - a variant change needs `--variant-change`.
- `website/content/docs/commands/codeagent.md:220`: replace "OpenCode models
  have none yet…" with:
  - supersessions are recorded for all three agents;
  - an OpenCode lineage stays within one provider and model line, for example
    `opencode/opencode_claude_opus_4_8` → `opencode/opencode_claude_opus_5_5`;
  - a model that a provider no longer serves is still offered its successor.
- `website/content/docs/skills/aitask-refresh-code-models.md`: one sentence on
  lineage proposals for newly added models.
- `website/content/docs/skills/aitask-add-model.md`: adjust any wording that
  says opencode is refused (check it first).
- Then run `cd website && python3 check_links.py --build`.

### Post-phase (risk mitigations)

1. [family_rule_negative_control] Work in a scratchpad copy of
   `.aitask-scripts/lib/` and `tests/test_model_supersession.py`, never in the
   real tree. Make two mutants, one at a time:
   - (a) `family()` ignores `agent` and falls back to leading letters;
   - (b) `variant()` always returns `""`.

   Run the copied test against the real backfilled table and seed registries
   for each mutant:
   - mutant (a) must fail the `FamilyTests` line cases and the
     `BLOCKED:family` case;
   - mutant (b) must fail, unconditionally:
     - the variant boundary cases;
     - `BLOCKED:variant`;
     - the controlled valid variant-changing fixture in `EdgeContractTests`
       (`stray_variant_change`).

     Conditionally, it must also fail `test_every_edge_meets_the_contract`, but
     only if at least one variant-change edge was approved in the backfill. If
     none was, that test passing under mutant (b) is correct, and the notes
     say so.

   Record the observed failures in Final Implementation Notes, then delete the
   copy.

### 7. Step 9 (Post-Implementation)

This is current-branch mode, so there is no merge. Archive and push per
task-workflow Step 9. The code commit includes `model_supersessions.json`,
with paths named:
`enhancement: Add OpenCode model supersession lineages (t1940)`.

## Verification

- `python3 tests/test_model_supersession.py`
- `bash tests/test_add_model.sh`
- `bash tests/test_install_superseded_models.sh`
- `shellcheck .aitask-scripts/aitask_add_model.sh`
- `python3 .aitask-scripts/aitask_model_supersession.py check --report` against
  a temp copy of the metadata whose config uses
  `opencode/opencode_claude_opus_4_8`; expect an offer of `opencode_claude_opus_5_5`.
- `cd website && python3 check_links.py --build`

## Risk

### Code-health risk: low
- If the provider-aware line and variant rules are ineffective, the structural contract (any-status registration) passes vacuously · severity: low · → mitigation: inline post-phase family_rule_negative_control
- `validate_agent` opt-in flag could let opencode through other subcommands · severity: low · → mitigation: none (Test 15 / Test 6 pin the refusals)
- The recorder and the contract could disagree on registration (an unlisted predecessor). Closed for opencode by the strict `BLOCKED:unlisted_old` check, and pinned by the fixture with an unlisted predecessor that has a valid family, variant and target · severity: low · → mitigation: none (in plan)
- Strict blocking applies to opencode only; claudecode/codex keep the WARN path, so the recorder and the contract still disagree for those agents (pre-existing) · severity: low · → mitigation: none (out of scope; noted for Final Implementation Notes)

### Goal-achievement risk: medium
- About 60 judgement-based lineage edges; uncertain ones could offer users an unsuitable switch · severity: medium · → mitigation: none (each edge is dry-run previewed and user-confirmed, variant changes carry an explicit recorded reason, and offers are opt-in with declines remembered)
- The refresh-skill lineage step depends on agent judgement · severity: low · → mitigation: none (it proposes only; variant changes need an explicit reason; the user confirms)

### Planned mitigations
- timing: post-phase | name: family_rule_negative_control | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: the structural contract passes vacuously under ineffective line/variant rules | desc: Isolated mutants (family ignores agent; variant always empty) must fail the line/variant tests and the shipped contract

## Post-Review Changes

### Change Request 1 (2026-10-11 15:10)
- **Requested by user:** (1) the auto-recorded `_1m` sibling of a variant-changing edge lacked `variant_change`, so the contract would reject it; (2) the Step 6b procedure was inlined in the refresh SKILL.md, against the extract-to-own-file convention; (3) its confirmation prompt lacked the NON-SKIPPABLE banner; (4) `cmd_record` read the registry twice.
- **Changes made:** (1) `_declare` copies the base entry's `variant_change` onto the generated sibling; new test `test_sibling_of_a_variant_change_carries_the_reason` (red-proved against a pre-fix copy: KeyError); (2) Step 6b moved to `.claude/skills/aitask-refresh-code-models/supersession-lineages.md`, SKILL.md keeps a thin reference; (3) the banner is at the procedure's confirmation step; (4) new `load_registry_sets()` returns `(offerable, listed)` from one read; `load_registry`/`load_registry_names` delegate to it; `cmd_record` uses it.
- **Files affected:** `.aitask-scripts/lib/model_supersession.py`, `.aitask-scripts/aitask_model_supersession.py`, `.claude/skills/aitask-refresh-code-models/SKILL.md`, `.claude/skills/aitask-refresh-code-models/supersession-lineages.md` (new), `tests/test_model_supersession.py`

## Final Implementation Notes
- **Actual work done:**
  - `lib/model_supersession.py`:
    - `STRICT_AGENTS = ("opencode",)`; the provider-aware `family(name, agent)` (line) and `variant(name, agent)`.
    - `edge_contract_problems()` (unlisted_old / unlisted_new / cycle / family / variant / stray_variant_change, structural any-status registration).
    - `load_registry_sets()` (one read) with `load_registry` / `load_registry_names` delegating to it.
    - `validate_table` accepts an optional non-empty `variant_change`.
    - `_declare` for strict agents emits `BLOCKED:unlisted_old` / `BLOCKED:family` / `BLOCKED:variant`, and `--variant-change` records the reason (`NOTE:variant_change`, `NOTE:variant_change_ignored`). The `_1m` sibling inherits the base edge's reason.
  - `aitask_model_supersession.py record`: `--variant-change`, plus `listed` names from the same registry read.
  - `aitask_add_model.sh`: `validate_agent --allow-opencode` for `record-supersession` only, and `--variant-change` forwarding. Usage and header are updated.
  - Tests:
    - `test_model_supersession.py`: FamilyTests, OpencodeRecordTests (incl. unlisted predecessor, legacy claudecode pin, sibling reason), EdgeContractTests (incl. a valid variant-change fixture and the availability-drift fixture), the shipped `test_every_edge_meets_the_contract`, and OpencodeOfferTests (unavailable old model, unavailable intermediate).
    - `test_add_model.sh` Test 15.
  - Backfilled 54 `opencode` edges, each dry-run previewed and confirmed by the user, 7 of them with `variant_change` (the codex tier mirrors):
    - opencode provider: claude opus/sonnet/haiku/fable, the gpt flagship chain, glm, gemini, grok, minimax, qwen, deepseek, muse_spark;
    - openai provider: the gpt and fast chains;
    - opencode mirrors: 5_5→5_6_sol, 5_3_codex→5_4, 5_4_mini→5_6_luna;
    - openai mirrors: 5_5→5_6_sol, 5_5_fast→5_6_sol_fast, 5_3_codex→5_4, 5_4_mini→5_6_luna.
  - The refresh skill's Step 6b references the new procedure file `supersession-lineages.md` (NON-SKIPPABLE confirmation). Step 8 commits the table.
  - Docs:
    - the add-model skill Notes;
    - `codeagent.md` (Superseded model defaults);
    - `aitask-add-model.md` (agents table);
    - `aitask-refresh-code-models.md` (lineage step).
- **Deviations from plan:**
  - Not recorded, by user decision: the gpt codex chain, nano/pro and kimi, plus all uncertain variant changes ("revisit when provider documentation confirms"). The uncertain openai-provider question came back unanswered and was treated as declined.
  - Post-review: the procedure was extracted to its own file, the sibling inherits `variant_change`, and the registry is read once.
- **Issues encountered:**
  - The first contract fixtures used toy names (`a`/`b`/`c`), which the opencode line rule reads as distinct providers. Replaced with realistic `opencode_glm_*` names.
  - The Python CLI has no `--report` flag (report is the default).
- **Key decisions:**
  - Strict blocking applies to opencode only, because it has no promotion path. claudecode/codex keep `WARN:family`, so `promote-config` is unchanged.
  - The contract checks registration structurally (any status); the recorder still requires an offerable target.
  - Variant changes are explicit, recorded exceptions rather than a looser family rule.
- **Negative control (post-phase family_rule_negative_control):** isolated scratchpad mutants, deleted afterwards.
  - (a) `family()` ignoring `agent` failed 22: the FamilyTests line cases, the line boundaries, and the `BLOCKED:family` case for `openai_codex_mini_latest`.
  - (b) `variant()` always `""` failed 16: the variant boundaries, `BLOCKED:variant`, the controlled valid-variant fixture (`stray_variant_change`), the variant problem kind, and `test_every_edge_meets_the_contract` (7 variant-change edges were approved, so the conditional expectation applies).
  - The sibling-reason test was red-proved against a pre-fix copy (KeyError).
- **Upstream defects identified:** `.aitask-scripts/lib/model_supersession.py:_declare` — for claudecode/codex a cross-family edge is still only `WARN:family`, yet `ShippedTableTests` rejects it, so a `promote-config` that records such an edge would produce a table failing its own contract (pre-existing recorder/contract disagreement; opencode is now strict).
