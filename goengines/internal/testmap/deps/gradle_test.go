package deps

import (
	"fmt"
	"slices"
	"testing"
)

// A /* or // inside a string literal is not a comment: the task's
// reproducing fixture, plus a Kotlin DSL module whose raw string ends in a
// backslash (no escapes in a Kotlin raw string — routed by kindOf).
func TestGradleCommentInString(t *testing.T) {
	r := repo(t, map[string]string{
		"settings.gradle":  "include ':app', ':lib', ':kts'\n",
		"lib/build.gradle": "plugins { id 'java' }\n",
		"app/build.gradle": "android {\n" +
			"    packaging { resources { excludes += '/META-INF/*' } }\n" +
			"}\n" +
			"dependencies {\n" +
			"    implementation project(':lib')\n" +
			"}\n" +
			"tasks.register('docs') { inputs.files(fileTree('d') { include '*/x.md' }) }\n",
		"app/src/main/kotlin/A.kt": "package com.x\n\nclass A\n",
		"kts/build.gradle.kts": lines(
			`val p = """C:\"""`,
			`val g = """**/*.kt"""`,
			`dependencies { implementation(project(":lib")) }`,
			`val h = "*/"`,
		),
	})
	g := scanRepo(t, r)
	if m, _ := g.ModuleOf("app/src/main/kotlin/A.kt"); !slices.Equal(m.Deps, []string{":lib"}) {
		t.Errorf(":app deps = %v", m.Deps)
	}
	requireEdge(t, g, "app/src/main/kotlin/A.kt", "lib/build.gradle", "", "module-build")
	for _, m := range g.Modules() {
		if m.Name == ":kts" && !slices.Equal(m.Deps, []string{":lib"}) {
			t.Errorf(":kts deps = %v", m.Deps)
		}
	}
	for _, p := range []string{"app/build.gradle", "kts/build.gradle.kts"} {
		if o := g.Opaque(p); o != "" {
			t.Errorf("%s opaque %q", p, o)
		}
	}
	if ps := g.Problems(); len(ps) != 0 {
		t.Errorf("problems %v", ps)
	}
}

// A script the lexer cannot read is visibly widened, never silently read.
func TestGradleUntokenizableWidens(t *testing.T) {
	r := repo(t, map[string]string{
		"settings.gradle.kts": `include(":a", ":b", ":c")` + "\n",
		"a/build.gradle.kts": lines(
			`val a = $$"""${/*}"""`,
			`dependencies { implementation(project(":b")) }`,
			`val b = """*/}"""`,
		),
		"b/build.gradle.kts": "",
		"c/build.gradle.kts": "",
	})
	g := scanRepo(t, r)
	for _, m := range g.Modules() {
		if m.Name == ":a" && !slices.Equal(m.Deps, []string{":", ":b", ":c"}) {
			t.Errorf(":a deps = %v", m.Deps)
		}
	}
	if o := g.Opaque("a/build.gradle.kts"); o != "gradle-dynamic" {
		t.Errorf("opaque %q", o)
	}
	if !slices.Contains(g.Problems(), Problem{Path: "a/build.gradle.kts", Reason: "gradle-dynamic: untokenizable"}) {
		t.Errorf("problems %v", g.Problems())
	}
}

// include is a settings statement: in a build file it is a fileTree / copy
// pattern, so even a GString one does not make the module dynamic.
func TestGradleBuildFileIncludeIsNotModule(t *testing.T) {
	r := repo(t, map[string]string{
		"settings.gradle":  lines(`include ':app', ':lib'`, `include "${extra}"`),
		"lib/build.gradle": "plugins { id 'java' }\n",
		"app/build.gradle": lines(
			`copy {`,
			`    include "${dir}/*.md"`,
			`}`,
			`dependencies { implementation project(':lib') }`,
		),
		"app/src/main/kotlin/A.kt": "package a\n",
	})
	g := scanRepo(t, r)
	if m, _ := g.ModuleOf("app/src/main/kotlin/A.kt"); !slices.Equal(m.Deps, []string{":lib"}) {
		t.Errorf(":app deps = %v", m.Deps)
	}
	if o := g.Opaque("app/build.gradle"); o != "" {
		t.Errorf("app/build.gradle opaque %q", o)
	}
	if o := g.Opaque("settings.gradle"); o != "gradle-dynamic" {
		t.Errorf("settings.gradle opaque %q", o)
	}
	want := []Problem{{Path: "settings.gradle", Reason: "gradle-dynamic: include"}}
	if ps := g.Problems(); !slices.Equal(ps, want) {
		t.Errorf("problems %v, want %v", ps, want)
	}
}

