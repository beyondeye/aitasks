package provider

import (
	"fmt"
	"sync"

	gts "github.com/odvcencio/gotreesitter"
	"github.com/odvcencio/gotreesitter/grammars"
)

func init() { register("gotreesitter", func() (Provider, error) { return NewGoTreeSitter(), nil }) }

// GoTreeSitter is github.com/odvcencio/gotreesitter (pure Go): tree-sitter
// parse tables run by a Go runtime, with Go-ported external scanners (and,
// for some grammars, Go-owned grammars or hand-written lexers — see
// results/ts_scanners.md). The tree goes through the shared MapTree.
type GoTreeSitter struct {
	mu      sync.Mutex
	parsers map[string]*gts.Parser
}

// GoTreeSitterLanguages maps each served language to its grammar.
var GoTreeSitterLanguages = map[string]func() *gts.Language{
	"bash": grammars.BashLanguage, "python": grammars.PythonLanguage, "go": grammars.GoLanguage,
	"kotlin": grammars.KotlinLanguage, "typescript": grammars.TypescriptLanguage, "tsx": grammars.TsxLanguage,
	"javascript": grammars.JavascriptLanguage, "java": grammars.JavaLanguage, "rust": grammars.RustLanguage,
	"swift": grammars.SwiftLanguage,
}

// NewGoTreeSitter returns the provider; grammars load on first use.
func NewGoTreeSitter() *GoTreeSitter { return &GoTreeSitter{parsers: map[string]*gts.Parser{}} }

func (*GoTreeSitter) Name() string                  { return "gotreesitter" }
func (*GoTreeSitter) Langs() []string               { return append([]string(nil), TSLangs...) }
func (*GoTreeSitter) Caps(lang string) Capabilities { return TSCaps(lang) }

func (g *GoTreeSitter) parser(lang string) (*gts.Parser, *gts.Language, error) {
	mk, ok := GoTreeSitterLanguages[lang]
	if !ok {
		return nil, nil, fmt.Errorf("gotreesitter: no grammar for %q", lang)
	}
	l := mk()
	p := g.parsers[lang]
	if p == nil {
		p = gts.NewParser(l)
		g.parsers[lang] = p
	}
	return p, l, nil
}

// Analyze parses src and maps the tree. A runtime error or panic is a
// provider failure (reported unsupported / not measured), never "no comments".
func (g *GoTreeSitter) Analyze(lang string, src []byte) (Result, error) {
	nodes, stopped, err := g.Flat(lang, src)
	if err != nil {
		return Result{}, err
	}
	return MapTree(lang, nodes, stopped, src), nil
}

// Flat parses src and returns the flattened tree and the early-stop reason
// ("" for a complete parse).
func (g *GoTreeSitter) Flat(lang string, src []byte) (nodes []TSNode, stopped string, err error) {
	g.mu.Lock()
	defer g.mu.Unlock()
	defer func() {
		if r := recover(); r != nil {
			err = fmt.Errorf("gotreesitter panic: %v", r)
		}
	}()
	p, l, err := g.parser(lang)
	if err != nil {
		return nil, "", err
	}
	tree, err := p.Parse(src)
	if err != nil {
		return nil, "", fmt.Errorf("gotreesitter: %w", err)
	}
	defer tree.Release()
	if tree.ParseStoppedEarly() {
		stopped = string(tree.ParseStopReason())
	}
	return FlattenGTS(tree.RootNode(), l), stopped, nil
}

// FlattenGTS walks a gotreesitter tree into preorder TSNodes.
func FlattenGTS(root *gts.Node, l *gts.Language) []TSNode {
	var out []TSNode
	var walk func(n *gts.Node, parent int)
	walk = func(n *gts.Node, parent int) {
		idx := len(out)
		cc := n.ChildCount()
		out = append(out, TSNode{
			Kind: n.Type(l), Start: int(n.StartByte()), End: int(n.EndByte()), Parent: parent,
			Named: n.IsNamed(), Error: n.IsError(), Missing: n.IsMissing(), Extra: n.IsExtra(), Leaf: cc == 0,
		})
		for i := 0; i < cc; i++ {
			walk(n.Child(i), idx)
		}
	}
	if root != nil {
		walk(root, -1)
	}
	return out
}
