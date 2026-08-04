---
Task: t1224_remote_lane_gate_live_verify.md
Base branch: main
plan_verified: []
---

# Plan: t1224 — Manual-verification auto-execution

## Context

t1224 is the risk-mitigation ("after") follow-up for t635_35: live remote-lane
verification of the active-gates materialization. Its three checks assert that
the `remote` profile's `rendered_gates: []` ceiling filters a task's declared
`gates:` down to an enforced `active_gates: []`, both on the `aitask-pickrem`
claim path (Step 5) and on the `aitask-web-merge` completion-marker path, and
that a bad marker fails closed before archival.

Autonomous verification was requested. Both entry points are agent-driven
skills whose gate behavior is carried entirely by deterministic helper
commands (`aitask_gate.sh materialize-active`, `aitask_web_merge.sh
materialize`, `aitask_archive.sh`). Verification drove those helpers directly
against **real throwaway tasks in the real repo**, and confirmed the skill
wiring — which step invokes which helper — by source inspection. The residual
gap is recorded under "Not covered" below.

Every item was run with a **negative control first**: each probe task was
observed `BLOCKED:risk_evaluated` before materialization, so a later
`NO_GATES` proves the materialization caused the change rather than the gate
never having been enforced.

## Execution Log

### Item 1
- Item text: Run `/aitask-pickrem <id>` on a throwaway task with a literal
  `gates: [risk_evaluated]` declaration; confirm Step 5 materializes
  `active_gates: []` at claim (status line `MATERIALIZED:(empty)`), the
  `active_gates_profile` stamp is `remote`, and the task archives at Step 10
  without any manual gate append.
- Approach: CLI invocation against a real throwaway task (t1406), driving the
  exact command `aitask-pickrem-remote-/materialize-active.md` specifies.
- Action run:
  - `aitask_create.sh --batch --name "throwaway remote gate materialization probe" --type chore --gates risk_evaluated --commit` → created `t1406`
  - Negative control: `aitask_gate.sh archive-ready 1406` → `BLOCKED:risk_evaluated`; `active-gates-status … --profile remote.yaml` → `ABSENT`
  - `aitask_gate.sh materialize-active 1406 --profile aitasks/metadata/profiles/remote.yaml`
  - `aitask_gate.sh archive-ready 1406`; `active 1406 risk_evaluated` under both the bash and `AIT_GATES_BACKEND=python` readers; `should-self-record 1406 risk_evaluated`
  - `ait gates run 1406`
  - `aitask_archive.sh 1406`
- Output (trimmed):
  - `MATERIALIZED:(empty)` (exit 0)
  - Written frontmatter: `active_gates: []`, `active_gates_filtered: [risk_evaluated]`, `active_gates_profile: remote`, `active_gates_digest: 5892c63ff1b4.bb8bee3fef56.59da88187338`
  - `archive-ready` → `NO_GATES`; `active-gates-status` → `FRESH / ACTIVE: / FILTERED:risk_evaluated / PROFILE:remote`
  - `active` → exit 1 under **both** backends (gate not in enforced set); `should-self-record` → exit 0
  - `ait gates run` → `No gates declared; nothing to do.` (exit 0)
  - Task file contained **zero** `## Gate Runs` sections — no gate was appended
  - `ARCHIVED_TASK:aitasks/archived/t1406_…md`, `COMMITTED:39fbc10d4`, exit 0
- Verdict: **pass**

### Item 2
- Item text: Produce (or hand-craft on a branch) a pickweb completion marker
  carrying `"profile": "remote"` and `"profile_filename": "remote.yaml"`; run
  `aitask-web-merge` and confirm the Step 5 materialization sub-step runs
  `aitask_web_merge.sh materialize`, reports `WEBMAT_OK:MATERIALIZED:(empty)`
  (or NOOP on re-run), and archival proceeds cleanly.
- Approach: test-data fabrication (hand-crafted marker JSON matching the
  pickweb Step-7 template) + CLI invocation against a second real throwaway
  task (t1407).
- Action run:
  - Created `t1407` with `gates: [risk_evaluated]`; negative control `archive-ready` → `BLOCKED:risk_evaluated`, tuple `ABSENT`
  - Hand-wrote `completed_t1407.json` in the session scratchpad with the full v1 marker field set, including `"profile": "remote"` / `"profile_filename": "remote.yaml"`
  - `aitask_web_merge.sh materialize 1407 <marker>` (twice, to exercise the re-run path)
  - `aitask_update.sh --batch 1407 --implemented-with "claudecode/opus5" --silent` (web-merge Step 5 attribution order)
  - `aitask_archive.sh 1407`
