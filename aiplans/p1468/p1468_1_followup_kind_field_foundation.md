---
Task: t1468_1_followup_kind_field_foundation.md
Parent Task: aitasks/t1468_mark_followup_task_provenance_and_surface_on_board.md
Sibling Tasks: aitasks/t1468/t1468_2_*.md, aitasks/t1468/t1468_3_*.md, aitasks/t1468/t1468_4_*.md, aitasks/t1468/t1468_5_*.md, aitasks/t1468/t1468_6_*.md
Archived Sibling Plans: aiplans/archived/p1468/p1468_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-10 18:20
---

# p1468_1 — `followup_kind` frontmatter field foundation

## Context

44% of active tasks are auto-spawned follow-ups and 95 of them carry no marker at
all, so the board and pick queue can no longer be used to choose genuinely *new*
work. The parent plan
`aiplans/p1468_mark_followup_task_provenance_and_surface_on_board.md` records the
design decision (a new orthogonal scalar `followup_kind:`) and why the two
alternatives were rejected — **do not re-litigate it**.

This is the foundation child: it registers the field and makes it survive every
round-trip. Nothing in t1468_2..t1468_7 is meaningful until this lands. The
field's *emission* at creation seams is t1468_2; board rendering is t1468_3.

**Verified against current source during re-planning.** Two design corrections
came out of that verification and are folded in below (vocabulary home; merge
resolver). Line numbers in this plan are the re-verified current ones.

---

## Pre-phase (risk mitigations)

Runs **before** step 1. All three are inline, confirmed at planning.

1. **[negctrl_field_destruction]** Write the round-trip test in its **final
   form** — a fixture task with a hand-added `followup_kind: risk_mitigation`
   line, run an *unrelated* `aitask_update.sh --batch <id> --status Ready`,
   assert the line **survives**. Run it now against unmodified source and confirm
   it goes **RED**. Record the failing test id and the exact failure message in
   Final Implementation Notes. At the end the same assertion, **byte-unchanged**,
   must pass. Asserting the *destroyed* state instead would go green against
   today's broken behaviour and prove nothing.

2. **[boardgroup_resolver_regression_guard]** Before touching
   `_resolve_base_aware`, run `bash tests/test_aitask_merge_boardgroup.sh` and
   the `TestBoardgroupBaseAwareMerge` class in `tests/test_aitask_merge.py` and
   record the passing baseline in Final Implementation Notes. After the signature
   change, both must pass **unchanged** — no test edits. `boardgroup` landed
   recently (t1243_8, commit `16afd191d`) and is the only current user of this
   resolver; a silent behaviour change there mis-resolves board-group membership
   on sync.

3. **[phantom_stub_visibility_probe]** Add a test pinning that a task file
   carrying **only** board keys plus `followup_kind` is **no longer** a phantom
   stub. Four readers share this predicate — `board/aitask_board.py:1348-1350`
   `TaskManager._is_phantom_stub` (the original), `lib/board_columns.py:483`
   (inverted polarity), `lib/trail_gather.py:313-314`,
   `lib/work_report_gather.py:180-181`. This is the intended consequence of
   keeping the field out of `BOARD_KEYS`, but it changes visibility for four
   surfaces and touches board fixtures (`tests/lib/board_fixture.py:101,159`),
   so it is pinned rather than left incidental.

---

## Implementation steps

### 1. Vocabulary — Python source of truth + shell bridge

**Design correction.** The task file specifies a `followup_kinds.tsv` read by two
independent parsers. Verification found **no precedent**: there are zero `.tsv`
files repo-wide and no shell script anywhere reads a data file out of `lib/`.
Two parsers can also disagree on quoting and blank lines. Instead follow the
repo's established seam for a closed enum shared by bash and Python —
`lib/launch_modes.py` + `lib/launch_modes_sh.sh` — where bash **derives** the
vocabulary rather than mirroring it, so drift is impossible by construction.

