---
name: TypeScript Style Guide
description: Check TypeScript code for Google style guide compliance including type system usage, naming, and disallowed features
reviewtype: style
reviewlabels: [naming, formatting, idioms, type-hints]
environment: [typescript]
source_url: https://github.com/gemini-cli-extensions/conductor/tree/main/templates/code_styleguides
---

## Review Instructions

### Variable Declarations and Modules
- Flag use of `var` (use `const` or `let`)
- Check that `const` is used by default
- Verify that ES6 modules are used (`import`/`export`)
- Flag use of `namespace`
- Verify that named exports are used
- Flag default exports

### Classes
- Flag use of `#private` fields (use TypeScript's `private` modifier)
- Check that properties not reassigned outside the constructor are marked `readonly`
- Flag use of `public` modifier (it is the default and should be omitted)
- Verify that `private` or `protected` is used to restrict visibility where possible

### Language Features
- Check that single quotes are used for string literals
- Verify that template literals are used for interpolation
- Check that `===` and `!==` are used (never `==` or `!=`)
- Flag type assertions (`x as SomeType`) and non-null assertions (`y!`) without clear justification
- Verify that function declarations are used for named functions, arrow functions for callbacks

### Disallowed Features
- Flag use of `any` type (prefer `unknown` or a more specific type)
- Flag `String`, `Boolean`, or `Number` wrapper class instantiation
- Flag reliance on Automatic Semicolon Insertion
- Flag use of `const enum` (use plain `enum`)
- Flag use of `eval()` or `Function(...string)`

### Naming
- Check that classes, interfaces, types, enums, and decorators use `UpperCamelCase`
- Check that variables, parameters, functions, methods, and properties use `lowerCamelCase`
- Check that global constants and enum values use `CONSTANT_CASE`
- Flag `_` prefix or suffix on identifiers (including private properties)

### Type System
- Verify that type inference is used for simple, obvious types
- Check that optional parameters/fields (`?`) are preferred over `|undefined`
- Verify that `T[]` is used for simple types and `Array<T>` for complex union types
- Flag use of `{}` type (prefer `unknown`, `Record<string, unknown>`, or `object`)
- Check that every statement ends with a semicolon

### Documentation
- Verify that `/** JSDoc */` is used for documentation comments
- Flag `@param` or `@return` tags with redundant type annotations in JSDoc
- Check that comments add information rather than restating the code
