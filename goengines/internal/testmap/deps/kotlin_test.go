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
