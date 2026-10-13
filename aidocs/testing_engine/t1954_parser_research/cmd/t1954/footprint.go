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
	ts := fs.Bool("ts", false, "also measure the tree-sitter family (t1954_2) into --ts-out: needs .tsref/ (tsref/fetch.sh) and .tswasm/ts.wasm (tswasm/build.sh)")
	tsOnly := fs.Bool("ts-only", false, "with --ts: build only the no-op reference and the tree-sitter probes; do not write --out")
	tsOut := fs.String("ts-out", "results/footprint_ts.md", "output file of the tree-sitter section")
	zig := fs.String("zig", "", "zig binary for the cgo cross-build attempts (empty = not attempted)")
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
		if *ts && *tsOnly && p.name != "noop" {
			continue
		}
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
	if *ts && *tsOnly {
		return writeTSFootprint(*tsOut, tmp, sizes["noop"]["linux/amd64"], *zig)
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
	if *ts {
		return writeTSFootprint(*tsOut, tmp, noop, *zig)
	}
	return 0
}

func writeTSFootprint(out, tmp string, noop int64, zig string) int {
	var b strings.Builder
	fmt.Fprintf(&b, "# Footprint — tree-sitter family (t1954_2)\n\n%s\n\nProbe binaries built `-trimpath -buildvcs=false` like `results/footprint.md` (t1954_1), whose no-op reference is rebuilt here: %d bytes on linux/amd64.\n", id.Header(), noop)
	b.WriteString(tsFootprint(tmp, noop, zig))
	if err := os.WriteFile(out, []byte(b.String()), 0o644); err != nil {
		fail(1, err)
	}
	fmt.Printf("WROTE:%s\n", out)
	return 0
}

// buildErr is the most informative line of a failed build's output.
func buildErr(o string) string {
	lines := strings.Split(o, "\n")
	for _, l := range lines {
		for _, k := range []string{"build constraints exclude", "error:", "undefined", "cannot"} {
			if strings.Contains(l, k) {
				return strings.TrimSpace(l)
			}
		}
	}
	for _, l := range lines {
		if l = strings.TrimSpace(l); l != "" && !strings.HasPrefix(l, "#") && !strings.HasPrefix(l, "package ") {
			return l
		}
	}
	return firstLine(o)
}

// tsGrammarTags are gotreesitter's subset tags for the 10 research grammars.
var tsGrammarTags = []string{"bash", "python", "go", "kotlin", "typescript", "tsx", "javascript", "java", "rust", "swift"}

const tsProbeSrc = `package main

import (
	"os"

	gts "github.com/odvcencio/gotreesitter"
	"github.com/odvcencio/gotreesitter/grammars"
)

func main() {
	src, _ := os.ReadFile(os.Args[1])
	for _, l := range []func() *gts.Language{grammars.BashLanguage, grammars.PythonLanguage, grammars.GoLanguage,
		grammars.KotlinLanguage, grammars.TypescriptLanguage, grammars.TsxLanguage, grammars.JavascriptLanguage,
		grammars.JavaLanguage, grammars.RustLanguage, grammars.SwiftLanguage} {
		t, err := gts.NewParser(l()).Parse(src)
		println(err == nil && t.RootNode() != nil)
	}
}
`

const tsWasmProbeSrc = `package main

import (
	"context"
	_ "embed"
	"os"

	"github.com/tetratelabs/wazero"
	"github.com/tetratelabs/wazero/imports/wasi_snapshot_preview1"
)

//go:embed ts.wasm
var bin []byte

func main() {
	ctx := context.Background()
	r := wazero.NewRuntime(ctx)
	wasi_snapshot_preview1.MustInstantiate(ctx, r)
	m, err := r.InstantiateWithConfig(ctx, bin, wazero.NewModuleConfig().WithStartFunctions("_initialize"))
	if err != nil {
		panic(err)
	}
	src, _ := os.ReadFile(os.Args[1])
	res, _ := m.ExportedFunction("malloc").Call(ctx, uint64(len(src)+1))
	m.Memory().Write(uint32(res[0]), src)
	out, err := m.ExportedFunction("t1954_parse").Call(ctx, 0, res[0], uint64(len(src)))
	println(err == nil, out[0] != 0)
}
`

