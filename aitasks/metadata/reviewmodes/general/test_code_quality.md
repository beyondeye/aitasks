---
name: Code Quality
description: Check code quality patterns including naming, complexity, and performance anti-patterns
reviewtype: code-smell
reviewlabels: [naming, complexity, coupling, memory, dry]
similar_to: general/code_conventions.md
---

## Review Instructions

### Naming Conventions
- Check that class/type names use PascalCase
- Check that function/method names follow the language's convention (snake_case for Python, camelCase for JS/TS)
- Flag single-letter variable names outside of tight loops or lambdas
- Check that boolean variables use descriptive prefixes: is_, has_, can_, should_

### Code Complexity
- Flag functions longer than 40 lines — they likely need to be split into smaller units
- Look for deeply nested conditionals (3+ levels of if/else) — consider early returns or guard clauses
- Flag functions with more than 4 parameters — consider using a config object or builder pattern
- Check for god classes or modules that handle too many responsibilities
- Flag methods with high cyclomatic complexity that are hard to test

### Code Duplication
- Look for repeated code blocks across multiple files — extract into shared utilities
- Flag copy-paste patterns where similar logic differs by only one or two lines
- Check for repeated string literals or magic numbers — extract into named constants

### Coupling and Dependencies
- Flag tight coupling between modules (direct access to another module's internal state)
- Check for circular dependencies between packages or modules
- Look for classes that depend on concrete implementations rather than interfaces/abstractions
- Flag God objects that are passed through many layers as a way to share state

### Performance Anti-patterns
- Flag unnecessary object creation inside loops
- Look for string concatenation in loops — use a string builder or join instead
- Check for large collections loaded entirely into memory when streaming would work
- Flag O(n^2) patterns: nested loops, repeated linear searches in a list
