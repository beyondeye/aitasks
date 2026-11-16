---
Task: t2299_4_sitrep_recovery_skill_and_docs.md
Parent Task: aitasks/t2299_sitrep_track_crashed_agents_for_resume.md
Sibling Tasks: aitasks/t2299/t2299_1_*.md, aitasks/t2299/t2299_2_*.md, aitasks/t2299/t2299_3_*.md
Archived Sibling Plans: aiplans/archived/p2299/p2299_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-11-16 15:30
---

# Plan: sitrep skill and docs for recovery items (t2299_4)

## Context

The first three children shipped crash recovery in sitrep (commits for t2299_1..3):
the `recover:t<N>` ref and `recovery-apply` writer verb (format 3), the
`aitask_sitrep_harvest.sh crashed` detector (`lib/sitrep_crash.py`), and the
refresh / monitor tick / TUI wiring. This last child teaches `/aitask-sitrep` to
triage recovery items and documents the feature, in current-state wording,
describing **what shipped** (siblings' Final Implementation Notes + the t2299_3
note acknowledged at pick time), not the original task tables.

## Verification of the earlier plan (2026-11-16)

Re-checked against the tree at `9a7048011`:

- **crash-recovery.md no longer carries t2284's foreign hunk** — t2284 landed it in
  `7a68196d0`, and `git status` shows the file clean. The hunk-scoped staging step
  is reduced to a guard: re-check `git status --short` on the file right before
  editing; only if a foreign hunk reappeared, fall back to the `git apply --cached`
  procedure. Never restore / stash.
- **The skill must not name `aitask_sitrep_harvest.sh` or `aitask_sitrep_refresh.sh`**
  (`tests/test_sitrep_skill_contract.sh:229-230` asserts their absence). The skill
  refers to "the crash detector" and "refresh", run by the TUI's `r` and the monitor
  tick — never by path.
- Contract check `d`: any paragraph naming `git push` / `git commit` / `send-keys` /
  `aitask_pick_own.sh` must contain "never". New guardrail prose is written as
  prohibitions. Any new `./.aitask-scripts/<helper>` named would need allow-list
  entries — none is added (`ait lock --unlock <N>` and `/aitask-pick <N>` are named,
  not paths).
- `AGENT_REQUESTS` did not change in t2299_3 (`sitrep_tui_requests.py` not in its
  diff) → no request-parity change.
- What shipped that the docs must reflect (vs. the task text):
  - recovery item: `kind=task`, `ref=recover:t<N>`, outcome `<category> · <evidence>`
    (`format_outcome`); categories stored: `crashed`, `orphan`, `stale_lock`
    (the TUI also falls back to generic recover text for an unknown label).
  - Group: crashed rank 1-2 → `now`, rank 3-4 → `next`; orphan → `next`;
    stale_lock → `waiting` (`Pass.group_of`). Ranks (`rank_of`): 1 approved plan +
    implementing/post_impl + signature not stale + `plan_fresh: fresh` + surviving
    work; 2 other approved; 3 draft; 4 none. The rank itself is not stored — the
    title (`Recover t<N> <slug> (<category>): <phase>, <plan> plan (<fresh>), <n> files[, overlaps …]`)
    and the survey passage carry its inputs.
  - Survey passage `SITREP_RECOVERY_SURVEY v1` (a retained `capture:` source):
    task, category, incarnation, lock, lock_age bucket, phase, phase_provenance,
    pending_gates, plan, plan_signature, plan_fresh, worktree,
    uncommitted_files (attributed/unattributed), attributed/overlap lines, commits,
    warning (three forms: surviving work / unattributed shared-tree edits /
    incomplete evidence). Optional pane-tail capture.
  - Decision table: 9 ordered rows; row 1 (unreadable input) never writes;
    other host / unknown liveness are never items (skip, existing item → unknown);
    alive → existing item done; rows 3/9 done.
  - Refresh: kind `recovery`, result words `unchanged` / `unverified`,
    `REFRESH_WARN:unverified|…`, `REFRESH_WARN:attempts_unwritable|…`, written only
    on change (`checked_at` = evidence last changed), attempt ledger at
    `<git common dir>/aitask-sitrep/refresh_attempts.json`.
  - Monitor tick and TUI `r`: harvest all → crashed → refresh (each step runs even
    if the previous failed; three verdict lines; partial refresh toasts a warning).
  - TUI `p` only for crashed and orphan recovery items; stale_lock shows
    `ait lock --unlock <N>` (never run).
  - Dismissal: `recovery-apply` keeps a dismissed item (`KEPT:`) unless a
    **different incarnation** reopens it with `--state open` and its context —
    i.e. a new claim that crashes again.
  - `crashed` is not exposed through `ait sitrep` (only the harvest script), so the
    user-facing reference documents the TUI's recovery verdict line, and the wire
    lines go in `aidocs/framework/sitrep.md`.
