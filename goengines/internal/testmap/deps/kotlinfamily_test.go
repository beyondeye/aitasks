package deps

import (
	"io/fs"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/annot"
)

// Three lexers read Kotlin on their own: annot's line classifier (annotation
// lines), ktLex (the .kt dependency scanner) and the kts mode of
// blankGradleComments (the .gradle.kts module graph). A construct one of them
// learns has had to be taught to the other two by hand. This file makes that
// visible the moment one changes:
//   - kotlinFamilyCases pins, per construct, what each lexer does against the
//     real KotlinLexer (kotlin-compiler-embeddable 2.3.20). The pinned
//     readings, the method and the evidence are in t1992's archived plan;
//   - TestKotlinFamilyCorpus asserts the three agree on every Kotlin fixture
//     of annot and deps.
// When a row fails, model the construct in all three lexers, or pin the new
// divergence here with its reason.

// familyLexer is one Kotlin-family lexer: whether it reads a source without
// refusing it, and the projection its consumer reads.
type familyLexer struct {
	name    string
	accepts func(src string) bool
	project func(src string) string
}

var familyLexers = [3]familyLexer{
	{"annot", func(s string) bool { return annot.Classify(annot.Kotlin, []byte(s)).Uncertain == nil }, familyAnnot},
	{"ktLex", func(s string) bool { _, err := ktLex(s); return err == nil }, familyTokens},
	{"kts", func(s string) bool { _, at := blankGradleComments(s, true); return at < 0 }, func(s string) string {
		out, _ := blankGradleComments(s, true)
		return out
	}},
}

// familyAnnot renders what annot's consumers read: the line classes (c Code,
// # Comment, L Literal) and the Package / Import anchors placement uses.
func familyAnnot(src string) string {
	c := annot.Classify(annot.Kotlin, []byte(src))
	var b strings.Builder
	for _, k := range c.Class {
		b.WriteByte("c#L"[k])
	}
	return b.String() + " package=" + strconv.Itoa(c.Package) + " import=" + strconv.Itoa(c.Import)
}

// familyTokens renders ktLex's whole stream, one <kind><esc>@<line>:<text>
// per token (esc "`" for a backticked name); text escapes \ space \n \r \t.
func familyTokens(src string) string {
	toks, _ := ktLex(src)
	esc := strings.NewReplacer(`\`, `\\`, " ", `\s`, "\n", `\n`, "\r", `\r`, "\t", `\t`)
	out := make([]string, len(toks))
	for i, k := range toks {
		flag := ""
		if k.esc {
			flag = "`"
		}
		out[i] = string(k.kind) + flag + "@" + strconv.Itoa(k.line) + ":" + esc.Replace(k.text)
	}
	return strings.Join(out, " ")
}

// familyOpen is a lexer's line-start view: '.' when every string, comment and
// template is closed at the start of line i+1, 'o' otherwise. A prefix that
// ends at a line start is accepted exactly when nothing is open there.
func familyOpen(src string, accepts func(string) bool) string {
	var b strings.Builder
	for at := 0; at < len(src); { // a final "\n" starts no line, as in annot
		if accepts(src[:at]) {
			b.WriteByte('.')
		} else {
			b.WriteByte('o')
		}
		nl := strings.IndexByte(src[at:], '\n')
		if nl < 0 {
			break
		}
		at += nl + 1
	}
	return b.String()
}

// familyBlank blanks the byte ranges "s-e,…" of src to spaces, keeping
// newlines: what the real lexer's comment ranges make of src.
func familyBlank(t *testing.T, src, ranges string) string {
	b := []byte(src)
	for _, r := range strings.Split(ranges, ",") {
		if r == "" {
			continue
		}
		s, e, ok := strings.Cut(r, "-")
		from, err1 := strconv.Atoi(s)
		to, err2 := strconv.Atoi(e)
		if !ok || err1 != nil || err2 != nil || from > to || to > len(b) {
			t.Fatalf("bad comment range %q", r)
		}
		for i := from; i < to; i++ {
			if b[i] != '\n' {
				b[i] = ' '
			}
		}
	}
	return string(b)
}

// familyOutcome is how one lexer reads a construct: modelled (it reads what the
// real lexer reads), refuses (it fails closed on the file), or a pinned
// divergence — its exact line-start view and projection.
type familyOutcome struct {
	refuses       bool
	open, project string
	why           string
}

var modelled = familyOutcome{}

func refuses(why string) familyOutcome { return familyOutcome{refuses: true, why: why} }

func differs(open, project, why string) familyOutcome {
	return familyOutcome{open: open, project: project, why: why}
}

