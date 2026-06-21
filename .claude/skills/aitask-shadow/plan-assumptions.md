# Plan Assumption Surfacing

A sub-procedure of the shadow skill (`aitask-shadow`). Use it when the user wants
the plan's hidden premises made explicit — "what is this assuming?", "what has to
be true for this to work?". Plans fail most often on an unstated assumption that
quietly doesn't hold.

**Inputs:** the captured screen (shadow Step 1) and/or the fetched plan file
(shadow Step 2). Fetch the full plan first if only a fragment is on screen.

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

   Map assumptions to items: emit one item per **dangerous** assumption
   (load-bearing AND unverified — the ones Step 4 ordered first); include lesser
   ones only if useful. Set `priority` by how exposed the assumption is:
   - load-bearing **and** unverified → `high`,
   - load-bearing **and** verified, or peripheral **and** unverified → `medium`,
   - peripheral → `low`.

   Emit exactly this fenced format (single source of truth:
   `aidocs/framework/shadow_concern_format.md`):

   ```
   ===AITASK-CONCERNS===
   - [high | sequencing] The plan assumes sibling t1037_1's parser has already landed, but nothing in it verifies that. If the parser isn't there yet, the emitted block has no consumer and the whole feature silently does nothing — no error, just a no-op that looks like success in a demo. Worth confirming the parser module exists (or wiring it as an explicit dependency) before relying on it; how to sequence that is your call.
   - [medium | behavior of other code] The plan assumes aitask_shadow_capture.sh hands the parser wrap-joined lines, but the capture call omits tmux's -J flag. Long concern bodies will then split mid-word at the pane edge and the parser's space-join will stitch the fragments with a stray space inside a word. It only surfaces on bodies long enough to wrap, so it passes short-example tests and breaks in real use. Adding -J (or otherwise rejoining) at the capture site would fix it — exact spot left to you.
   ===END-CONCERNS===
   ```

   Rules — all load-bearing for minimonitor's parser; match them exactly:
   - One concern per line, in the form `- [priority | region] body`.
   - The leading `- ` (dash **and** space) is **MANDATORY** on every concern
     line — it is the wrap-collision guard (a soft-wrapped continuation line
     never carries it, so the parser can't mistake wrapped text for a new item).
   - `priority` is one of `high`, `medium`, `low` (mapped as above).
   - `region` names the assumption category (`environment/tooling`,
     `data/inputs`, `behavior of other code`, `sequencing`, `intent/scope`) or a
     named plan region.
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
   - **Always emit the closing `===END-CONCERNS===` fence** — minimonitor's
     auto-offer only fires on a complete block.
   - Emit the block **only when you have at least one assumption worth
     forwarding**; otherwise omit it entirely.
