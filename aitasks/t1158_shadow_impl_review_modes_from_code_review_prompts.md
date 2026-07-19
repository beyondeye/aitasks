---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [shadow]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-17 19:06
updated_at: 2026-07-19 12:42
boardidx: 30
---

Add effort-tiered, angle-based implementation review modes to the shadow skill
(`.claude/skills/aitask-shadow/impl-challenge.md`), adapted from the prompts
behind Claude Code's built-in `/code-review` effort levels, which were
extracted verbatim from the local Claude Code binary during exploration.

## Background

Shadow's `impl-challenge.md` today is one flat adversarial mode with three
axes (implementation flaws, unmitigated risks, unjustified deviations from the
plan). It has no effort tiers, no per-angle finder methodology, and no
verification pass. The built-in `/code-review` skill structures the same job
much more sharply, and its full prompt text was recovered from the installed
binary (v2.1.212, Bun-compiled ELF; `strings`/`grep -abo`/`dd` offset carving
— the recipe is reproducible on any installed version if re-extraction is
wanted: `grep -abo "high-confidence findings" ~/.local/share/claude/versions/<v>`
then carve ±50KB around the hit and around offset of
"Keep candidates where the vote is CONFIRMED").

**Full reference (read first):** `aidocs/codeagents/claudecode_builtin_prompts.md`
carries the complete verbatim reconstruction — all shared fragments, per-level
assembly for all three prompt families (default subagent, Opus-4.8 inline,
workflow-backed multi-agent), the routing matrix, flag fragments, and the
extraction recipe. The distillation below is a summary of that document.

## Extracted /code-review structure (distilled, faithful to source)

**Effort tiers (inline family):**
- **low**: 1 diff pass, no subagents, no full-file reads; flag only
  runtime-correctness bugs visible from the hunk alone (inverted condition,
  off-by-one, null deref, removed guard, falsy-zero, missing await,
  wrong-variable copy-paste, swallowed error) plus hunk-visible duplication
  and dead code; skip test/fixture hunks; ≤4 findings, one line each; output
  `(none)` if nothing qualifies.
- **medium**: precision-tuned ("every finding one a maintainer would act on").
  Phase 0 gather diff → Phase 1: 8 finder angles (3 correctness + 5 cleanup),
  up to 6 candidates each with file/line/summary/failure_scenario → Phase 2:
  1-vote 3-state verify per candidate → ≤8 findings.
- **high**: recall-tuned ("catch every real bug a careful reviewer would catch
  in one sitting; err on the side of surfacing"). Same fan-out, recall-biased
  verify ladder → ≤10 findings.
- **xhigh/max**: 10 angles (adds correctness angles D and E), up to 8
  candidates each → verify → Phase 3 gap-sweep (fresh pass hunting ONLY for
  defects not already listed) → ≤15 findings.

**Correctness angles (verbatim essence):**
- **A — line-by-line diff scan**: read every hunk line by line, then the
  enclosing function of each hunk (bugs in unchanged lines of a touched
  function are in scope). For every line ask: what input, state, timing, or
  platform makes this line wrong?
- **B — removed-behavior auditor**: for every line the diff DELETES or
  replaces, name the invariant it enforced, then search the new code for where
  that invariant is re-established. Can't find it → candidate (removed guard,
  dropped error path, narrowed validation, deleted covering test).
- **C — cross-file tracer**: for each changed function, Grep for callers and
  check whether the change breaks any call site (new precondition, changed
  return shape, new exception, ordering dependency); also check callees.
- **D — language-pitfall specialist**: classic pitfalls of the diff's
  language/framework (JS falsy-zero/`==` coercion/closure-captured loop var;
  Python mutable default args/late-binding closures; Go nil-map write/range-var
  capture; SQL injection; timezone/DST drift; float equality).
- **E — wrapper/proxy correctness**: when a type wraps another (cache, proxy,
  decorator, adapter), check every method routes to the wrapped instance and
  not back through a registry/session/global, and that the wrapper forwards
  all methods callers actually use.

**Cleanup angles:** Reuse (new code re-implementing an existing helper — name
the helper to call instead); Simplification (redundant/derivable state,
copy-paste variation, deep nesting, dead code — name the simpler form);
Efficiency (redundant computation/repeated I/O, sequential independent ops,
blocking work on hot paths, closure-built long-lived objects — name the
cheaper alternative); Altitude (change implemented at the wrong depth — a
special case layered on shared infrastructure instead of generalizing the
mechanism); Conventions (find governing CLAUDE.md files, flag only violations
where you can quote the exact rule and the exact breaking line).

