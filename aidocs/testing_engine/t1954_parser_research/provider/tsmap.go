package provider

import (
	"bytes"
	"sort"
)

// The shared tree-sitter mapping. All three tree-sitter runtimes (the pure-Go
// gotreesitter, the official cgo binding, and the wazero-hosted wasm build)
// flatten their parse tree into []TSNode and hand it to MapTree, so their
// matrix rows and the differential compare RUNTIMES, never three mapping
// implementations. The per-language kind tables below are the whole
// per-language adapter cost of a tree-sitter provider.
//
// Policy (the M2.2 contract the hand oracles encode): annotations live only
// on comment lines outside every string, heredoc, block comment and backtick
// substitution. So a data node is data across its WHOLE range, interpolation
// fields included (a comment inside a multi-line f-string field or `${…}` is
// never an annotation line). The one carve-out is bash `$( … )` inside a
// double-quoted string, which M2.2 and the shfmt provider both read as code.

// TSNode is one parse-tree node, flattened in preorder.
type TSNode struct {
	Kind                         string
	Start, End                   int
	Parent                       int // index of the parent node; -1 for the root
	Named, Error, Missing, Extra bool
	Leaf                         bool // no children
}

// TSTreer is a tree-sitter provider that also exposes its flattened tree
// (the differential compares trees, not only mapped Results).
type TSTreer interface {
	Provider
	Flat(lang string, src []byte) (nodes []TSNode, stopped string, err error)
}

// tsLang is a language's kind table.
type tsLang struct {
	comments map[string]bool // comment nodes
	data     map[string]bool // whole-node data (strings, templates, chars, regex, JSX text)
	heredoc  map[string]bool // bash heredoc bodies (span runs through the terminator line)
	anchors  AnchorSet       // anchors MapTree determines for this language
	anchorK  []string        // node kinds the anchor rules read (for the kind guard)
}

func set(ks ...string) map[string]bool {
	m := map[string]bool{}
	for _, k := range ks {
		m[k] = true
	}
	return m
}

var tsLangTable = map[string]tsLang{
	"bash": {
		comments: set("comment"),
		data:     set("string", "raw_string", "ansi_c_string", "translated_string", "expansion", "command_substitution"),
		heredoc:  set("heredoc_body"),
		anchors:  AShebang,
		anchorK:  []string{"heredoc_end"},
	},
	"python": {
		comments: set("comment"),
		data:     set("string"),
		anchorK:  []string{"expression_statement", "parenthesized_expression", "concatenated_string", "string_start", "string_end"},
	},
	"go": {
		comments: set("comment"),
		data:     set("interpreted_string_literal", "raw_string_literal", "rune_literal"),
		anchors:  APackage | AImportEnd,
		anchorK:  []string{"package_clause", "import_declaration"},
	},
	"kotlin": {
		comments: set("line_comment", "multiline_comment"),
		data:     set("string_literal", "character_literal"),
		anchors:  APackage | AImportEnd,
		anchorK:  []string{"package_header", "import_list", "import_header"},
	},
	"typescript": {
		comments: set("comment", "html_comment"),
		data:     set("string", "template_string", "regex", "jsx_text", "template_literal_type"),
		anchors:  AImportEnd | APrologue,
		anchorK:  []string{"import_statement", "expression_statement", "hash_bang_line"},
	},
	"java": {
		comments: set("line_comment", "block_comment"),
		data:     set("string_literal", "character_literal"),
		anchors:  APackage | AImportEnd,
		anchorK:  []string{"package_declaration", "import_declaration"},
	},
	"rust": {
		comments: set("line_comment", "block_comment"),
		data:     set("string_literal", "raw_string_literal", "char_literal"),
		anchors:  AInnerAttrEnd | AImportEnd,
		anchorK:  []string{"inner_attribute_item", "inner_doc_comment_marker", "use_declaration"},
	},
	"swift": {
		comments: set("comment", "multiline_comment"),
		data:     set("line_string_literal", "multi_line_string_literal", "raw_string_literal", "regex_literal"),
		anchors:  AImportEnd,
		anchorK:  []string{"import_declaration"},
	},
}

func init() {
	ts := tsLangTable["typescript"]
	tsLangTable["tsx"] = ts
	js := ts
	js.data = set("string", "template_string", "regex", "jsx_text")
	tsLangTable["javascript"] = js
}

