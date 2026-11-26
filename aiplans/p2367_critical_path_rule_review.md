---
Task: t2367_critical_path_rule_review.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2367 — Critical-path rule review for t2335_3's plan

## Context

Risk-mitigation "before" task for t2335_3. Its approved plan
(`aiplans/p2335/p2335_3_trails_highlight_and_critical_path_overlay.md`) interprets the trail schema
and the documented classifications into a critical-path rule and an advice contract that t2335_4's
`>d` / `>q` / `>p` codes will quote. This task reviews that rule against the sources before t2335_3 is
implemented, edits the plan in place where it is wrong or incomplete, and records one verdict per point
in a new `## Critical-path rule review` section. No code changes.

The review is already done during planning. The findings, each checked against the named source:

| # | Point | Verdict | Source evidence |
|---|---|---|---|
| 1 | Wave edges by classification | confirmed | implementation-trails.md: "Only a hard prerequisite is a reason to wait: a coordination-only entry only has to land at a different time"; board reference table (◆ "true blocker", ▲ "not strictly blocking", ● core, ⇄ "no dependency", ○ "trail does not depend on it"); `trail_schema.py` allows a ref in several entries (no task-uniqueness rule), so "earliest ordinal" is needed |
| 2 | Live `depends:` authoritative, saved edges fallback, superseded | confirmed | schema `snapshot`: "the task file remains the source of truth"; `relations`: fact edges "mirror real recorded constraints"; `trail_schema.py` hard_depends mirror check; every `task_ref` is project-qualified |
| 3 | `released` satisfies depends edges, not wave-hard | confirmed | `dep_resolution.py`: gate_released → SATISFIED (t635_3); `gate_ledger.dependents_status` "dependents may proceed"; a hard prerequisite blocks "until this lands", and the trail's "landed" is status Done (`board_trail_view.build_trail_lanes`, ✔ only for Done) |
| 4 | xdeps block under the existing rule | confirmed | `cross_repo_deps.classify_xdep_status` (only Done unblocks; "" / NOT_FOUND unreachable); `aitask_ls.sh calculate_blocked_status` applies the same rule |
| 5 | NEXT = pick eligibility; full readiness set | **corrected** | the readiness rule covers "every highlighted node", but a highlighted id that is not a trail member has no defined readiness. With xdeps it would read blocked by keys `remote_keys` never probes; without them it could be NEXT with no card and none of the trail's wave knowledge. And the protocol's `BLOCKER:` lines are keyed to a highlighted ref only, so nothing says which node a blocker blocks |
| 6 | Outside prerequisites reported, not followed | confirmed rule, **corrected** consumer contract | the contract does not say what `>p` does when a highlighted task's only blockers are OUTSIDE / XDEP (no NEXT exists): it must not say "nothing to do", and must not offer an OUTSIDE ref as a pick |
| 7 | Only verified Done clears | **corrected** (user decision) | sources conflict: `dep_resolution.py` never reads bundles ("a surface that resolved more than the others would break the parity"), so `ait ls` shows a dependent whose live `depends:` names a bundle-only task as `Blocked (… (UNRESOLVED))`; the trail cards read bundles (`find_archived_markdown_by_id`) and show it ✔. User's answer, verbatim: "Keep verified bundled tasks landed with reason=bundle. If a candidate's live depends: includes a prerequisite found only in a bundle, show the picker's unresolved:bundled blocker on the candidate and withhold NEXT and >p pick advice. For wave-order edges, verified Done still clears the edge." |
| 8 | Freshness qualifier on every NEXT | confirmed qualifiers, **corrected** consumer contract | the trail's `FRESHNESS` (drift helper) and a direction's freshness verdict (`aidocs/framework/sitrep.md` "The freshness verdict") share the vocabulary current / stale / unknown, and the contract does not name them apart. The direction verdict compares its inputs **now** with its **saved baseline**; the trail's `<hash>:<drift verdict>` is one input line. So a direction whose summary was saved over an already-stale trail reads `current` while that line still matches (`trail_stale` fires only when the verdict *became* stale), and an unreadable input makes the direction `unknown` whatever the trail says. Neither verdict can be derived from the other |
| 9 | Direction identity (slug) vs display title | confirmed | `sitrep_todo.DIRECTION_RE` `^[a-z0-9][a-z0-9_-]*\Z`, `MAX_DIRECTION_TITLE = 120`, `_single_line` (no CR/LF, `strip()`, pipes allowed for titles, so base64url transport is needed) |

