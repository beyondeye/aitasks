# Parallel-Admission Checker Contract

How to invoke the shared parallel-admission checker and decide whether its
output may be used at all. It carries **no profile conditionals**: every caller
needs the same invocation and the same well-formedness rule, and a caller whose
own knob is `off` must still be able to reference this file.

Two callers today, with different evidence in hand:

- `parallel-admission.md` — the post-plan preflight, which passes
  `--plan "<plan_file>"`.
- `parallel-assessment.md` — the pre-claim assessment, which runs before the
  task is claimed and omits `--plan`, letting the checker discover the
  candidate's evidence itself (see below).

## Input context

| Variable | Description |
|----------|-------------|
| `task_id` | The candidate task (`16` or `16_2`). |
| `plan_file` | Path to the externalized plan — **optional**. Pass it when the caller has an approved plan it wants judged; otherwise omit the whole flag. |

## 1. Run the checker

Bind `plan_file` to a variable; never paste a literal into the command line.
Capture stdout with the `if`-form — a bare `out="$(…)"; rc=$?` dies under
`set -e` before `rc` is read — and **never merge stderr into stdout**, because
every line a caller parses is `KEY:value` and merging corrupts the parse:

```bash
if out="$(./.aitask-scripts/aitask_parallel_admission.sh check \
    --candidate <task_id> --from plan [--plan "<plan_file>"] \
    --lock-freshness require-fresh)"; then
  rc=0
else
  rc=$?
fi
```

`--plan "<plan_file>"` is the **only** optional part of that invocation. With it,
the candidate's surface is read from that plan. Without it, the checker
**discovers** the candidate's evidence in this order: the task's plan file, if
one already exists (a `Ready` task can carry one — a deferred approved plan, a
decomposed child's pre-written plan), and only when there is none, the task's
**description** (`task_declared`), which is weaker evidence and cannot grade a
bare `CLEAR`. Do not assume which one it used — read the provenance field of the
`CANDIDATE:<ref>|<provenance>|…` line (`plan_declared` or `task_declared`), and
never substitute a guessed path for a plan that does not exist.

Three things about that invocation are not preferences:

- **`--lock-freshness require-fresh` is mandatory.** A cached lock ref hides a
  lock another agent took seconds ago — a false `CLEAR` at exactly the admission
  point this exists to defend.
- **The checker excludes the candidate itself, and must.** By the preflight's
  call site `task-workflow` has already set the task `Implementing` and taken its
  lock back at **Step 4**. Without the exclusion the candidate overlaps 100% of
  its own plan and every single pick is a `CONFLICT`. Do not "simplify" the
  exclusion away.
- **Read live state at call time.** Never reuse a roadmap snapshot: it is older
  by construction, and these are the call sites where that matters.

Every *content* state exits 0 — read `VERDICT:`, never the exit status.

## 2. Accept the result only if it is well-formed

Stdout must carry **exactly one** `VERDICT:` line whose
token is one of `CLEAR`, `CLEAR_CAVEATED`, `CONFLICT`, `UNCHECKABLE`.
Anything else is **"checker unusable"** — never an auto-proceed:

| observed | treated as |
|---|---|
| exit 2 (CLI misuse) | checker unusable · report it as a **wiring error**, naming the stderr line |
| any other non-zero exit, or a crash | checker unusable · report the exit status |
| empty stdout, or no `VERDICT:` line | checker unusable |
| more than one `VERDICT:` line | checker unusable · never pick one |
| a `VERDICT:` token outside the closed set | checker unusable · quote the token verbatim |
| an `UNCHECKABLE_CAUSE:` whose reason code is not declared in the checker's vocabulary (below) | checker unusable · print the raw reason field verbatim rather than swallowing it |

**Validate cause codes against the checker's own vocabulary, never against a
caller's remedy table.** Split each `UNCHECKABLE_CAUSE:<scope>|<reason>` on the
first `|`; the code is `<reason>` up to its first `:`. It is well-formed exactly
when that code is a key of `UNCHECKABLE_REASONS` in
`.aitask-scripts/lib/parallel_admission_vocab.py` (for example `no_plan`,
`all_phantom`, `no_extractable_paths`, `source_unavailable`). A declared code the
caller has no remedy row for is still a **well-formed** `UNCHECKABLE` — the
caller reports it verbatim — and must never be demoted to "checker unusable":
a caller without a remedy table (the pre-claim assessment), or one whose table
is rendered away, would otherwise turn every ordinary `no_plan` into a
checker failure.

Say plainly that a "checker unusable" cause is **procedure-originated, not a
checker verdict** — it is not a member of `UNCHECKABLE_REASONS` in
`.aitask-scripts/lib/parallel_admission_vocab.py` and must not be reported as
one.

This is fail-safe, not fail-open: a lock fetch that cannot reach the remote, a
parser change, or a helper crash must never read as "no known conflict".

## 3. Hand back to the caller

This file **classifies** — it says what the checker answered and whether that
answer may be used. **Each caller owns the disposition**: what a verdict means
for its own flow, which remedies it prints, whether it prompts, and what the
options are. Nothing here ends a workflow.