// TSLangs are the languages the tree-sitter providers serve (research names;
// "tsx" is its own grammar).
var TSLangs = []string{"bash", "python", "go", "kotlin", "typescript", "tsx", "javascript", "java", "rust", "swift"}

// TSCaps is what MapTree establishes for lang.
func TSCaps(lang string) Capabilities {
	// FullCover is false by measurement: tree-sitter does not materialise
	// hidden tokens and extras as nodes (string delimiters and contents in
	// some grammars, doc-comment text, bash line continuations, a BOM), so
	// leaves never partition the input (findings_t1954_2.md).
	return Capabilities{TokenRanges: true, Errors: true, DocLiterals: lang == "python", Anchors: tsLangTable[lang].anchors}
}

// TSKinds lists every node kind the mapping for lang reads, so a test can
// prove each one exists in the grammar (a renamed kind must fail loudly, not
// silently unmap).
func TSKinds(lang string) []string {
	t := tsLangTable[lang]
	var out []string
	for _, m := range []map[string]bool{t.comments, t.data, t.heredoc} {
		for k := range m {
			out = append(out, k)
		}
	}
	out = append(out, t.anchorK...)
	sort.Strings(out)
	return out
}

// MapTree turns a flattened parse tree into a provider Result. stopped is
// non-empty when the runtime stopped before finishing the parse.
func MapTree(lang string, nodes []TSNode, stopped string, src []byte) Result {
	t := tsLangTable[lang]
	l, _ := LangByName(lang)
	var res Result
	if stopped != "" {
		res.Diags = append(res.Diags, Diag{0, 0, "parse stopped early: " + stopped})
	}
	if len(nodes) == 0 {
		res.Diags = append(res.Diags, Diag{0, 0, "no tree"})
		return res
	}
	if tail := lastNonSpace(src); tail >= 0 && nodes[0].End <= tail {
		res.Diags = append(res.Diags, Diag{nodes[0].End, len(src), "tree ends before the input"})
	}
	children := make([][]int, len(nodes))
	for i, n := range nodes {
		if n.Parent >= 0 {
			children[n.Parent] = append(children[n.Parent], i)
		}
	}
	// inData[i]: an ancestor of i is a data or heredoc node (its span already
	// covers i).
	inData := make([]bool, len(nodes))
	for i, n := range nodes {
		if n.Error {
			res.Diags = append(res.Diags, Diag{n.Start, n.End, "ERROR node"})
		}
		if n.Missing {
			res.Diags = append(res.Diags, Diag{n.Start, n.End, "MISSING " + n.Kind})
		}
		if n.Parent >= 0 {
			p := nodes[n.Parent]
			inData[i] = inData[n.Parent] || isData(t, p, src)
		}
		switch {
		case t.comments[n.Kind] && n.End > n.Start:
			end := trimEOL(src, n.Start, n.End)
			k := BlockComment
			if bytes.HasPrefix(src[n.Start:], []byte(l.Leader)) {
				k = LineComment
			}
			res.Spans = append(res.Spans, Span{n.Start, end, k})
		case inData[i]:
		case t.heredoc[n.Kind]:
			end := n.End
			if p := n.Parent; p >= 0 {
				for _, c := range children[p] {
					if nodes[c].Kind == "heredoc_end" && nodes[c].Start >= n.Start {
						end = max(end, nodes[c].End)
						break
					}
				}
			}
			for end < len(src) && src[end] != '\n' {
				end++
			}
			res.Spans = append(res.Spans, Span{n.Start, end, Heredoc})
		case isData(t, n, src):
			for _, piece := range dataPieces(lang, i, nodes, children, src) {
				res.Spans = append(res.Spans, Span{piece[0], piece[1], String})
			}
		}
	}
	starts := LineStarts(src)
	if lang == "bash" {
		markContinuationComments(res.Spans, src)
	}
	res.Anchors = anchors(lang, nodes, children[0], children, src, starts)
	if lang == "python" {
		res.Doc = pyDoc(nodes, children, src)
	}
	return res
}

