# Plan: t1508 — refresh_and_verify_live_trails (manual-verification auto-execution)

- **Task:** `aitasks/t1508_refresh_and_verify_live_trails.md`
- **Task ID:** 1508
- **Type:** manual_verification (risk-mitigation follow-up of t1468_5)
- **Profile:** fast
- **Base branch:** main
- **Output branch:** main
- **Working directory:** repo root (current branch)
- **Strategy:** autonomous auto-verification (retroactive record)

## Context

t1468_5 bumped the implementation-trail schema to **1.1.0**, adding the optional
`entry.snapshot.followup_kind`. The trail is single-version by design, so both
live trail artifacts failed validation as `ERROR:invalid_trail` from the moment
t1468_5 landed. This task refreshed both and inspected the stored documents to
prove the agent-authored snapshot producer is real — the only end-to-end check
that exists, since the producer is an instruction in
`.claude/skills/aitask-trail/SKILL.md.j2`, not code.

## Artifacts written

| handle | version | digest |
|---|---|---|
| `art:trail-gates-framework-landing` | v6 — `sha256:90d678a0f9ee60f9d4…` | `e334cf4957514e11` |
| `art:trail-shadow-review-loop` | v5 — `sha256:6c64559cd3c3cfe0f9…` | `16212553ff7e716f` |

Prior versions remain recoverable via `ait artifact versions <handle>` /
`get --version sha256:<hash>`.

## Execution Log

### Item 1 — gates trail refresh reports `schema_version: "1.1.0"`

- **Item text:** `/aitask-trail refresh art:trail-gates-framework-landing` completes and the stored document reports `schema_version: "1.1.0"`
- **Approach:** CLI invocation + skill-driven refresh (`aitask-trail` Step 3), then file inspection of the fetched artifact.
- **Action run:** `aitask_artifact.sh get/versions` → `aitask_trail_gather.sh drift`
  (returned `ERROR:invalid_trail` as predicted) → `aitask_trail_gather.sh snapshot
  --scope task --owner 635 <27 refs>` → re-author at 1.1.0 → validate → `aitask_artifact.sh update`.
- **Output (trimmed):** `Updated artifact art:trail-gates-framework-landing — current is now sha256:90d678a0f9ee…`; refetched document reports `schema_version: '1.1.0'`.
- **Verdict:** pass

Membership delta: t1416 landed 2026-08-10 and was retained as a frozen landed
entry (dropped from `generation.inputs`, per the established convention that the
gatherer cannot resolve archived tasks); t1473 — its Step-8d risk-mitigation
follow-up — was admitted into wave 1 by explicit user decision. Member count
stays at 27.

### Item 2 — shadow trail refresh reports `schema_version: "1.1.0"`

- **Item text:** `/aitask-trail refresh art:trail-shadow-review-loop` completes and the stored document reports `schema_version: "1.1.0"`
- **Approach:** same, over a much larger re-analysis.
- **Action run:** as item 1 with `--owner 1159`; two snapshot rounds (see the
  mid-refresh race below).
- **Output (trimmed):** `Updated artifact art:trail-shadow-review-loop — current is now sha256:6c64559cd3c3…`; refetched document reports `schema_version: '1.1.0'`.
- **Verdict:** pass

Membership delta: t1159 was decomposed into seven children after the previous
version, so the parent became `coordination_only` and t1159_1/_2/_3 joined as
landed records; nine further anchor:1159 tasks were admitted by user decision
(cross-agent arming + quality/visibility), producing three new waves. t1502 was
excluded by analysis as test-infrastructure drift that orders against nothing in
the trail.

**Mid-refresh race.** t1520 was `Implementing` in the opening snapshot and
archived at 13:03 — before the pre-write validation, which caught it as
`DRIFT:task_completed` together with `DRIFT:input_missing` for its vanished plan
and `DRIFT:new_related_task|aitasks#1529`. The candidate document was discarded
and re-analysed over a fresh snapshot; t1520 became a landed record and its
manual verification t1529 (found by the incoming `verifies:` sweep, which is the
only edge that could have surfaced it) took its member slot. Recorded in the
trail as `obs-refresh-race`.

### Item 3 — both artifacts at `freshness.state: current`

- **Approach:** file inspection of both refetched documents.
- **Output:** gates `current` @ `2026-08-16T09:57:52Z`; shadow `current` @ `2026-08-16T10:05:54Z`. Neither returns `ERROR:invalid_trail`.
- **Verdict:** pass

### Item 4 — PRODUCER, present case

- **Item text:** a member task carrying a real `followup_kind` has that exact value stored in its `entry.snapshot.followup_kind`
- **Approach:** file inspection of the **stored** documents (refetched via
  `ait artifact get`, not the locally authored files), compared against
  independent ground truth — `followup_kind` read directly out of each member's
  task-file frontmatter, not from the gatherer output that produced the document.
