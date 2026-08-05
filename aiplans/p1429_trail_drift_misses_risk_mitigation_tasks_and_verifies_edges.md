---
Task: t1429_trail_drift_misses_risk_mitigation_tasks_and_verifies_edges.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1429 — Trail drift misses `risk_mitigation_tasks` and `verifies` edges

## Context

A trail's staleness check (`.aitask-scripts/lib/trail_gather.py`, `drift` verb)
derives its `new_related_task` drift reason from exactly two conditions
(:937-943): the candidate's qualified topic key matches `scope.topics`, or its
`depends` intersects the persisted member set. Two structured frontmatter
fields that encode real post-landing task connections are never read:

- **`risk_mitigation_tasks:`** — written on the *member* at task-workflow
  Step 8d, naming the follow-ups created because that task landed with a
  recorded residual risk.
- **`verifies:`** — written on a *manual-verification* task, back-referencing
  the member it verifies.

Consequence, observed while refreshing `art:trail-shadow-review-loop` on
2026-08-05: four members landed, two spawned Step 8d follow-ups (t1426 from
t1293, t1411 from t1319), and neither surfaced as drift. They were found only
because the agent hand-read the archived members' frontmatter — nothing in the
refresh procedure asks for that. The refresh flow, which runs *after* tasks
land (exactly when these follow-ups are born), is the flow that stops looking.

Intended outcome: both connection edges become deterministic
`new_related_task` reasons, and the refresh procedure gains an explicit
re-read instruction so it does not silently degrade if the scan misses a case.

## Established ground truth (verified against live data)

| field | carried by | points at | member typically |
|---|---|---|---|
| `depends` | the **new task** | the member | active or archived |
| `verifies` | the **new task** | the member | archived |
| `risk_mitigation_tasks` | the **member** | the new task | **archived** |

Verified in the repo:

- archived `t1293` → `risk_mitigation_tasks: [1426]`; live `t1426` carries **no**
  back-reference. Archived `t1319` → `risk_mitigation_tasks: [1411, 1410]`.
  `parse_frontmatter` returns these as real lists of ints.
- live `t1425` → `verifies: [1293]` **and** `depends: [1293]` — which is exactly
  why it surfaces today, and why a fixture that keeps the `depends` edge would
  not prove the new code runs.
- the `verifies` edge is *not* always masked by `depends`. Two producers create
  a manual-verification task with `--verifies` and no dependency on the verified
  tasks: the archive **carry-over** path (`aitask_archive.sh:582-590` passes
  `--verifies` + `--followup-of`, never `--deps`), and the **aggregate sibling**
  path (`aitask_create_manual_verification.sh:118-124` — `--deps` is added only
  on the standalone `--related` branch; the `--parent` branch relies on
  `aitask_create.sh`'s auto-dep, which targets the *previous sibling* only, not
  every task in `--verifies`).

So the two edges run in **opposite directions**, and only one of them can be
found by scanning live rows:

- `verifies` is new-task-side → it slots into the existing live-row scan.
- `risk_mitigation_tasks` is **member-side and inverted** → the live-row scan
  is structurally incapable of finding it. `load_tree()` (:317-335) globs only
  `aitasks/*.md` + `aitasks/t*/t*_*.md`, so `tree.rows` never contains an
  archived task. The scan must be inverted to read the **member's own**
  frontmatter, reaching the archived tree.

**Decided with the user:** implement the member-side direction only (the
task's own §1 is right; its Verification bullet (a) states the opposite
direction and is factually wrong — correct that bullet in the task file as
part of this change). A follow-up whose target is itself archived or absent is
**not** reported — only targets resolving to a live active row, matching
today's scan, which iterates `tree.rows` only.

Also established: in `art:trail-shadow-review-loop` the archived members
(`aitasks#1293`, `aitasks#1319`, `#1289`, `#1294`) exist only as
`waves[].entries` — **not** in `generation.inputs` (the gatherer refuses to
snapshot archived ids). Only `member_refs = {stored task inputs} | entry_refs`
(:929) contains them, so the inverted scan must iterate `member_refs`, not
`task_inputs`.

## Implementation

### Pre-phase (risk mitigations)

