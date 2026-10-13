package provider

import (
	"fmt"
	"io"
)

// Composite dispatches each language to one provider: the "native"
// configuration (bash: shfmt, python: pytokenize, go: goscanner) used by the
// end-to-end bench. Not registered: it would duplicate its parts in matrices.
type Composite struct {
	by    map[string]Provider
	langs []string
}

// NativeParts are the native composite's providers.
var NativeParts = []string{"shfmt", "pytokenize", "goscanner"}

// NewComposite builds the native composite. It refuses an incomplete
// configuration: a part that cannot be constructed (e.g. no Python) would
// otherwise silently hand its languages to the landed lexer while results
// still name the part.
func NewComposite() (*Composite, error) {
	c := &Composite{by: map[string]Provider{}}
	for _, n := range NativeParts {
		p, err := New(n)
		if err != nil {
			return nil, fmt.Errorf("native composite: part %s unavailable: %w", n, err)
		}
		for _, l := range p.Langs() {
			c.by[l] = p
			c.langs = append(c.langs, l)
		}
	}
	return c, nil
}

// Composition maps each language to the provider that handles it.
func (c *Composite) Composition() map[string]string {
	out := map[string]string{}
	for l, p := range c.by {
		out[l] = p.Name()
	}
	return out
}

func (c *Composite) Name() string    { return "native" }
func (c *Composite) Langs() []string { return c.langs }
func (c *Composite) Caps(lang string) Capabilities {
	if p, ok := c.by[lang]; ok {
		return p.Caps(lang)
	}
	return Capabilities{}
}
func (c *Composite) Analyze(lang string, src []byte) (Result, error) {
	return c.by[lang].Analyze(lang, src)
}

var _ io.Closer = (*Composite)(nil)

// Close is a no-op: the parts are closed by CloseAll.
func (c *Composite) Close() error { return nil }