**Verdict ladder (verify pass):**
- CONFIRMED — can name the inputs/state that trigger it and the wrong
  output/crash; quote the line.
- PLAUSIBLE — mechanism is real, trigger uncertain (timing, env, config);
  state what would confirm it.
- REFUTED — factually wrong or guarded elsewhere; quote the line that proves it.
Recall-biased addendum (high+): "PLAUSIBLE by default" — do not refute for
being 'speculative' when the state is realistic (races, rare-but-reachable nil
paths, falsy-zero, boundary off-by-one, retry storms, regex that lost an
anchor). REFUTED only when constructible from the code: factually wrong (quote
the line), provably impossible (type/constant/invariant), already handled in
this diff (cite the guard), or pure style.
Keep CONFIRMED + PLAUSIBLE; drop REFUTED.

**Gap-sweep (xhigh+):** one more pass as a fresh reviewer holding the verified
list, looking ONLY for defects not already listed — moved/extracted code that
dropped a guard or anchor; second-tier footguns (dataclass default evaluated
once, hash() non-determinism, lock-scope shrink, predicate methods with side
effects); setup/teardown asymmetry in tests; config defaults flipped. Never
pad.

**Anti-drop rule (all multi-angle tiers):** pass every candidate with a
nameable failure scenario through to verify — finders that silently drop
half-believed candidates are the dominant cause of misses.

## What to build

Rework `impl-challenge.md` (and/or add sibling sub-procedure files) so the
shadow implementation review offers selectable modes/tiers instead of one flat
pass. Design intent (final shape decided at planning):

1. **Effort tiers** — e.g. quick (low-style single diff pass over the task's
   changes) / standard (multi-angle + verify) / deep (adds D+E angles and the
   gap-sweep). User picks via free text or an AskUserQuestion when they invoke
   the impl review.
2. **Angle catalog** — adapt correctness angles A–E and the cleanup angles to
   the shadow context. Note the shadow runs in one context (advisory
   companion), so angles run inline/sequentially like the Opus-4.8 inline
   variant of /code-review — no finder subagents required (though Task/Explore
   subagents are available if the plan finds them worthwhile).
3. **Verdict ladder** — add the CONFIRMED/PLAUSIBLE/REFUTED self-verification
   pass (precision-biased at standard, recall-biased at deep) before emitting
   findings, and carry the verdict into the prose findings list.
4. **Keep shadow's unique axes** — plan-vs-diff comparison (unjustified
   deviations), unmitigated plan risks, and Final Implementation Notes
   cross-referencing are shadow-specific value the generic prompts lack; the
   new modes layer the angle methodology on top of, not instead of, these.

## Constraints (load-bearing)

- The minimonitor **concern-block contract** in impl-challenge.md
  (`===AITASK-CONCERNS===` / `===END-CONCERNS===`, `- [priority | region] body`
  lines, block-last, omit-when-clean) must be preserved exactly across all
  modes — single source of truth `concern-format.md`.
- The **advisory-only guardrail** and the "too early to review" gate (Final
  Implementation Notes presence check, archived-plan fallback) stay.
- Shadow sub-procedures are Claude-only; other agent trees are redirect
  wrappers — no cross-agent port needed (see memory: shadow skill = wrapper).
- Findings stay honest: severity-ordered, no filler, omit block when clean —
  the existing rules extend to every new mode.
- Read `aidocs/framework/skill_authoring_conventions.md` before editing skill
  files; run `./.aitask-scripts/aitask_skill_verify.sh` before committing if
  any stub/template surface is touched (impl-challenge.md is a plain
  sub-procedure, not a .j2 surface, so goldens likely unaffected — verify).

## Acceptance criteria

- Shadow impl review offers at least a quick tier and a deep tier (exact tier
  set decided at planning) with documented methodology per tier.
- Correctness angles A–E and the cleanup/altitude/conventions angles are
  available in at least one tier, adapted to review the task's diff sources
  (committed / staged / working-tree, as impl-challenge already resolves).
- A verify pass with the 3-state verdict ladder runs in the non-quick tiers,
  and verdicts appear in the findings presentation.
- Concern-block output, advisory-only guardrail, and too-early gate unchanged
  and working in every tier.
- SKILL.md Step 3 routing text updated so the user can request a tier in free
  text ("quick review of the implementation", "deep review").
