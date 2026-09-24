---
Task: t1687_4_concepts_trails_and_shadow_agent.md
Parent Task: aitasks/t1687_concepts_docs_gap_sweep.md
Sibling Tasks: aitasks/t1687/t1687_1_concepts_gates_page.md, aitasks/t1687/t1687_2_concepts_attachments_and_attach_command.md, aitasks/t1687/t1687_3_concepts_task_notes_and_cross_repo.md, aitasks/t1687/t1687_5_concepts_index_regroup_and_link_verification.md
Archived Sibling Plans: aiplans/archived/p1687/p1687_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-09-23 19:21
---

# t1687_4 — Implementation trails and shadow agent (verified 2026-09-23)

## Context

Part of t1687 (Concepts docs gap sweep). The trail (an advisory *artifact*) and
the shadow (an advisory *agent*) have workflow pages but no concept pages. These
are the two highest-duplication pages in the sweep; the user chose "write both,
**strictly complementary**". If a paragraph could be pasted into the workflow
page without looking out of place, it belongs there, not here.

## Verification findings (what changed since the plan was written)

- **Workflow line numbers shifted by +4** in `workflows/implementation-trails.md`:
  the no-restate ranges are now `:9-47` (what a trail is / waves /
  classifications / observations / exclusions — unchanged), `:94-111` (Keeping a
  Trail Current — freshness/drift), `:129-138` (What a Trail Never Does). The
  `#what-a-trail-never-does` heading is at line 129.
  `workflows/shadow-agent.md` is unchanged: `:9-11`, `:28-38`, `:186-188`.
- **Corrected claim — `scope.topics`.** The original plan said "`scope.topics`
  lists members rather than their anchor roots". That is true **only** for
  trails produced by the backlog roadmap (`.aitask-scripts/lib/roadmap_run.py:403`).
  The schema (`implementation_trail.schema.json:56`) defines it as canonical
  topic-group keys (root ids), and `/aitask-trail` writes it that way. The page
  therefore **does not mention `scope.topics`** at all — a schema field is not
  concept-level, and either phrasing would be wrong for some trails.
- Back-link anchors confirmed present: `tuis/board/reference.md:249`
  `#### By-Trail`; `tuis/minimonitor/_index.md:77`
  `## Launching a shadow agent`; `skills/aitask-trail.md:89` `## Related`;
  `concepts/topic-anchoring.md:130` `## See also` (trail workflow links at
  lines 21 and 136); `tuis/minimonitor/how-to.md:187` and
  `tuis/monitor/how-to.md:184` workflow-link sentences;
  `development/task-format.md:78` `### Nested fields: artifacts and attachments`.
- `concepts/artifacts.md` still does not exist; weights 105 and 125 are free.
- Code claims the shadow page relies on are confirmed:
  `SHADOW_TARGET_OPTION = "@aitask_shadow_target"` (`monitor/monitor_core.py:421`);
  the stamp-failure kill (`monitor_core.py:3801`, `:3884`); the capture's
  binding resolution, same-server check and `SHADOW_BIND_WAIT_MS` fail-closed
  wait (`aitask_shadow_capture.sh:50,96,229`); job-1 cleanup matching on the
  option (`aitask_companion_cleanup.sh:68-77`). The fold transfer of the
  `artifacts:` handle is at `aitask_fold_mark.sh:557-561`.
- Page conventions taken from siblings t1687_1–3 (`concepts/gates.md`,
  `concepts/task-notes.md`): frontmatter `title/linkTitle/weight/description/depth`;
  body `## What it is` (with `###` subsections) → `## Why it exists` →
  `## How to use` → `## See also`; **no `**Next:**` footer** (t1687_5 owns
  ordering); full-path relrefs; claims written against code, not aidocs.

## Implementation

### 1. NEW `website/content/docs/concepts/implementation-trails.md`

Frontmatter: `title: "Implementation Trails"`, `linkTitle: "Implementation trails"`,
`weight: 105`, `depth: [advanced]`, description ≈ "Why a sequencing
recommendation is kept as a versioned, task-owned artifact instead of being
worked out again each time."

