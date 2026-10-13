//go:build !unpatched

// Package seam is the only code that touches the snapshot's two research
// hooks (annot.ClassifyHook, annot.LangHook from baseline/seam.patch). The
// unpatched build (-tags unpatched, go.unpatched.mod) compiles the stub in
// seam_unpatched.go instead, which can only run with both hooks nil — that
// is what lets the guard build the same harness against an unpatched snapshot.
package seam

import (
	"sync"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/annot"
)

// Available reports whether this build can install hooks.
const Available = true

var mu sync.Mutex

// With runs fn with the hooks installed (nil = landed behaviour) and always
// clears them afterwards. Runs are serialised: the hooks are package globals.
func With(classify func(annot.Lang, []byte) annot.Context, lang func(string, []byte) (annot.Lang, bool), fn func() error) error {
	mu.Lock()
	defer mu.Unlock()
	annot.ClassifyHook, annot.LangHook = classify, lang
	defer func() { annot.ClassifyHook, annot.LangHook = nil, nil }()
	return fn()
}

// Landed runs the landed (unhooked) classifier from inside a ClassifyHook.
// Safe only because annot.Source reads files sequentially (no concurrent
// Classify while the hook is swapped); used by `bench` to hand a provider's
// unsupported languages to the landed lexer.
func Landed(l annot.Lang, data []byte) annot.Context {
	saved := annot.ClassifyHook
	annot.ClassifyHook = nil
	defer func() { annot.ClassifyHook = saved }()
	return annot.Classify(l, data)
}
