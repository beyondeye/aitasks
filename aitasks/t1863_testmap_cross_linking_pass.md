---
priority: medium
effort: low
depends: []
issue_type: chore
status: Ready
labels: [testmap, task-planning, dependencies]
gates: [risk_evaluated]
anchor: 1852
followup_kind: risk_mitigation
created_at: 2026-09-22 17:32
updated_at: 2026-09-22 17:32
---

## Origin

Risk-mitigation ("after") follow-up for t1852, created during t1852's coarse
planning pass (2026-09-22) rather than at Step 8d, because that pass stopped
at the child checkpoint and would never have reached Step 8d. Recorded in
`aiplans/p1852_testmap_m1_engine_foundation_and_distribution.md` under
`### Planned mitigations` as `testmap_cross_linking_pass`.

## Risk addressed

goal-achievement — cross-parent edges named by the wrong child number.
From the t1852 plan's `## Risk` section: "Cross-parent edges (M2.1 / M2.3 /
M3.1 / M5.1 / M6.1 → M1 children) are written by other parents' passes; if a
later pass names a child by the wrong number, the graph silently unblocks work
early."

## Goal

The test map feature (`aidocs/testing_engine/n014_explorer_006_proposal.md`)
is ten parent tasks t1852–t1861, one per module, each decomposed at its own
coarse planning pass into one child per submodule row. Cross-module order is
expressed in task data: a child's `depends:` names the children of other
parents it consumes, in `t<parent>_<m>` form. This task is the **one
cross-linking pass** the parents' bodies prescribe "after all ten parents are
planned": it checks every "depends on" cell against a real `depends:` entry,
checks the module → task map in every parent body against the real parent
ids, then refreshes the trail `art:trail-testmap-feature` with `--deep`.

Passes run in wave order at submodule granularity (M1's children are
implemented before M2 is planned), so by the time the last pass lands, early
children are **archived**. This task treats archived records as complete
evidence and repairs only pending tasks.

### Step 0 — completeness precondition (all-or-nothing, before any write)

`aitask_query_files.sh has-children` proves nothing here: it succeeds on any
positive local file count, and `children_to_implement` grows incrementally
during creation, so an interrupted or in-progress pass looks "decomposed".
Validate every prescribed submodule of every parent instead:

- For each parent t1852–t1861, resolved from **active or archived** records
  (`./.aitask-scripts/aitask_query_files.sh resolve <id>`, else
  `archived-task <id>`; `aitask_archive.sh` moves a finished parent and its
  children to `aitasks/archived/t<parent>/` and `aiplans/archived/p<parent>/`),
  parse its `## Submodules` table for the `**M<n>.<m>**` rows.
- For every row **not** marked `(cross-repo)`: require exactly one child file
  whose stem carries `m<n>_<m>_` across `aitasks/t<parent>/` and
  `aitasks/archived/t<parent>/`, **and** its plan file —
  `aitask_query_files.sh plan-file <parent>_<k>` (active) else
  `aiplans/archived/p<parent>/p<parent>_<k>_*.md` — containing the
  `Step 0 — Reality check` heading. An archived child with its archived plan
  is complete evidence (a landed provider), never `INCOMPLETE`.
- For every row marked `(cross-repo)` (today M10.2–M10.5 in t1861): require
  the parent's plan file to carry the cross-repo decomposition record
  (`.claude/skills/task-workflow/planning-cross-repo.md` Step 6: the
  `label | side | nominal parent | in-repo deps | cross-repo deps` table)
  with one entry naming that row and its target project as registered in
  `ait projects list`.
- Any missing item → print `INCOMPLETE:t<parent>:M<n>.<m>:<reason>` for each,
  then **stop with no dependency writes**; re-pick when the remaining passes
  have landed.

### Step 1 — graph check and repair, pending local rows only

