---
Task: t1569_1_gatherer_inflight_and_planned_surface_facts.md
Parent Task: aitasks/t1569_background_work_roadmap_trail_for_followup_backlog.md
Sibling Tasks: aitasks/t1569/t1569_2_*.md, aitasks/t1569/t1569_3_*.md, aitasks/t1569/t1569_4_*.md, aitasks/t1569/t1569_5_*.md, aitasks/t1569/t1569_6_*.md
Archived Sibling Plans: aiplans/archived/p1569/p1569_*_*.md
Base branch: main
Output branch: main
---

# t1569_1 — In-flight / planned-surface facts in the shared gatherer

Frontloaded risk of the t1569 tree: blast radius over every existing trail.

## Step 1 — Extract the plan-path extractor (do this first, it is independent)

`aitask_remote_drift_check.sh:225-230` holds the only implementation. Move it to
a shared helper and make the drift check consume it.

1. Create the helper (a `.aitask-scripts/lib/` shell function file, or a small
   `.sh` — pick whichever the drift check can `source` without a subprocess).
   Preserve **exactly** the current grammar; this task is a move, not a fix:
   ```bash
   grep -oE '[A-Za-z0-9_./-]+\.(sh|py|md|yaml|yml|json|toml)' "$plan_file" \
     | sed 's|^\./||' | sort -u
   ```
2. Add a `--validate-tracked` mode classifying each path `tracked` (in
   `git ls-files`) / `phantom` / `planned_new`.
3. **Decide `planned_new` now.** A plan legitimately naming a not-yet-created
   file must not be counted as `phantom` — that under-reports exactly the
   new-file collisions t1569_3's coordination lane exists to catch. Deciding it
   later means reopening this contract, the goldens and the pinned block.
   Suggested rule: a path whose *parent directory* is tracked but the file is
   not ⇒ `planned_new`; neither tracked ⇒ `phantom`.
4. Rewrite `aitask_remote_drift_check.sh` to call it. Keep the comment block at
   `:211-224` (it records why there is no root allowlist — t1275) with the file
   reference updated.
5. `bash tests/test_remote_drift_check.sh` must pass unchanged. That suite is the
   regression guard for this move.

## Step 2 — `MEMBER_EXT:` (cheapest new line, no probe)

In `lib/trail_gather.py`, beside `member_line()` (L523-537), add:

```
MEMBER_EXT:<ref>|<created_at>|<anchor>|<verifies csv>|<risk_code_health>|<risk_goal_achievement>
```

- A **new line**, never extra fields on `MEMBER:` — its free-ish `path` field is
  last by contract and insertion breaks positional parsers.
- Emit one per member, sorted by ref, immediately after the `MEMBER:` block.
- Use `_csv_entry()` for the list field and `enum_field()` for the levels so an
  absent value renders as the established sentinel rather than an empty field.
- These are **display facts**. They never enter an INPUT record.

## Step 3 — The in-flight probe, behind an opt-in flag

Add `--with-inflight` to `cmd_snapshot()`. Without it, nothing below runs and the
output is byte-identical to today — that is what keeps every ordinary trail off
the network.

**Source union**, tagged by which produced it:

| source | command | why neither suffices |
|---|---|---|
| gated | `aitask_query_files.sh inflight` | requires `Implementing` **and** a `## Gate Runs` heading; returns `NO_INFLIGHT` today while 5 tasks are `Implementing` |
| locks | `origin/aitask-locks` | t259 is locked but `Ready`; t887 is `Implementing` but not locked |

**Read locks without fetching.** Do **not** shell out to `ait lock --list`: it
performs a network `git fetch origin aitask-locks` (`aitask_lock.sh:414-421`) and
its degenerate paths print ANSI-coloured human text to **stdout** via `info()`.
Instead resolve the tree locally:

```bash
git rev-parse --verify --quiet origin/aitask-locks^{tree}
git ls-tree <tree>          # -> t<id>_lock.yaml blobs
```

and parse each blob's `task_id:` / `locked_by:` / `locked_at:` / `hostname:` /
`pid:` / `pid_starttime:` / `pid_starttime_kind:` keys with `awk`-style key
matching (not `grep`, which aborts under `set -euo pipefail` on a missing key —
the t1370 lesson at `aitask_lock.sh:411`). **Report the ref's age**; t1569_3
turns that into its `--lock-freshness` decision and must not have to guess.

