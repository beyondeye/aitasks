---
Task: t1663_4_workflow_check6_premise_procedure.md
Parent Task: aitasks/t1663_premise_staleness_mechanism.md
Sibling Tasks: aitasks/t1663/t1663_5_website_docs_premise_staleness.md, aitasks/t1663/t1663_6_retrospective_prompt_rate_evaluation.md
Archived Sibling Plans: aiplans/archived/p1663/p1663_*_*.md
Base branch: main
Output branch: main
---

# t1663_4 — Premise check in task-workflow Step 3 (as **Check 7**) + procedure file

## Context

t1663 lands the advisory task-premise-staleness mechanism designed in
`aidocs/framework/task_premise_staleness.md`. Siblings 1–3 shipped the verdict
engine (`aitask_premise_stale.sh check` + pure core `lib/task_premise.py`), the
`premise_baseline:` field with its validating writer (`aitask_update.sh
--premise-baseline`), and creation-time seeding / carry-over inheritance.
Nothing consumes the verdict yet: this child wires it into task-workflow so a
`Ready` task whose watched files changed since its baseline prompts once, with
evidence, before it is claimed.

Inputs that change the task body's assumptions (both inbox notes, acknowledged):
- **Numbering:** Step 3 Check 6 is already the `## Inbox` check (t1657). The
  premise check becomes **Check 7**. t1981_5 (Ready, not started) takes the next
  free number — note it at Step 8e.
- **Allowlist registration is this task's job** (handed over by t1663_1). The 5
  touchpoint files currently hold **t1981_1's uncommitted `aitask_relations.sh`
  hunks** (t1981_1 is Implementing) — gated, see step 9.

Decisions (planning + plan review):
- "Approve and stop here" after a replan **also advances** the baseline
  (fingerprint-gated), alongside Step 7. Drift-stop / resource-admission parks do not.
- "Postpone task" ends with a new **`postponed`** banner outcome.
- **Postpone never writes before ownership is held** (review finding 1): it
  routes through Step 4's standard claim, which is the mutex.
- **The claim re-validates the status under the lock** (review finding 5):
  `previous_status` is the pre-prompt snapshot, and `aitask_pick_own.sh` writes
  `Implementing` without re-reading, so with a premise choice pending the claim
  runs with a new opt-in `--expect-status Ready` gate (step 2b).
- **The advance write is one validated invocation** (review finding 4):
  approved removals and the baseline go to a single `aitask_update.sh` call.
- **Every evidence class has a defined resolution** (review finding 2, verified
  against `lib/task_premise.py`: after an advance to the reviewed commit a
  deleted path reads `absent_at_baseline` → `ASK_STALE` again):

  | Evidence class | Resolution |
  |---|---|
  | `CHANGED` | advance to `CHECKED:` |
  | `DELETED` | advance; next check classifies the path **`retired`** (new attested state — not evidence, not counted as checked; all-retired → `SKIP`, never `FRESH`) |
  | `absent_at_baseline`, present at checked rev (file added) | advance; next check reads it `ok` |
  | **`never_existed`** (new reason: absent at both ends, no history at all) | **kept by default** (may be an intended future file); removed from `file_references:` only on a separate **explicit** approval; kept → keeps reporting until the file exists or is removed (documented) |
  | `invalid_reference` (non-string / NUL entry) | not drift; recurs until `file_references:` is fixed by hand; prompt labels it as a scope defect with the diagnostic (the writer deliberately refuses to rewrite such a list) |
  | `history_unavailable` / `malformed_row` | **no advance** — advancing would mark commits nobody saw as reviewed; re-surfaces next pick |

- **Replan reviews the complete evidence** (review finding 3): the full protocol
  is retained; only the widget text is capped.
- The post-lock "re-check fingerprint → decide → write → advance last → commit"
  transaction lives in **source** (a new `advance` verb), not agent prose.

## Implementation

### 1. Core + producer: `retired` and `never_existed`

`.aitask-scripts/aitask_premise_stale.sh` §8 (classify), when `cat-file -e
<baseline>:<p>` fails:
- present at `<rev>` → `absent_at_baseline` (unchanged).
- absent at `<rev>` → window query `git log --format=%H <sha>..<rev> --
  ":(literal)p"` with explicit status (failure → `history_unavailable`);
  commits > 0 → `absent_at_baseline` (created and removed inside the window —
  still evidence); 0 commits → prior-history probe `git log -n1 --format=%H
  <sha> -- ":(literal)p"`: failure → `history_unavailable`; non-empty →
  `PATH:<k>|retired`; empty → `PATH:<k>|never_existed`.