- Output (trimmed):
  - First run → `WEBMAT_OK:MATERIALIZED:(empty)` (exit 0)
  - Re-run → `WEBMAT_OK:NOOP:unchanged` (exit 0)
  - `active-gates-status` → `FRESH / ACTIVE: / FILTERED:risk_evaluated / PROFILE:remote`; `archive-ready` → `NO_GATES`
  - Attribution exit 0; `ARCHIVED_TASK:aitasks/archived/t1407_…md`, `COMMITTED:c493900b2`, exit 0
- Verdict: **pass**

### Item 3
- Item text: Sanity-check the failure stop: point a marker at a nonexistent
  profile file and confirm web-merge surfaces `WEBMAT_INVALID:profile-not-found`
  and stops before archival with the Retry / Abort-branch prompt.
- Approach: test-data fabrication (a second marker differing from item 2's in
  exactly one field) + CLI invocation. Run on the **same** task t1407 and
  **before** item 2, so the failure and success paths form a within-task flip
  table on identical state.
- Action run:
  - `completed_t1407_badprofile.json` — identical to item 2's marker except
    `"profile_filename": "no_such_profile.yaml"` (one mutation)
  - `aitask_web_merge.sh materialize 1407 <bad marker>`
  - Re-checked `archive-ready` and `active-gates-status`
  - `aitask_archive.sh 1407` to test the archival guard for real
- Output (trimmed):
  - `WEBMAT_INVALID:profile-not-found`, exit 1
  - State untouched: `archive-ready` → `BLOCKED:risk_evaluated`, `active-gates-status` → `ABSENT` (no tuple written, no previous profile's tuple left authoritative)
  - `aitask_archive.sh 1407` → `GATE_PENDING:risk_evaluated` + `GATE_BLOCKED: cannot archive until all declared gates pass`, exit 2 — archival genuinely refused, not merely "not attempted"
  - Retry / Abort-branch prompt is agent-side; confirmed present in
    `.claude/skills/aitask-web-merge/materialize-gates.md` as the documented
    handling for `WEBMAT_INVALID` / `WEBMAT_FAIL`
- Verdict: **pass**

## Wiring confirmed by source inspection

- `.claude/skills/aitask-pickrem-remote-/SKILL.md:114` — Step 5 is "Assign Task"; line 154 makes the materialization an **ALWAYS-runs** ownership follow-on delegating to `materialize-active.md`, which names `--profile aitasks/metadata/profiles/remote.yaml` verbatim.
- `.claude/skills/aitask-pickrem-remote-/SKILL.md:398` — Step 10 is "Archive and Push" and carries the `GATE_PENDING` backstop with an explicit **never self-signal** rule.
- `.claude/skills/aitask-web-merge/SKILL.md:126-133` — Step 5 runs the materialization sub-step *before* attribution/archival, delegating to `materialize-gates.md`, which invokes `aitask_web_merge.sh materialize`.
- `aitasks/metadata/profiles/remote.yaml` declares `rendered_gates: []` — the empty ceiling under test.

## Incidental finding (not a defect)

`aitask_gate.sh effective-gates 1406` continued to print `risk_evaluated` after
materialization, while `archive-ready` reported `NO_GATES`. This is **not** a
reader disagreement: `effective-gates` (t635_14) is a deliberately separate
verb reporting *declared intent* for the read-only planning-window producer
trigger — its documented contract is "the task's literal `gates:` field wins
when present". The enforced-set readers (`active`, `should-self-record`,
`archive-ready`, `_active_set_csv`) all agreed on the empty set, and the bash
and python backends returned identical exit codes. Recorded here only so the
next reader of this plan does not re-open it as a discrepancy.

## Not covered

Neither live agent loop was driven end-to-end: no Claude Web `/aitask-pickweb`
session produced the marker (item 2's was hand-crafted, which the item text
explicitly permits — "or hand-craft on a branch"), and no live
`/aitask-pickrem` session drove item 1's claim. What was verified is the
deterministic helper seam each skill invokes plus the skill prose that invokes
it. A regression in the *prose* — e.g. a future edit dropping the Step 5
materialization call — would not be caught by this run; it is covered instead
by the source-inspection points listed above being re-checked whenever those
skills change.

## Cleanup

- Throwaway probe tasks `t1406` and `t1407` — archived by the procedure itself
  (that archival is part of items 1 and 2), so no residue in `aitasks/`.
- Hand-crafted markers `completed_t1407.json` and
  `completed_t1407_badprofile.json` — session scratchpad only; never committed,
  and never written into `.aitask-data-updated/`.
- No branches, worktrees, or tmux sessions were created.
