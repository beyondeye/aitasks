---
Task: t1560_3_document_merge_mutex_and_audit_merge_paths.md
Parent Task: aitasks/t1560_serialize_step9_merge_across_concurrent_tasks.md
Sibling Tasks: aitasks/t1560/t1560_4_manual_verification_serialize_step9_merge.md
Archived Sibling Plans: aiplans/archived/p1560/p1560_1_merge_mutex_and_broker_script.md, aiplans/archived/p1560/p1560_2_wire_step9_across_rendered_surfaces.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-24 22:52
---

# t1560_3 — Document the merge mutex, audit the other merge paths

## Context

Sibling **t1560_1** shipped the merge broker (`.aitask-scripts/aitask_merge_task.sh`)
and its session-anchored mutex; **t1560_2** wired it into Step 9 across every
rendered surface. Neither published anything user-facing, and neither checked the
*other* merge paths in the tree. This task closes both gaps.

Two website pages are the surface. `concepts/locks.md` documents only the task
lock — its "what the lock actually excludes" table is accurate today only because
merging was unprotected. `workflows/parallel-development.md:20` describes the
merge-back in one sentence with no serialization caveat. A third loose end:
`merge-broker.md:607` says force-release's verdicts "are documented with the lock
model rather than rendered here" — a forward reference to `locks.md` that
currently lands nowhere.

Intended outcome: a user who hits a queued merge, a `NO_SESSION_ANCHOR` refusal,
or a wedged lock can resolve it from the published docs alone; and every merge
path in the tree has a recorded disposition.

## Verification outcome (this pass)

The plan's approach is sound. Five corrections from checking it against the
shipped code:

1. **No port follow-ups are needed.** The plan says a web-merge fix would need
   separate aitasks to port to Codex / OpenCode. Both ports
   (`.agents/skills/aitask-web-merge/`, `.opencode/skills/aitask-web-merge/`) are
   thin "Source of Truth" pointer wrappers carrying no merge code, so a fix to the
   Claude file propagates with no regeneration. That clause is vacuous — drop it.
2. **web-merge cannot adopt the broker as-is.** `begin` runs a plain
   `git merge "$task_branch"` (`aitask_merge_task.sh:207`) which *creates* the
   commit; web-merge needs `--no-ff --no-commit` so it can strip
   `.aitask-data-updated/` before committing, and its source is a remote
   `origin/<branch>`, not a local `aitask/<name>`. There is no acquire-only verb.
   Wiring it requires extending the broker — forbidden by this task's non-goals.
   **User decision: document the hazard honestly and file a follow-up.**
3. **A third, independent web-merge defect.** It never asserts HEAD (zero
   `git checkout` tokens in the file) and assumes `main`. Since Step 9 leaves the
   shared root on `$output_branch`, a later web-merge would pull, merge and
   `git push` *that* branch. The broker guards this with
   `PREFLIGHT_HEAD_MISMATCH`; web-merge has no equivalent. Folds into the same
   follow-up.
4. **Liveness rules differ between the two paths** and the docs must not blur
   them: on acquire, `alive` **and** `unknown` both mean leave it alone (only a
   provably `dead` anchor is reclaimed, `merge_lock.sh:50-54`); on
   `force-release`, only a literal `alive` refuses, so `unknown` is clearable —
   deliberately, as a human act.
5. **Style constraints** the plan didn't capture: `{{% alert %}}` is used **zero**
   times site-wide (callouts are `> **Note:**`); concepts pages use only absolute
   `{{< relref >}}`; concepts headings are sentence case, workflows Title Case;
   tables use the compact `|---|---|`.

Already-satisfied constraints, kept as no-regression checks: `diffviewer` appears
zero times under `website/content/docs/`, and neither page names a real repository.

## Implementation

### Step 1 — `website/content/docs/concepts/locks.md`

Leave the frontmatter alone (`concepts/_index.md:30` duplicates the `description`
verbatim; changing one creates drift). Leave the existing task-lock section and
its table untouched.