### Plan review — concerns addressed

| Concern | Resolution |
|---|---|
| Bundle rule scope: edits 1–2 applied the bundle exception to every depends edge, including the saved `hard_depends` / `snapshot.depends` fallback, so a foreign or unresolved member could get a blocker against a verified Done predecessor with no live picker evidence | The exception is bound to **live** depends edges only (the edges `ait ls` reads). A saved fallback edge from a bundle-only Done predecessor is **satisfied**, like a wave-hard edge. Stated in the edge rule and in a split state-table column; both cases pinned (edits 1, 2, 7) |
| Blocker evidence: a highlighted non-member seeds the path but has no `BLOCKER:` lines, so a blocked path member cannot be tied to what blocks it (A outside → member B → bundled C) | New line `BLOCKED_BY:<node>|<direct blocker>|…` for **every** `blocked` node, highlighted member or path member, and for a non-member highlight's unsatisfied edges to members. The mixed case is pinned in a CLI fixture (edits 4, 6, 7) |
| Freshness contract: "a stale trail makes its direction stale" is wrong — the direction verdict is a comparison with its saved baseline, and an unreadable input makes it `unknown` | The contract says trail drift is **one input** to direction freshness, gives the two counter-cases, and tells the consumer to report each verdict from its own source and never derive one from the other (edit 5) |
| Outside highlight seeds: edit 4 made every member in a non-member's live depends a traversal seed without the edge verdict, so a Done or released member would go back on the path, or its unfinished predecessor would surface as NEXT | A non-member's live depends edges to members are **ordinary live depends edges**: the satisfaction rule runs first. `done` → landed, `released` → released, neither traversed; a bundle-only `done` → an `unresolved:bundled` direct blocker of the non-member, not expanded; only an unsatisfied edge puts the member on the path. Fixtures for a Done, a released and a bundled prerequisite (edits 4, 7) |
| Bundle blocker display: edits 7–8 pinned a generic `blocked` label, while the user asked to show the bundle blocker on the candidate | The card note of a node with a bundled direct blocker **names it and its reason** from the direct-blocker details already computed: `… · blocked by <n> · t40 unresolved (bundled)`. No new marker, no lookup. Asserted in the mixed CLI/TUI fixture (edits 7, 8) |
| Completed outside highlight: edit 4 checked each prerequisite's state but not the outside root's own, so a Done non-member whose file still lists a Ready member put it on the path and emitted NEXT | The root's own state decides first, total over the four states: `done` (loose or bundle) and `unresolved` are **not expanded**; `open` / `released` are. `NOT_IN_TRAIL:` carries that state. Fixtures: a single completed root → no PATH, BLOCKED_BY or NEXT, with a Ready-root control (edits 4, 6, 7) |

## Implementation — edits to `aiplans/p2335/p2335_3_trails_highlight_and_critical_path_overlay.md`

1. **Semantics → Edges, "Depends (strong)"**: add two bullets after the three existing ones:
   - **Live edge, bundle-only predecessor**: an edge taken from X's **live** `depends:` whose
     predecessor is `done` only through a numbered bundle (`reason=bundle`) is **not satisfied**. It
     blocks X as `unresolved:bundled`. That is the picker's verdict for the same edge
     (`dep_resolution` never reads bundles, so `ait ls` shows X blocked), and NEXT is pick eligibility.
     The predecessor itself stays `done`: its card keeps ✔, it is listed `LANDED` with `bundle`, it is
     not a path node and is not expanded.
   - **Saved fallback edge, bundle-only predecessor**: an edge taken from the saved evidence
     (`hard_depends` / `snapshot.depends`, used when X is unresolved or foreign) is **satisfied** by a
     bundle-only `done` predecessor, like any verified Done. No picker reads that edge, so there is no
     picker verdict to mirror.
   Add to the **Wave-hard** bullet: "A bundle-only `done` entry satisfies it (verified Done clears
   wave order)."
