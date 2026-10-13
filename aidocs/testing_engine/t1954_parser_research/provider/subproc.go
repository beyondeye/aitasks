package provider

import (
	"bufio"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/exec"
	"sync"
)

// jsonProc is a long-lived helper process speaking one JSON object per line
// (the pytokenize pattern), shared by the t1954_3 subprocess providers.
type jsonProc struct {
	name string
	mu   sync.Mutex
	cmd  *exec.Cmd
	in   io.WriteCloser
	out  *bufio.Reader
}

func startJSONProc(name string, env []string, argv ...string) (*jsonProc, error) {
	cmd := exec.Command(argv[0], argv[1:]...)
	if env != nil {
		cmd.Env = append(os.Environ(), env...)
	}
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
		return nil, fmt.Errorf("%s: %w", name, err)
	}
	return &jsonProc{name: name, cmd: cmd, in: in, out: bufio.NewReaderSize(outp, 1<<20)}, nil
}

func (p *jsonProc) call(req any, resp any) error {
	p.mu.Lock()
	defer p.mu.Unlock()
	b, err := json.Marshal(req)
	if err != nil {
		return err
	}
	if _, err := p.in.Write(append(b, '\n')); err != nil {
		return fmt.Errorf("%s: write: %w", p.name, err)
	}
	line, err := p.out.ReadBytes('\n')
	if err != nil {
		return fmt.Errorf("%s: read: %w", p.name, err)
	}
	return json.Unmarshal(line, resp)
}

// Close ends the helper (stdin EOF) and waits for it.
func (p *jsonProc) Close() error {
	if p == nil {
		return nil
	}
	if p.in != nil {
		p.in.Close()
	}
	if p.cmd != nil && p.cmd.Process != nil {
		return p.cmd.Wait()
	}
	return nil
}

// wireToken is [start, end, type, text_b64] as the helpers send it.
type wireToken [4]any

func (w wireToken) raw() (RawToken, error) {
	start, end := num(w[0]), num(w[1])
	typ, _ := w[2].(string)
	t64, _ := w[3].(string)
	text, err := base64.StdEncoding.DecodeString(t64)
	if err != nil {
		return RawToken{}, fmt.Errorf("%w: token text not base64: %v", ErrAdapterConversion, err)
	}
	return RawToken{Start: start, End: end, Text: text, Type: typ}, nil
}

func envOr(keys ...string) string {
	for _, k := range keys[:len(keys)-1] {
		if v := os.Getenv(k); v != "" {
			return v
		}
	}
	return keys[len(keys)-1]
}

func b64(b []byte) string { return base64.StdEncoding.EncodeToString(b) }
