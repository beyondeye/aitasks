package axes

import (
	"errors"
	"fmt"
	"math/rand/v2"
	"reflect"
	"sort"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
	"gopkg.in/yaml.v3"
)

// [undeclared_never_underselects] Invariant 1 for the axis channel: removing
// a declaration or widening the sources never shrinks what an axis hit
// selects. Part A is a property of the in-memory Table (synthetic, not a
// proof of the loader path); part B round-trips each declaration through the
// real parser, so it speaks for accepted inputs. Neither proves the final
// selection on its own: that a path with no axis hit keeps every variant of
// an edge-reached unit is the caller obligation, pinned by
// TestEdgeWithoutAxisHitKeepsAllVariants.

const propertySeeds = 300

var propertyPaths = []string{
	"s/f0/x0/a.xml", "s/f1/x1/b.xml", "s/f2/x2/c", "s/x0.txt", "s/x1.txt", "s/deep/x2/y", "other/z.kt", "s/f0/x1/d",
}

// genDecl builds a valid declaration: 1–2 axes, 2–3 facets, 1–6 values (one
// value exercises the last-value refusal), facet values from x0..x2, and
// sources only on carried facet values.
func genDecl(r *rand.Rand) fileDoc {
	var doc fileDoc
	doc.Contract = 1
	for ai := range 1 + r.IntN(2) {
		d := axisDoc{Name: fmt.Sprintf("a%d", ai), Values: map[string]map[string]string{}, Sources: map[string]map[string][]string{}}
		for fi := range 2 + r.IntN(2) {
			d.Facets = append(d.Facets, fmt.Sprintf("f%d", fi))
		}
		for vi := range 1 + r.IntN(6) {
			decl := map[string]string{}
			for _, f := range d.Facets {
				decl[f] = fmt.Sprintf("x%d", r.IntN(3))
			}
			d.Values[fmt.Sprintf("v%d", vi)] = decl
		}
		globs := func(f, v string) []string {
			pool := []string{"s/" + f + "/" + v + "/**", "s/" + v + ".txt", "s/**/" + v + "/*", "s/*/" + v + "/**"}
			r.Shuffle(len(pool), func(i, j int) { pool[i], pool[j] = pool[j], pool[i] })
			return pool[:1+r.IntN(2)]
		}
		for _, f := range d.Facets {
			for _, v := range []string{"x0", "x1", "x2"} {
				if r.IntN(2) == 0 {
					continue
				}
				carried := false
				for _, decl := range d.Values {
					carried = carried || decl[f] == v
				}
				if carried {
					if d.Sources[f] == nil {
						d.Sources[f] = map[string][]string{}
					}
					d.Sources[f][v] = globs(f, v)
				}
			}
		}
		doc.Axes = append(doc.Axes, d)
	}
	return doc
}

// genRows builds scanned rows: variant rows on each axis (declared values
// plus an undeclared one), a row on an undeclared axis, and plain rows with
// member and file-level claims.
func genRows(r *rand.Rand, doc fileDoc) []registry.ScannedRow {
	var rows []registry.ScannedRow
	for _, d := range doc.Axes {
		for ui := range 2 {
			var vs []string
			for _, v := range sortedKeys(d.Values) {
				if r.IntN(3) > 0 {
					vs = append(vs, v)
				}
			}
			vs = append(vs, "zz")
			rows = append(rows, registry.ScannedRow{Test: fmt.Sprintf("t/%s_%d.kt#M", d.Name, ui), Axis: d.Name, Variants: vs})
		}
	}
	rows = append(rows, registry.ScannedRow{Test: "t/undeclared.kt#M", Axis: "nope", Variants: []string{"v0"}})
	claim := func() string {
		d := doc.Axes[r.IntN(len(doc.Axes))]
		return fmt.Sprintf("%s.%s=x%d", d.Name, d.Facets[r.IntN(len(d.Facets))], r.IntN(3))
	}
	rows = append(rows,
		registry.ScannedRow{Test: "t/plain.kt", Facets: []string{claim()}},
		registry.ScannedRow{Test: "t/members.kt", Facets: []string{claim()}},
		registry.ScannedRow{Test: "t/members.kt#A", Facets: []string{claim()}},
		registry.ScannedRow{Test: "t/members.kt#B"},
	)
	return rows
}

func renderDecl(t *testing.T, doc fileDoc) []byte {
	t.Helper()
	data, err := yaml.Marshal(doc)
	if err != nil {
		t.Fatal(err)
	}
	return data
}

func cloneDoc(doc fileDoc) fileDoc {
	data, _ := yaml.Marshal(doc)
	var out fileDoc
	if err := yaml.Unmarshal(data, &out); err != nil {
		panic(err)
	}
	return out
}

// selected is the id set the axis channel selects for the corpus.
func selected(t *testing.T, tab *Table, rows []registry.ScannedRow) map[string]bool {
	t.Helper()
	placed, err := tab.Select(rows, tab.Join(propertyPaths))
	if err != nil {
		t.Fatal(err)
	}
	out := map[string]bool{}
	for _, p := range placed {
		out[p.ID.String()] = true
	}
	return out
}

func missing(before, after map[string]bool) []string {
	var out []string
	for id := range before {
		if !after[id] {
			out = append(out, id)
		}
	}
	sort.Strings(out)
	return out
}

func hitSet(hits []Hit) map[Hit]bool {
	out := map[Hit]bool{}
	for _, h := range hits {
		out[h] = true
	}
	return out
}