- **`## What it is`** — add a paragraph naming the second lock and splitting the
  responsibility: the task lock says who owns a task ID; the **merge mutex**
  serializes the **end-of-task merge** across concurrent tasks.

  **Scope the claim at first mention.** Do not write that the mutex governs "who
  may drive the shared working tree" — it governs only the merge paths that
  participate in it, which today is the task workflow's end-of-task merge and
  nothing else. A reader who meets the broad claim first will infer protection
  that does not exist for `/aitask-web-merge` or for any hand-run
  `git checkout` / `git merge` in the repo root.
- **New `## The merge mutex`**, with three `###` sub-headings so each lands in the
  page TOC (t1560_4's checklist requires each to be *findable without prior
  knowledge*):
  - lead, then the **boundary immediately** — a `> **Note:**` callout (house
    style; `{{% alert %}}` does not exist on this site) stating what does *not*
    participate: `/aitask-web-merge`, and any merge run by hand outside the task
    workflow. Placing it under the lead rather than at the end of the section is
    the point — the qualification has to reach the reader before the mechanism
    does.
  - **`### What the merge mutex excludes`** — a two-column table mirroring
    the task-lock one: free → proceeds; held by a running task → queued, and you
    are told the holding task id; provably gone → reclaimed; liveness
    unverifiable → left alone, reusing the page's existing *"cannot tell" is its
    own answer, never rounded up to "go ahead"* framing. State that it is **one
    global lock per repo, not one per branch** — two tasks merging into different
    output branches still drive one HEAD, one index, one working tree.
  - **`### The reservation outlives the command`** — session-anchor lifetime:
    `begin` / `finish` / `abort` are three separate short-lived processes, so the
    reservation is anchored to the agent session, not the script process. It is
    deliberately held through conflict resolution, verification (`ait gates run`)
    and cleanup — that is what makes a build result attributable — and **nothing
    auto-releases it**.
  - **`### Before a merge can start: the session anchor`** — the precondition,
    stated as a real user-visible constraint, not an implementation detail: with
    no resolvable anchor the merge is refused *before anything is acquired*
    (`NO_SESSION_ANCHOR`). Name **both** remedies — but state the requirement, not
    merely the check:
    - **Run inside a tmux pane** — the standard route. The framework launches each
      agent as its pane's own process, so the anchor dies exactly when the agent
      does.
    - **Set `AIT_AGENT_PID`** — for launchers that start an agent outside tmux. It
      must name the process that **represents and outlives the whole agent
      session** (normally the launcher/session process), not any convenient live
      PID.

    Say plainly *why*, because the broker cannot check it: it verifies only that
    the PID is a positive integer naming a process that exists right now
    (`pid_anchor.sh:274-290`), so a wrong-but-live PID is accepted silently and
    fails in one of two directions —
    - a PID that **outlives** the session (an unrelated daemon) leaves the holder
      permanently `alive`, so automatic reclaim never fires and `force-release`
      refuses it (`REFUSED_LIVE_HOLDER`); the reservation is stranded until that
      process is stopped;
    - a PID that **dies early** (a short-lived child) makes the holder `dead`
      mid-merge, so a contending task reclaims the tree while the merge is still
      in progress — the exact defect the anchor exists to prevent (recorded in
      `pid_anchor.sh`'s `History` note, t1465).
  - **`### Recovering a stuck merge mutex`** — the ladder, as numbered steps:
    `status` (names holder, pid, liveness, output branch, acquired-at) → clear a
    leaked `.gc` guard with `rmdir`, **never** `rm -rf`, since its emptiness is
    the proof no reclaim is running → `force-release` with no flags is a dry run
    that prints the holder, the residue it found, the remedy flag it derived and a
    copy-safe armed command carrying `--expect <token>` → run that line verbatim.
    Cover: it **refuses a provably live holder**; the **two residue states have
    two distinct remedies** (`MERGE_HEAD` present → `--abort-merge`; unmerged
    index / dirty tree with no `MERGE_HEAD` → `--reset-hard`, which prints the
    blast radius before discarding); a mismatched flag is refused, never
    attempted. Close by stating the ladder **terminates**: either the mutex is
    released, or the tool names the specific reason it will not act.
  - close the section by referring back to the boundary callout with the one
    actionable consequence: do not run `/aitask-web-merge` while a task is at its
    merge step. (The boundary itself is stated up top, not here.)
- **`## Why it exists`** — one paragraph: the merge is the single mutating step
  that runs in the shared repo root rather than the task's worktree, so worktree
  isolation does not extend to it.
- **`## How to use`** — state that the merge mutex is acquired and released
  automatically, that [`ait lock`]({{< relref … >}}) does **not** manage it (it
  covers task locks only), and that inspection/recovery is
  `./.aitask-scripts/aitask_merge_task.sh status` / `force-release`. This matters:
  the broker is not exposed through the `ait` dispatcher, so a user following the
  existing text would look in the wrong place.
- **`## See also`** — add Parallel development.

### Step 2 — `website/content/docs/workflows/parallel-development.md`

Line 20 is accurate as written; leave it and add a new Title Case section
**`## Serialized Merge-Back`** after "Git Worktrees for Isolation", covering:
concurrent tasks reaching the merge are serialized — one at a time drives the
shared checkout; a queued agent is told **which task** it is waiting on; a
conflict-parked merge **keeps the shared tree reserved until the human is done**,
so the next task cannot absorb half-resolved work; the reservation is held through
verification and cleanup. Then state plainly the consequence recorded in the
parent plan: under `create_worktree: false` there is no task branch and the merge
step does not run at all, so shared-checkout mode is unaffected. Link to the new
`locks.md` section via `{{< relref >}}` with anchor.

Keep the page's existing agent-set-agnostic phrasing ("multiple code agent
sessions"), per `documentation_conventions.md` §3.

### Step 3 — Audit disposition + follow-up task

Record all three outcomes in the Final Implementation Notes:

| skill | disposition |
|---|---|
| `aitask-pickrem` | **Exempt** — no merge, no branch switch. Verified across the `.j2`, all three rendered variants and all six ports: zero `git checkout\|merge\|switch`. Its only push is the `./ait git` aitask-data wrapper. |
| `aitask-pickweb` | **Exempt** — no cross-branch operation at all; its description is literally true of current source. It is the *producer* whose consumer is web-merge. |
| `aitask-web-merge` | **NOT exempt — hazard confirmed.** Merges `origin/<branch>` in the shared root with `--no-ff --no-commit`, never asserts HEAD, takes no lock, and pushes. Fix deferred to the follow-up below, because it needs a broker change this task's non-goals forbid. |

Create one follow-up task (`ait create --batch`, `issue_type: bug`, labels
`git, task_workflow`, explicit `depends`) scoped to: extend the broker with an
acquire-only / `--no-commit` mode that fits a remote-ref source; wire
`aitask-web-merge` to it; add the missing HEAD assertion. Note in it that the
Codex/OpenCode ports are pointer wrappers needing no separate port tasks, and
that editing web-merge's frontmatter `description:` would trip the
wrapper-parity check in `aitask_audit_wrappers.sh`.

When that task lands, `locks.md`'s boundary callout must be revisited — it is the
sentence that stops being true.

No skill files are edited by this task.

### Post-phase (risk mitigations)

**`verdict_prose_crosscheck`** — before committing, walk the drafted prose against
the source, line by line, and correct any divergence:

- every verdict name that appears in the two pages (`NO_SESSION_ANCHOR`,
  `REFUSED_LIVE_HOLDER`, `WRONG_REMEDY`, `FORCE_RELEASED`, …) against
  `aitask_merge_task.sh:498-505`;
- the residue-state → remedy-flag mapping against the `force-release` branches at
  `aitask_merge_task.sh:399-435` — `MERGE_HEAD` present → `--abort-merge`;
  unmerged index / dirty tree with no `MERGE_HEAD` → `--reset-hard`;
- the liveness asymmetry against `merge_lock.sh:50-54` (acquire: `alive` **and**
  `unknown` both protected) versus `aitask_merge_task.sh:399-401` (force-release:
  only `alive` refuses);
- the two anchor remedies against `pid_anchor.sh:274-290` — including that the
  prose states the *requirement* (a process representing and outliving the agent
  session) and not merely the *check* the broker performs, and that both failure
  directions are named;
- the scope qualification: no sentence claims the mutex governs the shared working
  tree in general, and the boundary callout precedes the mechanism.

## Verification

- `cd website && hugo build --gc --minify` exits 0 and still reports **237 pages**
  (baseline captured before any edit: rc=0, 237 pages, two pre-existing
  deprecation warnings). No new warnings.
- Cross-references: Hugo fails the build on an unresolvable `relref`, so a green
  build **is** the check — assert it explicitly rather than implying it.
- `grep` both pages: the merge mutex, the anchor precondition
  (`NO_SESSION_ANCHOR` + both remedies) and the `force-release` ladder are each
  present, each under a heading that appears in the page TOC.
- No-regression greps: zero `diffviewer`, zero real repository names on both
  pages.
- Read both rendered pages to confirm the three targets are findable without
  prior knowledge (this is t1560_4's manual-verification item, previewed here) —
  and specifically that the boundary callout is encountered before the mechanism,
  reading top to bottom.
- `aitask_skill_verify.sh` is **not** run: this task edits no skill file. Recorded
  as a deliberate deviation from the task's conditional verification bullet, whose
  precondition ("if `aitask-web-merge` gains the mutex") is not met.

## Risk

### Code-health risk: low
- Prose-only change to two pages; no code paths, no callers, build-verified. The
  one residual: `locks.md` roughly doubles in length and now carries two distinct
  lock models on one page, so a future merge-mutex edit has to find its section
  inside a page that also documents task locks · severity: low · → mitigation: None

### Goal-achievement risk: medium
- The published recovery ladder documents a **destructive** remedy: `--reset-hard`
  discards tracked working-tree state. If the prose blurs which residue state maps
  to which flag, a reader could run the wrong one and lose work · severity: medium
  · → mitigation: inline post-phase verdict_prose_crosscheck
- The liveness rule is asymmetric — on acquire, `alive` **and** `unknown` are both
  left alone; on `force-release`, only a literal `alive` refuses. Stating it
  backwards would tell users either that a wedged unverifiable lock cannot be
  cleared, or that a live holder can be displaced · severity: medium · →
  mitigation: inline post-phase verdict_prose_crosscheck
- Two claims are easy to publish in an under-qualified form that misleads: that
  the mutex protects the shared working tree generally (it protects only the
  participating end-of-task merge), and that any live PID is a valid
  `AIT_AGENT_PID` (a wrong-but-live PID either strands the reservation or permits
  reclaim mid-merge, and the broker cannot detect either) · severity: medium · →
  mitigation: inline post-phase verdict_prose_crosscheck
- "Findable without prior knowledge" (t1560_4's checklist) is a human verdict
  passed later; TOC-level headings are the design response but cannot guarantee it
  · severity: low · → mitigation: merge_verdict_docs_drift_guard

### Planned mitigations
- timing: post-phase | name: verdict_prose_crosscheck | type: documentation | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: destructive-remedy mis-mapping + liveness asymmetry (goal-achievement) | desc: walk every verdict name, remedy flag and residue-state mapping in the drafted prose against the force-release branches in aitask_merge_task.sh and the adapter deltas in merge_lock.sh, line by line, before commit
- timing: after | name: merge_verdict_docs_drift_guard | type: test | priority: medium | effort: medium | inline_risk: low | added_complexity: medium | addresses: destructive-remedy mis-mapping + liveness asymmetry, durably (goal-achievement) | desc: a test pinning the CURATED published recovery mapping in locks.md (the residue-state to remedy-flag pairs and the user-facing verdicts the page names) against the broker's behaviour — scoped to that curated set, never to the full --list-verdicts vocabulary, so a new workflow-internal verdict cannot fail the website guard
