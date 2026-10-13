package main

// lsp: does a language server expose comment locations (semantic tokens of
// type `comment`, folding ranges of kind `comment`)? One experiment per
// server, installed into a scratch dir (never system-wide), driven through a
// protocol-correct lifecycle (t1954_3 plan, step 7):
//
//   initialize (capability negotiation: position encodings, semantic tokens
//   with `comment` in tokenTypes, folding kinds, workspace/configuration,
//   workDoneProgress, per-server initializationOptions) → initialized →
//   answer every server→client request → wait for readiness (progress end /
//   quiet period, bounded) → controls → per-fixture didOpen + one request per
//   ADVERTISED feature + didClose → shutdown / exit.
//
// Controls run on a known-good file in a valid per-server project:
//   - readiness (shared): documentSymbol names the known function;
//   - semanticTokens (only if advertised): a token at the known identifier;
//   - foldingRange (only if advertised): the known function-body fold.
// The two feature controls are independent; a failed one makes only its own
// feature `inconclusive`. Outcomes are kept apart: measured, not advertised,
// inconclusive, setup failed, not measured. Only measured rows are evidence.

import (
	"bufio"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
	"unicode/utf8"

	"github.com/beyondeye/aitasks/goengines/t1954research/internal/corpus"
	"github.com/beyondeye/aitasks/goengines/t1954research/internal/oracle"
	"github.com/beyondeye/aitasks/goengines/t1954research/provider"
)

func init() { extraVerbs["lsp"] = cmdLSP }

type rpcMsg struct {
	ID     json.RawMessage `json:"id,omitempty"`
	Method string          `json:"method,omitempty"`
	Params json.RawMessage `json:"params,omitempty"`
	Result json.RawMessage `json:"result,omitempty"`
	Error  *struct {
		Code    int    `json:"code"`
		Message string `json:"message"`
	} `json:"error,omitempty"`
}

type lspClient struct {
	name    string
	cmd     *exec.Cmd
	in      io.WriteCloser
	wmu     sync.Mutex
	mu      sync.Mutex
	next    int
	pending map[string]chan rpcMsg
	config  func(section string) any
	// observed notifications
	progressOpen map[string]bool
	lastNote     time.Time
	diagFiles    map[string]int // uri -> diagnostics count (latest publish)
	unknownReqs  []string
	stderr       *strings.Builder
}

func startLSP(name string, argv []string, dir string, config func(string) any) (*lspClient, error) {
	cmd := exec.Command(argv[0], argv[1:]...)
	cmd.Dir = dir
	in, err := cmd.StdinPipe()
	if err != nil {
		return nil, err
	}
	out, err := cmd.StdoutPipe()
	if err != nil {
		return nil, err
	}
	var se strings.Builder
	cmd.Stderr = &limitedWriter{b: &se, n: 1 << 16}
	if err := cmd.Start(); err != nil {
		return nil, err
	}
	c := &lspClient{name: name, cmd: cmd, in: in, pending: map[string]chan rpcMsg{}, config: config,
		progressOpen: map[string]bool{}, diagFiles: map[string]int{}, stderr: &se, lastNote: time.Now()}
	go c.read(bufio.NewReaderSize(out, 1<<20))
	return c, nil
}

type limitedWriter struct {
	b *strings.Builder
	n int
}

func (w *limitedWriter) Write(p []byte) (int, error) {
	if w.b.Len() < w.n {
		w.b.Write(p)
	}
	return len(p), nil
}

func (c *lspClient) write(m any) error {
	b, err := json.Marshal(m)
	if err != nil {
		return err
	}
	c.wmu.Lock()
	defer c.wmu.Unlock()
	_, err = fmt.Fprintf(c.in, "Content-Length: %d\r\n\r\n%s", len(b), b)
	return err
}

func (c *lspClient) read(r *bufio.Reader) {
	for {
		n := -1
		for {
			line, err := r.ReadString('\n')
			if err != nil {
				c.failAll()
				return
			}
			line = strings.TrimRight(line, "\r\n")
			if line == "" {
				break
			}
			if k, v, ok := strings.Cut(line, ":"); ok && strings.EqualFold(strings.TrimSpace(k), "Content-Length") {
				n, _ = strconv.Atoi(strings.TrimSpace(v))
			}
		}
		if n < 0 {
			continue
		}
		buf := make([]byte, n)
		if _, err := io.ReadFull(r, buf); err != nil {
			c.failAll()
			return
		}
		var m rpcMsg
		if json.Unmarshal(buf, &m) != nil {
			continue
		}
		switch {
		case m.Method != "" && len(m.ID) > 0:
			c.answer(m)
		case m.Method != "":
			c.note(m)
		default:
			c.mu.Lock()
			ch := c.pending[string(m.ID)]
			delete(c.pending, string(m.ID))
			c.mu.Unlock()
			if ch != nil {
				ch <- m
			}
		}
	}
}