- **Output:** 18 live entries store a `followup_kind`, and every one matches its
  task file exactly, spanning six distinct kinds:

  | kind | entries |
  |---|---|
  | `risk_mitigation` | 1417, 1473, 1457, 1458, 1381, 1394, 1524 |
  | `upstream_defect` | 1437, 1456, 1390, 1522 |
  | `manual_verification` | 1438, 1159_5, 1529 |
  | `review_finding` | 1159_7, 1506 |
  | `verification_failure` | 1499, 1525 |

- **Verdict:** pass

### Item 5 — PRODUCER, absent case (the common path)

- **Item text:** an ordinary member with no `followup_kind` has NO `followup_kind` key in its `entry.snapshot` — not the literal `unknown`, not `invalid`
- **Approach:** as item 4, plus a whole-document string scan at every nesting
  level for the two transport sentinels.
- **Output:** 24 live entries whose task file carries no `followup_kind` omit
  the key entirely. No `"followup_kind": "unknown"` or `"followup_kind":
  "invalid"` anywhere in either document. Every stored value is in the schema
  enum. Zero problems.
- **Verdict:** pass

This is the majority case, as the task predicted: 24 omissions against 18
stored values.

### Item 6 — `drift` reports `CURRENT` for both

- **Approach:** CLI invocation against both the fetched documents and the handles.
- **Output:** `CURRENT` for both immediately before each write (validated twice
  each — once on the authored candidate, once on the re-authored one). Re-run
  after the writes returns `STALE` for both, with a single reason each:
  `DRIFT:plan_changed|aitasks#1263|plan appeared:…` and
  `DRIFT:plan_changed|aitasks#1525|plan appeared:…`. Both digests are
  byte-identical to the stored ones (`e334cf4957514e11`, `16212553ff7e716f`), so
  no membership, status or metadata drifted — two members that were already
  `Implementing` externalized their plans in the intervening minutes.
- **Verdict:** pass (user-confirmed after the facts were presented)

Chasing it would not converge while those two tasks are in flight: any edit to
either plan changes the digest again.

### Item 7 — t1470's "Live hazard" paragraph

- **Approach:** file inspection.
- **Output:** `t1470_surface_intrawave_parallel_safety_in_bytrail_view.md:212-224`
  names t1508 explicitly ("The refresh is tracked as **t1508**"), and the
  frontmatter carries `depends: [1508]`.
- **Verdict:** pass

The edge was **left in place deliberately**. It is verification-scoped ("do not
verify until t1508 is Done"), so archiving t1508 satisfies it through the normal
mechanism; dropping it would remove the guard for no gain.

## Upstream defects identified

- `.aitask-scripts/lib/trail_gather.py:375-384` (`plan_glob_regex`) — a parent
  member's plan regex also matches its **child's** plan relpath, so drift's
  per-member plan attribution mis-attributes whenever a parent and one of its
  children both have plan files. `plan_glob_regex("1159")` is
  `(?:.*/)?p1159_[^/]*\.md$`, applied with `re.search`, which matches
  `aiplans/p1159/p1159_4_docs_and_integration.md` as well as
  `aiplans/p1159_shadow_review_loop_automation.md`. The attribution then takes
  the first match via `next()` over the stored `generation.inputs`, and the
  gatherer itself emits the child plan first (path sort: `/` < `_`). A trail
  that copies the gatherer's INPUT order verbatim — which
  `.claude/skills/aitask-trail/SKILL.md.j2` instructs — is therefore reported
  `STALE` with an unclearable
  `DRIFT:plan_changed|aitasks#1159|plan moved: …p1159/p1159_4_… -> …p1159_shadow_…`,
  and every refresh reproduces it. Verified by running `drift` over the
  identical document with the two plan records in each order: child-first →
  `STALE`, parent-first → `CURRENT`, same digest in both runs. Worked around in
  the shadow trail by emitting the parent plan record first, and recorded there
  as `obs-plan-attribution-order` so a later refresh does not "tidy" the order
  back.

## Notes for future refreshes

- A schema bump makes every stored trail **un-driftable**, not merely stale:
  `ERROR:invalid_trail` is a hard stop in both the drift check and the refresh
  flow, so the landed-vs-live split must be established from direct evidence
  (archived frontmatter + an anchor-wide sweep across `aitasks/` **and**
  `aitasks/archived/`). Both refreshes here ran that way.
- The drift scan cannot see a **decomposition**. t1159 gaining seven children
  was the single largest change to the shadow trail since its previous version
  and no `DRIFT:` code would have reported it. Check for new children under
  every parent member explicitly.
- The anchor sweep across the archived tree earned its keep again: five
  shadow-topic tasks (t1159_1, t1159_2, t1159_3, t1498, t1523) were created
  **and** archived between the two refreshes and were invisible to the
  active-only scan.

## Cleanup

Scratch files under the session scratchpad
(`snap_gates.txt`, `snap_shadow.txt`, `gates_v6.json`, `shadow_v5.json`,
`build_gates.py`, `build_shadow.py`, fetched copies). No tmux sessions were
created; no files outside `aitasks/`, `aiplans/` and the artifact store were
modified.
