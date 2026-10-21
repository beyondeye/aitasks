package axes

import (
	"errors"
	"os"
	"path/filepath"
	"reflect"
	"strconv"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/annot"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

const matrixYAML = `contract: 1
axes:
  - name: matrix
    facets: [locale, direction]
    values:
      en-ltr: {locale: en, direction: ltr}
      ru-ltr: {locale: ru, direction: ltr}
      ar-rtl: {locale: ar, direction: rtl}
    sources:
      locale:
        ru: ["res/values-ru/**", "fonts/cyrillic/*.ttf"]
        ar: ["res/values-ar/**"]
`

func mustParse(t *testing.T, y string) *Table {
	t.Helper()
	tab, err := Parse([]byte(y))
	if err != nil {
		t.Fatal(err)
	}
	return tab
}

func TestParseGolden(t *testing.T) {
	tab := mustParse(t, matrixYAML)
	if !tab.Declared() || len(tab.Axes) != 1 {
		t.Fatalf("%+v", tab)
	}
	a, ok := tab.Axis("matrix")
	if !ok || !reflect.DeepEqual(a.Facets, []string{"locale", "direction"}) {
		t.Fatalf("%+v", a)
	}
	if !reflect.DeepEqual(a.ValueNames(), []string{"ar-rtl", "en-ltr", "ru-ltr"}) || a.Values["ru-ltr"]["locale"] != "ru" {
		t.Fatalf("values %v", a.Values)
	}
	want := []Source{{Glob: "res/values-ru/**", Origin: OriginHand}, {Glob: "fonts/cyrillic/*.ttf", Origin: OriginHand}}
	if !reflect.DeepEqual(a.Sources["locale"]["ru"], want) || a.Sources["direction"] != nil {
		t.Fatalf("sources %v", a.Sources)
	}
	if empty := mustParse(t, "contract: 1\n"); !empty.Declared() || len(empty.Axes) != 0 {
		t.Fatal("an axes.yaml with no axes is declared and empty")
	}
	if (&Table{}).Declared() || Of(nil).Declared() {
		t.Fatal("a zero table is undeclared")
	}
}

func TestParseRefusals(t *testing.T) {
	base := "contract: 1\naxes:\n  - name: m\n    facets: [l]\n"
	for in, want := range map[string]string{
		"contract: 1\nbogus: 1\n":                        "field bogus not found",
		base + "    values: {a: {l: x}}\n    extra: 1\n": "field extra not found",
		base + "    values: {a: {l: x}}\n  - name: m\n    facets: [l]\n    values: {b: {l: y}}\n": "declared twice",
		"contract: 1\naxes:\n  - name: m\n    values: {a: {}}\n":                                  "facets is required",
		"contract: 1\naxes:\n  - name: m\n    facets: [l, l]\n    values: {a: {l: x}}\n":          "facet l declared twice",
		base:                                     "values is required",
		base + "    values: {a: {}}\n":           "facet l is missing",
		base + "    values: {a: {l: x, d: y}}\n": "facet d is not declared",
		base + "    values: {a: {l: x}}\n    sources: {d: {x: [g]}}\n":                    "facet d is not declared",
		base + "    values: {a: {l: x}}\n    sources: {l: {xx: [g]}}\n":                   "no value carries l=xx",
		base + "    values: {a: {l: x}}\n    sources: {l: {x: []}}\n":                     "has no glob",
		base + "    values: {a: {l: x}}\n    sources: {l: {x: ['[']}}\n":                  "invalid glob",
		base + "    values: {a: {l: x}}\n    sources: {l: {x: ['']}}\n":                   "invalid glob",
		"contract: 1\naxes:\n  - name: m.x\n    facets: [l]\n    values: {a: {l: x}}\n":   "invalid axis name",
		"contract: 1\naxes:\n  - name: m\n    facets: [a/b]\n    values: {a: {a/b: x}}\n": "invalid facet name",
		base + "    values: {a: {l: 'x y'}}\n":                                            "invalid facet value",
		base + "    values: {a: {l: 'x=y'}}\n":                                            "invalid facet value",
		base + "    values: {'a/b': {l: x}}\n":                                            "invalid variant value",
		base + "    values: {'a@b': {l: x}}\n":                                            "invalid variant value",
		base + "    values: {'': {l: x}}\n":                                               "invalid variant value",
		base + "    values: {a: {l: x}, a: {l: y}}\n":                                     "already defined",
	} {
		_, err := Parse([]byte(in))
		var inv *registry.InvalidError
		if !errors.As(err, &inv) || inv.Path != Path || !strings.Contains(err.Error(), want) {
			t.Errorf("%q: %v (want %q)", in, err, want)
		}
	}
}

// A misspelt source value is refused, not silently accepted as a value only
// claims could reach (the policy question is deferred to M4.1's design).
func TestLoadRefusesOrphanSourceValue(t *testing.T) {
	_, err := Parse([]byte(strings.Replace(matrixYAML, "        ar: [", "        arr: [", 1)))
	if err == nil || !strings.Contains(err.Error(), "no value carries locale=arr") {
		t.Fatalf("%v", err)
	}
}

func writeAxes(t *testing.T, root, content string) {
	t.Helper()
	p := filepath.Join(root, filepath.FromSlash(Path))
	if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(p, []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
}

func TestLoad(t *testing.T) {
	root := t.TempDir()
	if tab, err := Load(root); err != nil || tab.Declared() {
		t.Fatalf("absent: %v %+v", err, tab)
	}
	writeAxes(t, root, "contract: 99\naxes: []\n")
	var cm *testmap.ContractMismatchError
	if _, err := Load(root); !errors.As(err, &cm) {
		t.Fatalf("newer contract: %v", err)
	}
	writeAxes(t, root, "contract: 1\n---\naxes: []\n")
	var inv *registry.InvalidError
	if _, err := Load(root); !errors.As(err, &inv) {
		t.Fatalf("two documents: %v", err)
	}
	// An empty value name is not a variant (an `x@` id is invalid), so the
	// loader refuses it rather than declaring an unlistable variant.
	writeAxes(t, root, "contract: 1\naxes:\n  - name: m\n    facets: [locale]\n    values:\n      '': {locale: ru}\n")
	if _, err := Load(root); !errors.As(err, &inv) || !strings.Contains(err.Error(), `invalid variant value ""`) {
		t.Fatalf("empty value name: %v", err)
	}
	writeAxes(t, root, matrixYAML)
	if tab, err := Load(root); err != nil || len(tab.Axes) != 1 {
		t.Fatalf("%v", err)
	}
}

// The post-loader puts the table into the registry and refuses a malformed
// persisted axis field.
func TestRegistryPostLoad(t *testing.T) {
	root := t.TempDir()
	writeAxes(t, root, matrixYAML)
	reg, err := registry.Load(root)
	if err != nil {
		t.Fatal(err)
	}
	if !Of(reg).Declared() {
		t.Fatal("axes.yaml not loaded into the registry")
	}
	for body, want := range map[string]string{
		"contract: 1\nunits:\n  - test: a.kt\n    axis: matrix\n":                   "axis without variants",
		"contract: 1\nunits:\n  - test: a.kt\n    axis: 'm.x'\n    variants: [v]\n": "invalid axis name",
		"contract: 1\nunits:\n  - test: a.kt\n    facets: [matrix.locale]\n":        "invalid axis claim",
	} {
		p := filepath.Join(root, filepath.FromSlash(registry.ScannedPath))
		if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(p, []byte(body), 0o644); err != nil {
			t.Fatal(err)
		}
		_, err := registry.Load(root)
		var inv *registry.InvalidError
		if !errors.As(err, &inv) || inv.Path != registry.ScannedPath || !strings.Contains(err.Error(), want) {
			t.Errorf("%q: %v (want %q)", body, err, want)
		}
	}
}

// annotClaim is what the real annotation parser makes of a `testmap:axis`
// line carrying s: the single argument it records, or ok=false when it
// refuses the line.
func annotClaim(t *testing.T, s string) (string, bool) {
	t.Helper()
	f, err := annot.ParseFile("tests/test_claim.sh", []byte("#!/bin/sh\n# testmap:axis "+s+"\n"))
	if err != nil {
		return "", false
	}
	u, _ := f.Unit("")
	if u == nil || len(u.Axes) != 1 || len(u.Axes[0].Args) != 1 {
		return "", false
	}
	return u.Axes[0].Args[0], true
}

// ParseClaim accepts s exactly when the real annotation parser
// (annot.ParseFile) accepts a `testmap:axis s` line and records s itself as
// the argument — over a pinned corpus of edge cases, Unicode whitespace
// included (annot splits arguments with strings.Fields).
func TestParseClaimMatchesAnnotParser(t *testing.T) {
	for _, s := range []string{
		"m.l=ru", "m.l=r.u", "m.l=a/b", "m.l=", ".l=ru", "m.=ru", "m.l.x=ru", "m.l=r=u", "ml=ru",
		"m.l=r u", "m.l=r|u", "m.l=r#u", "m.l=r@u", "m@.l=ru", "m.l#=ru", "a/b.c=d", "m.l=ru\t",
		"m.l=ünï", "m\u00a0.l=ru", "m.l=ru\u00a0alt", "m.l=ru\u2003", "", "m.l=ru ",
	} {
		arg, ok := annotClaim(t, s)
		annotAccepts := ok && arg == s
		if _, err := ParseClaim(s); (err == nil) != annotAccepts {
			t.Errorf("%q: ParseClaim err=%v, annot records it=%v (arg %q)", s, err, annotAccepts, arg)
		}
	}
	if c, _ := ParseClaim("matrix.locale=ru"); c != (Claim{"matrix", "locale", "ru"}) || c.String() != "matrix.locale=ru" {
		t.Fatalf("%+v", c)
	}
}

// Every axis name, facet name and facet value the loader accepts can be
// written as a `testmap:axis` claim the real annotation parser records
// verbatim; the ones it cannot are refused at load.
func TestDeclaredValuesAreClaimable(t *testing.T) {
	for _, v := range []string{"ru", "r.u", "a/b", "ünï", "x-1_2", "ru\u00a0alt", "ru\u2003", "r u", "r|u", "r=u"} {
		decl := "contract: 1\naxes:\n  - name: m\n    facets: [l]\n    values:\n      a: {l: " + strconv.Quote(v) + "}\n"
		_, loadErr := Parse([]byte(decl))
		arg, ok := annotClaim(t, "m.l="+v)
		claimable := ok && arg == "m.l="+v
		if (loadErr == nil) != claimable {
			t.Errorf("facet value %q: load err=%v, claimable=%v", v, loadErr, claimable)
		}
	}
	for _, n := range []string{"matrix", "ma\u00a0trix", "m x", "m/x"} {
		_, axisErr := Parse([]byte("contract: 1\naxes:\n  - name: " + strconv.Quote(n) + "\n    facets: [l]\n    values: {a: {l: x}}\n"))
		_, facetErr := Parse([]byte("contract: 1\naxes:\n  - name: m\n    facets: [" + strconv.Quote(n) + "]\n    values: {a: {" + strconv.Quote(n) + ": x}}\n"))
		a, okA := annotClaim(t, n+".l=x")
		f, okF := annotClaim(t, "m."+n+"=x")
		if axisErr == nil && !(okA && a == n+".l=x") {
			t.Errorf("axis name %q loads but cannot be claimed", n)
		}
		if facetErr == nil && !(okF && f == "m."+n+"=x") {
			t.Errorf("facet name %q loads but cannot be claimed", n)
		}
	}
}

func TestJoin(t *testing.T) {
	tab := mustParse(t, matrixYAML)
	hits := tab.Join([]string{"res/values-ru/strings.xml", "src/Main.kt", "fonts/cyrillic/a.ttf", "res/values-ru/strings.xml"})
	want := []Hit{
		{Axis: "matrix", Facet: "locale", Value: "ru", Glob: "fonts/cyrillic/*.ttf", Origin: OriginHand, Path: "fonts/cyrillic/a.ttf"},
		{Axis: "matrix", Facet: "locale", Value: "ru", Glob: "res/values-ru/**", Origin: OriginHand, Path: "res/values-ru/strings.xml"},
	}
	if !reflect.DeepEqual(hits, want) {
		t.Fatalf("%+v", hits)
	}
	// A deleted path still joins: the match is on the pattern, not the disk.
	if h := tab.Join([]string{"res/values-ar/gone.xml"}); len(h) != 1 || h[0].Value != "ar" {
		t.Fatalf("%+v", h)
	}
	// One path on two values of one facet yields a hit for each.
	two := mustParse(t, strings.Replace(matrixYAML, `ar: ["res/values-ar/**"]`, `ar: ["res/values-ar/**", "res/shared/**"]`, 1))
	two.Axes[0].Sources["locale"]["ru"] = append(two.Axes[0].Sources["locale"]["ru"], Source{Glob: "res/shared/**", Origin: OriginHand})
	if h := two.Join([]string{"res/shared/x"}); len(h) != 2 || h[0].Value != "ar" || h[1].Value != "ru" {
		t.Fatalf("%+v", h)
	}
}

func TestExplain(t *testing.T) {
	tab := mustParse(t, matrixYAML)
	tab.Widen([]ObservedSource{{Axis: "matrix", Facet: "locale", Value: "ru", Glob: "res/xml-ru/**"}})
	for path, want := range map[string][]Explanation{
		"res/values-ru/a.xml": {{"matrix", "locale", "ru", "res/values-ru/**"}, {"matrix", "direction", "-", "no-source"}},
		"src/Main.kt":         {{"matrix", "locale", "-", "no-match"}, {"matrix", "direction", "-", "no-source"}},
		"res/xml-ru/a.xml":    {{"matrix", "locale", "ru", "observed:res/xml-ru/**"}, {"matrix", "direction", "-", "no-source"}},
	} {
		if got := tab.Explain(path); !reflect.DeepEqual(got, want) {
			t.Errorf("%s: %+v", path, got)
		}
	}
}

func rowsFixture() []registry.ScannedRow {
	return []registry.ScannedRow{
		{Test: "app/F.kt#Welcome", Axis: "matrix", Variants: []string{"ar-rtl", "en-ltr", "ru-ltr", "zz-new"}},
		{Test: "app/G.kt#Other", Axis: "other", Variants: []string{"ru-ltr"}},
		{Test: "app/H.kt#Plain", Facets: []string{"matrix.locale=ru"}},
		{Test: "app/H.kt#Bare"},
		{Test: "app/H.kt", Facets: []string{"matrix.locale=ar"}},
		{Test: "tests/test_x.sh", Facets: []string{"matrix.locale=ru"}},
		{Test: "app/V.kt#Claimed", Axis: "matrix", Variants: []string{"en-ltr"}, Facets: []string{"matrix.locale=ru"}},
	}
}

func ids(ps []Placed) []string {
	var out []string
	for _, p := range ps {
		out = append(out, p.ID.String())
	}
	return out
}

func TestSelect(t *testing.T) {
	tab := mustParse(t, matrixYAML)
	got, err := tab.Select(rowsFixture(), tab.Join([]string{"res/values-ru/strings.xml"}))
	if err != nil {
		t.Fatal(err)
	}
	// ru-ltr carries locale=ru; zz-new is undeclared (widening); the other
	// axis's row is not on matrix; the plain member claims ru; the bare member
	// inherits only the file-level ar claim; the file row of a file with
	// members is not a unit; a variant-bearing row's own claim is ignored.
	want := []string{"app/F.kt#Welcome@ru-ltr", "app/F.kt#Welcome@zz-new", "app/H.kt#Plain", "tests/test_x.sh"}
	if !reflect.DeepEqual(ids(got), want) {
		t.Fatalf("%v", ids(got))
	}
	if !got[1].Undeclared || got[0].Undeclared {
		t.Fatalf("undeclared marks: %+v", got)
	}
	if r := got[0].Reason(); r != "axis(matrix.locale=ru) <- res/values-ru/strings.xml" {
		t.Fatal(r)
	}
	got, _ = tab.Select(rowsFixture(), tab.Join([]string{"res/values-ar/x"}))
	if want := []string{"app/F.kt#Welcome@ar-rtl", "app/F.kt#Welcome@zz-new", "app/H.kt#Bare", "app/H.kt#Plain"}; !reflect.DeepEqual(ids(got), want) {
		t.Fatalf("ar: %v", ids(got))
	}
	if got, _ := tab.Select(rowsFixture(), nil); len(got) != 0 {
		t.Fatalf("no hits selects nothing on the axis channel: %v", ids(got))
	}
	if _, err := tab.Select([]registry.ScannedRow{{Test: "a#b@c"}}, nil); err == nil {
		t.Fatal("a scanned row with a variant fragment is refused")
	}
}

// The value -> facet mapping is the table's: two loadable tables that swap
// locale between opaque values select different ids for identical rows and
// an identical hit — so selection cannot be a function of (rows, hits).
func TestSelectReadsTableValues(t *testing.T) {
	mk := func(v1, v2 string) *Table {
		return mustParse(t, "contract: 1\naxes:\n  - name: m\n    facets: [locale]\n    values:\n      v1: {locale: "+v1+"}\n      v2: {locale: "+v2+"}\n    sources:\n      locale:\n        ru: [res/ru/**]\n")
	}
	rows := []registry.ScannedRow{{Test: "a.kt#S", Axis: "m", Variants: []string{"v1", "v2"}}}
	hit := []Hit{{Axis: "m", Facet: "locale", Value: "ru", Glob: "res/ru/**", Origin: OriginHand, Path: "res/ru/x"}}
	a, _ := mk("ru", "en").Select(rows, hit)
	b, _ := mk("en", "ru").Select(rows, hit)
	if !reflect.DeepEqual(ids(a), []string{"a.kt#S@v1"}) || !reflect.DeepEqual(ids(b), []string{"a.kt#S@v2"}) {
		t.Fatalf("%v %v", ids(a), ids(b))
	}
}

// The caller obligation, composed as stated: a changed path covered by an
// ordinary edge with no axis hit keeps every variant of the unit, because the
// selection is Select(Join(changed)) ∪ Expand(edge-reached units), never an
// intersection.
func TestEdgeWithoutAxisHitKeepsAllVariants(t *testing.T) {
	tab := mustParse(t, matrixYAML)
	rows := rowsFixture()
	changed := []string{"src/Main.kt"} // covered by an edge of app/F.kt#Welcome; on no axis source
	edgeReached := []registry.ID{registry.MustParseID("app/F.kt#Welcome")}
	hits := tab.Join(changed)
	if len(hits) != 0 {
		t.Fatalf("fixture: %v", hits)
	}
	placed, err := tab.Select(rows, hits)
	if err != nil {
		t.Fatal(err)
	}
	sel := map[string]bool{}
	for _, p := range placed {
		sel[p.ID.String()] = true
	}
	for _, u := range edgeReached {
		for _, id := range Expand(rows, u) {
			sel[id.String()] = true
		}
	}
	for _, v := range []string{"ar-rtl", "en-ltr", "ru-ltr", "zz-new"} {
		if !sel["app/F.kt#Welcome@"+v] {
			t.Errorf("variant %s lost: %v", v, sel)
		}
	}
}

func TestExpand(t *testing.T) {
	rows := rowsFixture()
	got := Expand(rows, registry.MustParseID("app/F.kt#Welcome"))
	if len(got) != 4 || got[0].String() != "app/F.kt#Welcome@ar-rtl" {
		t.Fatalf("%v", got)
	}
	for _, in := range []string{"app/H.kt#Plain", "app/F.kt#Welcome@ru-ltr", "nowhere.kt"} {
		if got := Expand(rows, registry.MustParseID(in)); len(got) != 1 || got[0].String() != in {
			t.Errorf("%s: %v", in, got)
		}
	}
}

func TestCounts(t *testing.T) {
	c := mustParse(t, matrixYAML).Counts(rowsFixture())
	if want := map[string]int{"ar-rtl": 1, "en-ltr": 2, "ru-ltr": 1}; !reflect.DeepEqual(c["matrix"], want) {
		t.Fatalf("%v", c)
	}
}

func TestForce(t *testing.T) {
	tab := mustParse(t, matrixYAML)
	if _, err := ParseForce("matrix.locale"); err == nil {
		t.Fatal("malformed --axis accepted")
	}
	for in, reason := range map[string]string{"nope.locale=ru": "axis", "matrix.size=ru": "facet", "matrix.locale=fr": "value", "matrix.locale=ru": ""} {
		f, err := ParseForce(in)
		if err != nil {
			t.Fatal(err)
		}
		err = tab.ResolveForce(f)
		var fe *ForceError
		if reason == "" {
			if err != nil {
				t.Errorf("%s: %v", in, err)
			}
			continue
		}
		if !errors.As(err, &fe) || fe.Reason != reason {
			t.Errorf("%s: %v (want %s)", in, err, reason)
		}
	}
	ru, _ := ParseForce("matrix.locale=ru")
	ar, _ := ParseForce("matrix.locale=ar")
	ltr, _ := ParseForce("matrix.direction=ltr")
	ix, err := IndexRows(rowsFixture()) // built once, reused for every candidate
	if err != nil {
		t.Fatal(err)
	}
	for _, c := range []struct {
		forces []Force
		id     string
		want   bool
	}{
		{[]Force{ru}, "app/F.kt#Welcome@ru-ltr", true},
		{[]Force{ru}, "app/F.kt#Welcome@en-ltr", false},
		{[]Force{ru}, "app/F.kt#Welcome@zz-new", false},    // undeclared: cannot be shown to carry ru
		{[]Force{ru, ar}, "app/F.kt#Welcome@ar-rtl", true}, // same facet: alternatives
		{[]Force{ru, ltr}, "app/F.kt#Welcome@ru-ltr", true},
		{[]Force{ar, ltr}, "app/F.kt#Welcome@ar-rtl", false}, // different facets: all must hold
		{[]Force{ru}, "app/G.kt#Other@ru-ltr", true},         // another axis passes
		{[]Force{ru}, "app/H.kt#Plain", true},
		{[]Force{ar}, "app/H.kt#Plain", true}, // inherits the file-level ar claim
		{[]Force{ru}, "app/H.kt#Bare", false}, // claims ar only
		{[]Force{ru}, "tests/other.sh", true}, // unclaimed passes
		{[]Force{ltr}, "app/H.kt#Bare", true}, // no claim on direction
	} {
		if got := tab.Admits(c.forces, ix, registry.MustParseID(c.id)); got != c.want {
			t.Errorf("%v %s: %v (want %v)", c.forces, c.id, got, c.want)
		}
	}
	for _, bad := range []string{"a#b@c", "/abs"} {
		if _, err := IndexRows([]registry.ScannedRow{{Test: bad}}); err == nil {
			t.Errorf("IndexRows accepted row %q", bad)
		}
	}
}

func TestWiden(t *testing.T) {
	tab := mustParse(t, matrixYAML)
	before := tab.Join([]string{"res/values-ru/a", "res/xml-ru/a"})
	rejected := tab.Widen([]ObservedSource{
		{Axis: "matrix", Facet: "locale", Value: "ru", Glob: "res/xml-ru/**"},
		{Axis: "matrix", Facet: "locale", Value: "ru", Glob: "res/values-ru/**"}, // already declared: a no-op
		{Axis: "nope", Facet: "locale", Value: "ru", Glob: "x/**"},
		{Axis: "matrix", Facet: "size", Value: "ru", Glob: "x/**"},
		{Axis: "matrix", Facet: "locale", Value: "fr", Glob: "x/**"},
		{Axis: "matrix", Facet: "locale", Value: "ru", Glob: "["},
		{Axis: "matrix", Facet: "direction", Value: "rtl", Glob: "layout-rtl/**"}, // a facet with no sources yet
	})
	if len(rejected) != 4 {
		t.Fatalf("rejected %v", rejected)
	}
	a, _ := tab.Axis("matrix")
	want := []Source{{"res/values-ru/**", OriginHand}, {"fonts/cyrillic/*.ttf", OriginHand}, {"res/xml-ru/**", OriginObserved}}
	if !reflect.DeepEqual(a.Sources["locale"]["ru"], want) || len(a.Values) != 3 {
		t.Fatalf("%v %v", a.Sources, a.Values)
	}
	if a.Sources["direction"]["rtl"][0].Origin != OriginObserved {
		t.Fatal("observed source on a new facet cell")
	}
	after := tab.Join([]string{"res/values-ru/a", "res/xml-ru/a"})
	if len(after) != len(before)+1 {
		t.Fatalf("before %v after %v", before, after)
	}
}

func TestTokenFormat(t *testing.T) {
	id := registry.MustParseID("app/F.kt#Welcome@ru-ltr")
	for in, want := range map[string]string{
		"{id}":                           "app/F.kt#Welcome@ru-ltr",
		"{base}":                         "app/F.kt#Welcome",
		"{path}::{member}:{variant}":     "app/F.kt::Welcome:ru-ltr",
		"--tests {member} -Pm={variant}": "--tests Welcome -Pm=ru-ltr",
	} {
		f, err := ParseTokenFormat(in)
		if err != nil || f.Render(id) != want || f.String() != in {
			t.Errorf("%q: %v %q", in, err, f.Render(id))
		}
	}
	if (TokenFormat{}).Render(id) != id.String() {
		t.Fatal("zero format renders the id")
	}
	for _, bad := range []string{"", "{x}", "{id", "id}", "}{id}", "{}", "a\nb"} {
		if _, err := ParseTokenFormat(bad); err == nil {
			t.Errorf("%q accepted", bad)
		}
	}
}