// familyCase is one construct. open, classes, anchors, tokens and comments
// are the real KotlinLexer's reading: its line-start view, annot's line
// classes, the line of the first top-level package and last top-level import
// (0 = none), the ktLex vocabulary of its tokens (numeric literals segmented
// by ktLex's digit rule, under which 1e-5 is three tokens; no consumer reads a
// d token) and its comment byte ranges. An empty open means the real lexer
// rejects src.
type familyCase struct {
	name, rule string
	src        string
	open       string
	classes    string
	anchors    string
	tokens     string
	comments   string
	want       [3]familyOutcome // annot, ktLex, kts
}

var kotlinFamilyCases = []familyCase{
	{
		name: "backticked_names", rule: "ESCAPED_IDENTIFIER",
		src:  "val `it's // here` = 1\nfun `has \"quotes\"`() = `it's // here`\n// probe: a real comment\nval probe = 1\n",
		open: "....", classes: "cc#c", anchors: "package=0 import=0",
		tokens:   "n@1:val n`@1:it's\\s//\\shere o@1:= d@1:1 n@2:fun n`@2:has\\s\"quotes\" o@2:( o@2:) o@2:= n`@2:it's\\s//\\shere n@4:val n@4:probe o@4:= d@4:1",
		comments: "61-85",
		want:     [3]familyOutcome{modelled, modelled, modelled},
	},
	{
		name: "block_comment", rule: "BLOCK_COMMENT",
		src:  "/* a // b \"c\n   still 'd' comment */\n// probe: a real comment\nval probe = 1\n",
		open: ".o..", classes: "cL#c", anchors: "package=0 import=0",
		tokens:   "n@4:val n@4:probe o@4:= d@4:1",
		comments: "0-36,37-61",
		want:     [3]familyOutcome{modelled, modelled, modelled},
	},
	{
		name: "bom_comment", rule: "a leading byte-order mark",
		src:  "\ufeff// first line comment after a BOM\n// probe: a real comment\nval probe = 1\n",
		open: "...", classes: "##c", anchors: "package=0 import=0",
		tokens:   "n@3:val n@3:probe o@3:= d@3:1",
		comments: "3-36,37-61",
		want:     [3]familyOutcome{modelled, modelled, modelled},
	},
	{
		name: "char_literals", rule: "CHARACTER_LITERAL",
		src:  "val c = listOf('\"', '\\'', '\\\\', '\\u0041', '/', '`', '$')\n// probe: a real comment\nval probe = 1\n",
		open: "...", classes: "c#c", anchors: "package=0 import=0",
		tokens:   "n@1:val n@1:c o@1:= n@1:listOf o@1:( S@1: o@1:, S@1: o@1:, S@1: o@1:, S@1: o@1:, S@1: o@1:, S@1: o@1:, S@1: o@1:) n@3:val n@3:probe o@3:= d@3:1",
		comments: "57-81",
		want:     [3]familyOutcome{modelled, modelled, modelled},
	},
	{
		name: "crlf", rule: "CRLF line separators",
		src:  "val r = \"\"\"\r\n// in raw\r\n\"\"\"\r\n// probe: a real comment\r\nval probe = r\r\n",
		open: ".oo..", classes: "cLL#c", anchors: "package=0 import=0",
		tokens:   "n@1:val n@1:r o@1:= s@1:\\n//\\sin\\sraw\\n n@5:val n@5:probe o@5:= n@5:r",
		comments: "29-54",
		want:     [3]familyOutcome{modelled, differs(".oo..", "n@1:val n@1:r o@1:= s@1:\\r\\n//\\sin\\sraw\\r\\n n@5:val n@5:probe o@5:= n@5:r", "a raw string's content keeps the \\r that kotlinc normalises away (t1992 decision record)"), modelled},
	},
	{
		name: "doc_comment", rule: "DOC_COMMENT",
		src:  "/** KDoc \"quote\" // slashes\n * nested /* c */ block\n */\n// probe: a real comment\nval probe = 1\n",
		open: ".oo..", classes: "cLL#c", anchors: "package=0 import=0",
		tokens:   "n@5:val n@5:probe o@5:= d@5:1",
		comments: "0-55,56-80",
		want:     [3]familyOutcome{modelled, modelled, modelled},
	},
	{
		name: "invalid_backslash_in_code", rule: "BAD_CHARACTER \\\\",
		src:  "val a = foo \\ bar\nval probe = 1\n",
		want: [3]familyOutcome{differs("..", "cc package=0 import=0", "invalid Kotlin read leniently: a backslash in code is ignored"), differs("..", "n@1:val n@1:a o@1:= n@1:foo o@1:\\\\ n@1:bar n@2:val n@2:probe o@2:= d@2:1", "invalid Kotlin read leniently: a backslash in code is an operator token"), refuses("invalid Kotlin")},
	},
	{
		name: "invalid_backslash_newline_in_string", rule: "a backslash before a newline in STRING",
		src:  "val s = \"a\\\nb\"\nval probe = 1\n",
		want: [3]familyOutcome{refuses("invalid Kotlin"), differs(".o.", "n@1:val n@1:s o@1:= S@1: n@2:val n@2:probe o@2:= d@2:1", "invalid Kotlin read leniently: the backslash escapes the newline"), differs(".o.", "val s = \"a\\\nb\"\nval probe = 1\n", "invalid Kotlin read leniently: the backslash escapes the newline")},
	},
	{
		name: "invalid_unclosed_backtick", rule: "an unclosed ESCAPED_IDENTIFIER",
		src:  "val `x = 1\nval probe = 1\n",
		want: [3]familyOutcome{differs("..", "cc package=0 import=0", "invalid Kotlin read leniently: an unclosed backtick is a stray character"), refuses("invalid Kotlin"), refuses("invalid Kotlin")},
	},
	{
		name: "invalid_unclosed_char", rule: "a malformed CHARACTER_LITERAL",
		src:  "val c = 'ab\nval probe = 1\n",
		want: [3]familyOutcome{differs("..", "cc package=0 import=0", "invalid Kotlin read leniently: an unclosed char literal is a stray quote"), refuses("invalid Kotlin"), refuses("invalid Kotlin")},
	},
	{
		name: "invalid_unterminated_block", rule: "an unclosed BLOCK_COMMENT",
		src:  "/* never closed\nval probe = 1\n",
		want: [3]familyOutcome{refuses("invalid Kotlin"), refuses("invalid Kotlin"), refuses("invalid Kotlin")},
	},
	{
		name: "invalid_unterminated_raw", rule: "an unclosed RAW_STRING",
		src:  "val s = \"\"\"abc\n// x\n",
		want: [3]familyOutcome{refuses("invalid Kotlin"), refuses("invalid Kotlin"), refuses("invalid Kotlin")},
	},
	{
		name: "invalid_unterminated_string", rule: "DANGLING_NEWLINE",
		src:  "val s = \"abc\nval probe = 1\n",
		want: [3]familyOutcome{refuses("invalid Kotlin"), refuses("invalid Kotlin"), refuses("invalid Kotlin")},
	},
	{
		name: "invalid_unterminated_template", rule: "an unclosed LONG_TEMPLATE_ENTRY",
		src:  "val s = \"${a\n",
		want: [3]familyOutcome{refuses("invalid Kotlin"), refuses("invalid Kotlin"), refuses("invalid Kotlin")},
	},
	{
		name: "line_comment", rule: "EOL_COMMENT",
		src:  "val a = 1 // it's \"x\" /* not a block\n// probe: a real comment\nval probe = 1\n",
		open: "...", classes: "c#c", anchors: "package=0 import=0",
		tokens:   "n@1:val n@1:a o@1:= d@1:1 n@3:val n@3:probe o@3:= d@3:1",
		comments: "10-36,37-61",
		want:     [3]familyOutcome{modelled, modelled, modelled},
	},
	{
		name: "lonely_dollar", rule: "LONELY_DOLLAR",
		src:  "val s = \"$\" + \"a$ b\" + \"$$\" + \"\"\"$\"\"\"\n// probe: a real comment\nval probe = 1\n",
		open: "...", classes: "c#c", anchors: "package=0 import=0",
		tokens:   "n@1:val n@1:s o@1:= s@1:$ o@1:+ s@1:a$\\sb o@1:+ s@1:$$ o@1:+ s@1:$ n@3:val n@3:probe o@3:= d@3:1",
		comments: "38-62",
		want:     [3]familyOutcome{modelled, modelled, modelled},
	},
	{
		name: "multidollar_in_template", rule: "{INTERPOLATION}?\\\" inside LONG_TEMPLATE_ENTRY",
		src:  "val s = \"${ $$\"x\" }\"\n// probe: a real comment\nval probe = 1\n",
		open: "...", classes: "c#c", anchors: "package=0 import=0",
		tokens:   "n@1:val n@1:s o@1:= o@1:$ o@1:$ s@1:x S@1: n@3:val n@3:probe o@3:= d@3:1",
		comments: "21-45",
		want:     [3]familyOutcome{modelled, refuses("multi-dollar strings fail closed in deps (t1980)"), refuses("multi-dollar strings fail closed in deps (t1975)")},
	},
	{
		name: "multidollar_plain", rule: "{INTERPOLATION}?\\\" (Kotlin 2.2)",
		src:  "val j = $$\"{x} $${y} ${'$'}z\"\n// probe: a real comment\nval probe = 1\n",
		open: "...", classes: "c#c", anchors: "package=0 import=0",
		tokens:   "n@1:val n@1:j o@1:= o@1:$ o@1:$ n@1:y S@1: n@3:val n@3:probe o@3:= d@3:1",
		comments: "30-54",
		want:     [3]familyOutcome{modelled, refuses("multi-dollar strings fail closed in deps (t1980)"), refuses("multi-dollar strings fail closed in deps (t1975)")},
	},
	{
		name: "multidollar_raw_desync", rule: "{INTERPOLATION}?\\\"\\\"\\\" (Kotlin 2.2)",
		src:  "val s = $$\"\"\"${/*\"\"\"\n// */\nval t = \"\"\"\n// look-alike inside raw\n\"\"\"\n// probe: a real comment\nval probe = 1\n",
		open: "...oo..", classes: "c#cLL#c", anchors: "package=0 import=0",
		tokens:   "n@1:val n@1:s o@1:= o@1:$ o@1:$ s@1:${/* n@3:val n@3:t o@3:= s@3:\\n//\\slook-alike\\sinside\\sraw\\n n@7:val n@7:probe o@7:= d@7:1",
		comments: "21-26,68-92",
		want:     [3]familyOutcome{modelled, refuses("multi-dollar strings fail closed in deps (t1980): one file opaque; annot models them (t1990)"), refuses("multi-dollar strings fail closed in deps (t1975): the module widens; annot models them (t1990)")},
	},
	{
		name: "nested_block_comment", rule: "BLOCK_COMMENT nesting",
		src:  "/* a /* b */\n// inside: still a comment\n*/\n// probe: a real comment\nval probe = 1\n",
		open: ".oo..", classes: "cLL#c", anchors: "package=0 import=0",
		tokens:   "n@5:val n@5:probe o@5:= d@5:1",
		comments: "0-42,43-67",
		want:     [3]familyOutcome{modelled, modelled, modelled},
	},
	{
		name: "numbers", rule: "INTEGER_LITERAL, FLOAT_LITERAL",
		src:  "val n = listOf(1.5f, 0x1F, 1..2, 1e-5, 1_000L, 0b101, 2.0e10, .5)\n",
		open: ".", classes: "c", anchors: "package=0 import=0",
		tokens:   "n@1:val n@1:n o@1:= n@1:listOf o@1:( d@1:1.5f o@1:, d@1:0x1F o@1:, d@1:1 o@1:. o@1:. d@1:2 o@1:, d@1:1e o@1:- d@1:5 o@1:, d@1:1_000L o@1:, d@1:0b101 o@1:, d@1:2.0e10 o@1:, o@1:. d@1:5 o@1:)",
		comments: "",
		want:     [3]familyOutcome{modelled, modelled, modelled},
	},
	{
		name: "operators", rule: "operator and keyword tokens deps reads",
		src:  "@file:JvmName(\"X\")\npackage p.q\n\nimport a.b.C as D\n\n@Ann(x) class Box<T>(val t: T)\nfun <T> Box<T>.f(): T? = this?.t\nval r = R.string.k\nval m = mapOf(1 to 2)[1]\nval g = { x: Int -> x * 2 }\nval k = String::class.java\nval e = a ?: b!!\nval n = a !in b && c !is D && (d as? E) != null\nval p = x::y\n",
		open: "..............", classes: "cccccccccccccc", anchors: "package=2 import=4",
		tokens:   "o@1:@ n@1:file o@1:: n@1:JvmName o@1:( s@1:X o@1:) n@2:package n@2:p o@2:. n@2:q n@4:import n@4:a o@4:. n@4:b o@4:. n@4:C n@4:as n@4:D o@6:@ n@6:Ann o@6:( n@6:x o@6:) n@6:class n@6:Box o@6:< n@6:T o@6:> o@6:( n@6:val n@6:t o@6:: n@6:T o@6:) n@7:fun o@7:< n@7:T o@7:> n@7:Box o@7:< n@7:T o@7:> o@7:. n@7:f o@7:( o@7:) o@7:: n@7:T o@7:? o@7:= n@7:this o@7:? o@7:. n@7:t n@8:val n@8:r o@8:= n@8:R o@8:. n@8:string o@8:. n@8:k n@9:val n@9:m o@9:= n@9:mapOf o@9:( d@9:1 n@9:to d@9:2 o@9:) o@9:[ d@9:1 o@9:] n@10:val n@10:g o@10:= o@10:{ n@10:x o@10:: n@10:Int o@10:- o@10:> n@10:x o@10:* d@10:2 o@10:} n@11:val n@11:k o@11:= n@11:String o@11::: n@11:class o@11:. n@11:java n@12:val n@12:e o@12:= n@12:a o@12:? o@12:: n@12:b o@12:! o@12:! n@13:val n@13:n o@13:= n@13:a o@13:! n@13:in n@13:b o@13:& o@13:& n@13:c o@13:! n@13:is n@13:D o@13:& o@13:& o@13:( n@13:d n@13:as o@13:? n@13:E o@13:) o@13:! o@13:= n@13:null n@14:val n@14:p o@14:= n@14:x o@14::: n@14:y",
		comments: "",
		want:     [3]familyOutcome{modelled, modelled, modelled},
	},
	{
		name: "plain_string_escapes", rule: "STRING, ESCAPE_SEQUENCE",
		src:  "val s = \"a\\\"// not a comment\\\\\" + \"/*\"\n// probe: a real comment\nval probe = 1\n",
		open: "...", classes: "c#c", anchors: "package=0 import=0",
		tokens:   "n@1:val n@1:s o@1:= S@1: o@1:+ s@1:/* n@3:val n@3:probe o@3:= d@3:1",
		comments: "39-63",
		want:     [3]familyOutcome{modelled, modelled, modelled},
	},
	{
		name: "raw_string_backslash_end", rule: "RAW_STRING: no escapes",
		src:  "val p = \"\"\"C:\\\"\"\"\n// probe: a real comment\nval probe = 1\n",
		open: "...", classes: "c#c", anchors: "package=0 import=0",
		tokens:   "n@1:val n@1:p o@1:= s@1:C:\\\\ n@3:val n@3:probe o@3:= d@3:1",
		comments: "18-42",
		want:     [3]familyOutcome{modelled, modelled, modelled},
	},
	{
		name: "raw_string_lookalikes", rule: "RAW_STRING",
		src:  "val r = \"\"\"\n// not a comment\n/* not a block\n\" \"\" \\\n\"\"\"\n// probe: a real comment\nval probe = 1\n",
		open: ".oooo..", classes: "cLLLL#c", anchors: "package=0 import=0",
		tokens:   "n@1:val n@1:r o@1:= s@1:\\n//\\snot\\sa\\scomment\\n/*\\snot\\sa\\sblock\\n\"\\s\"\"\\s\\\\\\n n@7:val n@7:probe o@7:= d@7:1",
		comments: "55-79",
		want:     [3]familyOutcome{modelled, modelled, modelled},
	},
	{
		name: "raw_string_quote_run", rule: "RAW_STRING: THREE_OR_MORE_QUO",
		src:  "val q = \"\"\"a \"b\" \"\"\"\"\nval q2 = \"\"\"\"\"x\"\"\"\"\"\n// probe: a real comment\nval probe = 1\n",
		open: "....", classes: "cc#c", anchors: "package=0 import=0",
		tokens:   "n@1:val n@1:q o@1:= s@1:a\\s\"b\"\\s\" n@2:val n@2:q2 o@2:= s@2:\"\"x\"\" n@4:val n@4:probe o@4:= d@4:1",
		comments: "43-67",
		want:     [3]familyOutcome{modelled, modelled, modelled},
	},
	{
		name: "raw_template_nested_raw", rule: "RAW_STRING template holding a RAW_STRING",
		src:  "val r = \"\"\"${\"\"\"x\"\"\"} ${ \"y\" }\"\"\"\n// probe: a real comment\nval probe = 1\n",
		open: "...", classes: "c#c", anchors: "package=0 import=0",
		tokens:   "n@1:val n@1:r o@1:= s@1:x s@1:y S@1: n@3:val n@3:probe o@3:= d@3:1",
		comments: "34-58",
		want:     [3]familyOutcome{modelled, modelled, modelled},
	},
	{
		name: "shebang_brace", rule: "SHEBANG_COMMENT holding {",
		src:  "#!/usr/bin/env -S kotlin -J-Dtag={\npackage p\nclass Actual\n// probe: a real comment\nval probe = 1\n",
		open: ".....", classes: "ccc#c", anchors: "package=2 import=0",
		tokens:   "n@2:package n@2:p n@3:class n@3:Actual n@5:val n@5:probe o@5:= d@5:1",
		comments: "0-34,58-82",
		want:     [3]familyOutcome{differs(".....", "ccc#c package=0 import=0", "shebang not modelled: its { hides the package line from the anchors (t2030)"), differs(".....", "o@1:# o@1:! o@1:/ n@1:usr o@1:/ n@1:bin o@1:/ n@1:env o@1:- n@1:S n@1:kotlin o@1:- n@1:J o@1:- n@1:Dtag o@1:= o@1:{ n@2:package n@2:p n@3:class n@3:Actual n@5:val n@5:probe o@5:= d@5:1", "shebang not modelled: its { hides the package clause and every declaration from scanKotlin (t2030)"), modelled},
	},
	{
		name: "shebang_paren", rule: "SHEBANG_COMMENT holding (",
		src:  "#!/usr/bin/env -S kotlin -J-Dtag=(\npackage p\nclass Actual\n// probe: a real comment\nval probe = 1\n",
		open: ".....", classes: "ccc#c", anchors: "package=2 import=0",
		tokens:   "n@2:package n@2:p n@3:class n@3:Actual n@5:val n@5:probe o@5:= d@5:1",
		comments: "0-34,58-82",
		want:     [3]familyOutcome{modelled, differs(".....", "o@1:# o@1:! o@1:/ n@1:usr o@1:/ n@1:bin o@1:/ n@1:env o@1:- n@1:S n@1:kotlin o@1:- n@1:J o@1:- n@1:Dtag o@1:= o@1:( n@2:package n@2:p n@3:class n@3:Actual n@5:val n@5:probe o@5:= d@5:1", "shebang not modelled: its ( hides every declaration from scanKotlin (t2030)"), modelled},
	},
	{
		name: "shebang_plain", rule: "SHEBANG_COMMENT",
		src:  "#!/usr/bin/env kotlin\n// probe: a real comment\nval probe = 1\n",
		open: "...", classes: "c#c", anchors: "package=0 import=0",
		tokens:   "n@3:val n@3:probe o@3:= d@3:1",
		comments: "0-21,22-46",
		want:     [3]familyOutcome{modelled, differs("...", "o@1:# o@1:! o@1:/ n@1:usr o@1:/ n@1:bin o@1:/ n@1:env n@1:kotlin n@3:val n@3:probe o@3:= d@3:1", "shebang not modelled: its line is read as code tokens (t2030)"), modelled},
	},
	{
		name: "shebang_slash_star", rule: "SHEBANG_COMMENT holding /*",
		src:  "#!/usr/bin/env -S kotlin -cp lib/*\n// probe: a real comment\nval probe = 1\n",
		open: "...", classes: "c#c", anchors: "package=0 import=0",
		tokens:   "n@3:val n@3:probe o@3:= d@3:1",
		comments: "0-34,35-59",
		want:     [3]familyOutcome{refuses("shebang not modelled: its /* opens a comment that never closes (t2030)"), refuses("shebang not modelled: its /* opens a comment that never closes (t2030)"), modelled},
	},
	{
		name: "short_template_backticked", rule: "SHORT_TEMPLATE_ENTRY + ESCAPED_IDENTIFIER in STRING",
		src:  "val s = \"$`a\"b`\"\n// probe: a real comment\nval probe = 1\n",
		open: "...", classes: "c#c", anchors: "package=0 import=0",
		tokens:   "n@1:val n@1:s o@1:= n`@1:a\"b S@1: n@3:val n@3:probe o@3:= d@3:1",
		comments: "17-41",
		want:     [3]familyOutcome{modelled, modelled, modelled},
	},
	{
		name: "short_template_backticked_raw", rule: "SHORT_TEMPLATE_ENTRY + ESCAPED_IDENTIFIER in RAW_STRING",
		src:  "val r = \"\"\"$`c//d`\"\"\"\n// probe: a real comment\nval probe = 1\n",
		open: "...", classes: "c#c", anchors: "package=0 import=0",
		tokens:   "n@1:val n@1:r o@1:= n`@1:c//d S@1: n@3:val n@3:probe o@3:= d@3:1",
		comments: "22-46",
		want:     [3]familyOutcome{modelled, modelled, modelled},
	},
	{
		name: "short_template_ident", rule: "SHORT_TEMPLATE_ENTRY",
		src:  "val s = \"$name.$this and $x\"\n// probe: a real comment\nval probe = 1\n",
		open: "...", classes: "c#c", anchors: "package=0 import=0",
		tokens:   "n@1:val n@1:s o@1:= n@1:name n@1:this n@1:x S@1: n@3:val n@3:probe o@3:= d@3:1",
		comments: "29-53",
		want:     [3]familyOutcome{modelled, modelled, modelled},
	},
	{
		name: "single_dollar_prefix", rule: "{INTERPOLATION}?\\\" with one $",
		src:  "val s = $\"a\"\n// probe: a real comment\nval probe = 1\n",
		open: "...", classes: "c#c", anchors: "package=0 import=0",
		tokens:   "n@1:val n@1:s o@1:= o@1:$ s@1:a n@3:val n@3:probe o@3:= d@3:1",
		comments: "13-37",
		want:     [3]familyOutcome{modelled, refuses("a $-prefixed string fails closed in deps (t1980), a single $ included"), refuses("a $-prefixed string fails closed in deps (t1975), a single $ included")},
	},
	{
		name: "string_content_operators", rule: "STRING content that looks like operators",
		src:  "val dot = \".\"\nval br = \"]\"\nval gt = \">\"\nval sep = \"::\"\nclass After\n",
		open: ".....", classes: "ccccc", anchors: "package=0 import=0",
		tokens:   "n@1:val n@1:dot o@1:= s@1:. n@2:val n@2:br o@2:= s@2:] n@3:val n@3:gt o@3:= s@3:> n@4:val n@4:sep o@4:= s@4::: n@5:class n@5:After",
		comments: "",
		want:     [3]familyOutcome{modelled, modelled, modelled},
	},
	{
		name: "string_template_nested", rule: "LONG_TEMPLATE_ENTRY with nested strings",
		src:  "val s = \"${f(\"}\")} and ${ m[\"k\"] }\"\n// probe: a real comment\nval probe = 1\n",
		open: "...", classes: "c#c", anchors: "package=0 import=0",
		tokens:   "n@1:val n@1:s o@1:= n@1:f o@1:( s@1:} o@1:) n@1:m o@1:[ s@1:k o@1:] S@1: n@3:val n@3:probe o@3:= d@3:1",
		comments: "36-60",
		want:     [3]familyOutcome{modelled, modelled, modelled},
	},
	{
		name: "template_comment", rule: "a comment inside LONG_TEMPLATE_ENTRY",
		src:  "val s = \"${ /* \"*/ 1 }\"\n// probe: a real comment\nval probe = 1\n",
		open: "...", classes: "c#c", anchors: "package=0 import=0",
		tokens:   "n@1:val n@1:s o@1:= d@1:1 S@1: n@3:val n@3:probe o@3:= d@3:1",
		comments: "12-18,24-48",
		want:     [3]familyOutcome{modelled, modelled, modelled},
	},
	{
		name: "template_lambda_braces", rule: "LONG_TEMPLATE_ENTRY brace depth",
		src:  "val s = \"${ xs.map { \"}\" }.size }\"\n// probe: a real comment\nval probe = 1\n",
		open: "...", classes: "c#c", anchors: "package=0 import=0",
		tokens:   "n@1:val n@1:s o@1:= n@1:xs o@1:. n@1:map o@1:{ s@1:} o@1:} o@1:. n@1:size S@1: n@3:val n@3:probe o@3:= d@3:1",
		comments: "35-59",
		want:     [3]familyOutcome{modelled, modelled, modelled},
	},
	{
		name: "template_multiline", rule: "LONG_TEMPLATE_ENTRY across lines",
		src:  "val s = \"${\n    f(1) // a comment inside the template\n}\"\n// probe: a real comment\nval probe = 1\n",
		open: ".oo..", classes: "ccc#c", anchors: "package=0 import=0",
		tokens:   "n@1:val n@1:s o@1:= n@2:f o@2:( d@2:1 o@2:) S@1: n@5:val n@5:probe o@5:= d@5:1",
		comments: "21-53,57-81",
		want:     [3]familyOutcome{modelled, modelled, modelled},
	},
}