**1.1 `.aitask-scripts/lib/followup_kinds.py`** — the single source of truth. An
ordered mapping `kind → (glyph, colour, label)`, plus `VALID_FOLLOWUP_KINDS`, a
`followup_kinds_pipe()` (sorted, pipe-separated, for shell regex consumers) and
a `normalize_followup_kind()` used by the merge resolver. Colour assignment is
**families**: colour signals severity class, glyph distinguishes kind.

| kind | glyph | colour |
|---|---|---|
| `manual_verification` | `◇` | `cyan` |
| `risk_mitigation` | `▲` | `yellow` |
| `upstream_defect` | `▼` | `red` |
| `verification_failure` | `✗` | `red` |
| `carry_over` | `↻` | `cyan` |
| `qa_test_gap` | `◐` | `magenta` |
| `review_finding` | `◈` | `magenta` |
| `docs_gap` | `▤` | `bright_black` |

All eight are East-Asian-Width *Ambiguous* (width 1 outside CJK locales), the
same class as the house precedent `TRAIL_CLASSIFICATION_GLYPHS`
(`board/aitask_board.py:617-626` — `◆ ▲ ● ⇄ ○`). t1468_3 owns render-level width
and colour verification; pick conservatively here so it need not renegotiate.

**1.2 `.aitask-scripts/lib/followup_kinds_sh.sh`** — thin bridge, modelled on
`launch_modes_sh.sh` but **lazy**. `launch_modes_sh.sh` computes eagerly at
source time; here that would add a Python subprocess to *every* `ait create` /
`ait update` invocation, and t1468_6's backfill loops `aitask_update.sh` over
~171 tasks. So expose a function that shells out on first call and memoises:

```bash
[[ -n "${_AIT_FOLLOWUP_KINDS_LOADED:-}" ]] && return 0
_AIT_FOLLOWUP_KINDS_LOADED=1
_AIT_FOLLOWUP_KINDS_PIPE=""

followup_kinds_pipe() {
    [[ -n "$_AIT_FOLLOWUP_KINDS_PIPE" ]] && { printf '%s' "$_AIT_FOLLOWUP_KINDS_PIPE"; return 0; }
    local dir="${AIT_FOLLOWUP_KINDS_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
    local pycmd="${_AIT_RESOLVED_PYTHON:-python3}"
    _AIT_FOLLOWUP_KINDS_PIPE="$("$pycmd" -c "
import sys
sys.path.insert(0, '$dir')
from followup_kinds import followup_kinds_pipe
sys.stdout.write(followup_kinds_pipe())
")" || return 1
    printf '%s' "$_AIT_FOLLOWUP_KINDS_PIPE"
}

is_valid_followup_kind() { [[ "$1" =~ ^($(followup_kinds_pipe))$ ]]; }
```

Keep the `AIT_FOLLOWUP_KINDS_DIR` test hook and the `_AIT_RESOLVED_PYTHON`
fallback comment, both copied from `launch_modes_sh.sh`. **Fail closed**: if the
bridge cannot resolve the vocabulary, validation must `die`, never accept.

**No install plumbing is needed** — `.aitask-scripts/` ships wholesale
(`.github/workflows/release.yml:87-96`, `install.sh:1256`); this is exactly why
`implementation_trail.schema.json` lives under `lib/`. **But** every shell test
that scaffolds a fake repo must `cp` both new files explicitly:
`tests/lib/test_scaffold.sh` copies only the unconditional system libs.

### 2. `aitask_create.sh` — the `anchor` pattern, not the `verifies` pattern

All three serializers read the **global** `RESOLVED_ANCHOR`; none takes a
positional, and the same is true of `BATCH_GATES` / `BATCH_ALSO_BLOCKS_DEPENDENTS`.
Do **not** add a 17th positional.

