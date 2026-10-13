package main

import (
	"bytes"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/beyondeye/aitasks/goengines/t1954research/internal/corpus"
	"github.com/beyondeye/aitasks/goengines/t1954research/internal/oracle"
	"github.com/beyondeye/aitasks/goengines/t1954research/internal/report"
	"github.com/beyondeye/aitasks/goengines/t1954research/internal/runner"
	"github.com/beyondeye/aitasks/goengines/t1954research/internal/seam"
	"github.com/beyondeye/aitasks/goengines/t1954research/provider"
)

func subjectNames() []string { return append([]string{"baseline"}, provider.Names()...) }

func subjects(spec string) ([]runner.Subject, error) {
	names := subjectNames()
	if spec != "" && spec != "all" {
		names = strings.Split(spec, ",")
	}
	var out []runner.Subject
	for _, n := range names {
		if n == "baseline" {
			out = append(out, runner.Baseline)
			continue
		}
		if !seam.Available {
			return nil, fmt.Errorf("provider %q needs the seam; this is the unpatched (guard) build", n)
		}
		p, err := provider.New(n)
		if err != nil {
			return nil, err
		}
		out = append(out, runner.Subject{Name: n, P: p})
	}
	return out, nil
}

func filterLangs(cases []corpus.Case, spec string) []corpus.Case {
	if spec == "" {
		return cases
	}
	want := map[string]bool{}
	for _, l := range strings.Split(spec, ",") {
		want[l] = true
	}
	var out []corpus.Case
	for _, c := range cases {
		if want[c.Lang] {
			out = append(out, c)
		}
	}
	return out
}

// corpusLangs is the corpus directory order used in every table.
var corpusLangs = []string{"bash", "python", "go", "kotlin", "typescript", "java", "rust", "swift"}

func runAll(subs []runner.Subject, cases []corpus.Case, opt runner.Options) map[string][]runner.Row {
	out := map[string][]runner.Row{}
	for _, s := range subs {
		for _, c := range cases {
			out[s.Name] = append(out[s.Name], runner.Run(s, c, opt))
		}
	}
	return out
}

func cmdMatrix(args []string) int {
	fs := flag.NewFlagSet("matrix", flag.ExitOnError)
	prov := fs.String("provider", "all", "subjects (comma list) or all")
	lang := fs.String("lang", "", "corpus languages (comma list); empty = all")
	out := fs.String("out", "results", "output directory")
	beh := fs.Bool("behaviour", true, "run controlled exec: fixtures before/after applied edits")
	orc := fs.Bool("oracle", true, "compare provider comment ranges with native oracles")
	_ = fs.Parse(args)
	subs, err := subjects(*prov)
	if err != nil {
		fail(1, err)
	}
	cases, err := corpus.Load("corpus")
	if err != nil {
		fail(1, err)
	}
	cases = filterLangs(cases, *lang)
	opt := runner.Options{Behaviour: *beh}
	if *orc {
		opt.Oracle = oracle.Comments
		defer oracle.Close()
	}
	defer provider.CloseAll()
	rows := runAll(subs, cases, opt)
	if err := os.MkdirAll(*out, 0o755); err != nil {
		fail(1, err)
	}
	var order []string
	for _, s := range subs {
		order = append(order, s.Name)
		p := filepath.Join(*out, "matrix_"+s.Name+".md")
		if err := os.WriteFile(p, []byte(report.Matrix(s.Name, id.Header(), rows[s.Name], corpusLangs)), 0o644); err != nil {
			fail(1, err)
		}
		fmt.Printf("WROTE:%s\n", p)
	}
	if *prov == "all" && *lang == "" {
		p := filepath.Join(*out, "matrix.md")
		if err := os.WriteFile(p, []byte(report.Combined(id.Header(), rows, order, corpusLangs)), 0o644); err != nil {
			fail(1, err)
		}
		fmt.Printf("WROTE:%s\n", p)
	}
	return 0
}

