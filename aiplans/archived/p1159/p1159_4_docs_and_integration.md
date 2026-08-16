---
Task: t1159_4_docs_and_integration.md
Parent Task: aitasks/t1159_shadow_review_loop_automation.md
Sibling Tasks: aitasks/t1159/t1159_5_*.md, aitasks/t1159/t1159_6_*.md, aitasks/t1159/t1159_7_*.md
Archived Sibling Plans: aiplans/archived/p1159/p1159_*_*.md
Worktree: . (current directory — profile 'fast', current branch)
Branch: main
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-16 18:57
---

# Plan — t1159_4: Docs and integration sweep

Parent design: `aiplans/p1159_shadow_review_loop_automation.md`. Depends on
t1159_2 and t1159_3, both landed. **Document the landed source, not the plans.**

## Context

t1159_1..3 shipped the shadow review-loop automation: the `Round: <N> @ <ts>`
header inside the concern fences, minimonitor's `L` auto-recheck loop, and the
picker's `t` spin-off arm. **t1509 then landed on top**, adding Codex shadow
readiness, the settle latch and two-rung agent resolution — so t1159_2 must not
be documented as-planned. This child consolidates user-facing and framework docs
for all of it and resolves the cross-agent porting question.

## Verification findings (2026-08-16)

Re-verified against landed source before implementation. Six assumptions moved.

1. **`shadow_agent.md` already has the section.** `## Review-loop automation
   (auto-recheck)` exists at `aidocs/framework/shadow_agent.md:504`, seeded by
   t1159_2 and extended by t1509. Its safety contract is **10 numbered points
   plus an inserted `5b`**, not the parent plan's 8 — p1159_2's own notes call it
   "the 10-item safety contract". **Decision: do not reproduce the parent plan's
   8 points.** That would regress a correct document. The task's 8-point
   instruction is superseded.
2. **Placement differs from the task text.** The section sits *after* "Concern
   rejection store", not between it and "Feedback freshness". **Decision: keep
   the landed placement** — the loop consumes the rejection store, so it reads
   correctly after it, and moving ~135 lines buys the reader nothing.
3. **Pane-option claim VERIFIED.** Exactly three `@aitask_shadow_*` options exist
   repo-wide (`target`, `analyzed_at`, `phase`); none of the three landed commits
   adds a `set-option` site. Loop state is in-process on the app instance. There
   is also **no pane-option family *table*** to leave untouched — the family is
   documented as prose plus one bullet at `:665-670`.
4. **The followed-agent gate is not `live_tiers_available`.** Arming calls
   `review_loop.review_loop_agent_supported`; `REVIEW_LOOP_AGENTS = ("claude",)`.
   The code and `shadow_agent.md:766-772` both state why: since t1467
   `live_tiers_available` is true for Codex/OpenCode, but this loop *injects*, so
   it stays Claude-only until each agent earns it with live evidence. The task's
   "t1467 prompt detection" framing is stale.
5. **t1159_3 shipped zero documentation.** Four published surfaces are now
   factually **wrong**, stating concerns carry two or three mutually exclusive
   dispositions. There are four (`☐` / `☑` / `✗` / `»`). Not called out in the
   original plan; it is the highest-value fix in the task.
6. **The stale rejection-store paragraph** (in `## Concern rejection store`) says
   `ConcernPickResult` carries `forwarded` / `rejected` / `unrejected` and that
   the store is written only via `--producer picker`. It now has four fields
   including `spun_off`, and `spinoff` is a second producer.
7. **HEAD advanced mid-session: t1520 ("Add OpenCode shadow readiness detection",
   `a43c66313`) landed after t1509.** This invalidated an earlier read of this
   plan's own source. `SHADOW_READY_DETECTORS` now ships **`claude`, `codex` and
   `opencode`** — every configured shadow agent has a detector, and
   `test_opencode_shadow_of_a_claude_pane_now_arms` pins that an OpenCode shadow
   of a Claude pane arms. t1520 also updated `shadow_agent.md` itself, which is
   therefore **current** on the matrix and needs no fix there. Two consequences:
   the capability prose in step 3a must not deny OpenCode as a shadow, and
   **`shadow_agent.md` line numbers cited anywhere are unreliable** — this plan
   addresses its edits by heading and quoted text, never by line number.

Cross-agent porting is **definitively a no-op** — resolved in step 4.

**Re-verify before editing.** HEAD moved once during planning; re-read each
target's current text (not this plan's quotations) before changing it.

