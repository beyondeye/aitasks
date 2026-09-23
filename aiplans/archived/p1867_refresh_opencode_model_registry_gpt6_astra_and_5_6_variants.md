---
Task: t1867_refresh_opencode_model_registry_gpt6_astra_and_5_6_variants.md
Base branch: main
Output branch: main
---

# Plan: t1867 — Refresh the OpenCode model registry

## Context

`aitasks/metadata/models_opencode.json` (67 entries, byte-identical to
`seed/models_opencode.json`) was last refreshed on 2026-07-24 and lacks the GPT-6
and most GPT-5.6 models. The only supported writer is
`.aitask-scripts/aitask_opencode_models.sh` (whole-registry rewrite from
`opencode models`; preserves `verified`/`verifiedstats`; soft-deletes vanished
models as `status: "unavailable"`). Scope decided in the task: accept the full
refresh.

## Premise re-measured (2026-09-23, opencode 1.18.32, auth: OpenCode Zen api + OpenAI oauth)

The task says to update its body if the premise moved. It moved:

| claim in task body | measured now |
|---|---|
| GPT-6 is `opencode/gpt-6-astra` only; no `openai/gpt-6-*` | **3** GPT-6 ids: `opencode/gpt-6-astra`, `openai/gpt-6-astra`, `openai/gpt-6-astra-fast` |
| `openai/` offers 12 gpt-5.6 ids (9 missing) | `openai/` offers **6**: `gpt-5.6-{luna,sol,terra}` + `-fast` each (3 new). No bare `gpt-5.6`, `-fast`, `-pro`, or `*-pro` |
| Total 108 (92 active, 16 unavailable) | **104 (85 active, 19 unavailable)** |
| 16 flip to unavailable | 11 of the 19 are *already* unavailable; **8 newly flip**: `openai/gpt-5.2`, `openai/gpt-5.3-codex`, `openai/gpt-5.5-pro`, `opencode/claude-opus-4-1`, `opencode/deepseek-v4-flash-free`, `opencode/minimax-m2.5-free`, `opencode/nemotron-3-super-free`, `opencode/ring-2.6-1t-free` |

The same three `openai/` ids (5.2, 5.3-codex, 5.5-pro) remain offered under
`opencode/`, so the openai-side flips reflect what the OpenAI-OAuth provider
lists on this box — the machine-dependence caveat the task names.
No config/default references any flipped id (`codeagent_config.json` has no
`opencode/` entry; the only other hits are test fixtures that build their own
registries).

## Implementation

1. **Update the task body** (`aitasks/t1867_…md`) so every measured claim
   matches this run:
   - "Premise correction" and "GPT-5.6 is NOT complete" → the measured table
     above (3 GPT-6 ids; 6 `openai/gpt-5.6*` ids, 3 of them new).
   - "The registry is broadly stale" → 104 total (85 active, 19 unavailable)
     against 67; 11 of the 19 were already unavailable; the **8 newly flipped**
     ids listed by name (replacing the stale 108 / 16 / example list).
   - Verification bullets → 3 GPT-6 ids, 6 openai 5.6 ids.
2. **Snapshot the pre-refresh registry** (for step 4):
   `cp aitasks/metadata/models_opencode.json <scratchpad>/before.json`, and save
   the reviewed dry-run's expected transitions to `<scratchpad>/expected_*.txt`:
   the 8 newly-unavailable ids, and the new-id list (dry-run ACTIVE ids not
   present in `before.json`).
3. **Apply the refresh with seed sync:**
   `./.aitask-scripts/aitask_opencode_models.sh --sync-seed`
   (this re-runs discovery, so its result may differ from the reviewed dry-run).
4. **Transition check against the reviewed dry-run — before committing.** With
   jq, compute from `before.json` vs the written file:
   - `active→unavailable` ids, `unavailable→active` ids, and added ids;
   - `diff` each against the expected lists from step 2.
   Expected: flips = exactly the 8 reviewed ids, no reverse flips, additions =
   the reviewed new-id list. **Any difference → stop and show it to the user
   before committing** (and correct the task body to match if accepted).
5. **Consistency:** counts = 104 in both files; `cmp` metadata vs seed identical.

## Verification