func TestKotlinFamilyConstructs(t *testing.T) {
	for _, c := range kotlinFamilyCases {
		real := [3]string{c.classes + " " + c.anchors, c.tokens, ""}
		if c.open != "" {
			real[2] = familyBlank(t, c.src, c.comments)
		}
		for i, l := range familyLexers {
			w := c.want[i]
			acc, open, proj := l.accepts(c.src), familyOpen(c.src, l.accepts), l.project(c.src)
			fail := func(got, want string) {
				t.Errorf("%s: %s %s, want %s — a Kotlin-family lexer changed how it reads %s; "+
					"model it in all three lexers or pin the divergence in kotlinFamilyCases (t1992)",
					c.name, l.name, got, want, c.rule)
			}
			switch {
			case w.refuses:
				if acc {
					fail("accepts the file", "refuses ("+w.why+")")
				}
			case w.open != "" || w.project != "":
				if !acc {
					fail("refuses the file", "the pinned divergence ("+w.why+")")
				} else if open != w.open || proj != w.project {
					fail(strconv.Quote(open)+" "+strconv.Quote(proj), "the pinned divergence "+
						strconv.Quote(w.open)+" "+strconv.Quote(w.project)+" ("+w.why+")")
				}
			case c.open == "":
				t.Errorf("%s: %s is marked modelled, but the real lexer rejects the source", c.name, l.name)
			default:
				switch {
				case !acc:
					fail("refuses the file", "modelled")
				case open != c.open:
					fail("line-start view "+strconv.Quote(open), "modelled: "+strconv.Quote(c.open))
				case proj != real[i]:
					fail(strconv.Quote(proj), "modelled: "+strconv.Quote(real[i]))
				}
			}
		}
	}
}