func cmdEdit(args []string) int {
	fs := flag.NewFlagSet("edit", flag.ExitOnError)
	prov := fs.String("provider", "baseline", "subject")
	lang := fs.String("lang", "", "corpus languages")
	_ = fs.Parse(args)
	subs, err := subjects(*prov)
	if err != nil {
		fail(1, err)
	}
	cases, err := corpus.Load("corpus")
	if err != nil {
		fail(1, err)
	}
	var withEdits []corpus.Case
	for _, c := range filterLangs(cases, *lang) {
		if len(c.Edits) > 0 {
			withEdits = append(withEdits, c)
		}
	}
	defer provider.CloseAll()
	fmt.Println(id.Header())
	bad := 0
	for _, s := range subs {
		for _, c := range withEdits {
			r := runner.Run(s, c, runner.Options{Behaviour: true})
			fmt.Printf("%s %s/%s status=%s ops=%d applied=%d refused=%d unsupported=%d not-measured=%d corruption=%d fidelity=%d behaviour=%d\n",
				s.Name, c.Lang, c.Name, r.Status, r.Ops, r.OpsApplied, r.OpsRefused, r.OpsUnsupported, r.OpsNotMeasured, r.RecordCorruption, r.Fidelity, r.Behaviour)
			for _, n := range r.Notes {
				if strings.HasPrefix(n, "op ") {
					fmt.Printf("    %s\n", n)
				}
			}
			bad += r.RecordCorruption + r.DocstringWrite + r.FPWritable + r.Fidelity
		}
	}
	if bad > 0 {
		return 1
	}
	return 0
}

