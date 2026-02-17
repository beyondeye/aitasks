---
name: Refactoring Opportunities
description: Identify complex functions, tight coupling, and code smells
---

## Review Instructions

### Function Complexity
- Flag functions longer than ~50 lines — these likely do too much and should be broken down
- Look for deeply nested conditionals (3+ levels of if/else or loops) — extract inner blocks into well-named helper functions
- Flag functions with high cyclomatic complexity (many branching paths) — consider refactoring into smaller, focused functions
- Check for functions that do multiple unrelated things (e.g., validate input AND save to database AND send notification) — each responsibility should be a separate function
- Flag long chains of method calls that are hard to follow — intermediate results with descriptive names improve readability

### Class and Module Size
- Flag classes with more than ~10 public methods or ~300 lines — they likely have too many responsibilities (god class)
- Look for classes that could be split along clear responsibility boundaries (e.g., a class that handles both serialization and business logic)
- Flag modules/files with too many unrelated public functions — group related functionality into separate modules
- Check for classes with excessive mutable state (many instance variables) — consider splitting or using immutable data patterns

### Coupling and Dependencies
- Flag tight coupling between modules: direct access to internal data structures instead of going through an interface
- Look for "feature envy" — functions that use more data from another class/module than their own
- Check for concrete class dependencies where an interface/protocol would allow easier testing and future flexibility
- Flag functions that take a large object just to access one field — pass the specific data needed instead
- Look for modules with many imports from unrelated areas — this suggests the module is doing too much or has unclear boundaries

### Code Smells
- Flag functions with long parameter lists (5+) — consider grouping related parameters into a data class or configuration object
- Look for boolean parameters that control branching inside a function — these often indicate the function should be split into two functions
- Flag "primitive obsession" — using raw strings or integers where a typed value would add clarity (e.g., `status: str` vs `status: TaskStatus`)
- Check for repeated type-checking with isinstance/typeof — this often indicates a missing polymorphic design
- Flag functions that return different types depending on conditions — this creates fragile caller code
- Look for "shotgun surgery" patterns — when a single logical change requires touching many files, the abstraction may be wrong