- Also in scope (missed by the task's file list): `website/content/docs/skills/aitask-sitrep.md`,
  the skill's reference page, which lists `>p` and the never-does list.

## Plan-review concerns (2026-11-16, both verified and addressed)

1. **Recovery theme.** Verified: `Pass.context_entry` writes no `theme:`, and
   `item_theme` returns `""` for recovery items, so the TUI's `w` is unavailable on
   them and the skill's `>w <theme>` check would refuse `crashed-agents` on a fresh
   store. Fixed in step 1 by making `crashed-agents` a **virtual theme**, derived
   from `recover:` refs, with a matching check exception. The detector keeps
   ownership of recovery contexts. TUI `w` stays unavailable on recovery items, and
   that is documented. Making `w` work there would need TUI routing (a code change);
   it is offered as a follow-up at Step 8b/8e, not done here.
2. **Recovery timestamp.** Verified: the detector and refresh write `checked_at`
   only on change, so the `>q` one-hour rule would always flag a quiet recovery
   item. Fixed in step 1 (`>q`) and in the website wording (workflow step 3,
   how-to and reference `Checked`): for recovery items it is the evidence age, not
   the scan age. No new timestamp mechanism.

## Steps

1. **Skill** — `.claude/skills/aitask-sitrep/SKILL.md.j2` (Capabilities stays the
   single source of the menu; no new shortcode):
   - **The list:** a paragraph on recovery items — `kind=task` with
     `ref=recover:t<N>`; the outcome's leading token is the category
     (`crashed` / `orphan` / `stale_lock`), the rest is evidence; the title carries
     phase, plan state/freshness, attributed files and overlaps. Their context has a
     `capture:` survey passage (header `SITREP_RECOVERY_SURVEY v1`), read like any
     capture. Unknown liveness and other-host locks are never items; a dismissed
     one stays dismissed for that claim attempt and reopens only when the task is
     claimed again and crashes again.
   - **Writing:** recovery items are written only by the crash detector and refresh
     (`recovery-apply` is not an agent verb): never `add` a `recover:` ref (the
     writer refuses it), never `set-state`, `upsert-context` or reopen one. The agent
     only names them in situation text, `qa` and answers.
   - **`>w` — `crashed-agents` is a virtual theme.** The detector writes recovery
     contexts with no `theme:` (`Pass.context_entry`, `lib/sitrep_crash.py`), and
     they stay detector-owned: the agent never adds one with `upsert-context`.
     Instead, `crashed-agents` is the theme of every `recover:` item by definition:
     - it **needs text** while `list` shows any open or unknown `recover:` item; a
       bare `>w` includes it, and `>w crashed-agents` writes it;
     - when no open/unknown `recover:` item remains, `>w` removes its block (empty
       input);
     - the text summarises per category, with ids (crashed → resume, orphans,
       stale locks → clean up), naming overlaps.
   - **Requests from the sitrep TUI, `>w <theme>` check:** add the exception —
     `crashed-agents` is also valid when the fresh `list` shows a `recover:` item
     (any state), even with no context naming it and no block yet.
     **TUI `w` stays unavailable on recovery items** (`sitrep_tui_requests.item_theme`
     reads only the context theme, which recovery items lack). No TUI routing is
     added in this documentation task; the user types `>w` or `>w crashed-agents`.
     Stated in the skill, the aidocs TUI section and the TUI reference.
   - **`>q` — recovery `checked_at` is evidence age, not scan age.** For a
     `recover:` item, `checked_at` is when its evidence last changed (the detector
     and refresh write only on change). An old value is not by itself a stale or
     failed check: do not apply the one-hour "suggest Refresh" rule to it, and do
     not infer a verification failure from it. Say "evidence unchanged since
     <age>"; suggest `r` only when the user wants a current reading or the item
     is `unknown`.
   - **`>p`:** before the roadmap relation, when recovery items are open, advise a
     resume order from the survey (rank order 1→4 as listed above; for post_impl,
     say what remains — review, procedure gates, archive — from `pending_gates`).
     Keep "Never rank tasks yourself": the resume order is the detector's evidence,
     not the agent's ranking; the agent names `/aitask-pick <N>` for the user.
   - **Cleanup:** flag stale locks (`ait lock --unlock <N>`, after the user checks
     the holder) and orphans (`/aitask-pick <N>` to resume, or the board) for the
     user to run.
   - **Guardrail:** never reclaim, unlock or pick; never suggest `git restore` /
     `git stash` / checkout on a tree whose survey warns of surviving work (any of
     the three warning forms), and call out overlaps between tasks.
   - **Requests from the sitrep TUI:** unchanged lines; `>q c<N>` on a recovery item
     reads its survey first.
2. **Goldens:** regenerate `tests/golden/skills/aitask-sitrep/SKILL-{default,fast,remote}-claude.md`
   with the loop in `aidocs/framework/skill_authoring_conventions.md`; review the
   diff equals the template edit. Also rerender the committed
   `.claude/skills/aitask-sitrep/SKILL.md` if the render test requires it.
   Run `./.aitask-scripts/aitask_skill_verify.sh`,
   `bash tests/test_skill_render_aitask_sitrep.sh`,
   `bash tests/test_sitrep_skill_contract.sh`.
3. **`aidocs/framework/sitrep.md`:**
   - Components: a `crash detector` row (`aitask_sitrep_harvest.sh crashed` →
     `lib/sitrep_crash.py`); the refresh row covers recovery items; maintenance
     sentence → harvest → crashed → refresh (`_maybe_detect_sitrep_crashes`).
   - New section **Crash recovery items**: the `recover:` ref and format 3, the
     one-writer rule (`recovery-apply`, two-key incarnation rule, `KEPT:` for
     dismissed, reopen only by a different incarnation = the dismissal exception),
     the episode key, a summary of the 9-row table pointing to `lib/sitrep_crash.py`
     (row 1 never writes; unknown never rounded up; host guard first), survey and
     evidence (pointer to header), ranks and groups, idempotence (`checked_at` =
     evidence last changed), the wire lines (`CRASH_ITEM` / `CRASH_SKIP` /
     `CRASH_WARN` / finals), and the refresh `recovery` class (result words, warns,
     attempt ledger).
   - TUI: `r` three steps and partial verdict; `classify` → `recover` with
     `RECOVER_STEPS`; pick only `RECOVER_PICKABLE`; stale-lock command shown only;
     `w` unavailable on recovery items (no context theme) — the `crashed-agents`
     virtual theme is the skill's, typed as `>w`.
   - Recovery `checked_at` = evidence last changed; scan recency lives in the
     detector's final line and the refresh attempt ledger, not on the item.
   - The skill section: recovery bullets matching step 1.
   - Tests table: `tests/test_sitrep_crash.py`, `tests/test_sitrep_crash.sh`; refresh
     row names Tests 15/16 and `CrashDetectJobTests`; TUI rows name
     `CrashDetectorStepTests`, `RecoverPickTests`, `test_recovery_guidance_per_category`.
4. **Website** (read `aitasks/metadata/doc_update_guide.md` and
   `aidocs/framework/documentation_conventions.md` first; current-state only):
   - `workflows/sitrep.md` (intermediate): new `## Crashed agents` section (what is
     detected, the three categories, where they land in the list, resuming with
     `p` → `/aitask-pick` crash recovery, cleanup of stale locks and orphans, never
     restore/stash a tree with surviving work, dismissal and its reopen exception);
     amend step 6's "A dismissed item stays dismissed" sentence; step 2 mentions the
     crash check in the startup run; step 3's "how long ago that was" gets the
     recovery distinction (a crash-recovery item shows when its evidence last
     changed, not when it was last checked). The Crashed agents section says the
     situation text is under `crashed-agents`, written with `>w` (the TUI's `w`
     does not apply to recovery items).
   - `tuis/sitrep/reference.md` (advanced): "What to do" rows for the recovery
     categories; `p` "Shown when" covers crashed/orphan recovery items; the
     collect-and-re-check panel's three lines incl. `Recovery: …` verdicts and the
     partial-refresh suffixes; Timing mentions the crash check in the monitor pass;
     the `Checked` column row and the `w` key row note the recovery-item exceptions
     (evidence age; `w` not shown for recovery items).
   - `tuis/sitrep/how-to.md` (intermediate): `### How to Resume Crashed Work`; the
     `r` how-to mentions the crash check; `p` bullet covers recovery items; the
     **Checked** column bullet gets the recovery distinction.
   - `skills/aitask-sitrep.md`: recovery items in the description, `>p` resume order,
     never-does additions (reclaim/unlock, restore/stash advice).
   - `workflows/crash-recovery.md`: a Tip / See-also cross-link "find every crashed
     task at once" → `{{< relref "/docs/workflows/sitrep" >}}#crashed-agents`
     (guard: `git status --short` on the file before editing, per Verification above).
   - Use `{{< relref >}}` for every new link.
5. **Link checks:** `cd website && python3 check_links.py --build` (mandatory); offer
   `check_link_relevance.py`.
6. **Note to t2199** (codex/opencode port of the sitrep skill):
   `./ait note 2199 --from 2299_4 --file -` naming the skill sections added (list
   paragraph, writing rule, `>w` theme, `>p` resume order, cleanup, guardrail).
7. **Doc review:** read each changed page as a fresh reader against its depth contract.

### Post-phase (risk mitigations)

- **claim_audit** — after the docs are written, list every concrete claim the new
  text makes (identifiers, result words, file paths, key names, category names,
  group placement, wording quoted from the TUI) and grep each in the shipped code
  (`lib/sitrep_crash.py`, `lib/sitrep_refresh.py`, `sitrep_tui_model.py`,
  `sitrep_tui_actions.py`, `monitor_shared.py`, the helper headers); fix any claim
  without a match. Record the audit table in the Final Implementation Notes.

Step 9 (Post-Implementation): commit the code/docs paths only —
`documentation: Document sitrep crash recovery and teach the skill recovery items (t2299_4)`
— the plan via `./.aitask-scripts/aitask_task_commit.sh`, then archive.

## Verification

- `./.aitask-scripts/aitask_skill_verify.sh`
- `bash tests/test_skill_render_aitask_sitrep.sh`
- `bash tests/test_sitrep_skill_contract.sh`
- `cd website && python3 check_links.py --build` clean
- `git diff --stat` shows only this task's paths; `crash-recovery.md` diff holds only
  the cross-link.
- claim_audit table: every claim has a code match.
- The `>w` check and the `>q` age rule in the rendered skill name the two recovery
  exceptions (virtual `crashed-agents` theme; evidence age).

## Risk

### Code-health risk: low
- Skill prose could trip the contract test (a writing action outside a "never"
  paragraph, or naming the harvest/refresh scripts) or leave stale goldens ·
  severity: low · → mitigation: none needed beyond Verification (the contract and
  render tests catch both)
- A concurrent session re-dirtying `crash-recovery.md` or another doc page before
  the commit · severity: low · → mitigation: path-scoped commit plus the
  `git status` guard in step 4

### Goal-achievement risk: low
- Docs describing the planned design rather than what shipped (e.g. the task's
  "rows 2/4 → unknown" table, a stored rank, a `crashed` CLI verb under
  `ait sitrep`) · severity: medium · → mitigation: inline post-phase claim_audit

### Planned mitigations
- timing: post-phase · name: claim_audit · inline_risk: low · added_complexity: low · addresses: docs describe the plan rather than what shipped

## Post-Review Changes

### Change Request 1 (2026-11-16 14:05)
- **Requested by user:** four verified review concerns: (1) "unknown liveness / other-host lock is never an item" ignored that rows 2/4 move an EXISTING item to `unknown` (outcome `other_host · …` / `unknown · …`), keeping its old title and survey; (2) the stale_lock definition presented a missing PID anchor or a non-Implementing status as proof that no live session holds the lock; (3) aidocs said refresh writes through `recovery-apply`, but it uses `set-state --batch`; (4) the how-to `x` bullet still promised that a dismissed item never comes back.
- **Changes made:**
  - The skill now separates creating an item from moving an existing one, reports `unknown` recovery items as unverified (never in the >p order, survey read as history, check the holder), defines stale_lock by its actual conditions ("check who holds it, never proof that nobody does"), and names both write paths.
  - aidocs gains the two-writer paragraph (detector `recovery-apply`, refresh `set-state --batch`), a corrected table summary, and a "Creation vs. an existing item" paragraph.
  - The workflow page has the stale-lock and unknown-item wording.
  - The how-to has the `x` exception and the unknown-item note.
  - The reference has the unknown-item note.
  - Goldens regenerated, and a correction note sent to t2199.
- **Files affected:** `.claude/skills/aitask-sitrep/SKILL.md.j2`, `tests/golden/skills/aitask-sitrep/*`, `aidocs/framework/sitrep.md`, `website/content/docs/workflows/sitrep.md`, `website/content/docs/tuis/sitrep/how-to.md`, `website/content/docs/tuis/sitrep/reference.md`

## Final Implementation Notes
- **Actual work done:**
  - Skill (`.claude/skills/aitask-sitrep/SKILL.md.j2`):
    - "The list": a crash-recovery paragraph (ref, categories, title, survey passage, `checked_at` = evidence age, creation vs. existing-item `unknown` transitions);
    - "Writing": a detector/refresh ownership rule naming both write paths, plus the dismissal/reopen rule;
    - the `crashed-agents` virtual theme in `>w`, with a matching exception in the TUI-request `>w` check;
    - the `>q` evidence-age exception;
    - the `>p` resume-order tiers, `post_impl` pending gates and cleanup commands;
    - guardrail additions;
    - the greeting count;
    - the crash check named as the TUI's.
  - Goldens regenerated for all three profiles; the diff is identical to the template's.
  - `aidocs/framework/sitrep.md`:
    - a components row and the maintenance order;
    - a new "Crash recovery items" section: item, writers, episodes and dismissal, decision table, creation vs. existing item, survey, rank and group, idempotence, wire lines, refresh class;
    - the TUI `r` / pick / What-to-do / `w` notes;
    - the monitor maintenance order;
    - the skill bullet;
    - test-table rows.
  - Website:
    - `workflows/sitrep.md`: a "Crashed agents" section, with steps 2, 3, 5 and 6 amended;
    - `tuis/sitrep/how-to.md`: "How to Resume Crashed Work", plus the Checked / `r` / `p` / `x` wording;
    - `tuis/sitrep/reference.md`: the key rows, the Checked column, recovery What-to-do rows, the unknown-item note, the three-line result panel and Timing;
    - `skills/aitask-sitrep.md`;
    - `workflows/crash-recovery.md`: a Tip and a See-also cross-link.
- **Deviations from plan:**
  - The hunk-scoped staging of `crash-recovery.md` was not needed: t2284 committed its hunk (`7a68196d0`) before this task started, and the file was clean when re-checked before editing.
  - `skills/aitask-sitrep.md` was added to scope; the task's file list missed it.
  - The user's plan review added the `crashed-agents` virtual theme and the evidence-age rule.
  - The code review added four corrections (Post-Review Changes CR1).
- **Issues encountered:**
  - `tests/test_sitrep_skill_contract.sh` forbids naming `aitask_sitrep_harvest.sh` / `aitask_sitrep_refresh.sh` in the skill, so the skill says "the crash detector" / "refresh".
  - Every prohibition paragraph keeps a "Never".
- **Key decisions:**
  - `crashed-agents` is a virtual theme, derived from `recover:` refs; recovery contexts stay detector-owned.
  - The TUI's `w` stays unavailable on recovery items, documented rather than changed (a code change, out of scope).
  - The user-facing reference documents the TUI's `Recovery:` verdict and detail lines, not the `CRASH_*` wire lines: `crashed` is not exposed through `ait sitrep`, so the wire lines live in aidocs.
- **claim_audit (post-phase):** 32 concrete claims grepped against the shipped code. All OK:
  - `SITREP_RECOVERY_SURVEY v1`, `recover:t<N>[_<M>]`, `dismissed_no_incarnation`, `RECOVER_FORMAT`;
  - survey keys: `pending_gates`, `plan_signature`, `branch_head`, lock-age buckets;
  - `CRASH_NONE:nothing_inflight`, `kept_dismissed`, `other_host:<host>`;
  - every `Recovery:` verdict string, `recovery warning:`, `not verified` / `not reached`;
  - `ait lock --unlock {pick_id}`, `RECOVER_PICKABLE`, `recover_category`;
  - `recovery_refresh_verdict`, `refresh_attempts.json`, `attempts_unwritable`, `ATTEMPT_MAX_AGE_DAYS = 7`;
  - `HARVEST_CRASHED_TIMEOUT = 120`, `_sitrep_store_roots` (the monitor checks only roots that have a store), `MAX_COMMIT_SOURCES = 5`;
  - the title format and the stale-signature rule;
  - `refs/remotes/origin/aitask-locks`;
  - the test names `CrashDetectJobTests`, `CrashDetectorStepTests`, `RecoverPickTests`, `test_recovery_guidance_per_category` and Tests 15/16.

  Behavioural claims were checked against `recovery_verdict`, `Pass.rank_of` / `group_of` / `state_only`, `recovery_refresh_verdict`, `run_writer` (`set-state --batch`) and `_harvest_refresh`. Review CR1 caught three behavioural overstatements that the grep audit had not (the unknown transition, the stale-lock conditions, refresh's write path).
- **Verification:**
  - `aitask_skill_verify.sh`: OK.
  - `test_skill_render_aitask_sitrep.sh`: 126/126.
  - `test_sitrep_skill_contract.sh`: 70/70.
  - `check_links.py --build`: PASSED (0 broken).
- **Upstream defects identified:**
  - `.aitask-scripts/lib/sitrep_crash.py:138-139 — BACKGROUND["stale_lock"] says "no live session holds" the lock, but row 5 (no PID anchor) never proves the holder dead; the stored background over-claims for unanchored locks`
- **Notes for sibling tasks:**
  - t2199 (codex/opencode port) received two notes: `2026-11-16T13:37:20Z.fc390967…` with the sections to port, and `2026-11-16T13:51:55Z.56b01116…` with the CR1 corrections.
  - A possible follow-up: TUI routing so that `w` on a recovery item types `>w crashed-agents`.
