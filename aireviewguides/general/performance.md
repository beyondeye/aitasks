---
name: Performance
description: Find unnecessary allocations, N+1 patterns, and missing caching
reviewtype: performance
reviewlabels: [memory, caching, database, algorithmic-complexity]
---

## Review Instructions

### Memory and Allocations
- Flag unnecessary object creation inside loops (e.g., compiling a regex, creating a formatter, or instantiating a client on every iteration)
- Look for string concatenation in loops — use a string builder, list join, or buffer instead
- Check for large collections loaded entirely into memory when streaming/pagination would work (e.g., `SELECT *` without LIMIT, reading an entire file when only the first few lines are needed)
- Flag unnecessary copying of large data structures (deep copies where shallow copies or references suffice)
- Look for temporary collections created just to iterate once — consider using generators or lazy evaluation

### Database and I/O
- Flag N+1 query patterns: a query inside a loop where each iteration makes a separate database call (should be a single batch query or JOIN)
- Check for missing database indices on columns used in WHERE, JOIN, or ORDER BY clauses of frequent queries
- Look for blocking I/O on the main thread or event loop (synchronous file reads, HTTP calls, or database queries in async contexts)
- Flag missing connection pooling for database or HTTP clients (creating a new connection per request)
- Check for unnecessary round-trips: multiple sequential queries that could be combined into one

### Caching
- Look for repeated expensive computations with the same inputs — these are candidates for memoization or caching
- Flag expensive operations (API calls, file parsing, database queries) in hot paths that return the same result within a short window
- Check that cached values have appropriate expiration/invalidation strategies
- Look for cache stampede risks: when cache expires, many concurrent requests all compute the value simultaneously

### Algorithmic Complexity
- Flag O(n^2) or worse patterns: nested loops over the same collection, repeated linear searches in a list
- Look for linear searches on sorted data — use binary search instead
- Check for unnecessary sorting (sorting a collection just to find the min/max — use a single pass instead)
- Flag repeated traversals of the same data structure that could be combined into a single pass
- Look for hash map or set opportunities: using list containment checks (`x in list`) where a set would be O(1) instead of O(n)
