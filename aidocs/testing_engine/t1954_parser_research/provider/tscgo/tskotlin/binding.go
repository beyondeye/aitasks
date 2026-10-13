//go:build t1954cgo && cgo

// Package tskotlin compiles the pinned kotlin grammar (tsref/LOCK; fetched by
// tsref/fetch.sh into .tsref/) as its own translation unit — the official
// bindings/go pattern: parser.c's statics would clash in a shared one.
package tskotlin

// #cgo CFLAGS: -std=c11 -fPIC -w -I${SRCDIR}/../../../.tsref/tree-sitter-kotlin/src
// #include "../../../.tsref/tree-sitter-kotlin/src/parser.c"
// #include "../../../.tsref/tree-sitter-kotlin/src/scanner.c"
// static const void *t1954_language(void) { return tree_sitter_kotlin(); }
import "C"

import "unsafe"

// Language is the grammar's TSLanguage pointer.
func Language() unsafe.Pointer { return unsafe.Pointer(C.t1954_language()) }
