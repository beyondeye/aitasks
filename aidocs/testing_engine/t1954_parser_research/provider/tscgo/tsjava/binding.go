//go:build t1954cgo && cgo

// Package tsjava compiles the pinned java grammar (tsref/LOCK; fetched by
// tsref/fetch.sh into .tsref/) as its own translation unit — the official
// bindings/go pattern: parser.c's statics would clash in a shared one.
package tsjava

// #cgo CFLAGS: -std=c11 -fPIC -w -I${SRCDIR}/../../../.tsref/tree-sitter-java/src
// #include "../../../.tsref/tree-sitter-java/src/parser.c"
// static const void *t1954_language(void) { return tree_sitter_java(); }
import "C"

import "unsafe"

// Language is the grammar's TSLanguage pointer.
func Language() unsafe.Pointer { return unsafe.Pointer(C.t1954_language()) }