1. [characterize_archived_existence_classification] Before touching
   `_existence_reason`, add
   `test_existence_reason_archived_classification` to
   `tests/test_trail_gather.py` pinning its **three-way** archived outcome, and
   confirm it is green against the *unmodified* module:
   - archived + parseable + `status: Done` → `task_completed`;
   - archived + parseable + `status: Postponed` → `task_archived`;
   - archived + `folded_into` set → `task_folded`;
   - archived + **malformed frontmatter** (write the file with a broken YAML
     block, e.g. an unterminated flow sequence) → `task_archived` with the
     `status None` detail — **not** `task_deleted`;
   - absent from both trees → `task_deleted`.
   Each case deletes the active file first (archived state is only reachable
   when the active row is gone — see `test_task_completed_archived_done`
   :446-450). Only after this test passes on unmodified code may the
   `_archived_metadata` extraction in step 1b proceed; re-run it immediately
   after the extraction, where it must still pass unchanged.

### 1. `.aitask-scripts/lib/trail_gather.py` — two helper generalizations

**1a. Generalize the ref normalizer.** `_canonical_depends` (:383-397) becomes a
thin wrapper over a keyed form, so both new fields reuse its owning-project
semantics instead of open-coding a second normalizer. `task_record()` and the
digest are byte-for-byte unaffected:

```python
def _canonical_refs(metadata: dict, project: str, key: str) -> list[str]:
    """Normalize a list-valued relation field to canonical refs in the OWNING
    project's namespace; unparseable entries stay verbatim (deterministic).
    Deduplicated: identical membership must never hash differently."""
    raw = metadata.get(key)
    if not isinstance(raw, list):
        return []
    out = set()
    for entry in raw:
        parsed = canonical_id(str(entry), project)
        out.add(f"{parsed[0]}#{parsed[1]}" if parsed is not None else str(entry))
    return sorted(out)


def _canonical_depends(metadata: dict, project: str) -> list[str]:
    """Digest-bearing relation (see task_record) -- kept as its own name
    because the digest contract is pinned to it."""
    return _canonical_refs(metadata, project, "depends")
```

Callers of the new scan re-`parse_ref` the formatted result to get
`(project, bare_id)`. That parses twice and drops the verbatim passthrough
entries, which is intentional: the passthrough exists only so `task_record`
hashes stably, and a value that does not parse can never name a live row.
Reusing the one normalizer is worth more than saving a parse.

**1b. Extract the archived-frontmatter read — preserving a THREE-way outcome.**
`_existence_reason` (:730-743) distinguishes three cases, and a `dict | None`
helper only preserves them if `None` means *not archived* and `{}` means
*archived but unparseable*:

```python
def _archived_metadata(bare_id: str, archived_dir: Path) -> dict | None:
    """Frontmatter of an archived task, or None when it is NOT in the archive.

    `{}` means archived-but-unparseable and is NOT the same as None -- collapsing
    the two would reclassify every malformed archived task from `task_archived`
    to `task_deleted`. Deliberately does NOT apply _load_row's phantom-stub rule
    (:311-312): the archived path never had that guard, and adding it would flip
    archived stubs to `task_deleted` too.
    """
    archived = find_archived_markdown_by_id(bare_id, archived_dir)
    if archived is None:
        return None
    _, text = archived
    try:
        parsed = parse_frontmatter(text)
    except Exception:
        parsed = None
    return parsed[0] if parsed else {}
```

`_existence_reason`'s archived half is rewritten to call it and **must branch on
`is not None`**, never on truthiness. Behavior is byte-identical; the
distinction is pinned by a new characterization test (see Tests, item 0) written
**before** the refactor.

### 2. `verifies` — third branch of the existing live-row scan

In the digest-independent scan at :932-943, after the `depends` branch:

```python
            verifies = set(_canonical_refs(row.metadata, proj, "verifies"))
            if qualified_topic in scope_topics:
                add("new_related_task", row.ref, f"new task in topic {qualified_topic}")
            elif depends & member_refs:
                add("new_related_task", row.ref,
                    f"new task depends on {sorted(depends & member_refs)}")
            elif verifies & member_refs:
                add("new_related_task", row.ref,
                    f"new task verifies {sorted(verifies & member_refs)}")
```

