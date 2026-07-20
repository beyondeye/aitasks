# Implementation-review angle catalog (shared fragments)

Shared fragments for the shadow implementation review tiers
(`impl-challenge.md`). Read this file when a tier references it — the tier
definitions name which angles and mechanisms below are active. Single source of
truth: every angle text, the verdict ladder, the disposition rubric, and the
ordering/cap rules live only here; tier sections reference them by name and
never restate them.

Adapted from Claude Code's built-in `/code-review` prompts — the verbatim
extraction and per-level assembly live in
`aidocs/codeagents/claudecode_builtin_prompts.md`. Shadow adaptations: "the
diff" below always means **the task's resolved diff source** (committed /
staged / working-tree, as resolved by impl-challenge's Inputs — there is no
separate diff-gathering phase), and angles run **inline, sequentially, in this
context** — no finder subagents are required. Reading the shadow's own repo
checkout (Read, Grep, `git show`) is always allowed: advisory-only governs the
*followed pane*, not your own repo reads.

## Correctness angles

### Angle A — line-by-line diff scan
Read every hunk in the diff, line by line. Then Read the enclosing function for
each hunk — bugs in unchanged lines of a touched function are in scope (the
task's change re-exposes or fails to fix them). For every line ask: what input,
state, timing, or platform makes this line wrong? Look for inverted/wrong
conditions, off-by-one, null/undefined deref, missing `await`, falsy-zero
checks, wrong-variable copy-paste, error swallowed in catch, unescaped regex
metachars.

### Angle B — removed-behavior auditor
For every line the diff DELETES or replaces, name the invariant or behavior it
enforced, then search the new code for where that invariant is re-established.
If you can't find it, that's a candidate: a removed guard, a dropped error
path, a narrowed validation, a deleted test that was covering a real case.

### Angle C — cross-file tracer
For each function the diff changes, find its callers (Grep for the symbol) and
check whether the change breaks any call site: a new precondition, a changed
return shape, a new exception, a timing/ordering dependency. Also check
callees: does a parallel change in the same task make a call unsafe?

### Angle D — language-pitfall specialist
Scan for the classic pitfalls of the diff's language/framework — for example:
JS falsy-zero, `==` coercion, closure-captured loop var; Python mutable default
args, late-binding closures; Go nil-map write, range-var capture; SQL
injection; timezone/DST drift; float equality. Flag any instance the diff
introduces.

### Angle E — wrapper/proxy correctness
When the change adds or modifies a type that wraps another (cache, proxy,
decorator, adapter): check that every method routes to the wrapped instance and
not back through a registry/session/global — e.g. a caching provider holding a
`delegate` field that resolves IDs via `session.get(...)` instead of
`delegate.get(...)` will re-enter the cache or recurse. Also check that the
wrapper forwards all the methods the callers actually use.

## Cleanup angles

The correctness angles hunt for bugs; these hunt for cleanup in the changed
code.

### Reuse
Flag new code that re-implements something the codebase already has — Grep
shared/utility modules and files adjacent to the change, and name the existing
helper to call instead.

### Simplification
Flag unnecessary complexity the diff adds: redundant or derivable state,
copy-paste with slight variation, deep nesting, dead code left behind. Name
the simpler form that does the same job.

### Efficiency
Flag wasted work the diff introduces: redundant computation or repeated I/O,
independent operations run sequentially, blocking work added to startup or
hot paths. Also flag long-lived objects built from closures or captured
environments — they keep the entire enclosing scope alive for the object's
lifetime (a memory leak when that scope holds large values); prefer a
class/struct that copies only the fields it needs. Name the cheaper
alternative.

### Altitude
Check that each change is implemented at the right depth, not as a fragile
bandaid. Special cases layered on shared infrastructure are a sign the fix
isn't deep enough — prefer generalizing the underlying mechanism over adding
special cases.

### Conventions (CLAUDE.md)
Find the CLAUDE.md files that govern the changed code: the user-level
`~/.claude/CLAUDE.md`, the repo-root CLAUDE.md, plus any CLAUDE.md or
CLAUDE.local.md in a directory that is an ancestor of a changed file (a
directory's CLAUDE.md only applies to files at or below it). Read each one
that exists, then check the diff for clear violations of the rules they state.
Only flag a violation when you can quote the exact rule and the exact line
that breaks it — no style preferences, no vague "spirit of the doc"
inferences. In the finding, name the CLAUDE.md path and quote the rule so the
report can cite it. If no CLAUDE.md applies, return nothing for this angle.

### Cleanup precedence
Cleanup, altitude, and conventions candidates use the same `file`/`line`/
summary shape; in the failure scenario, state the concrete cost (what is
duplicated, wasted, harder to maintain, or which CLAUDE.md rule is broken)
instead of a crash. Correctness bugs always outrank cleanup, altitude, and
conventions findings when the output cap forces a cut.

## Shadow / legacy axes

The three axes of the pre-tier adversarial review, preserved one-to-one. They
are the Default tier's entire attack surface (run as one full-context pass)
and S1/S2 also run as angles in Advanced/Deep. S0 is Default-only: in
Advanced/Deep the broad flaw sweep is *superseded* by the mechanized angles
A–E (note: Angle A is not a subsumption of S0 — A's line-by-line hunk
methodology is a different, narrower procedure than S0's broad sweep).

### Angle S0 — implementation flaws (legacy broad axis)
Bugs, missed cases, incorrect logic, off-by-ones, mishandled error/empty/edge
inputs, or regressions in the code *as actually written*, checked against the
plan/task intent and the real diff.

### Angle S1 — unmitigated plan risks
Cross-reference the plan's `## Risk` section and Final Implementation Notes.
Do **NOT** re-flag a risk the implementation explicitly addressed/mitigated;
surface only risks that remain **open** in the landed code.

### Angle S2 — plan-deviation auditor
Compare the diff against the plan. A deviation the Final Implementation Notes
justify is fine. Flag only deviations that are unexplained or whose
justification does not hold up.

## Anti-drop rule

Pass every candidate with a nameable failure scenario through to the verify
pass — finders that silently drop half-believed candidates bypass the verify
step and are the dominant cause of misses.

## Verdict ladder (3-state)

- **CONFIRMED** — can name the inputs/state that trigger it and the wrong
  output or crash. Quote the line.
- **PLAUSIBLE** — mechanism is real, trigger is uncertain (timing, env,
  config). State what would confirm it.
- **REFUTED** — factually wrong (code doesn't say that) or guarded elsewhere.
  Quote the line that proves it.

Keep candidates whose verdict is CONFIRMED or PLAUSIBLE. Drop REFUTED.

### Recall addendum (Deep tier only)
**PLAUSIBLE by default** — do not refute a candidate for being "speculative" or
"depends on runtime state" when the state is realistic: concurrency races,
nil/undefined on a rare-but-reachable path (error handler, cold cache, missing
optional field), falsy-zero treated as missing, off-by-one on a boundary the
code does not exclude, retry storms / partial failures, regex/allowlist that
lost an anchor. These are PLAUSIBLE.
**REFUTED** only when constructible from the code: factually wrong (quote the
actual line); provably impossible (type/constant/invariant — show it); already
handled in this diff (cite the guard); or pure style with no observable effect.

## Gap-sweep focus list (Deep tier only)

Take one more pass (same context — no subagent) as a fresh reviewer who has the
verified list. Re-read the diff and enclosing functions looking ONLY for
defects not already listed. Do not re-derive or re-confirm anything already
there — the job is gaps. Focus on what the first pass tends to miss:
moved/extracted code that dropped a guard or anchor; second-tier footguns
(dataclass default evaluated once, `hash()` non-determinism, lock-scope shrink,
predicate methods with side effects); setup/teardown asymmetry in tests;
config defaults flipped. If nothing new, return nothing from this phase — do
not pad.

## Disposition rubric (angle-independent)

Every finding, in every tier, carries a disposition: `blocking` or
`follow-up`. Disposition is decided by the finding's **reachable impact
measured against the change's obligations** — the task's acceptance criteria,
the plan's stated goal and contracts, existing behavior, and mandatory project
rules. The discovering angle is **discovery context only** and never
determines disposition; verdict confidence never does either.

- **`blocking`** — if real, the change as landed fails an obligation. ANY of:
  - it breaks or regresses existing behavior on a reachable path;
  - the task's acceptance criteria or the plan's stated goal is not delivered
    (requirement unmet, misunderstood, or misimplemented) — including
    performance/efficiency findings when the task or plan obligates that
    characteristic (e.g. blocking I/O added to a path the plan promised to
    keep hot-path-safe);
  - it violates a mandatory, quotable project rule (e.g. a CLAUDE.md rule the
    conventions angle can cite) that the change is obligated to honor;
  - a risk the plan's `## Risk` section committed to mitigate **in this
    change** remains open;
  - it is an unjustified deviation that alters a contract or user-visible
    behavior.
- **`follow-up`** — real, but the change still delivers its obligations; the
  finding is separable improvement or separable debt. Typical (not
  categorical) cases:
  - a **pre-existing** defect surfaced by review but not introduced or
    worsened by this change;
  - improvements (reuse / simplification / efficiency / altitude /
    maintainability) whose impact does not breach an obligation above — a
    newly introduced maintainability imperfection is follow-up when it does
    not invalidate the change;
  - hardening or test gaps beyond the task's stated AC;
  - improvements to adjacent code the diff merely touches.
- **Accepted/deferred risks (three-way):**
  - a risk the plan **validly** accepted or deferred (explicitly documented,
    rationale holds, no obligation breached) is **omitted by default** — per
    Angle S1's rule, an explicitly addressed decision is not re-flagged;
  - emit it as `follow-up` **only when tracking is genuinely required** (the
    acceptance defers real work and no follow-up task or mitigation entry
    exists to carry it);
  - an acceptance that **does not hold up** — the rationale is unsupported,
    or the "accepted" risk in fact breaches a task obligation (AC, plan
    contract, existing behavior) — is `blocking`, classified like any other
    unmet obligation.
- **Cross-checks (the categorical trap):** a cleanup-angle finding whose
  reachable impact breaches an obligation (a task-breaking performance
  regression, a mandatory-rule violation) is `blocking`; a correctness-angle
  finding that is a minor newly introduced imperfection breaching no
  obligation is `follow-up`. Classify by impact, not by angle category.
- **Uncertainty rule:** a PLAUSIBLE verdict does NOT demote a finding to
  `follow-up`. Confidence (verdict) and disposition are orthogonal: classify
  by consequence-if-real; the verdict expresses how sure you are.

## Ordering and caps (partition before cap)

Partition findings `blocking` first, then `follow-up`; severity-ordered
*within* each partition. Tier findings caps apply **after** classification and
cut from the end of the `follow-up` partition first — a blocking finding is
never dropped in favor of a follow-up, regardless of severity.

**Cap-overflow rule (deterministic):** the cap never truncates the `blocking`
partition — when blocking findings alone reach or exceed the tier cap, report
**all** blocking findings (the advertised cap is exceeded by exactly the
blocking overflow) and omit the entire `follow-up` partition.

**Disclosure:** whenever the cap omits anything, state it explicitly at the end
of the prose list — how many findings were omitted and from which partition
(e.g. "cap: 3 follow-up findings omitted"). Silent omission is never allowed.
The concern block mirrors the same partition order and the same included set.
