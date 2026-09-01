---
Task: t1647_merge_trails_skill_shared_helpers_board_command_docs.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1647 — Trail-to-trail merge (fold): decomposition plan

## Context

The implementation-trail subsystem (t1210 family) can create, refresh, and show
trails, but has no way to **merge two trails** into one. Two real scenarios
drive this: a trail created without realizing a similar one exists (live case:
t1118 owns both `art:trail-mobile-shadow-driving` (lite) and
`art:trail-mobile-shadow-driving-deep` (deep) with identical 6-entry
membership), and a feature whose scope expanded across two trails. The
architecture is settled in the task: a dedicated `/aitask-merge-trails` skill
(not an overload of `/aitask-trail`'s pinned 3-mode grammar), a `merge-trails`
codeagent operation, shared lib helpers promoted out of the board, a board
By-Trail launch command, and docs. **This is a decomposing parent**: the plan
creates 6 implementation children + 1 aggregate manual-verification sibling.

## Decisions settled with the user (PINNED — do not re-decide in children)

1. **Depth reconciliation — deep wins.** Merged depth = `deep` if EITHER source
   is deep, else `lite`. Explicit `--lite`/`--deep` override; a downgrade that
   drops material requires a confirmation naming exactly what is dropped
   (counts of observations/relations/exclusions/evidence). The depth decision
   is made by the preflight script (emits `RESULT_DEPTH:`), the skill copies it
   into `--expect-depth` at validation — same "script decides, model copies"
   pattern as `aitask_trail_depth.sh` (t1505_4).
2. **Board key: `F` — "Fold Trails"** in By-Trail (free at App level; matches
   the framework's fold vocabulary; capital like the other agent-launching
   trail key `R`).
3. **Split: 6 children + manual verification** (below).

## Facts corrected against the task description (verified this session)

- **t1210_5 and t1210_6 have landed** (archived), not Ready as the task
  records. Consequences: `m`/`M` are now taken in By-Trail
  (`move_to_column` / `trail_move_wave`, `aitask_board.py:9004/9011`) — no
  coordination needed, just avoid them; and
  `website/content/docs/workflows/implementation-trails.md` **exists** — the
  docs child extends it instead of depending on t1210_6.
- Board seam line numbers moved: `trail_entry_refs:1258`,
  `compute_trail_overlaps:1294`, `dedupe_trail_records:1329`,
  `load_trail_blob:1453`, `discover_trails:1490`, `TrailSelectScreen:4471`,
  `PickerItem:4335`, `MergeColumnsConfirmScreen:8219`, `_launch_trail:12181`.
- Wave-entry task ref key is `task` (not `task_ref`).
- The Modal Dialogs Reference table (`reference.md:499`) now lists the By-Trail
  move modal but still **no** Trail Select / Trail Detail rows — close that gap
  with the merge dialog rows.
- **Cross-agent stubs cannot be deferred**: `tests/test_skill_dispatch_contract.sh`
  discovers templated skills at runtime (`find .claude/skills -name SKILL.md.j2`)
  and immediately requires all three agent surfaces + closure. The skill child
  ships all stubs in one commit (exception to the usual "separate aitasks for
  other agents" rule — the test forces it).
- `test_implementation_trail_design.py::test_no_unexpected_fixture_files` pins
  `FIXTURE_NAMES` — adding a merge fixture requires editing that list.

## In-flight coordination (re-verified 2026-09-01, after the task-data refresh)

- **t1603_4 and t1666 have landed** (archived; t1603_4's board commit
  `fdbc5cf90` is in this checkout, so the line anchors above already reflect
  it). The task's "sequence board children after t1603_4" constraint is
  satisfied.
- **t1603_5 (Implementing)** edits `website/content/docs/tuis/board/reference.md`
  (Task Card Anatomy ~94, View Filters ~196, Task Metadata Fields ~397) —
  disjoint from our By-Trail (~242) and Modal Dialogs (~499) sections, but the
  same file: **t1647_6 must re-verify section anchors and rebase around
  t1603_5** (it is last in our chain, so t1603_5 will normally have landed).
- **t1658_2 + t1599_3 (Implementing)** rework data-worktree/sync-commit
  plumbing — no shared edit surface (we only *call* `ait artifact`), but live
  artifact-write verification (t1647_7) may be flaky until they land.
- **t1569_6 / t1634 (Ready)** — related vocabulary, no scope overlap.

## Children

Linear order = dependency order (children auto-depend on siblings).

### t1647_1 — Promote trail discovery seams to `lib/trail_discovery.py`; board adopts

New module `.aitask-scripts/lib/trail_discovery.py`, moved verbatim-ish from
`.aitask-scripts/board/aitask_board.py` (pure/subprocess code, no Textual):
`TRAIL_ARTIFACT_KIND`, `TrailInfo`, `trail_entry_refs`,
`compute_trail_overlaps`, `_trail_owner_rank`, `dedupe_trail_records`,
`_iter_active_task_frontmatter`, `_iter_trail_frontmatter_records`,
`_trail_versions`, `load_trail_blob`, `discover_trails`.
Stays in the board: `trail_summary_text`, `run_trail_drift`, all rendering
(TrailEntryView, lanes, glyphs).

- Moved-code deps to resolve into lib imports: `parse_task_filename`,
  `parse_frontmatter` (task_yaml), `_task_id_sort_key` (check where defined; move
  or import), `iter_archived_frontmatter` (archive_iter), `trail_schema`,
  `TASKS_DIR`/`ARTIFACT_SCRIPT` path constants (module takes cwd = repo root,
  same convention as trail_gather.py).
- **Board re-exports the moved names** (`from trail_discovery import ...`) so
  `tests/test_board_bytrail_view.py`'s `ab.load_trail_blob` accessors and
  `patch("subprocess.run")` keep working unchanged; the read-only negative
  control (`ReadOnlyNegativeControlTests`) and the boot-phase spawn control
  must stay green.
- New tests: `tests/test_trail_discovery.py` (pure import, no board) — dedup
  precedence, overlap computation, discovery against a synthetic task dir,
  fail-closed load. Port/keep the board-side tests that pin the same logic
  where they exercise board glue.
- No `.sh` entry point yet — t1647_3 owns the skill-facing wrapper.

### t1647_2 — Schema: `merged_from` provenance + depth-reconciliation validation

- Add optional root property `merged_from` to BOTH schema copies
  (`aidocs/implementation_trail.schema.json` +
  `.aitask-scripts/lib/implementation_trail.schema.json`, byte-identical),
  **no `schema_version` bump** (root is `additionalProperties: false`, const
  `1.1.0`; the optional-additive `overview` precedent applies):

  ```json
  "merged_from": {
    "type": "array", "minItems": 1,
    "items": {"type": "object", "additionalProperties": false,
      "required": ["handle", "version", "merged_at"],
      "properties": {
        "handle":   {"type": "string"},
        "version":  {"type": "string"},
        "title":    {"type": "string"},
        "merged_at": {"$ref": "#/$defs/timestamp"}}}
  }
  ```

- Merge provenance convention (documented in the schema description + RFC):
  `generation.inputs` additionally carries one `{"kind": "other", "ref":
  "<handle>@<version>"}` entry per source trail.
- Tests: `tests/test_trail_schema.py` — merged_from accepted, wrong-shape
  rejected, still-valid-without-it; both-copies-identical assertion if not
  already present. `tests/test_implementation_trail_design.py`: add fixture
  `merged_trail.json` to `aidocs/implementation_trail_examples/` + extend
  `FIXTURE_NAMES` + a merged_from shape check.
- No validator code change needed for depth (deep-wins is preflight policy;
  `--expect-depth` already enforces marker+shape).

### t1647_3 — Merge preflight helper: `aitask_trail_merge.sh` + `lib/trail_merge.py`

Skills reach helpers only through whitelisted `.sh` entry points. New script
`.aitask-scripts/aitask_trail_merge.sh` (source `aitask_path.sh` +
`python_resolve.sh`, shell_conventions.md rules) wrapping new
`lib/trail_merge.py` (imports `trail_discovery`, `trail_schema`). Line
protocol, split on first colon:

- `candidates -- <ref>`: resolve `<ref>` with a two-tier rule. **Auto-resolve
  only on an exact handle or a unique exact advisory-name match** (mirror
  `_artifact_resolve_ref` semantics, `aitask_artifact.sh:115`) → emit
  `BASE:<handle>`. **Any approximate match never auto-resolves**: emit one
  `BASE_CANDIDATE:<handle>|<owner_id>|<title>` line per fuzzy hit
  (`lib/fuzzy_filter.py rank()` over titles+handles, best first) and NO
  `BASE:` line — the base of a destructive merge is a user selection, not an
  inference. Then (only when `BASE:` was resolved) emit
  `CANDIDATE:<handle>|<owner_id>|<n_shared>|<title>` folded-candidate lines
  (desc by shared entry refs via `compute_trail_overlaps`), or
  `NO_CANDIDATES`. Duplicate exact name → `ERROR:ambiguous:<ref>:<matches>`;
  no match at all → `ERROR:unresolved:<ref>`. Advisory only (RFC §13-A6 —
  never auto-dedup).
- `preflight -- <base_ref> <folded_ref> [--lite|--deep]`: resolve both, refuse
  `ERROR:same_trail`; load both docs fail-closed
  (`ERROR:invalid_trail:<handle>`); emit
  `BASE:<handle>|<owner_id>|<depth>|<current_version>`,
  `FOLDED:<handle>|<owner_id>|<depth>|<current_version>`,
  `RESULT_DEPTH:<lite|deep>` (deep-wins default, flag override),
  `DOWNGRADE:<observations>|<relations>|<exclusions>|<evidence>` when the
  override drops material (counts from the real docs),
  `OVERLAP:<task_ref>` / `BASE_ONLY:<task_ref>` / `FOLDED_ONLY:<task_ref>`
  per entry ref. Exit 0 resolved, 1 validation error, 2 usage.
  **Folded-reference enumeration (retirement is per-reference, and the
  substrate keeps a shared manifest):** `ait artifact rm` removes ONE task's
  frontmatter reference and keeps the manifest while any other active,
  archived, or Folded task still references the handle
  (`_artifact_handle_referenced_elsewhere`, `aitask_artifact.sh` rm txn) —
  and discovery scans active + archived frontmatter, so a partially-retired
  trail stays discoverable. Fold transfer (`aitask_fold_mark.sh` 5b) creates
  exactly this shared-reference state in the wild. So preflight enumerates
  EVERY reference to the folded handle: one
  `FOLDED_REF:<owner_task_id>|<active|archived|folded>` line per referencing
  task (from the same frontmatter scan discovery uses). Retirement = removing
  ALL of them (the last rm drops manifest + orphan blobs per the substrate's
  own logic). A reference `ait artifact rm` cannot target (verify in this
  child whether rm resolves archived/folded task files; if not) →
  `ERROR:unretirable_reference:<owner_id>` — fail closed with manual-cleanup
  guidance rather than silently leaving the trail discoverable.
  **Half-merged detection (resumable retirement, reference-aware):** before
  emitting a merge plan, check whether the base's CURRENT doc already carries
  a `merged_from` entry naming the folded handle. If yes, the folded trail
  still resolves, and its current version equals the entry's recorded
  `version` → the previous merge wrote the base but retirement is incomplete:
  emit `RESUME:retirement_pending|<folded_handle>|<remaining_owner_csv>`
  (the still-referencing owners) INSTEAD of the plan lines — the consumer
  must not re-author; completing the remaining rms is the only offered
  action. Once every reference is gone the folded ref no longer resolves →
  ordinary `ERROR:unresolved`, never a false resume. If the folded trail has
  MOVED since the record → `ERROR:merge_conflict:<folded_handle>` (completing
  the old retirement would destroy unseen content; human decision required).
- Read-only: only `artifact get`/manifest reads; never writes.
- Whitelist: `./.aitask-scripts/aitask_audit_wrappers.sh apply-helper-whitelist
  aitask_trail_merge.sh` (all 5 touchpoints).
- Tests: `tests/test_trail_merge_preflight.sh` — fixture trails MUST include a
  **divergent pair** (partial entry overlap, different wave structures, one
  deep with observations/relations/exclusions the other lacks), not only the
  identical-membership shape: pin OVERLAP / BASE_ONLY / FOLDED_ONLY
  partitioning, downgrade counts, ambiguity (BASE_CANDIDATE list, no BASE:),
  approximate-match-never-auto-resolves, same-trail refusal, protocol shape,
  and the **retirement states**: single-owner rm-failure →
  `RESUME:retirement_pending` with NO plan lines; **shared-reference fixture**
  (two tasks referencing the folded handle, one rm done) →
  `RESUME:retirement_pending` naming only the REMAINING owner;
  fully-retired → plain `ERROR:unresolved` (no false resume);
  base-records-folded-but-folded-moved → `ERROR:merge_conflict`;
  `FOLDED_REF:` enumeration across active + archived owners. Python-side
  unit coverage in `tests/test_trail_discovery.py` or a dedicated
  `test_trail_merge.py`.

### t1647_4 — `/aitask-merge-trails` skill + `merge-trails` codeagent operation

Full profile-aware surface per `skill_authoring_conventions.md` +
`stub-skill-pattern.md` §3g:
- `.claude/skills/aitask-merge-trails/SKILL.md` (stub, resolver key
  `merge-trails`) + `SKILL.md.j2` (authoring template);
- `.agents/skills/aitask-merge-trails/SKILL.md` (codex stub, `-codex-`
  rendered segment);
- `.opencode/commands/aitask-merge-trails.md` + skill-dir stub
  `.opencode/skills/aitask-merge-trails/SKILL.md`;
- goldens `tests/golden/skills/aitask-merge-trails/SKILL-{default,fast,remote}-claude.md`
  rendered via `skill_template.py` (same commit as the template).

Skill flow (template body):
0. Parse: `[--lite|--deep] <base_ref> [<folded_ref>]` (refs whitespace-free —
   the codeagent guard enforces this on launch).
1. One ref → `aitask_trail_merge.sh candidates`. If the output carries
   `BASE_CANDIDATE:` lines (approximate match), **AskUserQuestion to pick the
   surviving base first** — an approximate name never silently selects the
   survivor of a destructive merge; re-run `candidates` with the chosen
   handle. Then AskUserQuestion to pick the folded trail from `CANDIDATE:`
   lines (advisory; "no merge" always offered). Two refs (the board's
   argument shape) → skip the scan; each ref still resolves only exactly
   (handle or unique name) — approximate two-ref input gets the same
   pick-the-base treatment.
2. `aitask_trail_merge.sh preflight -- <base> <folded> [flag]` → display
   depth pair, RESULT_DEPTH, overlap/only sets; **record both
   `<current_version>` values as the stale-base baseline**; DOWNGRADE →
   NON-SKIPPABLE confirmation naming the dropped counts; ERROR → stop.
3. Fetch both docs (`ait artifact get <handle> --out <scratch>`).
4. **Author the merged document — agent re-authoring, never mechanical
   union** (lite union is schema-invalid): dedup entries by canonical task
   ref, renumber wave ordinals + per-wave positions strictly increasing,
   reconcile waves, merge narrative/exclusions/observations per RESULT_DEPTH
   (lite → omit heavy keys, exactly 1 evidence record), `trail_id`/handle =
   base's, `merged_from` records the folded AND base source versions
   (handle@version, merged_at now), `generation.inputs` gains the two
   `kind: other` entries, `generator.skill: "aitask-merge-trails"`,
   `freshness` current. Reuse `/aitask-trail`'s "Trail JSON authoring rules"
   (adapted inline — the trail skill's rules section is the model).
5. Validate: `./.aitask-scripts/aitask_trail_depth.sh validate <file>
   --expect-depth <RESULT_DEPTH>` (already whitelisted).
6. NON-SKIPPABLE confirmation naming the FULL write set: `ait artifact update
   <base_handle> <merged.json>` AND one `ait artifact rm <owner>
   <folded_handle>` per `FOLDED_REF:` line from preflight — retirement means
   removing EVERY reference (the substrate keeps the manifest while any
   remains), and the referencing owners may differ from the base's owner.
   The confirmation enumerates each owner (with its active/archived/folded
   state) so a shared-reference retirement is an explicit all-owner decision,
   never a surprise; everything is recoverable from data-branch history.
   **The confirmation comes BEFORE the stale-base guard** — the user can
   deliberate here indefinitely, so any version check taken earlier would be
   stale by the time they answer.
7. **Stale-base guard (both handles) — after confirmation, coupled directly
   to execution.** `ait artifact update` has no compare-and-swap, so the
   comparison must be the last act before the writes: re-read the current
   version of BOTH handles (`ait artifact versions <handle>` × 2, or re-run
   `preflight`) and compare against the Step-2 baseline. **Unchanged →
   execute both writes immediately, no further prompt.** Either moved →
   NON-SKIPPABLE AskUserQuestion mirroring the refresh flow's stale-base
   guard: "Reload and re-author" (re-fetch the moved doc(s), redo Steps 3–6
   on current content — including a fresh confirmation), "Overwrite anyway"
   (proceed on the stale baseline, named as such), "Abort" (no writes). A
   moved FOLDED trail matters as much as a moved base — the rm would retire
   content the author never saw. Residual (state it in the skill's notes):
   without CAS a write can still race inside the re-read→write gap; this
   guard shrinks the window from user-deliberation time to that gap, it does
   not eliminate it.
8. **Write order + partial-failure recovery.** Always `update` the base
   FIRST, then the `rm` sequence (one per referencing owner) — never retire
   first (an update failure after retirement would lose the only live copy
   of the fold decision's context). Outcomes:
   - `update` fails → nothing to compensate: the artifact CLI's txn rolls
     back its own commit failures, the folded trail is untouched; report and
     stop.
   - `update` succeeds, any `rm` fails (or only some complete) →
     **retirement-pending state**: the trail stays discoverable while any
     reference remains, and the base's `merged_from` records the retirement.
     Report exactly which owners' references remain and their completing
     commands, and note that re-running `/aitask-merge-trails <base>
     <folded>` resumes rather than re-merges: preflight (t1647_3) detects
     the state deterministically and emits `RESUME:retirement_pending` with
     the REMAINING owners, and the skill then offers ONLY "complete the
     retirement" / "abort" — never a second authoring pass from ambiguous
     state.
9. Run summary + board pointer (By-Trail `z`/`s`), mirroring the trail skill.

Codeagent op `merge-trails` in `.aitask-scripts/aitask_codeagent.sh`:
`SUPPORTED_OPERATIONS` (line 26), per-agent prompt branches (case arms near
:426/:476/:545/:575 — claude `/aitask-merge-trails <args>`, codex
`build_skill_prompt "$aitask-merge-trails"`, opencode `--prompt`), usage text
(:644), and `defaults."merge-trails"` in BOTH `aitasks/metadata/codeagent_config.json`
and `seed/codeagent_config.json` (project convention).

Tests: `tests/test_skill_render_aitask_merge_trails.sh` (goldens ×3, agent
invariance, no Jinja leak, stub markers — model:
`test_skill_render_aitask_trail.sh`); `tests/test_merge_trails_skill_contract.sh`
(pins across all 3 goldens: one-confirmation-covers-the-full-write-set banner
(update + every FOLDED_REF rm), rm-targets-each-referencing-owner,
preflight-before-author, validate-with-expect-depth, advisory-candidates,
**approximate-base-requires-explicit-selection**, the **two-handle
stale-base guard placed AFTER the final confirmation with its
reload/overwrite/abort options**, **update-before-rm write order**, and the
**rm-failure guidance naming the completing command and the resumable
re-invocation** — model: `test_trail_skill_contract.sh`, whose refresh-flow
stale-base pin this extends); `tests/test_codeagent_merge_trails.sh`
(model: `test_codeagent_trail.sh`). `test_skill_dispatch_contract.sh` covers
the new skill automatically.

### t1647_5 — Board By-Trail `F` command + dialogs

`.aitask-scripts/board/aitask_board.py`:
- `Binding("F", "trail_merge", "Fold Trails")` in the By-Trail block of
  `KanbanApp.BINDINGS` (~:9011, next to `M`).
- `check_action` branch: live only when `base_filter == "bytrail"`, an
  `active_trail_handle` is set, and ≥2 trails were discovered (the folded
  candidate list would otherwise be empty); hidden while `_trail_launch_pending`
  (same rationale as `R`). Action body re-checks (command palette reachability).
- `action_trail_merge`: modal to pick the folded trail — new
  `TrailMergeSelectScreen` modeled on `TrailSelectScreen` (:4471) /
  `PickerItem`, listing discovered trails EXCLUDING the active one, showing
  the §9.2 "also in" overlap notes → confirm screen modeled on
  `MergeColumnsConfirmScreen` (:8219) naming base (survivor), folded
  (retired), shared-entry count, and that an agent will perform the merge →
  `_launch_merge_trails([base_handle, folded_handle])` mirroring
  `_launch_trail` (:12181): `resolve_dry_run_command(Path("."),
  "merge-trails", ...)`, `AgentCommandScreen`, tmux/dialog launch, version
  watch on the BASE handle (reload when the merged version lands),
  `debounce_key` for `F`.
- The board never merges in-process — it only spawns the launch (the
  read-only contract; the negative control keeps pinning that only
  drift/get/versions + the confirmed launch are spawned).
- Tests in `tests/test_board_bytrail_view.py`: footer/gating (outside bytrail,
  no active trail, single trail, launch pending), launch-arg construction
  (both handles, operation `merge-trails`), watch-on-confirmed-launch-only,
  cancel path, read-only control still green.

### t1647_6 — Docs: website + RFC

- `website/content/docs/tuis/board/reference.md`: By-Trail section — add `F`
  to the key table with cost note (launches an agent); Modal Dialogs
  Reference — add **Trail Select**, **Trail Detail**, **Trail Merge (pick)**,
  **Trail Merge Confirm** rows (closes the no-trail-modals gap).
- `website/content/docs/tuis/board/how-to.md`: By-Trail block — "merge two
  trails" how-to.
- `website/content/docs/workflows/implementation-trails.md`: new "Merging Two
  Trails" section (when to merge, deep-wins rule, what retirement means,
  recovery from data-branch history); keep current-state prose.
- `website/content/docs/skills/aitask-merge-trails.md` page +
  `_index.md` row (Task Creation & Analysis table, next to `/aitask-trail`).
- `aidocs/implementation_trail_design.md`: merge flow section (invocation
  surfaces, preflight protocol, deep-wins, `merged_from`, single-confirmed-write
  + retirement) — current-state prose per documentation_conventions.md.
- Verify with `hugo build --gc --minify` in `website/` (anchors are NOT
  checked by hugo — verify relrefs manually).
- **Coordination:** t1603_5 (Implementing) edits other sections of
  `reference.md` — re-verify section anchors against the landed state before
  editing.

### t1647_7 — manual_verification (aggregate sibling)

Seeded from the children's `## Verification` sections via
`aitask_create_manual_verification.sh` at decomposition time (the standard
post-child-creation offer). Expected checklist highlights:
- Board `F` flow end-to-end in a real terminal; skill invocation with one
  approximate name (base candidates presented for explicit selection, then
  folded-candidate scan).
- **Divergent-pair merge (the discriminating case).** The t1118 pair has
  identical membership, so it cannot prove re-authoring quality. Create two
  synthetic trails on a scratch task with partial entry overlap, different
  wave structures, and deep-only material on one side; run the full merge and
  check: shared entries deduped once, base-only AND folded-only entries all
  present and sensibly placed, wave ordinals/positions renumbered strictly
  increasing, deep-wins result retains the deep side's
  observations/relations/exclusions/evidence, narrative reconciled (not
  concatenated). Retire the scratch trails afterwards.
- **The real t1118 lite+deep merge** (deep-wins → deep result; folded lite
  trail retired; By-Trail shows the merged trail; `ait artifact versions`
  shows provenance) — the user's live scenario 1; proves the identical-
  membership path but NOT re-authoring (the divergent case above owns that).
- Stale-base guard live check: launch a merge, and while the final
  confirmation dialog is open bump one source trail from a second terminal;
  confirm, and verify the post-confirmation guard catches the move and offers
  reload/overwrite/abort (the deliberation window is exactly what the
  guard's placement covers).
- Half-merged recovery live check: simulate an rm failure after a successful
  base update (e.g. temporarily break the folded owner's frontmatter), rerun
  the skill with the same pair, verify it offers ONLY completing the
  retirement.
- Shared-reference retirement live check: give the folded trail a second
  referencing task (the fold-transfer shape), run the merge, verify the
  confirmation enumerates BOTH owners, both references are removed, the
  manifest is gone, and the trail no longer appears in By-Trail discovery.

## Risk

### Code-health: medium

- Moving load-bearing discovery code out of the 12k-line board module
  (t1647_1) risks breaking By-Trail. · severity: medium · → mitigation:
  inline — board re-exports the moved names; the full existing
  `test_board_bytrail_view.py` suite (incl. negative controls) must pass
  unchanged in the same child.
- Board BINDINGS/check_action edits (t1647_5) touch a heavily-pinned surface.
  · severity: low · → mitigation: inline — gating tests written in the same
  child; footer-label test updated.
- Schema change is optional-additive with both copies edited together; a
  mistake would invalidate every stored trail. · severity: low · → mitigation:
  inline — t1647_2's tests validate all existing fixtures + the two live-style
  docs against the new schema before landing.

### Goal-achievement: medium

- The merge itself is agent re-authoring guided by prose — a bad merge could
  validate yet lose meaning (schema-valid JSON with wrong ordering or dropped
  reasoning). · severity: medium · → mitigation: inline — preflight emits the
  overlap/only sets and RESULT_DEPTH deterministically, the validator enforces
  shape via `--expect-depth`, `merged_from` + `generation.inputs` make
  provenance auditable, both writes sit behind one NON-SKIPPABLE confirmation,
  and the retired trail is recoverable from data-branch history; t1647_3's
  divergent fixture pair pins the preflight partitioning and t1647_7's
  divergent-pair MV case checks the re-authored result itself (dedup,
  placement, renumbering, deep reconciliation) — the identical-membership
  t1118 merge alone cannot discriminate these.
- An approximate base reference or a concurrently-moved source could target
  the destructive writes wrongly. · severity: high (if unmitigated) · →
  mitigation: inline — approximate matches never auto-resolve the base
  (explicit `BASE_CANDIDATE` selection), and the two-handle stale-base guard
  runs AFTER the final confirmation, coupled directly to the writes (the
  confirmation dialog is where a user deliberates, so any earlier check goes
  stale); both pinned by the contract test. Residual: no CAS — the
  re-read→write gap remains, stated in the skill.
- The writes (base update + per-owner rm sequence) are independent
  transactions; a failure between them leaves a partially-retired state —
  and a shared-reference handle (fold transfer creates these) means rm alone
  never guarantees the trail disappears. · severity: medium · → mitigation:
  inline — preflight enumerates every folded-handle reference
  (`FOLDED_REF:`), the confirmation covers the all-owner retirement set,
  update-before-rm ordering (an update failure compensates itself: nothing
  was retired), and resume detection is reference-aware: preflight emits
  `RESUME:retirement_pending` naming the REMAINING owners
  (complete-the-retirement only, never a second authoring pass), plain
  `ERROR:unresolved` once fully retired (no false resume), or
  `ERROR:merge_conflict` when the pending trail moved; shared-reference,
  true-rm-failure, and fully-retired states all fixture-tested in t1647_3.
- Deferring the skill's cross-agent stubs would fail
  `test_skill_dispatch_contract.sh`. · severity: low · → mitigation: inline —
  t1647_4 ships all three surfaces in one commit.

No spawned before/after mitigation tasks: every mitigation is inline in a
child, and the parent exits at the child checkpoint (decomposed parents never
reach Step 8d — mitigations must not be deferred there).

## Post-approval execution (this session)

1. Externalize this parent plan to `aiplans/p1647_merge_trails_skill_shared_helpers_board_command_docs.md`.
2. Batch-create the 6 children under `aitasks/t1647/` (self-contained
   descriptions: context, key files with the corrected line anchors, pinned
   decisions, per-child test list, verification steps).
3. Revert parent to `Ready`, clear `assigned_to`, release the lock (children
   own the locks).
4. Write all 6 child plans to `aiplans/p1647/`, commit together.
5. Offer the aggregate manual-verification sibling (t1647_7) seeded from the
   child plans' `## Verification` sections.
6. Child checkpoint: start `/aitask-pick 1647_1` or stop.

## Verification (feature-level)

- `bash tests/test_trail_discovery.sh`-family + `python3 -m pytest` lane via
  `bash tests/run_all_python_tests.sh` (check the LAST stderr line only).
- `bash tests/test_skill_dispatch_contract.sh`,
  `test_skill_render_aitask_merge_trails.sh`,
  `test_merge_trails_skill_contract.sh`, `test_codeagent_merge_trails.sh`,
  `test_trail_merge_preflight.sh`, `test_trail_schema.py`,
  `test_implementation_trail_design.py`, `test_board_bytrail_view.py`.
- `shellcheck .aitask-scripts/aitask_trail_merge.sh` (+ codeagent edit).
- `./.aitask-scripts/aitask_skill_verify.sh` after the stub/template child.
- Manual: t1647_7 checklist, headlined by the live t1118 lite+deep merge.
