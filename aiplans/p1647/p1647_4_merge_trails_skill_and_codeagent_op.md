---
Task: t1647_4_merge_trails_skill_and_codeagent_op.md
Parent Task: aitasks/t1647_merge_trails_skill_shared_helpers_board_command_docs.md
Sibling Tasks: aitasks/t1647/t1647_1_*.md … t1647_6_*.md
Worktree: (none — profile 'fast', current branch)
Base branch: main
Output branch: main
plan_verified: []
---

# Plan: t1647_4 — `/aitask-merge-trails` skill + `merge-trails` codeagent op

## Context

The user-facing surface. Consumes t1647_3's protocol and t1647_2's
provenance. Read `aidocs/framework/skill_authoring_conventions.md` and
`aidocs/framework/stub-skill-pattern.md` BEFORE writing any skill file.

**All three agent surfaces land in this one child** —
`tests/test_skill_dispatch_contract.sh` discovers templated skills at
runtime and immediately requires every stub + rendered closure (deliberate
exception to the "separate aitasks per agent" rule).

## Files

1. `.claude/skills/aitask-merge-trails/SKILL.md` — profile stub; resolver
   key `merge-trails`; model: `.claude/skills/aitask-trail/SKILL.md`
   (resolve profile → render → Read-and-follow
   `.claude/skills/aitask-merge-trails-<profile>-/SKILL.md`).
2. `.claude/skills/aitask-merge-trails/SKILL.md.j2` — authoring template
   (body below). Follow the trail template's structure: Overview, protocol
   pins, Workflow steps, run summary, authoring rules, Notes. Profile
   conditionals only where the trail template has them (headless guard for
   remote).
3. `.agents/skills/aitask-merge-trails/SKILL.md` — codex stub (`-codex-`
   rendered segment per §3g).
4. `.opencode/commands/aitask-merge-trails.md` + skill-dir stub
   `.opencode/skills/aitask-merge-trails/SKILL.md`.
5. Goldens `tests/golden/skills/aitask-merge-trails/SKILL-{default,fast,remote}-claude.md`
   — regenerate with `.aitask-scripts/lib/skill_template.py` (loop in
   skill_authoring_conventions "Regenerate goldens"), SAME commit as the
   template. Review the diff, don't rubber-stamp.
6. `.aitask-scripts/aitask_codeagent.sh` + config (below).

## Skill flow (template body; PINNED semantics — the merge-safety contract)

0. **Parse** `[--lite|--deep] <base_ref> [<folded_ref>]`. Refs are
   whitespace-free (codeagent launch guard enforces).
