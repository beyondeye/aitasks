package deps

import (
	"slices"
	"strconv"
	"strings"
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
		// A type annotation's string argument is not a bracket.
		"string-gt-arg": {`fun Box<@Ann(">") Int>.render() = 0`, []string{"fun:render"}, []string{"render"}},
		"string-lt-arg": {`fun Box<@Ann("<") Int>.render() = 0`, []string{"fun:render"}, []string{"render"}},
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

// `fun interface X` declares X once, under its `fun`: the `interface` token
// after the keyword is part of that declaration, not a second one. A
// backticked name is an identifier, never a keyword — it neither opens a
// declaration nor forms the `fun interface` pair. Every row is compared
// exactly, so a phantom declaration fails as surely as a lost one.
func TestKotlinFunInterfaceDeclaredOnce(t *testing.T) {
	for name, tc := range map[string]struct {
		src  string
		want []string
	}{
		"fun-interface":    {`fun interface Listener { fun on() }`, []string{"fun:Listener"}},
		"modified-generic": {`public fun interface P<T> { fun on(t: T) }`, []string{"fun:P"}},
		"split-lines":      {lines(`fun`, `interface Q`), []string{"fun:Q"}},
		"escaped-fun":      {lines("val a = `fun`", `interface Y`), []string{"val:a", "interface:Y"}},
		"escaped-object":   {lines("val b = `object`", `fun g() = 1`), []string{"val:b", "fun:g"}},
		// A function named `interface`.
		"escaped-interface-name": {"fun `interface`() = 1", []string{"fun:interface"}},
		// Controls.
		"plain-interface":    {`interface Foo`, []string{"interface:Foo"}},
		"fun-then-interface": {lines(`fun f() = 1`, `interface I`), []string{"fun:f", "interface:I"}},
		"dotted-escaped-fun": {lines("val a = obj.`fun`", `interface Y`), []string{"val:a", "interface:Y"}},
		"escaped-val-name":   {"val `fun` = 1", []string{"val:fun"}},
	} {
		var got []string
		for _, s := range scanKotlin([]byte(lines(`package x`, tc.src))).Symbols {
			got = append(got, s.Kind+":"+s.Name)
		}
		if !slices.Equal(got, tc.want) {
			t.Errorf("%s: symbols %v, want %v", name, got, tc.want)
		}
	}
}

// A backticked keyword is an identifier: an escaped `import` / `package`
// opens no directive — so it neither records a phantom path nor swallows the
// declaration after it — and an escaped `inline` / `const` / `typealias`, or
// an escaped `fun` / `val` / modifier after the real ones, triggers no opaque
// rule. A name that is an identifier anyway (`Class`) matches escaped or not.
// Every field is compared exactly.
func TestKotlinEscapedKeywordsAreIdentifiers(t *testing.T) {
	for name, tc := range map[string]struct {
		src     string
		pkg     string
		decls   []string
		imports []string
		opaque  []string
	}{
		"escaped-import-fun":    {lines(`package x`, "val x = `import`", `fun f() = 1`), "x", []string{"val:x", "fun:f"}, nil, nil},
		"escaped-import-object": {lines(`package x`, `import a.b.C`, "val x = `import`", `object O`), "x", []string{"val:x", "object:O"}, []string{"a.b.C"}, nil},
		"escaped-import-infix":  {lines(`package x`, "val p = `import` to 1", `class K`), "x", []string{"val:p", "class:K"}, nil, nil},
		// File annotations precede the package directive.
		"escaped-import-file-annotation":  {lines("@file:Ann(`import` to 1)", `package com.x`, `fun f() = 1`), "com.x", []string{"fun:f"}, nil, nil},
		"escaped-package-file-annotation": {lines("@file:Ann(`package` to 1)", `package com.x`, `fun f() = 1`), "com.x", []string{"fun:f"}, nil, nil},
		"escaped-inline":                  {lines(`package x`, "val x = `inline`", `fun f() = 1`), "x", []string{"val:x", "fun:f"}, nil, nil},
		"inline-escaped-fun":              {lines(`package x`, `fun g() {`, `    val a = inline`, "    `fun`()", `}`), "x", []string{"fun:g"}, nil, nil},
		"inline-escaped-modifier":         {lines(`package x`, `fun g() {`, `    val a = inline`, "    `suspend`", `    fun h() = 1`, `}`), "x", []string{"fun:g"}, nil, nil},
		"escaped-const":                   {lines(`package x`, "val x = `const`", `val y = 1`), "x", []string{"val:x", "val:y"}, nil, nil},
		"const-escaped-val":               {lines(`package x`, `fun g() {`, `    val a = const`, "    `val`()", `}`), "x", []string{"fun:g"}, nil, nil},
		"escaped-typealias":               {lines(`package x`, `fun f() {`, "    val y = `typealias`", `    Wire = javax.inject.Inject`, `}`, `@Wire class C`), "x", []string{"fun:f", "class:C"}, nil, nil},
		// Controls.
		"directives":              {lines(`package com.x`, `import a.b.C`, `import a.b.*`, `import a.b.D as E`, `fun f() = 1`), "com.x", []string{"fun:f"}, []string{"a.b.C", "a.b", "a.b.D"}, nil},
		"escaped-import-segment":  {lines(`package com.x`, "import a.b.`import`", `fun f() = 1`), "com.x", []string{"fun:f"}, []string{"a.b.import"}, nil},
		"escaped-package-segment": {lines("package `import`.b", `fun f() = 1`), "import.b", []string{"fun:f"}, nil, nil},
		"inline-fun":              {lines(`package x`, `public inline suspend fun f() = 1`), "x", []string{"fun:f"}, nil, []string{"inline-fun"}},
		"const-val":               {lines(`package x`, `const val y = 1`), "x", []string{"val:y"}, nil, []string{"const-val"}},
		"typealias-di":            {lines(`package x`, `typealias Wire = javax.inject.Inject`, `@Wire class C`), "x", []string{"typealias:Wire", "class:C"}, nil, []string{"di"}},
		"escaped-class-forname":   {lines(`package x`, "val c = `Class`.forName(\"a\")"), "x", []string{"val:c"}, nil, []string{"reflection"}},
	} {
		raw := scanKotlin([]byte(tc.src))
		var decls, imports []string
		for _, s := range raw.Symbols {
			decls = append(decls, s.Kind+":"+s.Name)
		}
		for _, imp := range raw.Kt.Imports {
			imports = append(imports, imp.Path)
		}
		if raw.Kt.Package != tc.pkg || !slices.Equal(decls, tc.decls) || !slices.Equal(imports, tc.imports) || !slices.Equal(raw.Opaque, tc.opaque) {
			t.Errorf("%s: package %q symbols %v imports %v opaque %v, want %q %v %v %v",
				name, raw.Kt.Package, decls, imports, raw.Opaque, tc.pkg, tc.decls, tc.imports, tc.opaque)
		}
	}
}

// Annotations interleave with modifiers (`modifiers: (annotation |
// modifier)+`): the inline / const walks step over whole annotations, so
// `inline @Ann fun` is as opaque as `@Ann inline fun`.
func TestKotlinAnnotationsBetweenModifiers(t *testing.T) {
	annots := func(n int) string { return strings.Repeat("@A ", n) }
	for name, tc := range map[string]struct {
		src    string
		decls  []string
		opaque []string
	}{
		"inline-annotation":          {lines(`package x`, `inline @JvmSynthetic fun f() = 1`), []string{"fun:f"}, []string{"inline-fun"}},
		"inline-annotation-args":     {lines(`package x`, `inline @JvmName("x") fun f() = 1`), []string{"fun:f"}, []string{"inline-fun"}},
		"inline-annotation-modifier": {lines(`package x`, `public inline @JvmSynthetic suspend fun f() = 1`), []string{"fun:f"}, []string{"inline-fun"}},
		"inline-dotted-nested-args":  {lines(`package x`, `inline @kotlin.Deprecated("x", ReplaceWith("y")) fun f() = 1`), []string{"fun:f"}, []string{"inline-fun"}},
		// Longer than a token bound would reach.
		"inline-long-args":        {lines(`package x`, `inline @Suppress("a", "b", "c", "d") fun f() = 1`), []string{"fun:f"}, []string{"inline-fun"}},
		"inline-paren-in-string":  {lines(`package x`, `inline @Ann(")") fun f() = 1`), []string{"fun:f"}, []string{"inline-fun"}},
		"inline-multi-annotation": {lines(`package x`, `inline @[JvmSynthetic Ann("x")] fun f() = 1`), []string{"fun:f"}, []string{"inline-fun"}},
		"inline-use-site":         {lines(`package x`, `inline @receiver:Ann fun String.f() = 1`), []string{"fun:f"}, []string{"inline-fun"}},
		"inline-type-args":        {lines(`package x`, `inline @Ann<Int>(1) fun f() = 1`), []string{"fun:f"}, []string{"inline-fun"}},
		"const-annotation":        {lines(`package x`, `const @Ann val y = 1`), []string{"val:y"}, []string{"const-val"}},
		"const-annotation-args":   {lines(`package x`, `const @Ann("x") val y = 1`), []string{"val:y"}, []string{"const-val"}},
		"const-modifier":          {lines(`package x`, `const internal val y = 1`), []string{"val:y"}, []string{"const-val"}},
		"long-list-reaches-fun":   {lines(`package x`, `inline `+annots(ktModifierWalk-1)+`fun f() = 1`), []string{"fun:f"}, []string{"inline-fun"}},
		"exhaustion-fails-closed": {lines(`package x`, `inline `+annots(ktModifierWalk)+`class C`), []string{"class:C"}, []string{"inline-fun"}},
		// Controls.
		"annotation-first":                   {lines(`package x`, `@JvmSynthetic inline fun f() = 1`), []string{"fun:f"}, []string{"inline-fun"}},
		"annotation-first-const":             {lines(`package x`, `@Ann const val y = 1`), []string{"val:y"}, []string{"const-val"}},
		"inline-annotation-class":            {lines(`package x`, `inline @Ann class C`), []string{"class:C"}, nil},
		"under-bound-not-a-fun":              {lines(`package x`, `inline `+annots(ktModifierWalk-1)+`class C`), []string{"class:C"}, nil},
		"inline-annotation-escaped-fun":      {lines(`package x`, `fun g() {`, `    val a = inline`, "    @Ann `fun`()", `}`), []string{"fun:g"}, nil},
		"inline-annotation-escaped-modifier": {lines(`package x`, `fun g() {`, `    val a = inline`, "    @Ann `suspend`", `    fun h() = 1`, `}`), []string{"fun:g"}, nil},
		"const-annotation-escaped-val":       {lines(`package x`, `fun g() {`, `    val a = const`, "    @Ann `val`()", `}`), []string{"fun:g"}, nil},
	} {
		raw := scanKotlin([]byte(tc.src))
		var decls []string
		for _, s := range raw.Symbols {
			decls = append(decls, s.Kind+":"+s.Name)
		}
		if !slices.Equal(decls, tc.decls) || !slices.Equal(raw.Opaque, tc.opaque) {
			t.Errorf("%s: symbols %v opaque %v, want %v %v", name, decls, raw.Opaque, tc.decls, tc.opaque)
		}
	}
}

// An inline property's accessors are inlined into their call sites exactly
// like an inline function's body: `inline` on the property (both accessors)
// or on one accessor marks the file inline-fun. Every row is compared
// exactly; the controls pin what stays transparent.
func TestKotlinInlineProperties(t *testing.T) {
	for name, tc := range map[string]struct {
		src    string
		decls  []string
		opaque []string
	}{
		"inline-val":               {lines(`package x`, `inline val x: Int get() = 1`), []string{"val:x"}, []string{"inline-fun"}},
		"inline-var":               {lines(`package x`, `inline var x: Int`, `    get() = 1`, `    set(v) {}`), []string{"var:x"}, []string{"inline-fun"}},
		"inline-getter":            {lines(`package x`, `val x: Int inline get() = 1`), []string{"val:x"}, []string{"inline-fun"}},
		"inline-setter":            {lines(`package x`, `var x: Int`, `    get() = 1`, `    inline set(v) {}`), []string{"var:x"}, []string{"inline-fun"}},
		"inline-private-setter":    {lines(`package x`, `var x: Int`, `    get() = 1`, `    private inline set(v) {}`), []string{"var:x"}, []string{"inline-fun"}},
		"inline-ext-val":           {lines(`package x`, `inline val String.size2: Int get() = length`), []string{"val:size2"}, []string{"inline-fun"}},
		"inline-annotation-val":    {lines(`package x`, `inline @JvmSynthetic val x: Int get() = 1`), []string{"val:x"}, []string{"inline-fun"}},
		"annotation-inline-getter": {lines(`package x`, `val x: Int @JvmName("a") inline get() = 1`), []string{"val:x"}, []string{"inline-fun"}},
		"member-inline-val":        {lines(`package x`, `class C {`, `    inline val x: Int get() = 1`, `}`), []string{"class:C"}, []string{"inline-fun"}},
		// Controls.
		"plain-getter":       {lines(`package x`, `val x: Int get() = 1`), []string{"val:x"}, nil},
		"inline-escaped-get": {lines(`package x`, `fun g() {`, `    val a = inline`, "    `get`()", `}`), []string{"fun:g"}, nil},
		"inline-escaped-val": {lines(`package x`, `fun g() {`, `    val a = inline`, "    `val`()", `}`), []string{"fun:g"}, nil},
		"inline-dot-get":     {lines(`package x`, `val a = inline.get()`), []string{"val:a"}, nil},
		"inline-class":       {lines(`package x`, `inline class V(val v: Int)`), []string{"class:V"}, nil},
	} {
		raw := scanKotlin([]byte(tc.src))
		var decls []string
		for _, s := range raw.Symbols {
			decls = append(decls, s.Kind+":"+s.Name)
		}
		if !slices.Equal(decls, tc.decls) || !slices.Equal(raw.Opaque, tc.opaque) {
			t.Errorf("%s: symbols %v opaque %v, want %v %v", name, decls, raw.Opaque, tc.decls, tc.opaque)
		}
	}
}

// The lexer emits a plain string literal as a kind-s token whose text is its
// content, so a `"]"` or `"."` is never a bracket or a dot: a multi-annotation
// list reads past a bracket in a string argument, and a string before a
// keyword or a chain hides neither. Every field is compared exactly.
func TestKotlinStringContentIsNotSyntax(t *testing.T) {
	for name, tc := range map[string]struct {
		src    string
		decls  []string
		refs   []string
		opaque []string
	}{
		"multi-close-bracket": {lines(`package x`, `@[Foo("]") Inject] class C`), []string{"class:C"}, nil, []string{"di"}},
		"multi-close-paren":   {lines(`package x`, `@[Foo(")") Inject] class C`), []string{"class:C"}, nil, []string{"di"}},
		"multi-open-bracket":  {lines(`package x`, `@[Foo("[") Inject] class C`), []string{"class:C"}, nil, []string{"di"}},
		"multi-open-paren":    {lines(`package x`, `@[Foo("(") Inject] class C`), []string{"class:C"}, nil, []string{"di"}},
		// A template's code stays tokens; the string inside it is content.
		"multi-template-bracket": {lines(`package x`, `@[Foo("${"]"}") Inject] class C`), []string{"class:C"}, nil, []string{"di"}},
		"dot-before-class":       {lines(`package x`, `const val SEP = "."`, `class After`), []string{"val:SEP", "class:After"}, nil, []string{"const-val"}},
		"scope-before-fun":       {lines(`package x`, `val s = "::"`, `fun after() = 1`), []string{"val:s", "fun:after"}, nil, nil},
		"quest-before-object":    {lines(`package x`, `val q = "?"`, `object After`), []string{"val:q", "object:After"}, nil, nil},
		"dot-before-typealias": {lines(`package x`, `val s = "."`, `typealias Wire = javax.inject.Inject`, `@Wire class C`),
			[]string{"val:s", "typealias:Wire", "class:C"}, []string{"javax.inject.Inject"}, []string{"di"}},
		"dot-before-ref": {lines(`package x`, `fun f() {`, `    val s = "."`, `    com.x.util.helper()`, `}`), []string{"fun:f"}, []string{"com.x.util.helper"}, nil},
		// Controls.
		"multi-plain-arg":      {lines(`package x`, `@[Foo("x") Inject] class C`), []string{"class:C"}, nil, []string{"di"}},
		"multi-bracket-not-di": {lines(`package x`, `@[Foo("]") Bar] class C`), []string{"class:C"}, nil, nil},
		"plain-before-class":   {lines(`package x`, `val s = "a"`, `class After`), []string{"val:s", "class:After"}, nil, nil},
		"plain-before-ref":     {lines(`package x`, `fun f() {`, `    val s = "a"`, `    com.x.util.helper()`, `}`), []string{"fun:f"}, []string{"com.x.util.helper"}, nil},
	} {
		raw := scanKotlin([]byte(tc.src))
		var decls, refs []string
		for _, s := range raw.Symbols {
			decls = append(decls, s.Kind+":"+s.Name)
		}
		for _, r := range raw.Kt.Refs {
			refs = append(refs, r.Chain)
		}
		if !slices.Equal(decls, tc.decls) || !slices.Equal(refs, tc.refs) || !slices.Equal(raw.Opaque, tc.opaque) {
			t.Errorf("%s: symbols %v refs %v opaque %v, want %v %v %v", name, decls, refs, raw.Opaque, tc.decls, tc.refs, tc.opaque)
		}
	}
}

// End to end through --from-body: a name after a string literal `"."`,
// `"::"` or `"?"` is not in a receiver position, so it resolves as a simple
// name rather than as an extension (no ref) or not at all.
func TestKotlinFromBodyStringBeforeName(t *testing.T) {
	for name, str := range map[string]string{"dot": `"."`, "scope": `"::"`, "quest": `"?"`} {
		r := repo(t, map[string]string{
			"aitestmap/.keep":      "",
			"src/a/LoginState.kt":  "package com.x.a\n\ndata class LoginState(val email: String)\n",
			"tests/a/LoginTest.kt": lines(`package com.x.a`, ``, `// testmap:unit M`, `fun m() {`, `    val sep = `+str, `    LoginState(sep)`, `}`),
		})
		refused, refs, _, err := FromBody(bg, r.Dir, registry.ID{Path: "tests/a/LoginTest.kt", Member: "M"},
			Options{Config: registry.Defaults(), Uncached: true})
		want := []BodyRef{{Source: "src/a/LoginState.kt", Symbol: "LoginState", Line: 6}}
		if err != nil || refused != "" || !slices.Equal(refs, want) {
			t.Errorf("%s: FromBody: refused %q refs %+v err %v, want %+v", name, refused, refs, err, want)
		}
	}
}

// End to end: a declaration after an escaped `import` stays in the
// resolution index, so an import of it resolves to its declaring file as a
// static import, not a closure-only package fallback.
func TestKotlinEscapedImportKeepsDeclaration(t *testing.T) {
	r := repo(t, map[string]string{
		"src/b/Lib.kt":  "package com.x.b\n\nval tag = `import`\nfun helper() = 1\n",
		"src/c/User.kt": "package com.x.c\n\nimport com.x.b.helper\n\nfun u() = helper()\n",
	})
	g := scanRepo(t, r)
	f, _ := g.Facts("src/b/Lib.kt")
	var names []string
	for _, s := range f.Symbols {
		names = append(names, s.Kind+":"+s.Name)
	}
	if want := []string{"val:tag", "fun:helper"}; !slices.Equal(names, want) {
		t.Errorf("symbols %v, want %v", names, want)
	}
	requireEdge(t, g, "src/c/User.kt", "src/b/Lib.kt", Import, "import")
	if u, _ := g.Facts("src/c/User.kt"); slices.Contains(u.Unresolved, "com.x.b.helper") {
		t.Errorf("unresolved: %v", u.Unresolved)
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

// A script header is a comment (Kotlin.flex SHEBANG_COMMENT): a { or ( in it
// must not hide the package or the declarations. A lone CR, which kotlinc
// reads as a newline and ktLex's line rules do not, fails closed instead of
// letting a // comment swallow what follows it.
func TestKotlinShebang(t *testing.T) {
	const decls = "package p\nclass Actual\n"
	for name, tc := range map[string]struct {
		src     string
		pkg     string
		symbols []string
		opaque  []string
	}{
		"brace":      {"#!/usr/bin/env -S kotlin -J-Dtag={\n" + decls, "p", []string{"class:Actual"}, nil},
		"paren":      {"#!/usr/bin/env -S kotlin -J-Dtag=(\n" + decls, "p", []string{"class:Actual"}, nil},
		"slash-star": {"#!/usr/bin/env -S kotlin -cp lib/*\n" + decls, "p", []string{"class:Actual"}, nil},
		"bom":        {"\ufeff#!/usr/bin/env -S kotlin -J-Dtag={\n" + decls, "p", []string{"class:Actual"}, nil},
		"crlf":       {"#!/x {\r\n// note\r\npackage p\r\nclass Actual\r\n", "p", []string{"class:Actual"}, nil},
		"lone-cr":    {"#!/x {\r// note\rpackage p\rclass Actual\r", "", nil, []string{"untokenizable"}},
		// Without a header too: the // comment ran to the end of the file.
		"lone-cr-no-shebang": {"// note\rpackage p\rclass Actual\r", "", nil, []string{"untokenizable"}},
		"lone-cr-final":      {"package p\nclass Actual\r", "", nil, []string{"untokenizable"}},
		// Controls: no header, and a #! line no newline ends, which is code.
		"none":         {decls, "p", []string{"class:Actual"}, nil},
		"unterminated": {"#!a {", "", nil, nil},
	} {
		raw := scanKotlin([]byte(tc.src))
		var symbols []string
		for _, s := range raw.Symbols {
			symbols = append(symbols, s.Kind+":"+s.Name)
		}
		if raw.Kt.Package != tc.pkg || !slices.Equal(symbols, tc.symbols) || !slices.Equal(raw.Opaque, tc.opaque) {
			t.Errorf("%s: package %q symbols %v opaque %v, want %q %v %v", name, raw.Kt.Package, symbols, raw.Opaque, tc.pkg, tc.symbols, tc.opaque)
		}
	}
	// CRLF keeps every line number.
	toks, err := ktLex("#!/x {\r\n// note\r\npackage p\r\nclass Actual\r\n")
	var got []string
	for _, k := range toks {
		got = append(got, k.text+"@"+strconv.Itoa(k.line))
	}
	if want := []string{"package@3", "p@3", "class@4", "Actual@4"}; err != nil || !slices.Equal(got, want) {
		t.Errorf("crlf tokens %v %v, want %v", got, err, want)
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
