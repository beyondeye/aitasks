---
priority: low
effort: low
depends: []
issue_type: test
status: Ready
labels: [sitrep]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
anchor: 2175
followup_kind: risk_mitigation
created_at: 2026-11-03 10:40
updated_at: 2026-11-03 11:51
---

## Origin

Risk-mitigation ("after") follow-up for t2175_2, created at Step 8d after implementation landed.

## Risk addressed

goal-achievement — heuristics tuned on Claude Code rendering:
"The passage-start detection and the marker search are tuned on Claude Code's
tool-call layout. On codex/opencode captures the passage range may be wrong, or
the marker invisible; the result is a linked duplicate triage item, never
suppressed advice · severity: medium"

## Goal

Once codex and opencode agents have finished picks that end in the
workflow-end banner (and have been frozen, so `capture.txt` exists), add
fixtures modelled on their real layout to `tests/fixtures/sitrep_harvest/`
(synthetic, as the README requires: real captures hold other projects'
content) and extend `tests/test_sitrep_harvest.py` / `tests/test_sitrep_harvest.sh`:

- the banner parses (indentation, glyphs, wrapping in that agent's renderer);
- the wrap-up passage starts at that agent's closing-message marker
  (`lib/sitrep_harvest.py` `MSG_RE` / `PROMPT_RE` are Claude-Code-only today);
- the `HARVEST_RUN:` first output line of the harvest call is visible in that
  agent's tool-call display, so piped-then-captured Stopped runs match instead
  of duplicating — or, if it is not, document the duplicate as expected.

Fix whatever heuristics those fixtures break. Identity must stay
normalization-free (explicit run id, archival commit, byte-exact passage).

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2175_6** id=2026-11-05T12:22:17Z.4b5f34c05be90ecd47c5d37b from=t2175_6 from_verified=yes at=2026-11-05T12:22:17Z base=6fc7b397232cf5bc2edc27ed4d45cc2cee114a08 base_branch=main dirty=yes host=omg16
>
> | t2175_6 landed in 6fc7b3972 (tree-relative, as of that commit). Where it meets your other-agent captures:
> | 
> | 1. The harvest now runs a confidence check (`sitrep_harvest.assess`). A banner line that no parsed banner starts on fires `banner_unparsed`, and a malformed `Created: aitasks/...` reference fires `created_unparsed`. Other agents' layouts that the Claude-Code grammar misses will therefore be preserved as review cases instead of certified as nothing_found: the whole raw input is kept byte for byte (`.aitask-sitrep/raw/`), with trusted case records under `cases/`.
> | 2. Those cases are ready-made inputs for you. `ait sitrep case list` / `case show <hex>` / `case read <hex>` find and read them. `case replay <hex>` re-runs the current grammar and writes nothing; `case export <hex> --out <dir>` turns a case the parser now handles into a fixture (redact it first), which is checked by `tests/test_sitrep_corpus_fixtures.py`. `tests/fixtures/sitrep_harvest/corpus/joined_banner/` is the first example.
> | 3. A grammar change should bump `PARSER_REV` (now 2), so each analysis records which grammar produced it. Receipts carry `cert=2`; a receipt without it is re-harvested.