`.aitask-scripts/lib/task_premise.py`:
- `PATH_STATES` += `retired`, `never_existed`; `PATH_REASONS` += `never_existed`;
  `SCOPE_REASONS` += `all_retired` ("every scope path was deleted at or before
  the baseline").
- `retired` paths emit no `CHANGED/DELETED/UNKNOWN` row and are excluded from the
  positively-checked set; `FRESH` still requires ≥1 positively checked path, so
  an all-retired scope reads `SKIP`/`all_retired`. `never_existed` is an
  `UNKNOWN` (evidence, drives `ASK_STALE`).
- DISPLAY mentions retired count when non-zero. Fingerprint unchanged (it
  digests metadata, not path states).
- Update the producer's ORDERED EVALUATION header, the core docstring row
  vocabulary, and existing `tests/test_premise_stale.sh` / `tests/test_task_premise.py`
  expectations whose never-in-history fixtures now read `never_existed` (each
  change deliberate and listed in Final Notes). Purity suite unaffected.

### 2. `advance` verb — `aitask_premise_stale.sh`

`advance <task_file> --checked <sha> --fingerprint <fp> [--remove-ref <path>]...`

- CLI misuse dies: missing/nonexistent task file, `--checked` not full 40/64-hex,
  `--fingerprint` not 16 hex (so `NONE` from a SKIP can never be confirmed),
  unknown flag, basename not `t<id>_…`.
- Re-run `check` (subshell), capture full output.
  1. Fresh `FINGERPRINT:` ≠ `--fingerprint` (incl. fresh `NONE`) →
     `MISMATCH:<prompted>|<fresh>` + the fresh protocol lines; write nothing.
  2. Fresh evidence holds `history_unavailable` / `malformed_row` →
     `ADVANCE_REFUSED:unverifiable|<n>` + fresh protocol; write nothing.
  3. Each `--remove-ref` must be a `never_existed` row in the fresh check, else
     `ADVANCE_REFUSED:not_removable|<enc path>`; write nothing (never removes a
     live reference).
  4. Write in **one** `aitask_update.sh --batch <id> [--remove-file-ref <p>]...
     --premise-baseline <checked> --silent` invocation (the prompted sha, never
     current HEAD). One invocation is what makes it all-or-nothing: `main()`
     validates `--premise-baseline` (grammar + commit existence) before any file
     is touched, and the reference list is read and processed before the single
     `write_task_file`, so a rejected baseline or an unreadable list leaves the
     task byte-identical. Never split removals and the baseline across calls.
     Then `aitask_task_commit.sh -m "ait: Advance premise baseline for t<id>"
     <task_file>`. Print `REMOVED:<enc path>` per ref, `ADVANCED:<checked>`,
     then the commit helper's outcome line verbatim.
  5. Writer failure → `ADVANCE_FAILED:<reason>`, task file byte-identical
     (verified by the test, not assumed).
- Exit 0 for every content state. Header: `check` rewrites nothing; `advance` is
  the only write path and delegates writes to `aitask_update.sh`. Known limit
  stated: re-check → write is not atomic against non-workflow writers (sync
  merge); the lock narrows it and the merge driver resolves divergent advances to
  PARTIAL (t1663_2).

### 2b. `aitask_pick_own.sh --expect-status <status>` (opt-in claim precondition)

Today `main()` reads `prev_status` (Step 1c) **before** `acquire_lock`, then
`update_task_status` writes `Implementing` unconditionally; its `RECLAIM_*`
signals fire only for a prior `Implementing` by the same email, so a task that
went `Postponed` / `Done` / `Editing` while the prompt was open — by a session
that has since released it — would be silently re-claimed.

- New flag `--expect-status <S>` (validated against the status vocabulary; usage
  + help text updated). Absent → behaviour byte-for-byte unchanged (every
  existing caller).
- With it, **after** `acquire_lock` succeeds (or after a `--force` takeover) and
  **before** `update_task_status`: call `task_sync` again (a session that
  changed the status committed and pushed before releasing the lock, so a pull
  **under the lock** is what makes the read current) and branch on
  `TASK_SYNC_STATUS` — never on the call's exit code, which is 0 on failure by
  design:
  - `synced` / `up-to-date` → the local file is current; continue.
  - `no-remote` → there is nothing to be stale against; continue.
  - `failed` (or empty / anything else) → freshness is **unverified**: release
    the lock this run acquired (`aitask_lock.sh --unlock`), print
    `STATUS_UNVERIFIED:<TASK_SYNC_REASON>`, exit 1 — no status, contributor-list
    or commit mutation (the gate sits above all three).
  Then re-resolve and re-read `status:` (missing file →
  `STATUS_CHANGED:missing|<S>`).
- Mismatch → release the lock this run acquired, print
  `STATUS_CHANGED:<actual>|<S>`, exit 1. Nothing else is written: the check sits
  above the status write, the email store and the commit, exactly like the
  existing refusal gates.
- Consequence, stated in help text and the record: in a checkout whose task
  data cannot sync (e.g. a wedged data worktree — this checkout reported one at
  claim time today), a premise-pending claim refuses until `ait syncer`
  reconciles it. That is the intended fail-closed direction; claims without a
  pending premise choice are unaffected.
- Edit applied atomically (prepare in a scratch copy, `bash -n`, run the
  pick_own suites against it, then move into place): every pick in this checkout
  runs this script.

### 3. New procedure — `.claude/skills/task-workflow/premise-staleness.md`

Profile-invariant (no Jinja). Sections:

- **`## Check`** (Step 3 Check 7, **pre-lock — writes nothing**). Run
  `./.aitask-scripts/aitask_premise_stale.sh check <task_file>` from the repo
  root; branch on the **last line** `DECISION:`. `FRESH`/`SKIP` → silent,
  `premise_decision = null`, return.
  `ASK_STALE` → store the **complete** check output verbatim as
  `premise_decision.protocol` (every row; the source of truth for every later
  step). Decode path fields (`%0D`, `%0A`, `%7C`, then `%25`) and classify rows:
  drift (`CHANGED`, `DELETED`, `absent_at_baseline`), never-existed, scope
  defects (`invalid_reference`), unverifiable (`history_unavailable`,
  `malformed_row`). The **question text** carries `DISPLAY:` plus the rows —
  **capped at 10 for presentation only**, then "… and K more (all K are kept and
  reviewed)" — and one line per non-drift class saying what Proceed will do with
  it (from the table above).
  ⚠️ **NON-SKIPPABLE** banner (Step 8 wording; no profile key covers it —
  currently: none; auto mode, "work without stopping", "be brief"/"don't ask"
  do not cover it; the only skip is an explicit user pre-decision in chat).
  `AskUserQuestion`, header "Premise", options:
  1. "Proceed — premise still valid" (description says whether the baseline will
     advance; "will not advance — N path(s) could not be checked" when
     unverifiable rows exist) → `premise_decision.choice = proceed`; continue.
  2. "Review & replan with this evidence" → `choice = replan`; continue.
  3. "Postpone task" → `choice = postpone`; continue. **No write here** — the
     status change happens post-lock (§`## Post-lock`), because a Ready task can
     be claimed by another session while this prompt is open, and local
     `aitask_update.sh` does not check locks.
  4. "Pick a different task" → return to the calling skill's task selection
     (nothing changed, no banner — same shape as Step 4 LOCK_FAILED).
