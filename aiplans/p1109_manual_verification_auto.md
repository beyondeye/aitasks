---
Task: t1109_async_human_gate_live_verify.md
Branch: (current branch, autonomous auto-verification)
---

# Auto-verification record — t1109 (async human gate, live)

Strategy: **autonomous** (chosen at the Step 1.5 offer). Every item was executed
inline against the real framework; this file is the retroactive record.

**Result: 6 pass, 1 fail (item 5 → follow-up bug t1409), 0 defer.**

The run used a throwaway headless profile `local/gatetest_async_human.yaml`
(`rendered_gates: [review_approved]`) and a throwaway task **t1408**, exactly as
the premise section of t1109 prescribes after t1224 resolved the ceiling
question.

## Deviations agreed before execution

1. **The throwaway task implemented nothing committable.** Item 3's checklist
   text says "code committed". Committing a scratch code file would have left
   junk commits permanently in `main`'s history, and a throwaway branch would
   have disturbed a concurrent session's uncommitted work in the shared
   worktree. The user chose the no-code-change variant: pickrem's Step 9 code
   commit was correctly skipped and the durable committed artifact was the plan
   file (`aiplans/p1408_*.md`, data branch). Everything Step 9.5 does is
   unaffected by whether the code commit fired.
2. **`EnterPlanMode` / `ExitPlanMode` was skipped** when driving pickrem Step
   7.1. This lane ran nested inside the attended t1109 session, where a nested
   plan mode blocks the very tool calls the verification needs. The plan file —
   what that round trip produces — was written directly.
3. **The digest flip in item 5 used an untracked scratch file**
   (`scratch_t1109_digest_probe.sh` at repo root, deleted at cleanup) rather
   than a committed edit. `code_digest()` counts untracked non-ignored files
   (`gate_orchestrator.py:88-90`), so the flip is real; only the commit is
   avoided.

## Execution Log

### Item 1 — Setup: throwaway headless profile with a non-empty ceiling
- Approach: file creation + CLI introspection.
- Action run: `sed` copy of `remote.yaml` → `aitasks/metadata/profiles/local/gatetest_async_human.yaml`
  with `name: gatetest_async_human`, `rendered_gates: [review_approved]`,
  `headless: true` retained; then `aitask_scan_profiles.sh` and a `git status`
  on the profiles dir.
- Output: `PROFILE|local/gatetest_async_human.yaml|gatetest_async_human|…`;
  `git status aitasks/metadata/profiles/` empty (ignored via
  `.aitask-data/.gitignore` → `aitasks/metadata/profiles/local/`).
- Verdict: **pass**

### Item 2 — Precondition: the gate actually enters the active set
- Approach: CLI invocation + frontmatter inspection, with the prescribed
  negative control first.
- Action run:
  `aitask_create.sh --batch --gates review_approved --commit` → **t1408**;
  `aitask_gate.sh archive-ready 1408` (pre-claim);
  `aitask_gate.sh materialize-active 1408 --profile aitasks/metadata/profiles/local/gatetest_async_human.yaml`.
- Output: negative control `BLOCKED:review_approved`; then
  `MATERIALIZED:review_approved`; frontmatter `active_gates: [review_approved]`,
  `active_gates_filtered: []`,
  `active_gates_digest: 841b6478bb88.30b132f20e86.9f6677c6c52c`.
- Verdict: **pass**
- Note: `active_gates_profile` records **`local/gatetest_async_human`** — the
  dir-qualified scanner name — not the bare `gatetest_async_human` the checklist
  text predicted. Checklist wording imprecision, not a defect.

### Item 3 — Stop-clean at pending-human
- Approach: drove the real headless lane. `aitask_skill_render.sh aitask-pickrem
  --profile gatetest_async_human --agent claude` produced
  `.claude/skills/aitask-pickrem-gatetest_async_human-/SKILL.md`, which was then
  followed step by step for t1408 (0a init-data → 2 resolve → 3 sync → 4 checks
  → 5 claim+materialize → 6 current branch → 7 plan → 8 implement/attribute →
  9 auto-commit → 9.5 gates).
- Output:
  - Step 5: `OWNED:1408`, then `NOOP:unchanged` from the re-materialization
    (confirming re-derivation stability under the same profile).
  - Step 3 sync: `SYNC_FAILED:dirty_worktree` — non-blocking per contract, lane
    continued.
  - Step 9: no code changes → code commit correctly skipped; plan committed as
    `ait: Update plan for t1408`.
  - **Step 9.5:** `ait gates run 1408` → `  review_approved: pending — awaiting
    human signal`, `rc=0`.
