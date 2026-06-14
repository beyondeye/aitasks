---
Task: t635_4_gate_guarded_archival.md
Parent Task: aitasks/t635_gates_framework.md
Sibling Tasks: aitasks/t635/t635_5_ledger_driven_reentry.md, aitasks/t635/t635_7_gate_aware_aitask_pick.md, aitasks/t635/t635_8_python_gate_ledger_parser.md, aitasks/t635/t635_14_profile_gate_declaration_unification.md, aitasks/t635/t635_17_autonomous_lane_rigor.md, aitasks/t635/t635_20_stats_multistage_completion.md
Archived Sibling Plans: aiplans/archived/p635/p635_1_gate_ledger_substrate.md, aiplans/archived/p635/p635_2_task_workflow_checkpoint_recording.md, aiplans/archived/p635/p635_3_dependency_unblock_semantics.md
Base branch: main
plan_verified: []
---

# t635_4 — Gate-guarded archival

## Context

Phase 2 of the gate-framework roadmap (`aidocs/gates/integration-roadmap.md`,
decision **D5**). Today task-workflow **Step 9** archives a task at workflow
end, and `aitask_archive.sh` moves it to `aitasks/archived/` unconditionally.
Once gates exist, *workflow-end* and *all-gates-pass* no longer coincide: a
task whose code is committed but whose human review / manual verification /
`docs_updated` gate pends for days would be archived prematurely (archive =
immutable record → kills re-entry).

This task makes archival **gate-guarded**: a task with any declared (`gates:`
frontmatter) gate not in `pass` state **stays active** instead of archiving,
and is re-enterable later. When the last gate passes, archival is **offered**
on the next pick. `aitask_archive.sh` itself **refuses** to archive a
non-pass-gated task (defense-in-depth for any caller), with an explicit
escape-hatch flag.

**Dormancy (zero behavior change today).** The guard keys off the **declared
`gates:` field**, which no task carries yet — `gates:` population is t635_14
(Phase 4). So like t635_3, the mechanism ships the contract + enforcement now
and is **inert** until t635_14 makes it live; correctness is proven by
synthetic fixtures. `record_gates: true` (fast) records checkpoint *runs* in
`## Gate Runs`, but the `gates:` *field* stays empty → guard is a no-op →
archival proceeds exactly as today.

Direct deps **t635_2** (checkpoint recording) and **t635_3**
(dependency-unblock semantics) have both landed.

## Key design decisions (rationale + rejected alternative)

1. **Guard = "every *declared* gate is `pass`"** (D5), derived from the ledger
   (D6 — no new status value, no cached frontmatter summary). No registry
   lookup: unlike t635_3's `dependents_status` (which filters to
   `blocks_dependents` gates), archival requires **all** declared gates. A
   declared gate with no recorded run counts as not-pass (pending).
   *Rejected:* a coarse `status: Verifying` enum value (D6 — drift risk) or a
   denormalized `gates_summary` field (stale-cache risk).

