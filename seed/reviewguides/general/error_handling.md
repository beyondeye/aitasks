---
name: Error Handling
description: Check for missing error handling, poor messages, and resource leaks
reviewtype: bugs
reviewlabels: [errors, exceptions, edge-cases, resource-cleanup]
---

## Review Instructions

### Missing Error Checks
- Flag unchecked return values from functions that can fail (file operations, network calls, parsing)
- Look for unhandled promise rejections or missing `.catch()` on async operations
- Check for missing null/nil/None checks before dereferencing (especially for values from external sources: API responses, database queries, user input)
- Flag ignored error returns from I/O operations (write, close, flush)
- Look for missing error handling on type conversions/parsing (string to int, JSON parsing, date parsing)

### Error Message Quality
- Flag generic error messages like "something went wrong", "error occurred", or "invalid input" — messages should describe what failed and why
- Check that error messages include context: which input was invalid, what value was received vs expected, which operation failed
- Flag stack traces or internal details exposed to end users — these should be logged server-side but not shown to users
- Look for error messages that leak implementation details (database table names, internal paths, query structures)
- Check that error messages suggest a corrective action when possible (e.g., "File not found: config.yaml. Run 'init' to create it.")

### Exception/Error Handling Patterns
- Flag overly broad catch blocks: `except Exception`, `catch (Exception e)`, `catch {}` — catch specific exceptions
- Flag empty catch blocks that silently swallow errors — at minimum, log the error
- Look for catch-and-ignore patterns where the caller has no way to know an error occurred
- Flag exceptions used for normal control flow (e.g., catching an exception to check if a key exists instead of using `in` or `.get()`)
- Check that caught exceptions are either handled, re-raised, or wrapped with context — not just logged and forgotten

### Edge Cases
- Check for missing handling of empty collections (empty lists, empty strings, empty maps)
- Look for off-by-one errors in boundary conditions (loop bounds, string slicing, array indexing)
- Flag missing handling of concurrent access (race conditions when multiple threads/goroutines access shared state)
- Check for missing timeout handling on network calls, database queries, and external API requests
- Look for missing handling of partial failures in batch operations (what happens if item 50 of 100 fails?)

### Resource Cleanup
- Flag missing finally/defer/cleanup blocks for acquired resources (file handles, database connections, locks, temporary files)
- Look for resource leaks: opened files, connections, or streams that are not closed on all code paths (including error paths)
- Check that partial failure states are rolled back (e.g., if step 2 of 3 fails, step 1's changes should be reverted)
- Flag missing cleanup in test code (temporary files, test databases, mock servers)
- Look for lock acquisition without guaranteed release (missing try/finally around lock.acquire/lock.release)
