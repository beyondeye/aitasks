---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [gates]
gates: [risk_evaluated]
anchor: 1605
followup_kind: upstream_defect
created_at: 2026-08-25 22:12
updated_at: 2026-08-25 22:12
---

## Origin

Spawned from t1609 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/gate_ledger.py:531,535-537` — `_read_frontmatter_list_from_text`
  strips a *run* of quote chars off either end via `.strip("'\"")`, so a block
  item `- echo "hi"` becomes `echo "hi` (trailing quote eaten). Deliberately
  not changed in t1609: this reader feeds only identifier-shaped gate fields, and
  bash is now the YAML-correct side. Reachable only if a command-shaped value
  is ever read through it.
- `.aitask-scripts/lib/yaml_utils.sh:250-262` — the value-capture loop counts
  `[`/`]` without quote awareness, so `verify_build: ["ls ["]` leaves the depth
  counter at 1 and swallows subsequent config lines until a `]` appears.
  Pre-existing; untouched by t1609.
- `.aitask-scripts/lib/config_utils.py:326-345` — the settings TUI saves
  `verify_build` through `yaml.safe_dump(default_flow_style=False)`, which
  single-quotes any scalar starting `[`, `*`, `#` or containing `: `. Harmless
  now that the reader unquotes, but it means the TUI silently changes the
  on-disk quoting of a command the user typed unquoted.

## Diagnostic context

t1609 fixed the asymmetry where `read_yaml_list`'s BLOCK branch emitted items
verbatim (quotes intact) while its inline `[a, b]` branch deleted every `[`,
`]`, `'`, `"` in the value. Both branches now share `_yaml_norm_list_item`:
trim, then strip ONE surrounding matching quote pair.

That work established two things this task follows up on.

**1. bash and Python now disagree in the opposite direction.** The bash reader
feeds `active_gates_digest` via `aitask_gate.sh:813` `_yaml_list_csv`, and the
digest halves must match `gate_ledger._read_frontmatter_list_from_text`
byte-for-byte. t1609 moved bash *toward* Python on every realistic case
(verified live: block `- "a b"` / `- c··` and inline `[a, b]···` now agree), but
Python's `.strip("'\"")` remains more aggressive than bash's single-pair rule.
The divergence is unreachable today because the digest reads only
identifier-shaped fields (`gates`, `active_gates`, `active_gates_filtered`) — an
awk scan over the whole corpus found 767 occurrences, zero containing a quote,
an inner bracket, or trailing whitespace. It becomes reachable the moment any
command-shaped or path-shaped value is read through that Python function.
`tests/test_yaml_utils.sh` carries a cross-language pin for the identifier case;
it does **not** cover the divergent case, by design.

**2. The bracket-counting hazard is orthogonal and untouched.** t1609 explicitly
declined it in the plan's "Declined / out of scope" section so review would not
re-raise it. It is a *parse* bug, not a quoting bug: the capture loop's depth
counter is what joins PyYAML-wrapped flow lists, and it has no notion of quotes.

## Suggested fix

- **gate_ledger.py:** replace `.strip().strip("'\"")` with the same single-pair
  rule bash uses, in both the inline and block branches. Decide deliberately
  whether Python should also emit empty block items (bash does; Python's
  `if ln.strip()` drops them) — that is a second, separate divergence. Extend
  the `tests/test_yaml_utils.sh` cross-language pin to cover `echo "hi"` once
  the two agree.
- **yaml_utils.sh capture loop:** make the depth counter quote-aware, or bound
  the join to the frontmatter block so a malformed value cannot swallow
  arbitrary following lines. Note t1444's constraint: this is the framework's
  hottest reader and the path is deliberately fork-free, so a per-character
  bash loop is not acceptable.
- **config_utils.py:** likely no code change — decide whether the round-trip
  re-quoting is worth documenting in the settings TUI docs now that both
  quoted forms resolve correctly.