1. **Resolve/candidates.** One ref →
   `./.aitask-scripts/aitask_trail_merge.sh candidates -- <ref>`:
   - `BASE_CANDIDATE:` lines → AskUserQuestion to pick the surviving base
     FIRST (approximate names never silently select the survivor of a
     destructive merge), then re-run `candidates` with the chosen handle.
   - Then AskUserQuestion over `CANDIDATE:` lines for the folded trail —
     advisory, "no merge" always offered (RFC §13-A6).
   Two refs (the board's shape) → skip the scan; an approximate ref still
   gets the pick-the-base treatment.
   `RESUME:retirement_pending|<handle>|<owners>` at ANY invocation → offer
   ONLY "complete the retirement" (run the remaining rms after
   confirmation) / "abort". Never re-author from this state.
   **`<handle>` need not be either trail the user named.** Preflight is
   record-aware (t1647_3 step 3, corrected by t1647_2 finding 2a): a pending
   retirement recorded on the base blocks *any* new merge against it, because
   `merged_from` is written wholesale and authoring one would erase that
   handle's only recovery record. Report the handle preflight named, not the
   one the user asked about.
   `ERROR:merge_conflict` → explain and stop.
2. **Preflight.** `aitask_trail_merge.sh preflight -- <base> <folded>
   [depth-flag]`. Display depth pair, `RESULT_DEPTH`, the
   OVERLAP/BASE_ONLY/FOLDED_ONLY sets, and the `FOLDED_REF:` owners.
   **Record both `current_version` values — the stale-base baseline.**
   `DOWNGRADE:` present → NON-SKIPPABLE confirmation naming the dropped
   counts before continuing. Any `ERROR:` → stop.
3. **Fetch.** `ait artifact get <handle> --out <scratch>` × 2 (scratchpad
   paths).
3b. **Resolve the RESULT SCOPE — decides both the stored `scope.kind` and the
   snapshot call in step 4** (added by t1647_2 finding 2c; p1647_4 previously
   left this undefined for mixed pairs). **There is no `--scope ad_hoc`:**
   `snapshot --scope` accepts exactly `task|topic|multi_topic`
   (`lib/trail_gather.py`), while `scope.kind` also permits `ad_hoc` — and
   `ad_hoc` is live, being 2 of the 5 stored trails today. This reuses the
   framework's existing rules rather than inventing a convention:
   `.claude/skills/aitask-trail/SKILL.md.j2:323` (ad_hoc maps to task scope),
   `:526-532` (the refresh re-snapshot rule — same stored-trail→snapshot-call
   problem), and `:404-408` ("the gatherer cannot mix scopes").

   | base `scope.kind` | folded `scope.kind` | result `scope.kind` | snapshot call | membership |
   |---|---|---|---|---|
   | `topic` | `topic` | `multi_topic` | `--scope multi_topic <union of roots>` | live per topic |
   | `topic`/`multi_topic` | `topic`/`multi_topic` | `multi_topic` | `--scope multi_topic <union of roots>` | live per topic |
   | either side `task` or `ad_hoc` | | `ad_hoc` | `--scope task <union of both sources' recorded member ids>` | pinned to the exact union |

   Keeping the base's own topic after folding another topic would lose live
   related-task detection for the folded topic, which is why topic∪topic
   widens to `multi_topic`; conversely any pair touching a `task`/`ad_hoc`
   source resolves to `ad_hoc` over the exact recorded union, so membership
   never widens past the two sources.

   `scope.topics` on the result is the union of both sources' `topics` in
   every row — the schema calls it "a projection, not an assignment", so it
   never defines membership. `scope.selection_note` MUST name both source
   handles and the rule row applied.

4. **Author the merged document — agent re-authoring, never a mechanical
   union** (a lite union is schema-invalid: lite = exactly 1 evidence
   record, NO observations/relations/exclusions):
   - dedup entries by canonical task ref (`task` key); every BASE_ONLY and
     FOLDED_ONLY entry appears exactly once; OVERLAP entries once.
   - renumber wave `ordinal`s and per-wave `position`s strictly increasing;
     reconcile wave structure (merge waves that express the same phase;
     narrative explains the reconciliation).
   - narrative/exclusions/observations merged per `RESULT_DEPTH` (lite →
     omit the heavy keys entirely).
   - `trail_id` + handle = base's; `title` re-authored if needed.
   - `merged_from`: TWO entries — folded source AND the base's pre-merge
     version — each `{handle, version (Step-2 baseline), title, merged_at
     (now, UTC ISO-8601)}`. **Both entries share one `merged_at`** (they
     describe one event), and the value is written **wholesale**: a later
     merge REPLACES it rather than extending it, and inherited ancestry is
     never carried forward. Deeper history stays walkable because each
     `version` is the exact `ait artifact get <handle> --version` key for the
     previous hop. (Contract settled and verified in t1647_2; the schema
     `description` is authoritative, and
     `tests/test_implementation_trail_design.py::MergedProvenanceContract`
     pins it.)
   - `generation`: `generated_at` now; `generator.agent_string` per
     `$AITASK_AGENT_STRING` / self-detection;
     `generator.skill: "aitask-merge-trails"`.

     **`inputs` and `input_digest` — one snapshot, both values, no artifact
     refs (corrected by t1647_2; previously this bullet said "union of source
     inputs PLUS one `{"kind": "other", ...}` per source" and left the digest
     to "reuse the base's digest inputs contract"). Both halves were wrong:**

     - **No artifact refs in `inputs`, ever.** `_classify_stored_inputs`
       (`lib/trail_gather.py`) routes every input kind without a live
       resolver — `other` included, the only kind that would accept a handle
       — to a staged error, and the caller then does
       `if errors: emit_errors(...); return 0`. **One** such record refuses
       the document's **entire** staleness verdict, so every merged trail
       would report `ERROR:undriftable_input:` forever in the board and on
       refresh. Pinned by
       `tests/test_trail_gather.py::test_content_kinds_without_resolver_fail_closed`.
       Merge provenance lives in `merged_from` only, which is a **root**
       property and therefore outside the digest by construction.
     - **The digest cannot be reused, combined, or derived from stored
       inputs.** `_normalize_input_record` requires `exists` plus
       per-`(kind, exists)` state fields; stored `generation.inputs` records
       carry only `{ref, kind}`, so hashing them raises. And `input_digest`
       is a truncated sha256 over sorted *live* records, so two source
       digests cannot be merged. Reusing the base's digest ships a document
       that drift reports **STALE the moment it is written**, while every
       schema and depth check passes.
     - **Do this instead:** take **one**
       `./.aitask-scripts/aitask_trail_gather.sh snapshot` run over the
       **deduplicated union** of both sources' scope ids (scope per the
       result-scope policy in step 3b below), passing `--owner <base owner>`
       — mandatory on a multi-id snapshot, or the gatherer emits `OWNER:none`
       and the document fails the `owner` pattern. Write **that single run's**
       `INPUT:` pairs as the `{ref, kind}` records **and** its `DIGEST:` value
       into the merged document together. The pairing is what makes the
       document self-consistent; splitting it across two runs reintroduces the
       staleness the guard exists to prevent.
   - `freshness`: `{"state": "current", "checked_at": now}`.
   - Adapt the "Trail JSON authoring rules" section of
     `.claude/skills/aitask-trail/SKILL.md.j2` (~L799) inline: transport
     sentinels (omit `unknown`/`invalid` snapshot fields), hard_depends
     `provenance: fact` mirroring, evidence locators-not-content, overview
     non-blank rules all apply verbatim.
