---
name: Dart Style Guide
description: Check Dart code for Effective Dart compliance including naming, documentation, null safety, and API design
reviewtype: style
reviewlabels: [naming, formatting, idioms, comments, error-handling]
environment: [dart]
source_url: https://github.com/gemini-cli-extensions/conductor/tree/main/templates/code_styleguides
---

## Review Instructions

### Naming
- Check that types, extensions, and enum types use `UpperCamelCase`
- Check that packages, directories, and source files use `lowercase_with_underscores`
- Check that import prefixes use `lowercase_with_underscores`
- Check that class members, variables, and parameters use `lowerCamelCase`
- Verify that constants use `lowerCamelCase` (not `SCREAMING_CAPS`)
- Check that acronyms longer than two letters are capitalized like words (`Http`, `Uri`)
- Flag leading underscores on non-private identifiers
- Flag prefix letters (e.g., `kDefaultTimeout`)

### Formatting and Imports
- Verify that code is formatted with `dart format`
- Check that `dart:` imports come before other imports
- Check that `package:` imports come before relative imports
- Verify that exports are in a separate section after imports
- Check that import sections are sorted alphabetically
- Verify that curly braces are used for all flow control statements

### Documentation
- Check that `///` doc comments are used (not `/* */`) for members and types
- Verify that public APIs have doc comments
- Check that doc comments start with a single-sentence summary in its own paragraph
- Flag redundant doc comments that repeat the surrounding context
- Verify that square brackets (`[]`) are used to reference in-scope identifiers in doc comments
- Check that doc comments come before metadata annotations

### Null Safety
- Flag explicit initialization of variables to `null`
- Flag explicit default values of `null` for parameters
- Flag boolean comparisons like `if (nonNullableBool == true)`
- Flag `late` variables where a nullable type with an explicit check would be clearer

### Collections and Strings
- Check that collection literals are used (`[]`, `{}`) instead of constructors
- Flag use of `.length` to check emptiness (use `.isEmpty`/`.isNotEmpty`)
- Flag `Iterable.forEach()` with function literals (prefer `for-in`)
- Flag `List.from()` when `.toList()` would suffice
- Check that `whereType()` is used to filter collections by type
- Verify that string interpolation uses `$variable` without unnecessary braces

### Functions and Variables
- Flag lambdas where a tear-off would suffice (e.g., `list.forEach(print)`)
- Check that a consistent rule is followed for `var` vs `final` on local variables
- Flag stored computed values that could be calculated

### Classes and Constructors
- Flag unnecessary getter/setter wrappers around fields
- Check that read-only properties use `final` fields
- Verify that initializing formals (`this.field`) are used in constructors
- Flag use of `new` keyword
- Flag redundant `const` in constant contexts
- Check that empty constructor bodies use `;` instead of `{}`

### Error Handling
- Flag `catch` clauses without `on` clauses
- Flag caught exceptions that are silently discarded
- Check that `rethrow` is used instead of `throw` to preserve stack traces
- Verify that `Error` types are thrown only for programmatic errors

### Async Patterns
- Verify that `async`/`await` is preferred over raw `Future` usage
- Flag `async` functions where it has no useful effect
- Flag direct use of `Completer` where simpler patterns work

### API Design
- Flag one-member abstract classes where a `typedef` would suffice
- Flag classes containing only static members (prefer top-level functions)
- Check that class modifiers (`final`, `interface`, `sealed`) are used to control subclassing
- Verify that fields and top-level variables are `final` where possible
- Flag returning nullable `Future`, `Stream`, or collection types (prefer empty containers)
- Flag positional boolean parameters (prefer named or enum)
- Check that `==` overrides also override `hashCode`
