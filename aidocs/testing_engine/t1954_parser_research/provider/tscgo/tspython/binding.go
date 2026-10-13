//go:build t1954cgo && cgo

// Package tspython compiles the pinned python grammar (tsref/LOCK; fetched by
// tsref/fetch.sh into .tsref/) as its own translation unit — the official
// bindings/go pattern: parser.c's statics would clash in a shared one.
package tspython

// #cgo CFLAGS: -std=c11 -fPIC -w -I${SRCDIR}/../../../.tsref/tree-sitter-python/src
// #include "../../../.tsref/tree-sitter-python/src/parser.c"
// #include "../../../.tsref/tree-sitter-python/src/scanner.c"
// static const void *t1954_language(void) { return tree_sitter_python(); }
import "C"

import "unsafe"

// Language is the grammar's TSLanguage pointer.
func Language() unsafe.Pointer { return unsafe.Pointer(C.t1954_language()) }
