# Compare proposals

**Advisory-only:** never edit proposal files, node YAML or any brainstorm session
state, and never run a mutating `ait brainstorm` command — present everything to the user.

A sub-procedure of the brainstorm discuss skill (`aitask-brainstorm-discuss`).
Serves `>c` (compare in simple words) and `>cd` (compare in depth).

**Inputs:** the proposals the user named (handles or node ids; default: every
proposal listed at Step 0), their `PROPOSAL:` paths, and — for the detailed
depth — their `META:` node YAML.

## 0. Preconditions

- **At least two proposals are needed.** With only one resolved proposal, say so
  in one line and offer `>e` (explain it) or `>h` (how it evolved — its ancestors
  are the natural comparison) instead. Do not compare a proposal with itself.
- A proposal whose path was `NOT_FOUND` is left out; name it and say why.
- **Read each compared proposal in full now.** Step 0 only skimmed titles; a
  comparison built from those skims is not a comparison.

## 1. Simple depth (`>c`)

Read `discuss-audience.md` first — its audience rule binds this whole answer.

1. **What each proposal is betting on** — one or two sentences per proposal: the
   central idea, and the problem it thinks matters most.
2. **The differences that matter** — the one or two differences that would
   actually change the outcome for the user. Skip differences in wording,
   structure or level of detail that lead to the same result.
3. **Who should prefer which** — for each proposal, the situation or priority
   under which it is the better choice ("pick A if you want this running next
   month; pick B if you expect to support many more projects").
4. **Where they agree** — one line, so the user knows what is *not* at stake.

End by offering `>cd` for the detailed version.

## 2. Detailed depth (`>cd`)

1. **Read the node YAML** (`META:` path) for every compared proposal. Dimension
   fields are the keys starting with `requirements_`, `assumption_`,
   `component_` and `tradeoff_`. If a `META:` path was `NOT_FOUND`, compare that
   proposal from its text alone and say the table is partial.
2. **Per-dimension table.** Rows = the union of dimension keys, grouped by prefix
   (Requirements, Assumptions, Components, Tradeoffs); one column per proposal.
   Each cell is a short paraphrase of that proposal's value, or `—` when the
   proposal does not set the key. Mark rows whose values are **substantively**
   different — a reworded but equivalent value is not a difference.
3. **Trade-offs.** For each marked row, what the difference buys and what it
   costs.
4. **What each makes easy or hard later.** The future changes each proposal
   invites or closes off (extending it, reversing it, operating it).
5. **Where they are actually equivalent.** Rows or whole areas that look
   different but would behave the same in practice — so the user does not spend
   a decision on them.
6. **Proposal-text differences the dimensions miss.** Anything decision-relevant
   that lives only in the proposal body.

Close with a short verdict framed as conditions ("A is stronger if …, B if …"),
never as a directive. Offer `>f` on any proposal whose risk looked material.
