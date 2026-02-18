---
name: Code Duplication
description: Find DRY violations, copy-paste code, and repeated patterns
reviewtype: code-smell
reviewlabels: [dry, extraction, deduplication]
---

## Review Instructions

### Exact and Near Duplicates
- Look for identical or near-identical code blocks across files (same logic with only variable names changed)
- Flag functions that do the same thing but are defined in different modules — these should be consolidated into a shared utility
- Check for copy-paste patterns: blocks that are structurally identical but differ in 1-2 values (these should be parameterized)
- Look for duplicated test setup/teardown code that could be extracted into fixtures or helpers

### Structural Duplication
- Flag repeated switch/case or if/elif chains that map values to actions — these often indicate a table-driven approach would be cleaner
- Look for repeated validation sequences across different handlers/endpoints (e.g., same null-check + type-check + range-check pattern)
- Check for boilerplate wrappers that are repeated around different core logic (e.g., try/catch + logging + metrics wrapping applied manually to each function)
- Flag repeated patterns of "fetch data, transform, save" that could use a shared pipeline abstraction

### Data Duplication
- Flag magic numbers or string literals that appear in multiple places without being defined as named constants
- Check for configuration values (URLs, timeouts, limits) repeated across files instead of sourced from a single config
- Look for identical default values defined in multiple places — these should reference a single source of truth
- Flag duplicated error message strings that could be centralized

### Extraction Opportunities
- Identify code blocks (5+ lines) that appear with minor variations in multiple locations and could be extracted into helper functions
- Flag repeated conditional guards at function entry points that could be extracted into a decorator, middleware, or shared validation function
- Look for duplicated error handling wrappers (try/catch with same recovery logic) that could be a shared utility
- Check for repeated sequence of API calls or data transformations that represent a reusable workflow
