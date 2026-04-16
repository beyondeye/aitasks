---
priority: medium
effort: low
depends: []
issue_type: refactor
status: Done
labels: [brainstorming, ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-04-16 17:47
updated_at: 2026-04-16 18:22
completed_at: 2026-04-16 18:22
---

## Context

The section format reference block (explaining HTML comment section markers syntax) is currently duplicated across three brainstorm agent templates: explorer.md, synthesizer.md, and detailer.md. Each contains the same instructional text:

```
### Section Format
Wrap each major section ... in structured section markers using HTML comments:
  Opening: \<!-- section: name [dimensions: dim1, dim2] -->
  Closing: \<!-- /section: name -->
...
```

This was introduced in t571_2. It should be extracted into a shared file (e.g., `.aitask-scripts/brainstorm/templates/_section_format.md`) and included/referenced from each template to avoid drift.

## Key Files

- **CREATE**: `.aitask-scripts/brainstorm/templates/_section_format.md` — shared section format reference
- **MODIFY**: `.aitask-scripts/brainstorm/templates/explorer.md` — replace inline block with reference to shared file
- **MODIFY**: `.aitask-scripts/brainstorm/templates/synthesizer.md` — same
- **MODIFY**: `.aitask-scripts/brainstorm/templates/detailer.md` — same

## Implementation Notes

- The templates are used as work2do instructions for AI agents. The shared file content needs to be inlined into the template at assembly time, OR the template can instruct the agent to read the shared file. Check how `brainstorm_crew.py` assembles agent instructions (via `_read_template()` or similar) to determine the best approach.
- The detailer version says 'plan' instead of 'proposal' — the shared file should be generic enough for both, or parameterized.

## Verification

1. Read all three templates — verify they reference the shared file instead of duplicating the block
2. Run existing tests: `python3 -m unittest discover -s tests -p 'test_brainstorm_*.py'`
3. Verify an assembled agent input still contains the section format instructions
