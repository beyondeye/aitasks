---
Task: t1647_2_trail_schema_merged_from_provenance.md
Parent Task: aitasks/t1647_merge_trails_skill_shared_helpers_board_command_docs.md
Sibling Tasks: aitasks/t1647/t1647_1_*.md … t1647_6_*.md
Worktree: (none — profile 'fast', current branch)
Base branch: main
Output branch: main
plan_verified: []
---

# Plan: t1647_2 — `merged_from` merge provenance in the trail schema

## Context

A merged trail must record where it came from, and the recorded version of
the folded (retired) source is what makes an interrupted retirement
deterministically resumable (t1647_3 reads it). Optional-additive schema
change — **no `schema_version` bump**: root is `additionalProperties: false`
with const `"1.1.0"` and the loader rejects other versions, so any
required-field or version change would invalidate every stored trail. The
`overview` precedent (t1505_3) is the model.

## Steps

1. **Edit BOTH schema copies identically** —
   `aidocs/implementation_trail.schema.json` and
   `.aitask-scripts/lib/implementation_trail.schema.json` (byte-identical
   today; keep them byte-identical). Add to root `properties`:

   ```json
   "merged_from": {
     "description": "Provenance of a trail-to-trail merge: the source trails whose content was re-authored into this document. Written by /aitask-merge-trails; absent on any trail that never absorbed another. The recorded version of the folded (retired) source makes an interrupted retirement deterministically resumable.",
     "type": "array", "minItems": 1,
     "items": {
       "type": "object", "additionalProperties": false,
       "required": ["handle", "version", "merged_at"],
       "properties": {
         "handle":    {"type": "string", "minLength": 1},
         "version":   {"type": "string", "minLength": 1},
         "title":     {"type": "string"},
         "merged_at": {"$ref": "#/$defs/timestamp"}
       }
     }
   }
   ```

   (Do NOT add `merged_from` to root `required`.)

2. **Provenance convention** (schema `description` text is the carrier here;
   the RFC child t1647_6 documents it in prose): a merged doc's
   `generation.inputs` also carries one `{"kind": "other", "ref":
   "<handle>@<version>"}` entry per source trail. The `inputs` `kind` enum
   already contains `other` — no enum change.

3. **Fixture:** add `aidocs/implementation_trail_examples/merged_trail.json` —
   a small deep trail (2 waves, 3 entries) carrying `merged_from` (two
   entries: the folded source and the base's pre-merge version) and the two
   `kind: other` inputs. Must satisfy every existing design-contract check
   (project-qualified `task` refs + `topic`, strictly increasing ordinals /
   positions, resolvable evidence_refs, narrative first-class, no `anchor`
   keys, hard_depends provenance facts).

4. **Tests.**
   - `tests/test_trail_schema.py`: merged_from accepted on a valid doc;
     rejected shapes (missing `version`, extra item key, empty array,
     non-timestamp `merged_at`); doc WITHOUT merged_from still valid
     (backward compat — the load-bearing case). Add a schema-copies
     byte-identical assertion if none exists yet.
   - `tests/test_implementation_trail_design.py`: extend `FIXTURE_NAMES`
     with `merged_trail.json` (`test_no_unexpected_fixture_files` REQUIRES
     the list edit), plus a stdlib-style structural check that the fixture's
     `merged_from` records match `generation.inputs` `other` refs.

5. **Depth: no validator change.** Deep-wins reconciliation is preflight
   policy (t1647_3). `_check_depth_contract` / `_check_lite_shape` +
   `--expect-depth` already enforce marker-matches-authoring; leave
   untouched.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests` green
  (test_trail_schema.py, test_implementation_trail_design.py at minimum).
- `diff aidocs/implementation_trail.schema.json .aitask-scripts/lib/implementation_trail.schema.json`
  → empty.
- `./.aitask-scripts/aitask_trail_depth.sh validate aidocs/implementation_trail_examples/merged_trail.json --expect-depth deep`
  → `VALID:<trail_id>`.
- Existing live trails still load (`ait board` By-Trail spot check or
  `aitask_trail_depth.sh validate` on a fetched live doc).
