//go:build t1954cgo && cgo

package provider

import (
	"fmt"
	"sync"
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

func init() { register("tscgo", func() (Provider, error) { return NewTSCgo(), nil }) }

// TSCgo is the reference: the official go-tree-sitter binding (the C runtime
// it vendors) with the C grammars and C external scanners at the commits
// gotreesitter extracted from (tsref/LOCK). Host-only: it needs cgo and a C
// toolchain per target, so it is evidence, not a deployable configuration.
type TSCgo struct {
	mu      sync.Mutex
	parsers map[string]*sitter.Parser
}

var tsCgoLanguages = map[string]func() unsafe.Pointer{
	"bash": tsbash.Language, "python": tspython.Language, "go": tsgo.Language,
	"kotlin": tskotlin.Language, "typescript": tstypescript.Language, "tsx": tstsx.Language,
	"javascript": tsjavascript.Language, "java": tsjava.Language, "rust": tsrust.Language,
	"swift": tsswift.Language,
}

// NewTSCgo returns the provider; parsers are created on first use.
func NewTSCgo() *TSCgo { return &TSCgo{parsers: map[string]*sitter.Parser{}} }

func (*TSCgo) Name() string                  { return "tscgo" }
func (*TSCgo) Langs() []string               { return append([]string(nil), TSLangs...) }
func (*TSCgo) Caps(lang string) Capabilities { return TSCaps(lang) }

// Close frees the C parsers.
func (c *TSCgo) Close() error {
	c.mu.Lock()
	defer c.mu.Unlock()
	for _, p := range c.parsers {
		p.Close()
	}
	c.parsers = map[string]*sitter.Parser{}
	return nil
}

// Analyze parses src with the C runtime and maps the tree.
func (c *TSCgo) Analyze(lang string, src []byte) (Result, error) {
	nodes, stopped, err := c.Flat(lang, src)
	if err != nil {
		return Result{}, err
	}
	return MapTree(lang, nodes, stopped, src), nil
}

// Flat parses src and returns the flattened tree. A nil tree (the parser
// gave up) is a provider failure, never an empty result.
func (c *TSCgo) Flat(lang string, src []byte) ([]TSNode, string, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	p := c.parsers[lang]
	if p == nil {
		mk, ok := tsCgoLanguages[lang]
		if !ok {
			return nil, "", fmt.Errorf("tscgo: no grammar for %q", lang)
		}
		p = sitter.NewParser()
		if err := p.SetLanguage(sitter.NewLanguage(mk())); err != nil {
			p.Close()
			return nil, "", fmt.Errorf("tscgo: %s: %w", lang, err)
		}
		c.parsers[lang] = p
	}
	tree := p.Parse(src, nil)
	if tree == nil {
		return nil, "", fmt.Errorf("tscgo: %s: parse returned no tree", lang)
	}
	defer tree.Close()
	return FlattenCgo(tree.RootNode()), "", nil
}

// FlattenCgo walks a C tree with a cursor into preorder TSNodes.
func FlattenCgo(root *sitter.Node) []TSNode {
	var out []TSNode
	cur := root.Walk()
	defer cur.Close()
	stack := []int{-1}
	for {
		n := cur.Node()
		out = append(out, TSNode{
			Kind: n.Kind(), Start: int(n.StartByte()), End: int(n.EndByte()), Parent: stack[len(stack)-1],
			Named: n.IsNamed(), Error: n.IsError(), Missing: n.IsMissing(), Extra: n.IsExtra(), Leaf: n.ChildCount() == 0,
		})
		if cur.GotoFirstChild() {
			stack = append(stack, len(out)-1)
			continue
		}
		for !cur.GotoNextSibling() {
			if !cur.GotoParent() {
				return out
			}
			stack = stack[:len(stack)-1]
		}
	}
}