const tsCgoProbeSrc = `package main

import (
	"os"
	"unsafe"

	sitter "github.com/tree-sitter/go-tree-sitter"

	"github.com/beyondeye/aitasks/goengines/t1954research/provider/tscgo/tsbash"
	"github.com/beyondeye/aitasks/goengines/t1954research/provider/tscgo/tsgo"
	"github.com/beyondeye/aitasks/goengines/t1954research/provider/tscgo/tsjava"
	"github.com/beyondeye/aitasks/goengines/t1954research/provider/tscgo/tsjavascript"
	"github.com/beyondeye/aitasks/goengines/t1954research/provider/tscgo/tskotlin"
	"github.com/beyondeye/aitasks/goengines/t1954research/provider/tscgo/tspython"
	"github.com/beyondeye/aitasks/goengines/t1954research/provider/tscgo/tsrust"
	"github.com/beyondeye/aitasks/goengines/t1954research/provider/tscgo/tsswift"
	"github.com/beyondeye/aitasks/goengines/t1954research/provider/tscgo/tstsx"
	"github.com/beyondeye/aitasks/goengines/t1954research/provider/tscgo/tstypescript"
)

func main() {
	src, _ := os.ReadFile(os.Args[1])
	p := sitter.NewParser()
	for _, l := range []func() unsafe.Pointer{tsbash.Language, tspython.Language, tsgo.Language, tskotlin.Language,
		tstypescript.Language, tstsx.Language, tsjavascript.Language, tsjava.Language, tsrust.Language, tsswift.Language} {
		_ = p.SetLanguage(sitter.NewLanguage(l()))
		println(p.Parse(src, nil) != nil)
	}
}
`