func (c *lspClient) failAll() {
	c.mu.Lock()
	defer c.mu.Unlock()
	for k, ch := range c.pending {
		close(ch)
		delete(c.pending, k)
	}
}

// answer replies to a server→client request.
func (c *lspClient) answer(m rpcMsg) {
	var result any
	switch m.Method {
	case "workspace/configuration":
		var p struct {
			Items []struct {
				Section string `json:"section"`
			} `json:"items"`
		}
		_ = json.Unmarshal(m.Params, &p)
		out := make([]any, len(p.Items))
		for i, it := range p.Items {
			out[i] = c.config(it.Section)
		}
		result = out
	case "client/registerCapability", "client/unregisterCapability", "window/workDoneProgress/create",
		"window/showMessageRequest", "workspace/workspaceFolders":
		result = nil
		if m.Method == "workspace/workspaceFolders" {
			result = []any{}
		}
	default:
		c.mu.Lock()
		c.unknownReqs = append(c.unknownReqs, m.Method)
		c.mu.Unlock()
		_ = c.write(map[string]any{"jsonrpc": "2.0", "id": m.ID, "error": map[string]any{"code": -32601, "message": "method not found"}})
		return
	}
	_ = c.write(map[string]any{"jsonrpc": "2.0", "id": m.ID, "result": result})
}

func (c *lspClient) note(m rpcMsg) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.lastNote = time.Now()
	switch m.Method {
	case "$/progress":
		var p struct {
			Token json.RawMessage `json:"token"`
			Value struct {
				Kind string `json:"kind"`
			} `json:"value"`
		}
		if json.Unmarshal(m.Params, &p) == nil {
			switch p.Value.Kind {
			case "begin":
				c.progressOpen[string(p.Token)] = true
			case "end":
				delete(c.progressOpen, string(p.Token))
			}
		}
	case "textDocument/publishDiagnostics":
		var p struct {
			URI         string            `json:"uri"`
			Diagnostics []json.RawMessage `json:"diagnostics"`
		}
		if json.Unmarshal(m.Params, &p) == nil {
			c.diagFiles[p.URI] = len(p.Diagnostics)
		}
	}
}

var errTimeout = errors.New("timeout")

func (c *lspClient) request(method string, params any, timeout time.Duration) (json.RawMessage, error) {
	c.mu.Lock()
	c.next++
	id := strconv.Itoa(c.next)
	ch := make(chan rpcMsg, 1)
	c.pending[id] = ch
	c.mu.Unlock()
	if err := c.write(map[string]any{"jsonrpc": "2.0", "id": c.next, "method": method, "params": params}); err != nil {
		return nil, err
	}
	select {
	case m, ok := <-ch:
		if !ok {
			return nil, errors.New("server exited")
		}
		if m.Error != nil {
			return nil, fmt.Errorf("%s: error %d %s", method, m.Error.Code, m.Error.Message)
		}
		return m.Result, nil
	case <-time.After(timeout):
		c.mu.Lock()
		delete(c.pending, id)
		c.mu.Unlock()
		return nil, fmt.Errorf("%s: %w after %s", method, errTimeout, timeout)
	}
}

func (c *lspClient) notify(method string, params any) error {
	return c.write(map[string]any{"jsonrpc": "2.0", "method": method, "params": params})
}

// waitReady: every started progress has ended and the server has been quiet
// for `quiet`, bounded by `max`.
func (c *lspClient) waitReady(quiet, max time.Duration) time.Duration {
	start := time.Now()
	for time.Since(start) < max {
		c.mu.Lock()
		open := len(c.progressOpen)
		idle := time.Since(c.lastNote)
		c.mu.Unlock()
		if open == 0 && idle >= quiet {
			break
		}
		time.Sleep(100 * time.Millisecond)
	}
	return time.Since(start)
}

func (c *lspClient) stop() {
	_, _ = c.request("shutdown", nil, 10*time.Second)
	_ = c.notify("exit", nil)
	done := make(chan struct{})
	go func() { _ = c.cmd.Wait(); close(done) }()
	select {
	case <-done:
	case <-time.After(10 * time.Second):
		_ = c.cmd.Process.Kill()
		<-done
	}
}

// ---- servers ----

type lspServer struct {
	name, lang string
	argv       func() ([]string, error) // nil error = obtainable
	initOpts   any
	config     func(section string) any
	exts       []string // corpus fixtures it serves, by extension
	project    func(dir string) error
	control    string // control file name
	controlSrc string
	knownFn    string // function documentSymbol must name
	knownLine  int    // 0-based line of the known identifier (semantic-token control)
	foldLine   int    // 0-based start line of the known function-body fold
	runtime    string
	installDir func() string
}

