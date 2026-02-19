---
name: C++ Style Guide
description: Check C++ code for Google style guide compliance including naming, formatting, class design, and modern C++ usage
reviewtype: style
reviewlabels: [naming, formatting, idioms, organization, memory, error-handling]
environment: [cpp]
source_url: https://github.com/gemini-cli-extensions/conductor/tree/main/templates/code_styleguides
---

## Review Instructions

### Naming
- Check that type names (classes, structs, enums, concepts) use PascalCase
- Check that variables and data members use snake_case
- Check that class data members end with an underscore (`my_member_`)
- Check that struct data members do NOT end with an underscore
- Check that constants and enumerators use `k` + PascalCase (`kDays`, `kOk`)
- Check that functions use PascalCase (`GetValue()`)
- Check that accessors/mutators use snake_case: `count()`, `set_count()`
- Check that namespace names are lowercase with underscores
- Check that macros use ALL_CAPS
- Check that file names are lowercase with underscores or dashes

### Header Files
- Check that every `.cc` file has a corresponding `.h` file
- Verify that headers are self-contained (can be included on their own)
- Check that header guards follow `#define <PROJECT>_<PATH>_<FILE>_H_`
- Flag forward declarations of `std::` symbols
- Flag inline functions longer than 10 lines in headers
- Check that include order follows: related header, C system, C++ standard, other libraries, project headers (separated by blank lines, alphabetical within groups)

### Formatting
- Check that indentation uses 2 spaces
- Check that line length does not exceed 80 characters
- Flag function definitions with open brace on the same line (should be on next line)
- Verify that `switch` statements include a `default` case
- Check that `[[fallthrough]]` is used for explicit fall-through in switch cases
- Verify that floating-point literals include a radix point (`1.0f`, not `1f`)
- Check that namespace contents are not indented
- Flag `return` statements with unnecessary parentheses
- Verify that pointer declarations attach `*` to the type (`char* c`, not `char *c`)
- Check that class members are ordered: `public`, `protected`, `private`

### Classes
- Flag single-argument constructors missing `explicit`
- Flag virtual method calls in constructors
- Verify Rule of 5: if one special member is defined, all five are declared
- Flag multiple implementation inheritance
- Check that `override` is used instead of `virtual` for overridden methods
- Verify that data members are `private` (except in structs and constants)
- Check declaration order within access sections: Types, Constants, Factory, Constructors, Destructor, Methods, Data Members

### Functions
- Check that function parameters follow input-first, output-last ordering
- Verify that outputs prefer return values or `std::optional` over output parameters
- Flag functions longer than 40 lines
- Flag default arguments on virtual functions
- Check that nonmember functions in namespaces are preferred over static member functions

### Scoping
- Flag `using namespace` directives
- Check that `using std::string` style is used instead of `using namespace std`
- Verify that variables are declared in the narrowest possible scope
- Flag global/static variables that are not trivially destructible (no global `std::string`, `std::map`, smart pointers)
- Check that anonymous namespaces or `static` are used for internal linkage in `.cc` files

### Modern C++ Features
- Flag use of C++23 features (target C++20)
- Flag use of C++20 Modules
- Flag `std::enable_if` where C++20 Concepts could be used instead
- Flag use of `std::auto_ptr` (use `std::unique_ptr`)
- Check that `nullptr` is used instead of `NULL` or `0`
- Verify that `constexpr`/`consteval` is used for constants and functions where possible
- Flag use of `std::bind` (prefer lambdas)
- Check that C++ casts (`static_cast`, `std::bit_cast`) are used instead of C-style casts
- Flag lambdas with broad captures (`[=]`, `[&]`) that escape their scope

### Best Practices
- Check that methods and variables are marked `const` wherever possible
- Flag use of exceptions (exceptions are forbidden)
- Flag use of `dynamic_cast` or `typeid` outside of unit tests
- Flag macro definitions where `constexpr`, `inline`, or templates could be used
- Flag macros defined in headers without a corresponding `#undef`
- Flag use of `unsigned` types solely for non-negativity enforcement
- Check that `++i` is preferred over `i++`
- Check that `sizeof(varname)` is preferred over `sizeof(type)`
- Verify that `using` aliases are used instead of `typedef`