2. **Semantics → States table**: split the "Depends edge from it" column into **"Live depends edge
   from it"** and **"Saved (fallback) depends edge from it"**. `done` row: live = "satisfied; a
   **bundle-only** copy blocks the dependent (`unresolved:bundled`)", saved = "satisfied", wave-hard =
   "satisfied". The other rows carry their current value in both new columns (`released`: satisfied /
   satisfied; `open` and `unresolved`: blocks / blocks).
3. **Semantics → Sets**: in "Traverse backwards…", add: a live edge blocked as `unresolved:bundled`
   is an unsatisfied edge of its dependent and a **direct blocker** of it, but its predecessor is not
   traversed and not put on the path (it is `done`; it is recorded in **landed**). **Clear** needs no
   wording change: the bundled edge is an unsatisfied direct strong edge.
4. **Semantics → not_in_trail bullet and blockers**:
   - Replace the bullet: a highlighted id that is not a member → **not_in_trail**, never dropped, and
     recorded with its own resolved state. **Its own state decides first whether it is expanded** —
     the rule a highlighted member follows, total over the four states:
     - `done` (loose or bundle-only) → **not expanded**: a completed task waits on nothing, even
       though its file still lists `depends:`. No path node, no direct blocker and no NEXT come from it;
     - `unresolved` (missing, unreadable, folded, malformed `depends:`) → not expanded: its live
       depends are unavailable, and no saved edges exist for a non-member;
     - `open` or `released` → expanded as below (a released highlighted member is expanded too).
     When expanded, its live `depends:` entries that are trail members are **ordinary live depends
     edges** into it, decided by the same rules as any other, **before** anything is traversed:
     - predecessor `done` → satisfied, recorded in **landed**, not traversed;
     - predecessor `released` → satisfied, recorded in **released**, not traversed;
     - predecessor `done` only through a bundle → unsatisfied as `unresolved:bundled`: a direct
       blocker of the non-member, recorded in **landed**, not put on the path, not expanded;
     - otherwise (`open` / `unresolved`) → unsatisfied: the member goes on the path (`via=depends`)
       and the traversal continues from it as from any path node.
     The non-member has no wave edges, no readiness, and is never NEXT; its xdeps are not probed and
     its non-member prerequisites are not reported. The trail knows nothing about its own readiness,
     which is `ait ls`'s business.
   - **Readiness** line: "every highlighted **member** … and every path node".
   - **Blockers** bullet, add **direct blockers**: for every node of (highlighted members ∪ path) with
     readiness `blocked`, the predecessors of its own unsatisfied strong depends and wave-hard edges
     (its unsatisfied cross-repo prerequisites stay in **cross_repo**, keyed by the same node); and
     for every not_in_trail highlight, the predecessors of its unsatisfied live depends edges to
     members — a partial list by construction (members only), said so on both surfaces. `blocked` ⇒
     at least one direct blocker or one blocked cross-repo prerequisite (asserted). In §3 this is one
     field, `CriticalPath.blocked_by: tuple` of `(node ref, blocker ref, via, state, reason)` edges —
     a bundled edge carries `state="unresolved"`, `reason="bundled"`; `not_in_trail` becomes a tuple of
     `(ref, state, reason)`.
