---
name: Code Conventions
description: Check naming, formatting, and pattern consistency
reviewtype: style
reviewlabels: [naming, formatting, organization, comments]
---

## Review Instructions

### Naming Conventions
- Check that class/type names use PascalCase (e.g., `UserProfile`, not `user_profile` or `userProfile`)
- Check that function/method names use the language's convention (snake_case for Python/Rust/Ruby, camelCase for Java/Kotlin/JS/TS)
- Check that constants use UPPER_SNAKE_CASE (e.g., `MAX_RETRIES`, not `maxRetries` or `max_retries`)
- Flag single-letter variable names outside of tight loops or lambdas (e.g., `x = get_user()` should be `user = get_user()`)
- Check that boolean variables/functions use descriptive prefixes: `is_`, `has_`, `can_`, `should_` (e.g., `is_valid` not `valid`)
- Flag names that are misleading or inconsistent with what the code actually does
- Check that acronyms follow project convention (e.g., `HttpClient` vs `HTTPClient` — should be consistent within the project)

### Code Organization
- Check that imports/includes are grouped logically: standard library, third-party, local — with blank lines between groups
- Flag circular imports or dependency cycles between modules
- Check that public API functions/methods come before private/internal ones within a file
- Flag files that mix unrelated responsibilities (e.g., a file containing both HTTP handlers and database queries)
- Check that related functions are grouped together, not scattered across the file

### Formatting Consistency
- Check that indentation style is consistent within each file (no mixed tabs and spaces)
- Check that brace/bracket style is consistent within the project (same-line vs next-line)
- Check that string quoting is consistent within each file (single vs double quotes, unless language requires mixing)
- Flag lines that significantly exceed the project's line length convention (typically 80-120 chars)
- Check that blank lines are used consistently to separate logical sections

### Comment Hygiene
- Flag commented-out code blocks — these should be removed (version control preserves history)
- Flag TODO/FIXME/HACK comments that lack a ticket/issue reference
- Flag comments that restate what the code does without adding insight (e.g., `# increment counter` before `counter += 1`)
- Check that comments describing complex logic are still accurate after code changes (stale comments are worse than no comments)
- Flag comments that describe "why not" without explaining "why" (e.g., `# don't use X` without saying what to use instead)
