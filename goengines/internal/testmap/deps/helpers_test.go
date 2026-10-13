package deps

import (
	"context"
	"slices"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

var bg = context.Background()

// repo writes files into a fresh fixture repository (untracked files are in
// the universe, as git-visible files).
func repo(t *testing.T, files map[string]string) *fixture.Repo {
	t.Helper()
	r := fixture.New(t)
	for p, c := range files {
		r.Write(t, p, c)
	}
	return r
}

// scanRepo scans r uncached with the default config (plus cfg mutations).
func scanRepo(t *testing.T, r *fixture.Repo, mut ...func(*Options)) *Graph {
	t.Helper()
	o := Options{Config: registry.Defaults(), Uncached: true}
	for _, m := range mut {
		m(&o)
	}
	g, err := Scan(bg, r.Dir, o)
	if err != nil {
		t.Fatal(err)
	}
	return g
}

// edge is a compact form of a Dep for assertions: "target origin via".
func edges(g *Graph, p string) []string {
	f, ok := g.Facts(p)
	if !ok {
		return nil
	}
	var out []string
	for _, d := range f.Deps {
		out = append(out, d.Target+" "+string(d.Origin)+" "+d.Via)
	}
	return out
}

// requireEdge asserts p has a dep on target with origin ("" = closure-only)
// and, when via is non-empty, that via.
func requireEdge(t *testing.T, g *Graph, p, target string, origin Origin, via string) {
	t.Helper()
	f, _ := g.Facts(p)
	for _, d := range f.Deps {
		if d.Target == target && d.Origin == origin && (via == "" || d.Via == via) {
			return
		}
	}
	t.Errorf("%s: no edge to %s origin=%q via=%q; have %q", p, target, origin, via, edges(g, p))
}

// requireNoEdge asserts p has no dep on target at all.
func requireNoEdge(t *testing.T, g *Graph, p, target string) {
	t.Helper()
	f, _ := g.Facts(p)
	for _, d := range f.Deps {
		if d.Target == target {
			t.Errorf("%s: unexpected edge %+v", p, d)
		}
	}
}

func reached(g *Graph, from, to string) bool {
	return slices.ContainsFunc(g.Closure(from, 0), func(r Reach) bool { return r.Path == to })
}

func lines(s ...string) string { return strings.Join(s, "\n") + "\n" }