func lspServers() []lspServer {
	nm := os.Getenv("T1954_LSP_NODE_MODULES")
	writeFiles := func(dir string, files map[string]string) error {
		for n, s := range files {
			if err := os.MkdirAll(filepath.Dir(filepath.Join(dir, n)), 0o755); err != nil {
				return err
			}
			if err := os.WriteFile(filepath.Join(dir, n), []byte(s), 0o644); err != nil {
				return err
			}
		}
		return nil
	}
	need := func(env, what string) func() ([]string, error) {
		return func() ([]string, error) { return nil, fmt.Errorf("%s not set (%s)", env, what) }
	}
	gopls := need("T1954_GOPLS", "the gopls binary")
	if p := os.Getenv("T1954_GOPLS"); p != "" {
		gopls = func() ([]string, error) { return []string{p}, nil }
	}
	pyright := need("T1954_LSP_NODE_MODULES", "node_modules with pyright")
	tsls := need("T1954_LSP_NODE_MODULES", "node_modules with typescript-language-server and typescript")
	if nm != "" {
		pyright = func() ([]string, error) {
			return []string{"node", filepath.Join(nm, "pyright", "langserver.index.js"), "--stdio"}, nil
		}
		tsls = func() ([]string, error) {
			return []string{"node", filepath.Join(nm, "typescript-language-server", "lib", "cli.mjs"), "--stdio"}, nil
		}
	}
	klsp := need("T1954_KOTLIN_LSP", "the kotlin-lsp.sh of the standalone archive")
	if p := os.Getenv("T1954_KOTLIN_LSP"); p != "" {
		klsp = func() ([]string, error) { return []string{p, "--stdio"}, nil }
	}
	none := func(string) any { return nil }
	return []lspServer{
		{name: "gopls", lang: "go", argv: gopls, initOpts: map[string]any{"semanticTokens": true},
			config: func(s string) any { return map[string]any{"semanticTokens": true} },
			exts:   []string{".go"},
			project: func(d string) error {
				return writeFiles(d, map[string]string{"go.mod": "module lspprobe\n\ngo 1.22\n"})
			},
			control: "control/control.go", controlSrc: "package control\n\n/*\nblock comment\nline two\n*/\nfunc Known() int {\n\tx := 1\n\treturn x\n}\n",
			knownFn: "Known", knownLine: 6, foldLine: 6, runtime: "native binary (Go)",
			installDir: func() string { return os.Getenv("T1954_GOPLS") }},
		{name: "pyright", lang: "python", argv: pyright, config: none, exts: []string{".py"},
			project: func(d string) error {
				return writeFiles(d, map[string]string{"pyrightconfig.json": "{}\n"})
			},
			control: "control.py", controlSrc: "\"\"\"doc\"\"\"\n# comment one\n# comment two\ndef known():\n    x = 1\n    return x\n",
			knownFn: "known", knownLine: 3, foldLine: 3, runtime: "Node.js",
			installDir: func() string { return filepath.Join(nm, "pyright") }},
		{name: "typescript-language-server", lang: "typescript", argv: tsls,
			initOpts: map[string]any{"tsserver": map[string]any{"path": filepath.Join(nm, "typescript", "lib")}},
			config:   none, exts: []string{".ts", ".tsx", ".js", ".jsx", ".mts", ".mjs"},
			project: func(d string) error {
				return writeFiles(d, map[string]string{"tsconfig.json": `{"compilerOptions":{"allowJs":true,"checkJs":false,"jsx":"preserve","noEmit":true,"target":"es2022","module":"esnext"},"include":["**/*"]}` + "\n"})
			},
			control: "control.ts", controlSrc: "/*\nblock comment\nline two\n*/\nexport function known(): number {\n  const x = 1;\n  return x;\n}\n",
			knownFn: "known", knownLine: 4, foldLine: 4, runtime: "Node.js + typescript",
			installDir: func() string { return filepath.Join(nm, "typescript-language-server") }},
		{name: "kotlin-lsp", lang: "kotlin", argv: klsp, config: none, exts: []string{".kt", ".kts"},
			project: func(d string) error { return nil },
			control: "src/main/kotlin/Control.kt", controlSrc: "/*\nblock comment\nline two\n*/\nfun known(): Int {\n    val x = 1\n    return x\n}\n",
			knownFn: "known", knownLine: 4, foldLine: 4, runtime: "JVM (bundled JBR)",
			installDir: func() string { return filepath.Dir(os.Getenv("T1954_KOTLIN_LSP")) }},
	}
}

// ---- measurement ----

type featureResult struct {
	advertised bool
	control    string // pass | fail:<why> | n/a
	outcome    string // measured | not advertised | inconclusive | setup failed | not measured
	files      int    // fixtures measured
	withComm   int    // fixtures where the server exposed >= 1 comment
	lineAgree  int    // fixtures whose comment-line set equals the hand oracle's
	fpLines    int    // look-alike lines the server reports as comment lines (semantic) / inside a comment fold
	missLines  int    // hand-oracle comment lines the server does not report
	rangeEq    int    // fixtures whose line-comment byte ranges equal the native oracle's
	rangeOf    int    // fixtures with a native oracle
	failures   []string
	details    []string // per-fixture disagreements
	firstMs    float64
}

