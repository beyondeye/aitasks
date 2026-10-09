---
Task: t1927_supersession_policy_beyond_framework_defaults.md
Base branch: main
Output branch: main
---

# t1927 — Supersession policy beyond framework defaults

## Context

t1910 recorded model supersession only for models that were once framework
defaults. t1916 changed that policy: an obsolete model should be offered its
successor whether or not the framework ever shipped it as a default. t1916 has
already recorded `haiku4_5 → haiku5_5` and rewritten the policy text. This task
makes the policy systematic:

- fix the add-model skill's commit condition;
- offer a lineage when a model is registered;
- backfill the lineages the old policy left out;
- decide the OpenCode scope;
- port the skill changes to the other agent trees.

Decisions already taken with the user:

- **OpenCode** is deferred to a follow-up task that runs after t1919 (t1919
  landed as dfa4d47b1). OpenCode names are provider-prefixed, so `family()`
  sees every OpenCode model as family `opencode`. `validate_agent` also refuses
  opencode.
- **Registration-time lineage:** the skill asks which model, if any, the new
  one succeeds. `record-supersession` gets a dry-run-only `--assume-registered`
  flag that mirrors `promote-config`, and the apply order is `add-json` →
  `record-supersession`.

Work happens on the current branch (profile `fast`).

## Steps

### 1. `record-supersession --assume-registered` (dry-run only)

File: `.aitask-scripts/aitask_add_model.sh`, in `cmd_record_supersession`.

- Parse `--assume-registered`. Reject it without `--dry-run`, with the same
  message `promote-config` uses: `die "--assume-registered is only valid with
  --dry-run"`.
- Pass it through to `supersession_record`. The Python `record` CLI already
  supports `--assume-registered` for the explicit (`--old`) path: it adds the
  target to the available set and prints `NOTE:assumes_registration:…`.
- Update `usage()` (the `record-supersession` line and the paragraph that
  explains `--assume-registered`) and the header comment.
- This reverses a t1910 decision. t1910 kept `record-supersession` on the real
  registry because it was only used for *later* declarations. A
  registration-time lineage is the same preview problem `promote-config`
  solved. An apply still always validates against the real registry.

### 2. Tests — `tests/test_add_model.sh`

- Flip the assertion at ~L495 (`record-supersession accepts no
  --assume-registered`). The new behaviour: `--dry-run --assume-registered`
  exits 0 and prints `NOTE:assumes_registration:claudecode/opus4_7` and
  `RECORDED:claudecode/opus4_5->claudecode/opus4_7` (assuming the fixture seed
  does not use opus4_5; confirm when implementing).
- Keep the `fixture_checksum` "refusals wrote nothing" check, and rename its
  label so it also covers the preview.
- Add: `record-supersession --assume-registered` without `--dry-run` exits 1
  with "only valid with --dry-run".
- **Required integration case: the add-only apply sequence**, in the isolated
  fixture, run in the skill's order:
  1. Take checksums of the fixture's `aitasks/metadata/codeagent_config.json`
     and `seed/codeagent_config.json`.
  2. `add-json --agent claudecode --name <new> …` (apply).
  3. `record-supersession --agent claudecode --old <registered non-seed model>
     --new <new>` (apply, without `--assume-registered`).
  4. Assert:
     - `table_successor <old>` equals `<new>` (the persisted link);
     - the output contains `NOTE: commit
       .aitask-scripts/lib/model_supersessions.json`;
     - both config checksums are unchanged (no default moved);
     - `seed_invariant` is `OK`.

### 3. Skill — `.claude/skills/aitask-add-model/SKILL.md`

- **Step 1 (inputs):** add a `--supersedes <old>` flag, the registered
  same-agent model this one succeeds. If it is not given, ask with
  `AskUserQuestion`: "Does `<agent>/<name>` succeed an already-registered
  model?"
  - Options: the registered models of the same agent whose
    `family()`/leading-letters prefix matches, newest first (at most 3),
    plus "None — no lineage".
  - The candidate list is only a convenience. The user picks, or names another
    model through "Other". Nothing is inferred.
- **One opt-out decision: `record_lineage`.** The skill keeps a single boolean
  that governs **both** recording paths: `promote-config`'s implicit edges and
  the explicit `record-supersession` call.
  - It starts `true`.
  - It becomes `false` on `--no-supersession`, on "Apply without recording
    supersession" (Step 4), on "Register without lineage" (Step 3
    BLOCKED handling) or on "Promote without recording supersession" (the
    existing BLOCKED:partial branch).
  - When it is `false`:
    - `promote-config` runs with `--no-supersession` (preview and apply);
    - the explicit `record-supersession` is **not run at all**, neither the
      preview nor the apply;
    - the Step 4 summary says "no lineage will be recorded".