5. **Validate.** `./.aitask-scripts/aitask_trail_depth.sh validate <file>
   --expect-depth <RESULT_DEPTH>` — INVALID → fix and re-validate; never
   write an invalid doc.
6. **NON-SKIPPABLE confirmation — the FULL write set, BEFORE the guard:**
   names `ait artifact update <base_handle> <merged.json>` AND one
   `ait artifact rm <owner> <folded_handle>` per `FOLDED_REF:` line, each
   owner with its active/archived/folded state (retirement removes EVERY
   reference — the substrate keeps the manifest while any remains; owners
   may differ from the base's). Note recoverability from data-branch
   history. The confirmation precedes the stale-base guard because the user
   can deliberate indefinitely — an earlier check would be stale by answer
   time.
7. **Stale-base guard (both handles), AFTER confirmation, coupled to
   execution:** re-read both current versions (`ait artifact versions` × 2,
   or re-run preflight) vs the Step-2 baseline. Unchanged → execute
   immediately, no further prompt. Either moved → NON-SKIPPABLE
   AskUserQuestion: "Reload and re-author" (redo Steps 3–6 on current
   content, fresh confirmation) / "Overwrite anyway" (named as stale) /
   "Abort" (no writes). Skill Notes state the residual: no CAS — the
   re-read→write gap remains; the guard shrinks the window to that gap.
8. **Writes + partial-failure recovery:** `update` the base FIRST, then the
   rm sequence — never retire first. `update` fails → nothing to
   compensate (the artifact txn rolls back its own commit failures); report
   and stop. Any rm fails / partial → report which owners' references
   remain + their exact completing commands, and state that re-running
   `/aitask-merge-trails <base> <folded>` resumes via
   `RESUME:retirement_pending` (complete-retirement only).
9. **Run summary** + board pointer (By-Trail `z` / `s`), mirroring the
   trail skill's run-summary parts.

## Codeagent op

`.aitask-scripts/aitask_codeagent.sh`:
- `SUPPORTED_OPERATIONS` (:26) += `merge-trails`.
- Prompt branches (case arms near :426, :476, :545, :575): claudecode →
  `CMD+=("/aitask-merge-trails ${args[*]}")`; codex →
  `prompt=$(build_skill_prompt "\$aitask-merge-trails" "${args[@]}")`;
  opencode → `CMD+=("--prompt" "/aitask-merge-trails ${args[*]}")`. Usage
  text (:644) += `merge-trails`.
- `defaults."merge-trails"` in BOTH `aitasks/metadata/codeagent_config.json`
  and `seed/codeagent_config.json` (same agent string as `trail`).

## Tests

- `tests/test_skill_render_aitask_merge_trails.sh` — model
  `test_skill_render_aitask_trail.sh`: goldens ×3, agent invariance (1b),
  profile-conditional sanity, no Jinja markers, walk-write reference
  rewrite, stub markers ×3 agents.
- `tests/test_merge_trails_skill_contract.sh` — model
  `test_trail_skill_contract.sh`; pins across ALL 3 goldens:
  full-write-set single confirmation (update + every FOLDED_REF rm);
  rm-targets-each-referencing-owner; preflight-before-author;
  validate `--expect-depth`; advisory candidates;
  approximate-base-explicit-selection; stale-base guard AFTER the final
  confirmation with reload/overwrite/abort; update-before-rm; rm-failure
  completing-command guidance + resumable re-invocation; RESUME never
  re-authors. Keep each pin greppable on one rendered line
  (golden-prose-pin rule).

  **Plus four pins required by t1647_2 (findings 1, 2a, 2b, 2c).** These are
  the failure modes t1647_2's own tests are structurally blind to — its drift
  tests build their own snapshots, and drift never reads `scope.kind` — so
  this contract test is where they become executable:
  1. **result-scope policy** — the step-3b rows are stated, an `ad_hoc`
     result snapshots as `--scope task <union of recorded member ids>`, and
     **no `--scope ad_hoc` exists**;
  2. **one snapshot, both values** — `inputs` and `input_digest` come from a
     single run over the deduplicated union, with `--owner`; source digests
     are never reused or combined;
  3. **no artifact refs in `generation.inputs`** — merge provenance lives in
     `merged_from` only (a mirrored `kind: other` record refuses the whole
     drift verdict);
  4. **`merged_from` is written wholesale as exactly two records** (base
     pre-merge + folded source) and never accumulates inherited ancestry;
     and the producer **refuses to author while preflight reports
     `RESUME:retirement_pending`**, whichever handle it names — the
     consumer-side half of finding 2a, without which the record-aware
     detection in t1647_3 is merely advisory.
- `tests/test_codeagent_merge_trails.sh` — model
  `test_codeagent_trail.sh`.
- `bash tests/test_skill_dispatch_contract.sh` — must pass (auto-covers the
  new skill).
- `./.aitask-scripts/aitask_skill_verify.sh` before committing.

## Verification

- All tests above green; `shellcheck .aitask-scripts/aitask_codeagent.sh`.
- `./.aitask-scripts/aitask_codeagent.sh resolve merge-trails` →
  `AGENT_STRING:`; `invoke merge-trails --dry-run art:a art:b` prints the
  slash command.
- Live dry read path: `/aitask-merge-trails trail-mobile` (approximate) in a
  sandbox session reaches the BASE_CANDIDATE question without any write.
- **The merged document must be CURRENT the moment it is written** (t1647_2
  finding 2b): `aitask_trail_gather.sh drift --trail <merged>` returns
  `CURRENT` with no `ERROR:` lines immediately after the merge, and `STALE`
  after mutating one source's task state. Check **both** result shapes — a
  same-scope merge (`topic`∪`topic` → `multi_topic`) **and** a mixed-scope one
  (→ `ad_hoc`), since only the second exercises the kind with no snapshot
  verb. A document that is stale on arrival is the exact failure the
  one-snapshot recipe exists to prevent, and it passes every schema and depth
  check, so nothing else catches it.
