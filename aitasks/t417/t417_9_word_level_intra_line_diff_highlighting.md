---
priority: medium
effort: medium
depends: [t417_8]
issue_type: feature
status: Ready
labels: [tui, brainstorming]
created_at: 2026-03-19 09:50
updated_at: 2026-03-19 09:50
---

Add word-level (intra-line) diff highlighting in the side-by-side diff view. Currently, when two lines differ by only a few words, the entire line is highlighted as changed. This task adds secondary word-level diffing for replace hunks to highlight only the specific changed words/spans within each line.