- **Step 2 (validate):**
  - `--supersedes` must be registered in `models_<agent>.json` and must differ
    from `--name`.
  - **`--supersedes` together with `--no-supersession` is contradictory** and
    is refused here, before any dry-run, with "`--supersedes` declares a
    lineage and `--no-supersession` forbids one — pass one of them." The skill
    does not guess which flag wins.
  - Only one case suppresses the lineage question: an interactive run where
    `--no-supersession` was passed. Then `record_lineage` is already `false`
    and nothing would be recorded.
  - Duplicate-name abort message: add "if the model is already registered and
    only its lineage is missing, run `record-supersession --agent <a> --old
    <old> --new <name>` directly".
- **Step 3 (dry-run):** when a predecessor was named, also run
  `record-supersession --dry-run --assume-registered --agent <a> --old <old>
  --new <name>`. Relay its `RECORDED`/`WARN`/`SKIPPED`/`BLOCKED` lines using
  the same rules as the promote-config list.
  - `BLOCKED:in_seed` (the old model is still a seed default): offer
    "Promote instead (re-run with --promote)", "Register without lineage" or
    "Abort".
  - `BLOCKED:conflict|cycle|seed_invariant`: offer only "Register without
    lineage" or "Abort".
  - In promote mode, if `promote-config` already printed `RECORDED:` for the
    same old model, skip the explicit call, because it would be a duplicate.
- **Step 4 (confirm/apply):**
  - When an edge is previewed (implicit or explicit), add the option "Apply
    without recording supersession" in add mode too. It sets `record_lineage =
    false`, as defined above, which suppresses both recording paths.
  - Apply order: `add-json` → `promote-config` → `record-supersession` (only if
    `record_lineage` and a predecessor was named and not already recorded by
    promote-config) → `promote-default-agent-string` (drop the ones that do not
    apply).
  - **If an apply call fails:**
    1. **Stop** the remaining calls.
    2. Report which calls succeeded and which one failed, with its output.
    3. Report the **actual saved state** by looking at it, not by trusting exit
       statuses: a failed call can have written some of its files.
       - `./ait git status --short -- aitasks/metadata/models_<agent>.json
         aitasks/metadata/codeagent_config.json`
       - `git status --short -- seed/ .aitask-scripts/lib/model_supersessions.json`
       - Do not relay a helper's "Nothing was written" as describing the whole
         operation.
    4. If the model is registered but its predecessor link is missing, give
       the targeted retry: `record-supersession --agent <a> --old <old> --new
       <name>`, once the BLOCKED cause is resolved. Re-running the skill with
       the same `--name` would stop at the duplicate check.

    General promotion recovery is out of scope (see Follow-ups).
- **Step 6 (commit), goal 1:** change the "Supersession table" condition to
  "when `promote-config` **or `record-supersession`** printed `NOTE: commit
  .aitask-scripts/lib/model_supersessions.json`". Drop "promote mode".
- **Notes:** rewrite the supersession bullet to point at the Step 1 question
  and the `--supersedes` flag, and keep the manual `record-supersession`
  command for later declarations. Add one line saying OpenCode has no
  supersession lineages yet (it is refused here, as before).

### 4. Backfill missing lineages (goal 3)

For each candidate edge:

1. Run `./.aitask-scripts/aitask_add_model.sh record-supersession --dry-run
   --agent <a> --old <old> --new <new>`.
2. Show the user the result lines and the diff.
3. Confirm each edge with `AskUserQuestion` (multiSelect, at most 4 edges per
   question, each option one edge with its rationale).
4. Apply only the confirmed edges, in chain order.

`_1m` siblings are handled by the existing sibling rule. For example,
`opus4_7_1m` already points to `opus4_8`, so `opus4_7 → opus4_8` reports
`SKIPPED:sibling_conflict`, which is informational. No candidate is a seed
default; today's seed uses only opus5_5, sonnet5_5 and gpt6_1_sol.

Candidates:

**claudecode** (immediate successor; the chain resolves to the newest
registered model):

- `fable5 → fable5_1`
- `opus4_5 → opus4_6`
- `sonnet4_5 → sonnet4_6`
- `opus4_7 → opus4_8`

**codex** — lineage is judged from the registry notes. The uncertain ones are
flagged and the user decides:

- `gpt5_2 → gpt5_4` ("Previous general-purpose")
- `gpt5_4 → gpt5_5`
- `gpt5_5 → gpt5_6_sol` (flagship tier)
- `gpt5_6_sol → gpt6_sol` (flagship; then reaches `gpt6_1_sol` through the
  existing edge)
- `gpt5_6_luna → gpt6_luna` (fast/affordable tier)
- uncertain:
  - `gpt5_3codex → gpt5_4` (notes: its coding capabilities power GPT-5.4)
  - `gpt5_4_mini → gpt5_6_luna` (small tier)
  - `gpt5_6_terra → ?` (no gpt6 balanced tier; propose none)
  - `gpt5_3codex_spark` (research preview; propose none)

Existing contract tests guard the shipped table: `ShippedTableTests` in
`tests/test_model_supersession.py` checks canonical format, that every edge is
registered in seed, that the chain is acyclic, the same-family rule, the seed
invariant and sibling completeness.

### 5. OpenCode decision (goal 4)

- Docs: add one sentence to
  `website/content/docs/commands/codeagent.md#superseded-model-defaults` saying
  supersessions are recorded for claudecode and codex models, and OpenCode
  models have none yet. The add-model skill Notes line comes from step 3.
