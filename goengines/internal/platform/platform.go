// Package platform holds the host-facing pieces every Go executable of the
// framework shares: the release-asset platform suffix, the worker-pool cap,
// the exclusive file lock and the per-user cache root.
package platform

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"runtime"

	"golang.org/x/sync/errgroup"
)

// PoolCap is the engine-wide ceiling on concurrent workers, whatever the host
// offers or a caller requests.
const PoolCap = 8

// OS returns the GOOS the binary was built for (linux, darwin).
func OS() string { return runtime.GOOS }

// Arch returns the GOARCH the binary was built for (amd64, arm64).
func Arch() string { return runtime.GOARCH }

// AssetSuffix returns `<os>_<arch>`, the suffix of the release asset
// `ait-testmap_<V>_<os>_<arch>`.
func AssetSuffix() string { return OS() + "_" + Arch() }

// Workers returns the pool size for a request: requested <= 0 means "one per
// CPU"; the result is always in [1, PoolCap].
func Workers(requested int) int {
	n := requested
	if n <= 0 {
		n = runtime.NumCPU()
	}
	return max(1, min(n, PoolCap))
}

// NewGroup returns an errgroup limited to Workers(n) concurrent goroutines.
func NewGroup(ctx context.Context, n int) (*errgroup.Group, context.Context) {
	g, ctx := errgroup.WithContext(ctx)
	g.SetLimit(Workers(n))
	return g, ctx
}

// ErrNoCacheRoot is returned when neither XDG_CACHE_HOME nor HOME is an
// absolute path: the cache is never placed relative to the working directory.
var ErrNoCacheRoot = errors.New("platform: no cache root: neither XDG_CACHE_HOME nor HOME is an absolute path")

// CacheRoot returns `${XDG_CACHE_HOME:-$HOME/.cache}/aitasks`, the per-user
// framework cache, on every OS. It deliberately does not use
// os.UserCacheDir, which is ~/Library/Caches on darwin and ignores
// XDG_CACHE_HOME there; the cache location is part of the framework's
// contract, not a platform default.
func CacheRoot() (string, error) {
	return cacheRoot(os.Getenv)
}

func cacheRoot(getenv func(string) string) (string, error) {
	// The XDG base-directory spec says a relative value is invalid and must
	// be ignored.
	if x := getenv("XDG_CACHE_HOME"); x != "" && filepath.IsAbs(x) {
		return filepath.Join(x, "aitasks"), nil // invariant5-ok: the per-user cache namespace, not the task dir
	}
	if h := getenv("HOME"); h != "" && filepath.IsAbs(h) {
		return filepath.Join(h, ".cache", "aitasks"), nil // invariant5-ok: the per-user cache namespace, not the task dir
	}
	return "", ErrNoCacheRoot
}