| # | site | line |
|---|---|---|
| 1 | `BATCH_FOLLOWUP_KIND=""` global, beside `BATCH_ANCHOR` | `:48` |
| 2 | usage text, beside `--anchor` / `--followup-of` | **`:88-95`** (not `:115`) |
| 3 | arg parse `--followup-kind) BATCH_FOLLOWUP_KIND="$2"; shift 2 ;;` | `:191-192` |
| 4 | enum validation, beside the `resolve_anchor` call — **before any file is written** | `:2017` |
| 5 | emit in `create_child_task_file` | `:556-559` |
| 6 | emit in `create_draft_file` | `:693-696` |
| 7 | emit in `create_task_file` | `:1892-1895` |

All three emit blocks are byte-identical today; mirror them exactly:

```bash
        # Only write followup_kind (auto-spawned follow-up provenance) if present
        if [[ -n "$BATCH_FOLLOWUP_KIND" ]]; then
            echo "followup_kind: $BATCH_FOLLOWUP_KIND"
        fi
```

Missing `create_draft_file` means the field vanishes on any draft-based creation.
`finalize_draft()` (`:794`) needs **no change** — its copies at `:823` / `:859`
are `sed` delete-lists, not re-serializations, so any key passes through
verbatim. Still add the draft→finalize test (`tests/test_anchor_create.sh:270-283`
is the analogue).

Validation shape: the inline `case` allowlist at `:2007-2010` is the minimal-diff
precedent, guarded by `[[ -n "$BATCH_FOLLOWUP_KIND" ]]` so the field stays
optional.

### 3. `aitask_update.sh` — eleven sites, all of them

A missed site is silent data loss, not a visible failure. The read `case` at
`:511-579` has **no `*)` arm** (33 keys allowlisted) and `write_task_file`
rebuilds frontmatter from scratch, so an unregistered key dies on every rewrite.

| # | site | line | shape to copy |
|---|---|---|---|
| 1 | `BATCH_FOLLOWUP_KIND`, `BATCH_FOLLOWUP_KIND_SET` | `:92-93` | `BATCH_ANCHOR*` |
| 2 | `CURRENT_FOLLOWUP_KIND` | **`:135`** (not `:127`) | `CURRENT_ANCHOR` |
| 3 | usage text | `:241-243` | anchor block |
| 4 | arg parse (value **and** `_SET` flag) | `:356` | `--anchor` |
| 5 | **default reset** in `parse_yaml_frontmatter` | `:461` | `CURRENT_ANCHOR=""` |
| 6 | READ arm in `case "$key" in` | `:560` | `anchor) CURRENT_ANCHOR="$value" ;;` |
| 7 | `write_task_file` **positional arg 33** | after `:665` | see below |
| 8 | emit in `_ait_write_task_file_body` | `:792-795` | anchor emit |
| 9 | call site — parent children cleanup | `:1161-1170` | `CURRENT_*` |
| 10 | call site — interactive write | `:1679-1688` | `CURRENT_*` |
| 11 | call site — batch write | `:2110-2118` | `new_*` |
| 12 | `has_update` gating | `:1796` | `BATCH_ANCHOR_SET` |
| 13 | batch merge `new_followup_kind` | `:2018-2023` | `new_anchor` |
| 14 | validation in `main()` | `:2276-2280` | `--boardgroup` slug check |

**Site 5 is load-bearing and easy to miss.** Several existing `CURRENT_*` vars
(`CURRENT_PULL_REQUEST`, `CURRENT_CONTRIBUTOR`, `CURRENT_VERIFIES`) are set in
the case arm but absent from the reset block — a looping invocation leaks the
previous task's value into the next file. Add to **both** `:428-472` and
`:511-579`.

**Arg 33, appended — not inserted.** Positionals currently end at 32
(`boardgroup_present="${32:-false}"`), and the comment at `:660-663` states the
convention: inserting mid-list silently renumbers every read above. All three
call sites currently end with the boardgroup pair, so arg 33 goes after those.

**Clearing is key removal, no tombstone.** The emit uses `if [[ -n … ]]`, so
`--followup-kind ""` omits the line. Unlike `boardgroup`, this field needs **no**
`_present` companion positional — it follows `anchor` (single positional). The
merge rule in step 5 depends on this.

