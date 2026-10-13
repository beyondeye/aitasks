// Package oracle returns native-tool comment ranges per language, for the
// range level: go/scanner (Go), Python tokenize (Python), mvdan/sh (bash) and
// the parser-aware TypeScript extractor (TS/JS, only when its self-test has
// passed and T1954_TS_NODE_MODULES points at the scratch node_modules).
// Languages without one return name "" — "no native oracle", never an empty
// result.
package oracle

import (
	"bufio"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"sync"

	"github.com/beyondeye/aitasks/goengines/t1954research/provider"
)

var (
	mu sync.Mutex
	py *provider.PyTokenize
	ts *tsProc
)

// Comments returns the comment spans of src (the file named name) per the
// language's native oracle, and the oracle's name ("" = none for this
// language). The name matters: TypeScript's script kind (.ts / .tsx / .js /
// .jsx) changes the parse — `<number>x` is a type assertion in .ts and JSX
// in .tsx.
func Comments(name, lang string, src []byte) ([]provider.Span, string, error) {
	switch lang {
	case "go":
		res, err := provider.GoScanner{}.Analyze(lang, src)
		return comments(res), "goscanner", err
	case "bash":
		res, err := provider.Shfmt{}.Analyze(lang, src)
		if err == nil && len(res.Diags) > 0 {
			err = errors.New("shfmt cannot parse: " + res.Diags[0].Reason)
		}
		return comments(res), "shfmt", err
	case "python":
		mu.Lock()
		if py == nil {
			p, err := provider.NewPyTokenize()
			if err != nil {
				mu.Unlock()
				return nil, "pytokenize", err
			}
			py = p
		}
		p := py
		mu.Unlock()
		res, err := p.Analyze(lang, src)
		return comments(res), "pytokenize", err
	case "typescript", "tsx", "javascript":
		t, err := tsOracle()
		if err != nil || t == nil {
			return nil, "", err
		}
		sp, err := t.comments(name, lang, src)
		return sp, "ts-parser", err
	}
	return nil, "", nil
}

func comments(r provider.Result) []provider.Span {
	var out []provider.Span
	for _, s := range r.Spans {
		if s.Kind == provider.LineComment || s.Kind == provider.BlockComment {
			out = append(out, s)
		}
	}
	return out
}

// Close stops oracle subprocesses.
func Close() {
	mu.Lock()
	defer mu.Unlock()
	if py != nil {
		py.Close()
		py = nil
	}
	if ts != nil {
		ts.close()
		ts = nil
	}
}

type tsProc struct {
	cmd *exec.Cmd
	in  io.WriteCloser
	out *bufio.Reader
}

// TSAvailable reports whether the TypeScript oracle can run, and why not.
func TSAvailable() (bool, string) {
	nm := os.Getenv("T1954_TS_NODE_MODULES")
	if nm == "" {
		return false, "T1954_TS_NODE_MODULES not set"
	}
	if _, err := os.Stat(filepath.Join(nm, "typescript", "package.json")); err != nil {
		return false, "typescript not installed in " + nm
	}
	return true, ""
}

func tsOracle() (*tsProc, error) {
	mu.Lock()
	defer mu.Unlock()
	if ts != nil {
		return ts, nil
	}
	if ok, _ := TSAvailable(); !ok {
		return nil, nil
	}
	cmd := exec.Command("node", filepath.Join("oracle", "ts_oracle.js"), "--serve")
	cmd.Env = append(os.Environ(), "NODE_PATH="+os.Getenv("T1954_TS_NODE_MODULES"))
	in, err := cmd.StdinPipe()
	if err != nil {
		return nil, err
	}
	out, err := cmd.StdoutPipe()
	if err != nil {
		return nil, err
	}
	cmd.Stderr = os.Stderr
	if err := cmd.Start(); err != nil {
		return nil, fmt.Errorf("ts oracle: %w", err)
	}
	ts = &tsProc{cmd: cmd, in: in, out: bufio.NewReaderSize(out, 1<<20)}
	return ts, nil
}

func (t *tsProc) comments(name, lang string, src []byte) ([]provider.Span, error) {
	if name == "" {
		return nil, errors.New("ts oracle: a file name is required (it selects the script kind)")
	}
	req, _ := json.Marshal(map[string]string{"name": name, "lang": lang, "src": base64.StdEncoding.EncodeToString(src)})
	mu.Lock()
	defer mu.Unlock()
	if _, err := t.in.Write(append(req, '\n')); err != nil {
		return nil, err
	}
	line, err := t.out.ReadBytes('\n')
	if err != nil {
		return nil, err
	}
	var r struct {
		Comments [][2]int `json:"comments"`
		Error    string   `json:"error"`
	}
	if err := json.Unmarshal(line, &r); err != nil {
		return nil, err
	}
	if r.Error != "" {
		return nil, errors.New(r.Error)
	}
	var out []provider.Span
	for _, c := range r.Comments {
		out = append(out, provider.Span{Start: c[0], End: c[1], Kind: provider.LineComment})
	}
	return out, nil
}

func (t *tsProc) close() {
	t.in.Close()
	_ = t.cmd.Wait()
}