// tsFootprint measures the tree-sitter family: gotreesitter (curated subset
// and all grammars) and tswasm (wazero + the embedded module) under the
// release constraints; tscgo under CGO_ENABLED=0 (expected to fail), as a
// host cgo build, and — when zig is given — as cgo cross builds with zig cc.
func tsFootprint(tmp string, noop int64, zig string) string {
	type row struct{ name, what string }
	sizes := map[string]map[string]int64{}
	errs := map[string]string{}
	root, _ := filepath.Abs(id.Root)
	run := func(name, dir, tags string, env []string, t string) {
		os_, arch, _ := strings.Cut(t, "/")
		bin := filepath.Join(tmp, strings.ReplaceAll(name, " ", "_")+"_"+os_+"_"+arch)
		args := []string{"build", "-buildvcs=false", "-trimpath", "-o", bin}
		if tags != "" {
			args = append(args, "-tags", tags)
		}
		cmd := exec.Command("go", append(args, ".")...)
		cmd.Dir = dir
		cmd.Env = append(append(os.Environ(), "GOOS="+os_, "GOARCH="+arch, "GOFLAGS=-mod=mod"), env...)
		if sizes[name] == nil {
			sizes[name] = map[string]int64{}
		}
		if o, err := cmd.CombinedOutput(); err != nil {
			errs[name+" "+t] = strings.ReplaceAll(strings.ReplaceAll(buildErr(string(o)), root, "<R>"), filepath.Dir(zig), "<zig>")
			return
		}
		if st, err := os.Stat(bin); err == nil {
			sizes[name][t] = st.Size()
		}
	}
	mk := func(name, gomod, src string, deps []string, files map[string]string) (string, error) {
		dir := filepath.Join(tmp, "ts_"+strings.ReplaceAll(name, " ", "_"))
		_ = os.MkdirAll(dir, 0o755)
		_ = os.WriteFile(filepath.Join(dir, "go.mod"), []byte(gomod), 0o644)
		_ = os.WriteFile(filepath.Join(dir, "main.go"), []byte(src), 0o644)
		for dst, from := range files {
			b, err := os.ReadFile(from)
			if err != nil {
				return "", err
			}
			_ = os.WriteFile(filepath.Join(dir, dst), b, 0o644)
		}
		cmdline := "cd " + dir
		for _, d := range deps {
			cmdline += " && go get " + d
		}
		cmdline += " && go mod tidy"
		if o, err := exec.Command("sh", "-c", cmdline).CombinedOutput(); err != nil {
			return "", fmt.Errorf("%s", firstLine(string(o)))
		}
		return dir, nil
	}
	nocgo := []string{"CGO_ENABLED=0"}
	var subsetTags []string
	for _, g := range tsGrammarTags {
		subsetTags = append(subsetTags, "grammar_subset_"+g)
	}
	rows := []row{}
	if dir, err := mk("gotreesitter", "module probe/gts\n\ngo 1.26.0\n", tsProbeSrc, []string{"github.com/odvcencio/gotreesitter@v0.55.1"}, nil); err != nil {
		errs["gotreesitter (subset)"], errs["gotreesitter (all)"] = err.Error(), err.Error()
	} else {
		for _, t := range targets {
			run("gotreesitter (subset)", dir, "grammar_subset "+strings.Join(subsetTags, " "), nocgo, t)
			run("gotreesitter (all)", dir, "", nocgo, t)
		}
	}
	rows = append(rows, row{"gotreesitter (subset)", "gotreesitter v0.55.1, `grammar_subset` + the 10 `grammar_subset_<lang>` tags, CGO_ENABLED=0"},
		row{"gotreesitter (all)", "gotreesitter v0.55.1, default embedding (all ~206 grammars), CGO_ENABLED=0"})
	if dir, err := mk("tswasm", "module probe/tswasm\n\ngo 1.26.0\n", tsWasmProbeSrc, []string{"github.com/tetratelabs/wazero@v1.12.0"},
		map[string]string{"ts.wasm": filepath.Join(root, ".tswasm", "ts.wasm")}); err != nil {
		errs["tswasm"] = err.Error()
	} else {
		for _, t := range targets {
			run("tswasm", dir, "", nocgo, t)
		}
	}
	rows = append(rows, row{"tswasm", "wazero v1.12.0 + the embedded `.tswasm/ts.wasm` (C runtime + 10 grammars), CGO_ENABLED=0"})
	cgoMod := "module probe/tscgo\n\ngo 1.26.0\n\nrequire github.com/beyondeye/aitasks/goengines/t1954research v0.0.0\n\n" +
		"replace github.com/beyondeye/aitasks/goengines/t1954research => " + root + "\n\n" +
		"replace github.com/beyondeye/aitasks/goengines => " + filepath.Join(root, ".baseline", "goengines") + "\n"
	if dir, err := mk("tscgo", cgoMod, tsCgoProbeSrc, nil, nil); err != nil {
		errs["tscgo (CGO_ENABLED=0)"] = err.Error()
	} else {
		for _, t := range targets {
			run("tscgo (CGO_ENABLED=0)", dir, "t1954cgo", nocgo, t)
		}
		run("tscgo (host cgo)", dir, "t1954cgo", []string{"CGO_ENABLED=1"}, "linux/amd64")
		if zig != "" {
			for t, zt := range map[string]string{"linux/arm64": "aarch64-linux-gnu", "darwin/amd64": "x86_64-macos", "darwin/arm64": "aarch64-macos"} {
				run("tscgo (cgo, zig cc cross)", dir, "t1954cgo", []string{"CGO_ENABLED=1", "CC=" + zig + " cc -target " + zt}, t)
			}
		}
	}
	rows = append(rows, row{"tscgo (CGO_ENABLED=0)", "go-tree-sitter v0.25.0 + the 10 C grammars (`-tags t1954cgo`), CGO_ENABLED=0 — the release constraint"},
		row{"tscgo (host cgo)", "the same with CGO_ENABLED=1, host toolchain (gcc)"})
	if zig != "" {
		rows = append(rows, row{"tscgo (cgo, zig cc cross)", "the same with CGO_ENABLED=1 and `zig cc -target <triple>` as CC (zig " + zigVersion(zig) + ")"})
	}
	var b strings.Builder
	b.WriteString("\nRerun: `tsref/fetch.sh && tswasm/build.sh <zig> && go run ./cmd/t1954 footprint --ts --ts-only --zig <zig>`. Each probe parses real input with all 10 research grammars (a blank import would let dead-code elimination hide the cost). Δ is against the no-op probe above. A failure is the most informative line of the build error (`<R>` = the research directory).\n\n")
	b.WriteString("| probe | what | " + strings.Join(targets, " | ") + " | Δ vs no-op (linux/amd64) |\n|---|---|---|---|---|---|---|\n")
	for _, r := range rows {
		line := "| " + r.name + " | " + r.what + " |"
		for _, t := range targets {
			switch {
			case sizes[r.name][t] > 0:
				line += fmt.Sprintf(" %d |", sizes[r.name][t])
			case errs[r.name+" "+t] != "":
				line += " fail: " + esc(errs[r.name+" "+t]) + " |"
			case errs[r.name] != "":
				line += " fail: " + esc(errs[r.name]) + " |"
			default:
				line += " not attempted |"
			}
		}
		if s := sizes[r.name]["linux/amd64"]; s > 0 && noop > 0 {
			line += fmt.Sprintf(" %+d |", s-noop)
		} else {
			line += " — |"
		}
		b.WriteString(line + "\n")
	}
	return b.String()
}

func zigVersion(zig string) string {
	o, err := exec.Command(zig, "version").Output()
	if err != nil {
		return "unknown"
	}
	return strings.TrimSpace(string(o))
}