// kotlinFamilyCorpusKnown pins every fixture on which the three lexers
// disagree, by path, with familyCorpusView's rendering of all three.
var kotlinFamilyCorpusKnown = map[string]struct{ view, why string }{
	"../annot/testdata/conformance/kotlin/multidollar_comment_desync.kt.in": {"annot=........oo.. ktLex=refuses kts=refuses", familyMultiDollar},
	"../annot/testdata/conformance/kotlin/multidollar_interpolation.kt.in":  {"annot=....... ktLex=refuses kts=refuses", familyMultiDollar},
	"../annot/testdata/conformance/kotlin/multidollar_literal_brace.kt.in":  {"annot=...oo... ktLex=refuses kts=refuses", familyMultiDollar},
	"../annot/testdata/conformance/kotlin/multidollar_quote_boundary.kt.in": {"annot=....oo.o.. ktLex=refuses kts=refuses", familyMultiDollar},
}

const familyMultiDollar = "multi-dollar strings: annot models them (t1990), deps fails closed on them (t1975, t1980)"

// kotlinFamilyCorpusFloor is the number of Kotlin fixtures the walk found when
// t1992 measured it: fewer means the corpus moved and the test lost its input.
const kotlinFamilyCorpusFloor = 71

// familyCorpusView renders what the three lexers make of src — each one's
// line-start view, or "refuses" — and whether they agree.
func familyCorpusView(src string) (view string, agree bool) {
	parts := make([]string, len(familyLexers))
	agree = true
	for i, l := range familyLexers {
		v := "refuses"
		if l.accepts(src) {
			v = familyOpen(src, l.accepts)
		}
		parts[i] = l.name + "=" + v
		if i > 0 && v != parts[0][len(familyLexers[0].name)+1:] {
			agree = false
		}
	}
	return strings.Join(parts, " "), agree
}