- Stop-clean invariants, all confirmed: `status: Implementing`; task file still
  in `aitasks/` (nothing under `aitasks/archived/`); plan commit local-only
  (`origin/aitask-data..HEAD` non-empty); **no** witness at
  `.aitask-gates/t1408/` — the agent never self-signalled; ledger
  `review_approved: pending`; `archive-ready` → `BLOCKED:review_approved`.
- Verdict: **pass**

### Item 4 — Sign and record
- Approach: CLI invocation + witness/ledger inspection.
- Action run: `ait gate pass 1408 review_approved`, with `code_digest()` sampled
  from `gate_orchestrator` immediately before.
- Output: live digest `ade0da54f016ff4c`; witness
  `.aitask-gates/t1408/review_approved.signed` written with
  `code_digest=ade0da54f016ff4c` (plus `signer`, `signed_at`, `hostname`);
  ledger appended `status=pass attempt=2 type=human` with
  `Note: signed_digest:ade0da54f016ff4c` — the `gate_orchestrator.py:432`
  contract.
- Verdict: **pass**

### Item 5 — Stale signature re-pends
- Approach: CLI invocation after a real digest flip, with the discrimination
  requirement honoured (witness left **stamped-but-wrong**, never unstamped).
- Action run: created untracked `scratch_t1109_digest_probe.sh` (digest
  `ade0da54f016ff4c` → `81c0bebb7d96cc4e`; witness still stamped with the old
  value), then `ait gates run 1408`.
- Output: ❌ `All gates satisfied. Task ready for archive` and
  `archive-ready` → `ALL_PASS`. **It did not re-pend.**
- Follow-up probes (to separate "logic broken" from "logic unreachable"):
  - `ait gates run 1408 --gate review_approved` (force path) → ✅ `pending —
    stale signature: signed against ade0da54f016ff4c, code now
    81c0bebb7d96cc4e — re-sign with 'ait gate pass'` — the exact spec text.
  - With the ledger thereby back at `pending`, plain `ait gates run 1408` → ✅
    re-pends identically; `archive-ready` → `BLOCKED:review_approved`.
- Root cause: `run()` short-circuits at `gate_orchestrator.py:470` on
  `all(_satisfied(...))`, and `compute_unlocked` (line 227) skips satisfied
  gates — both read the **ledger status**, never the witness. So
  `_handle_human` → `_signal_state` (the only digest comparison) is unreachable
  once a `pass` is recorded. The stale-detection logic is correct; its dispatch
  gating is what fails.
- Why it matters: the documented completion sequence is *sign → re-run
  `/aitask-pickrem <id>` to archive*. Code changed during that resumed run is
  never re-validated, so the task archives carrying code the reviewer never
  approved — precisely what `gates.yaml:190-201`'s code-binding exists to
  prevent.
- Verdict: **fail** → follow-up bug **t1409**
  (`aitasks/t1409_fix_failed_verification_t1109_item5.md`), enriched with the
  evidence table, root-cause line references, a fix direction (re-validate
  signal-bearing human gates before the short-circuit, and reach
  `archive-ready` too, since it returned `ALL_PASS` independently), and a
  regression-test spec with a required negative control.

### Item 6 — Re-sign and archive
- Approach: CLI invocation + archive script exit-status check.
- Action run: `ait gate pass 1408 review_approved` (against the current state),
  `aitask_gate.sh archive-ready 1408`, `aitask_archive.sh 1408`.
- Output: `Re-signed gate 'review_approved' … (witness refreshed)` with
  `code_digest=81c0bebb7d96cc4e`; orchestrator recorded `pass (human signal
  observed)`; `archive-ready` → `ALL_PASS`; archive exit **0** with
  `ARCHIVED_TASK:` / `ARCHIVED_PLAN:` / `COMMITTED:0bb19f70f` and **no**
  `GATE_PENDING`.
- Verdict: **pass**

### Item 7 — Cleanup
- Approach: file removal + re-inspection.
- Action run: removed `aitasks/metadata/profiles/local/gatetest_async_human.yaml`
  (and the now-empty `local/`), `.aitask-gates/t1408/`,
  `scratch_t1109_digest_probe.sh`, and the two rendered
  `*-gatetest_async_human-` skill variant dirs.
- Output: scanner back to the 3 shipped profiles; all removed paths gone;
  `git status` shows no residue from this run (t1408 itself was removed by its
  own archival in item 6).
- Verdict: **pass**

## Cleanup

All items above were removed during item 7. Nothing outstanding. No tmux
sessions were created. The pre-existing uncommitted changes in the worktree
belong to a concurrent session and were deliberately left untouched — no code
commit in this run staged anything outside the throwaway artifacts.