2. **Deferred-archival state = task stays `Implementing`, ledger entries
   present.** This is exactly the **in-flight resume signal** t635_5 (re-entry)
   and t635_7 (gate-aware pick) key on ("ledger entries present + status
   Implementing → resume"). The status enum is unchanged (D6).
   *Rejected:* revert to `Ready` (loses the "work done, gated" distinction;
   `Ready` means "not started") or invent a new status value (D6 forbids it).

3. **Lock left held; re-entry/lock polish deferred to t635_5.** When Step 9
   defers archival, the task lock stays held — an `Implementing` + locked task
   is precisely the "in-flight, awaiting resume" shape the existing
   crash-recovery / reclaim path (Step 4 `RECLAIM_*` signals) already handles,
   and which t635_5 generalizes to be ledger-driven. t635_4 does **not** touch
   lock semantics. *Rejected:* releasing the lock + reverting to Ready here
   (mimics "Approve and stop here") — that overreaches into t635_5's re-entry
   contract and conflates "gated, work-done" with "approved, not-started".

4. **Archival is offered at the EARLIEST opportunity — immediately in-session
   when the last gate passes — not only on a later re-pick** *(per user
   steer)*. A single reusable **Archival Offer** (built on the `archive-ready`
   decision) fires from **two** trigger points: (a) **in-session at Step 9** —
   when the workflow's own final checkpoint gate is recorded, or when the user
   resolves a pending gate right there, and `archive-ready` flips to
   `ALL_PASS`, the user is asked to archive **immediately** (no re-pick); and
   (b) **at Step 3 on a later pick** — the backstop for the genuinely-async
   case (session ended, gate passed out of band). Re-entry is therefore a
   fallback, never the *required* path. *Rejected:* making the next-pick (Step
   3 Check 4) the **only** archival trigger — forces a pointless
   stop-and-re-pick cycle when the last gate is satisfiable in the current
   session.

   The **interactive** offer (AskUserQuestion) ships now; the
   `(or profile-gated auto-applied)` clause maps to
   `auto_complete_on_all_gates_pass`, a key the roadmap assigns to **t635_17**
   (autonomous lane) — deferred there with a coordination note, not introduced
   here (would step on t635_17 and the "Gates" settings group it owns).

5. **Script escape hatch = `--ignore-gates` flag; profile-gating of it deferred
   to t635_17.** The framework table's "(profile-gated)" escape hatch is
   realized at the script layer by a `--ignore-gates` flag (manual override +
   future autonomous-lane use). The skill's Step 9 never passes it (it defers
   instead); wiring a *profile* to it is t635_17. *Rejected:* a new profile key
   here (same t635_17 overlap as #4).

6. **Skill changes are profile-INVARIANT (no new Jinja gate).** The Step 9
   guard and Step 3 offer are runtime checks (the *script* enforces; the skill
   reacts to its output), self-gating on declared gates. So they render
   identically across `default`/`fast`/`remote` — `SKILL-{default,fast,remote}`
   goldens all gain the same prose. *Rejected:* gating behind `record_gates`
   (the guard keys off declared `gates:`, which is orthogonal to *recording*;
   declared gates can exist on any profile once t635_14 lands — making it
   profile-specific would be incorrect).

## Deliverables (file by file)

### 1. Core decision — `lib/gate_ledger.py` (extend; stdlib-only)

Add the archival decision next to `dependents_status` (t635_3):

```python
def archive_status(task_file: str) -> tuple[str, list[str]]:
    """Decide whether `task_file` may archive (D5: every declared gate pass).

    - ("NO_GATES", [])  — no declared gates → archive as today (dormant case).
    - ("ALL_PASS", [])  — every declared gate has derived status `pass`.
    - ("BLOCKED", nonpass) — one or more declared gates not `pass` (incl. no run).
    """
    declared = read_declared_gates(task_file)
    if not declared:
        return ("NO_GATES", [])
    with open(task_file, encoding="utf-8") as fh:
        state = derive_status(fh.read())
    nonpass = [g for g in declared if state.get(g, {}).get("status") != "pass"]
    return ("BLOCKED", nonpass) if nonpass else ("ALL_PASS", [])
```

CLI verb `archive-ready <task-file>` (no registry arg) → prints `ALL_PASS` /
`BLOCKED:<csv>` / `NO_GATES`. Mirror the `deps-unblock` dispatch block in
`main()` and add it to the module docstring's CLI list.

### 2. Bash surface — `aitask_gate.sh` (extend)

Add `archive-ready <task-id>` subcommand mirroring `cmd_deps_unblock`: resolve
file via `resolve_task_file`, `delegate_python archive-ready "$file"`, degrade
to `NO_GATES` if python is unavailable (`|| echo "NO_GATES"`). Register in the
`main()` `case`, the header comment subcommand list, and `show_help`.

### 3. Archive-script guard — `aitask_archive.sh` (extend)

Mirror the existing `verification_gate_and_carryover()` precedent exactly:

- New flag `--ignore-gates` (parsed like `--superseded`; sets
  `IGNORE_GATES=true`). Escape hatch: bypass the declared-gate guard.
- New `gate_guard()` (called in `main()` **after**
  `verification_gate_and_carryover`, before the parent/child dispatch):
  - Resolve the task file; run `aitask_gate.sh archive-ready <task_num>`
    (full-path helper). Self-gating: `NO_GATES` / `ALL_PASS` → return (no-op).
  - On `BLOCKED:<csv>` **and** `IGNORE_GATES` false: print
    `GATE_PENDING:<csv>` + a human-readable
    `GATE_BLOCKED: cannot archive until all declared gates pass (use --ignore-gates to override)`
    line, then `exit 2` (reuse the existing exit-2 convention — already "a
    gate blocked archival").
  - On `--ignore-gates`: `info` a one-line override notice and proceed.
- Update `show_help` (`--ignore-gates` option; add `GATE_PENDING:<csv>` to the
  Output-format and exit-code-2 docs).

### 4. task-workflow Step 9 — gate-guarded archival + immediate offer (SKILL.md, profile-invariant)

In `.claude/skills/task-workflow/SKILL.md` Step 9, at the **Run the archive
script** sub-step, add handling (no Jinja — applies to all profiles).
`aitask_archive.sh` exits non-zero (code 2) with a `GATE_PENDING:<csv>` line
when the task declares gates that are not all `pass`. Handle that exit-2 case:

> **Gate guard (pending gates).** When archival is blocked by `GATE_PENDING:<csv>`,
> do **NOT** archive yet. Use `AskUserQuestion`: "Task t<id> can't archive — pending
> gate(s): <csv>. How to proceed?"
> - **"Resolve now & archive"** — for each pending gate the user can satisfy in
>   this session (e.g. run docs/tests, perform the review), record it via the
>   **Gate Recording Procedure** (`gate-recording.md`, `status=pass`). After each,
>   re-run `aitask_gate.sh archive-ready <id>`; **the moment it returns `ALL_PASS`,
>   archive immediately** (re-run the archive script) — no re-pick. If a gate
>   genuinely can't be satisfied now (e.g. an async reviewer the user doesn't
>   control), fall through to Defer.
> - **"Defer — keep in-flight"** — the task stays active (`Implementing`) and
>   re-enterable; its committed code + recorded gate runs are the resume state.
>   Inform: "Archival deferred — re-pick t<id> with `/aitask-pick <id>` once the
>   gate(s) pass." Lock is intentionally left held (re-entry is t635_5's domain).
>   End the workflow (skip push-after-archival; proceed to Step 9b Satisfaction
>   Feedback — implementation work was done).

The success path (`COMMITTED:` etc.) is unchanged — `NO_GATES`/`ALL_PASS` archive
straight through. Place the guard immediately after the archive-script invocation,
before the structured-line parsing (which only runs on the success path). The
"resolve-now & archive immediately" branch is the user-requested immediate offer;
Step 3 Check 4 (§5) is the next-pick backstop, not the only trigger.

### 5. task-workflow Step 3 — archival offer on later pick (backstop) (SKILL.md, profile-invariant)

The next-pick backstop for the async case (the session ended before the last
gate passed). Add **Check 4 — Gated task with all gates now passing** (after
Check 3, before the closing Note), profile-invariant:

> **Check 4 - In-flight gated task, all gates now pass:**
> - Run `./.aitask-scripts/aitask_gate.sh archive-ready <taskid>`. Parse:
>   `NO_GATES` / `BLOCKED:<csv>` → skip this check (fall through to normal
>   selection). `ALL_PASS` → the task's substantive work landed earlier and
>   every declared gate now passes:
>   - Use `AskUserQuestion`: "Task t<id> has all gates passing and is ready to
>     archive. Archive it now?" — options "Yes, archive it" (→ skip Steps 4–8,
>     go to **Step 9** for archival) / "No, keep it active" (→ end the
>     workflow).
> - Like Check 1/2, do NOT set status to Implementing and skip Step 4 when
>   archiving via this check.

