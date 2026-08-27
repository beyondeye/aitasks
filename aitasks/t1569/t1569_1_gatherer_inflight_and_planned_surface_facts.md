---
priority: high
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [artifacts, scheduling, planning]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1569
implemented_with: claudecode/opus5
created_at: 2026-08-27 11:26
updated_at: 2026-08-27 15:44
---

Extend the shared trail gatherer with **generic in-flight / planned-surface
facts only**. Slice 1 of 6 for t1569 — read the parent task and
`aiplans/p1569_background_work_roadmap_trail_for_followup_backlog.md` first.

**This is the frontloaded risk of the tree.** It is the piece whose failure would
change the design, and it has blast radius over every existing trail.

## Context

The implementation-trail RFC (`aidocs/implementation_trail_design.md:307`) lists
"in-flight/lock state" as an intended gather output. `lib/trail_gather.py` has no
such probe — a standing gap. t1569's roadmap needs it, and so does the shared
parallel-admission checker (t1569_3). Scoring, freshness, follow-up semantics and
lane policy stay **out** of the gatherer — they are policy, not facts.

## Scope

### New digest-excluded line prefixes on `snapshot`

```
INFLIGHT:<ref>|<gate|lock|both>|<PLAN|IMPLEMENT|POSTIMPL|->|<gate_state>
INFLIGHT_PATH:<ref>|<tracked|phantom|planned_new>|<path>
INFLIGHT_SCAN:<n_tasks>|<n_tracked>|<n_phantom>|<full|partial|uncheckable>
MEMBER_EXT:<ref>|<created_at>|<anchor>|<verifies csv>|<risk_code_health>|<risk_goal_achievement>
```

- Source = **union** of `aitask_query_files.sh inflight` and `ait lock --list`,
  tagged by which produced it. Neither suffices alone: `inflight` requires
  `status: Implementing` **and** a `## Gate Runs` heading (it returns
  `NO_INFLIGHT` today while 5 tasks are `Implementing`), while `lock --list`
  returned t259 (locked, `status: Ready`) and missed t887 (`Implementing`, not
  locked).
- `MEMBER_EXT:` is a **new line**, never extra fields on `MEMBER:` — that line's
  free-ish `path` field is last by contract and insertion breaks positional
  parsers. `MEMBER:` today carries none of the value signal or origin evidence
  (no `created_at`, `anchor`, `verifies`, `risk_code_health`,
  `risk_goal_achievement`).

### The digest-exclusion contract (the hazard the parent flags)

`trail_gather.py` guarantees byte-identical output over unchanged state and
excludes volatile fields from `DIGEST:`. Locks and in-flight status change minute
to minute; if they entered the digest **every existing trail would report STALE
permanently**.

Good news, verified: `trail_schema._normalize_input_record()` **hard-errors on
any unknown key** (`_RECORD_BASE_FIELDS = ref,kind,exists`;
`_ALL_STATE_FIELDS = status,depends,gates_pending,content_hash`). So the
exclusion is **structurally enforced** as long as new facts arrive as new line
prefixes. Adding an INPUT record field instead would force a
`NORMALIZATION_VERSION` bump -> `schema_version` bump -> every stored digest
incomparable. Follow the `followup_kind` / `boardidx` precedent exactly.

**Also amend the determinism claim.** The module docstring states "two runs over
unchanged state are byte-identical" for the *whole output*, and the skill's
PINNED contract block reproduces the full line set. Volatile lines break that as
written. Scope the claim to digest-relevant lines — otherwise the determinism
test encodes the wrong property and keeps passing while the real one rots.

### Plan-path extraction: factor out, do not fork

`aitask_remote_drift_check.sh:225-230` holds the only implementation:

```bash
grep -oE '[A-Za-z0-9_./-]+\.(sh|py|md|yaml|yml|json|toml)' "$PLAN_FILE" \
  | sed 's|^\./||' | sort -u
```

Extract it to a shared helper and make the drift check **consume** it, with
`tests/test_remote_drift_check.sh` as the regression guard. It gains three more
consumers (this task, t1569_3, t1569_4); forking it guarantees divergence on the
NFC/NFD, extension-list and char-class edges recorded in
`aidocs/framework/plan_path_reference_extraction_findings.md`. Note t1275 (the
repo-specific root allowlist) is **already fixed** — do not re-add it.

