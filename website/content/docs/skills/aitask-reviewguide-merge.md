---
title: "/aitask-reviewguide-merge"
linkTitle: "/aitask-reviewguide-merge"
weight: 90
description: "Compare two similar review guides and merge, split, or keep separate"
---

Compare two similar review guide files and decide whether to merge them, deduplicate shared content, or keep them separate. This skill keeps the review guide library clean and free of redundant checks.

**Usage:**
```
/aitask-reviewguide-merge security perf   # Compare two specific guides (fuzzy match)
/aitask-reviewguide-merge security        # Compare a guide with its similar_to target
/aitask-reviewguide-merge                 # Batch: find and process all similar pairs
```

> **Note:** Must be run from the project root directory. See [Skills overview](..) for details.

## Workflow Overview

**Single-pair mode** (with arguments):

1. **Resolve files** — Fuzzy-matches arguments to guide files. With one argument, uses the file's `similar_to` field to find the second file
2. **Detailed comparison** — Categorizes every review bullet as duplicate (same check, different wording), unique to file A, or unique to file B. Computes overlap percentage
3. **Propose action** — Recommends merge (>70% overlap), merge or keep separate (30-70%), or keep separate (<30%)
4. **Execute** — Options: merge into file A, merge into file B, keep separate (deduplicate shared bullets), or cancel. Merging combines unique bullets, unions metadata labels, deletes the source file, and updates `similar_to` references across all other guides

**Batch mode** (no arguments):

1. **Find merge candidates** — Scans all guides for `similar_to` relationships and overlap counts
2. **Optional environment filter** — Narrow candidates to a specific environment (e.g., only Python guides)
3. **Iterate** — Presents candidate pairs sorted by overlap (highest first) with pagination. Each pair goes through the single-pair workflow
4. **Summary** — Reports pairs processed, files merged, files kept separate, and files deleted

## Key Capabilities

- **Semantic deduplication** — Identifies bullets that check the same thing even when worded differently, rather than doing simple text comparison
- **Non-destructive keep-separate** — When keeping guides separate, removes only exact duplicates and clears the `similar_to` field so they won't be flagged again
- **Reference integrity** — After deleting a merged source file, updates `similar_to` in any other guide that referenced the deleted file
- **Feeds from classify** — The `similar_to` relationships that drive merge candidates are established by [`/aitask-reviewguide-classify`](../aitask-reviewguide-classify/)
