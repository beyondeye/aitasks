---
Task: t1885_isolate_verified_update_flags_test_from_real_repo.md
Base branch: main
Output branch: main
---

# t1885 — verified-update flags test isolation, opencode name collisions, stale `ait opencode-models` hint

## Context

t1885 (an upstream_defect follow-up from t1884) lists three defects:

1. `tests/test_verified_update_flags.sh` ran against the real repo and pushed
   `test_414_flags` scores to `origin/aitask-data`.
2. `convert_to_model_name` (`.aitask-scripts/aitask_opencode_models.sh:67`) is
   non-injective. `-`, `.` and `_` in the model part all map to `_`, so
   `opencode/foo-bar`, `opencode/foo.bar` and `opencode/foo_bar` all derive
   `opencode_foo_bar`. (The task's `a_b/c` example cannot occur: the
   discovery regex `^[a-zA-Z]+/` only accepts letters in provider ids. The
   defect is real within one provider.) `merge_with_existing` builds
   `name → row` maps with `add`, so a collision silently drops one model, or
   carries one model's verified stats onto another.
3. `lib/agent_string.sh:165` tells users to run `ait opencode-models`, a
   command the dispatcher never routed (`git log -S` on `ait` finds no such
   route). The script's own header (lines 8-11) and `--help` usage (line 40)
   say the same thing. Note from t2333: that header misled a task author too.

**Defect 1 is already fixed** by commit `579dd60bc` (t1937). The test now uses
`setup_local_metadata_repo` from `tests/lib/metadata_update_fixture.sh`,
asserts the fixture has no remote, and never `cd`s into the real repo.
Running it here gives 20/20 PASS. The exit-3-on-dirty-worktree failure is gone
with it: the fixture has no remote and no data worktree, so the script never
reaches the `UPDATED_REMOTE_ONLY` path. So no change is needed for defect 1.
The closing notes record this, citing t1937.

Current registries (`aitasks/metadata/models_opencode.json`,
`seed/models_opencode.json`) were checked: no duplicate names, and every row's
name equals its derived name. A fail-closed guard therefore does not break
today's refresh.

## Implementation

### Step 1 — Row-identity guard in `.aitask-scripts/aitask_opencode_models.sh`

Add `collision_guard_message <registry_file>`, a sibling of the existing
`reserved_guard_message`, with the same contract: print a refusal message
when a conflict exists, print nothing when clean, return 1 only on a jq
failure.

