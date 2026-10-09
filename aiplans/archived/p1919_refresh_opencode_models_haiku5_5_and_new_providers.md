---
Task: t1919_refresh_opencode_models_haiku5_5_and_new_providers.md
Base branch: main
Output branch: main
---

# t1919 — Refresh OpenCode model registry (haiku 5.5 + new providers)

## Context

t1916 registered `claudecode/haiku5_5` and deliberately left the OpenCode side to
this carry-over task. `aitasks/metadata/models_opencode.json` and its seed twin
`seed/models_opencode.json` (currently byte-identical, last refreshed by t1867)
are behind what OpenCode 1.18.34 offers: `opencode/claude-haiku-5-5` and ~24
other models are missing, and 3 models it no longer offers are still `active`.
The owning path is the discovery script `.aitask-scripts/aitask_opencode_models.sh`.

## Counter-loss defect in the merge — fixed here, before the refresh (verified)

`aitask_usage_update.sh:200-248` writes a per-row `usagestats` field with an
**unlocked** `jq > tmp; mv` (no lock the refresh could share). The merge in
`aitask_opencode_models.sh:192-201` rebuilds every rediscovered row from the fresh
discovery object and carries over only `verified` and `verifiedstats`, so any
`usagestats` (or any other non-generated field) on a rediscovered row is silently
dropped. No OpenCode row carries `usagestats` today, but a usage bump that lands
**during discovery** (between any pre-run snapshot and the merge's read) is
erased with exit 0, and no snapshot-based check can see it — the reviewer
reproduced exactly that. A snapshot precondition therefore cannot protect this
run; the merge itself must preserve the field. That is a small, contained change
in the only refresh script (`aitask_opencode_models.sh` is the sole model-refresh
script), so it lands in this task rather than as a follow-up.

## Measured refresh scope (2026-10-08, live dry run + scratch-copy run)

- **+25 added**, all `active` with zeroed `verified`: `opencode_claude_haiku_5_5`,
  `opencode_claude_opus_5_5`, `opencode_claude_sonnet_5_5`,
  `openai_gpt_6_{luna,sol}[_fast]`, `openai_gpt_6_1_sol[_fast]`,
  `openai_gpt_6_astra_ultrafast`, `openai_gpt_5_4_mini_flex`,
  `opencode_gpt_6_{luna,sol}`, `opencode_gpt_6_1_sol`, `opencode_grok_4_7`,
  `opencode_mistral_large_4`, `opencode_qwen3_8_{flash,max}`,
  `opencode_deepseek_v4_1_flash`, and free models `opencode_exo_free`,
  `opencode_fledge_alpha_free`, `opencode_ling_3_1_flash_free`,
  `opencode_longcat_2_5_preview_free`, `opencode_mimo_v2_6_flash_free`,
  `opencode_space_bunny_free`.
- **3 flipped to `unavailable`**: `opencode_mimo_v2_5_free`,
  `opencode_muse_spark_1_2_contributor_free`, `opencode_union_alpha`.
- **0 removed.** 104 → 129 rows (107 active, 22 unavailable).
- Existing rows: all `verified`/`verifiedstats` unchanged; one `notes` refresh
  (`opencode_gpt_5_6_sol` drops the upstream "(50% Off)" tag).
- No `codeagent_config.json` default, supersession rule or test references a
  flipped model; t1912 (touches `models_*.json`) is `Ready`, not in flight.

## Steps

### 1. Fix the merge to preserve every non-generated field

`.aitask-scripts/aitask_opencode_models.sh`, `merge_with_existing()`, the
rediscovered-row branch (currently lines 192-201). Replace the two hand-picked
carries with "existing row, minus the fields discovery regenerates, overlaid on
the discovered row":

```jq
($discovered | map(
    .name as $n |
    .cli_id as $id |
    ($exist_name_map[$n] // $exist_cli_map[$id]) as $existing |
    if $existing then
        # Discovery owns name/cli_id/notes/status; everything else on the
        # existing row (verified, verifiedstats, usagestats, ...) is carried
        # over, so a counter written by another updater is never dropped.
        . + ($existing
             | del(.name, .cli_id, .notes, .status)
             | with_entries(select(.value != null)))
    else
        .
    end
)) as $updated_discovered |
```

- `with_entries(select(.value != null))` keeps today's `//` fallback semantics:
  an existing `verified: null` still yields the discovered default.
- `verifiedstats` default stays `{}` from the discovered row when absent.
- Update the comment above the block ("preserve existing verified scores and
  stats") to say all non-generated fields are preserved. The header comment at
  line 166 likewise.
- Unavailable rows (`$unavailable`) already keep the whole existing row — no change.

### 2. Test the fix — `tests/test_opencode_models_merge.sh` (new)

Same fixture pattern as `tests/test_opencode_models_reserved.sh` (copy the script
+ `lib/terminal_compat.sh` into a temp project, stub `opencode` on `PATH` printing
a canned `opencode models --verbose` listing, run with `--sync-seed`). Cases:

1. Rediscovered row keeps `usagestats`, `verified`, `verifiedstats` and an
   arbitrary extra field byte-for-byte; `notes` is regenerated.
2. Row matched by `cli_id` under a changed name keeps its `usagestats`.
3. A previously `unavailable` row that is rediscovered becomes `active` and keeps
   its counters.
4. **The reviewer's race:** the stub `opencode` first writes a `usagestats` entry
   into the registry with `jq` (simulating `aitask_usage_update.sh` landing during
   discovery), then prints the listing. After the refresh exits 0 the count is
   present in both the metadata file and the seed.
5. Existing `verified: null` falls back to the discovered default (semantics kept).

Red proof: run the new file against the **pre-fix** script (copy from
`git show HEAD:.aitask-scripts/aitask_opencode_models.sh` into the fixture via an
env override, or run once before applying step 1) and confirm cases 1, 2 and 4
fail; then green after the fix. Also re-run `tests/test_opencode_models_reserved.sh`
and `shellcheck .aitask-scripts/aitask_opencode_models.sh`.

### 3. Run the refresh inside a git-coordinated window

Step 1 fixes writes that land before the merge's read. A counter write after that
read, or at any point before our metadata commit, is still a lost-update race,
and it cannot be ruled out by watching processes: `aitask_usage_update.sh` and
`aitask_verified_update.sh` are plain shell writers any agent (any machine) can
run. What every successful counter write **does** leave is a commit touching
`aitasks/metadata/models_opencode.json`. With origin configured (it is) the
writers commit in a temp clone, push to `origin/aitask-data`, then fast-forward
local (`lib/verified_update_lib.sh:168-242`). Without a remote they commit
locally. So the window is coordinated through those commits. It runs from the pin
below through our own metadata commit **and push** (step 5), not only through the
script run. Broader writer locking stays out of scope.

```bash
cp aitasks/metadata/models_opencode.json "$S/pre_run.json"
(cd .aitask-data && git fetch --quiet origin aitask-data \
  && git status --porcelain -- aitasks/metadata/models_opencode.json \
  && git log -1 --format=%H HEAD -- aitasks/metadata/models_opencode.json \
  && git log -1 --format=%H origin/aitask-data -- aitasks/metadata/models_opencode.json) \
  > "$S/pin.txt"
./.aitask-scripts/aitask_opencode_models.sh --sync-seed
```

- Pin preconditions: the file is **clean** in the data worktree, and local HEAD
  already contains the origin tip for the path (`merge-base --is-ancestor`). If
  either fails, stop and sync first (`./ait sync`), then re-pin.
- `pgrep -a opencode` before/after is recorded as **supporting evidence only**,
  never as proof that no write occurred.

### 4. Check the result

- `jq . aitasks/metadata/models_opencode.json seed/models_opencode.json >/dev/null`
  and `cmp` the two (seed is a byte copy).
- **Field-preservation diff (python) vs `pre_run.json`:** every pre-run row still
  exists; for each, every field except the regenerated `notes`/`status` is
  unchanged (covers `verified`, `verifiedstats`, `usagestats`, anything else).
  Any difference → stop before committing. Review added/flipped rows that differ
  from the measured list.
- **Target assertion — the gate:**
  ```bash
  jq -e '[.models[] | select(.name=="opencode_claude_haiku_5_5"
           and .cli_id=="opencode/claude-haiku-5-5"
           and .status=="active")] | length == 1' aitasks/metadata/models_opencode.json
  ./.aitask-scripts/aitask_codeagent.sh list-models --active-only opencode \
    | grep -F 'MODEL:opencode_claude_haiku_5_5 CLI_ID:opencode/claude-haiku-5-5 STATUS:active'
  ```
  Non-zero (missing or `unavailable` after drift) → goal not met; stop and report.
- Registry tests: `bash tests/test_codeagent.sh`,
  `python3 -m pytest -q tests/test_model_supersession.py`.

### 5. Review and commit (Step 8), following the t1867 precedent

- Code commit (code branch), by path:
  `git commit -F - -- .aitask-scripts/aitask_opencode_models.sh tests/test_opencode_models_merge.sh seed/models_opencode.json`
  — `chore: Refresh opencode model registry and preserve usage counters on refresh (t1919)`
  (`git add` the new test file first).
- Metadata (task-data branch) — **close the window first**, immediately before
  committing: re-fetch and recompute the two tips from `pin.txt`. If either local
  HEAD or `origin/aitask-data` has a new commit touching the path since the pin, a
  counter write landed inside the window. **Stop, do not commit**, and ask the
  user. The recovery is to set aside only our generated file, `./ait sync`, then
  re-run step 3, whose fixed merge now carries the new counter. Otherwise commit
  and push at once:
  `./.aitask-scripts/aitask_task_commit.sh -m "ait: Refresh opencode model registry (t1919)" aitasks/metadata/models_opencode.json`
  then `./ait git push`. A rejected (non-fast-forward) push means a write landed
  between the re-check and the push. Treat it the same way: stop, never
  force-push, never resolve the JSON by hand.

### 6. Step 9

Current-branch mode, no merge: archive via `./.aitask-scripts/aitask_archive.sh 1919`.

## Verification

- New `tests/test_opencode_models_merge.sh` fails on the pre-fix script (cases
  1/2/4) and passes after; `test_opencode_models_reserved.sh` still passes;
  shellcheck clean.
- No commit touching `models_opencode.json` landed on local HEAD or
  `origin/aitask-data` between the pin and our push; the push fast-forwarded.
- `opencode_claude_haiku_5_5` exists exactly once with cli_id
  `opencode/claude-haiku-5-5`, `status: active` (`jq -e`), and is in
  `list-models --active-only opencode`.
- Both files parse and are identical; pre/post diff shows only additions, status
  flips and notes refreshes.

## Risk

### Code-health risk: low
- The merge change could alter fields beyond counters (e.g. resurrect a stale
  field the regeneration used to clear) · severity: low (rows carry only
  name/cli_id/notes/status/verified/verifiedstats[/usagestats]; discovery-owned
  fields are explicitly excluded) · → mitigation: step-2 cases 1/3/5 pin the
  per-field behaviour.

### Goal-achievement risk: low
- Live drift could leave the target absent or `unavailable` · severity: low ·
  → mitigation: step-4 exact `jq -e` gate on name + cli_id + `active`.
- A counter write after the merge's read (until our push) would be overwritten ·
  severity: low · → mitigation: step-3 pin + step-5 re-check and fast-forward-only
  push, which detect it through the writers' own commits and stop. Process checks
  are supporting evidence only. Writer locking itself is out of scope.

## Final Implementation Notes
- **Actual work done:** Fixed `merge_with_existing()` in `.aitask-scripts/aitask_opencode_models.sh` to overlay every existing field except the discovery-owned `name`/`cli_id`/`notes`/`status` (nulls dropped so defaults still apply), replacing the hand-picked `verified`/`verifiedstats` carry. Added `tests/test_opencode_models_merge.sh` (5 cases, 19 checks; `OPENCODE_MODELS_SCRIPT` override for the red proof). Then ran the refresh with `--sync-seed` inside the git-pinned window: +25 models (incl. `opencode_claude_haiku_5_5`, `opencode_claude_opus_5_5`, `opencode_claude_sonnet_5_5`), 3 flipped to `unavailable` (`opencode_mimo_v2_5_free`, `opencode_muse_spark_1_2_contributor_free`, `opencode_union_alpha`), 0 removed, 104 → 129 rows (107 active / 22 unavailable) — identical to the planning measurement.
- **Deviations from plan:** None in substance. Externalization needed `--internal <path>` (the internal plan was older than the helper's recency window → `NOT_FOUND:no_internal_files` on the first call).
- **Issues encountered:** The plan went through three review rounds before approval: a snapshot precondition cannot see a counter write landing during discovery; process absence (`pgrep`) is not exclusion because the counter writers are plain shell scripts; so the merge was fixed in-task and the window coordinated through the writers' own commits (pin local + origin tips for the path, re-check before the metadata commit, fast-forward-only push).
- **Key decisions:** Fix by ownership (`del` the owned fields) rather than extending the keep-list, so any future counter field survives too. Pin results: file clean, local = origin = `16be0047` (t1867) before the run; pre-run `usagestats` count 0. Field-preservation diff vs the fresh pre-run snapshot: no lost row, no changed non-generated field; only notes change is `opencode_gpt_5_6_sol` dropping the upstream "(50% Off)" tag.
- **Verification:** red proof — 6 checks fail on `HEAD`'s script, 19/19 pass after; `test_opencode_models_reserved.sh` 22/22; shellcheck clean apart from the pre-existing SC1091 info; `jq -e` gate (name + cli_id + `active`) and `list-models --active-only opencode` both find `opencode_claude_haiku_5_5`; `test_codeagent.sh`, `test_usage_update.sh` (71), `test_verified_update.sh` (173), `test_codeagent_{trail,work_report,discuss,op_wiring}.sh`, and pytest `test_model_supersession.py` + `test_aitask_stats_py.py` (91) all pass.
- **Upstream defects identified:**
  - `.aitask-scripts/aitask_opencode_models.sh:178-307 — the refresh's read→write of models_opencode.json is uncoordinated with aitask_usage_update.sh / aitask_verified_update.sh: a counter write landing between the merge's read and the final write is still last-writer-wins (only detectable after the fact through the writers' commits); a shared writer lock or a commit-based compare-and-swap would close it`