Emit:

```
INFLIGHT:<ref>|<gate|lock|both>|<PLAN|IMPLEMENT|POSTIMPL|->|<gate_state>
INFLIGHT_PATH:<ref>|<tracked|phantom|planned_new>|<path>
INFLIGHT_SCAN:<n_tasks>|<n_tracked>|<n_phantom>|<full|partial|uncheckable>
```

Hard-timeout every probe; on timeout or unresolvable tree emit
`INFLIGHT_SCAN:...|uncheckable` and no `INFLIGHT:` lines. Never fail the snapshot.

`INFLIGHT_PATH:` comes from Step 1's helper against each in-flight task's
`aiplans/p<N>*.md`. An in-flight task with no plan contributes an `INFLIGHT:`
line and zero `INFLIGHT_PATH:` lines — that asymmetry is the signal t1569_3 turns
into `UNCHECKABLE`, so it must be representable, not smoothed away.

## Step 4 — Prove the digest exclusion, and fix the determinism claim

The exclusion is **structural**: `trail_schema._normalize_input_record()`
(L615-698) hard-errors on any key outside `_RECORD_BASE_FIELDS` +
`_ALL_STATE_FIELDS`. So the rule is simply *never put these facts in an INPUT
record*. Do not add fields there — it would force `NORMALIZATION_VERSION` →
`schema_version` → every stored digest incomparable.

Amend the module docstring (L57-61): "two runs over unchanged state are
byte-identical" is currently stated for the **whole output**. Scope it to
digest-relevant lines and name the volatile prefixes explicitly. Without this the
determinism test encodes the wrong property and keeps passing while the real one
rots.

## Step 5 — Skill contract + goldens, same commit

1. Update the **PINNED** gatherer output contract at
   `.claude/skills/aitask-trail/SKILL.md.j2:47-78` with the four new prefixes and
   a sentence saying they are digest-excluded and only present under
   `--with-inflight`.
2. Regenerate the three goldens:
   ```bash
   PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
   for p in default fast remote; do
     "$PYTHON" .aitask-scripts/lib/skill_template.py \
       ".claude/skills/aitask-trail/SKILL.md.j2" "aitasks/metadata/profiles/$p.yaml" claude \
       > "tests/golden/skills/aitask-trail/SKILL-${p}-claude.md"
   done
   ```
3. Update `tests/test_trail_skill_contract.sh` if it pins the line set.

## Verification

```bash
python3 -m unittest tests.test_trail_gather tests.test_trail_schema -v
bash tests/test_trail_skill_contract.sh
bash tests/test_skill_render_aitask_trail.sh
bash tests/test_remote_drift_check.sh
shellcheck .aitask-scripts/aitask_remote_drift_check.sh
./.aitask-scripts/aitask_trail_gather.sh snapshot --scope task 1569
./.aitask-scripts/aitask_trail_gather.sh snapshot --scope task 1569 --with-inflight
```

New tests in `tests/test_trail_gather.py`:

1. **Digest invariance across a lock acquisition** — snapshot, acquire a lock in
   the synthetic repo, snapshot again; assert `DIGEST:` byte-identical while the
   `INFLIGHT:` lines differ. This is the parent task's named hazard and the whole
   point of Step 4.
2. **Default-off byte-identity** — without `--with-inflight`, output is
   byte-identical to the pre-change gatherer.
3. **Existing full-output comparisons audited** — `DeterminismTests` (L1039),
   `RecordGroundTruthTests` (L372), `PresenceTests` (L1024) are written against
   the whole output and will break; update them to the scoped property rather
   than deleting the assertion.
4. **Test isolation** — the probe needs an injectable seam **plus** an env
   kill-switch. `tests/test_trail_gather.py` chdirs into a synthetic repo with no
   remote; a probe resolving anything else makes the suite machine-dependent.
5. `tracked` / `phantom` / `planned_new` classification, including an
   all-phantom plan (model it on `aiplans/p259_batch_reviews.md`, whose 45
   `aiscripts/...` paths all fail `git ls-files`).
6. An in-flight task with **no** plan file ⇒ `INFLIGHT:` present, zero
   `INFLIGHT_PATH:`, `INFLIGHT_SCAN:...|partial` or `uncheckable`.
