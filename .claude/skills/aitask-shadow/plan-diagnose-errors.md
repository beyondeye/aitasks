# Diagnose skill/helper errors (in the followed agent)

A sub-procedure of the shadow skill (`aitask-shadow`). Use it when the followed
agent's captured screen shows **tool-call errors or retries** — signs of a bug in
a workflow skill definition or in a helper bash script it calls (wrong parameters,
or a bug in the script itself). Your job is to diagnose those errors, surface them
as a list of candidate concerns the user can pick from, and — for the ones the
user chooses — **offer** to spin each into its own fix-task via `/aitask-explore`.

This capability is **on-request only**: run it when the user asks you to diagnose
what is going wrong. It is deliberately *not* offered proactively — the shadow
never emits unsolicited error concerns.

**Inputs:** the captured screen (shadow Step 1). Refetch with
`aitask_shadow_capture.sh` if the screen may be stale. No plan file is needed.

**Advisory-only:** present everything to the user; never drive the followed
agent's pane. The fix-task offer below runs `/aitask-explore` in **your own**
pane — never the followed pane.

## Procedure

1. **Read the captured screen** (shadow Step 1; refetch if it may be stale).

2. **Scan for error / retry signals.** Look for:
   - `InputValidationError`
   - `Tool error:`
   - `Traceback (most recent call last):`
   - bash `error:` / stderr lines (e.g. `<script>.sh: line N:`, `command not found`,
     a non-zero-exit diagnostic)
   - **repeated identical commands** — the same tool call or bash line issued 2+
     times in succession (a retry loop).

   **Do not manufacture problems.** Error-*shaped* text is not always a live
   failure: a passing test run may print the word `error:` in narrative output, an
   *intentionally* failing test may be exactly what the agent expects, and a
   traceback the agent has pasted to *discuss* is not a fresh crash. Judge whether
   each signal reflects an actual, unhandled failure the agent is stuck on. If
   nothing on screen is a genuine error/retry problem, **say so plainly and stop**
   — emit no concern block.

3. **Attribute each genuine signal to the likely skill / helper.** For each error
   cluster, identify which workflow skill or `aitask_*.sh` helper the followed
   agent was running when it hit the error, and — where inferable — whether it
   looks like a *wrong-parameter call* (the caller passed bad arguments) versus a
   *bug in the script/skill itself*. Name the concrete file(s) to look at.

4. **Present the candidate concerns, then emit the marked concern block.** First
   give the user a short human-readable list (one item per error cluster, ordered
   by severity, each with: what failed, the likely cause, and the file to look
   at). Then append a machine-parseable copy of the *same* concerns so the user
   can forward a subset via minimonitor's concern picker instead of retyping.

   Emit exactly this fenced format (single source of truth:
   `aidocs/framework/shadow_concern_format.md`):

   ```
   ===AITASK-CONCERNS===
   - [high | aitask_pick_own.sh] The followed agent's claim call exits non-zero with `aitask_pick_own.sh: line 88: LOCK_DIR: unbound variable`, then retries the identical command three times — the helper dereferences LOCK_DIR before it is set, so every claim on this path crashes. Look at the variable's init in aitask_pick_own.sh; likely a missing default or an ordering bug rather than a bad caller argument.
   - [medium | task-workflow Step 4] The agent passes `--email ""` and the script emits `InputValidationError: email must be non-empty`, looping twice. The workflow's email-resolution branch is handing an empty string to the claim call instead of omitting the flag; the fix likely belongs in the Step 4 email branch, not the helper.
   ===END-CONCERNS===
   ```

   Format rules — all load-bearing for minimonitor's parser; match them exactly:
   - One concern per line, in the form `- [priority | region] body`.
   - The leading `- ` (dash **and** space) is **MANDATORY** on every concern line
     — it is the wrap-collision guard (a soft-wrapped continuation line never
     carries it, so the parser can't mistake wrapped text for a new item).
   - `priority` is one of `high`, `medium`, `low`.
   - `region` names the offending skill / helper (a script name, a skill step,
     etc.).
   - `body` carries the **full framing** — what failed, *why it bites* (the error
     and the likely cause), and the concrete file to look at. Match the substance
     of the corresponding prose item; do **not** compress it to a bare one-liner.
     "One logical line" is a **parser constraint** (emit no literal newline
     mid-concern — let the terminal soft-wrap), not a brevity constraint.
   - Order items by severity, matching the prose list.
   - **Always emit the closing `===END-CONCERNS===` fence** — minimonitor's
     auto-offer only fires on a complete block.
   - Emit the block **only when you found at least one genuine error/retry
     signal** (step 2). If there were none, omit the block entirely.

5. **Let the user choose which concerns to act on, then offer ONE action.** Ask
   the user which of the presented concerns actually warrant their own fix-task —
   use `AskUserQuestion` (multiSelect) with one option per concern plus a
   "None — just keep the marked concerns" choice. For each concern the user
   selects, **offer** to launch `/aitask-explore` seeded with a prompt naming that
   concern's skill / helper path(s) and the captured error excerpt, so the bug
   becomes its own scoped fix-task. Only on explicit confirmation do you launch it,
   in **your own** pane.

   Scope (v1): the offered action is **`/aitask-explore` with a seed prompt
   only** — do not branch into direct batch task creation here (a possible later
   enhancement). Never auto-launch, and never send anything to the followed pane.