`elif` keeps today's detail text for tasks (like t1425) that carry both edges,
and makes at most one of the three details reachable per row.

### 3. `risk_mitigation_tasks` — new inverted, member-side scan

A separate digest-independent loop, immediately after the live-row scan:

```python
    # Member-side edge (INVERTED): risk_mitigation_tasks is written on the
    # MEMBER at task-workflow Step 8d and names the follow-up; the follow-up
    # carries no back-reference, and the member is usually archived by the time
    # it matters (the real case: archived aitasks#1293 -> live aitasks#1426).
    # So neither the live-row scan above nor a depends edge can ever see it.
    #
    # Invariant: member_refs is a subset of (baseline | input_refs) -- entry_refs
    # feeds baseline (_doc_task_refs) and task_inputs' canonicals feed input_refs.
    # That single containment makes self-reference, member-targets and cycles
    # structurally unreportable; no extra guard is needed for them.
    archived_meta: dict[tuple[str, str], dict | None] = {}
    for member_ref in sorted(member_refs):
        parsed = parse_ref(member_ref)
        if parsed is None:
            continue            # schema permits a bare `1234` entry ref
        proj, bare = parsed
        tree = fresh.get(proj)
        if tree is None:
            continue
        row = tree.by_own_id.get(bare)
        if row is not None:
            meta = row.metadata
        else:
            key = (proj, bare)
            if key not in archived_meta:
                archived_meta[key] = _archived_metadata(bare, tree.archived_dir)
            meta = archived_meta[key]
        if not meta:
            continue            # absent, or archived-but-unparseable
        for ref in _canonical_refs(meta, proj, "risk_mitigation_tasks"):
            target_parsed = parse_ref(ref)
            if target_parsed is None:
                continue
            # .get(): a cross-repo target's project may not be in `fresh` at all.
            # Do NOT add it to the scanned `projects` set (:823-826) -- that could
            # stage `unresolved_project` and turn a working drift run into an
            # ERROR-only run, and would widen the live-row scan to a new tree.
            target_tree = fresh.get(target_parsed[0])
            target = (target_tree.by_own_id.get(target_parsed[1])
                      if target_tree is not None else None)
            if target is None:
                continue        # archived / deleted / unscoped: nothing to add
            if target.ref in baseline or target.ref in input_refs:
                continue
            # Detail prefix sorts AFTER every existing new_related_task detail
            # ('n' < 'r'), so dedup_reasons' smallest-detail rule preserves the
            # topic/depends wording byte-for-byte for a doubly-reachable target.
            add("new_related_task", target.ref,
                f"risk-mitigation follow-up of {member_ref}")
```

Properties this relies on:

- **No new drift code.** `GATHERER_DRIFT_CODES` (:151-155) is unchanged; both
  edges emit the existing `new_related_task`. Every consumer (board badge,
  schema enum, validator) is untouched — pinned by the existing
  `test_emittable_set_is_pinned_subset`.
- **No new input record** → `DIGEST:` cannot move. This is unconditional and
  directly testable; "still reads `CURRENT`" is the *conditional* half (it holds
  when the edge does not fire), because this whole block is the already
  digest-independent scan that flips `CURRENT`→`STALE` by design (:1006).
- **Same suppression as today.** A candidate already in `baseline` (entries ∪
  `exclusions[].task` ∪ `observations[].affects`) or in `input_refs` is skipped,
  so an already-evaluated follow-up never re-fires.
- **Deterministic.** `dedup_reasons` (:772-783) collapses to one reason per
  `(code, task_ref)` with the lexicographically smallest detail and sorts the
  result; `find_archived_markdown_by_id` is itself deterministic
  (`sorted(glob(...))`, fixed tar member order).
- **Archived reads are memoized** per `(project, bare_id)` and happen only for
  members absent from the active tree. Measured cost on this repo: 0.2–0.5 ms
  for a loose hit, 3–5 ms for a full miss (bundle decompress); trails run ~8
  members, so worst case is ~40 ms.