// gradleLexCase pins comment blanking for one literal form. refs are the
// ProjectRefs names, dynamic the Dynamic entries as "name:line".
type gradleLexCase struct {
	name     string
	kts      bool
	src      string
	refs     []string
	includes []string // checked when non-nil
	dynamic  []string
	line     int // checked when > 0: the line of refs[0]
}

const (
	lexURLTail  = `; def u = 'https://x'; dependencies { implementation project(':lib') }`
	lexGoneTail = ` // it's project(':gone')`
)

// gradleLexCases cover every literal form of both dialects.
var gradleLexCases = []gradleLexCase{
	{name: "glob-single", src: lines(
		`android { packaging { resources { excludes += '/META-INF/*' } } }`,
		`dependencies { implementation project(':lib') }`,
		`tasks.register('docs') { inputs.files(fileTree('d') { include '*/x.md' }) }`,
	), refs: []string{":lib"}},
	{name: "glob-double", src: lines(
		`android { packaging { resources { excludes += "/META-INF/*" } } }`,
		`dependencies { implementation project(":lib") }`,
		`def docs = "*/x.md"`,
	), refs: []string{":lib"}},
	{name: "glob-kts", kts: true, src: lines(
		`val sources = fileTree("src") { include("**/*.kt") }`,
		`dependencies { implementation(project(":lib")) }`,
		`val docs = "*/x"`,
	), refs: []string{":lib"}},
	{name: "url-line", src: lines(
		`repositories { maven { url 'https://jitpack.io' } }; dependencies { implementation project(':lib') }`,
	), refs: []string{":lib"}},
	{name: "thinking_app-glob-pair", src: lines(
		`        rootProject.fileTree('app/src/test/screenshots') {`,
		`            include '*/*_REVIEW.md'`,
		`            include '*/evidence/t53_*/LEDGER_RECONCILE.tsv'`,
		`        },`,
	), includes: []string{"*/*_REVIEW.md", "*/evidence/t53_*/LEDGER_RECONCILE.tsv"}},
	{name: "real-comments", src: lines(
		`/* implementation project(':gone') */`,
		`// implementation project(':gone2')`,
		`// don't project(':gone3')`,
		`dependencies { /* it's */ implementation project(':kept') }`,
	), refs: []string{":kept"}},
	{name: "escaped-quote", src: lines(
		`def a = 'it\'s /*'`,
		`implementation project(':lib')`,
		`def b = '*/x'`,
	), refs: []string{":lib"}},
	{name: "template-nested-string", src: lines(
		`implementation "${a.replace("//", "/")}"; implementation project(':lib')`,
	), refs: []string{":lib"}},
	{name: "triple-double", src: lines(
		`def s = """a /* b`,
		` c"""`,
		`implementation project(':lib')`,
		`def t = '*/'`,
	), refs: []string{":lib"}, line: 3},
	{name: "triple-single", src: lines(
		`def s = '''a /* b`,
		` c'''`,
		`implementation project(':lib')`,
		`def t = '*/'`,
	), refs: []string{":lib"}, line: 3},
	{name: "dollar-slashy", src: lines(
		`def a = $/META-INF/*/$`,
		`dependencies { implementation project(':lib') }`,
		`def b = $/*/x/$`,
	), refs: []string{":lib"}},
	{name: "dollar-slashy-escape", src: lines(`def c = $/a$/$/$` + lexURLTail), refs: []string{":lib"}},
	{name: "slashy-escaped-slash", src: lines(
		`def r = /META-INF\/*/`,
		`implementation project(':lib')`,
		`def q = /x*/`,
	), refs: []string{":lib"}},
	{name: "slashy-after-tilde", src: lines(`def r = ~/it's/` + lexURLTail), refs: []string{":lib"}},
	{name: "slashy-after-plus", src: lines(`def label = 'prefix' + /it's/` + lexURLTail), refs: []string{":lib"}},
	{name: "slashy-after-minus", src: lines(`def m = 'prefix' - /it's/` + lexURLTail), refs: []string{":lib"}},
	{name: "slashy-after-in", src: lines(`if (v in /it's/) {}` + lexURLTail), refs: []string{":lib"}},
	{name: "threadsafe-keyword", src: lines(`threadsafe /it's/` + lexURLTail), refs: []string{":lib"}},
	{name: "division-ident", src: lines(`def n = total / 2` + lexGoneTail)},
	{name: "division-inc", src: lines(`def k = i++ / 2` + lexGoneTail)},
	{name: "division-dec", src: lines(`def j = i-- / 2` + lexGoneTail)},
	{name: "division-paren", src: lines(`def m = (a) / b` + lexGoneTail)},
	{name: "division-this", src: lines(`def t = this / 2` + lexGoneTail)},
	{name: "val-is-identifier", src: lines(
		`def val = 4`,
		`def n = val / 2`,
		`def a = 'https://x'; def b = 'https://y'; dependencies { implementation project(':lib') }`,
	), refs: []string{":lib"}},
	// yield, record, sealed and permits are keywords in Groovy 4 only: a /
	// after one does not lex the same under Gradle 8 and Gradle 9.
	{name: "version-word-division", src: lines(`def record = 4`, `def n = record / 2`+lexGoneTail),
		refs: []string{":gone"}, dynamic: []string{"untokenizable:2"}},
	{name: "version-word-slashy", src: lines(`yield /it's/` + lexURLTail),
		refs: []string{":lib"}, dynamic: []string{"untokenizable:1"}},
	{name: "newline-top-level", src: lines(
		`def n = 1`,
		`/it's/.each { println it }`+lexURLTail,
	), refs: []string{":lib"}},
	{name: "newline-after-line-comment", src: lines(
		`def n = 1 // one`,
		`/it's/.each { println it }`+lexURLTail,
	), refs: []string{":lib"}},
	{name: "newline-in-block", src: lines(
		`tasks.register('x') {`,
		`    def n = 1`,
		`    /it's/.each { println it }`+lexURLTail,
		`}`,
	), refs: []string{":lib"}},
	{name: "newline-in-try-paren", src: lines(
		`try (def r = 1`,
		`/it's/.size()) {}; def u = 'https://x'; implementation project(':lib')`,
	), refs: []string{":lib"}},
	{name: "hidden-newline-paren", src: lines(`def n = foo(1`, `    / 2)`+lexGoneTail)},
	{name: "hidden-newline-bracket", src: lines(`def l = [1`, `    / 2]`+lexGoneTail)},
	{name: "hidden-newline-continuation", src: lines(`def n = 1 \`, `    / 2`+lexGoneTail)},
	{name: "hidden-block-comment", src: lines(`def n = 1 /* c */ / 2` + lexGoneTail)},
	{name: "line-continuation", src: lines(`def a = 1 + \`, `2`)},
	{name: "stray-backslash", src: lines(`def a = foo \ bar`), dynamic: []string{"untokenizable:1"}},
	{name: "shebang", src: lines(`#!/usr/bin/env groovy`, `implementation project(':lib')`), refs: []string{":lib"}},
	// Groovy's SH_COMMENT is every leading #! line; a Kotlin script has one.
	{name: "shebang-groovy-run", src: lines(`#!/usr/bin/env groovy`, `#! project(':gone')`, `implementation project(':lib')`), refs: []string{":lib"}},
	{name: "kts-shebang-second-line", kts: true, src: lines(`#!/usr/bin/env kotlin`, `#! project(":kept")`), refs: []string{":kept"}},
	// kotlinc strips the byte-order mark, so the header after it is still one.
	{name: "kts-shebang-bom", kts: true, src: "\ufeff" + lines(`#!/usr/bin/env -S kotlin -cp lib/*`,
		`dependencies { implementation(project(":a")) }`), refs: []string{":a"}},
	{name: "kts-shebang-crlf", kts: true, src: "#!/x {\r\n// project(\":c\")\r\ndependencies { implementation(project(\":a\")) }\r\n", refs: []string{":a"}},
	// kotlinc reads a lone CR as a newline; the // rule here ends only at
	// \n, so the script fails closed and is read whole.
	{name: "kts-lone-cr", kts: true, src: "// project(\":c\")\rdependencies { implementation(project(\":a\")) }\r",
		refs: []string{":c", ":a"}, dynamic: []string{"untokenizable:1"}},
	{name: "kts-lone-cr-shebang", kts: true, src: "#!/x {\r// project(\":c\")\rdependencies { implementation(project(\":a\")) }\r",
		refs: []string{":c", ":a"}, dynamic: []string{"untokenizable:1"}},
	{name: "kts-lone-cr-final", kts: true, src: "dependencies { implementation(project(\":a\")) }\n// c\r",
		refs: []string{":a"}, dynamic: []string{"untokenizable:2"}},
	{name: "kts-raw-string-backslash", kts: true, src: lines(
		`val p = """C:\"""`,
		`val g = """**/*.kt"""`,
		`dependencies { implementation(project(":lib")) }`,
		`val h = "*/"`,
	), refs: []string{":lib"}},
	{name: "kts-nested-comment", kts: true, src: lines(
		`/* a /* b */ implementation(project(":gone")) */`,
		`dependencies { implementation(project(":kept")) }`,
	), refs: []string{":kept"}},
	{name: "kts-backticked-name", kts: true, src: "val `it's` = 1\n" +
		`val u = "https://x"; dependencies { implementation(project(":lib")) }` + "\n",
		refs: []string{":lib"}},
	{name: "kts-char-literals", kts: true, src: lines(
		`val u = "https://x"; val q = '"'; dependencies { implementation(project(":lib")) }`,
	), refs: []string{":lib"}},
	{name: "kts-multi-dollar", kts: true, src: lines(
		`val a = $$"""${/*}"""`,
		`dependencies { implementation(project(":lib")) }`,
		`val b = """*/}"""`,
	), refs: []string{":lib"}, dynamic: []string{"untokenizable:1"}},
	{name: "kts-multi-dollar-single-line", kts: true, src: lines(`val j = $$"{x}"`), dynamic: []string{"untokenizable:1"}},
	// $`name` is a short template whose name may hold quotes: read as text,
	// they closed the string, and the /* after it blanked the deps line.
	{name: "kts-short-template-backticks", kts: true, src: lines(
		"val `q\"` = 1",
		"val s = \"$`q\"`\" + \"`/*\"",
		`dependencies { implementation(project(":lib")) }`,
		`val t = 1 // */`,
	), refs: []string{":lib"}},
	{name: "kts-short-template-raw", kts: true, src: lines(
		"val r = \"\"\"$`x\"\"\"`\"\"\" + \"\"\"`/*\"\"\"",
		`dependencies { implementation(project(":lib")) }`,
		`val t = 1 // */`,
	), refs: []string{":lib"}},
	{name: "kts-short-template-unclosed", kts: true, src: lines(
		"val s = \"$`x\"; val u = \"https://x\"; dependencies { implementation(project(\":lib\")) }",
	), refs: []string{":lib"}},
	{name: "unclosed-block-comment", src: lines(
		`// project(':c')`,
		`implementation project(':a')`,
		`/* never closed`,
	), refs: []string{":c", ":a"}, dynamic: []string{"untokenizable:3"}},
	{name: "unclosed-string", src: lines(
		`// project(':c')`,
		`def s = 'oops`,
		`implementation project(':a')`,
	), refs: []string{":c", ":a"}, dynamic: []string{"untokenizable:2"}},
	{name: "unclosed-dollar-slashy", src: lines(
		`// project(':c')`,
		`def s = $/never closed`,
		`implementation project(':a')`,
	), refs: []string{":c", ":a"}, dynamic: []string{"untokenizable:2"}},
}

func TestScanGradleStringAwareComments(t *testing.T) {
	for _, c := range gradleLexCases {
		t.Run(c.name, func(t *testing.T) {
			g := scanGradle([]byte(c.src), c.kts).Gradle
			var refs, includes, dynamic []string
			for _, r := range g.ProjectRefs {
				refs = append(refs, r.Name)
			}
			for _, i := range g.Includes {
				includes = append(includes, i.Name)
			}
			for _, d := range g.Dynamic {
				dynamic = append(dynamic, fmt.Sprintf("%s:%d", d.Name, d.Line))
			}
			if !slices.Equal(refs, c.refs) {
				t.Errorf("refs %q, want %q", refs, c.refs)
			}
			if c.includes != nil && !slices.Equal(includes, c.includes) {
				t.Errorf("includes %q, want %q", includes, c.includes)
			}
			if !slices.Equal(dynamic, c.dynamic) {
				t.Errorf("dynamic %q, want %q", dynamic, c.dynamic)
			}
			if c.line > 0 && (len(g.ProjectRefs) == 0 || g.ProjectRefs[0].Line != c.line) {
				t.Errorf("refs %+v, want line %d", g.ProjectRefs, c.line)
			}
		})
	}
}
