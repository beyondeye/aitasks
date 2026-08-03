---
priority: low
effort: low
depends: []
issue_type: documentation
status: Ready
labels: [docs, codeagent]
gates: [risk_evaluated]
anchor: 1307
created_at: 2026-07-29 21:38
updated_at: 2026-07-29 21:38
boardidx: 96256
---

## Origin

Risk-mitigation ("after") follow-up for t1318, created at Step 8d after
implementation landed.

## Risk addressed

*Goal-achievement risk (low) — partly-untrustworthy promotion checklist:*

> The promotion checklist is only **partially** refreshed: registering these
> three files in a doc whose other `opus4_*` line references are stale leaves
> the next promoter with a partly-untrustworthy checklist.

`aidocs/framework/model_reference_locations.md` is the canonical "what to touch
when promoting a model to default" registry. Its omission of three test files is
exactly why t1241 promoted the defaults to `claudecode/opus5` and left them red
(fixed in t1318). t1318 registered those three files but deliberately scoped out
the rest of the doc's staleness.

## Known stale content

- Line-number references to `opus4_6` / `opus4_7` / `opus4_8` throughout —
  reported stale at (approximately) lines 36, 44-49, 74, 85-90, 109-115, 228,
  354-355. **Re-derive these; do not trust the list.** Line numbers shift, and
  t1318 already inserted rows into §7.
- §7 classifies `tests/test_codeagent.sh` lines 127-144 etc. as
  `needed_for_promote` using line numbers that predate several edits.
- The §1 registry tables and the "Summary matrix" counts should be re-checked
  against the current `models_*.json` (12 claudecode models registered today).

## Sweep both spellings

**Critical, learned the hard way in t1318:** a model reference appears in two
distinct spellings and a sweep must cover both.

- Agent-string form: `claudecode/opus4_8`
- **cli_id form: `claude-opus-4-8`** (dashes)

t1318's planning sweep searched only the first form and consequently missed two
live stale assertions (`tests/test_codeagent_trail.sh:88`,
`tests/test_codeagent_work_report.sh:80`), which surfaced only when the suite was
run. Any audit driven by this doc must grep for both, e.g.:

```bash
grep -rnE 'claudecode/(opus|sonnet|haiku)4_[0-9]|claude-(opus|sonnet|haiku)-4-[0-9]' \
  tests/ .aitask-scripts/ aidocs/ website/content/ seed/
```

## Goal

Refresh the doc so a future promoter can trust it end to end:

1. Re-derive every line reference against current file contents.
2. Re-check each `needed_for_promote` / `informational_only` / `needed_for_add`
   tag — some entries have since become promotion-proof.
3. Add the two-spelling sweep guidance above to the doc itself, so the next audit
   does not repeat t1318's miss.
4. Preserve the t1318 note in §7 and its cross-reference to
   `aidocs/framework/testing_conventions.md` (see t1339, which adds the
   testing-conventions side of that link).

## Verification

- Every line number cited in the doc resolves to the content it claims (spot-check
  each cited file:line).
- The two-spelling grep above is documented in the doc and returns no
  *default-coupled assertion* hits that the doc does not list.