type serverResult struct {
	s           lspServer
	status      string // measured | setup failed | not measured
	why         string
	encoding    string
	legend      []string
	initMs      float64
	readyMs     float64
	sem, fold   featureResult
	ctrlComment string // did the control file's block comment come back as a comment token / fold?
	diagFiles   int
	malformed   int
	unknownReqs []string
	installSize int64
}

func cmdLSP(args []string) int {
	fs := flag.NewFlagSet("lsp", flag.ExitOnError)
	only := fs.String("servers", "", "comma list (default: all)")
	out := fs.String("out", filepath.Join("results", "lsp.md"), "output file")
	work := fs.String("workdir", "", "scratch directory for the per-server projects (default: a temp dir)")
	_ = fs.Parse(args)
	cases, err := corpus.Load("corpus")
	if err != nil {
		fail(1, err)
	}
	defer oracle.Close()
	root := *work
	if root == "" {
		root, err = os.MkdirTemp("", "t1954-lsp-")
		if err != nil {
			fail(1, err)
		}
		defer os.RemoveAll(root)
	}
	var results []serverResult
	for _, s := range lspServers() {
		if *only != "" && !strings.Contains(","+*only+",", ","+s.name+",") {
			continue
		}
		r := runServer(s, filepath.Join(root, s.name), cases)
		fmt.Fprintf(os.Stderr, "LSP:%s|%s|%s\n", s.name, r.status, r.why)
		results = append(results, r)
	}
	if err := os.WriteFile(*out, []byte(lspReport(results)), 0o644); err != nil {
		fail(1, err)
	}
	fmt.Printf("WROTE:%s\n", *out)
	return 0
}

