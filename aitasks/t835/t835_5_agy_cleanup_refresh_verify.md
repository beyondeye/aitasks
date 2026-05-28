---
priority: medium
effort: medium
depends: [t835_4]
issue_type: chore
status: Ready
labels: [codeagent]
created_at: 2026-05-28 12:19
updated_at: 2026-05-28 12:19
---

## Context

Inverse counterpart of t812_5. Final cleanup pass for agy support:
populate the real model catalog, run end-to-end verification of the
detection path in a live agy session, and remove the consumed
migration reference doc.

Absorbs the t835_2 fold concern (migrated from t401_3): end-to-end
verification of the agy detection flow through
`aitask_parse_detected_agent.sh`. Lives here naturally — verification
requires agy actually running, which can only happen after t835_1-3
have landed and agy can be launched against this repo.

Primary inverse reference: `aiplans/archived/p812/p812_5_cleanup_pending_geminicli_aitasks.md`
→ `### For t814 (add-agy): inverse instructions`.

## Key Files / Resources

- `seed/models_agy.json` — replaced with real catalog.
- `aitasks/metadata/models_agy.json` — replaced with real catalog.
- `aidocs/geminicli_to_agy.md` — DELETE (`git rm`); inverse-
  instruction subsections in `aiplans/archived/p812/` are the
  durable reference going forward.

## Reference Files for Patterns

- `/aitask-refresh-code-models` skill — invoked to populate model
  catalogs from web sources.
- `./.aitask-scripts/aitask_parse_detected_agent.sh` — entry point
  for detection verification.

## Implementation Plan

1. **Refresh model catalog:** Run `/aitask-refresh-code-models`,
   select agy. Verify the produced `aitasks/metadata/models_agy.json`
   has real entries (not the stub). Copy to `seed/models_agy.json`
   for future installs. Commit both.

2. **Manual end-to-end verification:**
   a. Launch agy in this repo: `agy` from project root.
   b. From within the agy session, invoke a workflow that triggers
      model self-detection (e.g. `/aitask-pick` on any Ready task).
   c. Verify `./.aitask-scripts/aitask_parse_detected_agent.sh --agent agy --cli-id <model_id>`
      returns the expected `AGENT_STRING:agy/<name>` matching a
      `models_agy.json` entry.
   d. Verify the picked task's frontmatter `implemented_with` field
      is written correctly on completion.
   e. If detection fails, loop back to t835_1's surface choice and
      open a follow-up (do NOT silently patch — the surface
      decision should be revisited explicitly).

3. **Delete consumed reference doc:**
   ```bash
   git rm aidocs/geminicli_to_agy.md
   ```
   Per the parent task description, this file's content has been
   fully consumed by t835_1-4.

4. **Sanity grep:** `grep -r "\bagy\b" .aitask-scripts/ seed/ install.sh .github/workflows/release.yml`
   shows agy in every expected touchpoint (mirror of t812_5's
   cleanup check).

## Verification Steps

Steps 1-3 ARE the verification work for this child. Final coverage
check is step 4.

Acceptance criteria:
- `aitasks/metadata/models_agy.json` has ≥1 real (non-stub) model.
- An agy CLI session can complete a `/aitask-pick` end-to-end with
  correct attribution.
- `aidocs/geminicli_to_agy.md` no longer exists.
- `grep -r "\bgeminicli\b" .aitask-scripts/ seed/ install.sh` is
  empty (apart from intentional references in
  `aidocs/adding_a_new_codeagent.md` per t812_4 plan).
