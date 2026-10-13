package main

// footprint-t3: the t1954_3 candidates' footprint. Go libraries (Chroma,
// the ANTLR4 runtime + the committed generated lexers) are probe binaries
// built like t1954_1's (CGO_ENABLED=0 -trimpath, the four release targets,
// each probe USING its library on real input). Subprocess providers have no
// Go-side cost; their runtime + library on disk is measured instead (`du` of
// the scratch installs named by the env vars), since no release artefact
// ships Python, Node.js or a JVM. Writes its own file, so t1954_1's
// footprint.md stays as committed.

import (
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

func init() { extraVerbs["footprint-t3"] = cmdFootprintT3 }

const chromaProbeSrc = `package main

import (
	"os"

	"github.com/alecthomas/chroma/v2"
	"github.com/alecthomas/chroma/v2/lexers"
)

func main() {
	data, _ := os.ReadFile(os.Args[1])
	n := 0
	for _, name := range []string{"bash", "python", "go", "kotlin", "typescript", "javascript", "java", "rust", "swift"} {
		it, _ := lexers.Get(name).Tokenise(&chroma.TokeniseOptions{State: "root"}, string(data))
		for t := it(); t != chroma.EOF; t = it() {
			n++
		}
	}
	println(n)
}
`

const antlrProbeSrc = `package main

import (
	"os"

	"github.com/antlr4-go/antlr/v4"

	antlrjava "github.com/beyondeye/aitasks/goengines/t1954research/provider/antlrgen/java"
	antlrkotlin "github.com/beyondeye/aitasks/goengines/t1954research/provider/antlrgen/kotlin"
	antlrrust "github.com/beyondeye/aitasks/goengines/t1954research/provider/antlrgen/rust"
)

func count(l antlr.Lexer) int {
	n := 0
	for t := l.NextToken(); t.GetTokenType() != antlr.TokenEOF; t = l.NextToken() {
		n++
	}
	return n
}

func main() {
	data, _ := os.ReadFile(os.Args[1])
	s := string(data)
	n := count(antlrkotlin.NewKotlinLexer(antlr.NewInputStream(s)))
	n += count(antlrjava.NewJavaLexer(antlr.NewInputStream(s)))
	n += count(antlrrust.NewRustLexer(antlr.NewInputStream(s)))
	println(n)
}
`

func cmdFootprintT3(args []string) int {
	fs := flag.NewFlagSet("footprint-t3", flag.ExitOnError)
	out := fs.String("out", "results/footprint_t3.md", "output file")
	_ = fs.Parse(args)
	tmp, err := os.MkdirTemp("", "t1954-fp3-")
	if err != nil {
		fail(1, err)
	}
	defer os.RemoveAll(tmp)
	root, _ := filepath.Abs(id.Root)
	sizes := map[string]map[string]int64{}
	errs := map[string]string{}
	mk := func(name, gomod, src string, deps []string) (string, error) {
		dir := filepath.Join(tmp, name)
		_ = os.MkdirAll(dir, 0o755)
		_ = os.WriteFile(filepath.Join(dir, "go.mod"), []byte(gomod), 0o644)
		_ = os.WriteFile(filepath.Join(dir, "main.go"), []byte(src), 0o644)
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
	build := func(name, dir string) {
		sizes[name] = map[string]int64{}
		for _, t := range targets {
			os_, arch, _ := strings.Cut(t, "/")
			bin := filepath.Join(tmp, strings.ReplaceAll(name, " ", "_")+"_"+os_+"_"+arch)
			cmd := exec.Command("go", "build", "-buildvcs=false", "-trimpath", "-o", bin, ".")
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
	type row struct{ name, what string }
	var rows []row
	if dir, err := mk("noop", "module probe/noop\n\ngo 1.26.0\n", footprintProbes[0].src, nil); err == nil {
		build("noop", dir)
	} else {
		errs["noop"] = err.Error()
	}
	rows = append(rows, row{"noop", "reference"})
	if dir, err := mk("chroma", "module probe/chroma\n\ngo 1.26.0\n", chromaProbeSrc, []string{"github.com/alecthomas/chroma/v2@v2.27.0"}); err == nil {
		build("chroma", dir)
	} else {
		errs["chroma"] = err.Error()
	}
	rows = append(rows, row{"chroma", "github.com/alecthomas/chroma/v2 v2.27.0 `lexers` (the registry embeds every lexer; no per-language subset), 9 lexers used"})
	antlrMod := "module probe/antlr\n\ngo 1.26.0\n\nrequire github.com/beyondeye/aitasks/goengines/t1954research v0.0.0\n\n" +
		"replace github.com/beyondeye/aitasks/goengines/t1954research => " + root + "\n\n" +
		"replace github.com/beyondeye/aitasks/goengines => " + filepath.Join(root, ".baseline", "goengines") + "\n"
	if dir, err := mk("antlr", antlrMod, antlrProbeSrc, nil); err == nil {
		build("antlr", dir)
	} else {
		errs["antlr"] = err.Error()
	}
	rows = append(rows, row{"antlr", "antlr4-go/antlr/v4 v4.13.1 + the three generated lexers (provider/antlrgen: Kotlin, Java, Rust), driven directly"})

	var b strings.Builder
	fmt.Fprintf(&b, "# Footprint (t1954_3)\n\n%s\n\n", id.Header())
	b.WriteString("Rerun: `go run ./cmd/t1954 footprint-t3` (subprocess rows read the scratch installs named by `T1954_PYGMENTS_PYTHON`, `T1954_TS_NODE_MODULES`, `T1954_KOTLINC`, `T1954_TM_NODE_MODULES`, `T1954_LSP_NODE_MODULES`, `T1954_GOPLS`, `T1954_KOTLIN_LSP`). Go probes are built `CGO_ENABLED=0 -trimpath -buildvcs=false` for the four release targets and USE their library; Δ is against the no-op probe. The no-op, baseline-annot and engine rows of t1954_1 are in `footprint.md`.\n\n")
	b.WriteString("## Go libraries\n\n| probe | what | " + strings.Join(targets, " | ") + " | Δ vs no-op (linux/amd64) |\n|---|---|---|---|---|---|---|\n")
	noop := sizes["noop"]["linux/amd64"]
	for _, r := range rows {
		line := "| " + r.name + " | " + r.what + " |"
		for _, t := range targets {
			if s, ok := sizes[r.name][t]; ok {
				line += fmt.Sprintf(" %d |", s)
			} else if e, ok := errs[r.name+" "+t]; ok {
				line += " fail: " + lspEsc(e) + " |"
			} else if e, ok := errs[r.name]; ok {
				line += " fail: " + lspEsc(e) + " |"
			} else {
				line += " not measured |"
			}
		}
		if s, ok := sizes[r.name]["linux/amd64"]; ok && noop > 0 {
			line += fmt.Sprintf(" %+d |", s-noop)
		} else {
			line += " — |"
		}
		b.WriteString(line + "\n")
	}
	b.WriteString("\n## Subprocess providers and servers: runtime + library on disk\n\n")
	b.WriteString("Not shippable in the engine's release artefact (one static Go binary): each needs a runtime the host must provide. Sizes are `du` of the scratch install (bytes, apparent size); the runtime row is the host's.\n\n")
	b.WriteString("| provider / server | runtime | library on disk | runtime on disk |\n|---|---|---|---|\n")
	sz := func(p string) string {
		if p == "" {
			return "not measured"
		}
		if n := dirSize(p); n > 0 {
			return fmt.Sprintf("%.1f MB (`%s`)", float64(n)/1e6, filepath.Base(p))
		}
		return "not measured"
	}
	envDir := func(k string, up int) string {
		v := os.Getenv(k)
		if v == "" {
			return ""
		}
		for range up {
			v = filepath.Dir(v)
		}
		return v
	}
	nm := func(env, pkg string) string {
		if v := os.Getenv(env); v != "" {
			return filepath.Join(v, pkg)
		}
		return ""
	}
	// CPython here is the system install (python3 on PATH may be a wrapper):
	// its size is not attributable to one provider, so it is not measured.
	pyRuntime := ""
	// The node binary itself: its install dir also holds globally installed
	// npm packages, which are not the runtime's footprint.
	nodeRuntime := ""
	if p, err := exec.LookPath("node"); err == nil {
		if r, err := filepath.EvalSymlinks(p); err == nil {
			nodeRuntime = r
		}
	}
	javaRuntime := hostDir("java", 2)
	pyNote := "host CPython (system install; not measured)"
	if pyRuntime != "" {
		pyNote = sz(pyRuntime)
	}
	fmt.Fprintf(&b, "| pygments | CPython (%s) | %s | %s |\n", toolVersion(envOr("T1954_PYGMENTS_PYTHON", "python3"), "--version"), sz(filepath.Join(envDir("T1954_PYGMENTS_PYTHON", 2), "lib")), pyNote)
	fmt.Fprintf(&b, "| pytokenize (t1954_1) | CPython | standard library only | %s |\n", pyNote)
	fmt.Fprintf(&b, "| tsnative | Node.js (%s) | %s | %s |\n", toolVersion("node", "--version"), sz(nm("T1954_TS_NODE_MODULES", "typescript")), sz(nodeRuntime))
	fmt.Fprintf(&b, "| textmate | Node.js | %s + %s + %s | %s |\n", sz(nm("T1954_TM_NODE_MODULES", "vscode-textmate")), sz(nm("T1954_TM_NODE_MODULES", "vscode-oniguruma")), sz(nm("T1954_TM_NODE_MODULES", "tm-grammars")), sz(nodeRuntime))
	kclib := envDir("T1954_KOTLINC", 2)
	if kclib != "" {
		kclib = filepath.Join(kclib, "lib")
	}
	fmt.Fprintf(&b, "| ktpsi | JVM (%s) | kotlin-compiler.jar + stdlib + coroutines: %s | %s |\n", toolVersion("java", "-version"), jarSizes(kclib, "kotlin-compiler.jar", "kotlin-stdlib.jar", "kotlinx-coroutines-core-jvm.jar"), sz(javaRuntime))
	fmt.Fprintf(&b, "| LSP: gopls | native binary | %s | — |\n", sz(os.Getenv("T1954_GOPLS")))
	fmt.Fprintf(&b, "| LSP: pyright | Node.js | %s | %s |\n", sz(nm("T1954_LSP_NODE_MODULES", "pyright")), sz(nodeRuntime))
	fmt.Fprintf(&b, "| LSP: typescript-language-server | Node.js | %s + typescript %s | %s |\n", sz(nm("T1954_LSP_NODE_MODULES", "typescript-language-server")), sz(nm("T1954_LSP_NODE_MODULES", "typescript")), sz(nodeRuntime))
	fmt.Fprintf(&b, "| LSP: kotlin-lsp | bundled JBR | %s (includes its JBR) | — |\n", sz(envDir("T1954_KOTLIN_LSP", 1)))
	if err := os.WriteFile(*out, []byte(b.String()), 0o644); err != nil {
		fail(1, err)
	}
	fmt.Printf("WROTE:%s\n", *out)
	return 0
}

// hostDir: the install directory of a PATH tool, `up` levels above the
// resolved binary (e.g. …/node/25.2.1/bin/node -> …/node/25.2.1).
func hostDir(tool string, up int) string {
	p, err := exec.LookPath(tool)
	if err != nil {
		return ""
	}
	if r, err := filepath.EvalSymlinks(p); err == nil {
		p = r
	}
	for range up {
		p = filepath.Dir(p)
	}
	if p == "/" || p == "/usr" {
		return "" // a system prefix is not one runtime's footprint
	}
	return p
}

func envOr(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}

func toolVersion(tool string, flag string) string {
	o, err := exec.Command(tool, flag).CombinedOutput()
	if err != nil {
		return "not found"
	}
	return strings.TrimSpace(firstLine(string(o)))
}

func jarSizes(dir string, jars ...string) string {
	if dir == "" {
		return "not measured"
	}
	var n int64
	for _, j := range jars {
		st, err := os.Stat(filepath.Join(dir, j))
		if err != nil {
			return "not measured"
		}
		n += st.Size()
	}
	return fmt.Sprintf("%.1f MB", float64(n)/1e6)
}
