package main

import (
	"context"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

// countModuleInference wraps the registered live module inference (the
// modules package's, linked into this binary) with a call counter for the
// test's duration.
func countModuleInference(t *testing.T) *int {
	t.Helper()
	n := new(int)
	var prev registry.ModuleInference
	prev = registry.RegisterModuleInference(func(ctx context.Context, root string, reg *registry.Registry) (*registry.LiveModules, error) {
		*n++
		return prev(ctx, root, reg)
	})
	if prev == nil {
		t.Fatal("no module inference registered: the modules package is not linked")
	}
	t.Cleanup(func() { registry.RegisterModuleInference(prev) })
	return n
}
