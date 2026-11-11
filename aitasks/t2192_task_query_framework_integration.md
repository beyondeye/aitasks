---
priority: medium
effort: high
depends: []
xdeps: [93]
xdeprepo: aitasks_go
issue_type: feature
status: Ready
labels: [go_engine, install, skills, task_relations]
gates: [risk_evaluated]
created_at: 2026-11-04 08:54
updated_at: 2026-11-04 08:54
---

## Goal

Make the task-query engine (aitasks_go#93) usable from the framework. Install
it, expose it through `ait`, keep a fallback for when it is absent, and wire it
into the skills that search tasks today.

## Context — read first

- `aidocs/framework/task_search_analysis.md` (committed in `aa67dd50e`): why
  grep-based task search costs what it does, the comparison with GitHub Issues
  and beads, the measurements, and the layered direction. This task is the
  framework-side half of layers L1 and L2.
- The engine itself is **aitasks_go#93**. The work is split along the
  repository line: engine in aitasks_go, shim, installer, skills and docs here.
  This task waits for it through `xdeps`. Read its landed interface (the
  `goengines/README.md` *Interfaces* mirror) before planning, because verb
  names and the output protocol are settled there.
- How candidates become recorded relations, and how the notify list at task
  completion is consumed, is **t1981**'s decision. Coordinate; do not
  duplicate.

## Scope

1. **Install.** `lib/engine_install.sh` stages, verifies and publishes only
   `ait-testmap` (plus its `.sha256` sidecar). Extend it to the new executable
   while keeping SHA256SUMS verification, the `.dev` marker, `ait engine prune`,
   the `ait engine build` dev slot, `--local-engine`, `--force-engine`,
   `--no-testmap` and `AIT_TESTMAP_FETCH=0`. Decide whether those opt-outs
   cover the new binary or it gets its own (the `TESTMAP` names are
   testmap-specific). Read `aidocs/framework/go_engine.md` and
   `aidocs/framework/aitasks_extension_points.md` (install flow, PATH and
   binary shimming) first.
2. **Shim and fallback.** Add an `ait` verb through a
   `.aitask-scripts/aitask_<name>.sh` shim that resolves the engine from the
   slot for `.aitask-scripts/VERSION`, as `aitask_testmap.sh` does. When the
   engine is absent, a fallback must answer. Either a Python path built on
   `lib/plan_paths.py` and `lib/task_yaml.py` covers the subset it can, or a
   distinct absent-engine line tells consumers to fall back to grep. Every
   answer states which path produced it.
3. **Helper whitelist.** The touchpoints for a helper invoked from skills
   (`aidocs/framework/aitasks_extension_points.md`).
4. **Skill integration** (Claude Code first; separate port tasks for the other
   agent trees):
   - `/aitask-note` Related Task Discovery: candidates from `mentioned-by`,
     `mentions` and `cited-by`, triaged with cards, instead of titles, labels
     and the first ~5 body lines.
   - `/aitask-trail`: cards for `new_related_task` neighbours, and member path
     surfaces for shared-file collisions. Today the gatherer extracts paths
     for in-flight tasks only. Extend the gatherer's pinned contract rather
     than forking it.
   - `/aitask-create`: an advisory "does this already exist?" check before
     creating. It never blocks.
   - The notify offer at task completion: candidates only, coordinated with
     t1981.
5. **Docs.** Website docs for the new `ait` verb, following
   `aidocs/framework/documentation_conventions.md`. Regenerate goldens for any
   `.md.j2` or procedure change in the same commit.

## Requirements

- Helpers report evidence; the agent judges. No relevance thresholds in skill
  prose.
- The fallback has its own tests, run with the engine absent. Exit statuses
  survive pipelines (check `PIPESTATUS`, never `| tail`).
- Tests never touch a real `~/.aitask` or `AITASKS_HOME`; use a scratch `HOME`.
- Where the Python fallback and the engine overlap they must agree. Decide at
  planning whether that is pinned here or by aitasks_go#93's differential test.

## Out of scope

- The relations store and its consumption policy (t1981).
- Semantic re-ranking.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1981** id=2026-11-04T13:37:48Z.fb0f0ac669702e7e849fa9f2 from=t1981 from_verified=yes at=2026-11-04T13:37:48Z base=5026118e29a2635e34760ae91d842f73fd6078e6 base_branch=main dirty=yes host=omg16
>
> | From t1981 (task relations and obsolescence). Advisory: this is the boundary t1981's design settled between its children and your scope. Reply by note if it conflicts with your plan.
> | 
> | Design: aidocs/framework/task_relations.md (commit 5026118e2), sections D6 and D8.
> | 
> | - Step 8e (the notify offer at task completion) is owned by t1981_5. Please do not edit Step 8e. t1981_5 also adds a "store first" step to /aitask-note's no-target path, ahead of the Related Task Discovery Procedure. Your engine-based upgrade of that procedure stays yours, and it is what /aitask-note falls back to.
> | - aitask-explore, aitask-fold and aitask-contribution-review keep your engine-based discovery. t1981 does not change them in v1.
> | - t1981_2 (the candidate generator) depends on t2192 and consumes your shim's verbs: mentions / mentioned-by, cites / cited-by, card and search. It needs to know which path answered (engine or fallback) and which verbs did not answer. Your Scope item 2 leaves the form open; any form works as long as a missing or failed verb is reported explicitly, never as an empty result. t1981 treats a missing core verb (mentions, cites) as a failed job, and a missing optional verb (search) as missing coverage.
> | - Path-grammar extensions (more extensions, suffix resolution of bare basenames) stay in your one-grammar-or-pinned-differential scope. t1981 builds no private copy.

> **✉ note:t110** id=2026-11-10T07:51:17Z.95ea32250704cdae6e988e67 from=aitasks_go#t110 from_verified=yes at=2026-11-10T07:51:17Z base=0e17732b1e5f4d2b3849a80cf3000e2ddf2b22d2 base_branch=main dirty=no host=omg16
>
> | Advisory from aitasks_go t110: aitasks_go will move its YAML dependency from the archived gopkg.in/yaml.v3 v3.0.1 to the YAML org's maintained v3 line, go.yaml.in/yaml/v3 (v3.0.6 tested), in aitasks_go task t114.
> | 
> | Impact on the public side: .github/scripts/goengines_integrity.sh CLOSURE_ALLOWED_MODULES must accept go.yaml.in/yaml/v3 before a promoted engine requires it. aitasks_go's three private mirrors are goengines/guards_test.go allowedDeps, promote/checks.go closureAllowlist, and promote/checks_test.go TestClosureViolations.
> | 
> | Evidence as of aitasks_go 6168932: an import-only rewrite; suites green; a zero-change per-file frontmatter differential over 6342 live files plus the committed corpus/fuzz; performance equal. No action is needed until t114 is picked. This note is for ordering and coordination only.

> **✉ note:t93_3** id=2026-11-11T17:02:15Z.4a3b711ae7f092974a61b2af from=aitasks_go#t93_3 from_verified=yes at=2026-11-11T17:02:15Z base=47212a7f2f5e27f87b066faf91fca5e977748998 base_branch=main dirty=yes host=omg16
>
> | From aitasks_go#t93_3 (task-query engine, ait-taskquery): the query verbs card, mentions, mentioned-by, cites and cited-by have landed (aitasks_go commit 86e343aca824). Advisory: these are the settled shapes your shim consumes. The canonical source is the private goengines/README.md, Interfaces → "ait-taskquery", where every row is pinned by a named test. search is still a stub (aitasks_go#t93_4).
> | 
> | Repository targeting
> | - --root <dir> names the repository. The engine never resolves --project: the shim runs `ait projects resolve` and passes --root. With no --root, the engine uses the nearest ancestor of the cwd that holds aitasks/metadata/.
> | - --project-name <name> overrides the identity, which otherwise comes from project_config.yaml project.name, else the root's basename.
> | 
> | Answer frame (every query verb)
> | - PROJECT:<name>|<flag|config|basename>
> | - CORPUS:<branch|legacy>|<root>
> | - the verb's rows, its summaries
> | - NOT_FOUND:<ref>
> | - the scoped problem lines (UNREADABLE, VANISHED, DECODE_REPLACED, FRONTMATTER_ERROR, ZSTD_UNAVAILABLE, PROJECT_CONFIG, DUPLICATE, and RESOLVE_UNAVAILABLE for cites --resolve)
> | - then COVERAGE:complete or COVERAGE:partial|<n>
> | 
> | Exit codes: 0 complete; 1 partial or a queried id NOT_FOUND; 3 framework (NOT_AITASKS_ROOT, IDENTITY_INVALID, SCAN_ERROR, OUTPUT_ERROR, all on stderr); 64 usage (a reason line, then USAGE:<verb usage> on stderr, before any scan). An empty answer is MENTIONS:<ref>|0|0 or FAN_IN:<path>|0 with exit 0, never a failure. Every field is percent-escaped (% → %25, | → %7C, LF → %0A, CR → %0D), and <file>:<line> splits at its last ":".
> | 
> | Coverage scope (new): a problem counts only if it affects the answer.
> | - Task-side and repository-level problems are printed and counted.
> | - Plan side, with --plans: everything but FRONTMATTER_ERROR counts (no verb reads plan frontmatter).
> | - Plan side, for card without --plans: the presence classes count (ZSTD_UNAVAILABLE, UNREADABLE, VANISHED).
> | - Otherwise plan problems are neither printed nor counted.
> | - DUPLICATE is printed when in scope, never counted. An unknown class is printed and counted.
> | - Effect: `--archivebundles` on aitasks is now complete (the 12 archived-plan FRONTMATTER_ERRORs that Python also fails on no longer make every answer partial).
> | 
> | Verbs (batch: one scan per process)
> | - card <id>...:
> |   - CARD:<ref>|<status>|<priority>|<effort>|<type>|<labels,>|<location active|archived|bundle>|<path>|<plan path or ->
> |   - CARD_REL:<ref>|<field>|<refs,> for parent, children, children_to_implement, depends, anchor, verifies, folded_tasks, folded_into, risk_mitigation_tasks
> |   - UNRESOLVABLE_ID:<ref>|<field>|<raw JSON>
> |   - CARD_CITES:<ref>|<path>|<count>|<tier>|<anchored count>
> |   - CARD_MENTIONS:<ref>|<target>|<count>
> |   - CARD_GOAL:<ref>|<escaped paragraph>
> | - mentions <id>... / mentioned-by <id>...: MENTION:<from>|<to>|<source>|<tier>|<file>:<line>, then MENTIONS:<ref>|<hits>|<distinct tasks>. mentioned-by takes any project's ref, e.g. aitasks#1981.
> | - cites <id>...: CITE:<ref>|<path>|<source>|<tier>|<full|bare>|<anchor -|L<n>|L<n>-<m>>|<file>:<line>. --anchored keeps the anchored rows. --resolve adds CLASSIFY:<token>|<malformed|tracked|planned_new|phantom> (plan_paths.classify against one `git ls-files -z`) and RESOLVES:<token>|<tracked>|<bare|suffix>.
> | - cited-by <path>...:
> |   - CITE rows with kind full|bare|suffix, then FAN_IN:<path>|<distinct citing tasks>; --count prints only FAN_IN.
> |   - It uses the find_references grammar, so there is no extension list.
> |   - Each queried path is matched alone, so a batch answer equals the single runs.
> | - --json: one document per run (keys project, corpus, the verb's arrays, not_found, problems, coverage). anchor is {"start":n,"end":m} or null.
> | 
> | Vocabulary
> | - Sources: description, plan, inbox_note (a note marker's parsed from=, a claim), inbox_body, gate_ledger, folded_history, meta:<field>. --sources meta selects every meta:<field>.
> | - Tiers: compat, ext. A tier names the grammar of the verb that found the row: cites, mentions and card use plan_paths.extract and A.1 plus the ext forms; cited-by uses find_references (compat) plus a basename-only kind (ext). So one a.go occurrence is ext in cites and compat in cited-by.
> | - Ext forms: path extensions go kt kts ts tsx js rs java gradle j2 txt; <project>:<path>; <project>#t?<id>; t<id>_slug.md / p<id>_slug.md; in cited-by, the basename-only kind.
> | 
> | Filters: --status <csv> | --pending (Ready, Editing, Implementing, Postponed) restrict the citing universe of mentioned-by and cited-by; a plan takes its task's status. --archived, --archivebundles (implies --archived), --plans (opt-in), --sources <csv>, --tier compat|ext. Flags interleave with positionals, and -- ends the flags.
> | 
> | Closure check: the public goengines_integrity.sh closure check (CLOSURE_ALLOWED_MODULES and the binaries it builds) names only ait-testmap and monitord. ait-taskquery is in the export manifest and in promote's closureCommands (t93_1), so the public check needs ait-taskquery added.

> **✉ note:t114** id=2026-11-11T17:30:43Z.2927b7e81354555bfe804adc from=aitasks_go#t114 from_verified=yes at=2026-11-11T17:30:43Z base=47212a7f2f5e27f87b066faf91fca5e977748998 base_branch=main dirty=yes host=omg16
>
> | Follow-up to the t110 advisory above: aitasks_go t114 has landed as commit da80ee4 on aitasks_go main. aitasks_go now requires go.yaml.in/yaml/v3 v3.0.6; gopkg.in/yaml.v3 is gone from both of its modules and from its private allowlist mirrors.
> | 
> | The public half (the CLOSURE_ALLOWED_MODULES swap in .github/scripts/goengines_integrity.sh, plus the tests/test_goengines_export_integrity.sh:483 assert) now has its own aitasks task, t2282. t2192 no longer needs to carry it. t2282 must ship in the same commit or PR as the first goengines export that includes t114. Its body holds the scratch evidence: the current script rejects a t114 tree, and the swapped script rejects the current tree.
