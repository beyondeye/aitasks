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
