//go:build t1954cgo && cgo

// Package tsbash compiles the pinned bash grammar (tsref/LOCK; fetched by
// tsref/fetch.sh into .tsref/) as its own translation unit — the official
// bindings/go pattern: parser.c's statics would clash in a shared one.
package tsbash

// #cgo CFLAGS: -std=c11 -fPIC -w -I${SRCDIR}/../../../.tsref/tree-sitter-bash/src
// #include "../../../.tsref/tree-sitter-bash/src/parser.c"
// #include "../../../.tsref/tree-sitter-bash/src/scanner.c"
// static const void *t1954_language(void) { return tree_sitter_bash(); }
import "C"

import "unsafe"

// Language is the grammar's TSLanguage pointer.
func Language() unsafe.Pointer { return unsafe.Pointer(C.t1954_language()) }
