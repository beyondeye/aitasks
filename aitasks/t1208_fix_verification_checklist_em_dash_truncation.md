---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [verification]
anchor: 1202
created_at: 2026-07-21 18:09
updated_at: 2026-07-21 18:09
boardidx: 40
boardcol: bug_fixes
---

## Problem

`_strip_annotation` in `.aitask-scripts/aitask_verification_parse.py:118-121`
splits an item's text on the **first** occurrence of `SUFFIX_SPLIT`
(`" — "` — space, U+2014 em-dash, space) anywhere in the line:

```python
SUFFIX_SPLIT = " — "

def _strip_annotation(text: str) -> str:
    if SUFFIX_SPLIT in text:
        return text.split(SUFFIX_SPLIT, 1)[0].rstrip()
    return text
```

It is meant to strip a previously written `" — PASS 2026-07-21 17:43 <note>"`
annotation before rewriting one. But the delimiter is not anchored to the
annotation boundary, so **any checklist item whose own prose contains an
em-dash loses everything after that em-dash** on the first
`aitask_verification_parse.sh set` — permanently, since the file is rewritten
in place.

## Live occurrence

Hit during the auto-verification of **t1202** (verifying t1200). Two of its six
checklist items were truncated mid-sentence on their first `set`:

- Item 2 lost `Advanced is the recommended tier; say 'advanced review' for it."
  A user must never have to infer the tier from the output.`
- Item 3 lost `this is the core "I very rarely get concerns" symptom and can
  only be judged on live output.`

Both were restored by hand from commit `8f23b114e`. Without that recovery the
archived task file — the durable record of *what was verified* — would have
silently misstated the acceptance criteria.

`_is_section_header` (line 133) calls the same helper, so a section-header
bullet containing an em-dash can also be misclassified.

## Impact

Silent, permanent data loss in the archived verification record. Em-dashes are
common in this repo's generated checklist prose (the shadow/manual-verification
follow-up procedures emit them routinely), so recurrence is likely rather than
exotic. Pre-existing; unrelated to t1200.

## Suggested fix

Anchor the strip to the real annotation boundary rather than the first
em-dash — e.g. match from the **right** against
`" — (PASS|FAIL|SKIP|DEFER) \d{4}-\d{2}-\d{2} \d{2}:\d{2}"` and strip only
that suffix, leaving item prose untouched. Exact form is the implementer's call.

## Acceptance criteria

- [ ] An item whose text contains ` — ` survives a `set` with its full text intact.
- [ ] Re-running `set` on an already-annotated item replaces the annotation
      (no annotation stacking) — including when the item text also contains an em-dash.
- [ ] Regression test in `tests/` covering both cases above, plus a
      section-header bullet containing an em-dash.
- [ ] `_is_section_header` still classifies correctly.

**Found by:** t1202 auto-verification (see `aiplans/p1202_manual_verification_auto.md`,
"Upstream defect identified").
