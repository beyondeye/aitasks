package deps

import (
	"slices"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

func TestKotlinResolution(t *testing.T) {
	const test = "app/src/test/kotlin/com/x/ui/ScreenTest.kt"
	r := repo(t, map[string]string{
		"app/src/main/kotlin/com/x/ui/Screen.kt": "package com.x.ui\n\nclass Screen\n",
		"app/src/main/kotlin/com/x/ui/Model.kt": lines(
			`package com.x.ui`,
			`class Model`,
			`object Holder { val LIMIT = 1 }`,
			`enum class Color { RED }`,
		),
		"app/src/main/kotlin/com/x/data/Repo.kt": lines(
			`package com.x.data`,
			`class Repo`,
			`fun topFun() = 1`,
			`fun String.ext() = length`,
			`typealias Alias = Repo`,
		),
		"app/src/main/kotlin/com/x/util/Util.kt":      "package com.x.util\n\nfun util() = 1\n",
		"app/src/main/java/com/x/data/JavaThing.java": "package com.x.data;\n\npublic class JavaThing {}\n",
		test: lines(
			`package com.x.ui`,
			``,
			`import com.x.data.Repo`,
			`import com.x.data.topFun as tf`,
			`import com.x.data.JavaThing`,
			`import com.x.data.Nope`,
			`import com.x.util.*`,
			`import com.x.ui.Holder.LIMIT`,
			`import kotlin.math.max`,
			``,
			`class ScreenTest {`,
			`    fun t() = com.x.util.util() + tf() + LIMIT`,
			`}`,
		),
	})
	g := scanRepo(t, r)
	requireEdge(t, g, test, "app/src/main/kotlin/com/x/data/Repo.kt", Import, "")
	requireEdge(t, g, test, "app/src/main/java/com/x/data/JavaThing.java", Import, "import")
	requireEdge(t, g, test, "app/src/main/kotlin/com/x/util/Util.kt", Import, "fq-ref")
	requireEdge(t, g, test, "app/src/main/kotlin/com/x/ui/Model.kt", Import, "import")
	requireEdge(t, g, test, "app/src/main/kotlin/com/x/ui/Screen.kt", "", "same-package")
	f, _ := g.Facts(test)
	if !slices.Contains(f.Unresolved, "com.x.data.Nope") {
		t.Errorf("unresolved: %v", f.Unresolved)
	}
	if g.Opaque("app/src/main/java/com/x/data/JavaThing.java") != "java-unscanned" {
		t.Error("java file not opaque")
	}
	repoFacts, _ := g.Facts("app/src/main/kotlin/com/x/data/Repo.kt")
	var names []string
	for _, s := range repoFacts.Symbols {
		names = append(names, s.Kind+":"+s.Name)
	}
	if want := []string{"class:Repo", "fun:topFun", "fun:ext", "typealias:Alias"}; !slices.Equal(names, want) {
		t.Errorf("symbols %v, want %v", names, want)
	}
}

// Primary-constructor parameters are members of their class, not top-level
// declarations of the package: a keyword declares only outside every brace
// and parenthesis. Every case ends with a real top-level declaration after
// the constructor, so a parenthesis counter that never closes cannot pass by
// dropping everything.
func TestKotlinCtorParamsAreNotTopLevel(t *testing.T) {
	for name, tc := range map[string]struct {
		src  string
		want []string
	}{
		"data-class": {lines(`package x`, `data class LoginState(val email: String, var busy: Boolean = false)`, `fun after() = 1`),
			[]string{"class:LoginState", "fun:after"}},
		"enum": {lines(`package x`, `enum class Tab(val label: String) {`, `    HOME("home");`, `    val upper get() = label.uppercase()`, `}`, `val after = 1`),
			[]string{"class:Tab", "val:after"}},
		"inject-constructor": {lines(`package x`, `class LoginViewModel @Inject constructor(private val repo: Repo) : ViewModel()`, `typealias After = LoginViewModel`),
			[]string{"class:LoginViewModel", "typealias:After"}},
		"multi-line": {lines(`package x`, `class Form(`, `    private val mapper: Mapper,`, `    var inProgress: Boolean = false,`, `    val onDone: (Int) -> Unit = { val x = it },`, `) : Base(mapper)`, `object After`),
			[]string{"class:Form", "object:After"}},
		// '<' and '>' are comparison operators too: they never nest.
		"comparison": {lines(`package x`, `val less = 1 < 2`, `class After(val p: Int)`),
			[]string{"val:less", "class:After"}},
	} {
		var got []string
		for _, s := range scanKotlin([]byte(tc.src)).Symbols {
			got = append(got, s.Kind+":"+s.Name)
		}
		if !slices.Equal(got, tc.want) {
			t.Errorf("%s: symbols %v, want %v", name, got, tc.want)
		}
	}
}

// End to end through --from-body: a member body's local `email` gets no ref to
// a file whose constructor has an `email` parameter, and the class the body
// does name still resolves. `email` comes first because FromBody keeps one ref
// per file (the first symbol that reaches it), so pre-fix the wrong symbol
// wins.
func TestKotlinFromBodyIgnoresCtorParams(t *testing.T) {
	r := repo(t, map[string]string{
		"aitestmap/.keep":      "",
		"src/a/LoginState.kt":  "package com.x.a\n\ndata class LoginState(val email: String, var busy: Boolean = false)\n",
		"tests/a/LoginTest.kt": lines(`package com.x.a`, ``, `// testmap:unit M`, `fun m() {`, `    val email = "x"`, `    println(LoginState(email))`, `}`),
	})
	if f, _ := scanRepo(t, r).Facts("src/a/LoginState.kt"); len(f.Symbols) != 1 || f.Symbols[0].Name != "LoginState" {
		t.Errorf("symbols %+v, want [LoginState]", f.Symbols)
	}
	refused, refs, _, err := FromBody(bg, r.Dir, registry.ID{Path: "tests/a/LoginTest.kt", Member: "M"},
		Options{Config: registry.Defaults(), Uncached: true})
	want := []BodyRef{{Source: "src/a/LoginState.kt", Symbol: "LoginState", Line: 6}}
	if err != nil || refused != "" || !slices.Equal(refs, want) {
		t.Fatalf("FromBody: refused %q refs %+v err %v, want %+v", refused, refs, err, want)
	}
}

// A fun / val / var is named by the identifier after its optional receiver
// type: whatever follows the name — a delegate (`by lazy`), an accessor
// (`get()`), the parameter list — is never read as the name. The control rows
// are forms the name walk already got right; they pin it to its old answers.
func TestKotlinDeclNameStopsAfterName(t *testing.T) {
	for name, tc := range map[string]struct {
		src  string
		want []string
		exts []string
	}{
		"lazy":             {`val retrofit by lazy { cache }`, []string{"val:retrofit"}, nil},
		"mutable-state":    {`var counter by mutableStateOf(0)`, []string{"var:counter"}, nil},
		"dotted-delegate":  {`val y by Delegates.notNull<Int>()`, []string{"val:y"}, nil},
		"ext-delegate":     {`val Foo.bar by lazy { 1 }`, []string{"val:bar"}, []string{"bar"}},
		"accessor":         {`val isEmpty get() = true`, []string{"val:isEmpty"}, nil},
		"star-receiver":    {`fun List<*>.firstOrBlank() = ""`, []string{"fun:firstOrBlank"}, []string{"firstOrBlank"}},
		"nested-args":      {`fun Map<String, List<Int>>.total() = 0`, []string{"fun:total"}, []string{"total"}},
		"arrow-arg":        {`fun Box<(Int) -> Unit>.run() = 0`, []string{"fun:run"}, []string{"run"}},
		"nullable-generic": {`fun <T> List<T>?.orEmpty2() = 0`, []string{"fun:orEmpty2"}, []string{"orEmpty2"}},
		// Controls.
		"typed":               {`val plain: Int = 1`, []string{"val:plain"}, nil},
		"type-param-receiver": {`fun <T> T.also2() = 0`, []string{"fun:also2"}, []string{"also2"}},
		"nullable-receiver":   {`fun Foo?.orDefault() = 0`, []string{"fun:orDefault"}, []string{"orDefault"}},
		// Redundant nullability is legal (`quest+`): every '?' is skipped.
		"double-nullable":    {`fun String??.f() = 1`, []string{"fun:f"}, []string{"f"}},
		"qualified-receiver": {`fun a.b.C.helper() = 0`, []string{"fun:helper"}, []string{"helper"}},
		"paren-receiver":     {lines(`fun (A).f() = 0`, `val after = 1`), []string{"val:after"}, nil},
		// A backticked `-` is an identifier: its '>' closes, unlike an arrow's.
		"backticked-minus-arg":   {"fun Box<`-`>.render() = 0", []string{"fun:render"}, []string{"render"}},
		"backticked-minus-bound": {"fun <T : `-`> T.render() = 0", []string{"fun:render"}, []string{"render"}},
	} {
		raw := scanKotlin([]byte(lines(`package x`, tc.src)))
		var got []string
		for _, s := range raw.Symbols {
			got = append(got, s.Kind+":"+s.Name)
		}
		if !slices.Equal(got, tc.want) || !slices.Equal(raw.Kt.Exts, tc.exts) {
			t.Errorf("%s: symbols %v exts %v, want %v exts %v", name, got, raw.Kt.Exts, tc.want, tc.exts)
		}
	}
}

// End to end: an import of a delegated property resolves to its declaring
// file as a static import, not a closure-only package fallback.
func TestKotlinDelegatedPropertyImport(t *testing.T) {
	r := repo(t, map[string]string{
		"src/b/Net.kt":  "package com.x.b\n\nprivate val cache = 1\nval retrofit by lazy { cache }\n",
		"src/c/User.kt": "package com.x.c\n\nimport com.x.b.retrofit\n\nfun u() = retrofit\n",
	})
	g := scanRepo(t, r)
	f, _ := g.Facts("src/b/Net.kt")
	var names []string
	for _, s := range f.Symbols {
		names = append(names, s.Kind+":"+s.Name)
	}
	if want := []string{"val:cache", "val:retrofit"}; !slices.Equal(names, want) {
		t.Errorf("symbols %v, want %v", names, want)
	}
	requireEdge(t, g, "src/c/User.kt", "src/b/Net.kt", Import, "import")
	if u, _ := g.Facts("src/c/User.kt"); slices.Contains(u.Unresolved, "com.x.b.retrofit") {
		t.Errorf("unresolved: %v", u.Unresolved)
	}
}

// An import of an undeclared name inside a repository package keeps the
// whole package reachable (closure-only), never nothing.
func TestKotlinPackageFallback(t *testing.T) {
	r := repo(t, map[string]string{
		"src/a/A.kt": "package p.a\n\nclass A\n",
		"src/a/B.kt": "package p.a\n\nclass B\n",
		"src/t/T.kt": "package p.t\n\nimport p.a.Missing\n\nclass T\n",
	})
	g := scanRepo(t, r)
	requireEdge(t, g, "src/t/T.kt", "src/a/A.kt", "", "package-fallback")
	requireEdge(t, g, "src/t/T.kt", "src/a/B.kt", "", "package-fallback")
}

func TestKotlinAndroidResKeys(t *testing.T) {
	files := map[string]string{
		"src/S.kt":               "package s\n\nfun f() = listOf(R.string.title, R.plurals.items, \"greeting\".localized())\n",
		"src/J.java":             "package s;\n",
		"res/values/strings.xml": "<resources/>\n",
	}
	off := scanRepo(t, repo(t, files))
	if f, _ := off.Facts("src/S.kt"); f.Keys != nil {
		t.Fatalf("keys without the opt-in: %v", f.Keys)
	}
	on := scanRepo(t, repo(t, files), func(o *Options) { o.Config.SymbolScanners = []string{AndroidRes} })
	if f, _ := on.Facts("src/S.kt"); !slices.Equal(f.Keys, []string{"greeting", "items", "title"}) {
		t.Fatalf("keys: %v", f.Keys)
	}
	if f, _ := on.Facts("src/J.java"); !slices.Equal(f.Keys, []string{"*"}) {
		t.Fatalf("java keys: %v", f.Keys)
	}
	cfg := registry.Defaults()
	cfg.SymbolScanners = []string{"nope"}
	if _, err := Scan(bg, repo(t, files).Dir, Options{Uncached: true, Config: cfg}); err == nil {
		t.Fatal("an unknown symbol scanner was accepted")
	}
}

func TestGradleModuleGraph(t *testing.T) {
	r := repo(t, map[string]string{
		"settings.gradle.kts": lines(
			`rootProject.name = "x"`,
			`include(":app", ":core", ":feature-auth")`,
			`project(":feature-auth").projectDir = file("modules/auth")`,
		),
		"app/build.gradle.kts": lines(
			`dependencies {`,
			`    implementation(project(":core"))`,
			`    implementation(projects.featureAuth)`,
			`}`,
		),
		"core/build.gradle.kts":               "plugins { kotlin(\"jvm\") }\n",
		"modules/auth/build.gradle.kts":       "dependencies {\n    api(project(\":core\"))\n}\n",
		"lib/extra/build.gradle":              "apply plugin: 'java'\n",
		"gradle.properties":                   "x=1\n",
		"gradle/libs.versions.toml":           "[versions]\n",
		"buildSrc/src/main/kotlin/D.kt":       "object D\n",
		"app/src/main/kotlin/a/A.kt":          "package a\n\nclass A\n",
		"modules/auth/src/main/kotlin/u/U.kt": "package u\n\nclass U\n",
	})
	g := scanRepo(t, r)
	var names []string
	for _, m := range g.Modules() {
		names = append(names, m.Name)
	}
	if want := []string{":", ":app", ":core", ":feature-auth", ":lib:extra"}; !slices.Equal(names, want) {
		t.Fatalf("modules %v, want %v", names, want)
	}
	if m, _ := g.ModuleOf("modules/auth/src/main/kotlin/u/U.kt"); m.Name != ":feature-auth" {
		t.Fatalf("ModuleOf follows the projectDir override: %+v", m)
	}
	if m, _ := g.ModuleOf("app/src/main/kotlin/a/A.kt"); !slices.Equal(m.Deps, []string{":core", ":feature-auth"}) {
		t.Fatalf("app deps: %+v", m)
	}
	const a = "app/src/main/kotlin/a/A.kt"
	for _, target := range []string{"app/build.gradle.kts", "core/build.gradle.kts", "modules/auth/build.gradle.kts"} {
		requireEdge(t, g, a, target, "", "module-build")
	}
	for _, target := range []string{"settings.gradle.kts", "gradle.properties", "gradle/libs.versions.toml", "buildSrc/src/main/kotlin/D.kt"} {
		requireEdge(t, g, a, target, "", "build-input")
	}
	requireNoEdge(t, g, a, "lib/extra/build.gradle")
	// The graph is immutable: what Modules and ModuleOf return are copies,
	// nested Deps included.
	for _, m := range g.Modules() {
		for i := range m.Deps {
			m.Deps[i] = "mutated"
		}
	}
	got, _ := g.ModuleOf(a)
	for i := range got.Deps {
		got.Deps[i] = "mutated"
	}
	if m, _ := g.ModuleOf(a); !slices.Equal(m.Deps, []string{":core", ":feature-auth"}) {
		t.Fatalf("a returned module aliases the graph: %+v", m)
	}
	if ms := g.Modules(); !slices.ContainsFunc(ms, func(m GradleModule) bool {
		return m.Name == ":app" && slices.Equal(m.Deps, []string{":core", ":feature-auth"})
	}) {
		t.Fatalf("a returned module aliases the graph: %+v", ms)
	}
}

// A dependency block the parse cannot read widens to every module.
func TestGradleDynamicDepsWiden(t *testing.T) {
	r := repo(t, map[string]string{
		"settings.gradle.kts":    `include(":a", ":b", ":c")` + "\n",
		"a/build.gradle.kts":     "dependencies { implementation(project(name)) }\n",
		"b/build.gradle.kts":     "",
		"c/build.gradle.kts":     "",
		"a/src/main/kotlin/A.kt": "package a\n",
	})
	g := scanRepo(t, r)
	if m, _ := g.ModuleOf("a/src/main/kotlin/A.kt"); !slices.Equal(m.Deps, []string{":", ":b", ":c"}) {
		t.Fatalf("deps %v", m.Deps)
	}
	if g.Opaque("a/build.gradle.kts") != "gradle-dynamic" || len(g.Problems()) == 0 {
		t.Fatalf("opaque %q problems %v", g.Opaque("a/build.gradle.kts"), g.Problems())
	}
}

// The DI fallback survives renaming: an import alias or a typealias of a DI
// annotation, and the multi-annotation form, still mark the file opaque.
func TestKotlinDIAliases(t *testing.T) {
	for name, src := range map[string]string{
		"import-alias": "package x\n\nimport javax.inject.Inject as Wire\n\nclass A @Wire constructor(val b: B)\n",
		"use-site":     "package x\n\nimport javax.inject.Inject as Wire\n\nclass A {\n    @field:Wire lateinit var b: B\n}\n",
		"typealias":    "package x\n\ntypealias Wire = javax.inject.Inject\n\nclass A @Wire constructor(val b: B)\n",
		"chained":      "package x\n\nimport dagger.Module as M\n\ntypealias Mod = M\n\n@Mod\nobject Bindings\n",
		"multi":        "package x\n\nimport javax.inject.Inject as Wire\nimport javax.inject.Named\n\nclass A {\n    @set:[Wire Named(\"b\")] var b: B? = null\n}\n",
	} {
		if got := scanKotlin([]byte(src)).Opaque; !slices.Contains(got, "di") {
			t.Errorf("%s: opaque %v, want di", name, got)
		}
	}
	for name, src := range map[string]string{
		"lookalike":     "package x\n\nannotation class Wired\n\nclass A @Wired constructor()\n",
		"non-di-alias":  "package x\n\nimport com.x.Marker as Tag\n\n@Tag\nclass A\n",
		"file-use-site": "@file:JvmName(\"A\")\npackage x\n\nclass A\n",
	} {
		if got := scanKotlin([]byte(src)).Opaque; slices.Contains(got, "di") {
			t.Errorf("%s: opaque %v, want no di", name, got)
		}
	}
	// Through a scan: the aliased construct is opaque in the graph.
	r := repo(t, map[string]string{
		"src/x/A.kt": "package x\n\nimport javax.inject.Inject as Wire\n\nclass A @Wire constructor(val b: B)\n",
		"src/x/B.kt": "package x\n\nclass B\n",
	})
	if got := scanRepo(t, r).Opaque("src/x/A.kt"); got != "di" {
		t.Fatalf("graph opaque %q, want di", got)
	}
}