// markContinuationComments: bash joins a backslash-newline, so a comment
// that opens a continuation line trails the previous command — a real
// comment that the M2.2 policy never treats as an annotation line. It is
// reported with kind BlockComment, so its range still counts as a comment
// for the range level while the adapter never classes the line Comment.
func markContinuationComments(spans []Span, src []byte) {
	inComment := func(off int) bool {
		for _, s := range spans {
			if (s.Kind == LineComment || s.Kind == BlockComment) && s.Start <= off && off < s.End {
				return true
			}
		}
		return false
	}
	for i, s := range spans {
		if s.Kind != LineComment {
			continue
		}
		ls := s.Start
		for ls > 0 && src[ls-1] != '\n' {
			ls--
		}
		if !isSpace(src[ls:s.Start]) || ls < 2 {
			continue
		}
		e := ls - 1 // the '\n'
		if e > 0 && src[e-1] == '\r' {
			e--
		}
		n := 0
		for e-1-n >= 0 && src[e-1-n] == '\\' {
			n++
		}
		if n%2 == 1 && !inComment(e-1) {
			spans[i].Kind = BlockComment
		}
	}
}

// isData reports whether n is a data node for the language. In bash a
// command substitution is data only in its backtick form (M2.2 classes
// backtick bodies as data); `$( … )` is code.
func isData(t tsLang, n TSNode, src []byte) bool {
	if !t.data[n.Kind] {
		return false
	}
	if n.Kind == "command_substitution" {
		return n.Start < len(src) && src[n.Start] == '`'
	}
	return true
}

// dataPieces is a data node's range, minus — for a bash double-quoted string
// only — its `$( … )` children, which are code.
func dataPieces(lang string, i int, nodes []TSNode, children [][]int, src []byte) [][2]int {
	n := nodes[i]
	if lang != "bash" || n.Kind != "string" {
		return [][2]int{{n.Start, n.End}}
	}
	var out [][2]int
	pos := n.Start
	for _, c := range children[i] {
		cn := nodes[c]
		if cn.Kind == "command_substitution" && cn.Start < len(src) && src[cn.Start] == '$' {
			if cn.Start > pos {
				out = append(out, [2]int{pos, cn.Start})
			}
			pos = cn.End
		}
	}
	if n.End > pos {
		out = append(out, [2]int{pos, n.End})
	}
	return out
}

func anchors(lang string, nodes []TSNode, top []int, children [][]int, src []byte, starts []int) Anchors {
	var a Anchors
	first := func(n TSNode) int { return LineOf(starts, n.Start) }
	last := func(n TSNode) int { return lastLine(src, starts, n.Start, n.End) }
	switch lang {
	case "bash":
		if bytes.HasPrefix(src, []byte("#!")) {
			a.Shebang = 1
		}
	case "go":
		for _, i := range top {
			switch nodes[i].Kind {
			case "package_clause":
				if a.Package == 0 {
					a.Package = first(nodes[i])
				}
			case "import_declaration":
				a.ImportEnd = last(nodes[i])
			}
		}
	case "kotlin":
		for _, i := range top {
			switch nodes[i].Kind {
			case "package_header":
				if a.Package == 0 {
					a.Package = first(nodes[i])
				}
			case "import_list":
				for _, c := range children[i] {
					if nodes[c].Kind == "import_header" {
						a.ImportEnd = last(nodes[c])
					}
				}
			case "import_header":
				a.ImportEnd = last(nodes[i])
			}
		}
	case "java":
		for _, i := range top {
			switch nodes[i].Kind {
			case "package_declaration":
				if a.Package == 0 {
					a.Package = first(nodes[i])
				}
			case "import_declaration":
				a.ImportEnd = last(nodes[i])
			}
		}
	case "typescript", "tsx", "javascript":
		prologue := true
		for _, i := range top {
			n := nodes[i]
			if n.Extra || n.Kind == "hash_bang_line" {
				continue
			}
			if prologue && n.Kind == "expression_statement" && isDirective(i, nodes, children) {
				a.Prologue = last(n)
				continue
			}
			prologue = false
			if n.Kind == "import_statement" {
				a.ImportEnd = last(n)
			}
		}
	case "rust":
		leading := true
		for _, i := range top {
			n := nodes[i]
			switch {
			case n.Kind == "inner_attribute_item" && leading:
				a.InnerAttrEnd = last(n)
			case (n.Kind == "line_comment" || n.Kind == "block_comment") && leading:
				for _, c := range children[i] {
					if nodes[c].Kind == "inner_doc_comment_marker" {
						a.InnerAttrEnd = last(n)
					}
				}
			case n.Extra:
			default:
				leading = false
				if n.Kind == "use_declaration" {
					a.ImportEnd = last(n)
				}
			}
		}
	case "swift":
		for _, i := range top {
			if nodes[i].Kind == "import_declaration" {
				a.ImportEnd = last(nodes[i])
			}
		}
	}
	return a
}