func runServer(s lspServer, dir string, cases []corpus.Case) serverResult {
	r := serverResult{s: s, sem: featureResult{outcome: "not measured", control: "n/a"}, fold: featureResult{outcome: "not measured", control: "n/a"}}
	argv, err := s.argv()
	if err != nil {
		r.status, r.why = "not measured", err.Error()
		return r
	}
	r.installSize = dirSize(s.installDir())
	_ = os.RemoveAll(dir)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		r.status, r.why = "setup failed", err.Error()
		return r
	}
	if err := s.project(dir); err != nil {
		r.status, r.why = "setup failed", "project: "+err.Error()
		return r
	}
	// the fixtures this server serves, one directory each (a malformed file
	// or a clashing package clause cannot break its neighbours)
	var mine []corpus.Case
	files := map[string]string{s.control: s.controlSrc}
	paths := map[string]string{}
	for _, c := range cases {
		if !contains(s.exts, c.Ext()) {
			continue
		}
		mine = append(mine, c)
		rel := filepath.Join("fx", strings.TrimSuffix(c.Name, c.Ext()), c.Name)
		if s.name == "kotlin-lsp" {
			rel = filepath.Join("src", "main", "kotlin", "fx", strings.TrimSuffix(c.Name, c.Ext()), c.Name)
		}
		paths[c.Lang+"/"+c.Name] = rel
		files[rel] = string(c.Data)
	}
	for rel, data := range files {
		p := filepath.Join(dir, rel)
		_ = os.MkdirAll(filepath.Dir(p), 0o755)
		if err := os.WriteFile(p, []byte(data), 0o644); err != nil {
			r.status, r.why = "setup failed", err.Error()
			return r
		}
	}
	cfg := s.config
	if cfg == nil {
		cfg = func(string) any { return nil }
	}
	t0 := time.Now()
	c, err := startLSP(s.name, argv, dir, cfg)
	if err != nil {
		r.status, r.why = "setup failed", "start: "+err.Error()
		return r
	}
	defer c.stop()
	rootURI := "file://" + dir
	tokenTypes := []string{"namespace", "type", "class", "enum", "interface", "struct", "typeParameter", "parameter",
		"variable", "property", "enumMember", "event", "function", "method", "macro", "keyword", "modifier", "comment",
		"string", "number", "regexp", "operator", "decorator", "label"}
	initParams := map[string]any{
		"processId": os.Getpid(), "rootUri": rootURI, "rootPath": dir,
		"workspaceFolders": []any{map[string]any{"uri": rootURI, "name": "t1954"}},
		"capabilities": map[string]any{
			"general":   map[string]any{"positionEncodings": []string{"utf-8", "utf-16"}},
			"window":    map[string]any{"workDoneProgress": true},
			"workspace": map[string]any{"configuration": true, "workspaceFolders": true},
			"textDocument": map[string]any{
				"synchronization":    map[string]any{"didSave": false},
				"documentSymbol":     map[string]any{"hierarchicalDocumentSymbolSupport": true},
				"publishDiagnostics": map[string]any{},
				"semanticTokens": map[string]any{
					"requests": map[string]any{"full": true}, "tokenTypes": tokenTypes,
					"tokenModifiers": []string{"declaration", "definition", "readonly", "static", "deprecated", "documentation", "defaultLibrary"},
					"formats":        []string{"relative"}, "multilineTokenSupport": true, "overlappingTokenSupport": false,
				},
				"foldingRange": map[string]any{"lineFoldingOnly": false,
					"foldingRangeKind": map[string]any{"valueSet": []string{"comment", "imports", "region"}}},
			},
		},
	}
	if s.initOpts != nil {
		initParams["initializationOptions"] = s.initOpts
	}
	res, err := c.request("initialize", initParams, 120*time.Second)
	if err != nil {
		r.status, r.why = "setup failed", "initialize: "+err.Error()+stderrTail(c)
		return r
	}
	r.initMs = msDur(time.Since(t0))
	var ir struct {
		Capabilities struct {
			PositionEncoding       string          `json:"positionEncoding"`
			SemanticTokensProvider json.RawMessage `json:"semanticTokensProvider"`
			FoldingRangeProvider   json.RawMessage `json:"foldingRangeProvider"`
			DocumentSymbolProvider json.RawMessage `json:"documentSymbolProvider"`
		} `json:"capabilities"`
	}
	_ = json.Unmarshal(res, &ir)
	r.encoding = ir.Capabilities.PositionEncoding
	if r.encoding == "" {
		r.encoding = "utf-16"
	}
	if adv(ir.Capabilities.SemanticTokensProvider) {
		var st struct {
			Legend struct {
				TokenTypes []string `json:"tokenTypes"`
			} `json:"legend"`
		}
		_ = json.Unmarshal(ir.Capabilities.SemanticTokensProvider, &st)
		r.legend = st.Legend.TokenTypes
		r.sem.advertised = true
	}
	r.fold.advertised = adv(ir.Capabilities.FoldingRangeProvider)
	_ = c.notify("initialized", map[string]any{})
	open := func(rel string, data []byte) string {
		uri := "file://" + filepath.Join(dir, rel)
		_ = c.notify("textDocument/didOpen", map[string]any{"textDocument": map[string]any{
			"uri": uri, "languageId": langID(rel), "version": 1, "text": string(data)}})
		return uri
	}
	tReady := time.Now()
	c.waitReady(2*time.Second, 120*time.Second)
	// readiness control: documentSymbol on the control file names the known function
	curi := open(s.control, []byte(s.controlSrc))
	ready := false
	var lastErr string
	for deadline := time.Now().Add(120 * time.Second); time.Now().Before(deadline); time.Sleep(2 * time.Second) {
		raw, err := c.request("textDocument/documentSymbol", map[string]any{"textDocument": map[string]any{"uri": curi}}, 30*time.Second)
		if err != nil {
			lastErr = err.Error()
			continue
		}
		if strings.Contains(string(raw), `"`+s.knownFn+`"`) || strings.Contains(string(raw), s.knownFn+"(") {
			ready = true
			break
		}
		lastErr = "documentSymbol did not name " + s.knownFn + ": " + clipStr(string(raw), 120)
	}
	r.readyMs = msDur(time.Since(tReady))
	ctrl := []byte(s.controlSrc)
	if !ready {
		r.status, r.why = "measured", "readiness control failed: "+lastErr
		for _, f := range []*featureResult{&r.sem, &r.fold} {
			if f.advertised {
				f.outcome, f.control = "inconclusive", "fail:readiness"
			} else {
				f.outcome = "not advertised"
			}
		}
		return r
	}
	// feature controls (independent)
	if r.sem.advertised {
		toks, err := semTokens(c, curi, r.legend, ctrl, r.encoding, 30*time.Second)
		switch {
		case err != nil:
			r.sem.control = "fail:" + err.Error()
		case !tokenOnLine(toks, s.knownLine):
			r.sem.control = fmt.Sprintf("fail:no token on line %d", s.knownLine+1)
		default:
			r.sem.control = "pass"
			n := 0
			for _, t := range toks {
				if t.typ == "comment" {
					n++
				}
			}
			r.ctrlComment = fmt.Sprintf("semanticTokens: %d comment token(s) for the control's block comment", n)
		}
	} else {
		r.sem.outcome = "not advertised"
	}
	if r.fold.advertised {
		folds, err := foldings(c, curi, 30*time.Second)
		switch {
		case err != nil:
			r.fold.control = "fail:" + err.Error()
		case !foldAt(folds, s.foldLine):
			r.fold.control = fmt.Sprintf("fail:no fold starting on line %d", s.foldLine+1)
		default:
			r.fold.control = "pass"
			n := 0
			for _, f := range folds {
				if f.Kind == "comment" {
					n++
				}
			}
			r.ctrlComment += fmt.Sprintf("; foldingRange: %d comment fold(s) for it", n)
		}
	} else {
		r.fold.outcome = "not advertised"
	}
	for _, f := range []*featureResult{&r.sem, &r.fold} {
		if f.advertised {
			if f.control == "pass" {
				f.outcome = "measured"
			} else {
				f.outcome = "inconclusive"
			}
		}
	}
	r.status = "measured"
	// fixtures
	for _, cs := range mine {
		data := cs.Data
		if !utf8.Valid(data) {
			continue
		}
		if cs.Exp.Uncertain {
			r.malformed++
		}
		uri := open(paths[cs.Lang+"/"+cs.Name], data)
		l, _ := provider.LangOfPath(cs.Name, data)
		want := map[int]bool{}
		for _, n := range cs.Exp.Comments {
			want[n] = true
		}
		look := map[int]bool{}
		for _, n := range cs.Exp.Lookalikes {
			look[n] = true
		}
		starts := provider.LineStarts(data)
		if r.sem.outcome == "measured" {
			t := time.Now()
			toks, err := semTokens(c, uri, r.legend, data, r.encoding, 30*time.Second)
			if r.sem.firstMs == 0 {
				r.sem.firstMs = msDur(time.Since(t))
			}
			if err != nil {
				r.sem.failures = append(r.sem.failures, cs.Lang+"/"+cs.Name+": "+err.Error())
			} else {
				var comm []provider.Span
				for _, tk := range toks {
					if tk.typ == "comment" {
						comm = append(comm, provider.Span{Start: tk.start, End: tk.end, Kind: provider.LineComment})
					}
				}
				r.sem.files++
				if len(comm) > 0 {
					r.sem.withComm++
				}
				got := commentLines(data, starts, comm, l.Leader)
				scoreLines(&r.sem, cs.Lang+"/"+cs.Name, got, want, look)
				if spans, name, err := oracle.Comments(cs.Name, cs.Lang, data); err == nil && name != "" {
					r.sem.rangeOf++
					if sameLineComments(data, comm, spans, l.Leader) {
						r.sem.rangeEq++
					}
				}
			}
		}
		if r.fold.outcome == "measured" {
			folds, err := foldings(c, uri, 30*time.Second)
			if err != nil {
				r.fold.failures = append(r.fold.failures, cs.Lang+"/"+cs.Name+": "+err.Error())
			} else {
				r.fold.files++
				any := false
				for _, f := range folds {
					if f.Kind != "comment" {
						continue
					}
					any = true
					var fp []int
					for n := f.StartLine; n <= f.EndLine; n++ {
						if look[n+1] {
							r.fold.fpLines++
							fp = append(fp, n+1)
						}
					}
					if len(fp) > 0 {
						r.fold.details = append(r.fold.details, fmt.Sprintf("%s/%s: comment fold lines %d-%d covers look-alike lines %v", cs.Lang, cs.Name, f.StartLine+1, f.EndLine+1, fp))
					}
				}
				if any {
					r.fold.withComm++
				}
			}
		}
		_ = c.notify("textDocument/didClose", map[string]any{"textDocument": map[string]any{"uri": uri}})
	}
	time.Sleep(time.Second)
	c.mu.Lock()
	for _, n := range c.diagFiles {
		if n > 0 {
			r.diagFiles++
		}
	}
	r.unknownReqs = append([]string(nil), c.unknownReqs...)
	c.mu.Unlock()
	return r
}

