---
priority: medium
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [skills, aitask_board, artifacts, web_site]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
created_at: 2026-08-31 11:10
updated_at: 2026-09-01 17:21
---

## Goal

Add trail-to-trail **merge (fold)** to the implementation-trail subsystem: fold
one existing trail into another, producing a single merged trail and retiring
the folded one. Complex feature — **decompose into child tasks at planning**.

## Usage scenarios (user-stated)

1. A new trail was created for a feature without realizing a similar trail
   already exists (live example: t1118 owns both `art:trail-mobile-shadow-driving`
   (lite) and `art:trail-mobile-shadow-driving-deep` (deep) with identical
   6-entry membership).
2. Scope of a feature expanded; a new trail was created for the new facet and
   should be merged with the remaining work in the related existing trail.

## Settled architecture (user decision, this exploration)

- **Keep `/aitask-trail` focused on one-trail authoring/viewing** (its 3 modes
  create/refresh/show are pinned in `aitask_trail_depth.sh resolve` +
  `tests/test_trail_depth_resolve.sh`; do not overload them).
- **New dedicated skill `/aitask-merge-trails`** for explicit two-trail
  operations (profile-aware stub + `.md.j2`, goldens, render test — the full
  surface per `aidocs/framework/skill_authoring_conventions.md`).
- **Distinct codeagent operation** (e.g. `merge-trails`): add to
  `SUPPORTED_OPERATIONS` in `aitask_codeagent.sh:26`, per-agent prompt branches
  (:426, :472-478, :544-545, :572-576), usage text (:644), and per-op
  `.defaults` entries in seed + live config (project convention: new ops need
  `.defaults` in both).
- **Shared library helpers own the real logic** — discovery, validation, merge
  planning, artifact writes — so the skill duplicates nothing and the board and
  `/aitask-trail` reuse the same seams.
- **Board "merge trail" command launches the dedicated workflow** with the two
  selected handles already supplied — it never merges in-process
  (`test_board_bytrail_view.py`'s read-only negative control pins that the
  board only spawns drift / artifact get / versions).

## Invocation surfaces

1. **Board By-Trail screen**: new command (free key; taken in By-Trail:
   r R d s S v T z, and t1210_5 claims m/M) → dialog to pick the trail to merge
   with (model on `TrailSelectScreen(ModalScreen)` at
   `.aitask-scripts/board/aitask_board.py:4218` + `PickerItem:4082`, excluding
   the active trail; the "pick survivor → confirm" pair
   `ColumnManageScreen._confirm_merge` → `MergeColumnsConfirmScreen`
   (:8085-8122, :7854) is the confirmation model) → launch via the
   `_launch_work_report` / `_launch_trail` pattern (`AgentCommandScreen`,
   `resolve_dry_run_command`, `launch_in_tmux`).
2. **Interactive skill invocation with an approximate trail name**: resolve the
   named base trail (exact handle wins; unique name accepted — mirror
   `_artifact_resolve_ref` in `aitask_artifact.sh:110-135`; fuzzy ranking via
   `lib/fuzzy_filter.py rank()` on titles/handles), then run a **fast, not
   deep** scan of existing trails and propose merge candidates via
   AskUserQuestion (candidate signal: shared entry refs — promote
   `compute_trail_overlaps` (board :1080); scan cost is small: frontmatter scan
   + one `artifact get` per trail, ~0.2s each, 4 trails today).
3. Invocation with **both** trails named skips the candidate scan and goes to
   merge planning (this is the argument shape the board passes).

## Merge semantics (verified constraints)

- **Merge is an agent re-authoring, not a mechanical union.** `lite_shape`
  (`lib/trail_schema.py:375`) requires a lite trail to have exactly 1 evidence
  record and NO observations/relations/exclusions — unioning two lite trails is
  schema-invalid. The skill synthesizes the merged document from both source
  docs: dedup entries by canonical task ref, renumber strictly-increasing
  ordinals/positions (`_check_strictly_increasing`), reconcile waves, merge
  narrative/exclusions/observations per depth rules.
- **Depth reconciliation is a real decision** (lite+deep exists live):
  `rendering_hints.depth` must match the merged shape (`depth_marker` rule,
  `trail_schema.py:345`); settle the rule at planning (e.g. result is deep iff
  authored deep-shaped, with `--expect-depth` asserted at validation).