**Behavior change for stored artifacts (state it in the commit):** any existing
trail whose archived member names a still-live, non-excluded follow-up will flip
`CURRENT` → `STALE` on its next drift run. That is the intended fix, but it
changes the verdict of already-stored documents, not only new ones.

### 4. Docstring — drift vocabulary (`:74-77`)

```
    new_related_task    unreferenced task in a scoped project whose
                        qualified topic key matches scope.topics, whose
                        depends or verifies intersects the persisted member
                        set (stored task inputs + entry tasks), or which a
                        member's own risk_mitigation_tasks names (that edge
                        is member-side and INVERTED -- the follow-up carries
                        no back-reference and the member is usually archived,
                        so it is read from the member's frontmatter, active
                        tree or archive; only live active targets are named)
```

### 5. `aidocs/implementation_trail_design.md`

- **§8.2** (:260-268) — extend the `new_related_task` gloss from "(a new task
  anchored into a member topic or depending on a member)" to also name the
  `verifies` back-reference and the member-side `risk_mitigation_tasks` edge,
  stating that the latter is read from the member's own frontmatter including
  the archived tree. While editing the sentence, fix its standing inaccuracy:
  it says reasons are produced "when [the digest] differs", but the
  `new_related_task` scan is deliberately **digest-independent** (a new task
  adds no input record, so it can never move the digest — which is precisely
  why it must be scanned rather than digested).
- **§8.3** (:272-275) — sharpen "newly created follow-up tasks are evaluated for
  membership" to name the two fields and point at the belt-and-braces re-read
  instruction in the skill.
- **§6** (:187-191) — the freshness bullet names `new_related_task` only as a
  fixture demonstration; leave it unless the §8.2 rewording makes it read
  stale.

### 6. `.claude/skills/aitask-trail/SKILL.md.j2` — refresh flow re-read

Step 3.3's "Then:" bullet list (:284-293) gains one bullet immediately after
the existing `new_related_task` bullet. **No renumbering**: it is inserted
inside item 3's sub-list, so the `Step 3.3` / `Step 3.5` / `Step 2e.3`
cross-references (:192, :310, :331) are untouched, and
`tests/test_trail_skill_contract.sh` checks (j)/(k) keep matching.

> - **Belt-and-braces follow-up sweep.** For every member that completed or was
>   archived since the loaded version, run both halves — the two relations point
>   in opposite directions, so one re-read cannot find both:
>   - **Outgoing (`risk_mitigation_tasks`)** — read that member's own task file
>     (active tree or `aitasks/archived/`) and take the ids its
>     `risk_mitigation_tasks:` list names.
>   - **Incoming (`verifies`)** — the member does **not** record who verifies
>     it, so re-reading it can never surface this edge. Look for it on the other
>     side, with a targeted over-inclusive prefilter confirmed by reading:
>     ```bash
>     grep -rl --include='t*.md' '^verifies:' aitasks \
>       | xargs -r grep -l '<member bare id>'
>     ```
>     Then open each hit and keep only those whose parsed `verifies:` list really
>     names the member. The confirm-by-reading step is required, not optional:
>     the wild corpus spells the list as `[1039]`, `['1074_2']` and
>     `[t1018_1, t1018_2]`, so no single regex decides membership reliably, and
>     the id can also appear in body prose.
>
>   Feed everything that survives into the same propose-and-confirm path as the
>   `new_related_task` reasons. This does not reopen the PINNED "don't scan task
>   files to build membership" contract: the sweep is a bounded lookup of two
>   named relations against an already-fixed member list, and nothing it finds
>   joins the trail without the user's confirmation. The gatherer reports both
>   edges too — this sweep is the backstop for the cases its scan deliberately
>   does not reach (a follow-up that is itself already archived, a target in an
>   unscoped project), not a substitute for it.

This is the one authoring template for **all** agents
(`agent_skills_paths.sh:79-82` hardcodes `.claude/skills/<skill>/SKILL.md.j2`),
so `.agents/` and `.opencode/` carry no independent copy — only generated
variants. **No cross-agent follow-up tasks are needed**; the committed rendered
variants are regenerated in this commit.

### 7. Task-file correction