type semTok struct {
	start, end, line int
	typ              string
}

func semTokens(c *lspClient, uri string, legend []string, data []byte, enc string, timeout time.Duration) ([]semTok, error) {
	raw, err := c.request("textDocument/semanticTokens/full", map[string]any{"textDocument": map[string]any{"uri": uri}}, timeout)
	if err != nil {
		return nil, err
	}
	var st struct {
		Data []int `json:"data"`
	}
	if string(raw) != "null" {
		if err := json.Unmarshal(raw, &st); err != nil {
			return nil, err
		}
	}
	starts := provider.LineStarts(data)
	var out []semTok
	line, char := 0, 0
	for i := 0; i+4 < len(st.Data); i += 5 {
		dl, dc, length, typ := st.Data[i], st.Data[i+1], st.Data[i+2], st.Data[i+3]
		if dl > 0 {
			line += dl
			char = dc
		} else {
			char += dc
		}
		s, err := provider.LinePosition(data, starts, line, char, enc)
		if err != nil {
			return nil, fmt.Errorf("token position %d:%d: %w", line, char, err)
		}
		e, err := advance(data, s, length, enc)
		if err != nil {
			return nil, err
		}
		name := ""
		if typ < len(legend) {
			name = legend[typ]
		}
		out = append(out, semTok{start: s, end: e, line: line, typ: name})
	}
	return out, nil
}