Angle (narrowed after review): **the task-owned handle and the structured
storage model.** The workflow page already explains the motivation
(scrollback, `:11-13`), that a trail is a durable versioned recommendation, that
refreshing keeps earlier versions (`:106`) and that topics and trails are
separate (`:138`). This page **links** to those passages rather than
re-explaining them. It states the thesis (a decision kept with its evidence,
not re-derived) in one paragraph, then covers where a trail lives and what that
placement implies.

- `## What it is` — two sentences: a trail is one structured document stored
  under a handle that one task owns. Then a link to
  `{{< relref "/docs/workflows/implementation-trails" >}}` for what a trail
  records and how it is refreshed.
  - `### Kept, not re-derived` — **the page's thesis (mandatory angle; keep it
    to one short paragraph).** A sequencing recommendation is a decision made
    against evidence that goes stale: task statuses, in-flight work, a red
    suite, and the agent's judgement of them. Running the analysis again
    later does not reproduce the decision; it makes a new one against
    different evidence. So what is stored is the decision **together with the
    evidence it was made on**, and a refresh records a new decision beside the
    old one instead of overwriting it. The version history is therefore a
    history of decisions, each still readable against its own evidence. Link
    `{{< relref "/docs/workflows/implementation-trails" >}}#keeping-a-trail-current`
    for how staleness is detected and refreshed. Do **not** repeat the
    scrollback story (`:11-13`), the drift-reason list or the refresh keys.
  - `### One owner carries the handle` — the handle appears only in the owner
    task's `artifacts:` frontmatter (link
    `{{< relref "/docs/development/task-format" >}}#nested-fields-artifacts-and-attachments`
    for the shape). Creating a trail writes that one entry. **The owner may
    also be a member** (a single-task trail defaults to the task it was started
    from), but the files of the *other* member tasks are never written. That is
    why a task can appear in any number of trails without churning its file.
    A trail over several topics, or an ad-hoc set, needs an owner chosen
    explicitly: no container task is created implicitly, because that would
    add board clutter.
  - `### Found through its owner` — trails are discovered by scanning task
    frontmatter, **active and archived**, for `kind: implementation_trail`
    entries (`lib/trail_discovery.py`). Consequences: archiving the owner does
    not hide or delete its trail (the board notes the archived owner). Do **not**
    say the trail becomes stale: freshness is assessed separately, from the
    trail's recorded inputs, and an explicitly chosen owner of a multi-topic or
    ad-hoc trail may be outside those inputs entirely. Folding the owner
    moves the handle to the fold primary (`aitask_fold_mark.sh:557-561`), so the
    trail survives with a new owner.
  - `### One document, several readings` — the stored thing is a single
    structured document with its prose rationale as first-class fields. The
    board's By-Trail view, `ait trails` and the markdown rendering are all
    projections of it, and none of them is saved as a second copy. Membership
    lives inside that document, never as a field on a member task.
  - `### Read by nothing that enforces` — the read-side counterpart to the
    workflow's "never rewrites" list: gate enforcement, `depends` resolution
    and archival guards never read a trail, so a trail cannot block or unblock
    anything. Link
    `{{< relref "/docs/workflows/implementation-trails" >}}#what-a-trail-never-does`
    for the write side instead of restating it.
