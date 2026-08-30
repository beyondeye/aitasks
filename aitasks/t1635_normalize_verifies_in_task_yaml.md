---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [backlog, planning]
anchor: 1569
followup_kind: risk_mitigation
created_at: 2026-08-28 17:52
updated_at: 2026-08-28 17:52
boardcol: now
boardidx: 19526
---

## Origin

Risk-mitigation ("after") follow-up for t1569_2, created at Step 8d after implementation landed.

## Risk addressed

`verifies:` id shapes are heterogeneous corpus-wide; every future consumer must
re-canonicalise or silently miss 2/3 of entries. · severity: medium

Measured over the live corpus during t1569_2 (2026-08-28):

| field | shapes present |
|---|---|
| `anchor` | **167 x Python `int`** — never a string, never `t`-prefixed |
| `verifies` | 125 x `'t1018_1'`, 59 x `int`, 3 x bare `'1018_1'` |

`task_yaml.parse_frontmatter` normalises **neither** field for this purpose:
`_normalize_task_ids` covers only `depends` / `children_to_implement` /
`folded_tasks`, and the scalar `_normalize_task_id` prefixes only a
`^\d+_\d+$` *string* while explicitly preserving `int` type. So a consumer that
reads `verifies:` and looks ids up in a bare-string-keyed map misses 125 of 187
entries — silently, because a miss is indistinguishable from "no such origin".

t1569_2 handled this locally by canonicalising every id through
`dep_resolution.canonical_dep_id` inside `lib/followup_origin.py`. That is
correct for one consumer but does not scale: each new reader of `verifies:` must
rediscover the hazard.

## Goal

Add `verifies` to `task_yaml`'s id-normalisation list so consumers stop
re-canonicalising, and the parser returns one id form for this field.

**This was deliberately NOT done inline in t1569_2** (`inline_risk: high`,
`added_complexity: high`): `task_yaml.parse_frontmatter` is the shared frontmatter
parser read by the board, `ait ls`, the monitor, the work report, applink and the
gate machinery. Changing what it returns for a field is a cross-cutting behaviour
change with its own blast radius, and it needs its own risk evaluation rather
than riding along on an unrelated feature.

Scope to settle when planning this:

- Which normalisation `verifies` should get. `_normalize_task_ids` yields a
  `t`-prefixed form (`'t85_2'`) and leaves plain ints alone; `canonical_dep_id`
  yields a bare string (`'85_2'`). These are **different target forms**, and
  picking the `t`-prefixed one would still leave `int` anchors unnormalised —
  so it would not actually remove the need for consumers to canonicalise.
  Decide deliberately; do not assume symmetry with `depends`.
- Whether `anchor` should be included (today it is normalised only when it is
  already a `^\d+_\d+$` string, so all 167 live int anchors pass through raw).
- Every existing reader of `verifies:` / `anchor:` must be swept: a consumer
  that currently compares against the raw form would break when the parser
  starts returning a different one. Enumerate them before changing the parser.
- `lib/followup_origin.py` should then drop its local canonicalisation, or keep
  it as a defensive no-op — decide which, and say why.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests` — read ONLY the last line.
- A test asserting the chosen form for all three live `verifies` shapes
  (`int`, `'t1018_1'`, bare `'1018_1'`).
- A regression test per swept consumer, proving it still resolves after the
  parser's return form changes.