## Steps

### 1. `aidocs/framework/shadow_agent.md`

The controller, safety contract, settle latch, bounded-capture residual and
pattern-location prose are landed and correct. Leave them alone except:

- **Correct the stale rejection-store paragraph** (in `## Concern rejection
  store`, the sentence beginning "The store is touched only when the *picker* is
  confirmed"): name all four `ConcernPickResult` fields and both producers
  (`picker`, `spinoff`). Keep the existing note that the shadow's consult is
  deliberately **producer-blind**.
- **Soften the safety-contract preamble** ("the module docstring carries the same
  items"): the docstring carries five of them as "Contract highlights". Say that.
- **Add `### The round header`** under the review-loop section: the
  `Round: <N> @ <timestamp>` grammar, the metadata-only clean-round block, the
  strict `is_metadata_only_block` certification, and the three consumer roles
  (display; the auto-offer dedup lift; the `(round, reviewed_at)` freshness key —
  the **pair**, never the round alone, since a restarted shadow counts from 1).
  Point at `concern-format.md` as the owning spec rather than restating it, and
  fix the weak cross-link at `:381`, which names the header with no reference.
- **Add `### Spin-off triage arm`** — absent from all of `aidocs/` today. Cover:
  the fourth picker disposition `»` (no dimming — the concern is kept, just
  elsewhere); per-concern draft creation via `aitask_create.sh --batch --silent
  --name <name> --desc-file - --priority <p> --labels shadow-concern
  --followup-of <task_id> --followup-kind review_finding`, **no `--commit`**, body
  on stdin; the collision-safe `shadow_<region>_<nonce>_<index>` naming and why a
  per-batch nonce is required; drafts in `aitasks/new/` reported by **path**
  (drafts have no id until `ait create` finalizes them) with
  `ls aitasks/new/*<nonce>*` as the batch selector; and the loop hygiene — one
  batched `aitask_shadow_rejected.sh add <task_id> --producer spinoff` so the
  now-tracked concern is suppressed next round, reusing the t1427 store. Include
  the created-but-NOT-suppressed state and why it has its own wording, and the
  accepted **single-process** duplicate-guard limitation (two TUIs bound to one
  task can each create a draft; cost is one extra unfinalized draft).
- **Note the armed-state consequence** of in-process state: the loop does not
  survive a minimonitor restart and is invisible to other processes — which is
  why the contract makes it "opt-in, permanently visible" via the banner. Also
  note it costs one extra small raw `capture-pane -e` read per tick, **only while
  armed**.

### 2. `.claude/skills/aitask-shadow/concern-format.md`

The "Round header" section (`:40-78`) is complete — grammar, placement hazard,
back-compat, metadata-only block, certification, three consumer roles, signature
note. t1159_1 did its job. Fix only:

- Say what consumers **do** with an uncertified round-headed block: warn and open
  the raw block view (`uncertified_round_block_msg`), because reporting "no
  concerns" would hide output the shadow did emit.
- Add the auto-recheck loop as a fourth consumer (the `+1` derivation feeding
  `compose_recheck_prompt`).
- `### Derived fields` (`:148`) and `## Rejected-concern suppression` (`:257`)
  both describe a three-state world — add the `spinoff` disposition and the
  `spinoff` producer.

### 3. Website — extend existing pages, add none

No new page ⇒ the **manual** `website/content/docs/workflows/_index.md` bullet
list is not touched.

Per `documentation_conventions.md`: current-state-only (no "you used to have to
type this by hand"), and **no task-id citations in website prose** — `t1159_2` /
`t1493` stay in `aidocs/` and plans. Literal identifiers (`L`, `t`,
`#mini-loop-status`, `Round: <N> @ <timestamp>`) stay verbatim and copy-safe.

**3a. `tuis/minimonitor/how-to.md`**
- Fix `:188` — "one of three dispositions" → four, adding `t` (`»`).
- New `### How to Run the Auto-Recheck Loop` after "How to Pick Shadow Concerns":
  what `L` arms, and the landed banner strings verbatim — `⟳ auto-recheck ARMED`,
  `⟳ waiting for shadow to settle`, `⟳ auto-recheck: delivering…`,
  `⟳ recheck #<N> sent — waiting for shadow`, banner cleared on disarm. Toasts:
  `Auto-recheck loop armed — press 'L' again to disarm` /
  `Auto-recheck loop disarmed` / `Auto-recheck loop disarmed: <reason>`. All six
  refusals, quoted: no followed agent pane; **Claude-only** (`the recheck loop is
  Claude-only for now`, naming the pane's current command); could not query the
  shadow pane; no shadow pane (`press 'e' to launch one`); could not resolve the
  shadow's agent yet (a *timing* answer — retry, not a verdict); shadow agent has
  no readiness detection yet.

  **The capability matrix has two independent axes — do not collapse them.** The
  page must say both, and must not deny a supported pairing:
  - **Followed pane: Claude only.** `REVIEW_LOOP_AGENTS = ("claude",)`. This is
    the gate that refuses arming with "the recheck loop is Claude-only for now".
  - **Shadow pane: every configured agent works.** `SHADOW_READY_DETECTORS`
    ships `claude`, `codex` **and `opencode`**, so a Claude followed pane can
    have a Claude, Codex **or OpenCode** shadow and the loop arms — the OpenCode
    pairing is pinned by `test_opencode_shadow_of_a_claude_pane_now_arms`. The
    "no readiness detection yet" refusal is therefore **not reachable by any
    shipped agent**; it is future-proofing for an agent added without a detector
    (its test drives a synthetic key deliberately). Do not name OpenCode — or
    any shipped agent — as unsupported on the shadow side.

  State plainly that minimonitor writes only into the **shadow** pane, never the
  followed one, and that concern forwarding stays clipboard-only. Mention the
  bounded-capture residual as why the manual recheck stays available.
- New `### How to Spin a Concern Off as Its Own Task`: `t`, drafts in
  `aitasks/new/`, finalize with `ait create`, the batch selector, and that a
  spun-off concern is suppressed next round.
- Key Bindings Quick Reference (`:285`): add an `L` row; add `t` to the `c` row's
  inline picker-key list. Source of truth for the key surface is
  `KEY_HINTS_TEXT`, whose parity with `BINDINGS` is test-pinned.
- `_index.md:78` mentions rejecting a concern and the auto-offer toast — add `t`
  and a pointer to the new loop section.

**3b. `tuis/monitor/how-to.md`** — the full monitor shares the picker, so `t`
works there too; the loop does **not** (minimonitor-only, do not document `L`).
- Fix `:198` — three→four dispositions, plus a spin-off paragraph mirroring 3a.
- Extend the "these keys belong to the picker, not to monitor" callout (`:206`),
  which currently names only `r`/`R`: monitor binds `t` at App level
  (scroll-to-tail), so the picker's `t` shadows it — exactly the situation that
  callout exists for.
- `:212` "Badge and auto-offer": add the `(round N)` toast suffix, and state that
  a **new round re-offers concerns you have already seen** — the dedup key is
  round-qualified, so a repeat round raising the same concerns is news, not
  noise. Extend its final sentence (currently only unparseable markers) with the
  uncertified-round-header case: such a block **warns and shows the raw block**
  rather than a false "no concerns" all-clear. Do **not** say it re-offers every
  tick — a *complete* uncertified block is still marked offered; only a streaming
  one stays unmarked.

**3c. `workflows/shadow-agent.md`**
- `:34` — "Ask the shadow to refetch whenever you want it to look at the latest
  output" is the page's manual-only framing and the highest-value single edit:
  add, positively phrased, that minimonitor can arm an auto-recheck loop with `L`
  that does this between rounds, with the manual ask always available.
- `:106` — "The two dispositions are mutually exclusive" → four, naming `t`.
- `:104` ("Every review round re-derives the shadow's findings from scratch") —
  tie in the round number: it is what makes rounds individually identifiable, and
  the freshness key is the `(round, reviewed_at)` **pair**, never the round alone.
- `:100` — the forwarding paragraph lists only `☐`/`☑`; add `✗` and `»`.

### 4. Cross-agent porting — resolved, spawn nothing

**Confirmed no-op.** `.agents/skills/aitask-shadow/` and
`.opencode/skills/aitask-shadow/` each hold exactly one ~1.1 KB dispatch
`SKILL.md` and nothing else — no producer files, no symlinks. The four producers
plus `concern-format.md` are authored once under `.claude/skills/aitask-shadow/`
and rendered per-agent into gitignored `*-/` artifact dirs by the render driver;
the t1159_1 round-header wording is already present in the codex and opencode
rendered trees with nobody having ported it. Per `skill_authoring_conventions.md`
("Before porting skill-wording fixes: check stub vs. full copy"), surface the
stale premise rather than fabricate edits. **Create no follow-up tasks**; record
the finding in the Final Implementation Notes.

Goldens: `concern-format.md` carries no Jinja and has no goldens — Test 1i in
`tests/test_skill_render_aitask_shadow.sh` asserts cross-profile/agent invariance
only, so no regeneration. No `.j2`, no stub surface, and **not** `impl-challenge.md`
(the one producer that does carry Jinja and would need goldens regenerated).

### Post-phase (risk mitigations)

- **docs_backreference_from_source** — add **one** comment line beside the
  spin-off block in `.aitask-scripts/monitor/monitor_shared.py`, pointing at
  `aidocs/framework/shadow_agent.md` → "Spin-off triage arm", in exactly the form
  `review_loop.py` already uses for the safety contract ("the full safety
  contract lives in `aidocs/framework/shadow_agent.md` → 'Review-loop
  automation'"). Scope limits, adopted from the plan review:
  - **Reference the stable canonical anchor only** — the aidocs file plus a
    heading name. Do **not** name website page paths in source comments: those
    move under Hugo restructuring and would create a second, unverified copy of
    navigation truth that no doc check covers.
  - **The reference must be verified, not asserted** — see Verification: each
    heading named in a source comment is grepped out of `shadow_agent.md`, so a
    later heading rename fails the check instead of rotting silently.
  - `review_loop.py` already carries its pointer and is **left unchanged**; the
    spin-off side is the only gap. Net effect: one comment line.

## Scope note

t1159_7 will refactor `review_loop.py` internals; t1159_6 will add an always-on
status line (a third banner, distinct from `#mini-shadow-stale` and
`#mini-loop-status`). This task therefore documents **stable user-facing
surfaces** — keys, banner strings, refusals, dispositions, the round header — and
does not re-describe controller internals beyond what t1159_2/t1509 already
wrote, minimizing what those siblings must rewrite.

## Verification

- `cd website && hugo build --gc --minify` succeeds (Hugo extended 0.164.0 is
  installed, so this runs for real — no skip note).
- `bash tests/test_skill_render_aitask_shadow.sh` passes after the
  `concern-format.md` edit.
- Every quoted banner / toast / refusal string is grepped back to its emitter in
  `minimonitor_app.py` / `monitor_shared.py` — no paraphrase presented as a quote.
- `grep -rniE "three (mutually exclusive )?dispositions|two dispositions" website/content/docs/`
  returns nothing; all four surfaces read four.
- `L` appears in the minimonitor Key Bindings Quick Reference; `t` appears in the
  `c` row and in monitor's picker-key callout.
- `grep -rniE "t1159|t1493|t1509|t1520" website/content/docs/` returns nothing (no
  task ids leaked into user-facing prose).
- **Capability matrix is not a denial.** The published pages state Claude-only on
  the *followed* axis and name `claude`, `codex` and `opencode` as working shadow
  agents. Cross-check the shadow list against the live registry rather than
  against this plan:
  ```bash
  python3 -c "import sys; sys.path.insert(0,'.aitask-scripts/monitor'); \
    import review_loop as r; print(sorted(r.SHADOW_READY_DETECTORS), r.REVIEW_LOOP_AGENTS)"
  ```
  Every key it prints must appear as supported on the shadow side; no shipped
  agent may be described as refused there.
- **Source-comment backlinks resolve.** Every heading named in a
  `monitor_shared.py` / `review_loop.py` doc pointer exists verbatim in
  `aidocs/framework/shadow_agent.md` — a heading rename must fail this:
  ```bash
  rc=0
  for h in '^## Review-loop automation' '^### Spin-off triage arm'; do
    grep -q "$h" aidocs/framework/shadow_agent.md \
      || { echo "BACKLINK_BROKEN: $h" >&2; rc=1; }
  done
  [ $rc -eq 0 ] && echo BACKLINKS_OK
  exit $rc
  ```
  **The failure branch must exit non-zero** — a trailing `|| echo BROKEN` prints
  a diagnostic and still exits 0, so any wrapper or CI step reads it as a pass
  while the comment points at a nonexistent section. Verified both ways before
  adoption: a missing heading exits 1, an existing one exits 0.
  No source comment names a `website/` path.
- Reference **Step 9 (Post-Implementation)** of the task-workflow skill for
  cleanup, archival, and merge.

## Risk

### Code-health risk: low
- Prose-only across `aidocs/` + website, plus a single comment line added in the
  post-phase; no executable behavior changes · severity: low · → mitigation: TBD
- Quoted banner/refusal strings can drift from their emitters as t1159_6/_7 land
  · severity: low · → mitigation: inline post-phase docs_backreference_from_source

### Goal-achievement risk: medium
- The task text prescribes an 8-point safety contract and a section placement the
  landed source has already superseded; following it literally would regress a
  correct document · severity: medium · → mitigation: TBD (recorded as an
  explicit, reviewable decision in "Verification findings" rather than silently
  deviating)
- Documenting surfaces that t1159_6's status line and t1159_7's refactor will
  move · severity: low · → mitigation: t1535

### Planned mitigations
- timing: post-phase | name: docs_backreference_from_source | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health (quoted strings drift from their emitters as t1159_6/_7 land) | desc: Add one comment line beside the spin-off block in monitor_shared.py pointing at the stable aidocs/framework/shadow_agent.md heading that documents it (no website paths; review_loop.py already has its pointer), with the named headings grep-verified so a rename fails the check
- timing: after | name: resweep_shadow_docs_after_status_line_and_refactor | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: high | addresses: goal-achievement (banner, keybinding and controller prose goes stale when t1159_6 adds the status line and t1159_7 refactors the loop) | desc: Re-sweep the shadow review-loop documentation once t1159_6 and t1159_7 land, refreshing banner strings, keybindings and controller prose against the then-current source. MUST NOT become eligible before both siblings land — see the Step 8d dependency wiring below | created: t1535

**Step 8d dependency wiring (required for the `after` mitigation).** Part 3 of
the Risk-Mitigation Follow-up Procedure creates "after" tasks with no `depends:`
of their own — it converges only the *original's* `risk_mitigation_tasks`. A
re-sweep created that way would be immediately eligible and would run **before**
either sibling lands, producing exactly the premature, misleading sweep it exists
to prevent. So immediately after Step 8d reports `Created risk-mitigation
follow-up t<new_id>`, wire the blocking edge explicitly:

```bash
# Resolve the EXACT file this run created — never a broad `add aitasks/`.
new_file=$(./.aitask-scripts/aitask_query_files.sh resolve <new_id> \
           | sed -n 's/^TASK_FILE://p')
[ -n "$new_file" ] || { echo "cannot resolve t<new_id> — do not commit"; exit 1; }

./.aitask-scripts/aitask_update.sh --batch <new_id> --deps 1159_6,1159_7
git -C . diff --stat -- "$new_file"          # inspect before staging
./ait git commit -o -m "ait: Gate t<new_id> on t1159_6 and t1159_7" -- "$new_file"
```

`-m` goes **before** `--`: everything after `--` is a pathspec, so the message
flag placed there fails with `pathspec '-m' did not match any file(s)` (verified).

**Path-scoped on purpose.** `./ait git add aitasks/` would sweep in any unrelated
task-data edits sitting in a shared dirty tree — this repo routinely has them —
and commit someone else's work under this task's message. Resolve the one file,
inspect its diff, and commit only that path with `-o --` so the index is never
consulted.

Then confirm it reads **Blocked** in `./.aitask-scripts/aitask_ls.sh -v`. If the
dependency cannot be wired, **delete the created task** rather than leaving an
ungated re-sweep in the queue.

## Final Implementation Notes

- **Actual work done:** All four planned steps landed, across seven files.
  `shadow_agent.md`: corrected the stale rejection-store paragraph (four
  `ConcernPickResult` fields, both producers, producer-blind consult), corrected
  the safety-contract preamble's claim that the module docstring carries the same
  items (it carries a five-item digest), added `### The round header` and
  `### Spin-off triage arm`, documented that loop state is in-process (no pane
  option, no restart survival, one extra tmux read per tick while armed), and
  fixed the weak round-header cross-link under "Block age vs read recency".
  `concern-format.md`: stated what consumers do with an *uncertified* round-headed
  block (warn + raw block view), widened "three consumer roles" to four (the loop
  derives its round as `previous.round + 1`), and noted that spun-off concerns
  land in the suppression store under `--producer spinoff` and must not be
  branched on. Website: fixed the disposition count on three pages, added
  "How to Run the Auto-Recheck Loop" and "How to Spin a Concern Off as Its Own
  Task" to the minimonitor how-to plus `L`/`t` in its keybinding table, added the
  spin-off paragraph and `t` key-shadowing note to the monitor how-to, extended
  both auto-offer callouts with the `(round N)` suffix / re-offer rationale /
  raw-block warning, and tied the round number to the re-derive-from-scratch
  sentence on the workflow page. Post-phase mitigation: one back-link comment in
  `monitor_shared.py._spawn_concern_tasks`.

- **Deviations from plan:** Two, both approved at plan time and re-stated here.
  (1) The task text asked for the parent plan's **8-point** safety contract
  reproduced verbatim; the landed contract is **10 points plus a `5b` settle
  latch** and was already correct in `shadow_agent.md`, so it was left alone —
  reproducing the older version would have regressed a correct document.
  (2) The task text asked for the section to sit between "Feedback freshness" and
  "Concern rejection store"; it landed *after* the rejection store and was kept
  there, since the loop consumes that store and reads correctly after it.
  One further deviation found during implementation: the plan (following an
  exploration report) listed `concern-format.md`'s `### Derived fields:
  disposition and verdict` as describing "a three-state world" needing the
  spin-off state added. That was a conflation — that section documents the
  *concern's own* `blocking`/`follow-up`/`informational` trailer, which is
  unrelated to the picker's row dispositions. It was correctly left unedited.

- **Issues encountered:**
  - **HEAD advanced twice mid-session.** t1520 ("Add OpenCode shadow readiness
    detection") landed after planning began and invalidated an early source read.
    The plan review caught the consequence: an earlier draft would have published
    "`opencode` as shadow is not supported", which is false — `SHADOW_READY_DETECTORS`
    ships `claude`, `codex` and `opencode`, and
    `test_opencode_shadow_of_a_claude_pane_now_arms` pins the pairing. The
    published matrix now separates the two axes: **followed** pane Claude-only
    (`REVIEW_LOOP_AGENTS`), **shadow** pane any supported agent. The
    "no readiness detection yet" refusal is documented as a state message, not as
    naming any shipped agent, because no shipped agent reaches it.
  - **A `grep`-based string round-trip produced a false negative**: the
    Claude-only refusal is split across two adjacent Python string literals, so no
    line-oriented match can see it. Re-verified by folding the concatenation in
    Python — all quoted strings are verbatim.
  - Two `Edit` calls failed on exact-match despite visually identical text
    (invisible-character mismatch in `concern-format.md`); split into smaller
    anchors.

- **Key decisions:**
  - **Documented stable user-facing surfaces, not controller internals.**
    t1159_7 will refactor `review_loop.py` and t1159_6 will add an always-on
    status line, so keys, banner strings, refusals, dispositions and the round
    header are what this task pinned; the internals `shadow_agent.md` already
    described were left untouched.
  - **The `after` mitigation must be gated.** Part 3 creates "after" tasks with no
    `depends:`, so the re-sweep would be eligible before either sibling lands. The
    plan carries an explicit Step 8d wiring step (`--deps 1159_6,1159_7`), a
    path-scoped commit, and a "delete it rather than leave it ungated" fallback.
  - **Back-links reference a stable anchor only** — the aidocs file plus a heading
    name, never a `website/` path (those move under Hugo restructuring), and the
    named headings are grep-verified with a check that **exits non-zero** on a
    miss, since a trailing `|| echo BROKEN` would report success.

- **Upstream defects identified:** None.

- **Notes for sibling tasks:**
  - **t1159_6 (status line):** the minimonitor how-to now documents the four loop
    banner states verbatim in a table
    (`### How to Run the Auto-Recheck Loop`). A third always-on widget will need
    that table revisited, and the `_index.md` loop paragraph with it.
  - **t1159_7 (loop refactor):** `shadow_agent.md` → "Review-loop automation" is
    the contract of record (10 points + `5b`), and its preamble now says the
    module docstring is a five-item digest — keep that true if the docstring is
    reshaped. `monitor_shared.py._spawn_concern_tasks` now carries a doc back-link
    to "Spin-off triage arm"; the same heading is asserted by this task's
    verification, so renaming it requires updating the comment.
  - **Cross-agent porting is a confirmed no-op** and no follow-up tasks were
    created. `.agents/skills/aitask-shadow/` and `.opencode/skills/aitask-shadow/`
    hold one ~1.1 KB dispatch stub each and no producer files; the four producers
    plus `concern-format.md` are authored once in the Claude tree and rendered
    per-agent into gitignored `*-/` dirs, so the round-header wording already
    reached both without a port. Editing `concern-format.md` needed no goldens
    regenerated (no Jinja; Test 1i asserts invariance) — only `impl-challenge.md`
    among the producers carries Jinja and would.
