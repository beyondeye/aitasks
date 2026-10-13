package provider

import (
	"fmt"
	"io"
	"sort"
	"sync"
)

var (
	registry = map[string]func() (Provider, error){}
	openMu   sync.Mutex
	open     []io.Closer
)

func register(name string, f func() (Provider, error)) { registry[name] = f }

// Names lists the registered candidate providers (the baseline is not one:
// it is the landed annot, never forced into this interface).
func Names() []string {
	var out []string
	for n := range registry {
		out = append(out, n)
	}
	sort.Strings(out)
	return out
}

// New constructs a registered provider; one that holds a subprocess is
// closed by CloseAll.
func New(name string) (Provider, error) {
	f, ok := registry[name]
	if !ok {
		return nil, fmt.Errorf("unknown provider %q (have %v)", name, Names())
	}
	p, err := f()
	if err != nil {
		return nil, err
	}
	if c, ok := p.(io.Closer); ok {
		openMu.Lock()
		open = append(open, c)
		openMu.Unlock()
	}
	return p, nil
}

// CloseAll releases every provider New returned.
func CloseAll() {
	openMu.Lock()
	defer openMu.Unlock()
	for _, c := range open {
		_ = c.Close()
	}
	open = nil
}
