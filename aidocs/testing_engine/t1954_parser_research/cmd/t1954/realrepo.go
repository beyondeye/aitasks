package main

import (
	"bytes"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/annot"
	"github.com/beyondeye/aitasks/goengines/t1954research/internal/corpus"
	"github.com/beyondeye/aitasks/goengines/t1954research/internal/runner"
	"github.com/beyondeye/aitasks/goengines/t1954research/provider"
)

// rrAgg is one subject × language over a real repository, compared with the
// baseline (the landed lexers) as the reference.
type rrAgg struct {
	files, errs, unsupported             int
	classDiffFiles, classDiffLines       int // lines whose Comment-ness differs
	uncertainOnlyBase, uncertainOnlySubj int // files uncertain for one side only
	recordDiffFiles                      int
	paths                                map[string][]string // kind -> paths (no contents)
}

const maxFileBytes = 2 << 20

// cmdRealrepo walks a repository READ-ONLY: git-visible files of the known
// languages are read and analysed; nothing is executed or written there.
// Output is counts and paths, never file contents.
func cmdRealrepo(args []string) int {
	fs := flag.NewFlagSet("realrepo", flag.ExitOnError)
	repo := fs.String("repo", "", "repository path (read-only)")
	name := fs.String("name", "", "report name (default: basename of --repo)")
	prov := fs.String("provider", "all", "subjects compared with the baseline")
	out := fs.String("out", "results", "output directory")
	maxPaths := fs.Int("max-paths", 40, "paths listed per disagreement kind")
	inputLabel := fs.Bool("input-label", false, "print the walked checkout's commit (and dirty state) under the header")
	_ = fs.Parse(args)
	if *repo == "" {
		fail(64, fmt.Errorf("realrepo: --repo required"))
	}
	if *name == "" {
		*name = filepath.Base(filepath.Clean(*repo))
	}
	subs, err := subjects(*prov)
	if err != nil {
		fail(1, err)
	}
	defer provider.CloseAll()
	lsOut, err := exec.Command("git", "-C", *repo, "ls-files", "-z", "--cached", "--others", "--exclude-standard").Output()
	if err != nil {
		fail(1, fmt.Errorf("git ls-files: %w", err))
	}
	files := strings.Split(strings.TrimRight(string(lsOut), "\x00"), "\x00")
	sort.Strings(files)
	byLang := map[string][]string{}
	skipped := 0
	for _, f := range files {
		if f == "" || strings.Contains(f, "/.baseline") {
			continue
		}
		p := filepath.Join(*repo, f)
		st, err := os.Lstat(p)
		if err != nil || !st.Mode().IsRegular() {
			continue
		}
		head := make([]byte, 0)
		if filepath.Ext(f) == "" {
			if b, err := readHead(p, 128); err == nil {
				head = b
			}
		}
		l, ok := provider.LangOfPath(f, head)
		if !ok {
			continue
		}
		if st.Size() > maxFileBytes {
			skipped++
			continue
		}
		byLang[l.Name] = append(byLang[l.Name], f)
	}
	aggs := map[string]map[string]*rrAgg{} // subject -> lang -> agg
	for _, s := range subs {
		if s.IsBaseline() {
			continue
		}
		aggs[s.Name] = map[string]*rrAgg{}
	}
	baseUnc := map[string]int{}
	for _, lang := range provider.AllLangs {
		for _, f := range byLang[lang] {
			data, err := os.ReadFile(filepath.Join(*repo, f))
			if err != nil {
				continue
			}
			var bctx annot.Context
			var brecs []corpus.Record
			bok := !provider.IsResearch(lang)
			if bok {
				bctx, brecs = analyse(runner.Baseline, lang, f, data)
				if bctx.Uncertain != nil {
					baseUnc[lang]++
				}
			}
			for _, s := range subs {
				if s.IsBaseline() {
					continue
				}
				a := aggs[s.Name][lang]
				if a == nil {
					a = &rrAgg{paths: map[string][]string{}}
					aggs[s.Name][lang] = a
				}
				a.files++
				if !s.Supports(lang) {
					a.unsupported++
					continue
				}
				sctx, srecs, err := analyseErr(s, lang, f, data)
				if err != nil {
					a.errs++
					a.add("provider-error", f, *maxPaths)
					continue
				}
				if !bok {
					continue
				}
				switch {
				case bctx.Uncertain != nil && sctx.Uncertain == nil:
					a.uncertainOnlyBase++
					a.add("uncertain-baseline-only", f, *maxPaths)
				case bctx.Uncertain == nil && sctx.Uncertain != nil:
					a.uncertainOnlySubj++
					a.add("uncertain-"+s.Name+"-only", f, *maxPaths)
				}
				if bctx.Uncertain == nil && sctx.Uncertain == nil {
					d := 0
					for i := range bctx.Class {
						if i < len(sctx.Class) && (bctx.Class[i] == annot.Comment) != (sctx.Class[i] == annot.Comment) {
							d++
						}
					}
					if d > 0 {
						a.classDiffFiles++
						a.classDiffLines += d
						a.add("comment-class-differs", f, *maxPaths)
					}
					if recString(brecs) != recString(srecs) {
						a.recordDiffFiles++
						a.add("records-differ", f, *maxPaths)
					}
				}
			}
		}
	}
	var b strings.Builder
	fmt.Fprintf(&b, "# Real-repository disagreement: %s\n\n%s\n\n", *name, id.Header())
	if *inputLabel {
		fmt.Fprintf(&b, "Input: `%s%s`, the walked checkout at that commit.\n\n", *name, describeCheckout(*repo))
	}
	b.WriteString("Read-only walk of the repository's git-visible files (`git ls-files --cached --others --exclude-standard`) in the 8 research languages; nothing was executed or written there, and this report holds counts and paths only, never contents. ")
	fmt.Fprintf(&b, "Each candidate is compared with the baseline (the landed M2.2 lexers) as the reference; a disagreement is evidence to inspect, not a verdict on either side. Files over %d bytes skipped: %d.\n\n", maxFileBytes, skipped)
	b.WriteString("## Files per language\n\n| lang | files | baseline uncertain |\n|---|---|---|\n")
	for _, lang := range provider.AllLangs {
		bu := fmt.Sprint(baseUnc[lang])
		if provider.IsResearch(lang) {
			bu = "unsupported"
		}
		fmt.Fprintf(&b, "| %s | %d | %s |\n", lang, len(byLang[lang]), bu)
	}
	b.WriteString("\n## Candidate vs baseline\n\n| subject | lang | files | unsupported | provider errors | comment-class differs (files / lines) | records differ (files) | uncertain: baseline only | uncertain: subject only |\n|---|---|---|---|---|---|---|---|---|\n")
	var names []string
	for n := range aggs {
		names = append(names, n)
	}
	sort.Strings(names)
	for _, n := range names {
		for _, lang := range provider.AllLangs {
			a := aggs[n][lang]
			if a == nil || a.files == a.unsupported {
				continue
			}
			fmt.Fprintf(&b, "| %s | %s | %d | %d | %d | %d / %d | %d | %d | %d |\n", n, lang, a.files, a.unsupported, a.errs,
				a.classDiffFiles, a.classDiffLines, a.recordDiffFiles, a.uncertainOnlyBase, a.uncertainOnlySubj)
		}
	}
	b.WriteString("\n## Paths per disagreement kind\n\n")
	any := false
	for _, n := range names {
		for _, lang := range provider.AllLangs {
			a := aggs[n][lang]
			if a == nil {
				continue
			}
			var kinds []string
			for k := range a.paths {
				kinds = append(kinds, k)
			}
			sort.Strings(kinds)
			for _, k := range kinds {
				any = true
				fmt.Fprintf(&b, "- %s / %s / %s:\n", n, lang, k)
				for _, p := range a.paths[k] {
					fmt.Fprintf(&b, "  - `%s`\n", p)
				}
			}
		}
	}
	if !any {
		b.WriteString("None.\n")
	}
	if err := os.MkdirAll(*out, 0o755); err != nil {
		fail(1, err)
	}
	p := filepath.Join(*out, "realrepo_"+*name+".md")
	if err := os.WriteFile(p, []byte(b.String()), 0o644); err != nil {
		fail(1, err)
	}
	fmt.Printf("WROTE:%s\n", p)
	return 0
}

func (a *rrAgg) add(kind, path string, max int) {
	if len(a.paths[kind]) < max {
		a.paths[kind] = append(a.paths[kind], path)
	}
}

func readHead(p string, n int) ([]byte, error) {
	f, err := os.Open(p)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	buf := make([]byte, n)
	k, _ := f.Read(buf)
	return buf[:k], nil
}

func analyse(s runner.Subject, lang, path string, data []byte) (annot.Context, []corpus.Record) {
	ctx, recs, _ := analyseErr(s, lang, path, data)
	return ctx, recs
}

// analyseErr returns the subject's context and the record list ParseFile
// reads through the seam ("" refusals leave records nil).
func analyseErr(s runner.Subject, lang, path string, data []byte) (annot.Context, []corpus.Record, error) {
	ctx, err := runner.ContextOf(s, lang, data)
	if err != nil {
		return ctx, nil, err
	}
	f, perr := runner.ParseOf(s, path, data)
	if perr != nil || f == nil {
		return ctx, nil, nil
	}
	return ctx, corpus.Records(f), nil
}

func recString(rs []corpus.Record) string {
	var b bytes.Buffer
	for _, r := range rs {
		b.WriteString(r.String())
		b.WriteByte('\n')
	}
	return b.String()
}
