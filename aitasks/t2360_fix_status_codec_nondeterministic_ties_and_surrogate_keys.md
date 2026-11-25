---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [monitor]
gates: [risk_evaluated]
followup_kind: upstream_defect
created_at: 2026-11-25 10:49
updated_at: 2026-11-25 10:49
---

## Origin

Spawned from aitasks_go t47_1 (the Go port of the monitor status protocol
codec) during its Step 8b review. Both defects were found while pinning the Go
codec byte for byte to this one, at aitasks commit 72bdd15db.

## Upstream defect

- `.aitask-scripts/monitor/status_protocol.py:281 — _v_selection sorts set() output by pane number only, so two spellings of one pane number ("%1", "%01") come out in hash-randomized order: encode output differs from process to process (also _sorted_ids, :906)`
- `.aitask-scripts/monitor/status_protocol.py:685-688 — two object keys that are distinct lone surrogates both become U+FFFD on encode, so the codec writes a line with a duplicate member that its own decode rejects`

## Diagnostic context

1. **Pane-number ties.** `_v_selection` returns
   `sorted(set(ids), key=_pane_num)`. `%1`, `%01` and `%001` are all valid pane
   ids (`%[0-9]{1,10}`) with the same number, and `sorted` is stable, so their
   order is the set's iteration order. Probed with two runs of
   `python3 -I` on `{"type":"set_content","content":["%1","%01","%001","%0001"]}`:
   the normalized order differed between the runs (`-I` ignores
   `PYTHONHASHSEED`). `_sorted_ids` (frame `completed`, `removed`) has the same
   shape. tmux itself never writes a leading zero, so this needs a client that
   sends one; the effect is a normalized message that is not a function of its
   input. The Go codec breaks the tie by string and documents the difference
   as a residual (goengines/internal/monitord/statusproto/doc.go, residual 2);
   its reference generator skips such inputs.
2. **Colliding surrogate keys.** `encode` serializes with `ensure_ascii=False`
   and, when the UTF-8 encode fails, replaces every surrogate in the whole
   text with U+FFFD. A map whose keys are the distinct strings `"\ud800"` and
   `"\udc00"` (reachable from the wire through escapes, e.g. as `sessions`
   keys) decodes fine, and encodes to a line with two identical `"�"`
   keys. `decode` rejects that line (`duplicate member`). So
   `decode(encode(decode(x)))` fails for an `x` that decoded. The Go codec
   reproduces this byte for byte (reference case `sur_keys_collide`).

## Suggested fix

1. Add the string as a secondary sort key (`key=lambda i: (_pane_num(i), i)`)
   in `_v_selection` and `_sorted_ids`, or reject a pane id with a leading
   zero. Either makes the output deterministic.
2. Reject a lone surrogate in a map key at validation, or check for collisions
   after replacement in `encode` and raise `ProtocolError`.

Both change what the codec accepts or writes, so the Go twin must follow:
regenerate the aitasks_go reference (aitasks_go goengines/README.md, "Python
reference and drift") and drop or adjust residual 2 there.
