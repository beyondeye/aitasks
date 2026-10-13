package provider

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
)

func init() { register("pytokenize", func() (Provider, error) { return NewPyTokenize() }) }

// PyTokenize is Python's own tokenize + ast (oracle/py_oracle.py) as a
// provider, run as one long-lived subprocess. It fills DocInfo from ast end
// positions plus tokenize STRING tokens.
type PyTokenize struct {
	mu      sync.Mutex
	cmd     *exec.Cmd
	in      io.WriteCloser
	out     *bufio.Reader
	Version string
}

// PyOracleScript locates oracle/py_oracle.py (the harness runs from the
// research dir).
func PyOracleScript() string { return filepath.Join("oracle", "py_oracle.py") }

// NewPyTokenize starts the oracle process.
func NewPyTokenize() (*PyTokenize, error) {
	py := os.Getenv("T1954_PYTHON")
	if py == "" {
		py = "python3"
	}
	cmd := exec.Command(py, PyOracleScript())
	in, err := cmd.StdinPipe()
	if err != nil {
		return nil, err
	}
	outp, err := cmd.StdoutPipe()
	if err != nil {
		return nil, err
	}
	cmd.Stderr = os.Stderr
	if err := cmd.Start(); err != nil {
		return nil, fmt.Errorf("pytokenize: %w", err)
	}
	p := &PyTokenize{cmd: cmd, in: in, out: bufio.NewReaderSize(outp, 1<<20)}
	var v struct{ Version string }
	if err := p.call(map[string]any{"version": true}, &v); err != nil {
		p.Close()
		return nil, err
	}
	p.Version = v.Version
	return p, nil
}

func (p *PyTokenize) call(req any, resp any) error {
	p.mu.Lock()
	defer p.mu.Unlock()
	b, err := json.Marshal(req)
	if err != nil {
		return err
	}
	if _, err := p.in.Write(append(b, '\n')); err != nil {
		return fmt.Errorf("pytokenize: write: %w", err)
	}
	line, err := p.out.ReadBytes('\n')
	if err != nil {
		return fmt.Errorf("pytokenize: read: %w", err)
	}
	return json.Unmarshal(line, resp)
}

// Close stops the oracle process.
func (p *PyTokenize) Close() error {
	if p.in != nil {
		p.in.Close()
	}
	if p.cmd != nil && p.cmd.Process != nil {
		return p.cmd.Wait()
	}
	return nil
}

func (*PyTokenize) Name() string    { return "pytokenize" }
func (*PyTokenize) Langs() []string { return []string{"python"} }
func (*PyTokenize) Caps(string) Capabilities {
	return Capabilities{TokenRanges: true, Errors: true, DocLiterals: true}
}

type pyResp struct {
	Spans [][3]any `json:"spans"`
	Diags [][3]any `json:"diags"`
	Doc   *struct {
		Literals [][3]any `json:"literals"`
		StmtEnd  int      `json:"stmt_end"`
	} `json:"doc"`
	Error string `json:"error"`
}

func num(v any) int {
	f, _ := v.(float64)
	return int(f)
}

// Analyze runs tokenize + ast on src.
func (p *PyTokenize) Analyze(_ string, src []byte) (Result, error) {
	var r pyResp
	if err := p.call(map[string]string{"src": base64.StdEncoding.EncodeToString(src)}, &r); err != nil {
		return Result{}, err
	}
	if r.Error != "" {
		return Result{}, errors.New("py_oracle: " + r.Error)
	}
	var res Result
	for _, s := range r.Spans {
		k := String
		if s[2] == "comment" {
			k = LineComment
		}
		res.Spans = append(res.Spans, Span{num(s[0]), num(s[1]), k})
	}
	for _, d := range r.Diags {
		reason, _ := d[2].(string)
		res.Diags = append(res.Diags, Diag{num(d[0]), num(d[1]), reason})
	}
	if r.Doc != nil {
		info := &DocInfo{StmtEnd: r.Doc.StmtEnd}
		for _, l := range r.Doc.Literals {
			raw, _ := l[2].(bool)
			info.Literals = append(info.Literals, DocLiteral{num(l[0]), num(l[1]), raw})
		}
		res.Doc = info
	}
	return res, nil
}
