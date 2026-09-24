package platform

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"runtime"
	"sync/atomic"
	"syscall"
	"testing"
	"time"
)

func TestAssetSuffix(t *testing.T) {
	want := runtime.GOOS + "_" + runtime.GOARCH
	if got := AssetSuffix(); got != want {
		t.Fatalf("got %q want %q", got, want)
	}
}

func TestWorkers(t *testing.T) {
	cpus := max(1, min(runtime.NumCPU(), PoolCap))
	for _, tc := range []struct{ in, want int }{
		{-3, cpus}, {0, cpus}, {1, 1}, {5, 5}, {8, 8}, {9, 8}, {1000, 8},
	} {
		if got := Workers(tc.in); got != tc.want {
			t.Errorf("Workers(%d) = %d, want %d", tc.in, got, tc.want)
		}
	}
}

func TestNewGroupNeverExceedsCap(t *testing.T) {
	g, _ := NewGroup(context.Background(), 1000)
	var cur, high atomic.Int32
	for range 50 {
		g.Go(func() error {
			n := cur.Add(1)
			for {
				h := high.Load()
				if n <= h || high.CompareAndSwap(h, n) {
					break
				}
			}
			time.Sleep(2 * time.Millisecond)
			cur.Add(-1)
			return nil
		})
	}
	if err := g.Wait(); err != nil {
		t.Fatal(err)
	}
	if h := high.Load(); h > PoolCap || h < 1 {
		t.Fatalf("high-water %d, want 1..%d", h, PoolCap)
	}
}

func TestLockExcludes(t *testing.T) {
	path := filepath.Join(t.TempDir(), ".lock")
	unlock, err := Lock(path)
	if err != nil {
		t.Fatal(err)
	}
	f, err := os.OpenFile(path, os.O_RDWR, 0)
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	err = syscall.Flock(int(f.Fd()), syscall.LOCK_EX|syscall.LOCK_NB)
	if !errors.Is(err, syscall.EWOULDBLOCK) {
		t.Fatalf("second locker while held: got %v, want EWOULDBLOCK", err)
	}
	if err := unlock(); err != nil {
		t.Fatal(err)
	}
	if err := syscall.Flock(int(f.Fd()), syscall.LOCK_EX|syscall.LOCK_NB); err != nil {
		t.Fatalf("second locker after unlock: %v", err)
	}
}

// cacheRoot has no OS branch: the same expression holds on linux and on
// darwin (where os.UserCacheDir would say ~/Library/Caches). Each case is
// run under both labels to keep it that way.
func TestCacheRoot(t *testing.T) {
	cases := []struct {
		name    string
		env     map[string]string
		want    string
		wantErr bool
	}{
		{"xdg absolute wins", map[string]string{"XDG_CACHE_HOME": "/x/cache", "HOME": "/h"}, "/x/cache/aitasks", false},
		{"xdg relative ignored", map[string]string{"XDG_CACHE_HOME": "rel/cache", "HOME": "/h"}, "/h/.cache/aitasks", false},
		{"xdg empty falls back to HOME", map[string]string{"XDG_CACHE_HOME": "", "HOME": "/h"}, "/h/.cache/aitasks", false},
		{"HOME only", map[string]string{"HOME": "/h"}, "/h/.cache/aitasks", false},
		{"neither", map[string]string{"XDG_CACHE_HOME": "rel"}, "", true},
		{"relative HOME", map[string]string{"HOME": "relative-home"}, "", true},
		{"relative XDG and relative HOME", map[string]string{"XDG_CACHE_HOME": "rel", "HOME": "relative-home"}, "", true},
	}
	for _, label := range []string{"linux", "darwin"} {
		for _, tc := range cases {
			t.Run(label+"/"+tc.name, func(t *testing.T) {
				got, err := cacheRoot(func(k string) string { return tc.env[k] })
				if tc.wantErr {
					if !errors.Is(err, ErrNoCacheRoot) {
						t.Fatalf("got %q, %v; want ErrNoCacheRoot", got, err)
					}
					return
				}
				if err != nil || got != tc.want {
					t.Fatalf("got %q, %v; want %q", got, err, tc.want)
				}
			})
		}
	}
}

func TestCacheRootReadsEnvironment(t *testing.T) {
	t.Setenv("XDG_CACHE_HOME", "/env/xdg")
	got, err := CacheRoot()
	if err != nil || got != "/env/xdg/aitasks" {
		t.Fatalf("got %q, %v", got, err)
	}
}
