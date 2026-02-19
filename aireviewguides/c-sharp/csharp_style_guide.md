---
name: C# Style Guide
description: Check C# code for Google style guide compliance including naming conventions, formatting, and language feature usage
reviewtype: style
reviewlabels: [naming, formatting, idioms, organization]
environment: [c-sharp]
source_url: https://github.com/gemini-cli-extensions/conductor/tree/main/templates/code_styleguides
---

## Review Instructions

### Naming Conventions
- Check that class names, method names, constants, properties, namespaces, and public fields use PascalCase
- Check that private, internal, and protected fields use `_camelCase` (leading underscore)
- Check that local variables and parameters use camelCase
- Verify that interface names are prefixed with `I` (e.g., `IMyInterface`)
- Check that type parameters use descriptive names prefixed with `T` (e.g., `TValue`, `TKey`)

### Formatting
- Check that indentation uses 2 spaces (no tabs)
- Verify K&R brace style: no line break before opening brace, `} else` on one line
- Check that braces are used even when optional (single-line blocks)
- Check that line length does not exceed 100 characters
- Verify one statement per line

### Declaration Order
- Check that class members are grouped in order: nested types/enums/delegates/events, static/const/readonly fields, fields/properties, constructors/finalizers, methods
- Verify that within each group, members are ordered by accessibility: public, internal, protected internal, protected, private
- Look for interface implementations grouped together

### Language Features
- Check that `var` is used when the type is obvious from the right side of the assignment
- Flag expression-bodied syntax on method definitions (should use block bodies)
- Look for string concatenation with `+` in performance-sensitive code (suggest `StringBuilder`)
- Verify that null-conditional operators (`?.`, `??`) are used to simplify null checks
- Check that pattern matching is used for type checks and casts

### Best Practices
- Verify that access modifiers are always explicitly declared
- Check that modifier ordering follows the standard: `public protected internal private new abstract virtual override sealed static readonly extern unsafe volatile async`
- Check that `using` directives are at the top of the file, `System` first, then alphabetical
- Verify that `const` is used where possible; `readonly` for values that cannot be `const`
- Flag magic numbers without named constants
- Flag use of `struct` for types that are not small, value-like, and short-lived
- Check that `IEnumerable`/`IReadOnlyList` is preferred for immutable inputs; `IList` for mutable output ownership

### File Organization
- Verify one class/interface/enum/struct per file
- Check that file names match the primary type name
- Flag namespaces deeper than 2 levels
- Verify that `out` parameters are placed after all other parameters

### Parameter Clarity
- Flag boolean parameters without clear intent at the call site
- Look for method calls with multiple arguments of unclear meaning (suggest named constants, enums, or named arguments)