5. **Advice contract → "What NEXT means for a consumer"**: append four rules:
   - **No NEXT, outside / cross-repo blockers only**: report what the direction waits on (the OUTSIDE /
     XDEP refs) and never say "nothing to do". An OUTSIDE ref is never pick advice, because its own
     prerequisites were not checked. Name it as "waiting on tN (outside the trail; check `ait ls`)".
   - **Bundled prerequisite**: a candidate blocked by `unresolved:bundled` is not offered as a pick.
     Say that its prerequisite is Done but archived in a bundle, so `ait ls` shows it blocked too.
   - **Two freshness verdicts, two sources**: `FRESHNESS` on this verb is the **trail's** drift
     verdict at this call. A **direction's** freshness (current / stale / unknown) is the sitrep
     refresh's comparison of the direction's inputs now with its saved baseline; the trail's hash and
     drift verdict are one input line of it. The words are the same and the verdicts are independent:
     a direction summarized over an already-stale trail reads `current` while its inputs still match,
     and an unreadable input makes it `unknown` whatever the trail's verdict. Report each verdict by
     name from its own source (`FRESHNESS:` here, the `directions` record there). Never derive one
     from the other.
   - **NOT_IN_TRAIL**: no readiness from this verb. Do not infer one. The line carries the task's own
     state: a `done` one needs no work and nothing is reported for it. For an `open` or `released`
     one, its `BLOCKED_BY:` lines name the trail members it waits on, and only those: its
     prerequisites outside the trail and its cross-repo prerequisites were not examined. No
     `BLOCKED_BY:` line does not mean it is ready.
