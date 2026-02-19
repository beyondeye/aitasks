---
name: Go Style Guide
description: Check Go code for idiomatic patterns including naming, formatting, error handling, and concurrency practices
reviewtype: style
reviewlabels: [naming, formatting, idioms, error-handling]
environment: [go]
source_url: https://github.com/gemini-cli-extensions/conductor/tree/main/templates/code_styleguides
---

## Review Instructions

### Formatting
- Verify that code is formatted with `gofmt`
- Check that tabs are used for indentation (not spaces)

### Naming
- Check that multi-word names use `MixedCaps` or `mixedCaps` (no underscores)
- Verify that exported names start with an uppercase letter
- Check that package names are short, lowercase, single-word
- Flag getter methods with a `Get` prefix (should be `Owner()`, not `GetOwner()`)
- Check that single-method interfaces use the `-er` suffix (`Reader`, `Writer`, `Stringer`)

### Control Structures
- Check that `if` statements do not use parentheses around conditions
- Verify that `for...range` is used to iterate over slices, maps, strings, and channels
- Flag explicit `fallthrough` usage in `switch` statements (ensure it is intentional)

### Functions
- Verify that functions returning errors follow the `value, err` pattern
- Check that `defer` is used for cleanup tasks (closing files, unlocking mutexes)
- Look for named return parameters and verify they improve clarity

### Data Structures
- Verify correct use of `new` vs `make`: `new` for zero-value pointers, `make` for slices, maps, and channels
- Check that slices are preferred over arrays
- Verify that the "comma ok" idiom is used for map lookups (`value, ok := myMap[key]`)

### Interfaces
- Verify that interfaces are implicitly satisfied (no explicit `implements`)
- Check that interfaces are small and focused (prefer single-method interfaces)

### Concurrency
- Look for shared memory access without channels (prefer communicating over sharing)
- Verify that goroutines and channels are used idiomatically

### Error Handling
- Flag discarded errors using the blank identifier (`_`)
- Verify that errors are checked explicitly after every function call that returns one
- Flag use of `panic` outside of truly unrecoverable situations