// cmdGuard proves seam.patch is behaviour-neutral: the baseline matrix from
// a build against the UNPATCHED snapshot and from this (patched, unhooked)
// build must be byte-identical apart from the identity line, whose commit
// and tree must agree.
func cmdGuard(args []string) int {
	if !seam.Available {
		fail(1, fmt.Errorf("run guard from the normal (patched) build"))
	}
	fs := flag.NewFlagSet("guard", flag.ExitOnError)
	beh := fs.Bool("behaviour", true, "include controlled exec: fixtures")
	gout := fs.String("out", "", "also write the verdict to this markdown file")
	_ = fs.Parse(args)
	verdict := func(line, ha, hb string, size int) int {
		fmt.Println(line)
		if *gout != "" {
			var b strings.Builder
			b.WriteString("# Seam guard (t1954_1)\n\n")
			b.WriteString("`seam.patch` must be behaviour-neutral: the baseline matrix built against the UNPATCHED snapshot (`-tags unpatched -modfile=go.unpatched.mod`) and against the patched snapshot with both hooks nil must be byte-identical, apart from the identity line (whose commit and tree must agree). Rerun: `go run ./cmd/t1954 guard`.\n\n")
			fmt.Fprintf(&b, "- unpatched: `%s`\n- patched:   `%s`\n- compared: %d bytes\n\n**%s**\n\n", ha, hb, size, line)
			b.WriteString("Negative control (run by hand in a scratch copy, 2026-10-12): a mutant unpatched snapshot whose Go lexer drops the package anchor (`c.Package = 0`) makes the guard report `GUARD:FAIL|baseline matrices differ …` — the guard can detect a behaviour difference.\n")
			_ = os.WriteFile(*gout, []byte(b.String()), 0o644)
		}
		if strings.HasPrefix(line, "GUARD:PASS") {
			return 0
		}
		return 1
	}
	// The two builds must differ only in the snapshot they replace goengines with.
	gm, _ := os.ReadFile("go.mod")
	um, _ := os.ReadFile("go.unpatched.mod")
	gs, _ := os.ReadFile("go.sum")
	us, _ := os.ReadFile("go.unpatched.sum")
	want := bytes.ReplaceAll(gm, []byte("./.baseline/goengines"), []byte("./.baseline-unpatched/goengines"))
	if !bytes.Equal(want, um) || !bytes.Equal(gs, us) {
		fmt.Println("GUARD:FAIL|go.unpatched.mod/.sum are out of sync with go.mod/.sum (regenerate: see README)")
		return 1
	}
	tmp, err := os.MkdirTemp("", "t1954-guard-")
	if err != nil {
		fail(1, err)
	}
	defer os.RemoveAll(tmp)
	un, pa := filepath.Join(tmp, "unpatched"), filepath.Join(tmp, "patched")
	cmd := exec.Command("go", "run", "-tags", "unpatched", "-modfile=go.unpatched.mod", "./cmd/t1954",
		"matrix", "--provider", "baseline", "--oracle=false", fmt.Sprintf("--behaviour=%v", *beh), "--out", un)
	cmd.Stdout, cmd.Stderr = os.Stderr, os.Stderr
	if err := cmd.Run(); err != nil {
		fmt.Println("GUARD:FAIL|unpatched build/run failed: " + err.Error())
		return 1
	}
	if code := cmdMatrix([]string{"--provider", "baseline", "--oracle=false", fmt.Sprintf("--behaviour=%v", *beh), "--out", pa}); code != 0 {
		return code
	}
	a, err1 := os.ReadFile(filepath.Join(un, "matrix_baseline.md"))
	b, err2 := os.ReadFile(filepath.Join(pa, "matrix_baseline.md"))
	if err1 != nil || err2 != nil {
		fmt.Printf("GUARD:FAIL|missing output: %v %v\n", err1, err2)
		return 1
	}
	ha, ra := splitHeader(a)
	hb, rb := splitHeader(b)
	fmt.Println("unpatched: " + ha)
	fmt.Println("patched:   " + hb)
	if field(ha, "commit") != field(hb, "commit") || field(ha, "tree") != field(hb, "tree") {
		fmt.Println("GUARD:FAIL|identities name different commits/trees")
		return 1
	}
	if !bytes.Equal(ra, rb) {
		return verdict("GUARD:FAIL|baseline matrices differ between the unpatched and the patched-unhooked build", ha, hb, len(ra))
	}
	return verdict(fmt.Sprintf("GUARD:PASS|baseline matrices byte-identical (%d bytes) excluding the identity line", len(ra)), ha, hb, len(ra))
}

func splitHeader(b []byte) (string, []byte) {
	var head string
	var rest [][]byte
	for _, l := range bytes.Split(b, []byte("\n")) {
		if bytes.HasPrefix(l, []byte("baseline: commit=")) && head == "" {
			head = string(l)
			continue
		}
		rest = append(rest, l)
	}
	return head, bytes.Join(rest, []byte("\n"))
}

func field(h, k string) string {
	for _, f := range strings.Fields(h) {
		if v, ok := strings.CutPrefix(f, k+"="); ok {
			return v
		}
	}
	return ""
}

func cmdClasses(args []string) int {
	fs := flag.NewFlagSet("classes", flag.ExitOnError)
	prov := fs.String("provider", "baseline", "subject")
	_ = fs.Parse(args)
	subs, err := subjects(*prov)
	if err != nil {
		fail(1, err)
	}
	defer provider.CloseAll()
	for _, p := range fs.Args() {
		data, err := os.ReadFile(p)
		if err != nil {
			fail(1, err)
		}
		c := corpus.Case{Lang: "?", Name: strings.TrimSuffix(filepath.Base(p), ".in"), Data: data, Exp: corpus.Expect{Placement: map[string]int{}}}
		for _, s := range subs {
			r := runner.Run(s, c, runner.Options{})
			fmt.Printf("%s %s status=%s classes=%s\n", s.Name, p, r.Status, runner.ClassString(r.Classes))
			for _, n := range r.Notes {
				fmt.Printf("    %s\n", n)
			}
		}
	}
	return 0
}
