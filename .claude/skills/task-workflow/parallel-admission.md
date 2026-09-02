# Parallel-Admission Preflight Procedure

Asks the shared parallel-admission checker whether any **other** in-flight task
collides with this one, and surfaces the answer before implementation starts. It
is **advisory**: no verdict ever ends the workflow on its own. Every stop is a
choice the user makes at the prompt.

Invoked from two places, both immediately after the **Remote Drift Check
Procedure** (see `remote-drift-check.md`) returned "Continue anyway":
`planning.md`'s Checkpoint, and `SKILL.md`'s **Re-entry Routing** on the
`IMPLEMENT` route. That order is load-bearing — the drift check can pull the base
branch, which changes what is in flight, so a preflight that ran first would be
reasoning about a stale world. It is deliberately **not** on the `POSTIMPL`
route: the code is already committed there, and nothing this procedure could say
would be actionable.

Control returns to the caller unless the user chose to stop or abort.

## Input context

| Variable | Description |
|----------|-------------|
| `task_id` | The task being admitted (`16` or `16_2`). |
| `task_num` | Numeric id for `aitask_update.sh` — the task's **own** id; for a child that is the child id (`16_2`), never the parent's. |
| `plan_file` | Path to the externalized plan (e.g. `aiplans/p16_add_auth.md`). |
| `active_profile` | Loaded execution profile (or null). |