- **`## Post-lock`** (Step 4, right after any ownership success, before
  materialize-active). Reached only when Step 4's claim succeeded — and with a
  premise choice pending, Step 4 claims with `--expect-status Ready` (step 2b),
  so the claim itself attests, under the lock and from freshly synced data, that
  the task is still the `Ready` task the prompt was about. Every `LOCK_FAILED` /
  `LOCK_LIVE_HOLDER` / `LOCK_UNVERIFIABLE_HOLDER` / `LOCK_ERROR` branch keeps its
  existing handling, so a session holding the task is never overwritten, and a
  status changed by a session that has since released it is caught by
  `STATUS_CHANGED:` (Step 4 branch, below).
  - `choice = postpone` → `aitask_update.sh --batch <num> --status Postponed
    --assigned-to "" --silent`, `aitask_task_commit.sh -m "ait: Postpone t<id>
    (premise check)" <task_file>`, `./ait git push`, then the **Lock Release
    Procedure** (`lock-release.md`); **Stopped** banner `outcome=postponed`,
    reason "premise may no longer hold — postponed", next "`ait update <id>
    --status Ready`, then `/aitask-pick <id>`"; end.
  - `choice = proceed`, prompted evidence has unverifiable rows → display
    "baseline not advanced — N path(s) could not be checked; re-checked next
    pick"; continue.
  - `choice = proceed`, otherwise → if never-existed rows exist, ask (⚠️
    NON-SKIPPABLE, user-owned removal) "Remove N reference(s) to files that have
    never existed: <list>? Kept references keep being reported until the file
    exists." options **"Keep them — may be future files"** (first, default) /
    "Remove them"; then run `advance` with the prompted `CHECKED`/`FINGERPRINT`
    and one `--remove-ref` per approved path.
    `ADVANCED:` → display "premise baseline advanced to <sha8>" (+ removed refs);
    parse the commit line per the `ait-git` outcome contract (uncommitted →
    warn, continue). `ADVANCE_REFUSED:` / `ADVANCE_FAILED:` → warn, baseline
    unchanged, continue. `MISMATCH:` → the answer is **void**; show the fresh
    evidence: fresh `FRESH`/`SKIP` → display "premise inputs changed after the
    prompt; fresh check reads <D> — baseline not advanced", continue; fresh
    `ASK_STALE` → replace `premise_decision.protocol` with the fresh output and
    re-prompt with the same four options (now post-lock): Proceed → loop this
    section; Replan → `choice = replan`; Postpone → the postpone branch above;
    Pick another → `aitask_update.sh --status Ready --assigned-to ""`, commit,
    push, Lock Release Procedure, return to selection.
- **`## Advance after an approved replan`** (Step 7; planning's Approve-and-stop).
  Same transaction rules: unverifiable prompted rows → no advance; never-existed
  rows → the same explicit keep/remove question; then `advance` with the stored
  pair. Anything but `ADVANCED:` → no advance, display the fresh `DISPLAY:`,
  continue (the plan is approved; the next pick re-checks). Never re-prompts the
  four options.

### 4. `.claude/skills/task-workflow/SKILL.md`

- Context table: add `premise_decision` (object/null: `choice`, `checked`,
  `fingerprint`, `protocol`; set by Step 3 Check 7; read by Step 4, planning.md,
  Step 7; initialized null).
- **Check 7 — Premise staleness** after Check 6 (thin dispatch): skip unless
  `status` is `Ready` and `issue_type` ≠ `manual_verification` (Check 3 / t1555
  seam owns MV — no double prompt). `{% if profile.headless %}` (mirrors Check
  6): run `check`; on `ASK_STALE` display `DISPLAY:` + evidence, **never prompt,
  never advance, never postpone**, continue `{% else %}` execute the Premise
  Staleness Procedure §`## Check` `{% endif %}`.
- Step 4 **Claim task ownership**: when `premise_decision` is set, append
  `--expect-status Ready` to every `aitask_pick_own.sh` invocation in Step 4 and
  in its `--force` re-runs. New output branch `STATUS_CHANGED:<actual>|Ready` →
  "Task t\<N\> changed while the premise prompt was open (status is now
  \<actual\>). Nothing was claimed." Void `premise_decision` and return to the
  calling skill's task selection (no write, nothing to undo).
  New branch `STATUS_UNVERIFIED:<reason>` → nothing was claimed; the lock was
  released. `AskUserQuestion` (question names the reason and that the task's
  current status could not be confirmed against the remote): "Retry" (re-run the
  same claim, flags unchanged) / "Pick a different task" (void
  `premise_decision`, return to selection). No option claims without the
  verification.
- Step 4: new bullet after the **Claim task ownership** block, before
  "Materialize the active-gates tuple": if `premise_decision` is set, execute
  §`## Post-lock` (postpone ends the run there, before materialization).
- Step 7, after "Record risk-evaluated gate", **before** "Risk-mitigation
  'before' creation" (a before-stop then still keeps the confirmed premise): if
  `premise_decision.choice` is `replan`, execute §`## Advance after an approved
  replan`. A resumed session has no `premise_decision` → no advance (fail-safe).
- Procedures list: add the **Premise Staleness Procedure** entry.

### 5. `.claude/skills/task-workflow/planning.md`