Update the closing **Note** to include Check 4 alongside Check 1/2 ("skip Step 4
when archiving"). (Profile auto-apply via `auto_complete_on_all_gates_pass` is a
t635_17 coordination note, not implemented here.)

### 6. Design doc — `aidocs/gates/gate-guarded-archival.md` (new)

Concise contract doc (mirrors `dependency-unblock-semantics.md` front-matter:
title/category/tags/sources/confidence/created/updated). Covers: the
all-declared-gates-pass criterion (D5) + ledger derivation (D6); the **two
archival-offer triggers** (immediate in-session at Step 9 when the last gate
passes; next-pick Step 3 backstop) so re-entry is never the *required* path;
the deferred-archival state contract (stays `Implementing`, lock held, ledger =
resume signal for t635_5/_7); the `--ignore-gates` escape hatch; dormancy /
sequencing (live only after t635_14); rejected alternatives (next-pick as the
only trigger; revert-to-Ready; new status value; release-lock-now;
auto-apply-in-this-task). Add a `[[...]]` back-link from
`integration-roadmap.md` Phase 2's gate-guarded-archival bullet.

### 7. Tests — `tests/test_gate_guarded_archival.sh` (new, self-contained)

Model the harness on `tests/test_archive_verification_gate.sh` (temp git repo,
`tests/lib/asserts.sh` + `test_scaffold.sh`):