## Procedure
{# ---------- parallel_admission ---------- #}{% if profile.parallel_admission is defined and (profile.parallel_admission == "off" or profile.parallel_admission == false) %}
**Profile '{{ profile.name }}' sets `parallel_admission: off`** — this procedure
is a **no-op**. Do not invoke the checker, do not display anything, and return to
the caller immediately. Nothing below applies.
{% else %}{# parallel_admission: "confirm", "warn", or the key is absent (warn is the default) #}
1. **Profile check.** If the active profile sets `parallel_admission: off`,
   return immediately: no invocation, no display.

2. **Run the checker.** Bind `plan_file` to a variable; never paste a literal
   into the command line. Capture stdout with the `if`-form — a bare
   `out="$(…)"; rc=$?` dies under `set -e` before `rc` is read — and **never
   merge stderr into stdout**, because every line parsed below is `KEY:value` and
   merging corrupts the parse:

   ```bash
   if out="$(./.aitask-scripts/aitask_parallel_admission.sh check \
       --candidate <task_id> --from plan --plan "<plan_file>" \
       --lock-freshness require-fresh)"; then
     rc=0
   else
     rc=$?
   fi
   ```

   Three things about that invocation are not preferences:

   - **`--lock-freshness require-fresh` is mandatory here.** A cached lock ref
     hides a lock another agent took seconds ago — a false `CLEAR` at exactly the
     admission point this exists to defend.
   - **The checker excludes the candidate itself, and must.** `task-workflow` set
     this task `Implementing` and took its lock back at **Step 4**, long before
     the plan existed. Without the exclusion the candidate overlaps 100% of its
     own plan and every single pick is a `CONFLICT`. Do not "simplify" the
     exclusion away.
   - **Read live state at call time.** Never reuse a roadmap snapshot: it is
     older by construction, and this is the one call site where that matters.

   Every *content* state exits 0 — read `VERDICT:`, never the exit status.

3. **Accept the result only if it is well-formed.** Stdout must carry **exactly
   one** `VERDICT:` line whose token is one of `CLEAR`, `CLEAR_CAVEATED`,
   `CONFLICT`, `UNCHECKABLE`. Anything else takes the **UNCHECKABLE**
   disposition — never an auto-proceed:

   | observed | treated as |
   |---|---|
   | exit 2 (CLI misuse) | UNCHECKABLE · report it as a **wiring error**, naming the stderr line |
   | any other non-zero exit, or a crash | UNCHECKABLE · report the exit status |
   | empty stdout, or no `VERDICT:` line | UNCHECKABLE |
   | more than one `VERDICT:` line | UNCHECKABLE · never pick one |
   | a `VERDICT:` token outside the closed set | UNCHECKABLE · quote the token verbatim |
   | an `UNCHECKABLE_CAUSE:` code the table in step 5 does not list | still UNCHECKABLE · print the raw reason field verbatim rather than swallowing it |

   Call this **"checker unusable"** and say plainly that the cause is
   **procedure-originated, not a checker verdict** — it is not a member of
   `UNCHECKABLE_REASONS` in `.aitask-scripts/lib/parallel_admission_vocab.py` and
   must not be reported as one.

   This is fail-safe, not fail-open: a lock fetch that cannot reach the remote, a
   parser change, or a helper crash must never read as "no known conflict".

4. **Dispositions.**

   | verdict | disposition |
   |---|---|
   | `CLEAR` | proceed. Word it **"no known conflict at check time"** — never "safe to run in parallel" |{% if profile.parallel_admission is defined and profile.parallel_admission == "confirm" %}
   | `CLEAR_CAVEATED` | **Profile '{{ profile.name }}' sets `parallel_admission: confirm`** — ask the step-6 question, naming each unverified source from the `CAVEAT:` lines |{% else %}
   | `CLEAR_CAVEATED` | display a visible note naming each unverified source from the `CAVEAT:` lines, then proceed. **Render it distinctly from `CLEAR`** — "no known conflict, but evidence was unverified: …", never the bare `CLEAR` wording |{% endif %}
   | `CONFLICT` | name the overlapping task(s) and file(s) from the `OVERLAP:` lines, then ask the step-6 question |
   | `UNCHECKABLE` | name *why*, with the remedy from step 5 for each cause, then ask the step-6 question |

   `DISPLAY:` carries a one-line human summary built by the checker — show it
   verbatim as the first line of any display, then add the detail above.

5. **Operator recovery paths — printed with every `UNCHECKABLE`.** A prompt with
   no remedy is what trains users to dismiss a guard.

   Causes arrive as `UNCHECKABLE_CAUSE:<scope>|<reason>`, split on the **first**
   `|`. `scope` is `candidate`, `locks`, `inflight:<task-ref>`, or
   `inflight:<gate|lock|status>`. `reason` is a bare code or `<code>:<param>`.

   | scope | reason | remedy to print |
   |---|---|---|
   | `inflight:<ref>` | `no_plan` | plan that task, or release its lock (`ait lock --unlock <ref>`), or override for it |
   | `inflight:<ref>` | `all_phantom` | that plan is stale — refresh or release it |
   | `inflight:<ref>` | `no_tokens`, `unreadable`, `unclassified`, `no_extractable_paths` | that plan declares no usable surface — add concrete paths to it, or release the claim |
   | `inflight:<ref>` | `unknown_history`, `unknown_origin` | no reachable commits for that id — it may predate the history in this checkout; `git fetch`, or override for it |
   | `candidate` | any value | **this** plan declares no resolvable surface — add concrete repo paths to it |
   | `locks` | `no_local_ref`, `unreadable_tree`, `no_reflog`, `clock_skew`, `timeout`, `scan_error` | the lock ref could not be read — check the network and re-run |
   | any | `source_unavailable:<gate\|lock\|status>` | that probe did not answer — re-run; if it persists, `ait lock --list` / `ait gates` diagnose it |

   The table is the **only** place these strings are written. Parse with the
   grammar above so a code the table does not list is reported **verbatim**
   rather than silently swallowed.

6. **The question — asked for `CONFLICT`, `UNCHECKABLE`, and{% if profile.parallel_admission is defined and profile.parallel_admission == "confirm" %} `CLEAR_CAVEATED`{% else %} (under `parallel_admission: confirm`) `CLEAR_CAVEATED`{% endif %}.**

   Use `AskUserQuestion`:

   - Question: "How would you like to proceed?"
   - Header: "Parallel"
   - Options, **in this order**:
     - "Continue anyway" (description: "Proceed to implementation — this check is advisory and observes only")
     - "Stop and re-plan" (description: "Release the lock, revert task to Ready, and end the workflow — re-pick once the overlapping work has landed")
     - "Abort task" (description: "Discard the task and revert status")

   **Continuing is listed first**, unlike the drift check's ordering. That is
   deliberate: this signal is heuristic — it reads paths scraped out of plan
   prose — and its false-positive rate is measured, not assumed. Putting a stop
   first would present a guess as the safe default.

7. **Branches.**

   - **"Continue anyway":** return so the caller proceeds to Step 7.
   - **"Stop and re-plan":** execute the **Approved-Plan Stop Sequence** (see
     `plan-approved-stop.md`) with `task_id`, `task_num`, `plan_file`,
     `stop_reason=parallel_admission`,
     `revert_commit_message="ait: Revert t<task_num> to Ready (parallel admission)"`,
     and a `closing_message` naming the overlapping task(s) or the unresolved
     cause, plus the re-pick command: "Task t\<task_id\> reverted to Ready. Re-pick
     with `/aitask-pick <task_id>` once the overlapping work has landed." That
     sequence ends the workflow — do NOT proceed to Step 7.
   - **"Abort task":** execute the **Task Abort Procedure** (`task-abort.md`).

   None of the three is ever selected automatically.
{% endif %}{# ---------- end parallel_admission ---------- #}

## Notes

- **`CLEAR` means "no known conflict at check time", never "safe to run in
  parallel".** The checker observes; it does not reserve. Overlapping work can
  begin the instant after it passes, and this procedure makes no promise about
  that. The residual closes only when t1343's declared-claims backend lands.
- **Advisory by design, not by omission.** No value of `parallel_admission` stops
  the workflow. The evidence is regex-extracted from plan prose — a path a plan
  merely *runs* inside a fenced command is indistinguishable from one it declares
  it will edit — and a measured false `CONFLICT` is on record. A heuristic of that
  shape may inform a decision; it may not make one. Any future hard-stop mode is
  gated on t1343's structured per-task declaration, not on this knob.
- **Not a gate, deliberately.** `MANUAL_VERIFICATION_REACHABLE_GATES` in
  `lib/task_utils.sh` is an allowlist and `filter_gates_for_issue_type()` would
  silently strip a new gate. The precedent is plan-verification staleness — a
  step in `planning.md`, not a gate — and the structural twin is
  `remote-drift-check.md`, which this mirrors. See
  `aidocs/framework/manual_verification_staleness.md` ("Why not a gate").
- **Distinct from resource admission, and neither may be folded into the other.**
  This asks whether *other tasks* collide with this one; `resource-admission.md`
  asks whether the *host* can afford the phase. Where both are wired, correctness
  runs before capacity: this preflight sits at the planning Checkpoint, that hook
  last, immediately before the fork.
- **No worktree exists at the planning-Checkpoint call site** — the fork is
  deferred to `SKILL.md` Step 7 — so a stop there strands nothing. On the
  `IMPLEMENT` re-entry route a worktree from the earlier session may already
  exist; it is left in place, and the next pick reuses it.
- For child tasks, `task_num` is the **child** id (e.g. `16_2`). The parent's
  status is untouched.