// advance moves `n` units (in enc) forward from byte s.
func advance(data []byte, s, n int, enc string) (int, error) {
	b := s
	for n > 0 && b < len(data) {
		r, w := utf8.DecodeRune(data[b:])
		switch enc {
		case "utf-8":
			n -= w
		case "utf-32":
			n--
		default:
			if r >= 0x10000 {
				n -= 2
			} else {
				n--
			}
		}
		b += w
	}
	if n > 0 {
		return 0, fmt.Errorf("token length runs past the end of the file")
	}
	return b, nil
}

type foldRange struct {
	StartLine int    `json:"startLine"`
	EndLine   int    `json:"endLine"`
	Kind      string `json:"kind"`
}

func foldings(c *lspClient, uri string, timeout time.Duration) ([]foldRange, error) {
	raw, err := c.request("textDocument/foldingRange", map[string]any{"textDocument": map[string]any{"uri": uri}}, timeout)
	if err != nil {
		return nil, err
	}
	var out []foldRange
	if string(raw) != "null" {
		if err := json.Unmarshal(raw, &out); err != nil {
			return nil, err
		}
	}
	return out, nil
}

func tokenOnLine(toks []semTok, line int) bool {
	for _, t := range toks {
		if t.line == line {
			return true
		}
	}
	return false
}

func foldAt(folds []foldRange, line int) bool {
	for _, f := range folds {
		if f.StartLine == line {
			return true
		}
	}
	return false
}

// commentLines: lines whose first non-blank byte starts a comment token that
// begins with the leader (the ToContext Comment-class definition).
func commentLines(data []byte, starts []int, comm []provider.Span, leader string) map[int]bool {
	at := map[int]bool{}
	for _, s := range comm {
		at[s.Start] = true
	}
	out := map[int]bool{}
	for i, st := range starts {
		f := st
		for f < len(data) && (data[f] == ' ' || data[f] == '\t') {
			f++
		}
		if at[f] && strings.HasPrefix(string(data[f:]), leader) {
			out[i+1] = true
		}
	}
	return out
}

func scoreLines(f *featureResult, fixture string, got, want, look map[int]bool) {
	eq := true
	var fp, extra, miss []int
	for n := range got {
		if look[n] {
			f.fpLines++
			fp = append(fp, n)
		} else if !want[n] {
			extra = append(extra, n)
		}
		if !want[n] {
			eq = false
		}
	}
	for n := range want {
		if !got[n] {
			f.missLines++
			miss = append(miss, n)
			eq = false
		}
	}
	if eq {
		f.lineAgree++
		return
	}
	sort.Ints(fp)
	sort.Ints(extra)
	sort.Ints(miss)
	f.details = append(f.details, fmt.Sprintf("%s: FP-shaped (look-alike) lines %v, other extra lines %v, missed lines %v", fixture, fp, extra, miss))
}

// sameLineComments: the server's single-line comment tokens that start with
// the leader equal the native oracle's line comments, byte for byte.
func sameLineComments(data []byte, comm, oracleSpans []provider.Span, leader string) bool {
	key := func(spans []provider.Span) []string {
		var k []string
		for _, s := range spans {
			if s.End <= len(data) && strings.HasPrefix(string(data[s.Start:]), leader) {
				e := s.End
				for e > s.Start && (data[e-1] == '\n' || data[e-1] == '\r') {
					e--
				}
				k = append(k, fmt.Sprintf("%d-%d", s.Start, e))
			}
		}
		sort.Strings(k)
		return k
	}
	return strings.Join(key(comm), ",") == strings.Join(key(oracleSpans), ",")
}

func adv(raw json.RawMessage) bool {
	s := strings.TrimSpace(string(raw))
	return s != "" && s != "null" && s != "false"
}

func langID(rel string) string {
	switch filepath.Ext(rel) {
	case ".go":
		return "go"
	case ".py":
		return "python"
	case ".ts", ".mts":
		return "typescript"
	case ".tsx":
		return "typescriptreact"
	case ".js", ".mjs":
		return "javascript"
	case ".jsx":
		return "javascriptreact"
	case ".kt", ".kts":
		return "kotlin"
	}
	return "plaintext"
}

func contains(xs []string, x string) bool {
	for _, y := range xs {
		if y == x {
			return true
		}
	}
	return false
}

func msDur(d time.Duration) float64 { return float64(d.Microseconds()) / 1000 }

func clipStr(s string, n int) string {
	if len(s) > n {
		return s[:n] + "…"
	}
	return s
}

func stderrTail(c *lspClient) string {
	s := strings.TrimSpace(c.stderr.String())
	if s == "" {
		return ""
	}
	if len(s) > 300 {
		s = s[len(s)-300:]
	}
	return " (stderr: " + strings.ReplaceAll(s, "\n", " ") + ")"
}

func dirSize(p string) int64 {
	if p == "" {
		return 0
	}
	var n int64
	_ = filepath.Walk(p, func(_ string, fi os.FileInfo, err error) error {
		if err == nil && !fi.IsDir() {
			n += fi.Size()
		}
		return nil
	})
	return n
}