- **Unit (`archive-ready` decision, both `aitask_gate.sh` and
  `AIT_GATES_BACKEND=python`):** no `gates:` field → `NO_GATES`; declared gate
  with a recorded `pass` → `ALL_PASS`; declared gate pending/absent-run →
  `BLOCKED:<gate>`; mixed (one pass, one pending) → `BLOCKED:<pending>`.
- **Integration (`aitask_archive.sh`):**
  - task declaring `gates: [review_approved]` with no/pending run → exit 2,
    stdout has `GATE_PENDING:review_approved`, task file **not** moved to
    `aitasks/archived/`.
  - same task after `aitask_gate.sh append <id> review_approved pass` →
    archives normally (file moved, `COMMITTED:` emitted).
  - `--ignore-gates` on the pending-gate task → archives despite the pending
    gate (escape hatch).
  - **regression / dormancy:** ungated task (no `gates:`) → archives exactly as
    today (no exit 2).
  - child-task path (`<parent>_<child>`) blocked + allowed.

**Regression (must stay green):** `bash tests/test_archive_verification_gate.sh`,
`tests/test_gate_ledger.sh`, `tests/test_gate_frontmatter_roundtrip.sh`,
`tests/test_archive_folded.sh`, `tests/test_archive_no_overbroad_add.sh`,
`tests/test_skill_render_task_workflow.sh`.

### 8. Goldens + render verification (same commit as SKILL.md edit)

The Step 3 + Step 9 additions are profile-invariant, so regenerate **all three**
SKILL goldens identically:
`tests/golden/procs/task-workflow/SKILL-{default,fast,remote}.md`
(via the render driver used by `test_skill_render_task_workflow.sh` — the same
`$RENDER <SKILL.md> <profile>.yaml claude` invocation, per profile). Confirm
`planning-*`, `manual-verification-*`, and the other proc goldens diff **empty**.
Run `./.aitask-scripts/aitask_skill_verify.sh` (renders/closure/stub-markers +
`task-workflow-remote-` prerender un-drifted).

### 9. Coordination notes (post-approval, Step 7 — plan mode is read-only)

Bidirectional links via `./ait git` (per the coordination convention):
- **t635_5 (re-entry):** deferred archival leaves the task `Implementing` with
  ledger entries = the in-flight resume signal; lock left held. t635_5 owns
  resume + lock generalization. Reverse pointer added here.
- **t635_7 (gate-aware pick):** Step 3 **Check 4** offers archival when
  `archive-ready` → `ALL_PASS`; t635_7's in-flight pick section should route an
  all-pass task to that offer (don't fork the `archive-ready` decision —
  consume `aitask_gate.sh archive-ready` / `gate_ledger.archive_status`).
- **t635_14 (gate declaration):** once profiles populate `gates:`, the guard
  goes live; build/review/merge gates recorded `pass` by t635_2 archive
  normally — only async/human/`docs_updated` gates defer archival.
- **t635_17 (autonomous lane):** owns `auto_complete_on_all_gates_pass` (profile
  auto-apply of the Step 3 offer) and profile-gating of the `--ignore-gates`
  escape hatch.