Validation follows `--boardgroup`'s **reject, never coerce** shape (`:2270-2280`):
a bad value dies with a named error and leaves the file byte-unchanged. Never
normalize — the value is an identity key.

### 4. Cross-field invariant (both scripts)

The invariant: `followup_kind: manual_verification` ⇒ `issue_type:
manual_verification`. The converse stays legal — an `issue_type:
manual_verification` task may carry `followup_kind: carry_over`.

**It must be evaluated on both *resulting* values, and there are two ways to
violate it — supplying the kind, or removing the type.** A task already carrying
both fields can be broken by `--type feature` *alone*, leaving a stored
`followup_kind: manual_verification` orphaned. A flag-level check catches only
the first.

**Placement matters and the obvious spot does not work.** `run_batch_mode`
computes `new_type="${BATCH_TYPE:-$CURRENT_TYPE}"` at `:1921` and is invoked at
`:2287` — *after* `main()`'s flag validation at `:2252-2280`. A check placed
beside the `--boardgroup` validation therefore structurally cannot see the
resulting type. Enforce instead in a small shared helper —
`enforce_manual_verification_kind_invariant <resulting_type> <resulting_kind>`,
naming mirrored from `aitask_create.sh`'s existing
`enforce_manual_verification_gate_invariant` — called from **both** update write
paths, after the resulting values exist and **before** `write_task_file`:

- batch path: after `new_type` (`:1921`) and the `new_followup_kind` merge
  (`:2018-2023`), before the write at `:2110`;
- interactive path: after `new_type` (`:1544` / `:1614`), before the write at
  `:1679`.

In `aitask_create.sh` a flag-level check at `:2017` is sufficient — for a new
file the resulting values *are* the flags.

Named error, non-zero exit, file byte-unchanged.

Enforce at the write seams; **tolerate at read** — the board normaliser must not
crash on a hand-edited inconsistency (t1468_7 verifies exactly that).

### 5. `aitask_merge.py` — make the resolver deletion-aware

Newer-`updated_at`-wins is **wrong** here; do not copy the `anchor` branch
(`:312-315`). `merge_frontmatter` resolves one-sided presence at `:288-294`
*before* any field rule, and `:268-270` says so: that branch "is unconditional and
would resurrect a value the other side deliberately cleared." A misclassification
must be correctable — including by clearing — so a clear has to survive sync,
which only base comparison delivers.

`_resolve_base_aware` (`:189`) cannot be reused as-is:

1. **Presence.** `present` is False only when *neither* side has the key
   (computed at **`:202-205`**, not in the docstring at `:194-196`). When the
   winning side *deleted* it, the resolver returns `None` and the **caller** at
   `:271-278` still executes `merged[key] = value`, so `serialize_frontmatter`
   writes a literal `followup_kind: null`. Verified empirically: serialize is
   membership-driven (`if key in metadata`), never a None check. **Real removal
   requires skipping the assignment**, exactly as the active-tuple block at
   `:262-266` does — returning a different value is not enough.
2. **Normaliser.** It compares through `normalize_group_slug` — boardgroup's
   tombstone semantics, the wrong vocabulary here.

**Fix:** make the resolver **deletion-aware and normaliser-parameterised** —
return the *winning side's* presence separately from its value, and take the
comparison normaliser as an argument. Keep `boardgroup` byte-identical (it relies
on its persisted `""` tombstone and its present-when-either-side-has-it
semantics); `followup_kind` passes `normalize_followup_kind` and deletion-aware
presence. Then add `followup_kind` to `_BASE_AWARE_FIELDS` (`:164`) with a
comment naming both defects.

Add it to **none** of `_LIST_UNION_FIELDS` (`:135`), `BOARD_LAYOUT_KEYS` or
`BOARD_KEYS` (`lib/task_yaml.py:55,69`) — four readers treat
"metadata ⊆ BOARD_KEYS" as "no real metadata" (see pre-phase 3).