Correct Verification bullet (a) in
`aitasks/t1429_…md` from "A live task whose `risk_mitigation_tasks` names an
archived member is reported" to the actual shape — an **archived member** whose
`risk_mitigation_tasks` names a live task — and replace its stated negative
control (see Tests item 2 for why the original is vacuous). Not a silent
deviation: the AC is corrected in the task record before the work lands.

### 8. Regenerate goldens + rendered variants (same commit)

```bash
PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
for profile in default fast remote; do
  "$PYTHON" .aitask-scripts/lib/skill_template.py \
    .claude/skills/aitask-trail/SKILL.md.j2 \
    aitasks/metadata/profiles/$profile.yaml claude \
    > tests/golden/skills/aitask-trail/SKILL-${profile}-claude.md
done
./.aitask-scripts/aitask_skill_rerender.sh default
./.aitask-scripts/aitask_skill_rerender.sh fast
./.aitask-scripts/aitask_skill_rerender.sh remote
```

Review the golden diff rather than rubber-stamping it: the only change must be
the one inserted bullet.

### Post-phase (risk mitigations)

1. [pin_stored_trail_verdicts] After the code change, run
   `./.aitask-scripts/aitask_trail_gather.sh drift --trail <handle>` for **both**
   stored trails in this repo — `art:trail-shadow-review-loop` and
   `art:trail-gates-framework-landing` — and confirm each emits **zero**
   `new_related_task` lines (every candidate is already excluded or archived).
   Record the observed before/after verdict and reason set for both trails in
   the plan's Final Implementation Notes, so the behavior change to
   already-stored artifacts is documented rather than assumed.
2. [pin_detail_prefix_ordering] Add
   `test_doubly_reachable_target_keeps_depends_detail`: a target reachable by
   **both** a `depends` edge and a member's `risk_mitigation_tasks` must emit
   `new task depends on [...]` verbatim. Add a comment at the
   `add("new_related_task", …, "risk-mitigation follow-up of …")` call site
   stating that the prefix must keep sorting after `"new task "` — `dedup_reasons`
   keeps the lexicographically smallest detail per `(code, task_ref)`, so a
   rename would silently rewrite existing drift output. The test is what makes
   that rename fail loudly.

## Tests — `tests/test_trail_gather.py`

`SyntheticRepo.archive_task` (:83-91) needs **no change**: `f"{key}: {value}"`
renders a Python list as a valid YAML flow sequence (`[1426]`,
`['t1018_1', 't1018_2']` both parse), so
`archive_task("300", "m", risk_mitigation_tasks=[500])` works today.

Fixtures build on `DriftCodeTests.base_trail` (:421-427), where `mainproj#100`
is an entry member and `mainproj#101` an input-only member.

0. **`test_existence_reason_archived_classification`** — specified in full by
   the **Pre-phase** block above (`characterize_archived_existence_classification`);
   listed here only so the module's test inventory is complete.
1. **`test_risk_mitigation_edge_from_archived_member`** — the real case, and
   the one that must go red on today's code. Build a trail whose `entries`
   include `mainproj#300` but whose `generation.inputs` do not (the entry-only
   archived shape of `art:trail-shadow-review-loop`); `archive_task("300",
   "member", risk_mitigation_tasks=[500])`; `write_task("500", "followup")`
   with **no** `depends` and **no** `anchor`. Expect
   `("new_related_task", "mainproj#500")`, verdict `STALE`,
   `digest == snap["digest"]`.
2. **`test_risk_mitigation_archived_non_member_not_scanned`** — the
   discriminating negative control. `archive_task("400", "stranger",
   risk_mitigation_tasks=[501])` + `write_task("501", "other")`, where 400 is in
   neither entries nor inputs. `mainproj#501` must NOT be reported. (The task's
   stated control — a *live* task carrying the field — passes **vacuously**
   under a member-side design and proves nothing; this replaces it.)
3. **`test_risk_mitigation_target_in_baseline_suppressed`** — fixture 1 with
   `500` in `exclusions`. Not reported, verdict `CURRENT`. This is the exact
   real-world t1293→t1426 shape.
4. **`test_risk_mitigation_archived_target_skipped`** — member 300 names `[502]`
   and 502 exists only via `archive_task`. Not reported (the real t1319→t1410
   shape).