### Out of scope (scope guard)
No lock-release / resume logic (t635_5); no in-flight pick-list section
(t635_7); no profile keys / Settings-TUI changes (t635_17 / t635_14); no board
or monitor changes (t635_9/_10); no stats redefinition (t635_20); no website
docs (t635_18 — current-state rule, nothing user-facing lands live while the
mechanism is dormant). No registry change. No `ait` dispatcher entry for
`archive-ready` (full-path helper, consistent with t635_1 decision #6).

## Verification

1. `shellcheck .aitask-scripts/aitask_gate.sh .aitask-scripts/aitask_archive.sh`.
2. `bash tests/test_gate_guarded_archival.sh` (unit + archive integration + child + dormancy).
3. Regression suite (§7) green; full `bash tests/run_all.sh` if present.
4. `bash tests/test_skill_render_task_workflow.sh` + `./.aitask-scripts/aitask_skill_verify.sh` green; `planning-*`/`manual-verification-*` golden diffs empty, `SKILL-*` diffs match the intended Step 3/9 adds.
5. Manual smoke on a scratch task: ungated task archives normally; add `gates: [review_approved]` → `aitask_archive.sh <id>` exits 2 with `GATE_PENDING:review_approved`; `aitask_gate.sh append <id> review_approved pass` → archives; `--ignore-gates` bypasses on a pending task.
6. macOS static sweep on edited scripts (`sed_macos_issues.md`): no `grep -P`, `sed -E` for `?`/`+`/`|`, no 3-arg `match()`, `mktemp` template form only (no new awk added here — the decision is python-delegated, like `deps-unblock`).

## Step 9 reference
Post-implementation cleanup and archival follow the shared **Step 9
(Post-Implementation)** flow (current branch — `fast` profile; no
worktree/merge). Note: this task itself declares no `gates:`, so its own
archival is unaffected by the guard it adds.

## Risk

### Code-health risk: medium
- Editing `aitask_archive.sh` `main()` (load-bearing on every task archival) to
  add a second pre-archive gate · severity: medium · → mitigation in-task: model
  exactly on the proven `verification_gate_and_carryover` exit-2 pattern;
  self-gating (no declared gates → no-op); `test_gate_guarded_archival.sh`
  dormancy/regression cases + keep `test_archive_verification_gate.sh` and
  `test_archive_*` green.
- Editing shared `task-workflow/SKILL.md` Step 3 + Step 9 (rendered into every
  calling skill's closure × 3 agents × 3 profiles) risks golden churn ·
  severity: medium · → mitigation: profile-invariant prose (no new Jinja);
  regenerate all 3 SKILL goldens; `test_skill_render_task_workflow.sh` +
  `aitask_skill_verify.sh` green; other proc goldens diff empty.
- New `archive_status` / `archive-ready` is additive and parallels the existing
  `dependents_status` / `deps-unblock` · severity: low · → mitigation: stdlib
  only; python-delegated bash subcommand; unit parity (awk path unchanged).

### Goal-achievement risk: low
- Mechanism is dormant until t635_14 populates `gates:` (designed against a
  not-yet-live surface) · severity: low · → mitigation: the design doc fixes the
  contract; synthetic-fixture tests prove correctness independently; sequencing
  honored (lands after t635_2/_3, before t635_14 makes it live).
- The deferred-active state (`Implementing` + lock held) must be a clean handoff
  to t635_5/_7 re-entry · severity: low · → mitigation: documented contract +
  bidirectional coordination notes; the state is exactly today's in-flight/
  crash-recovery shape, already handled by Step 4 reclaim.

### Planned mitigations
None — all risks are bounded and mitigated **in-task** by the test deliverables;
no separate before/after mitigation tasks are warranted.

## Final Implementation Notes

- **Actual work done:** Made archival gate-guarded (decision D5). `lib/gate_ledger.py`
  gained `archive_status()` (every *declared* gate must be `pass`; no registry
  filtering, unlike `dependents_status`) + CLI verb `archive-ready`
  (`NO_GATES`/`ALL_PASS`/`BLOCKED:<csv>`). `aitask_gate.sh` gained an
  `archive-ready <task-id>` subcommand (python-delegated; degrades to `NO_GATES`
  if Python is absent). `aitask_archive.sh` gained `gate_guard()` — mirrors the
  existing `verification_gate_and_carryover()` exit-2 pattern: on `BLOCKED` it
  prints `GATE_PENDING:<csv>` + `GATE_BLOCKED` and exits 2 (refusing to archive);
  self-gating (no declared gates → no-op) — plus an `--ignore-gates` escape-hatch
  flag. `task-workflow/SKILL.md` (profile-invariant): Step 9 handles the exit-2
  case with **"Resolve now & archive"** (satisfy the pending gate in-session via
  `aitask_gate.sh append`, re-check `archive-ready`, archive immediately on
  `ALL_PASS` — the user-requested immediate offer) and **"Defer — keep in-flight"**
  (stays `Implementing`, lock held, re-pick later); Step 3 added **Check 4**
  (next-pick backstop offering archival when `archive-ready` → `ALL_PASS`). New
  design doc `aidocs/gates/gate-guarded-archival.md` + roadmap back-link. New
  test `tests/test_gate_guarded_archival.sh` (31/31: unit decision + bash/python
  parity + archive integration incl. `--ignore-gates`, dormancy, child path).
  Regenerated all 3 `SKILL-*` goldens (profile-invariant → identical adds) +
  rerendered the committed `task-workflow-remote-` prerenders (claude/codex/
  opencode). Render test 99/99; `aitask_skill_verify.sh` OK; shellcheck + macOS
  sweep clean.

- **Deviations from plan:** One. The Step 9 "Resolve now & archive" branch
  initially referenced `aitask_gate_record.sh` (the `record_gates`-gated
  persistence helper); the render test (`test_skill_render_task_workflow.sh`,
  from t635_2) asserts the `default` render must NOT mention that script, so I
  switched to the profile-invariant substrate recorder `aitask_gate.sh append`
  — persistence comes from the subsequent archival commit instead of a
  per-recording commit. Behaviour is equivalent for the immediate-archive path
  and keeps the Step 9 guard profile-invariant.

- **Issues encountered:** In the new test, the unit layer `export`s `TASK_DIR`
  (temp fixture dir); that leaked into the integration layer and broke
  `resolve_task_file`. Fixed by `unset TASK_DIR` at the top of
  `setup_archive_project` (the archive flow uses the relative `aitasks` default,
  as in production).

- **Key decisions:** (1) Guard = all *declared* gates pass, derived from the
  ledger (D5/D6) — no registry lookup, no new status value. (2) Deferred-archival
  state = stays `Implementing` with ledger entries (the in-flight resume signal
  for t635_5/_7); lock left held. (3) Archival offered at the EARLIEST point
  (immediate in-session when the last gate passes) — re-entry/next-pick is a
  backstop, never required (per user steer). (4) Escape hatch = `--ignore-gates`
  flag; profile-gating of it + `auto_complete_on_all_gates_pass` auto-apply
  deferred to t635_17. (5) Profile-invariant skill edits (the guard keys off
  declared `gates:`, orthogonal to `record_gates`). (6) Dormant until t635_14
  populates `gates:` — zero behavior change today (no task declares gates).

- **Upstream defects identified:** None.

- **Notes for sibling tasks:**
  - **t635_5 (re-entry):** a deferred-archival task is `Implementing` + has
    `## Gate Runs` entries + lock held = the in-flight resume signal. Owns
    resume + lock/crash-recovery generalization; this task does not touch lock
    semantics.
  - **t635_7 (gate-aware pick):** Step 3 Check 4 already offers archival when
    `archive-ready` → `ALL_PASS`. Consume `aitask_gate.sh archive-ready` /
    `gate_ledger.archive_status` for the in-flight pick section — do NOT fork
    the decision.
  - **t635_14 (gate declaration):** once `gates:` is populated, the guard goes
    live; t635_2's recorded `build_verified`/`review_approved`/`merge_approved`
    archive normally — only async/human/`docs_updated` gates defer archival.
  - **t635_17 (autonomous lane):** owns `auto_complete_on_all_gates_pass`
    (profile auto-apply of the archival offers) and profile-gating of the
    `--ignore-gates` escape hatch. The board (`aitask_board.py`) and
    `manual-verification.md` also call `aitask_archive.sh`; they are unaffected
    while dormant but will see exit-2 once gates are live — board surfacing is
    t635_9's scope.
  - **`archive_status` vs `dependents_status`:** archival needs ALL declared
    gates; dependency-unblock needs only `blocks_dependents` gates. Two distinct
    decisions in `gate_ledger.py`; do not conflate.