func TestKotlinFamilyCorpus(t *testing.T) {
	var files []string
	for _, root := range []string{"testdata", filepath.Join("..", "annot", "testdata")} {
		err := filepath.WalkDir(root, func(p string, d fs.DirEntry, err error) error {
			if err != nil {
				return err
			}
			if !d.IsDir() && (strings.HasSuffix(p, ".kt.in") || strings.HasSuffix(p, ".kts.in")) {
				files = append(files, filepath.ToSlash(p))
			}
			return nil
		})
		if err != nil {
			t.Fatal(err)
		}
	}
	if len(files) < kotlinFamilyCorpusFloor {
		t.Fatalf("found %d Kotlin fixtures, want at least %d: the corpus moved", len(files), kotlinFamilyCorpusFloor)
	}
	seen := map[string]bool{}
	for _, p := range files {
		data, err := os.ReadFile(p)
		if err != nil {
			t.Fatal(err)
		}
		view, agree := familyCorpusView(string(data))
		known, pinned := kotlinFamilyCorpusKnown[p]
		seen[p] = pinned
		switch {
		case !pinned && !agree:
			t.Errorf("%s: the Kotlin-family lexers disagree: %s — a lexer changed how it reads a construct "+
				"in this file; model it in all three lexers, or pin the divergence in kotlinFamilyCases and "+
				"kotlinFamilyCorpusKnown (t1992)", p, view)
		case pinned && agree:
			t.Errorf("%s: the Kotlin-family lexers now agree (%s); drop its kotlinFamilyCorpusKnown pin (t1992)", p, view)
		case pinned && view != known.view:
			t.Errorf("%s: the Kotlin-family lexers now read %s, pinned %s (%s); update the pin, or model the "+
				"construct in all three lexers (t1992)", p, view, known.view, known.why)
		}
	}
	for p := range kotlinFamilyCorpusKnown {
		if !seen[p] {
			t.Errorf("%s: pinned in kotlinFamilyCorpusKnown, but no such fixture; drop the pin (t1992)", p)
		}
	}
}