- **Merge provenance**: optional new root property (e.g. `merged_from`) added
  WITHOUT a `schema_version` bump — root is `additionalProperties: false` with
  const `1.1.0` and the loader rejects any other version, so a required field /
  version bump would turn every existing trail into ERROR:invalid_trail. The
  optional-additive `overview` precedent applies. `generation.inputs` accepts
  `kind: other` → cite both source trails (handle@version) as inputs. Both
  schema copies (`aidocs/implementation_trail.schema.json` +
  `.aitask-scripts/lib/implementation_trail.schema.json`) must stay in sync.
- **Ownership / retirement**: merged doc writes to the base trail's handle via
  the existing single-confirmed-write path (`ait artifact update`); the folded
  trail is retired with `ait artifact rm <owner> <handle>` (removes the owner's
  `artifacts:` frontmatter entry + manifest + orphan blobs; recoverable from
  data-branch git history). Folded trail's owner may differ from the base
  trail's owner — the rm targets the folded trail's own owner task. Both writes
  happen only after explicit user confirmation (RFC §12 confirmation rule; the
  fold-transfer precedent `aitask_fold_mark.sh` Step 5b dedups artifacts by
  handle, pinned by `test_artifact_fold_transfer.sh`).
- **Merge is explicit user intent, never auto-dedup**: RFC §13-A6 decided
  overlapping trails are legitimate (many trails per task). Candidate proposals
  are advisory only.

## Shared-helper promotion (reuse, don't reimplement)

Board-internal seams to promote into shared lib (board then imports them):
`discover_trails` (aitask_board.py:1276, frontmatter-driven discovery per RFC
§5 — the manifest stores no kind), `load_trail_blob` (:1239),
`dedupe_trail_records` (:1115), `compute_trail_overlaps` (:1080). Candidate
landing spot: `lib/trail_gather.py` (new verb on `aitask_trail_gather.sh`, e.g.
`list`) or a new `lib/` module — skills must reach helpers through whitelisted
`.sh` entry points (allowlist convention; see `aitask_trail_depth.sh validate`
rationale). New helper scripts need their 5 whitelist entries
(`apply-helper-whitelist`).

## Documentation (required by the feature)

- Website: board docs — new command + dialog in
  `website/content/docs/tuis/board/reference.md` (By-Trail section L240-341;
  note the Modal Dialogs Reference table L458-483 currently lists NO trail
  modals — gap to close when adding the merge dialog) and
  `website/content/docs/tuis/board/how-to.md` (By-Trail block L210-245).
- Workflows: there is NO trail workflow page today — **t1210_6 (Ready) owns
  creating `website/content/docs/workflows/implementation-trails.md` + its
  hand-added `_index.md` bullet**. The merge workflow docs must link into /
  extend that page: coordinate — either depend on t1210_6 or make the docs
  child of this task explicitly cover the merge section of that page without
  duplicating its scope.
- `aidocs/implementation_trail_design.md`: add the merge flow to the RFC
  (current-state prose per documentation_conventions).

## Coordination (in-flight, verified at exploration time)

- **t1210_5 (Ready)** claims `m`/`M` + the same `KanbanApp.BINDINGS` list and
  By-Trail `check_action` branches — key choice and edit surface collide;
  sequence or coordinate.
- **t1210_6 (Ready)** owns the trail workflow website page (above).
- **t1569_6 (Ready)** authors trails from the backlog-roadmap skill; t1634
  (Ready) does fold-candidate clustering for tasks (not trails) — related
  vocabulary, no overlap in scope.

## Test surface (existing files that pin behavior this feature touches)

`tests/test_trail_depth_resolve.sh` (mode grammar — must stay 3-mode),
`test_trail_skill_contract.sh` (write invariants; the new skill needs its own
contract test), `test_skill_render_aitask_trail.sh` (render goldens pattern),
`test_codeagent_trail.sh` (pattern for the new op's test), `test_trail_schema.py`
(schema/validator — merge provenance + depth rules), `test_trail_gather.py`,
`test_board_bytrail_view.py` (board read-only negative control + new
command/dialog tests), `test_artifact_fold_transfer.sh` (handle-dedup
precedent), `test_implementation_trail_design.py` (design-contract guard).

## Decomposition expectation

Split at planning into children, e.g.: shared-helper promotion (+ board
adoption), schema/provenance + merge-document rules, the
`/aitask-merge-trails` skill + codeagent op, the board command + dialog,
website/RFC docs (coordinated with t1210_6), and a manual-verification child.