For every local row whose child is **pending** (active and not `Done`):
check each "depends on" cell of the parent's submodule table against a real
`depends:` entry in `t<parent>_<m>` form on that child, and fill only the
missing ones with `./.aitask-scripts/aitask_update.sh --batch <child> --deps
"<current + missing>"` (`--deps` **replaces** the list — read it first).
Archived or `Done` children are **never** updated: a landed provider's edges
are history, and a dependency *on* an archived child is already satisfied,
so it is neither added nor required.

**M10.2–M10.5 are never repaired with local ids.** They live in their target
repositories, are referenced with `<project>#<id>` notation
(`aidocs/framework/cross_repo_references.md`), and depend on the framework
release carrying M1–M9 reaching each target rather than on this repository's
task ids (t1861 body). For them, only check that the cross-repo record names
each row and that any already-created cross-repo task carries the
project-qualified reference (`xdeps` + `xdeprepo`, both-or-neither);
mismatches are **reported, never rewritten** from here.

**Supplementary automation consumer:** also audit
[t1853_7](t1853/t1853_7_automate_testmap_repair_for_existing_codebases.md),
the user-requested full check–repair–recheck automation sibling. Its
`Dependencies and cross-references` table is an additional source of consumer
edges beyond the original module rows. Resolve those module references to real
active or archived provider children, preserve its existing dependencies, and
add missing pending-provider edges. Keep its dependency hold until every row
is resolved; then set it Ready if it is still Postponed solely for that hold.
Do not require this supplementary consumer's implementation plan as an extra
Step 0 precondition, or depend back on it from its base providers. Report its
unresolved rows in the dry run and include it in the refreshed trail.

Then check the module → task map in every parent body against the real
parent ids, and refresh the trail:
`/aitask-trail --refresh trail-testmap-feature --deep`.

`depends: []` on purpose — a `depends:` on the parents would block this task
until they are *Done*, far too late; Step 0 is the real gate.

## Verification

- Dry run first: print every `INCOMPLETE:` / mismatch line before any write.
- After repair, `./.aitask-scripts/aitask_ls.sh -v --children <parent> 99`
  for every parent shows blocked/unblocked exactly per its submodule table.
