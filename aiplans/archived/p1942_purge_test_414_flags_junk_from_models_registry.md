---
Task: t1942_purge_test_414_flags_junk_from_models_registry.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1942 — Purge `test_414_flags` junk from the models registry

## Context

Until t1937 (579dd60bc), `tests/test_verified_update_flags.sh` ran
`aitask_verified_update.sh` against the real repository, recording a
`test_414_flags` verified score on every run and pushing it to
`origin/aitask-data`. The key is test pollution, not a real skill, and must be
removed from every registry row.

**Precondition already satisfied (pre-plan):** the data branch was 72 local /
11 remote diverged. `aitask_sync.sh --batch` reconciled it (`MERGED`, guarded
merge 8621e612d, pushed; the 3 dirty task files of other live sessions —
t1932/t1936/t1938 — were left uncommitted). HEAD and `origin/aitask-data` now
agree (`0 0`).

**Current junk (re-queried after the sync):**
- `models_claudecode.json`: `opus4_6` (verified 91, 87 runs) and `opus4_7_1m`
  (verified 100, 3 runs) — both `.verified.test_414_flags` and
  `.verifiedstats.test_414_flags`.
- `models_codex.json`, `models_opencode.json`: none.

`jq . models_claudecode.json` round-trips byte-identically, so a plain `jq`
render changes only the deleted keys.

No code change: this is a one-off data rewrite. The test still uses
`test_414_flags`, but since t1937 only inside its isolated fixture.

## Implementation

1. **One-off CAS rewrite (scratchpad script, not committed).** Write
   `<scratchpad>/purge_test_414_flags.sh` that sources
   `.aitask-scripts/lib/registry_cas.sh` and calls
   `ait_cas_rewrite <registry> 5 render_purge`, where:
   ```bash
   render_purge() {  # must return, never exit (registry_cas.sh contract)
       jq 'del(.models[].verified.test_414_flags,
               .models[].verifiedstats.test_414_flags)' "$1" || return 1
   }
   ```
   Check the return: 0 swapped, 1 render/staging failed, 2 kept changing →
   report and stop. Run it over `aitasks/metadata/models_claudecode.json` only
   (the other two have nothing to purge; leave them untouched so they stay
   byte-identical).
   Before running, snapshot the file to the scratchpad (`before.json`) for the
   byte-identity check.

2. **Verify locally** (see Verification) before committing.

3. **Commit, path-scoped:**
   ```bash
   ./.aitask-scripts/aitask_task_commit.sh \
     -m "ait: Purge test_414_flags junk from claudecode model registry (t1942)" \
     aitasks/metadata/models_claudecode.json
   ```

4. **Push** with `./ait git push`. If rejected (a concurrent usage-count
   writer pushed meanwhile), reconcile with `./.aitask-scripts/aitask_sync.sh
   --batch` and re-check the query (a concurrent writer touches other rows'
   `usagestats`, which do not overlap the deleted keys).

5. **Step 9 (Post-Implementation)** — archival per the task workflow. No code
   commit on `main` (nothing in the code tree changes).

## Verification

- `jq '[.models[] | select(.verified.test_414_flags or .verifiedstats.test_414_flags) | .name]'`
  returns `[]` for all three registries locally, and for
  `git -C .aitask-data show origin/aitask-data:aitasks/metadata/models_claudecode.json`
  after the push.
- Other rows unchanged: `jq 'del(.models[].verified.test_414_flags, .models[].verifiedstats.test_414_flags)' before.json | cmp - <registry>`
  is identical (or, if a concurrent writer landed in between, the only
  diff is that writer's own usagestats lines — inspect `git diff` of the commit,
  which must show only removed `test_414_flags` lines).
- `git -C .aitask-data show --stat HEAD` touches only `models_claudecode.json`.

Residual note (not a risk of this plan): a checkout still running the
pre-t1937 test could re-add the key; t1937 owns that fix, and t1885 (Ready)
describes the same defect — worth checking whether it is now done.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.

## Final Implementation Notes
- **Actual work done:** Reconciled the diverged data branch with `aitask_sync.sh --batch` (`MERGED`, guarded merge 8621e612d, pushed; three other live sessions' dirty task files left uncommitted). Re-queried: junk only on `models_claudecode.json` rows `opus4_6` (91, 87 runs) and `opus4_7_1m` (100, 3 runs). Ran a one-off scratchpad script sourcing `lib/registry_cas.sh` → `ait_cas_rewrite <registry> 5 render_purge` with `jq 'del(.models[].verified.test_414_flags, .models[].verifiedstats.test_414_flags)'` — `CAS_RC:0 ATTEMPTS:1`. Registry diff: 39 deletions, 0 additions; `jq del(...) before.json | cmp - registry` identical, so every other row is byte-identical. The jq query now returns `[]` for all three registries.
- **Deviations from plan:** None.
- **Issues encountered:** None — the 11 remote commits touched only the registry and the local side had no registry commits, so the sync merge was conflict-free.
- **Key decisions:** No committed purge script — a one-off data fix; the test that produced the junk was already isolated by t1937.
- **Upstream defects identified:** None