- `## Why it exists` — why *this* storage model and not the alternatives
  recorded in the design (§4.2, §13 A2–A4): a field on every member task (one
  recommendation would rewrite many task files; the design keeps membership
  in trail content only); markdown plus a parser, or paired JSON and markdown
  (fragile validation, two sources of truth); an ownerless document (the
  artifact store has no unowned entries, and picking an owner automatically
  would tie the trail's lifecycle to a task the user did not choose).
- `## How to use` — `/aitask-trail` to create/refresh; board By-Trail view;
  `ait trails`.
- `## See also` — workflow page, `skills/aitask-trail`, `tuis/trails`,
  `tuis/board/reference#by-trail`, `concepts/topic-anchoring`.

**Hard limits:** do not describe the artifact store (`art:<id>` substrate,
manifests, backends — t1231_3 owns `concepts/artifacts.md`; no link to it).
**No merge line** (`merged_from` belongs to t1647_6). No restating the
workflow's waves/classification table, drift list, or never-does bullets.

### 2. NEW `website/content/docs/concepts/shadow-agent.md`

Frontmatter: `title: "Shadow Agent"`, `linkTitle: "Shadow agent"`,
`weight: 125`, `depth: [intermediate]`, description ≈ "How a companion agent
knows which agent it follows, and what keeps it advisory."

Angle: **the pane-binding identity and the advisory-only contract.**

- `## What it is` — one sentence plus a link to the workflow page for what a
  shadow is and does; this page covers how it is bound and why it cannot act.
  - `### The binding is a pane option` — the spawn stamps
    `@aitask_shadow_target = <followed pane id>` on the **shadow's** pane. That
    one option does three jobs: it tells monitor/minimonitor to leave the shadow
    out of the agent list, it names what the capture reads, and it lets cleanup
    close the shadow when the followed agent's pane dies. Pane options die with
    the pane, so a recycled pane id cannot carry a stale binding: the same
    mechanism as `@aitask_record` (link
    `{{< relref "/docs/concepts/framework-session" >}}#identity-versus-location`).
    If the stamp cannot be written, the new pane is killed rather than left
    behind, because an unstamped shadow looks exactly like a real agent: it
    would be listed, targeted and never cleaned up.
  - `### The capture reads the binding, not a typed id` — a pane id passed
    through a model can be mangled into the id of a *different live* pane, and
    then the capture succeeds and the advice is about the wrong agent. So in the
    normal flow the capture takes no id: it reads the binding off its own pane,
    accepts it only from the same tmux server, waits briefly for a just-spawned
    stamp and otherwise fails closed. It never guesses.
  - `### Reading a copy, not sharing a session` — capture → context-fetch →
    skill: the shadow reads a cleaned text capture of the followed pane and
    fetches the task and plan files by task id. Consequences: it can re-read on
    demand, and its view is only as fresh as its last capture.
  - `### What keeps it advisory` — state **two separate facts**, and never
    present either as a technical guarantee:
    1. *The framework's own path is read-only.* Capture reads the pane;
       context-fetch reads files. Concern forwarding goes through a picker in
       monitor/minimonitor, which copies the chosen items to the clipboard
       only after the user confirms. The framework never types into the
       followed pane on the shadow's behalf.
    2. *The shadow itself is told not to drive the followed pane.* The shadow
       is an ordinary code agent with its normal tools, and the `aitask-shadow`
       skill declares no tool restriction (verified). "Never send keystrokes
       or answers" is therefore an **instruction in its skill, not an isolation
       boundary**. Say so plainly: it is the contract the shadow is built to
       honour, not a sandbox that makes a write impossible.
    Link `workflows/shadow-agent#advisory-only` rather than repeating its wording.
- `## Why it exists` — a second agent must know whom it follows without the
  user restating it, and without trusting a model's copy of an identifier; a
  binding that lives and dies with the pane gives both.
- `## How to use` — **e** / **E** from minimonitor or monitor; link the
  workflow page and both how-to anchors.
- `## See also` — workflow page, `tuis/minimonitor`, `tuis/monitor`,
  `concepts/framework-session`.

No link to a `skills/aitask-shadow` page (none exists) and none to
`tuis/minimonitor/reference` (none exists).

### 3. Back-links (8 edits)

| File | Insertion point | Form |
|---|---|---|
| `workflows/implementation-trails.md` | end of `## What a Trail Never Does` ¶ at :138, after the topic-anchoring link | relref `/docs/concepts/implementation-trails` |
| `skills/aitask-trail.md` | new bullet in `## Related` (:89) | relref |
| `tuis/board/reference.md` | one sentence under `#### By-Trail` (:249) | relref |
| `concepts/topic-anchoring.md` | new `## See also` bullet after the :136 workflow bullet (kept) | relref |
| `workflows/shadow-agent.md` | end of lead ¶ :11 | **relative** `(../../concepts/shadow-agent/)` |
| `tuis/minimonitor/_index.md` | `## Launching a shadow agent` ¶ :79 | relref |
| `tuis/minimonitor/how-to.md` | :187, beside the workflow link | relref |
| `tuis/monitor/how-to.md` | :184, beside the workflow link | relref |

Every relref uses the full `/docs/concepts/...` path (slug collision with the
same-named workflow pages). Do **not** link from `tuis/monitor/reference.md`
or `tuis/monitor/_index.md`. Do **not** touch `concepts/_index.md`
(t1687_5).

### Post-phase (risk mitigations)

1. [link_relevance_triage] Re-read both new pages side by side with their
   workflow counterparts (trails `:9-47`, `:94-111`, `:129-138`; shadow `:9-11`,
   `:28-38`, `:186-188`) and delete any paragraph that restates them.
2. [claim_check_against_code] For every factual sentence on the two pages,
   confirm it against the code sites listed under "Verification findings"
   (and `roadmap_run.py`/the schema for anything touching topics). Remove or
   qualify any sentence that holds only for a subset of trails or shadows.

## Verification

```bash
cd website && hugo build --gc --minify; echo "hugo=$?"
cd website && python3 check_links.py --build; echo "links=$?"
cd website && python3 check_link_relevance.py   # report only, triage new links
grep -c "concepts/artifacts" website/content/docs/concepts/implementation-trails.md   # expect 0
grep -ci "merge" website/content/docs/concepts/implementation-trails.md             # expect 0
```

Confirm `#by-trail`, `#what-a-trail-never-does`, `#launching-a-shadow-agent`,
`#keeping-a-trail-current` and `#identity-versus-location` still resolve (covered
by `check_links.py`).

## Step 9 (Post-Implementation)

Standard cleanup, archival and merge. The `risk_evaluated` gate is active and
must pass before archival.

## Risk

### Code-health risk: low
- An ambiguous bare relref (slug collision) breaks the site build · severity: low · → mitigation: none (full-path relrefs + `hugo build` in Verification)

### Goal-achievement risk: low
- The new pages restate their workflow counterparts, producing the duplicate-index outcome the parent task warns against · severity: low (residual — the trails page was re-scoped at plan review to the storage model, and inline post-phase link_relevance_triage re-checks both pages) · → mitigation: inline post-phase link_relevance_triage
- The shadow page overstates advisory-only as a technical guarantee, when it is a skill instruction · severity: low (residual — plan now states the read-only framework path and the instruction as separate facts; claim_check_against_code re-checks the wording) · → mitigation: inline post-phase claim_check_against_code
- A concept sentence is true only for a subset of cases (as the original `scope.topics` claim was), and no build check detects a wrong claim · severity: low (residual — addressed by inline post-phase claim_check_against_code) · → mitigation: inline post-phase claim_check_against_code

### Planned mitigations
- timing: post-phase | name: link_relevance_triage | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: duplication with workflow pages | desc: Re-read both new pages against their workflow counterparts and delete restatements
- timing: post-phase | name: claim_check_against_code | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: partially-true concept claims | desc: Verify every factual sentence against the confirmed code sites; remove or qualify subset-only claims

## Implementation progress

- [x] 1. `concepts/implementation-trails.md` (weight 105) written.
- [x] 2. `concepts/shadow-agent.md` (weight 125) written.
- [x] 3. Eight back-links added (7 full-path relref, 1 relative in `workflows/shadow-agent.md`).
- [x] Post-phase link_relevance_triage — cut one clause on the trails page that
      repeated `workflows/implementation-trails.md:133` ("converting ordering …
      by hand"); reworded the topic-anchoring See-also bullet, which promised
      topic content the page does not carry.
- [x] Post-phase claim_check_against_code — qualified four trails-page claims:
      "handle appears in exactly one place" → among task files (the manifest and
      the document's `trail_id` also carry it); owner default is "the task or
      topic root" for single-scope trails (`trail_gather.py:1118`); "markdown
      summary" → "the summary the skill prints"; dropped "deletion guards" from
      the lifecycle list (not verified against code).
- Verification: `hugo build --gc --minify` = 0; `check_links.py --build` = 0;
  `check_link_relevance.py` reports none of the new links; no
  `concepts/artifacts`, no merge line, no `**Next:**` footer.

## Post-Review Changes

### Change Request 1 (2026-09-23 19:40)
- **Requested by user:** (1) the "handle in exactly one task file" claim is false between a fold and archival — the fold copies the handle to the primary and the folded task keeps its entry (discovery dedups, `trail_discovery.py:104-106`); (2) the "not auto-owned" rationale read as applying to every trail, though single-task/topic trails default their owner.
- **Changes made:** Scoped the one-entry claim to trail creation; renamed "Folding the owner moves the handle" to "copies", stating the temporary two-reference window and the dedup precedence; rewrote the Why-it-exists bullet as "Not ownerless" — single-scope trails take their task/topic root, only multi-topic/ad-hoc trails need a chosen owner.
- **Files affected:** `website/content/docs/concepts/implementation-trails.md`

## Final Implementation Notes

- **Actual work done:** Two new concept pages, both ending at `## See also` with
  no `**Next:**` footer (t1687_5 owns ordering).
  `concepts/implementation-trails.md` (weight 105, `depth: [advanced]`) — thesis
  "kept, not re-derived" (a decision stored with the evidence it was made on),
  then the storage model: one owner entry written at creation, discovery through
  active + archived owner frontmatter, fold copy + dedup, one structured document
  with derived views, and the read side ("read by nothing that enforces").
  `concepts/shadow-agent.md` (weight 125, `depth: [intermediate]`) — the
  `@aitask_shadow_target` pane-option binding (its first website presence), the
  capture reading the binding rather than a typed id, capture → context-fetch →
  skill, and the advisory contract split into two facts. Eight back-links (seven
  full-path relrefs, one relative link in `workflows/shadow-agent.md`).
- **Deviations from plan:** The trails page was re-scoped three times at plan
  review: narrowed to the storage model to avoid repeating the workflow page, then
  given back a one-paragraph thesis (the task's mandatory angle), then corrected
  on archived-owner freshness. `scope.topics` is not mentioned at all (see Issues).
- **Issues encountered:**
  - The original plan's "`scope.topics` lists members rather than anchor roots"
    is true only for backlog-roadmap trails (`lib/roadmap_run.py:403`); the
    schema and `/aitask-trail` use topic root ids. Dropped from the page.
  - Plan review: the planned "advisory by construction" wording implied technical
    isolation. The `aitask-shadow` skill declares no tool restriction, so the
    page now states the read-only framework path and the skill instruction as
    separate facts and says plainly it is not a sandbox.
  - Plan review: a single-task trail's owner can also be a member, so "a member's
    file is never written" was narrowed to the *other* members.
  - Plan review: archiving an owner does not make a trail stale. Freshness comes
    from recorded inputs, and a chosen multi-topic owner may not be one.
  - Step-8 review: the fold *copies* the handle (the folded task keeps its entry
    until archival; `trail_discovery.py:104-106` dedups), and the no-auto-owner
    rationale applies only to multi-topic / ad-hoc trails. Both fixed.
- **Key decisions:** Wrote every claim against code (`trail_gather.py:1118`
  owner default, `trail_discovery.py`, `aitask_fold_mark.sh:557-561`,
  `monitor_core.py:421/3801/3884`, `aitask_shadow_capture.sh`,
  `aitask_companion_cleanup.sh`), not the aidocs RFCs, which carry subset-only
  claims. Unverified items were dropped instead of hedged ("deletion guards").
- **Upstream defects identified:** None
- **Notes for sibling tasks:**
  - t1687_5: both new pages exist at the planned weights; add their
    `_index.md` bullets (trails → *Lifecycle and infrastructure*, shadow →
    *Workflow primitives*). `hugo build` = 0, `check_links.py --build` = 0,
    `check_link_relevance.py` reports none of the new links.
  - Four review passes each found a claim that was true only for a subset of
    cases. Neither `hugo build` nor `check_links.py` can detect that, so check
    concept-page prose against code, including the edge states (fold windows,
    archived owners, default vs explicit choices).