Validate extracted paths against `git ls-files`. **Decide `planned_new` here** (a
plan legitimately naming a not-yet-created file): discovering it later means
reopening this contract, the goldens and the pinned block. 22 of 108 active plans
are **all-phantom** (every path fails `git ls-files`) — e.g.
`aiplans/p259_batch_reviews.md` references `aiscripts/...`, a directory that no
longer exists.

### The lock probe must not make the shared gatherer network-dependent

`ait lock --list` performs a network `git fetch origin aitask-locks`
(`aitask_lock.sh:414-421`) and prints ANSI-coloured human lines to **stdout** on
its degenerate paths (`info()` in `lib/terminal_compat.sh` echoes to stdout, not
stderr). Unconditionally inside `snapshot` that would slow and fragilize *every*
ordinary trail, against the skill's latency rule. Required:

- gate the whole probe behind an **opt-in flag**;
- read local `origin/aitask-locks` **without fetching**, and label the freshness
  (t1569_3 turns this into an explicit `--lock-freshness` parameter — the
  gatherer's cached read is right for an *estimate* and wrong for an admission
  decision, so the freshness must be reported, not assumed);
- parse only `^t<id>: locked by ` and discard everything else, as
  `aitask_board.py:1665-1672` already does;
- hard timeout degrading to `INFLIGHT_SCAN:...|uncheckable`.

## Key files to modify

- `.aitask-scripts/lib/trail_gather.py` — record emitters (`member_line()`
  L523-537, `input_line()` L511-520), `cmd_snapshot()` L558-666, module docstring
  L57-61.
- `.aitask-scripts/aitask_remote_drift_check.sh` — extract lines 225-230.
- New shared plan-path extractor helper (shell or `lib/`, matching how the
  drift check can consume it).
- `.claude/skills/aitask-trail/SKILL.md.j2` — the **PINNED** gatherer output
  contract block at lines 47-78.
- `tests/golden/skills/aitask-trail/SKILL-{default,fast,remote}-claude.md` —
  regenerate in the SAME commit.
- `tests/test_trail_skill_contract.sh`, `tests/test_trail_gather.py`,
  `tests/test_remote_drift_check.sh`.

## Reference files for patterns

- `.aitask-scripts/lib/trail_schema.py` L597-599, L615-698 — the unknown-key
  rejection that makes digest exclusion structural.
- `.aitask-scripts/lib/record_protocol.py` — `enum_field`, delimiter safety.
- `.aitask-scripts/aitask_query_files.sh:504-558` — the `inflight` subcommand.
- `.aitask-scripts/lib/pid_anchor.sh` — `lock_holder_liveness` tri-state
  (`alive|dead|unknown`), needed by t1569_3 and worth surfacing here.
- `aidocs/framework/skill_authoring_conventions.md:486-497` — goldens
  regeneration command.

## Verification

- `python3 -m unittest tests.test_trail_gather tests.test_trail_schema -v`
- `bash tests/test_trail_skill_contract.sh`
- `bash tests/test_skill_render_aitask_trail.sh`
- `bash tests/test_remote_drift_check.sh`
- `./.aitask-scripts/aitask_trail_gather.sh snapshot --scope task 1569`

Required new tests:

1. **Digest invariance across a lock acquisition** — gather, acquire a lock,
   gather again; assert the `DIGEST:` line is byte-identical while the
   `INFLIGHT:` lines differ. This is the parent task's named hazard.
2. **Audit every existing full-output byte-comparison** in
   `tests/test_trail_gather.py` (`DeterminismTests`, `RecordGroundTruthTests`,
   `PresenceTests`) — volatile lines will break assertions written against the
   whole output.
3. **Test isolation.** `tests/test_trail_gather.py` chdirs into a synthetic repo
   with no remote. A probe that resolves anything other than that repo makes the
   suite machine-dependent. Needs an injectable probe seam **plus** an env
   kill-switch.
4. `planned_new` / `tracked` / `phantom` classification, including an
   all-phantom plan.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-27T12:44:33Z status=pass attempt=1 type=human