// isDirective: an expression statement whose only named child is a string.
func isDirective(i int, nodes []TSNode, children [][]int) bool {
	named := 0
	str := false
	for _, c := range children[i] {
		if nodes[c].Named && !nodes[c].Extra {
			named++
			str = nodes[c].Kind == "string"
		}
	}
	return named == 1 && str
}

// pyDoc: the module docstring — the first statement is an expression
// statement whose value is a plain (non-f, non-bytes) string literal or an
// implicit concatenation of them, possibly parenthesised.
func pyDoc(nodes []TSNode, children [][]int, src []byte) *DocInfo {
	var stmt = -1
	for _, i := range children[0] {
		if nodes[i].Extra {
			continue
		}
		stmt = i
		break
	}
	if stmt < 0 {
		return nil
	}
	// At the pinned tree-sitter-python commit (26855eab) expression_statement
	// is a supertype: neither the C runtime nor gotreesitter materialises it,
	// and the value sits directly under module (measured in both). Grammar
	// versions that do wrap it are accepted too. Both shapes end where the
	// statement's value ends (`;` is a sibling either way).
	v := stmt
	if nodes[stmt].Kind == "expression_statement" {
		v = onlyNamed(stmt, nodes, children)
	}
	for v >= 0 && nodes[v].Kind == "parenthesized_expression" {
		v = onlyNamed(v, nodes, children)
	}
	if v < 0 {
		return nil
	}
	var strs []int
	switch nodes[v].Kind {
	case "string":
		strs = []int{v}
	case "concatenated_string":
		for _, c := range children[v] {
			if nodes[c].Kind == "string" {
				strs = append(strs, c)
			}
		}
	default:
		return nil
	}
	info := &DocInfo{StmtEnd: nodes[stmt].End}
	for _, s := range strs {
		var start, end = -1, -1
		for _, c := range children[s] {
			switch nodes[c].Kind {
			case "string_start":
				start = c
			case "string_end":
				end = c
			}
		}
		if start < 0 || end < 0 {
			return nil
		}
		prefix := bytes.TrimRight(src[nodes[start].Start:nodes[start].End], `"'`)
		if bytes.ContainsAny(prefix, "fFbBtT") {
			return nil
		}
		info.Literals = append(info.Literals, DocLiteral{
			ContentStart: nodes[start].End, ContentEnd: nodes[end].Start,
			Raw: bytes.ContainsAny(prefix, "rR"),
		})
	}
	return info
}

func onlyNamed(i int, nodes []TSNode, children [][]int) int {
	got := -1
	for _, c := range children[i] {
		if nodes[c].Named && !nodes[c].Extra {
			if got >= 0 {
				return -1
			}
			got = c
		}
	}
	return got
}

// trimEOL drops a trailing "\n" / "\r" from a comment node (some grammars
// include the newline; CRLF files leave a '\r').
func trimEOL(src []byte, start, end int) int {
	for end > start && (src[end-1] == '\n' || src[end-1] == '\r') {
		end--
	}
	return end
}

// lastLine is the line of the last non-whitespace byte in [start, end).
func lastLine(src []byte, starts []int, start, end int) int {
	for end > start && isSpace(src[end-1:end]) {
		end--
	}
	if end > start {
		end--
	}
	return LineOf(starts, end)
}

func lastNonSpace(src []byte) int {
	for i := len(src) - 1; i >= 0; i-- {
		if !isSpace(src[i : i+1]) {
			return i
		}
	}
	return -1
}

func isSpace(b []byte) bool {
	for _, c := range b {
		switch c {
		case ' ', '\t', '\n', '\r', '\f', '\v':
		default:
			return false
		}
	}
	return true
}