func lspReport(rs []serverResult) string {
	var b strings.Builder
	b.WriteString("# LSP experiment: do language servers expose comment locations? (t1954_3)\n\n")
	b.WriteString(id.Header() + "\n\n")
	b.WriteString("Rerun: `go run ./cmd/t1954 lsp` with `T1954_GOPLS`, `T1954_LSP_NODE_MODULES` (pyright, typescript-language-server, typescript) and `T1954_KOTLIN_LSP` set (README). Each server runs in its own scratch project, through a protocol-correct lifecycle (initialize with capability negotiation → initialized → server requests answered → readiness → controls → per-fixture requests → shutdown/exit). ")
	b.WriteString("**Only `measured` outcomes are evidence about comment support**; `inconclusive` (a failed control, a timeout or an error), `setup failed` and `not measured` say nothing about it. The two features are scored independently, each on its own control.\n\n")
	b.WriteString("Comment lines are lines whose first non-blank byte starts a comment token beginning with the language's leader — the same definition the seam's line classes use — compared with each fixture's hand oracle (`comments:`). FP-shaped = a look-alike line (testmap-shaped data) reported as a comment line, or inside a comment fold. Exact = the server's line-comment byte ranges equal the native oracle's (goscanner / pytokenize / ts-parser; none for Kotlin).\n\n")
	b.WriteString("| server | lang | status | runtime | install size | position encoding | initialize | readiness | feature | advertised | control | outcome | fixtures | with ≥1 comment | comment-line agreement | missed lines | FP-shaped lines | exact vs native | first response |\n")
	b.WriteString("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")
	for _, r := range rs {
		size := "not measured"
		if r.installSize > 0 {
			size = fmt.Sprintf("%.1f MB", float64(r.installSize)/1e6)
		}
		for i, f := range []featureResult{r.sem, r.fold} {
			feat := []string{"semanticTokens/full", "foldingRange"}[i]
			agree, miss, exact := fmt.Sprintf("%d / %d", f.lineAgree, f.files), fmt.Sprint(f.missLines), fmt.Sprintf("%d / %d", f.rangeEq, f.rangeOf)
			if i == 1 {
				agree, miss, exact = "n/a (folds cover blocks, not single lines)", "n/a", "n/a"
			}
			if f.outcome != "measured" {
				agree, miss, exact = "—", "—", "—"
			}
			first := "—"
			if f.firstMs > 0 {
				first = fmt.Sprintf("%.1f ms", f.firstMs)
			}
			b.WriteString(fmt.Sprintf("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %v | %s | %s | %d | %d | %s | %s | %d | %s | %s |\n",
				r.s.name, r.s.lang, r.status, r.s.runtime, size, r.encoding, msOr(r.initMs), msOr(r.readyMs), feat, f.advertised,
				lspEsc(f.control), f.outcome, f.files, f.withComm, agree, miss, f.fpLines, exact, first))
		}
	}
	b.WriteString("\n## Per server\n\n")
	for _, r := range rs {
		b.WriteString(fmt.Sprintf("- **%s** (%s): %s", r.s.name, r.s.lang, r.status))
		if r.why != "" {
			b.WriteString(" — " + lspEsc(r.why))
		}
		b.WriteString(".\n")
		if r.ctrlComment != "" {
			b.WriteString("  - control file (a 4-line block comment, then the known function): " + strings.TrimPrefix(r.ctrlComment, "; ") + "\n")
		}
		if len(r.legend) > 0 {
			b.WriteString(fmt.Sprintf("  - semantic token legend: %s (has `comment`: %v)\n", strings.Join(r.legend, ", "), contains(r.legend, "comment")))
		}
		if r.status == "measured" {
			b.WriteString(fmt.Sprintf("  - malformed fixtures sent: %d; files with published diagnostics (asynchronous `publishDiagnostics` only — no request returns certainty with the tokens): %d\n", r.malformed, r.diagFiles))
		}
		if len(r.unknownReqs) > 0 {
			b.WriteString("  - server requests answered MethodNotFound: " + strings.Join(r.unknownReqs, ", ") + "\n")
		}
		for _, f := range append(r.sem.failures, r.fold.failures...) {
			b.WriteString("  - request failure: " + lspEsc(f) + "\n")
		}
		for _, d := range r.sem.details {
			b.WriteString("  - semanticTokens " + lspEsc(d) + "\n")
		}
		for _, d := range r.fold.details {
			b.WriteString("  - foldingRange " + lspEsc(d) + "\n")
		}
	}
	return b.String()
}

func msOr(v float64) string {
	if v == 0 {
		return "—"
	}
	return fmt.Sprintf("%.0f ms", v)
}

func lspEsc(s string) string { return strings.NewReplacer("|", "/", "\n", " ").Replace(s) }
