# Plan Assumption Surfacing

A sub-procedure of the shadow skill (`aitask-shadow`). Use it when the user wants
the plan's hidden premises made explicit — "what is this assuming?", "what has to
be true for this to work?". Plans fail most often on an unstated assumption that
quietly doesn't hold.

**Inputs:** the captured screen (shadow Step 1) and/or the fetched plan file
(shadow Step 2). Fetch the full plan first if only a fragment is on screen. When
you (re)capture the followed pane to read the plan, use the deeper plan-review
capture — `./.aitask-scripts/aitask_shadow_capture.sh --deep` — because plans
are long and the default 200-line window can truncate earlier constraints,
decisions, or risk notes. Pass no pane id: the helper resolves your bound
followed pane itself (add `<followed_pane_id>` only if Step 1 also had to).

**Advisory-only:** present the findings to the user; never drive the followed
agent's pane.

## Procedure

1. **Read the plan in full.**

2. **Enumerate the assumptions it relies on** — the things the plan takes for
   granted without stating or verifying. Look across:
   - **Environment / tooling** — a tool or version is present, a file/config
     exists, a path is writable, a service is reachable.
   - **Data / inputs** — shape, size, encoding, ordering, non-emptiness,
     uniqueness of the data it processes.
   - **Behavior of other code** — an API returns what the plan expects, a helper
     has no side effects, a caller invokes it a certain way.
   - **Sequencing / dependencies** — another task has landed, a migration ran, a
     step earlier in the flow already happened.
   - **Intent / scope** — the plan assumes it understood the user's actual goal,
     or that out-of-scope cases truly are out of scope.