- **§6.0b Premise replan** (after §6.0a, outside the plan-preference Jinja block,
  profile-invariant): if `premise_decision.choice` is `replan` and a plan exists
  → set `force_verify` (§6.0a's shape) and **enter verify mode directly**,
  bypassing the plan preference and its prompt (a `use_current` / `SKIP`
  resolution would silently drop the user's explicit choice). The verify-path
  `plan_verified` append still applies.
- §6.1 bullet **Premise evidence (replan)**, with or without an existing plan:
  read **`premise_decision.protocol` — never the capped widget list** — and
  inspect **every** evidence row (`git log --oneline <baseline>..<checked> --
  ":(literal)<path>"` for CHANGED; the culprit commit for DELETED; the reason for
  UNKNOWN). Record a `## Premise review` section in the plan listing **every**
  row (count stated and equal to the protocol's row count) with a per-row
  verdict.
- Checkpoint "Approve and stop here": if `premise_decision.choice` is `replan`,
  first execute §`## Advance after an approved replan` (lock still held), then
  the Approved-Plan Stop Sequence.

### 6. `postponed` banner outcome

- `.claude/skills/task-workflow/workflow-end.md`: add the `postponed` row.
- `.aitask-scripts/lib/sitrep_harvest.py`: `"postponed"` in `STOPPED_OUTCOMES`
  (not in the actionable `in-flight/ready/split` set).
- Grep the vocabulary (`aborted.*split.*unchanged`) across `.aitask-scripts/`,
  `tests/`, `aidocs/`, `website/` and update every consumer.

### 7. Goldens, renders, prerenders

- `tests/test_skill_render_task_workflow.sh`: `premise-staleness.md` into
  `WRAPPED_FILES_INVARIANT` + its `-default` golden.
- Regenerate `tests/golden/procs/task-workflow/{SKILL,planning}-{default,fast,remote}.md`
  (+ `premise-staleness-default.md`); review each diff against the edit.
- Refresh the committed remote prerenders (`.claude/skills/task-workflow-remote-/`,
  `.agents/skills/task-workflow-remote-codex-/`, `.opencode/skills/task-workflow-remote-/`)
  by rendering only the pickrem/pickweb remote closures, as t1663_2 did; each
  diff exactly this change.
- `./.aitask-scripts/aitask_skill_verify.sh` green.

### 8. Tests — `tests/test_premise_check_workflow.sh` (new)

Fixture: the `new_project` pattern of `tests/test_premise_baseline_seeding.sh`
plus the premise producer/core, `task_yaml`, `aitask_task_commit.sh`; tasks
seeded via `aitask_create.sh --batch --commit --file-ref …`.
`assert_counters_init` if bodies use subshells. Every case asserts the re-pick:
- **Changed (end-to-end):** `FRESH` → change + commit → `ASK_STALE` → `advance`
  → `ADVANCED:<CHECKED>`, stored == CHECKED, commit present → re-check `FRESH`.
- **Deleted:** delete a watched file (plus one live file) → `ASK_STALE` with
  `DELETED` → advance → re-check `FRESH` (deleted path `retired`, no UNKNOWN);
  all-watched-deleted variant → re-check `SKIP`/`all_retired`, **not** `FRESH`.
- **Never existed:** ref to a nonexistent path → `UNKNOWN …|never_existed`;
  advance without `--remove-ref` → ref kept, re-check still reports it; advance
  with `--remove-ref` → `REMOVED:`, ref gone, re-check `FRESH`; `--remove-ref`
  of a live path → `ADVANCE_REFUSED:not_removable`, file byte-identical.
  Later-created future file → reads `absent_at_baseline` then `ok` after advance.
- **Invalid reference:** `[good.py, null]` → advance → re-check still `ASK_STALE`
  naming only the defect (documented recurrence, never `FRESH`).
- **Unverifiable:** `log.date=invalid-date-mode` fixture → advance →
  `ADVANCE_REFUSED:unverifiable`, baseline unchanged.
- **TOCTOU revision:** commit between check and advance → stored == prompted
  CHECKED ≠ HEAD; re-check names exactly the 1 newer commit.
- **TOCTOU metadata:** mutate `file_references:` / the stored baseline between
  check and advance → `MISMATCH:`, file byte-identical, fresh protocol follows.
- **Overflow:** 12 changed watched files → `check` emits 12 `CHANGED` rows (no
  upstream truncation); advance covers all 12 (re-check `FRESH`).
- **Advance all-or-nothing:** an approved removable (`never_existed`) ref plus a
  full-length **nonexistent** `--checked` commit (40 hex, no such object) →
  `ADVANCE_FAILED:`, task file **byte-identical** (ref still present, baseline
  unchanged), no commit.
- **Prompt race, live holder:** after `check`, a second identity locks the task
  (`aitask_lock.sh <id> --email other@…`; lock + bare-remote fixture per
  `tests/test_pick_own_scoped_commit.sh` / `tests/test_lock_live_holder_gate.sh`)
  → `aitask_pick_own.sh --expect-status Ready` returns `LOCK_FAILED`; task not
  `Postponed`, no claim commit.
- **`tests/test_pick_own_expect_status.sh`** (new; two clones A/B of one bare
  remote, lock branch initialised). **Window control without production hooks:**
  the fixture's `.aitask-scripts/aitask_lock.sh` is a wrapper that execs the real
  script (`aitask_lock.real.sh`) and, on `--lock` only, first runs a per-case
  action file — so the action lands **after** A's initial `sync_remote` and
  **before** A's under-lock refresh. A fixture-only override appended to the
  copied `lib/task_utils.sh` makes `_task_pull_rebase` fail when a marker file
  exists (the original runs otherwise), so only the under-lock sync can fail.
  Cases (each asserts exit status, A's task file bytes, `emails.txt` bytes, A's
  `HEAD` unchanged / no claim commit, and `aitask_lock.sh --check` free after):
  1. **In-window change:** action = B sets `Postponed` (variant: `Done`),
     commits, pushes, holds no lock → `STATUS_CHANGED:Postponed|Ready`; A's file
     reads `Postponed` (pulled under the lock), no `Implementing` commit.
  2. **In-window change + failed sync:** action = B pushes `Postponed`, then the
     marker is created → `STATUS_UNVERIFIED:<reason>`; A's file still
     byte-identical `Ready`, no status / contributor-list / claim-commit mutation.
  3. **Pre-existing change** (B pushes before A starts; ordinary case) →
     `STATUS_CHANGED:` via the initial sync.
  4. Controls: no action, `Ready` → `OWNED:`; case-1 action **without** the
     flag → claims (today's behaviour), proving the gate is what refuses.
  Existing `test_pick_own_*` / `test_lock_*` suites stay green.
- **Structural pins** (rendered SKILL/planning/procedure, fast + default):
  `## Check` contains no `--status` / `advance` call; the advance and postpone
  writes are referenced only from Step 4 (`## Post-lock`), Step 7 and
  planning's Approve-and-stop; the procedure names `protocol` as the replan
  source and the 10-row cap as presentation-only; the never-existed question
  lists "Keep" first.
- **CLI misuse:** bad sha, `HEAD`, short sha, `NONE`/bad fingerprint, missing
  file → non-zero, file untouched.
- **Allowlist:** helper in all 5 touchpoints (shape of
  `test_verification_stale.sh::test_helper_is_in_every_invocation_allowlist`).
- Extend `tests/test_workflow_end_banner_contract.sh` (OUT_RE + vocabulary loop
  `postponed`) and `tests/test_sitrep_harvest.py` (a `postponed` banner parses
  with `complete_fields` and yields no stopped-self item).

### 9. Allowlist registration (gated)

Before the first edit require `git diff --quiet HEAD --` on the 5 files
(`.claude/settings.local.json`, `.codex/rules/default.rules`,
`seed/claude_settings.local.json`, `seed/codex_rules.default.rules`,
`seed/opencode_config.seed.json`). Still dirty with t1981_1's hunks → stop and
ask the user (wait for t1981_1 / hand registration back via a note); never
commit those files with foreign hunks. When clean: `aitask_audit_wrappers.sh
apply-helper-whitelist aitask_premise_stale.sh`, then `audit-helper-whitelist` →
no `MISSING:`.

### 10. Docs

`aidocs/framework/task_premise_staleness.md`: Interaction → Check 7 (why);
pre-lock prompt / post-lock writes; the evidence-class resolution table; the
`retired` / `never_existed` / `all_retired` vocabulary in the protocol section;
`advance` verb (single validated write); the claim-time `--expect-status Ready`
precondition and why `previous_status` cannot serve; headless = display only; lifecycle rows (approve-and-stop
advance, postpone post-lock, never-existed keep/remove, unverifiable no-advance);
`postponed` outcome; Known limits (invalid references recur until hand-fixed;
kept never-existed references keep reporting).
Step 8e notes: t1981_5 (take Check 8, re-read Step 3), t1663_5 (website: Check 7,
four options, `postponed`, resolution table), t1655 (core gained `retired` /
`never_existed` / `all_retired`). pickrem/pickweb run their own Step 3 and do not
get the check — offer a follow-up task at Step 8b/8e.

### Post-phase (risk mitigations)

1. [premise_advance_red_proofs] In a scratch mirror (copy of `.aitask-scripts/`
   + `tests/` + rendered skills; never the shared tree), run a control (both new
   suites green), then apply one mutant at a time and run **both**
   `tests/test_premise_check_workflow.sh` and `tests/test_pick_own_expect_status.sh`
   against it. Record per mutant the failing-assertion count **from the suite
   that exercises that mutation** — (a)–(f) from the premise suite, (g)–(h) from
   the expect-status suite (the premise suite's live-holder case refuses at
   `LOCK_FAILED`, before the guarded-claim code runs, so it cannot witness them)
   — and note the other suite's count as well:
   (a) `advance` skips the fingerprint compare → metadata-TOCTOU case fails;
   (b) `advance` writes `git rev-parse HEAD` instead of `--checked` → revision
       case fails;
   (c) the core counts `retired` as positively checked → all-retired case reads
       `FRESH` and fails;
   (d) `advance` skips the `never_existed` membership check → the live-path
       `--remove-ref` case fails;
   (e) a `## Check` section that writes `--status Postponed` → structural pin fails;
   (f) `advance` split into two `aitask_update.sh` calls (removals, then
       baseline) → the all-or-nothing case fails (ref removed, file changed);
   (g) `aitask_pick_own.sh --expect-status` without the under-lock `task_sync`
       → in-window case 1 fails (claims a `Postponed` task) while pre-existing
       case 3 still passes, proving the window is what case 1 tests; with the
       re-read removed entirely → cases 1 and 3 fail;
   (h) branching on `task_sync`'s exit code instead of `TASK_SYNC_STATUS` →
       failed-sync case 2 fails (claims on stale `Ready`).
   Record both suites' counts per mutant in Final Implementation Notes; a mutant
   with 0 failures in its witnessing suite means a vacuous test — fix it before
   Step 8.

## Verification

```bash
bash tests/test_premise_check_workflow.sh
bash tests/test_pick_own_expect_status.sh
bash tests/test_pick_own_scoped_commit.sh
bash tests/test_lock_live_holder_gate.sh
bash tests/test_lock_reclaim.sh
bash tests/test_premise_stale.sh
bash tests/test_premise_baseline_field.sh
bash tests/test_premise_baseline_seeding.sh
bash tests/test_skill_render_task_workflow.sh
bash tests/test_workflow_end_banner_contract.sh
bash tests/run_all_python_tests.sh   # verdict = last line (core + sitrep harvest + purity)
./.aitask-scripts/aitask_skill_verify.sh
./.aitask-scripts/aitask_audit_wrappers.sh audit-helper-whitelist aitask_premise_stale.sh
shellcheck .aitask-scripts/aitask_premise_stale.sh
```

Step 9 (Post-Implementation): current-branch mode — no merge; archive with
`aitask_archive.sh 1663_4`, push.

## Risk

### Code-health risk: medium
- Step 3/4/7 and planning.md edits sit on every pick's path; a misplaced condition (Check 7 firing for MV / in-flight tasks, a write before ownership, an advance on a non-confirming route) regresses every workflow · severity: medium · → mitigation: none (step 8 structural pins + golden diff review)
- The core/producer change (`retired`, `never_existed`, `all_retired`) touches t1663_1's verified engine and the t1655 contract surface; a misclassification could turn an uncheckable path into silence · severity: medium · → mitigation: none (attested probes with explicit status; FRESH still needs ≥1 positively checked path; red-proof mutant (c))
- `aitask_pick_own.sh` runs on every pick; a defect in the new `--expect-status` gate (or a torn mid-edit file) breaks every claim, and a gate that refuses wrongly strands tasks · severity: medium · → mitigation: none (opt-in flag, absent = unchanged; atomic replace; existing pick_own/lock suites + no-flag control; red-proof mutants (g)/(h))
- The fail-closed `STATUS_UNVERIFIED` gate blocks every premise-pending claim in a checkout whose task data cannot sync (this checkout's data worktree is wedged right now) · severity: low · → mitigation: none (by design; the prompt names `ait syncer`, "Pick a different task" stays available, non-premise claims unaffected)
- The 5 allowlist touchpoints currently carry t1981_1's uncommitted hunks; committing them would sweep foreign work into this task · severity: medium · → mitigation: none (step 9 clean-vs-HEAD gate, stop-and-ask)
- The new `postponed` outcome could miss a consumer of the closed vocabulary · severity: low · → mitigation: none (step 6 grep inventory)

### Goal-achievement risk: medium
- The prompt and its routes are agent-executed prose; tests pin the helper transactions and the routing text, not a live run · severity: medium · → mitigation: none (Step 8c manual-verification offer covers a live walk of the four options)
- The TOCTOU, re-pick and race tests could pass vacuously (a fixture mutation that never takes effect, an advance that never ran) · severity: low (residual — addressed by inline post-phase premise_advance_red_proofs) · → mitigation: inline post-phase premise_advance_red_proofs

### Planned mitigations
- timing: post-phase | name: premise_advance_red_proofs | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: TOCTOU/re-pick/race tests passing vacuously | desc: scratch-mirror mutants (no fingerprint compare / write HEAD / retired counted as checked / no never_existed membership check / pre-lock postpone write / split advance write / expect-status without under-lock sync or re-read / exit-code sync check) run against both new suites, each mutant witnessed by the suite that exercises it ((a)–(f) premise suite, (g)–(h) expect-status suite); counts recorded in Final Implementation Notes

## Post-Review Changes

### Change Request 1 (2026-11-07)
- **Requested by user:** four review findings, each verified against the code before changing anything.
  1. (high) `aitask_pick_own.sh --expect-status` assumed a lock was taken, but `acquire_lock` returns success without locking when no email resolves. With no email and another owner's lock, the guarded claim returned `OWNED:` and wrote `Implementing`.
  2. (medium) `advance` checked the given file but `aitask_update.sh` wrote the task it resolved by id. A copied `t<id>_*.md` could advance the real task's baseline past unreviewed changes.
  3. (medium) `verify_expected_status` compared the raw `status:` text, so a valid `status: "Ready"` read `STATUS_CHANGED:"Ready"|Ready`.
  4. (medium) planning.md routed an existing-plan replan into the verify path, whose terminal jump preceded the evidence-review bullet; a review could be skipped while the advance still ran.
- **Changes made:**
  1. The guarded claim refuses `LOCK_REQUIRED:no_email` before any lock, status, contributor-list or commit write.
  2. `advance` resolves the single active `t<id>_*.md` by the writer's rule and requires `-ef` identity with the given path (symlink aliases pass), and commits the canonical path.
  3. The status is read through `task_yaml.parse_frontmatter` (glue in `aitask_pick_own.sh`): quoted, commented and padded spellings are `Ready`; a missing status, invalid YAML or a non-string value is `STATUS_UNVERIFIED:unreadable_status`, never a state change; no Python is `STATUS_UNVERIFIED:python_unavailable`; a vanished file is `STATUS_CHANGED:missing`.
  4. The Premise evidence review became a numbered prerequisite placed before the verify-path paragraph ("first, on every path"); the verify path states it includes the review; a **Premise-review guard** after Save Plan checks `## Premise review` + `Evidence rows reviewed: <n>`; the replan advance has the same precondition and does not advance without it.
- **Tests:** `tests/test_pick_own_expect_status.sh` cases 6 (no email vs an existing holder), 7 (four status spellings), 8 (no status / bad YAML / numeric) — the pre-fix script fails all 19 of their assertions. `tests/test_premise_check_workflow.sh` J2 (copy refused, real task untouched and still reporting; symlink alias advances and commits the canonical file) and routing-order pins in L.
- **Files affected:** `.aitask-scripts/aitask_pick_own.sh`, `.aitask-scripts/aitask_premise_stale.sh`, `.claude/skills/task-workflow/planning.md`, `.claude/skills/task-workflow/premise-staleness.md`, `aidocs/framework/task_premise_staleness.md`, both new tests, the planning/premise-staleness goldens and the three remote prerenders.

### Change Request 2 (2026-11-07)
- **Requested by user:** (review finding, confirmed) Step 4 had no branch for the helper's new `LOCK_REQUIRED:no_email`, so a skip-email claim with a pending premise answer got a structured refusal with no route; and the `STATUS_UNVERIFIED` question always blamed synchronization and recommended `ait syncer`, though `unreadable_status` and `python_unavailable` are local failures. Consumer handling was unpinned.
- **Changes made:**
  - SKILL.md Step 4: `LOCK_REQUIRED:no_email` branch — "Provide an email" (step 6's email question without "Skip", then retry with `--email … --expect-status Ready`), "Continue without the premise answer" (`premise_decision` → null, plain no-email claim, baseline untouched), "Pick a different task".
  - `STATUS_UNVERIFIED:<reason>` question text now depends on the reason: `unreadable_status` (fix the frontmatter), `python_unavailable` (`ait setup`), any other value = sync classifier code (`ait syncer`). Header "Unverified".
  - Tests (L): the guarded refusal tokens are DERIVED from `aitask_pick_own.sh --help` (lines marked `--expect-status only`) and each must have a Step 4 branch; the LOCK_REQUIRED retry keeps the guard; continuing without it drops the answer; reason-specific wording, `ait syncer` only on the sync line.
  - Control: mutant `n_no_lock_required_branch` (branch marker removed) fails 8 premise-suite assertions.
- **Files affected:** `.claude/skills/task-workflow/SKILL.md`, `tests/test_premise_check_workflow.sh`, SKILL goldens (3), the three remote prerenders.

### Change Request 3 (2026-11-07)
- **Requested by user:** (review finding, confirmed) the `LOCK_REQUIRED:no_email` handler's "Continue without the premise answer" re-ran the claim with neither an email nor `--expect-status`, so the recovery could claim a task another owner held, or turn a task postponed meanwhile back into `Implementing` — dropping the premise answer does not make an unguarded claim safe.
- **Changes made:** removed that option; the branch now offers only "Provide an email" (guarded retry) and "Pick a different task", and states that no route re-runs the claim unguarded. The test assertion that required the bypass was replaced by pins that every claim re-run in the branch keeps `--expect-status Ready` and that no "continue without" option exists; `tests/test_pick_own_expect_status.sh` case 6b proves the only recovery cannot claim — refusal then guarded retry → `LOCK_FAILED` against another holder (lock untouched), and → `STATUS_CHANGED:Postponed|Ready` when the task was postponed between refusal and retry.
- **Control:** mutant `o_unguarded_recovery` (an unguarded re-run re-added) fails 2 premise-suite assertions.
- **Files affected:** `.claude/skills/task-workflow/SKILL.md`, both new tests, SKILL goldens (3), the three remote prerenders.

### Change Request 4 (2026-11-08)
- **Requested by user:** (review finding, confirmed) Step 4's existing `LOCK_ERROR` handler still offered "Continue without lock" with a premise answer pending — skipping the success-only `## Post-lock` step (a pending Postpone silently lost) — and planning's "Approve and stop here" advance assumed the lock was held though it runs before Step 7's ownership guard.
- **Changes made:**
  - `advance` takes a required `--owner <email>` and proves ownership itself: `aitask_lock.sh --check` must succeed and name that email on this host, else `ADVANCE_REFUSED:not_owner|<detail>` with no write. Placed LAST before the write (step 3b) — after the identity, fingerprint, unverifiable and removal checks — so the proof-to-write window is shortest; a repo whose lock cannot be read therefore refuses (fail-closed).
  - SKILL.md Step 4 `LOCK_ERROR`: while `premise_decision` is set, "Continue without lock" is not offered — only the guarded "Retry", "Pick a different task" (answer dropped, nothing claimed) and "Abort". The Step 7 ownership guard's LOCK_ERROR line defers to the same rule.
  - premise-staleness.md: every `advance` invocation passes `--owner "<email>"`; the replan-advance section states ownership is proven, not assumed. planning.md's Approve-and-stop wording no longer claims the lock is held.
  - Tests: J3 (unlocked → `not_owner|no lock held`, other owner's lock → `not_owner|locked by other@…`, byte-identical, no commit, change still reported); misuse "missing --owner"; pins for the LOCK_ERROR rule (Step 4 + Step 7 guard) and that every `advance` call in the procedure passes `--owner`. The suite's `padv` helper now takes the lock as the owner; case E takes it before breaking `git log`.
- **Files affected:** `.aitask-scripts/aitask_premise_stale.sh`, `.claude/skills/task-workflow/SKILL.md`, `.claude/skills/task-workflow/premise-staleness.md`, `.claude/skills/task-workflow/planning.md`, `aidocs/framework/task_premise_staleness.md`, `tests/test_premise_check_workflow.sh`, goldens (SKILL ×3, planning ×3, premise-staleness), the three remote prerenders.

### Change Request 5 (2026-11-08)
- **Requested by user:** (review finding, confirmed) the `advance` ownership proof checked only `locked_by` and `hostname`. Separate agent sessions of the same user share both, so a second live session (whose claim `aitask_pick_own.sh` correctly refused with `LOCK_LIVE_HOLDER`) could still advance and commit the baseline, and an older planning session could write after another same-user session took the task.
- **Changes made:** the ownership step (3b) now also requires the lock's recorded session anchor (`pid`, `pid_starttime`, `pid_starttime_kind`) to be THIS session's, via `lib/pid_anchor.sh::lock_anchor_is_self` — the same test the lock's acquire gate uses. A different live session → `ADVANCE_REFUSED:not_owner|held by another session of <email> on <host> (pid N)`. A lock with no anchor, or a caller that cannot resolve its own anchor (outside the agent's tmux pane, no `AIT_AGENT_PID`) → `ADVANCE_REFUSED:owner_unverifiable|…`, routed explicitly in the procedure and never a pass. Design record + Known limits updated (a session that cannot name itself cannot advance).
- **Tests:** the premise suite pins one anchor (`AIT_AGENT_PID=$$`); J4: same email + host, different live session (a `sleep` process anchor) → `not_owner`, byte-identical, no commit, holder's lock untouched; control: the holding session advances; anchor-less lock and anchor-less caller → `owner_unverifiable`, byte-identical. Pin: the procedure's `owner_unverifiable` bullet says never a pass. Live check: this session resolves the same anchor its claim recorded (pid 3311625).
- **Mutants:** `r_no_session_anchor_check` fails 4; `s_anchorless_lock_not_unverifiable` fails 1 (premise suite); control green.
- **Files affected:** `.aitask-scripts/aitask_premise_stale.sh`, `.claude/skills/task-workflow/premise-staleness.md`, `aidocs/framework/task_premise_staleness.md`, `tests/test_premise_check_workflow.sh`, premise-staleness golden, the three remote prerenders.

### Change Request 6 (2026-11-08)
- **Requested by user:** (review finding, confirmed) `ADVANCE_REFUSED:not_owner` was handled as "display and Continue", so after another session force-claimed the task, Step 4 went on to materialize-active (a write to a task this session no longer owned), and the replan route's blanket "anything other than ADVANCED → continue" fell through to the Approved-Plan Stop Sequence, which reverts the status and releases the new holder's lock.
- **Changes made:**
  - `aitask_premise_stale.sh`: the identity resolution and the ownership proof were extracted into `_resolve_active_task` / `_owner_proof` (advance's outputs unchanged), and exposed as a new verb `owner <task_file> --owner <email>` → `OWNER_OK` / `NOT_OWNER:<detail>` / `OWNER_UNVERIFIABLE:<detail>` (identity-checked, CLI misuse dies).
  - premise-staleness.md: new terminal section `## Ownership lost` — writes nothing more and undoes nothing (no status revert, no lock release, no gate materialization, no stop sequence, no abort, no advance), state-derived Stopped banner, end. Every `not_owner` routes there: Post-lock "proceed", the replan advance (which now tells callers the workflow ended), and the `owner` proof that now precedes the post-lock postpone write and the re-prompt revert to Ready. `OWNER_UNVERIFIABLE` before a postpone/revert warns and proceeds (the user's explicit choice, the same condition every step after the claim runs under; an advance still refuses on it).
  - SKILL.md Step 4 post-lock bullet and Step 7 replan bullet: an `## Ownership lost` exit ends the workflow — no materialization, no implementation. planning.md Approve-and-stop: after it, do **not** run the stop sequence.
  - Design record: `owner` verb, `not_owner` terminal everywhere, the unverifiable asymmetry.
- **Tests:** J5 (`owner` verb: own lock OK; another same-user session's force-claim → `NOT_OWNER` naming its pid, advance agrees, nothing written, new holder's lock untouched; no lock → `NOT_OWNER`; anchor-less → `OWNER_UNVERIFIABLE`; copy and missing `--owner` die). Routing pins: `## Ownership lost` forbids revert / lock release / materialization / stop sequence and ends state-derived; Post-lock's not_owner bullet routes there and never says continue; the owner proof precedes the postpone write and the revert; the replan advance's not_owner is terminal and forbids the stop sequence; Step 4 stops before materialization (and the step sits before it); Step 7 ends; Approve-and-stop states the skip before the stop sequence.
- **Files affected:** `.aitask-scripts/aitask_premise_stale.sh`, `.claude/skills/task-workflow/{premise-staleness,SKILL,planning}.md`, `aidocs/framework/task_premise_staleness.md`, `tests/test_premise_check_workflow.sh`, goldens (SKILL ×3, planning ×3, premise-staleness), the three remote prerenders.

## Final Implementation Notes
- **Actual work done:** all ten plan sections and the post-phase landed, then six review rounds (Change Requests 1–6 above) hardened the ownership boundary. What ships:
  - **Core/producer** (`lib/task_premise.py`, `aitask_premise_stale.sh check`): path states `retired` (absent at both ends, history reachable from the baseline proves it existed, 0 window commits — not evidence, not checked) and `never_existed` (UNKNOWN evidence); SKIP reason `all_retired`; `PremiseResult.retired`. FRESH still needs ≥1 positively checked path.
  - **`aitask_premise_stale.sh advance <task_file> --checked --fingerprint --owner [--remove-ref]...`** — the only write path: identity (`_resolve_active_task`: the single active `t<id>_*.md`, `-ef`) → fingerprint (`MISMATCH:` + fresh protocol) → unverifiable (`history_unavailable`/`malformed_row`/`unknown_history` → refused) → removals (each must be a fresh `never_existed` row; a list with non-string entries → `list_unwritable`) → ownership LAST (`_owner_proof`: lock names `--owner` on this host AND `lock_anchor_is_self` on the recorded pid anchor; `not_owner` / `owner_unverifiable`) → ONE `aitask_update.sh` call (removals + `--premise-baseline <checked>`) → path-scoped commit of the canonical file.
  - **`aitask_premise_stale.sh owner <task_file> --owner`** — the same proof for the procedure's other post-lock writes.
  - **`aitask_pick_own.sh --expect-status <S>`** — under the lock and above every write: `LOCK_REQUIRED:no_email` (no email ⇒ no real lock), re-`task_sync` branching on `TASK_SYNC_STATUS` (`STATUS_UNVERIFIED:<sync reason>`), status read via `task_yaml` (`STATUS_UNVERIFIED:unreadable_status` / `python_unavailable`), `STATUS_CHANGED:<actual>|<S>` (incl. `missing`); every refusal releases the lock it took. Absent ⇒ behaviour unchanged.
  - **Skills**: new `task-workflow/premise-staleness.md` (`## Check` pre-lock, writes nothing; `## Post-lock`; `## Advance after an approved replan`; terminal `## Ownership lost`); SKILL.md Check 7 (headless = report only) + Step 4 guarded claim, `STATUS_CHANGED`/`STATUS_UNVERIFIED`/`LOCK_REQUIRED` branches, no "Continue without lock" while an answer is pending, post-lock hook before materialization + Step 7 replan advance; planning.md §6.0b (replan forces verify mode, bypassing the plan preference), the Premise evidence review as the FIRST planning action with a `## Premise review` + `Evidence rows reviewed: <n>` record and a guard after Save Plan, and the Approve-and-stop advance (which skips the stop sequence on Ownership lost).
  - **`postponed`** banner outcome (`workflow-end.md`, `sitrep_harvest.STOPPED_OUTCOMES`, new `ACTIONABLE_STOPPED_OUTCOMES`).
  - Allowlist in all 5 touchpoints; design record rewritten for Check 7; goldens + 3 committed remote prerenders.
- **Deviations from plan:** the check is **Check 7** (Check 6 was taken by the inbox check). Ownership became the central concern of the review rounds: the plan's "post-lock, fingerprint-gated" grew into a proven-ownership transaction (identity, real lock, session anchor, terminal ownership-lost exit, a separate `owner` verb). Postpone routes through the guarded claim instead of writing pre-lock. `never_existed` references are kept unless explicitly approved for removal (user decision); invalid references recur until hand-fixed (user decision).
- **Issues encountered:**
  - The 5 allowlist files held t1981_1's uncommitted hunks at planning time; by step 9 t1981_1 had landed and they were clean vs HEAD, so registration went ahead without a sweep.
  - `aitask_lock.sh --check` fails under `log.date=invalid-date-mode`, so a repo with a broken `git log` cannot prove ownership: the ownership step was placed last (after the unverifiable check) and case E takes its lock before breaking `git log`.
  - Full Python suite: `PYTHON SUITE: FAILED` on 6 tests not caused by this task — 5 `test_screen_recording_cli.py::PickFromRuns` (another session was mid-edit on `screen_recording/`, 653 uncommitted lines; 9/9 pass when re-run alone) and `test_board_movement.py::IsolationNegativeControlTests::test_in_process_task_dir_override_reads_the_real_repo` (trips on another session's real task file `t2226_stop_sync_fixture_copying_pycache_into_every_fixture.md`, whose name ends in `_fixture.md`). Neither imports a file this task changed.
- **Red proofs (post-phase `premise_advance_red_proofs`, scratch mirror via `SRC`/`SKILLS_SRC`, driver kept in the session scratchpad; control green in both suites):** failing assertions in the witnessing suite — premise suite: (a) no fingerprint compare 5, (b) write HEAD 6, (c) retired counted as checked 3, (d) no never_existed membership 2, (e) `## Check` writes postpone 1, (f) split advance write 1, (i) no identity check 6, (l1) no premise-review guard 2, (l2) verify path skips review 2, (m) replan advance without precondition 1, (n) no LOCK_REQUIRED branch 8, (o) unguarded recovery 2, (p) no ownership check 6, (q) LOCK_ERROR allows continue 4, (r) no session-anchor check 7, (s) anchor-less lock not unverifiable 2, (t) not_owner continues 2, (u) postpone without owner proof 1, (v) Approve-and-stop runs the stop sequence 2; expect-status suite: (g1) no under-lock sync 28 (the pre-existing-change case 3 still passes, so case 1 tests the window), (g2) no re-read 26, (h) exit-code sync check 8, (j) raw status compare 12, (k) no email gate 10. Every mutant scores 0 in the other suite. The pre-fix `aitask_pick_own.sh` fails all 19 assertions of expect-status cases 6–8.
- **Key decisions:** the advance and every post-lock write are applied only by a session whose ownership is proven (email + host + session anchor); `owner_unverifiable` refuses the optional baseline write but lets a user-chosen postpone/revert proceed with a warning; `not_owner` is terminal everywhere and undoes nothing. Postpone is never written pre-lock. Sync freshness is read from `TASK_SYNC_STATUS`, never the exit code.
- **Upstream defects identified:** None
- **Notes for sibling tasks:**
  - t1663_5 (website docs): the check is Step 3 **Check 7**; four options; Postpone ends with the `postponed` banner outcome; the evidence-class resolution table and the headless report-only rule are in the design record's "Interaction" section. `aitask_pick_own.sh --expect-status`, `advance` and `owner` are framework-internal (not user commands).
  - t1663_6 (retrospective): measure prompt rates per evidence class; `owner_unverifiable` (sessions outside tmux without `AIT_AGENT_PID`) and kept `never_existed` references are the two recurrence sources by design — count them separately.
  - t1655 (roadmap adoption): the core gained `retired` / `never_existed` (PATH_STATES/PATH_REASONS) and `all_retired` (SCOPE_REASONS); a roadmap adapter that never emits them is unaffected.
  - pickrem/pickweb run their own Step 3 and do not get the check — a follow-up if wanted.