**Rule (the merge's precondition, stated exactly).** `merge_with_existing`
selects rows through `add`-built `name → row` and `cli_id → row` maps, which
silently keep the last of any repeated key. Usage and verification history
in the separate aitask-stats store (`lib/model_stats_store.py`, keyed
`models.<name>`) is also keyed by name. The guard therefore refuses when
**any** of these holds:
- (a) a name occurs **more than once in the discovered set** (two cli_ids
  derive it, or the listing repeats a model);
- (b) a name occurs **more than once in the registry**, even when the rows
  share a cli_id. Concern 3: two `opencode_foo` / `opencode/foo` rows with
  different `verified` scores, where the rediscovery silently keeps the last;
- (c) a name occurs once on each side but with **different cli_ids** (a
  discovered model would take over a registry row's name, and with it that
  name's aitask-stats history);
- (d) a cli_id occurs **more than once in the registry** (under different
  names). The merge carries one row and drops the other via
  `$disc_cli_map`, losing its `verified`. This is the same silent-merge
  class, and both real registries have 0 such duplicates today.

Exactly one matching row on each side (same name, same cli_id) is fine. So
is the cli_id-keyed rename (registry `legacy_foo_name` / `opencode/foo` →
discovered `opencode_foo` / `opencode/foo`, which is merge test 2): it
breaks none of (a)-(d).

jq shape: build `[{name, cli_id, src}]` for each side, then emit one line
per offending key:
```jq
def dups(f): group_by(f) | map(select(length > 1));
($disc | dups(.name))              as $a |
($reg  | dups(.name))              as $b |
($reg  | dups(.cli_id))            as $d |
([$disc[], $reg[]] | group_by(.name)
   | map(select(length == 2 and (map(.src) | unique | length) == 2
                and (map(.cli_id) | unique | length) == 2))) as $c |
...  # format each group as "  <key>: <cli_id> (<src>), ..."
```
Pass the registry rows only when the file exists, else `[]`.

**Recovery text (concern 1 — never moves a name away from its history).**
The aitask-stats history is keyed by name, so renaming or removing a
registry row does **not** move its history. A discovered model that then
takes the name would inherit the old model's history. The message
therefore never advises renaming. Per class:
- (c) registry row vs discovered model: "If `<discovered cli_id>` is the
  same model under a new id, change that row's `cli_id` to it and keep its
  name. The usage and verification history recorded under `<name>` then
  stays with the model it belongs to. Otherwise leave the row as it is.
  Renaming or removing it would not move that history, and the discovered
  model would inherit it. A different model cannot be registered under this
  name."
- (a) two discovered models: "The naming scheme cannot tell these cli_ids
  apart, and editing the registry cannot fix that. Disconnect one of them in
  OpenCode and report the collision."
- (b)/(d) duplicate registry rows: "Leave these rows in place. Each may
  carry its own `verified` values and legacy counters, and each name may have
  its own usage and verification history on the aitask-stats branch. This
  refresh cannot tell which is right, so do not delete either one until you
  have reconciled their metadata and any separate history by hand. The
  refresh changes nothing until then." The refresh only refuses; it never
  migrates.

Every message starts with "Refusing to update $METADATA_FILE: … Nothing was
written." Each class's advice appears only when that class is present,
mirroring the reserved message's split.

Wire it in at both existing guard points, so it fails closed exactly like
the reserved guard:
- **Pre-write** (after the reserved guard, before `merge_with_existing` and
  the `--dry-run` branch): `collision_msg=$(collision_guard_message "$METADATA_FILE") || die "Failed to read $METADATA_FILE"`, then `die` if
  non-empty. `--list` stays unguarded: it writes nothing, and printing the
  derived names is how a user sees the duplicate.
- **Inside the CAS render** (`render_refresh`): rename `RESERVED_MSG` to
  `GUARD_MSG`. Set it from the reserved guard, then (if that is empty) from
  the collision guard, each `|| return 1`, and `[[ -z "$GUARD_MSG" ]] || return 1`. Update the post-CAS `die "$RESERVED_MSG"` block to use
  `GUARD_MSG`, with its comment saying a guarded row arrived after the
  pre-write guard. This catches a colliding row a concurrent writer lands
  between the pre-check and the swap.

Update the `convert_to_model_name` comment to say that the mapping is
non-injective and that the collision guard is what makes it safe.

### Step 1b — Seed from the checked bytes (concern 2)

Today `--sync-seed` re-reads the live `$METADATA_FILE` *after* the swap
(lines 373-374), so a row landing between the swap and that read reaches
the seed unguarded. Fix:
- In `render_refresh`, capture the output instead of streaming it:
  `rendered="$(jq --indent 2 '.models |= sort_by(.name)' <<< "$merged")" || return 1; RENDERED_REGISTRY="$rendered"; printf '%s\n' "$rendered"`.
  `ait_atomic_render` runs the render in the same shell (`"$@" > "$tmp"`,
  `lib/atomic_write.sh:165`), and `RESERVED_MSG` / `merged` already
  propagate that way. Each retry overwrites the variable, so after a
  successful `ait_cas_rewrite` it holds exactly the bytes that were swapped
  in. That render also passed both guards.
- The seed step strips from those bytes:
  `jq -f "$SCRIPT_DIR/lib/model_stats_strip.jq" <<< "$RENDERED_REGISTRY" > "$seed_tmp"`.
  The success line's counts already come from `$merged`, not from the file.
- **Publish only while the registry still holds the checked bytes.**
  Without this check, a slower refresh could overwrite the seed of a newer
  refresh that completed both of its writes in between. Before the
  `mv "$seed_tmp" "$SEED_FILE"` (after the strip, as the last step), compare
  the live registry with the checked bytes:
  `[[ "$(cat "$METADATA_FILE")" == "$RENDERED_REGISTRY" ]]`. Both sides are
  `$( )`-trimmed the same way. On divergence, `rm -f "$seed_tmp"` and
  `warn "$METADATA_FILE changed after this refresh wrote it (a concurrent refresh or writer) — $SEED_FILE not synced; re-run with --sync-seed"`.
  Exit status stays 0, consistent with the existing "could not render the
  seed" warn path. A residual window between that compare and the `mv` is
  inherent without a lock. It is reduced to two adjacent statements, and the
  plan accepts it.
- No runtime test seam is added (see Step 3, case 5b).

### Step 2 — Fix the `ait opencode-models` references (text, no new command)

Fix the text rather than adding a dispatcher route. The supported entry
points are already `/aitask-refresh-code-models` and
`bash .aitask-scripts/aitask_opencode_models.sh` (website
`docs/installation/updating-model-lists.md` already documents the latter).
Adding a public `ait` verb would be new feature surface, beyond this bug's
scope.
- `.aitask-scripts/aitask_opencode_models.sh` header lines 8-11 and the
  `--help` usage line 40: `ait opencode-models` → `bash .aitask-scripts/aitask_opencode_models.sh`.
- `.aitask-scripts/lib/agent_string.sh:165`: `Run 'ait opencode-models' to refresh.` → `Run /aitask-refresh-code-models (for opencode: bash .aitask-scripts/aitask_opencode_models.sh) to refresh the model list.`
  (The `unavailable` status check is agent-generic, so the hint now names the
  generic refresh skill first.)
- Leave `CHANGELOG*.md` and the v0.9.0 blog post alone. They are historical
  release records, not current docs.

### Step 3 — Tests: new `tests/test_opencode_models_collision.sh`

Model it on `tests/test_opencode_models_reserved.sh`: the same
`setup_fixture`, which copies the script and its libs and puts a stub
`opencode` on PATH; `run_refresh --sync-seed`; `enter_scratch_cwd`; and the
assert helpers. Cases:
1. Two discovered models collide (`opencode/foo-bar` and `opencode/foo.bar`),
   with an existing registry → exit ≠ 0, the message names
   `opencode_foo_bar` and both cli_ids marked `(discovered)`, the discovered
   pair advice is present and the registry-row advice absent, "Nothing was
   written", the registry is byte-identical (`cmp`), and no seed is written.
2. A discovered model collides with a registry row (discovered
   `opencode/foo-bar`; registry row `opencode_foo_bar` / `opencode/foo.bar`
   with verifiedstats) → refused, and the class-(c) advice says to "keep its
   name" / "would not move that history". Assert the message does **not**
   contain "rename" advice. The registry is byte-identical and the row's
   verifiedstats are intact.
3. Two registry rows share a name with different cli_ids, and discovery is
   clean → refused.
3b. Two registry rows `opencode_foo` / `opencode/foo` with **unequal**
   `verified.pick` (90 and 40), with `opencode/foo` rediscovered → refused
   and the registry byte-identical. Pre-fix: the run succeeds and keeps only
   one score.
3c. Two registry rows with the same cli_id under different names → refused.
4. `--dry-run` with a discovered collision → refused.
5. A collision that arrives inside the CAS window:
   `AIT_CAS_BEFORE_SWAP_HOOK` (the seam in `lib/registry_cas.sh`, used by
   `test_opencode_models_merge.sh` tests 6-8) runs a script that appends a
   colliding row to the registry (idempotent, adding the row only if
   absent). The re-render must refuse: exit ≠ 0, a collision message, and
   the registry left as the hook wrote it (no merged write).
5b. Post-swap changes, injected without a runtime seam. The fixture puts a
   `jq` wrapper first on PATH. When its arguments include `-f` with
   `model_stats_strip.jq` (the seed strip starting), it runs
   `$FIX/inject.sh` once (a marker file makes it one-shot, and an env guard
   stops recursion), then `exec`s the real `jq` (resolved before the PATH
   change). The same fixture exercises the pre-fix and post-fix scripts
   unchanged.
   - **Conflicting-row injection:** `inject.sh` appends `opencode_foo` /
     `opencode/other` to the live registry. Post-fix: exit 0, the seed is
     not written (or left as it was before the run), the "not synced"
     warning is shown, and `opencode/other` is absent from the seed.
     Pre-fix: the seed contains both conflicting ids.
   - **Newer complete refresh:** `inject.sh` runs a full second refresh
     (`--sync-seed`, a different stub listing that adds `opencode/newer`) to
     completion. The assertions are split into two groups:
     - *File assertions (shared — run against both scripts):* the registry
       and seed both hold the newer models, i.e. the seed equals
       `jq -f model_stats_strip.jq` of the live registry and contains
       `opencode/newer`. Both scripts pass these: the pre-fix script
       re-reads the live file, and the revised script skips. The group pins
       the ordering regression that the bytes capture alone would
       introduce.
     - *Warning assertion (revised script only):* the older run's output
       contains the "not synced" warning. It is not asserted in the pre-fix
       control, which never prints it.
6. Positive controls: (a) a clean listing with an existing same-name /
   same-cli_id row → exit 0, stats carried; (b) a cli_id-keyed rename
   (`legacy_foo_name` / `opencode/foo-bar` → `opencode_foo_bar`) → exit 0,
   renamed, stats kept. This guards against a false positive on the
   legitimate rename path.

Pre-fix control: run the new file once against the pre-change script (keep
a copy of the original in the scratchpad, and use a `SCRIPT_UNDER_TEST`
override like the merge test's `OPENCODE_MODELS_SCRIPT`). Cases 1-5 must
FAIL there, except 5b's "newer complete refresh" shared file assertions,
which pass on both by design (its warning assertion is post-fix only, gated
by whether `SCRIPT_UNDER_TEST` is overridden). Case 6 must pass. The jq wrapper exercises the pre-fix copy
unmodified. Record the result in the Final
Implementation Notes.

## Verification

- `bash tests/test_opencode_models_collision.sh` (new): all pass.
- `bash tests/test_opencode_models_reserved.sh` and
  `bash tests/test_opencode_models_merge.sh`: still pass (no regression in
  the reserved guard, carry-over, rename or CAS behaviour).
- `bash tests/test_verified_update_flags.sh`: still 20/20 (defect 1 evidence).
- `python3 -m pytest tests/test_metadata_writer_inventory.py` (or run it via
  `bash tests/run_all_python_tests.sh --test-dir`) if it inventories this
  script's functions. Check it still passes, since a new function is added.
- `shellcheck .aitask-scripts/aitask_opencode_models.sh .aitask-scripts/lib/agent_string.sh tests/test_opencode_models_collision.sh`.
- `grep -rn "ait opencode-models" .aitask-scripts/` → no hits.

## Out of scope — upstream finding to hand off at Step 8b

Concern 1 exposes a pre-existing defect on the **allowed** path. The
cli_id-keyed rename in `merge_with_existing` (registry `legacy_foo_name` →
derived `opencode_foo`) renames the registry row, but the aitask-stats
history stays keyed under `legacy_foo_name`. The renamed model silently
loses its usage and verification history, and the old name's history is
orphaned. Fixing it means moving history in the stats store
(`model_stats_store.update`), which is a separate change. This guard does
not touch it. At Step 8b, offer an upstream_defect follow-up for it.

## Post-implementation

Step 9 of the task workflow: commit the code changes
(`bug: ... (t1885)`), commit the plan via `./ait git`, and archive.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.

The guard is additive and fails closed. It reuses the reserved guard's
two-point placement (pre-write + CAS render), and the seed now derives from
the guarded bytes. Today's registries have zero duplicate names or cli_ids,
and the positive controls pin the legitimate rename path. The one behaviour
change is intended: a refresh that used to merge two colliding models (or
duplicate rows) silently now refuses. Its recovery text never moves a name
away from its stats history.

## Post-Review Changes

### Change Request 1 (2026-11-20)
- **Requested by user:** (1) the new test forwarded an inherited `TASK_DIR`, so its refreshes could write a real registry; (2) the guard passed all registry rows as one `--argjson` argv string, which fails with "Argument list too long" on a large registry (2,400 rows); (3) the seed was staged in `$TMPDIR` and `mv`d, a non-atomic copy across filesystems, contrary to `shell_conventions.md`'s `lib/atomic_write.sh` rule.
- **Changes made:**
  - `run_refresh` pins `TASK_DIR=aitasks` (the nested refresh in `inject.sh` inherits it). The test exports `TASK_DIR` to an outside sentinel registry for the whole run and asserts at the end that the sentinel is byte-identical.
  - `collision_guard_message` reads the registry with `--slurpfile regdoc`; the no-registry case is an explicit `--argjson regdoc '[{"models": []}]'`.
  - The seed is written via `ait_atomic_render "$SEED_FILE" render_seed` (staged beside the resolved seed path). `render_seed` strips the checked bytes, and its last act is the live-registry compare (`SEED_DIVERGED=true; return 1` on divergence), the same shape as `_ait_cas_render`. The script now sources `lib/atomic_write.sh` explicitly.
  - New tests: T6c (a staging temp sits beside the seed during the render, none left behind), T6d (a 2,400-row / 597 KB registry refreshes), plus the isolation sentinel.
- **Files affected:** `.aitask-scripts/aitask_opencode_models.sh`, `tests/test_opencode_models_collision.sh`
- **Negative controls:** the test without the `TASK_DIR` pin fails the sentinel check (and T6b); a guard mutant passing the registry as argv fails T6d with "Argument list too long"; the pre-fix script fails T6c.

### Change Request 2 (2026-11-20)
- **Requested by user:** `ait_atomic_render` follows the final seed symlink, so a seed linked to the live registry made the refresh overwrite the registry with the stripped seed (losing its counters) and report success. Publish without following the final symlink, keep the compare immediately before publication, and add a regression test.
- **Changes made:** the seed is published with `ait_atomic_write_text_nofollow` (staged beside the seed, `mv -T` onto the path itself, so a link is replaced as the original `mv` did). The strip renders into a variable, the live-registry compare runs next, and publication follows immediately; `render_seed` / `SEED_DIVERGED` are gone. T6c now detects staging through a fixture `mktemp` wrapper (the staging no longer happens during the strip). New T6e: a seed symlinked to the registry is replaced by a regular file and the registry keeps its verifiedstats.
- **Files affected:** `.aitask-scripts/aitask_opencode_models.sh`, `tests/test_opencode_models_collision.sh`
- **Negative controls:** the round-1 script (follows the link) fails T6e (registry verifiedstats lost, link still present); the pre-fix script fails T6c (staged in `$TMPDIR`) and passes T6e (its plain `mv` replaced the link).

### Change Request 3 (2026-11-21)
- **Requested by user:** the live-registry compare ran before `ait_atomic_write_text_nofollow` staged the seed, so a newer refresh completing during staging had its seed replaced by the older bytes (reported as success). Compare after staging, immediately before the rename, keeping same-directory staging and symlink replacement; cover a newer refresh that completes during staging.
- **Changes made:**
  - `lib/atomic_write.sh`: new `ait_atomic_write_text_nofollow_if <dest> <content> <check_fn> [args...]`. `ait_atomic_write_text_nofollow` and the new function share `_ait_atomic_nofollow_publish`; the check runs after the content is written to the staging temp and immediately before the rename, and a failing check discards the temp and returns 3 (write failures stay 1). The existing function's behaviour is unchanged.
  - `aitask_opencode_models.sh`: the seed is published with `ait_atomic_write_text_nofollow_if "$SEED_FILE" "$seed_content" registry_unchanged`; rc 0 → synced, 3 → "not synced" warning, else write warning.
  - Test fixture: the `mktemp` wrapper is a second injection point (`INJECT_AT=stage`, fires right after the seed's staging temp is created, for both the fixed and the pre-fix staging templates). New T5b-3: a newer refresh completing during seed staging keeps its registry and seed.
  - `tests/test_atomic_write_sh.sh`: new `_if` cases (pass publishes; fail returns 3, publishes nothing, leaves no temp; the check sees the staged content; a link survives a refused write and is replaced by a published one).
  - `aidocs/framework/shell_conventions.md`: documents the new helper next to `ait_atomic_write_text_nofollow`.
- **Files affected:** `.aitask-scripts/lib/atomic_write.sh`, `.aitask-scripts/aitask_opencode_models.sh`, `tests/test_opencode_models_collision.sh`, `tests/test_atomic_write_sh.sh`, `aidocs/framework/shell_conventions.md`
- **Negative controls:** a mutant with the round-2 order (check, then `ait_atomic_write_text_nofollow`) fails T5b-3 (the older seed replaced the newer one); the fix passes 69/69. Every shell test that sources `atomic_write.sh` still passes.

### Change Request 4 (2026-11-21)
- **Requested by user:** (1) `_ait_atomic_nofollow_publish` ran the rename-mode probe (`ait_atomic_nofollow_native`: `mv --help | grep`) after the check, so a newer refresh finishing during the probe still had its seed overwritten without a warning. Decide the rename mode before the precondition and cover the probe timing. (2) The Change Request 3 record claimed `shell_conventions.md` documents the new helper, but that edit had failed (its `old_string` did not match) and the guide was unchanged.
- **Changes made:**
  - `lib/atomic_write.sh`: `native` is computed at the top of `_ait_atomic_nofollow_publish`, before staging. The check is now the last act before the selected `mv`.
  - `aidocs/framework/shell_conventions.md`: the `ait_atomic_write_text_nofollow_if` paragraph is actually added (verified by grep).
  - `tests/test_atomic_write_sh.sh`: a call-order case (a shell-function `mv` records every call). In the default run the probe precedes the check, and in both runs the only step after the check is the rename (`mv -fT` / `mv -f`).
  - `tests/test_opencode_models_collision.sh`: an `mv` wrapper is a third injection point (`INJECT_AT=probe`, at `mv --help`). T5b-3/T5b-4 run the newer-refresh case at the stage and probe points. An `ATOMIC_WRITE_LIB` override selects the library under test.
- **Files affected:** `.aitask-scripts/lib/atomic_write.sh`, `aidocs/framework/shell_conventions.md`, `tests/test_atomic_write_sh.sh`, `tests/test_opencode_models_collision.sh`
- **Negative controls:** the round-3 library (probe after the check) fails T5b-4 (older seed published, no warning) and both new order assertions in `test_atomic_write_sh.sh`. The fix passes the collision test 74/74 and `test_atomic_write_sh.sh` 62/62. Every shell test that sources `atomic_write.sh` passes.

### Change Request 5 (2026-11-22)
- **Requested by user:** T5b-4 inherited `AIT_ATOMIC_PORTABLE_MV=1`, which short-circuits the writer's `mv --help` probe, so the probe injection never ran and the case failed under that override.
- **Changes made:** T5b-4 runs with `AIT_ATOMIC_PORTABLE_MV` cleared for that case alone. Every other case keeps the inherited value.
- **Files affected:** `tests/test_opencode_models_collision.sh`
- **Verification:** 74/74 by default and 74/74 with `AIT_ATOMIC_PORTABLE_MV=1`. Under that override the round-3 library still fails T5b-4.

## Final Implementation Notes
- **Actual work done:**
  - Defect 1 (flags test isolation): no change. It was already fixed by t1937 (`579dd60bc`); `tests/test_verified_update_flags.sh` passes in its no-remote fixture.
  - Defect 2 (non-injective names): `collision_guard_message` in `.aitask-scripts/aitask_opencode_models.sh` refuses classes (a)-(d) at the pre-write point and inside the CAS render. Its recovery text never advises a rename, because aitask-stats history is keyed by name. The registry goes in as a jq file input (`--slurpfile`). The seed is rendered from the exact swapped bytes (`RENDERED_REGISTRY`) and published with the new `ait_atomic_write_text_nofollow_if`: staged beside the seed, a seed symlink replaced rather than followed, and the live-registry compare as the last act before the rename (rename mode decided before staging).
  - Defect 3 (stale `ait opencode-models`): the script header and `--help` usage now name `bash .aitask-scripts/aitask_opencode_models.sh`. The `lib/agent_string.sh` unavailable-model hint names `/aitask-refresh-code-models`, plus the opencode script.
  - `lib/atomic_write.sh`: new `ait_atomic_write_text_nofollow_if` (check after staging, immediately before the rename; returns 3 when the check fails). `ait_atomic_write_text_nofollow` shares the body and behaves as before. Documented in `aidocs/framework/shell_conventions.md`; unit cases in `tests/test_atomic_write_sh.sh`.
  - New `tests/test_opencode_models_collision.sh` (74 assertions). Injection points need no runtime seam: fixture `jq` / `mktemp` / `mv` wrappers (strip / stage / probe). There is a `TASK_DIR` isolation sentinel, and `OPENCODE_MODELS_SCRIPT` / `ATOMIC_WRITE_LIB` overrides select what is under test.
- **Deviations from plan:** Five review rounds widened the plan (see Post-Review Changes 1-5): `TASK_DIR` pinning and a sentinel; `--slurpfile`; atomic same-directory seed publication; no-follow publication; the compare moved after staging (a new library helper); the rename-mode probe moved before the check; the probe case isolated from an inherited portable-mv override. The planned runtime test seam was replaced by fixture-local command wrappers.
- **Issues encountered:** `'` escapes typed into a tool parameter arrived decoded as literal apostrophes and broke the bash-quoted jq program. The strings were reworded to contain no apostrophes. A `shell_conventions.md` edit failed (its `old_string` did not match) and was wrongly reported as done in Change Request 3. It was fixed and verified in Change Request 4.
- **Key decisions:** text fix instead of a new `ait opencode-models` route (no new public verb); fail closed with no migration (recovery is manual and history-preserving); a `_if` variant in the shared library rather than a hand-rolled publish in the script. Pre-fix control: the original script fails Tests 1-5b-1 and 6c, and passes 5b-2/5b-3 file assertions, 6a/6b/6d/6e; round mutants each fail exactly the case their round added.
- **Upstream defects identified:**
  - `.aitask-scripts/aitask_opencode_models.sh:merge_with_existing` — the cli_id-keyed rename (registry `legacy_name` → derived name) renames the registry row, but the aitask-stats history stays keyed under the old name. The renamed model loses its usage and verification history, and the old name's history is orphaned.
  - `tests/test_opencode_models_reserved.sh:run_refresh` / `tests/test_opencode_models_merge.sh:run_refresh` — forward an inherited `TASK_DIR`, so a run with `TASK_DIR` set writes the real registry it names (the same isolation defect fixed in the new collision test).