Leave `tests/test_aitask_merge.py:735-748`
(`test_one_sided_presence_resurrects_a_deleted_field`) alone — it pins the
resurrection defect using `anchor` as stand-in and stays valid.

### 6. `aitask_fold_mark.sh`

No-op. Add an explanatory comment at `:324`, beside the `anchor` (`:315-317`) and
`boardgroup` (`:319-323`) no-op comments, in the same free-standing-paragraph
shape: instance-specific scalar provenance, the primary keeps its own, folded
files are deleted at archival anyway.

### 7. Documentation — Layer 5, all of it

Per `aidocs/framework/aitasks_extension_points.md:42-63`:

- `seed/aitasks_agent_instructions.seed.md` "## Task File Format" (YAML block
  `:10-29`) **and** `aitasks/metadata/aitasks_agent_instructions.seed.md` —
  `assemble_aitasks_instructions` (`aitask_setup.sh:1279-1314`) reads the
  metadata copy **first**, so editing `seed/` alone is insufficient in this repo.
  Then regenerate the `AGENTS.md` mirror via `ait setup`.
- `.codex/instructions.md` / `.opencode/instructions.md` — **correction:** the
  extension-points doc says these are "markerless … do not run
  `insert_aitasks_instructions`". That is **false today** — both are fully
  `>>>aitasks`-wrapped and setup-generated (`aitask_setup.sh:2352-2358`,
  `:2502-2509`). They regenerate; **fix that stale sentence** as part of this
  work.
- `CLAUDE.md` "### Task File Format" (`:111-132`) — genuinely hand-maintained, no
  markers.
- `website/content/docs/development/task-format.md` "### Frontmatter Fields"
  table (`:32-65`). Note `boardgroup` is already missing from this table — add
  `followup_kind` correctly; fixing the `boardgroup` gap is out of scope.
- `aidocs/framework/aitasks_extension_points.md` — add `followup_kind` as a third
  worked example beside `anchor` (`:65-70`), naming the merge-resolver wrinkle so
  the next scalar field does not repeat it.
