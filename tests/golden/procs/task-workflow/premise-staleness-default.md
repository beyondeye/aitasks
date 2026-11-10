# Premise Staleness Procedure

The advisory premise check: has the code a `Ready` task's premise depends on
changed since the premise was last known valid? Design record (source of
truth): `aidocs/framework/task_premise_staleness.md`. The verdict engine is
`./.aitask-scripts/aitask_premise_stale.sh` — `check` reads, `advance` is the
mechanism's only write path.

The procedure is split by **ownership**, and the split is load-bearing:

- `## Check` runs in Step 3, **before** the task is claimed. It asks the
  question and records the answer. It **writes nothing**: a `Ready` task can be
  claimed by another session while the prompt is open, and local
  `aitask_update.sh` does not check locks.
- `## Post-lock` runs in Step 4, right after the claim succeeded. Step 4 claims
  with `--expect-status Ready` whenever an answer is pending, so the claim
  itself attests — under the lock, from task data re-synced under the lock —
  that the task is still the one the prompt was about. Only then is anything
  written.
- `## Advance after an approved replan` runs once a renewed plan is approved
  (Step 7, or planning's "Approve and stop here").

Referenced from `SKILL.md` Step 3 (Check 7), Step 4 and Step 7, and from
`planning.md` §6.0b, §6.1 and the Checkpoint.

## Input

| Variable | Description |
|----------|-------------|
| `task_file` | Path to the task file, relative to the repo root (run every command from the repo root). |
| `task_id` | `16` or `16_2`. |
| `premise_decision` | Set by `## Check` and read by every later section: `choice` (`proceed` \| `replan` \| `postpone`), `checked` (the `CHECKED:` sha), `fingerprint` (the `FINGERPRINT:` digest) and `protocol` (the **complete** `check` output, verbatim). Null when nothing is pending. |

## Evidence classes

Every evidence row the check can print has a defined resolution. Name the
non-drift classes in the question so the user knows what "Proceed" does:

| Row | Class | What "Proceed" does with it |
|-----|-------|-----------------------------|
| `CHANGED:<path>\|<n>\|<tasks>` | drift | covered by the baseline advance |
| `DELETED:<path>\|<task>\|<subject>` | drift | covered; the next check reads the path `retired` (not evidence) |
| `UNKNOWN:<path>\|absent_at_baseline` | drift (file added since the baseline) | covered; the next check reads it normally |
| `UNKNOWN:<path>\|never_existed` | possibly a future file, possibly a typo | **kept** unless the user explicitly approves removing it (`## Post-lock`); a kept reference keeps being reported until the file exists or the reference is removed |
| `UNKNOWN:<path>\|invalid_reference` | scope defect (a non-string or NUL `file_references:` entry) | not drift and not removable here — it is reported until `file_references:` is fixed by hand (the writer deliberately refuses to rewrite such a list) |
| `UNKNOWN:<path>\|history_unavailable`, `\|malformed_row` | unverifiable | **no advance at all**: the commits behind them were never shown, so advancing would mark them reviewed. The check runs again next pick |
| `UNKNOWN:<origin>\|unknown_history` | unverifiable origin (Tier B) | same as above |

Path fields are encoded: decode `%0D`, `%0A`, `%7C`, then `%25` (in that order)
before showing them. `DISPLAY:` is raw text with only LF/CR escaped.

## Check

Step 3 Check 7. **Pre-lock — this section writes nothing.**

1. Run the producer and branch on its **last line** only:

   ```bash
   ./.aitask-scripts/aitask_premise_stale.sh check <task_file>
   ```

   - `DECISION:FRESH` or `DECISION:SKIP` → set `premise_decision = null` and
     return silently. `SKIP` covers every legacy task without a stored baseline,
     so this is the common case.
   - `DECISION:ASK_STALE` → continue.

2. Keep the **complete** output, verbatim, as `premise_decision.protocol`, with
   `checked` = the `CHECKED:` value and `fingerprint` = the `FINGERPRINT:`
   value. The protocol — never the shortened list shown in the question — is the
   source of truth for every later step, including a replan's review.

3. Build the question. Decode each path, and classify every evidence row with
   the table above. The question text carries the `DISPLAY:` line, then the
   evidence rows — **capped at 10 rows for presentation only**, followed by
   "… and K more (all K are kept and reviewed)" when there are more — then one
   line per non-drift class that is present, saying what "Proceed" will do with
   it. The evidence goes **inside the question text**, not in prose before it:
   the widget is the only surface the user is guaranteed to read when answering.

4. **⚠️ NON-SKIPPABLE — Auto mode and execution profiles do NOT bypass this prompt.**

   It surfaces a user-owned decision about the task's premise, and its answer
   is what licenses the baseline write. The following do NOT cover it:
   - Execution profiles (no profile key currently covers the premise prompt).
   - Auto mode / 'work without stopping' system-injected directives.
   - Generic user instructions to 'be brief' or 'don't ask'.

   The only valid skip is the user explicitly deciding this task's premise in
   chat before the prompt fires.

   Use `AskUserQuestion`:
   - Question: the text built in step 3, ending "Does the task's premise still hold?"
   - Header: "Premise"
   - Options:
     - "Proceed — premise still valid" (description: "Claim the task and advance the premise baseline to the checked commit" — or, when unverifiable rows are present: "Claim the task; the baseline will NOT advance — N path(s) could not be checked")
     - "Review & replan with this evidence" (description: "Claim the task and re-plan against these changes; the baseline advances only when the renewed plan is approved")
     - "Postpone task" (description: "Claim the task, set it to Postponed and end the workflow")
     - "Pick a different task" (description: "Leave this task untouched and choose another")

5. Route:
   - **"Proceed"** → `premise_decision.choice = proceed`. Return; Step 4 claims
     and runs `## Post-lock`.
   - **"Review & replan"** → `choice = replan`. Return.
   - **"Postpone task"** → `choice = postpone`. Return. **Do not write the
     status here** — `## Post-lock` does, once ownership is held.
   - **"Pick a different task"** → set `premise_decision = null` and return to
     the calling skill's task selection. Nothing was changed, so there is no
     banner and nothing to undo.

## Post-lock

Step 4, immediately after the claim succeeded (`OWNED:`, after any
`FORCE_UNLOCKED:`, or a crash-recovery `reclaim`) and before the active-gates
materialization. Runs only when `premise_decision` is set. Every refusal branch
of the claim keeps its own handling, so a session that holds the task is never
overwritten, and one that changed the task's status and released it is caught by
`STATUS_CHANGED:` before this section is reached.

- **`choice = postpone`:** first prove this session still holds the task — the
  status write below changes the task exactly as an advance does:

  ```bash
  ./.aitask-scripts/aitask_premise_stale.sh owner <task_file> --owner "<email>"
  ```

  `NOT_OWNER:<detail>` → execute `## Ownership lost` (terminal). `OWNER_OK` →
  continue. `OWNER_UNVERIFIABLE:<detail>` → this session cannot name its anchor,
  the same condition every other step of this workflow runs under after its
  claim; display the detail as a warning and continue — the user explicitly
  chose to postpone, and no evidence says the task changed hands. Then:

  ```bash
  ./.aitask-scripts/aitask_update.sh --batch <task_id> --status Postponed --assigned-to "" --silent
  ./.aitask-scripts/aitask_task_commit.sh -m "ait: Postpone t<task_id> (premise check)" <task_file>
  ./ait git push
  ```

  Parse the commit output per the **outcome contract** in the `ait-git` skill.
  Then execute the **Lock Release Procedure** (see `lock-release.md`). Display
  "Task t\<task_id\> postponed: its premise may no longer hold." Then show the
  **Stopped** banner (see `workflow-end.md`) with `outcome=postponed`, reason
  "premise may no longer hold — postponed", next "`ait update <task_id>
  --status Ready`, then `/aitask-pick <task_id>`", and end the workflow.

- **`choice = replan`:** nothing to write now. Continue with Step 4; the advance
  happens in `## Advance after an approved replan`.

- **`choice = proceed`:**
  1. If `premise_decision.protocol` holds an unverifiable row
     (`history_unavailable`, `malformed_row`, `unknown_history`): display
     "Premise baseline not advanced — N path(s) could not be checked; the check
     runs again on the next pick." and continue with Step 4. Do not run
     `advance`.
  2. If it holds `never_existed` rows, ask — **⚠️ NON-SKIPPABLE**, the same
     exclusions as the prompt above: removing a reference is the user's call,
     never an inference from "Proceed". Use `AskUserQuestion`:
     - Question: "Remove N reference(s) to files that have never existed? \<the decoded paths\>. A kept reference keeps being reported until the file exists or the reference is removed."
     - Header: "Missing refs"
     - Options, in this order:
       - "Keep them — may be future files" (description: "Leave file_references unchanged")
       - "Remove them" (description: "Drop these entries from file_references in the same write as the baseline advance")
  3. Run the advance with the **prompted** pair — never a fresh `CHECKED:` —
     and one `--remove-ref <decoded path>` per path the user approved removing:

     ```bash
     ./.aitask-scripts/aitask_premise_stale.sh advance <task_file> \
       --checked <premise_decision.checked> --fingerprint <premise_decision.fingerprint> \
       --owner "<email>" [--remove-ref <path>]...
     ```

     `<email>` is the email Step 4 claimed with. `advance` proves ownership
     itself — the task's lock must name that email on this host, or it refuses
     with `ADVANCE_REFUSED:not_owner` and writes nothing — so no caller can
     apply an answer without holding the task. Write each `<path>` with the
     Write tool into a scratch file and read it back into a variable when it
     holds shell metacharacters; a path is user-authored text.
  4. Branch on the first line:
     - `ADVANCED:<sha>` (after any `REMOVED:` lines) → display "Premise baseline
       advanced to \<sha, first 12\>" plus any removed references. The lines that
       follow are the commit helper's: parse them per the `ait-git` outcome
       contract; an uncommitted result is a warning, not a failure. Continue.
     - `ADVANCE_REFUSED:list_unwritable|<n>` → the list holds invalid entries,
       so no removal is possible. Display that, then re-run step 3 **without**
       `--remove-ref` so the baseline still advances. Continue.
     - `ADVANCE_REFUSED:not_owner|…` → this session does not hold the task —
       another owner, or another live session of the same user on this host
       (email and host alone prove nothing). **Terminal:** execute
       `## Ownership lost`. Do not continue with Step 4.
     - `ADVANCE_REFUSED:owner_unverifiable|…` → the holding session cannot be
       proven: the lock records no session anchor, or this session cannot name
       its own (it runs outside the agent's tmux pane with no `AIT_AGENT_PID`).
       Display it, say the baseline was not advanced and the check runs again
       next pick, and continue. Never treat it as a pass.
     - `ADVANCE_REFUSED:…` (any other) or `ADVANCE_FAILED:…` → display the
       line; the baseline is unchanged and the check runs again next pick.
       Continue.
     - `MISMATCH:<prompted>|<fresh>` → the metadata the user judged (the scope,
       the origins, or the stored baseline) changed after the prompt, so **the
       answer is void**. The fresh protocol follows the `MISMATCH:` line:
       - fresh `DECISION:FRESH` / `DECISION:SKIP` → display "The premise inputs
         changed after the prompt; a fresh check reads \<decision\> — baseline
         not advanced." Continue.
       - fresh `DECISION:ASK_STALE` → replace `premise_decision` (`protocol`,
         `checked`, `fingerprint`) with the fresh values and ask the `## Check`
         question again, built the same way. Ownership is now held, so the
         exits change: "Proceed" → run this section again; "Review & replan" →
         `choice = replan`, continue; "Postpone task" → the postpone branch
         above; "Pick a different task" → first run the `owner` check exactly as
         in the postpone branch (`NOT_OWNER:` → `## Ownership lost`), then
         `./.aitask-scripts/aitask_update.sh --batch <task_id> --status Ready --assigned-to "" --silent`,
         commit it with
         `aitask_task_commit.sh -m "ait: Revert t<task_id> to Ready (premise check)" <task_file>`,
         `./ait git push`, then the **Lock Release Procedure**
         (`lock-release.md`), and return to the calling skill's task selection.

## Advance after an approved replan

Runs when `premise_decision.choice` is `replan` and the renewed plan was
approved: from `SKILL.md` Step 7 (after the risk gate records), or from
`planning.md`'s "Approve and stop here" before the stop sequence releases the
lock. Ownership is expected in both, but it is **proven, not assumed**: the
"Approve and stop here" path runs before Step 7's ownership guard, so the
advance passes `--owner "<email>"` and refuses (`ADVANCE_REFUSED:not_owner`,
no write) unless the task's lock is held by that email on this host.

**Precondition — the review happened.** The approved plan must carry exactly one
`## Premise review` section whose `Evidence rows reviewed: <n>` line equals the
number of evidence rows (`CHANGED:` + `DELETED:` + `UNKNOWN:`) in
`premise_decision.protocol` (`planning.md` §6.1 "Premise evidence review"):

```bash
grep -c '^## Premise review' <plan_file>
sed -n 's/^Evidence rows reviewed: \([0-9][0-9]*\)$/\1/p' <plan_file>
```

If either check fails, **do not advance**: display "Premise baseline not
advanced — the plan does not record a review of all \<n\> evidence rows; the
check runs again on the next pick." and continue. An advance past evidence
nobody reviewed is exactly what this mechanism must never do.

Then the same transaction rules as `## Post-lock` "proceed": unverifiable rows →
no advance; `never_existed` rows → the same explicit keep/remove question; then
`advance` with the stored pair.

`ADVANCE_REFUSED:not_owner|…` → **terminal:** execute `## Ownership lost`, and
tell the caller the workflow has ended — Step 7 must not implement, and
planning's "Approve and stop here" must **not** run its stop sequence, which
would revert the status and release the lock another session now holds.

Anything else other than `ADVANCED:` → no advance; display the line and the
fresh `DISPLAY:` as information and continue. **Never re-ask the four-option
question here**: the plan is already approved, and the next pick re-checks.

## Ownership lost

Terminal. Reached when the ownership proof (`advance` → `ADVANCE_REFUSED:not_owner`,
or `owner` → `NOT_OWNER:`) shows this session no longer holds the task — another
owner took it, or another live session of the same user force-claimed it.

**Write nothing more, and undo nothing.** Do not revert the status, do not
release the lock (it is the new holder's), do not materialize gates, do not run
the Approved-Plan Stop Sequence or the Task Abort Procedure, and do not advance
anything: every one of those writes a task this session does not own.

Display: "Task t\<task_id\> is now held by \<detail\> — this session no longer
owns it. Stopping without further changes." Then show the **Stopped** banner
(see `workflow-end.md`) with the state-derived outcome — re-read the task's
`status` **read-only** (`Implementing` → `outcome=in-flight`, `Ready` →
`outcome=ready`, `Postponed` → `outcome=postponed`), reason "ownership lost —
held by \<detail\>", next "check the session that now holds t\<task_id\>" — and
end the workflow.
