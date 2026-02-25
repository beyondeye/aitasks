---
title: "/aitask-reviewguide-classify"
linkTitle: "/aitask-reviewguide-classify"
weight: 80
description: "Classify a review guide by assigning metadata and finding similar guides"
---

Classify a review guide file by assigning metadata and finding similar existing guides. This skill builds the metadata foundation that makes [`/aitask-review`](../aitask-review/) auto-detection work effectively.

**Usage:**
```
/aitask-reviewguide-classify security     # Classify a specific guide (fuzzy match)
/aitask-reviewguide-classify              # Batch: find and classify all incomplete guides
```

> **Note:** Must be run from the project root directory. See [Skills overview](..) for details.

## Step-by-Step

**Single-file mode** (with argument):

1. **Resolve file** — Fuzzy-matches the argument against markdown files in `aireviewguides/`. If multiple matches, prompts for selection
2. **Analyze content** — Reads the guide's headings, bullets, and topics to determine what it reviews
3. **Assign metadata** — Proposes values for `reviewtype` (single classification from vocabulary), `reviewlabels` (3-6 topic tags), `environment` (language/framework, or universal for `general/` guides), and `similar_to` (guides with overlapping coverage)
4. **Confirm and apply** — Shows proposed metadata for review. Options: apply as proposed, modify, or cancel. On apply, updates the frontmatter and commits

**Batch mode** (no argument):

1. **Scan for incomplete** — Finds all guides missing `reviewtype`, `reviewlabels`, or `environment` (for non-general guides)
2. **Iterate** — Processes each incomplete file through the single-file process (Steps 2-4 above)
3. **Summary** — Reports files classified, new vocabulary values added, and `similar_to` relationships discovered

## Key Capabilities

- **Fuzzy file matching** — No need to type the full filename; a partial match like `security` or `python_best` resolves to the right file
- **Vocabulary-aware** — Reads existing values from `aireviewguides/reviewtypes.txt`, `aireviewguides/reviewlabels.txt`, and `aireviewguides/reviewenvironments.txt`. Strongly prefers existing terms for consistency, but can add new values when needed
- **Similarity detection** — After assigning metadata, compares against all other guides using a scoring formula based on shared labels, type match, and environment overlap. Sets `similar_to` when overlap is significant
- **Batch autocommit** — In batch mode, choose between autocommitting after each file or a single commit at the end

When `similar_to` is set, consider running [`/aitask-reviewguide-merge`](../aitask-reviewguide-merge/) to consolidate overlapping guides.

## Workflows

For the full review workflow including guide management, see [Code Review](../../workflows/code-review/).