- Create a follow-up task with `aitask_create.sh --batch` (after approval,
  during implementation). Proposed title "OpenCode model supersession
  lineages", labels `codeagent, models, model_selection`, anchor 1916. Its
  scope:
  - let `record-supersession` accept opencode, or add an opencode-only
    recording path;
  - define family/lineage for provider-prefixed names, e.g. compare after
    stripping `<provider>_` (`opencode_claude_opus_4_5` →
    `opencode_claude_opus_4_6`);
  - backfill against the t1919-refreshed registry (unavailable entries are
    never offered);
  - decide whether `aitask_opencode_models.sh` refreshes should propose edges.

### 6. Port to other agent trees (goal 5)

`.agents/skills/aitask-add-model/SKILL.md`,
`.opencode/skills/aitask-add-model/SKILL.md` and
`.opencode/commands/aitask-add-model.md` are thin wrappers that tell the agent
to read and follow `.claude/skills/aitask-add-model/SKILL.md`. The workflow
content, including t1910's supersession steps, is therefore already inherited,
and the "0 mentions" in the task is expected for a wrapper. The only part that
needs porting is the OpenCode skill wrapper's `## Arguments` line, which lists
the flags explicitly: add `--supersedes <old>`. No separate port tasks are
needed.

### 7. Website docs — `website/content/docs/skills/aitask-add-model.md`

- Document the lineage question and `--supersedes` (add-only and promote).
- Note that the dry-run previews the edge.
- Keep the existing `record-supersession` bullet for later declarations.
- Follow the current-state-only rule.

## Verification

- `bash tests/test_add_model.sh`
- `python3 tests/test_model_supersession.py` (the shipped-table contract
  covers the backfilled edges)
- `bash tests/test_install_superseded_models.sh`
- `python3 tests/test_install_superseded_prompt_pty.py`
- `shellcheck .aitask-scripts/aitask_add_model.sh`
- `./.aitask-scripts/aitask_add_model.sh record-supersession --dry-run
  --assume-registered --agent claudecode --old haiku5_5 --new haiku9` is a
  preview with `NOTE:assumes_registration`. Without `--dry-run` it is a usage
  error.
- `ait codeagent check-superseded --report` in this repo lists any project op
  that now gets a new offer. This is a sanity check only.
- `cd website && python3 check_links.py --build`
- `grep -n "record-supersession" .claude/skills/aitask-add-model/SKILL.md`
  shows Step 6's commit condition naming it.

## Commits

- Code, skill, tests, docs and wrappers on `main`, scoped with `git commit --
  <paths>`: `enhancement: … (t1927)`.
- The supersession table backfill is a separate scoped commit on `main`: `ait:
  Backfill model supersession lineages (t1927)`.
- The follow-up task is committed by `aitask_create.sh`.

## Follow-ups (offered, not created automatically)

- General add-model apply recovery and concurrency handling: identifying what
  a failed `promote-config` / `add-json` partially wrote, separating it from
  other sessions' edits, recovery commits, and the `promote-config` retry that
  records nothing once seed config is already written. Offered at Step 8 as a
  separate task.

## Post-implementation

Step 9 (Post-Implementation) covers review, archival and merge (current branch,
so there is no merge).

## Risk

### Code-health risk: low
- `--assume-registered` on `record-supersession` loosens a t1910 guard. It
  stays bounded to `--dry-run`, which writes nothing, and the apply path still
  validates against the real registry. Tests pin both directions. · severity:
  low · → mitigation: none needed (step 2 tests)
- A second recording path (the explicit `record-supersession` in the skill)
  could ignore the user's opt-out, or leave a registered model without its
  lineage after a mid-sequence failure. · severity: low (residual after the in-plan fixes) · → mitigation:
  none needed (addressed in-plan: the single `record_lineage` decision and
  the stop/report/retry instructions in step 3, plus the required integration
  case in step 2)

### Goal-achievement risk: medium
- Codex lineage is inferred from release notes and tier names (sol/terra/luna,
  mini, codex). A wrong edge would offer users an unsuitable model on `ait
  upgrade`. The offer is never auto-applied (the user is asked per model), and
  every edge is dry-run reviewed and confirmed per edge in step 4, with the
  uncertain ones flagged or proposed as none. · severity: medium · →
  mitigation: none needed (per-edge confirmation is built into step 4)
- OpenCode is deferred, so goal 4 is delivered as a decision plus a follow-up
  task rather than as recorded edges, which is the scope the user chose. ·
  severity: low · → mitigation: follow-up task created in step 5