6. **Line protocol (§4)**:
   - new line, after `BLOCKER:`:
     `BLOCKED_BY:<node ref>|<direct blocker ref>|<waves csv or ->|<depends|wave>|<state>|<reason or ->`
     `(one per direct unsatisfied depends / wave-hard edge of every blocked HIGHLIGHT or PATH node;`
     `for a NOT_IN_TRAIL ref: its unsatisfied live depends edges to trail members only)`;
   - a live edge to a bundle-only prerequisite prints `…|depends|unresolved|bundled` in both
     `BLOCKER:` and `BLOCKED_BY:` (the edge's verdict), while the same ref has `LANDED:<ref>|…|bundle`;
   - `NOT_IN_TRAIL:<ref>|<state>|<reason or ->` `(its own state, no readiness; a done or unresolved`
     `one is not expanded; else see its BLOCKED_BY lines)`;
   - `BLOCKER:` comment: "(transitive, per highlighted member)";
   - `SUMMARY` unchanged.
7. **Tests** — `tests/test_trail_critical_path.py`, add:
   - (a) **live edge**: a Ready member whose live depends names a bundle-only Done task → `blocked`,
     one direct blocker `unresolved:bundled`, not NEXT; the prerequisite is in `landed` (reason
     `bundle`) and not on the path;
   - (b) **wave edge**: the same bundle-only Done task as an earlier-wave `hard_prerequisite` of
     another member, with no depends edge → that edge is satisfied and the member is NEXT;
   - (c) **saved fallback edge**: an unresolved member and a foreign member, each with a saved
     `hard_depends` / `snapshot.depends` edge from the bundle-only Done task → the edge is satisfied,
     no `bundled` blocker on either (the unresolved one reads `unresolved`, the foreign one
     `unverified`);
   - (d) a highlighted non-member with an xdep and a live depends on an **open** member → the member
     is on the path with a `blocked_by` edge from the non-member, the non-member has no readiness and
     no NEXT, `remote_keys` does not contain its xdep;
   - (e) **outside highlight, satisfied prerequisite**: non-member A depends on member B, and B has
     an unfinished member predecessor P. With B **Done**: B in `landed`, path empty, P neither on the
     path nor NEXT, no `blocked_by` edge for A. With B **released**: B in `released`, the same
     otherwise. With B **Done only in a bundle**: B in `landed` (reason `bundle`), one `blocked_by`
     edge A → B `unresolved:bundled`, path empty, P not NEXT;
   - (f) **completed outside highlight**: the single highlighted root is non-member A, **Done**, whose
     file still lists `depends: [B]`, and B is a `Ready` member with no blockers → `not_in_trail` holds
     A with state `done`; path, `blocked_by` and `next_actionable` are all empty. The same with A
     Done only in a bundle, and with A missing (`unresolved`). A control with A `Ready`: B is on the
     path and is NEXT — so the emptiness above comes from A's state, not from the fixture;
   - (g) every `blocked` node in every fixture has ≥ 1 direct blocker or ≥ 1 blocked cross-repo
     prerequisite (extends the existing property check).
   `tests/test_trail_gather.py` `CriticalPathVerbTests`, add the **completed outside root**: only
   Done non-member A highlighted, A's file lists Ready member B → `NOT_IN_TRAIL:A|done|-`, and no
   `PATH:`, `BLOCKED_BY:` or `NEXT:` line (`SUMMARY:…|path=0|…|not_in_trail=1|…|next=0|…`). And the
   **mixed case**: only non-member A
   highlighted, A depends on open member B, B's live depends names bundle-only Done C (a member) →
   `NOT_IN_TRAIL:A|open|-`, `BLOCKED_BY:A|B|…|depends|open|-`, `PATH:B|…|depends|open|blocked|…`,
   `BLOCKED_BY:B|C|…|depends|unresolved|bundled`, `LANDED:C|…|bundle`, no `NEXT:`, no `HIGHLIGHT:`
   and no `BLOCKER:` line. Add the same tree to the CLI/TUI parity list, asserting the card texts:
   B reads `» critical path · blocked · t<C> unresolved (bundled)`, C keeps ✔ and carries no path
   marker. A second parity case with B itself highlighted: `★ direction · blocked by 1 · t<C>
   unresolved (bundled)`.
8. **§6 card notes**: no new marker and no new lookup. `overlay_for_entry` reads the node's
   `blocked_by` edges from the result it already receives. When one of them is a bundled edge, the
   note names that prerequisite and its reason after the standard text:
   `★ direction · blocked by <n> · t40 unresolved (bundled)` (highlighted) and
   `» critical path · blocked · t40 unresolved (bundled)` (path); with several bundled prerequisites
   the first in (wave, ref) order, then ` +<k>`. Other blockers keep the standard note. The bundled
   prerequisite's own card keeps ✔ with no path marker.
9. **§8 Docs**: the how-to's "what blocks and what does not" list gains the bundled-prerequisite
   case and the non-member highlight.
10. **§9 note to t2335_4**: add `BLOCKED_BY:` (including its partial meaning for a `NOT_IN_TRAIL`
    ref), the bundled rule, the outside-only rule and the two-freshness rule.
11. **Round table**: one row in "Plan review — concerns addressed", headed "t2367 review
    (2026-11-26)", pointing at the new section.
12. **New section `## Critical-path rule review`** (after "Advice contract", before
    "Implementation"): one line per point 1–9 with `confirmed` / `corrected` and its source; for each
    correction the exact change (the edits above, by plan section); the user's answer on point 7
    quoted verbatim.

Then commit only that plan file:
`./.aitask-scripts/aitask_task_commit.sh -m "ait: Record critical-path rule review in t2335_3 plan (t2367)" aiplans/p2335/p2335_3_trails_highlight_and_critical_path_overlay.md`

## Verification

- `grep -n '^## Critical-path rule review' <plan>` → one hit, 9 point lines.
- Re-read the edited Semantics / Advice contract / protocol for internal consistency: the readiness
  precedence still asserts `blocked` ⇒ ≥ 1 blocker (the bundled live edge supplies a direct one);
  "a done node is never on the path" still holds; every place that says "depends edge" names live
  or saved where the bundle rule makes them differ.
- `grep -n 'bundled' <plan>`: each hit is on a live-edge rule, a fixture or the consumer contract;
  none on a saved or wave edge except to say it is satisfied.
- `git show --stat HEAD` on the data branch names only the plan file.

## Risk

### Code-health risk: low
None identified. The change edits one plan file and no code. The corrections add rules to a plan that
is force-reverified when t2335_3 is next picked.

### Goal-achievement risk: low
None identified. Each verdict cites its source, the one point the sources could not decide was
answered by the user, and the edited plan is reviewed at Step 8 before the commit.

## Step 9 (Post-Implementation)

No code commit (plan-only change). Archive t2367 per Step 9. t2335_3's next pick force-reverifies its
plan because this mitigation landed (§6.0a).

## Post-Review Changes

### Change Request 1 (2026-11-27 01:10)
- **Requested by user:** the §4 protocol note said a bundle-only live dependency prints in both `BLOCKER:` and `BLOCKED_BY:`, which contradicts the mixed fixture (only outside A highlighted → `BLOCKED_BY:` for B's bundled blocker and no `BLOCKER:` line). Qualify the protocol; keep the fixture unchanged.
- **Changes made:** the §4 note now states the scope of each line: `BLOCKED_BY:` is always printed for the edge, keyed to the dependent; `BLOCKER:` stays transitive and scoped to highlighted trail members, so a run whose only highlight is outside the trail prints none. The "Blockers" bullet in "Semantics → Sets" says "of a highlighted **member**" and that a not_in_trail highlight has none. The fixture is unchanged.
- **Files affected:** `aiplans/p2335/p2335_3_trails_highlight_and_critical_path_overlay.md`

### Change Request 2 (2026-11-27 01:23)
- **Requested by user:** the revised §4 note promised that `BLOCKED_BY:` is always printed for a bundled live dependency. A gate-released highlighted member with such a dependency keeps readiness `released`, and the direct-blocker rule and the line format restrict `BLOCKED_BY:` to `blocked` nodes and expanded outside highlights. Replace the promise with the existing emission conditions and keep transitive `BLOCKER:` evidence keyed to the highlighted member.
- **Changes made:** the §4 note now states `BLOCKED_BY:`'s emission conditions (a `HIGHLIGHT` member or `PATH` node with readiness `blocked`, or an expanded `NOT_IN_TRAIL` ref) and names the released case as printing none. `BLOCKER:` is described as transitive and keyed to a highlighted member whatever its readiness, so the released member's bundled dependency appears there and in its `<n blockers>` count.
- **Files affected:** `aiplans/p2335/p2335_3_trails_highlight_and_critical_path_overlay.md`

## Final Implementation Notes
- **Actual work done:** Reviewed the nine points of t2335_3's critical-path rule and advice contract against the schema, the validator, the trail docs, `dep_resolution.py`, `cross_repo_deps.py`, `aitask_ls.sh` and the sitrep freshness contract. Edited `aiplans/p2335/p2335_3_trails_highlight_and_critical_path_overlay.md` in place and added its `## Critical-path rule review` section: points 1–4 and 9 confirmed, points 5–8 corrected. The corrections: the bundled-Done rule (live depends edge blocks as `unresolved:bundled`; saved fallback and wave-hard edges are satisfied; the dependent's card names the prerequisite), a total rule for a highlighted non-member (own state first, live depends on members as ordinary edges, no readiness), direct blocker evidence (`CriticalPath.blocked_by`, `BLOCKED_BY:`), `NOT_IN_TRAIL:<ref>|<state>|<reason>`, four consumer rules in the advice contract, and the fixtures that pin them. No code changed.
- **Deviations from plan:** None in scope. Two additions beyond the numbered edits: a sentence in §3 saying a bundle-only Done task is recognised by `reason="bundle"`, and the Post-Review Changes above (the `BLOCKER:` / `BLOCKED_BY:` scope note in §4).
- **Issues encountered:** The task-data sync at claim time warned that unstaged changes from other sessions block the rebase (`ait syncer` reconciles). It did not affect the edits or the path-scoped commits.
- **Key decisions:** Point 7 was not decidable from the sources (`ait ls` never reads bundles; the trail cards do), so the user decided it; the answer is quoted verbatim in the review section. `BLOCKED_BY:` is a separate line and not a wider `BLOCKER:`, so `BLOCKER:` keeps its meaning (transitive, per highlighted member) and the `<n blockers>` count on `HIGHLIGHT:` still matches it. `implemented_with` is `claudecode/fable5_2`: the session's model changed mid-run, while the launch-time `AITASK_AGENT_STRING` still read `claudecode/opus5_5`.
- **Upstream defects identified:** None
