# Audience rules for simple-words answers

**Advisory-only:** never edit proposal files, node YAML or any brainstorm session
state, and never run a mutating `ait brainstorm` command — present everything to the user.

A sub-procedure of the brainstorm discuss skill (`aitask-brainstorm-discuss`).
The other procedures read this file whenever they produce a *simple-words*
answer (`>c`, `>e`) or a plain-words line (`>f`). It holds two rules, adapted
from the shadow companion's audience rules and kept here so this skill stays
self-contained.

## 1. Who this is for (binding audience rule)

A simple-words answer is written for a reader who **will not open the
proposal** and has not followed the brainstorm in detail. Name outcomes and
behaviours, not mechanisms:

- no file paths, no function or class names, no framework terms, no dimension
  keys (`requirements_…`, `tradeoff_…`) and no node ids in running prose — refer
  to proposals by their handle and title ("proposal A, the Go-binary one");
- when a single technical word has no plain substitute, unpack it in the same
  sentence ("a lock — the marker that says someone is already working on this —");
- if a sentence would only make sense to someone who has the proposal open,
  rewrite it.

**Simple is not shorter-by-omission.** Plain words change the vocabulary, not the
coverage: every point that matters to the user's decision still appears.

## 2. The plain-words line (derivation order is load-bearing)

Where a procedure asks for it, a finding ends with one line:

    In plain words: <one or two sentences a non-expert can follow>

**Compose the full finding first** — the complete technical statement with its
reasoning and, for a flaw, its `Improves:` / `Worsens:` / `Effort:` trailer —
**then restate *that finding*** in plain language: what is wrong or missing, what
goes wrong for the user if it stays, and what would change if it were addressed.
Because the line is derived from the finding, the two cannot diverge. A finding
you cannot restate plainly is a finding you do not yet understand; go back to it.

The same order applies to a whole simple-words answer: work out the complete
answer first, then write it for the reader above. Never write the simple version
from a skim.
