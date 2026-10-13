package main

import (
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

// footprint probes: one minimal module per provider library that USES it (a
// blank import would let dead-code elimination hide the cost), built
// CGO_ENABLED=0 -trimpath for the four release targets, compared with a
// no-op probe and with ait-testmap built from the unpatched snapshot.
var footprintProbes = []struct {
	name, require, note string
	src                 string
}{
	{"noop", "", "reference", `package main

import "os"

func main() { println(len(os.Args)) }
`},
	{"baseline-annot", "goengines", "the landed annot package (current engine cost)", `package main

import (
	"os"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/annot"
)

func main() {
	data, _ := os.ReadFile(os.Args[1])
	l, _ := annot.LangOf(os.Args[1], data)
	println(len(annot.Classify(l, data).Class))
}
`},
	{"goscanner", "", "go/scanner (standard library)", `package main

import (
	"go/scanner"
	"go/token"
	"os"
)

func main() {
	src, _ := os.ReadFile(os.Args[1])
	fs := token.NewFileSet()
	var s scanner.Scanner
	s.Init(fs.AddFile("", fs.Base(), len(src)), src, nil, scanner.ScanComments)
	n := 0
	for _, tok, _ := s.Scan(); tok != token.EOF; _, tok, _ = s.Scan() {
		n++
	}
	println(n)
}
`},
	{"shfmt", "mvdan.cc/sh/v3@v3.14.1", "mvdan.cc/sh/v3/syntax", `package main

import (
	"os"

	"mvdan.cc/sh/v3/syntax"
)

func main() {
	f, _ := os.Open(os.Args[1])
	file, err := syntax.NewParser(syntax.KeepComments(true)).Parse(f, "")
	println(file != nil, err == nil)
}
`},
}

var targets = []string{"linux/amd64", "linux/arm64", "darwin/amd64", "darwin/arm64"}

func cmdFootprint(args []string) int {
	fs := flag.NewFlagSet("footprint", flag.ExitOnError)
	out := fs.String("out", "results/footprint.md", "output file")
	_ = fs.Parse(args)
	tmp, err := os.MkdirTemp("", "t1954-fp-")
	if err != nil {
		fail(1, err)
	}
	defer os.RemoveAll(tmp)
	unpatched, _ := filepath.Abs(filepath.Join(id.Root, ".baseline-unpatched", "goengines"))
	sizes := map[string]map[string]int64{}
	errs := map[string]string{}
	build := func(name, dir, pkg string) {
		sizes[name] = map[string]int64{}
		for _, t := range targets {
			os_, arch, _ := strings.Cut(t, "/")
			bin := filepath.Join(tmp, name+"_"+os_+"_"+arch)
			cmd := exec.Command("go", "build", "-buildvcs=false", "-trimpath", "-o", bin, pkg)
			cmd.Dir = dir
			cmd.Env = append(os.Environ(), "CGO_ENABLED=0", "GOOS="+os_, "GOARCH="+arch, "GOFLAGS=-mod=mod")
			if o, err := cmd.CombinedOutput(); err != nil {
				errs[name+" "+t] = firstLine(string(o))
				continue
			}
			if st, err := os.Stat(bin); err == nil {
				sizes[name][t] = st.Size()
			}
		}
	}
	for _, p := range footprintProbes {
		dir := filepath.Join(tmp, p.name)
		_ = os.MkdirAll(dir, 0o755)
		gomod := "module probe/" + p.name + "\n\ngo 1.26.0\n"
		if p.require == "goengines" {
			// Go's internal rule is import-path based: the probe must live under goengines/.
			gomod = "module github.com/beyondeye/aitasks/goengines/t1954probe\n\ngo 1.26.0\n"
			gomod += "\nrequire github.com/beyondeye/aitasks/goengines v0.0.0\n\nreplace github.com/beyondeye/aitasks/goengines => " + unpatched + "\n"
		}
		_ = os.WriteFile(filepath.Join(dir, "go.mod"), []byte(gomod), 0o644)
		_ = os.WriteFile(filepath.Join(dir, "main.go"), []byte(p.src), 0o644)
		if p.require != "" && p.require != "goengines" {
			if o, err := exec.Command("sh", "-c", "cd "+dir+" && go get "+p.require+" && go mod tidy").CombinedOutput(); err != nil {
				errs[p.name] = firstLine(string(o))
				continue
			}
		} else {
			_ = exec.Command("sh", "-c", "cd "+dir+" && go mod tidy").Run()
		}
		build(p.name, dir, ".")
	}
	// The current engine binary, from the pristine (unpatched) snapshot.
	build("ait-testmap (snapshot)", unpatched, "./cmd/ait-testmap")
	var b strings.Builder
	fmt.Fprintf(&b, "# Footprint (t1954_1)\n\n%s\n\n", id.Header())
	b.WriteString("Probe binaries built `CGO_ENABLED=0 -trimpath -buildvcs=false` for the four release targets; each probe USES its library (a blank import lets dead-code elimination hide the cost). Δ is against the no-op probe. `pytokenize` has no Go-side footprint to measure: it needs a Python 3 interpreter at run time, which no release artefact ships. Rerun: `go run ./cmd/t1954 footprint`.\n\n")
	b.WriteString("| probe | what | " + strings.Join(targets, " | ") + " | Δ vs no-op (linux/amd64) |\n|---|---|---|---|---|---|---|\n")
	notes := map[string]string{"ait-testmap (snapshot)": "the current engine binary, built from the pinned snapshot"}
	for _, p := range footprintProbes {
		notes[p.name] = p.note
	}
	order := []string{"noop", "baseline-annot", "goscanner", "shfmt", "ait-testmap (snapshot)"}
	noop := sizes["noop"]["linux/amd64"]
	for _, n := range order {
		row := "| " + n + " | " + notes[n] + " |"
		for _, t := range targets {
			if s, ok := sizes[n][t]; ok {
				row += fmt.Sprintf(" %d |", s)
			} else if e, ok := errs[n+" "+t]; ok {
				row += " fail: " + esc(e) + " |"
			} else {
				row += " not measured |"
			}
		}
		if s, ok := sizes[n]["linux/amd64"]; ok && noop > 0 {
			row += fmt.Sprintf(" %+d |", s-noop)
		} else {
			row += " — |"
		}
		b.WriteString(row + "\n")
	}
	b.WriteString("| pytokenize | Python tokenize + ast via a subprocess | n/a | n/a | n/a | n/a | runtime dependency: python3 |\n")
	b.WriteString("\nThe tree-sitter / tokenizer candidates' footprints are measured by the children that prototype them (t1954_2, t1954_3); `results/feasibility.md` has their compile-probe sizes.\n")
	if err := os.WriteFile(*out, []byte(b.String()), 0o644); err != nil {
		fail(1, err)
	}
	fmt.Printf("WROTE:%s\n", *out)
	return 0
}