5. **`test_verifies_edge_without_depends`** — `write_task("503", "manualver",
   verifies=[101])`, no `depends`, no `anchor`. Reported;
   `digest == snap["digest"]`. Spelling variants `verifies=["t100_1"]` and
   `verifies=["1149_5"]` pinned, since the wild corpus contains both forms and
   `canonical_id` (:236-239) accepts them.
6. **`test_verifies_non_member_not_reported`** — `verifies=[999]` → not reported.
7. **`test_doubly_reachable_target_keeps_depends_detail`** — specified in full
   by the **Post-phase** block above (`pin_detail_prefix_ordering`).

Re-run unchanged as regression:
`test_new_related_task_three_triggers_digest_unchanged` (:497),
`test_foreign_dependent_fires_new_related` (:844),
`test_qualified_topic_keys_never_cross_match` (:852),
`test_emittable_set_is_pinned_subset` (:429).

### Test sequencing — no stashing

The worktree is shared with a concurrent session that has uncommitted work, so
`git stash` is an avoidable hazard. Write **all** tests first, run them against
the still-unmodified module, then implement. Nothing is stashed or reverted.

Not every test is intended-red, and saying which is which is what makes the
baseline run meaningful:

| test | before the module change | why |
|---|---|---|
| 0 `existence_reason_archived_classification` | **green** | characterizes behavior that already exists — that is the point of the pre-phase |
| 1 `risk_mitigation_edge_from_archived_member` | **red** | the discriminating test; the edge does not exist yet |
| 5 `verifies_edge_without_depends` | **red** | the discriminating test for the second edge |
| 2, 3, 4, 6 (negatives) | green | they assert "not reported", and today *nothing* is reported — they pass **vacuously** |
| 7 `doubly_reachable_…keeps_depends_detail` | green | the `depends` edge already produces that detail |

For 1 and 5, confirm the failure is an assertion on the missing ref — not an
import, fixture, or trail-validation error.

