---
name: JavaScript Style Guide
description: Check JavaScript code for Google style guide compliance including module structure, naming, and language feature usage
reviewtype: style
reviewlabels: [naming, formatting, idioms, organization]
environment: [javascript]
source_url: https://github.com/gemini-cli-extensions/conductor/tree/main/templates/code_styleguides
---

## Review Instructions

### Module Structure
- Check that new files use ES modules (`import`/`export`)
- Verify that named exports are used (`export {MyClass}`)
- Flag default exports
- Check that `.js` extension is included in import paths
- Flag line-wrapped import statements

### Formatting
- Check that braces are used for all control structures, even single-line blocks
- Verify that indentation uses 2 spaces
- Check that every statement ends with a semicolon
- Verify that line length does not exceed 80 characters
- Check that continuation lines are indented at least 4 spaces

### Variable Declarations
- Flag use of `var` (use `const` or `let`)
- Check that `const` is used by default; `let` only when reassignment is needed
- Verify that trailing commas are used in array and object literals
- Flag use of `Array` or `Object` constructors

### Language Features
- Flag JavaScript getter/setter properties (`get name()`) in classes (use ordinary methods)
- Check that arrow functions are used for nested and anonymous functions
- Verify that single quotes are used for string literals
- Check that template literals are used for interpolation and multi-line strings
- Verify that `for-of` loops are preferred; `for-in` only on dict-style objects
- Check that `===` and `!==` are used (never `==` or `!=`)

### Disallowed Features
- Flag use of `with` keyword
- Flag use of `eval()` or `Function(...string)`
- Flag modifications to builtin prototypes (e.g., `Array.prototype.foo`)
- Flag reliance on Automatic Semicolon Insertion

### Naming
- Check that class names use `UpperCamelCase`
- Check that methods, functions, variables, and properties use `lowerCamelCase`
- Check that global constants use `CONSTANT_CASE`

### Documentation
- Verify that JSDoc is used on all classes, fields, and methods
- Check that `@param`, `@return`, `@override`, `@deprecated` tags are used appropriately