- `.claude/skills/task-workflow/task-creation-batch.md` — Input table row
  (`~:20`) only; the flag's *emission* is t1468_2. **Verified variant inventory
  (do not trust a shorter count):** editing the canonical file produces **nine**
  rendered outputs — 3 profiles (`default`, `fast`, `remote`) × 3 agent trees
  (`.claude/skills/`, `.agents/skills/…-codex-`, `.opencode/skills/`) — of which
  exactly **three are tracked in git**, the `remote` one per tree:

  | tree | default | fast | remote |
  |---|---|---|---|
  | `.claude/skills/` | gitignored | gitignored | **tracked** |
  | `.agents/skills/…-codex-` | gitignored | gitignored | **tracked** |
  | `.opencode/skills/` | gitignored | gitignored | **tracked** |

  So: **run the rerender once per profile — `default`, `fast` and `remote`, all
  three** (a driver call takes a profile argument; omitting one leaves that
  profile's local copies stale), then stage the canonical source **plus the three
  tracked remote copies** via an explicit path allowlist. Do not hand-edit any
  variant. Run `./.aitask-scripts/aitask_skill_verify.sh` and regenerate any
  affected goldens in the same commit — note
  `tests/fixtures/skills/task-workflow/task-creation-batch.md.pre-rewrite` is a
  fixture, not a render target; check whether it is compared against live content
  before touching it.
- `.claude/skills/aitask-create/SKILL.md` inline flag list (`:270-289`) — follow
  the pointer convention at `:285` ("specified once in the canonical contract")
  rather than restating semantics.

---

## Verification

1. **negctrl_field_destruction**: RED before implementation (record the test id
   and message), GREEN after, assertion **byte-unchanged**.
2. New round-trip test (clone `tests/test_gate_frontmatter_roundtrip.sh`'s Part-A
   no-git fixture + `tests/test_anchor_update.sh:187`): durability under an
   unrelated `--status` update; set; clear (line **absent**, not empty);
   read-modify-write; invalid kind rejected non-zero with the file byte-unchanged;
   a task never created with the flag never gains an empty field;
   draft→finalize carry-through. Remember to `cp` `lib/followup_kinds.py` and
   `lib/followup_kinds_sh.sh` into the scaffolded repo.
3. Merge tests — extend `tests/test_aitask_merge_boardgroup.sh` (parameterise its
   `parsed_boardgroup()` helper at `:30-45`, which already distinguishes
   `ABSENT` / `NoneType:None` / `str:''`) and `tests/test_aitask_merge.py`
   (clone `TestBoardgroupBaseAwareMerge`, `:512-662`):
   - one side clears, other unchanged ⇒ `self.assertNotIn("followup_kind", merged)`
     **and** the serialized file has no `followup_kind:` line — assert absence,
     not `== None`;
   - both sides changed differently ⇒ `PARTIAL:followup_kind`;
   - no base available ⇒ `PARTIAL` naming the field;
   - **boardgroup_resolver_regression_guard**: every existing `boardgroup` case
     passes unchanged, with no test edits.
4. **phantom_stub_visibility_probe** passes across all four readers.
5. **Per-call-site preservation coverage.** The three `write_task_file` call
   sites pass independent argument lists — none delegates to another — so a
   missed arg 33 at one site destroys the field on that route while a
   batch-only durability test stays green. Cover each:
   - **batch write (`:2110`)** — covered by test 2.
   - **parent children-cleanup (`:1161`)** — behaviourally reachable without a
     TTY: `handle_child_task_completion` fires from the batch path at `:2122`
     when the id matches `<parent>_<child>` *and* the new status is exactly
     `Done` (`:1101-1108`). Set `followup_kind` on the **parent**, run
     `aitask_update.sh --batch <p>_<c> --status Done` on a child, and assert the
     **parent's** `followup_kind` survives — this route rewrites the parent file,
     not the child's.
   - **interactive / non-batch write (`:1679`)** — fzf-driven and not driveable
     non-interactively. Cover it structurally instead: assert the source passes
     the new positional at every call site — exactly two occurrences of
     `"$CURRENT_FOLLOWUP_KIND"` (sites `:1161` and `:1679`) and one of
     `"$new_followup_kind"` (site `:2110`). Assert the counts, not mere presence,
     so a site added later without the argument fails the test.
6. **Cross-field invariant — both violation directions and the legal transition:**
   - kind-only: `--followup-kind manual_verification` on a `feature` task →
     rejected non-zero, file byte-unchanged;
   - **type-only:** a task already carrying `issue_type: manual_verification` +
     `followup_kind: manual_verification`, updated with `--type feature` **and no
     kind flag** → rejected non-zero, file byte-unchanged. This is the case a
     flag-level check misses;
   - **paired transition accepted:** `--type feature --followup-kind carry_over`
     in one call → succeeds, both fields written;
   - converse pairing accepted: `issue_type: manual_verification` +
     `followup_kind: carry_over`.
7. Bridge fail-closed: with the vocabulary module unreachable
   (`AIT_FOLLOWUP_KINDS_DIR` pointed at an empty dir), validation **dies** rather
   than accepting an arbitrary value.
8. `bash tests/run_all_python_tests.sh` — read the **last** line for the verdict
   (`set -o pipefail` if piping).
9. `shellcheck .aitask-scripts/aitask_create.sh .aitask-scripts/aitask_update.sh
   .aitask-scripts/aitask_fold_mark.sh .aitask-scripts/lib/followup_kinds_sh.sh`

---

## Risk

### Code-health risk: medium

- Missing one of the ~14 `aitask_update.sh` registration sites silently and
  irrecoverably destroys the field on the next unrelated update — no error, no
  test failure unless specifically tested · severity: medium (residual —
  addressed by inline pre-phase `negctrl_field_destruction`) · → mitigation:
  inline pre-phase negctrl_field_destruction
- Changing `_resolve_base_aware`'s signature alters a live merge path that
  freshly-landed `boardgroup` (t1243_8) depends on; a regression there silently
  mis-resolves board-group membership on sync · severity: medium (residual —
  addressed by inline pre-phase `boardgroup_resolver_regression_guard`) · →
  mitigation: inline pre-phase boardgroup_resolver_regression_guard
- Wide blast radius that no control removes: two bash scripts, a shared Python
  resolver, two new lib files, eight documentation surfaces and nine generated
  skill variants (three of them tracked) · severity: medium · → mitigation: none

### Goal-achievement risk: medium

- The cross-field invariant must test the *resulting* `issue_type` after the batch
  merge rather than the flag, and must be placed inside the write paths — the
  natural validation site in `main()` runs before `run_batch_mode` computes
  `new_type`, so a check there cannot see the resulting value and would silently
  miss the type-only violation · severity: medium · → mitigation: none (covered
  by verification step 6, which pins both violation directions and the legal
  paired transition)
- The three `write_task_file` call sites pass independent argument lists, so a
  missed positional at the parent-cleanup or interactive site destroys the field
  on that route while the main durability test stays green · severity: medium ·
  → mitigation: none (covered by verification step 5 — behavioural coverage for
  the batch and parent-cleanup routes, a call-site count assertion for the
  interactive one)
- Keeping the field out of `BOARD_KEYS` makes a board-keys-only file carrying
  `followup_kind` stop being a phantom stub in four readers, changing visibility
  for surfaces this task does not otherwise touch · severity: low (residual —
  addressed by inline pre-phase `phantom_stub_visibility_probe`) · → mitigation:
  inline pre-phase phantom_stub_visibility_probe

### Planned mitigations
- timing: pre-phase | name: negctrl_field_destruction | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: silent field destruction across the update.sh registration sites | desc: write the round-trip durability test in final form and confirm RED before any registration site is touched
- timing: pre-phase | name: boardgroup_resolver_regression_guard | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: regression in the boardgroup merge path sharing _resolve_base_aware | desc: record the passing boardgroup merge baseline before the signature change and require it to pass unchanged after
- timing: pre-phase | name: phantom_stub_visibility_probe | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: unintended phantom-stub visibility change in four readers | desc: pin that a board-keys-only file carrying followup_kind is no longer a phantom stub across all four _is_phantom_stub readers

---

## Notes for sibling tasks

- **Vocabulary home changed from the task file's spec.** It is
  `lib/followup_kinds.py` (source of truth) + `lib/followup_kinds_sh.sh` (bridge),
  **not** `followup_kinds.tsv`. t1468_3 imports the Python module directly;
  t1468_4's bash surfaces source the bridge. Rationale: no repo precedent for a
  dual-parser data file; the launch_modes seam makes drift impossible.
- Glyph/colour are **families** — colour signals severity class, glyph
  distinguishes kind. t1468_3 owns render-level width and colour verification.
- Clearing is key removal with **no tombstone** — any sibling reading the field
  must treat *absent* as "not a follow-up".
- `_resolve_base_aware`'s signature changes here. A sibling touching
  `aitask_merge.py` should read the new contract first.
- The `followup_kind` row in `task-creation-batch.md`'s Input table lands here;
  t1468_2 adds the flag *emission* and must re-render again. **Editing that file
  produces nine rendered outputs (3 profiles × 3 agent trees); exactly three are
  tracked — the `remote` copy in each tree.** Rerender for `default`, `fast` and
  `remote`, stage canonical + the three remote copies with an explicit allowlist.
- The cross-field invariant lives in a shared helper called from both update
  write paths, not in `main()`'s flag validation — `run_batch_mode` computes the
  resulting `issue_type` only at `:1921`, long after `main()`'s checks run.
- `aidocs/framework/aitasks_extension_points.md`'s "markerless" claim about
  `.codex` / `.opencode` instructions is corrected here — later children can
  trust the doc.