**The vacuous negatives need their own proof.** A guard that passes because the
feature is absent has not been shown to discriminate. After the module change,
prove the two load-bearing ones with **one mutation each**, reverting the
mutation by hand immediately (edit it back — no `git checkout`, which would take
the concurrent session's files with it):

- **Test 2 (member-set intersection):** change the member loop to iterate every
  archived task instead of `sorted(member_refs)`. Test 2 must go red; revert.
  This is what proves the edge keys on the member set rather than on field
  presence — the property the task's Verification section asks for, restated so
  it is actually decidable.
- **Test 4 (archived target skipped):** drop the `if target is None: continue`
  guard and fall back to naming the raw ref. Test 4 must go red; revert.

Then re-run the complete module — all eight green.

## Verification

```bash
# unit
bash tests/run_all_python_tests.sh --test-dir tests

# skill surface
bash tests/test_skill_render_aitask_trail.sh
bash tests/test_trail_skill_contract.sh
./.aitask-scripts/aitask_skill_verify.sh
```

**Live acceptance against real data** (independent ground truth — the trail that
exposed the defect). Compare only the `new_related_task` lines: this repo has
concurrent sessions, so `DIGEST:` and other drift codes move under us (two runs
minutes apart already showed `45f3be1068630701` → `2ae89390dac87e2a` from an
unrelated `status_changed` on t1427). Digest invariance is pinned by the unit
tests, where state is frozen.

1. `drift --trail art:trail-shadow-review-loop` and
   `drift --trail art:trail-gates-framework-landing` must each emit **zero**
   `new_related_task` lines, before and after — t1426 / t1411 / t1425 all sit in
   the first trail's `exclusions`, and t1410 is archived. Already-evaluated
   follow-ups must never re-fire.
2. Scratch copy of the first trail with those three refs removed from
   `exclusions`. **Pre-change baseline, already captured on unmodified code:**

   ```
   STALE
   DRIFT:new_related_task|aitasks#1425|new task depends on ['aitasks#1293']
   ```

   That single line is the whole defect: t1425 surfaces only because it happens
   to carry a `depends` edge, and the two real Step 8d follow-ups are invisible.
   After the change the same copy must additionally name
   `new_related_task|aitasks#1426` (via archived member `aitasks#1293`) and
   `new_related_task|aitasks#1411` (via archived member `aitasks#1319`), while
   `aitasks#1410` stays absent (archived target) — the exact follow-ups the
   2026-08-05 refresh had to find by hand.

## Sequencing / coordination

- `art:trail-shadow-review-loop` (owned by t1159) records this defect from the
  consumer side in `obs-single-member-topic` and
  `obs-task-content-invisible-to-drift`. After this lands, refresh that trail so
  the recorded workaround ("read `risk_mitigation_tasks` by hand") is restated
  as a residual covering only the out-of-scope content-hash half.
- **Deferred follow-up to propose at review (not in scope here):** `folded_into`
  is the one remaining post-landing connection the trail cannot see — a member
  folded into a live *non-member* absorber (real shape: `t666: folded_into:
  1343`). Today `_existence_reason` emits `task_folded` naming the member, and
  only when the digest moved; the absorber is never proposed as a candidate.
  Mechanically different (scalar, not list) and orthogonal to this task's two
  list fields.
- Out of scope per the task: task-file content hashing (would require a
  `NORMALIZATION_VERSION` + `schema_version` lockstep bump), and widening
  `scope.topics` semantics.

See **Step 9 (Post-Implementation)** of the task workflow for cleanup, merge to
the output branch, and archival.

## Risk

### Code-health risk: medium
- Refactoring `_existence_reason`'s archived half into `_archived_metadata` can
  silently reclassify a malformed archived task from `task_archived` to
  `task_deleted` if the three-way outcome (not-found / found-unparseable /
  found-parsed) is collapsed to a truthiness test. No existing test covers it,
  so it would land unnoticed. · severity: low (residual — the classification is
  pinned by a characterization test that must be green on unmodified code before
  the extraction proceeds) · → mitigation: inline pre-phase
  characterize_archived_existence_classification
- The new edges change the verdict of *already-stored* trail artifacts: any
  trail whose archived member names a still-live, non-excluded follow-up flips
  `CURRENT` → `STALE` on its next drift run. Intended, but it is a behavior
  change to documents already on disk, not only to new ones. · severity: low
  (residual — both stored trails are checked and their verdicts recorded) ·
  → mitigation: inline post-phase pin_stored_trail_verdicts
- `dedup_reasons` keeps the lexicographically smallest detail per
  `(code, task_ref)`, so a doubly-reachable target's *existing* wording survives
  only because `"risk-mitigation follow-up of …"` sorts after `"new task …"`.
  A later rename of that prefix would silently rewrite existing drift output. ·
  severity: low (residual — pinned by a test plus a call-site comment) ·
  → mitigation: inline post-phase pin_detail_prefix_ordering

The dimension stays **medium** after inlining: the mitigations remove the
unnoticed-regression paths, but the change still edits a deterministic helper
whose output is consumed by the board's By-Trail badge and whose verdicts are
stored in artifacts, and that blast radius is what sets the level.

### Planned mitigations
- timing: pre-phase | name: characterize_archived_existence_classification | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health risk 1 (task_archived silently becoming task_deleted) | desc: Characterization test pinning _existence_reason's three-way archived outcome, green on unmodified code before the _archived_metadata extraction.
- timing: post-phase | name: pin_stored_trail_verdicts | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health risk 2 (verdict change to already-stored artifacts) | desc: Run drift against both stored trails after the change, confirm zero new new_related_task lines, and record before/after verdicts in the Final Implementation Notes.
- timing: post-phase | name: pin_detail_prefix_ordering | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health risk 3 (detail-prefix rename silently rewriting existing drift output) | desc: Test that a doubly-reachable target keeps its depends detail verbatim, plus a call-site comment naming the lexicographic dependency.

### Goal-achievement risk: low
- The task's Verification bullet (a) states the opposite edge direction from its
  own §1; implementing it literally would not detect t1426 or t1411 and would
  not fix the reported defect. Already resolved — direction confirmed against
  live data and with the user, and the bullet is corrected in Implementation
  step 7. · severity: low · → mitigation: none needed