- The refreshed trail lists child tasks grouped by wave.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1853** id=2026-10-11T14:44:15Z.e9e2f360d57c16e0c10bbc0a from=t1853 at=2026-10-11T14:44:15Z base=3bc0de8ac7a9c9d1f60173e1257715a744efc451 base_branch=main dirty=yes host=omg16
>
> | Advisory, from the t1853 (M2) coarse pass (proposal commit 3bc0de8ac; t1853's `## Submodules` table synced to it).
> | 
> | - t1853 is decomposed: t1853_1..t1853_6 = M2.1..M2.6. Child depends: _1 [], _2 [t1853_1], _3 [t1853_2], _4 [t1853_1], _5 [t1853_1], _6 [t1853_1, t1853_2].
> | - **Pending edge:** M2.4 → M3.1. t1853_4's body names "M3.1 (pending: t1854 not decomposed)"; t1854's pass was asked to add it. Check it at your Step 1.
> | - M1.2 edges (M2.1, M2.3 → t1852_2) are deliberately omitted because t1852_2 is archived (your rule: satisfied, neither added nor required).
> | - The "depends on" column is the last column in the proposal's Module Map and the second-to-last (before wave) in parent `## Submodules` tables. Scope cells contain escaped `\|`, so extract by counting fields from the end (awk `$(NF-1)` / `$(NF-2)`), not from fixed left offsets.

> **✉ note:t1854** id=2026-10-13T16:21:29Z.16a285e4ce6becb529a7276f from=t1854 at=2026-10-13T16:21:29Z base=6a3a81efc30577c762d42f815f3e95eac95b4e3f base_branch=main dirty=no host=omg16
>
> | Advisory, from the t1854 (M3) coarse pass. The proposal's M3 cut was fixed in 6a3a81efc; the t1854 `## Submodules` table is synced with it. The edges below are as committed now; the audit should verify them, not assume them.
> | 
> | **Real `depends:` entries written:**
> | - t1854_2 → t1854_1
> | - t1854_3 → t1854_1, t1853_5
> | - t1854_4 → t1854_1, t1853_5
> | - t1853_4 → t1853_1, t1854_1: the pending M3.1 edge, now wired; its body no longer says "pending".
> | - t1853_7 → t1853_1..6 + t1854_1: its provider-table M3.1 row is annotated; it is still Postponed for its other rows.
> | 
> | **M3 "depends on" cells in the proposal and t1854:** `M1.2, M2.1, M2.2` / `M3.1` / `M3.1, M2.5` / `M3.1, M2.3, M2.5`.
> | - M1.2 (t1852_2), M2.1 (t1853_1), M2.2 (t1853_2) and M2.3 (t1853_3) are archived, so they are omitted from `depends:` as satisfied.
> | - M2.5 maps to t1853_5; M3.1 maps to t1854_1.
> | 
> | **Other row edits that change no dependency:**
> | - M2.4 no longer lists "cost" among its provides.
> | - M6.4 gains the `SCAFFOLD_TODO` `check` report.
> | - M10.1 gains the serial carve-out drift-test pin.

> **✉ note:t1954_4** id=2026-10-14T18:37:32Z.da5cb1d9577c6da4fa4d5505 from=t1954_4 from_verified=yes at=2026-10-14T18:37:32Z base=f8d4b2ef54e729ae6e7ee76c1ba3f63395660f14 base_branch=main dirty=yes host=omg16
>
> | t1954 (multi-language annotation parsers) is complete. The research-result handoff this task was told to preserve is now resolved. Verdict: action (cross-links).
> | - Report: aidocs/testing_engine/t1954_annotation_parser_research.md
> | - Evidence artifact: art:t1954-researchevidence (owner t1954, kind research_evidence)
> | - Follow-ups, anchor 1852, all advisory:
> |   - t1990: annot Kotlin multi-dollar fix;
> |   - t1991: annot conformance suite;
> |   - t1992: shared Kotlin-family lexer evaluation, after t1990.
> | - Trail: art:trail-testmap-feature, new deep version, entry e-parser-research.
> | - Please link these in the cross-linking pass. Consumer verdicts: report section 12 (actions for t1857, t1858, t1853_7, t1860; context for t1855, t1861).

> **✉ note:t1992** id=2026-10-15T22:35:50Z.763dc8603fa7e3bdcc801e03 from=t1992 from_verified=yes at=2026-10-15T22:35:50Z base=25b145da77a96b402c146b89a340243a6d0a3440 base_branch=main dirty=no host=omg16
>
> | Advisory context from t1992, for the cross-linking pass: the outcome of the "shared Kotlin-family lexer evaluation" follow-up, which t1954's report §13 lists as pending. Tree-relative claims are dated by this note's base commit.
> | 
> | - **Decision:** no shared lexical core for annot (`annot/lexctx.go` classifyKotlin), `deps/kotlinlex.go` and the kts mode of `deps/gradlelex.go`.
> |   - The decision record, with criteria C1–C6, every divergence and every script verbatim, is in t1992's plan: `aiplans/archived/p1992_kotlin_family_shared_lexical_core_evaluation.md` once archived.
> |   - It was measured against the real KotlinLexer 2.3.20 over 71 fixtures, 2051 real Kotlin files of the registered repositories (recorded commits), and 40 construct rows.
> | - **Safeguard landed:** `goengines/internal/testmap/deps/kotlinfamily_test.go` (code commit 25b145da7):
> |   - a construct table pinning all three lexers against the real lexer;
> |   - a cross-lexer differential over every Kotlin fixture of annot and deps.
> | - **Follow-ups filed (anchor 1852):**
> |   - t2030 `kotlin_shebang_line_hides_deps`: a shebang holding `{`/`(` silently hides declarations from the deps scanner (unsafe direction) and annot's package anchor;
> |   - t2033 `ktlex_raw_string_content_keeps_crlf`: harmless.
> | - **Possible link targets:** the t1954 report's §1/§7/§13 and §8.3 (the Kotlin language-version row still says multi-dollar "not failed closed (t1990)"; t1990 landed, and annot now models it). Whether and how to link is yours to decide.

> **✉ note:t1859** id=2026-10-19T12:47:18Z.5619eb1f34aeac68e1e918e8 from=t1859 at=2026-10-19T12:47:18Z base=bf32b336c0b0673eccba125bf097df173405e8d7 base_branch=main dirty=yes host=omg16
>
> | Advisory, from the t1859 (M8) coarse pass. Proposal fix: commit bf32b336c.
> | 
> | - **Children.** t1859 has six:
> |   - t1859_1 (M8.1, Ready);
> |   - t1859_2..5 (M8.2..M8.5);
> |   - t1859_6 (the M8.3 seeds step, a separate child per Dev 6).
> | 
> |   t1859_2..6 are Postponed with Dependency holds until t1855, t1856 and t1858 wire M4.2/M4.3/M4.4, M5.1/M5.2 and M7.1/M7.2.
> | - **New edges:**
> |   - t1853_7 → t1859_2, t1859_3 (written);
> |   - M5.1 → t1859_1 (pending t1856);
> |   - M6.5 → t1859_3 (pending t1857; new in Dev 12).
> | - **Omitted.** M8.2 → M2.1/M2.6 are archived and left out.
> | - **The parent table** has a seeds-step row, "M8.3, M7.1, M7.2", that the proposal expresses as "M4.2, M4.3; seeds step: M7.1, M7.2" in the M8.3 cell.

> **✉ note:t1854_2** id=2026-10-21T19:10:49Z.db49687dc6929bae21e3b920 from=t1854_2 from_verified=yes at=2026-10-21T19:10:49Z base=5582dd4f455372f5ba40a43b6d2dffe2101089b3 base_branch=main dirty=no host=omg16
>
> | Advisory, from t1854_2 (the M3.2 re-decomposition, 2026-10-21). Edges are as of the commit this note records.
> | - The M3.2 edge "t1854_2 → t1854_1" is now one of eleven sibling edges: t1854_2 and t1854_5 – t1854_14.
> | - Other edges changed: t1854_3 now also depends on t1854_6; t1859_4 depends on t1854_12 + t1854_7 instead of t1854_2; t2082 depends on t1854_8 – t1854_11.
> | - New standalone tasks: t2117, t2118 (both Postponed, depend on t1854_14) and t2119 (depends on t1854_6, t1854_7).
> | The full table is in parent t1854, section "M3.2 re-decomposition (2026-10-21)".

> **✉ note:t2131** id=2026-10-23T08:56:20Z.27657fadca978efbab717e49 from=t2131 at=2026-10-23T08:56:20Z base=6b3161606e2989d1865628155f4e0bc1021cb917 base_branch=main dirty=yes host=omg16
>
> | For the cross-linking audit: t2131 (test-map code-module tier, anchor 1852) was decomposed into t2131_1 … t2131_12. The edges to check:
> | - **Inside the parent:**
> |   - t2131_3 ← t2131_1;
> |   - t2131_4 ← t2131_3;
> |   - t2131_5 ← t2131_3;
> |   - t2131_6 ← t2131_5;
> |   - t2131_7 ← t2131_6;
> |   - t2131_9 ← t2131_5;
> |   - t2131_11 ← t2131_8, t2131_9;
> |   - t2131_12 ← t2131_7, t2131_8.
> | - **To other parents:**
> |   - t2131_8 ← t1859_4, t1859_5;
> |   - t2131_10 ← t1854_11.
> | - **Dependency holds, still unresolved:**
> |   - t2131_7 on M4.1, M4.4 and M4.5;
> |   - t2131_8 on M4.4;
> |   - t2131_12 on M4.4;
> |   - t2131_9 on M6.1, M6.4 and M6.5;
> |   - t2131_11 on M6.5.
> | 
> |   t1855 and t1857 were each sent a note asking their coarse pass to wire these ids.

> **✉ note:t15** id=2026-10-25T08:54:08Z.e579a3f36eda41f731f8812b from=aitasks_go#t15 at=2026-10-25T08:54:08Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
>
> | Coordination notice from aitasks_go (t15 ship-path decision; schedule in trail
> | art:trail-go-ship-path owned by aitasks_go#t22). Advisory context, not an
> | instruction. It does not change this task's scope.
> | 
> | WHAT IS PLANNED
> | ait-testmap Go development (public goengines/) will move ONCE into the private
> | aitasks_go repository, at a cutover performed by aitasks_go#t22. After that,
> | goengines/ here receives exported snapshots only (no tests, bench or ci), and
> | engine work happens in aitasks_go. As of 2026-10-25 the cutover has no date.
> | Its prerequisites are aitasks_go t20 and t21 and aitasks t2138.
> | 
> | UNTIL THE CUTOVER: CONTINUE THIS TASK HERE, AS NORMAL
> | To keep the cutover cheap and safe:
> | 1. Land goengines/ changes on main promptly. Avoid long-lived branches,
> |    worktrees or unmerged PRs touching goengines/, because the cutover has to
> |    wait for, or hand off, every one of them.
> | 2. Keep engine commits (goengines/**) separate from framework-side commits
> |    (the aitask_testmap.sh shim, installer/setup, skills, docs, aitestmap/).
> |    Mixed tasks will be split along that line, and separate commits keep both
> |    the split and the history migration clean.
> | 3. If goengines tests start reading data from outside goengines/ (as with the
> |    t1954 corpus under aidocs/testing_engine/), record that path in this
> |    task's plan. The migration must copy it into the private module.
> | 4. Add no new Go binary or non-testmap package to goengines/. ait-monitord is
> |    being re-homed to aitasks_go (aitasks_go#t23), and ait-tui is developed
> |    there.
> | 5. Keep the contracts and guards as usual: the dependency allowlist, the
> |    Invariant 4-5 tripwire, the hang guard, bench baselines, and the
> |    version/verb/exit-code interface. The migration carries them over verbatim
> |    and checks that nothing changed.
> | 
> | FREEZE PROTOCOL
> | Shortly before the cutover, aitasks_go#t22 will send this task a
> | "goengines freeze in effect" note. From that note until a matching
> | "goengines freeze lifted" note, do not claim or start goengines work here. A
> | task that is Implementing or locked at that time is never relocated under its
> | agent: t22 waits for it to land, or arranges an explicit checkpointed handoff
> | (commit/push, handoff note, release the lock, back to Ready).
> | 
> | AFTER THE CUTOVER
> | If this task still has engine work pending, it is re-homed to aitasks_go
> | (engine-only) or split (the Go part there, the framework part here), and the
> | original carries a pointer. Framework-side work (the shim, installer, skills,
> | docs, aitestmap/ and the n014 spec) stays in this repository permanently. An
> | emergency public fix to goengines/ after the cutover needs a
> | `Return-To: aitasks_go` trailer plus a return task in aitasks_go
> | (`ait create --batch --project aitasks_go`).

> **✉ note:t22_3** id=2026-10-29T22:23:15Z.9ce37698069bfd9ef4fc317f from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:23:15Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.

> **✉ note:t22_4** id=2026-10-30T10:12:50Z.184097b99380f5a63832065e from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:12:50Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | The testmap cross-linking graph now spans two repositories. Engine tasks
> | moved to beyondeye/aitasks_go (see aitasks_go
> | aidocs/aitasks_go/testmap_cutover.md, "Relocation map"). Cross-repo edges
> | are xdeps (xdeprepo: aitasks_go) and unblock only when the target is Done.
> | Do not add depends to Postponed pointer originals; link the aitasks_go
> | replacement instead.