- `jq -r '.models[]|select(.cli_id|test("gpt-6"))|.cli_id'` on both files →
  the 3 GPT-6 ids.
- `jq -r '.models[]|select(.cli_id|startswith("openai/gpt-5.6"))|.cli_id'` →
  6 ids, all `status: "active"`.
- `jq '.models|length'` equal in both (104); `cmp` identical.
- `jq -e '[.models[]|select(.status==null)]|length==0'` true; `jq .` parses.
- Existing verified scores preserved: spot-check an entry with a nonzero score
  is unchanged (`git diff` shows no `verified` value change on retained entries).
- Regression: `bash tests/test_codeagent_discuss.sh`,
  `tests/test_codeagent_op_wiring.sh`, `tests/test_codeagent_work_report.sh`,
  `tests/test_codeagent_trail.sh` (they copy the real registry).

## Commits

- Task data: `./.aitask-scripts/aitask_task_commit.sh -m "ait: Refresh opencode model registry (t1867)" aitasks/metadata/models_opencode.json aitasks/t1867_…md`
- main: `git commit -m "chore: Sync opencode model registry to seed (t1867)" -- seed/models_opencode.json`

Then Step 9 (Post-Implementation): archival via the task-workflow.

## Risk

### Code-health risk: low
- Tool-generated whole-file rewrite of two JSON registries; consumers read
  `verified` via `.get(op, 0)`, so new entries' 3-key default `verified` block
  (vs 5 keys on older entries) is harmless · severity: low · → mitigation: none
  (covered by the Verification regression tests)

### Goal-achievement risk: medium
- Catalog drifted from the task premise (GPT-6 = 3 ids; openai 5.6 = 6 ids, not
  12); the registered set differs from what the task body promised ·
  severity: medium · → mitigation: none (plan step 1 rewrites the task body
  to the measured set; user approves at checkpoint)
- 3 `openai/` flips (5.2, 5.3-codex, 5.5-pro) may be OAuth-plan filtering rather
  than retirement · severity: low · → mitigation: none (soft-delete only; a
  later refresh on a box that lists them flips them back to active)

## Implementation notes

- Steps 1–5 done. Transition check: flips = the 8 reviewed ids, 37 additions =
  the reviewed list, 0 reverse flips, 0 dropped; metadata ≡ seed (104).
- **Deviation — generator fix.** First apply broke the seed parity tests
  (`test_codeagent_work_report.sh` Test 7, `test_codeagent_trail.sh`):
  `aitask_opencode_models.sh` still emitted a 3-key default `verified` block
  (`pick`/`explain`/`batch-review`) for newly discovered models, predating the
  `work-report` (t1162_2) and `trail` (t1210) operations, whose seed scores must
  mirror `explain`. Added `"work-report": 0, "trail": 0` to the template, restored
  the pre-refresh snapshot and re-applied (the merge preserves an existing entry's
  `verified`, so a plain re-run would have kept the 3-key blocks). All 104
  entries now carry 5 keys; existing verified scores unchanged.
- Tests: codeagent_discuss / op_wiring / work_report / trail all pass;
  `tests/test_metadata_writer_inventory.py` passes; shellcheck clean apart
  from the pre-existing SC1091 info.

## Final Implementation Notes
- **Actual work done:** Refreshed `models_opencode.json` (metadata + seed, identical) from OpenCode discovery: 67 → 104 entries (85 active, 19 unavailable); 37 additions incl. `opencode/gpt-6-astra`, `openai/gpt-6-astra{,-fast}`, `openai/gpt-5.6-{luna,sol,terra}-fast`; 8 newly unavailable. Task body rewritten to the re-measured premise.
- **Deviations from plan:** One-line generator fix in `aitask_opencode_models.sh` (default `verified` block gains `work-report`/`trail`), then re-applied from the pre-refresh snapshot. Registry and seed committed in one code commit together with the script fix instead of a seed-only commit.
- **Issues encountered:** Seed parity tests failed on the first apply (3-key default `verified` blocks); fixed as above.
- **Key decisions:** Accepted the catalog as measured on 2026-09-23 rather than the task's original id set; verified the applied transitions against the reviewed dry-run before committing.
- **Upstream defects identified:** None