// deepCopy copies a table through its own fields (Widen mutates in place).
func deepCopy(tab *Table) *Table {
	out := &Table{declared: tab.declared}
	for _, a := range tab.Axes {
		c := &Axis{Name: a.Name, Facets: append([]string{}, a.Facets...), Values: map[string]map[string]string{}, Sources: map[string]map[string][]Source{}}
		for v, decl := range a.Values {
			m := map[string]string{}
			for f, x := range decl {
				m[f] = x
			}
			c.Values[v] = m
		}
		for f, cells := range a.Sources {
			c.Sources[f] = map[string][]Source{}
			for v, ss := range cells {
				c.Sources[f][v] = append([]Source{}, ss...)
			}
		}
		out.Axes = append(out.Axes, c)
	}
	return out
}

func TestPropertySynthetic(t *testing.T) {
	for seed := range uint64(propertySeeds) {
		r := rand.New(rand.NewPCG(seed, 1853))
		doc := genDecl(r)
		tab, err := Parse(renderDecl(t, doc))
		if err != nil {
			t.Fatalf("seed %d: generated declaration refused: %v", seed, err)
		}
		rows := genRows(r, doc)
		base := selected(t, tab, rows)

		// (a) deleting any one value declaration never shrinks the selection.
		for ai, a := range tab.Axes {
			for _, v := range a.ValueNames() {
				cut := deepCopy(tab)
				delete(cut.Axes[ai].Values, v)
				if lost := missing(base, selected(t, cut, rows)); len(lost) > 0 {
					t.Fatalf("seed %d: deleting %s@%s lost %v", seed, a.Name, v, lost)
				}
			}
		}

		// (b) widening never shrinks the hits or the selection.
		wide := deepCopy(tab)
		var obs []ObservedSource
		for range 1 + r.IntN(4) {
			a := doc.Axes[r.IntN(len(doc.Axes))]
			obs = append(obs, ObservedSource{Axis: a.Name, Facet: a.Facets[r.IntN(len(a.Facets))], Value: fmt.Sprintf("x%d", r.IntN(3)), Glob: propertyPaths[r.IntN(len(propertyPaths))]})
		}
		wide.Widen(obs)
		bh, wh := hitSet(tab.Join(propertyPaths)), hitSet(wide.Join(propertyPaths))
		for h := range bh {
			if !wh[h] {
				t.Fatalf("seed %d: widening lost hit %+v", seed, h)
			}
		}
		if lost := missing(base, selected(t, wide, rows)); len(lost) > 0 {
			t.Fatalf("seed %d: widening lost %v", seed, lost)
		}

		// (c) a rejected observed source changes nothing.
		same := deepCopy(tab)
		bad := []ObservedSource{
			{Axis: "nope", Facet: "f0", Value: "x0", Glob: "s/**"},
			{Axis: doc.Axes[0].Name, Facet: "nope", Value: "x0", Glob: "s/**"},
			{Axis: doc.Axes[0].Name, Facet: "f0", Value: "never", Glob: "s/**"},
			{Axis: doc.Axes[0].Name, Facet: "f0", Value: "x0", Glob: "["},
		}
		if rej := same.Widen(bad); len(rej) != len(bad) || !reflect.DeepEqual(same, deepCopy(tab)) {
			t.Fatalf("seed %d: a rejected source changed the table (rejected %v)", seed, rej)
		}
	}
}

func TestPropertyLoaderRoundTrip(t *testing.T) {
	refusals := map[string]int{}
	for seed := range uint64(propertySeeds) {
		r := rand.New(rand.NewPCG(seed, 1853))
		doc := genDecl(r)
		tab, err := Parse(renderDecl(t, doc))
		if err != nil {
			t.Fatalf("seed %d: %v", seed, err)
		}
		rows := genRows(r, doc)
		base := selected(t, tab, rows)
		for ai, d := range doc.Axes {
			for _, v := range sortedKeys(d.Values) {
				cut := cloneDoc(doc)
				delete(cut.Axes[ai].Values, v)
				orphan := ""
				for _, f := range sortedKeys(cut.Axes[ai].Sources) {
					for _, x := range sortedKeys(cut.Axes[ai].Sources[f]) {
						carried := false
						for _, decl := range cut.Axes[ai].Values {
							carried = carried || decl[f] == x
						}
						if !carried && orphan == "" {
							orphan = f + "=" + x
						}
					}
				}
				after, err := Parse(renderDecl(t, cut))
				var wantReason string
				switch {
				case len(cut.Axes[ai].Values) == 0:
					wantReason = "values is required"
				case orphan != "":
					wantReason = "no value carries " + orphan
				}
				if wantReason != "" {
					var inv *registry.InvalidError
					if !errors.As(err, &inv) || !strings.Contains(err.Error(), wantReason) {
						t.Fatalf("seed %d: deleting %s@%s: %v (want refusal %q)", seed, d.Name, v, err, wantReason)
					}
					refusals[strings.Fields(wantReason)[0]]++
					continue
				}
				if err != nil {
					t.Fatalf("seed %d: deleting %s@%s refused unexpectedly: %v", seed, d.Name, v, err)
				}
				if lost := missing(base, selected(t, after, rows)); len(lost) > 0 {
					t.Fatalf("seed %d: deleting %s@%s lost %v", seed, d.Name, v, lost)
				}
			}
		}
	}
	// Both refusal reasons must actually occur, or the property only ever
	// exercised the loadable branch.
	if refusals["values"] == 0 || refusals["no"] == 0 {
		t.Fatalf("refusal branches not exercised: %v", refusals)
	}
}
