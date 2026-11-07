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