3. **For each assumption, record:**
   - a one-line statement of the assumption,
   - whether it is **load-bearing** (the plan fails if it's false) or peripheral,
   - whether the plan **verifies** it or just trusts it,
   - how the user could confirm it, if it matters.

4. **Highlight the dangerous ones** — load-bearing **and** unverified. These are
   where the plan is most likely to silently go wrong. Order the list so these
   come first.

5. **Keep it grounded.** List assumptions the plan actually makes, not every
   conceivable precondition. Present everything to the user to judge; suggest, if
   asked, which assumptions would be worth turning into an explicit check.

6. **Also emit the structured concern block (for pick-and-forward).** After the
   human-readable list above, append a machine-parseable copy of the dangerous
   assumptions so the user can tick a subset and forward them to the followed
   agent via minimonitor's concern picker — instead of retyping them. This block
   is **additive**: it does not replace the prose, and it does **not** relax the
   advisory-only guardrail (it is text for the *user* to copy; you still never
   drive the followed pane).

   **Consult the rejection store before emitting.** Using the source task id
   from your launch arguments or Step 2 — resolving one now if you have neither
   (it is inferable from the followed agent's window name, e.g.
   `agent-pick-635_3`) — run
   `./.aitask-scripts/aitask_shadow_rejected.sh list <task_id>` and drop every
   fresh concern that is substantively the same as a previously-rejected entry,
   even when reworded. The full contract is in the rules list below.

   Map assumptions to items: emit one item per **dangerous** assumption
   (load-bearing AND unverified — the ones Step 4 ordered first); include lesser
   ones only if useful. Set `priority` by how exposed the assumption is:
   - load-bearing **and** unverified → `high`,
   - load-bearing **and** verified, or peripheral **and** unverified → `medium`,
   - peripheral → `low`.

   Emit a block delimited by an opening `===AITASK-CONCERNS===` line and a
   closing `===END-CONCERNS===` line (those two exact literals; single source of
   truth: `.claude/skills/aitask-shadow/concern-format.md`), with one concern per
   line between them. The concern lines themselves look like:

   ```
   Round: 1 @ 2026-08-11T14:03:27Z
   - [high | sequencing] The plan assumes sibling t1037_1's parser has already landed, but nothing in it verifies that. If the parser isn't there yet, the emitted block has no consumer and the whole feature silently does nothing — no error, just a no-op that looks like success in a demo. Worth confirming the parser module exists (or wiring it as an explicit dependency) before relying on it; how to sequence that is your call.
   - [medium | behavior of other code] The plan assumes aitask_shadow_capture.sh hands the parser wrap-joined lines, but the capture call omits tmux's -J flag. Long concern bodies will then split mid-word at the pane edge and the parser's space-join will stitch the fragments with a stray space inside a word. It only surfaces on bodies long enough to wrap, so it passes short-example tests and breaks in real use. Adding -J (or otherwise rejoining) at the capture site would fix it — exact spot left to you.
   ```

   **Emit a round header as the first line inside the block.** Immediately
   after the opening fence — before the first `- [` marker — emit exactly one
   line of the form `Round: <N> @ <timestamp>`, for example
   `Round: 2 @ 2026-08-11T14:03:27Z`. If the request that triggered this review
   names a round ("recheck round N"), use that N; otherwise N is 1 for the
   first review you run in this conversation and increments by one on each
   later review you run in it (any review sub-procedure counts; a fresh shadow
   session starts at 1 again — the timestamp is what disambiguates). Obtain the
   timestamp by running `date -u +%Y-%m-%dT%H:%M:%SZ` — never estimate it. A
   **zero-concern** review (nothing found, or suppression removed everything)
   still emits the block: the two fences with only this header between them,
   which is the machine-readable record that the round completed clean.

   Rules — all load-bearing for minimonitor's parser; match them exactly:
   - One concern per line, in the form `- [priority | region] body`.
   - The leading `- ` (dash **and** space) is **MANDATORY** on every concern
     line — it is the wrap-collision guard (a soft-wrapped continuation line
     never carries it, so the parser can't mistake wrapped text for a new item).
   - `priority` is one of `high`, `medium`, `low` (mapped as above).
   - `region` names the assumption category (`environment/tooling`,
     `data/inputs`, `behavior of other code`, `sequencing`, `intent/scope`) or a
     named plan region — it is **mandatory and never empty** (it is the row's
     only title in minimonitor's picker; an omitted one renders as
     `(no region)`) — and MUST stay **short** (≤ ~30 chars): use a category
     or a `basename.ext:LINE` locus, never a full repo path (put the full path
     in the body instead). The whole `[priority | region]` marker must survive
     on ONE rendered row: some agent TUIs hard-wrap long lines with literal
     newlines that even a wrap-joined capture cannot rejoin, and a wrap
     *inside the bracket* makes the item unparseable to minimonitor.
   - `body` carries the **full framing** — the assumption, *why it is dangerous*
     (what silently goes wrong if it's false), and enough context for the
     receiving agent to choose **how** to confirm or harden it. Match the
     **substance** of the corresponding prose item from Step 3; do **not**
     compress it to a bare one-liner — the framing is as important as the point.
     "One logical line" is a **parser constraint** (emit no literal newline
     mid-concern — let the terminal soft-wrap), **not** a brevity constraint: a
     rich, multi-sentence body that soft-wraps across several rows is correct and
     reassembles into one concern.
   - Order items by priority, matching the prose list (dangerous ones first).
   - **Suppress previously-rejected concerns.** Before emitting, run
     `./.aitask-scripts/aitask_shadow_rejected.sh list <task_id>`. Exactly three
     outcomes are defined: the single line `NO_REJECTIONS` means nothing is
     rejected; a printed body is the user's previously-rejected concerns; and
     **anything else** — a non-zero exit (a malformed task id exits `2`), empty
     output, or output matching neither shape — means you could not consult the
     store, so emit every fresh concern and state that rejection suppression was
     skipped. Never read an error as "nothing was rejected". Drop a fresh
     concern only when it is substantively the same as a rejected one; when
     unsure, **keep it and say why** (fail-open). Whenever N ≥ 1 were dropped,
     report `Suppressed N previously-rejected concern(s).` in the prose before
     the block. When no task id can be resolved, say suppression was skipped.
   - **Always emit the closing `===END-CONCERNS===` fence** — minimonitor's
     auto-offer only fires on a complete block.
   - **Round header.** The first line after the opening fence is
     `Round: <N> @ <timestamp>` and nothing else. It MUST come **before** the
     first `- [` marker — placed after an item it is absorbed into that item's
     body and the round is lost — and it must never itself begin with `- [`.
     Take N from the request when it names a round ("recheck round N"), else
     count from 1 within this conversation; get the timestamp from
     `date -u +%Y-%m-%dT%H:%M:%SZ`, never by estimate. A **zero-concern**
     review — no assumption worth forwarding after suppression — still emits
     the fences with only this header between them (say so in the prose).
     Minimonitor reads the header to show the round, to re-offer the picker
     when a later round repeats the same concerns, and to judge concern
     freshness.
