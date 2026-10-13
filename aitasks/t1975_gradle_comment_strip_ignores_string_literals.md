---
priority: high
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1852
created_at: 2026-10-13 17:39
updated_at: 2026-10-13 18:44
---

## Origin

Found by t1973 (Kotlin target probe: `deps.Scan` over thinking_app at `1dc7b958926f`). Measurements in `aiplans/p1973_kotlin_target_probe.md`.

## Defect

`scanGradle` (`goengines/internal/testmap/deps/gradle.go`) blanks comments with
`gradleComment = (?m)//[^\n]*$|/\*(?s:.*?)\*/` **before** reading `include`,
`project(...)`, `projectDir` and accessors, and that regex does not know about
string literals. A `/*` inside a quoted string (an Android `excludes += '/META-INF/*'`,
a glob such as `'**/*.kt'` or `'*/*_REVIEW.md'`) opens a fake block comment that runs to
the next `*/` anywhere later in the file, and everything in between is erased. A `//`
inside a string (`url 'https://…'`) erases the rest of that line the same way.

Two consequences, both observed:

1. **Under-selection (silent).** A `project(':lib')` dependency between the fake
   comment's ends disappears: the module's `Deps` lose `:lib`, its sources lose the
   `module-build` edge to `lib/build.gradle`, and **no Problem is reported**.
2. **Over-approximation (thinking_app).** In thinking_app's `app/build.gradle` the glob
   `'*/*_REVIEW.md'` (line 920) opens a fake comment that ends inside line 921's
   `'*/evidence/…'`, leaving `include '*` behind. That is read as a dynamic `include`
   (Problem `gradle-dynamic: include`), the build file is marked opaque, and `:app`'s
   `Deps` collapse to every module (`[":"]`).

Related secondary issue (same function): `includeRe` is applied to build files too,
where `include` is a `fileTree` / `copy` / `test { filter }` pattern rather than a
settings `include`. With a literal argument it is harmless, but a GString argument
(`include "${dir}/*.md"`) in a build file marks the module dynamic. Decide whether build
files should parse `include` at all.

## Reproducing fixture

Confirmed red against the scanner at commit `822fc6f47`:

```go
func TestGradleCommentInString(t *testing.T) {
	r := repo(t, map[string]string{
		"settings.gradle":  "include ':app', ':lib'\n",
		"lib/build.gradle": "plugins { id 'java' }\n",
		"app/build.gradle": "android {\n" +
			"    packaging { resources { excludes += '/META-INF/*' } }\n" +
			"}\n" +
			"dependencies {\n" +
			"    implementation project(':lib')\n" +
			"}\n" +
			"tasks.register('docs') { inputs.files(fileTree('d') { include '*/x.md' }) }\n",
		"app/src/main/kotlin/A.kt": "package com.x\n\nclass A\n",
	})
	g := scanRepo(t, r)
	m, _ := g.ModuleOf("app/src/main/kotlin/A.kt")
	// want [:lib]; the scanner gives [] and no problem
	if !slices.Equal(m.Deps, []string{":lib"}) { t.Errorf(":app deps = %v", m.Deps) }
}
```

Actual: `:app deps = []`, problems `[]`, and `A.kt` has edges to `app/build.gradle` and
`settings.gradle` only.

## Fix direction

Make the comment blanking string-aware: skip `'…'`, `"…"` and `"""…"""` (Groovy and
Kotlin DSL), keeping offsets so line numbers are unchanged. Add fixtures for:
- `/*` inside a string hiding a `project()` dependency;
- `//` inside a URL string on the same line as a `project()` dependency;
- the thinking_app glob pair, which must no longer report `gradle-dynamic`;
- a real block comment that still blanks a commented-out `project()`.

Bump the cache `schemaVersion`, because raw Gradle extraction changes.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1976** id=2026-10-13T20:59:32Z.b906cde13370932b8ffe5133 from=t1976 from_verified=yes at=2026-10-13T20:59:32Z base=8718afa0877d3e336f05c95d4b4dc37b30c5f6a5 base_branch=main dirty=no host=omg16
>
> | t1976 landed as 8718afa08 on main: cache.go `const schemaVersion` is now 5 at HEAD (it was 4).
> | This task's extraction change must carry its own bump: parent+1, read from HEAD at your commit time (6 if nothing else lands first). Do not reuse 5.
> | Why: cache.get (goengines/internal/testmap/deps/cache.go:61) checks only the entry's version and kind, with entries keyed by the file's blob hash and no extraction-rule fingerprint. Two committed extraction states that share a version would serve each other's cached entries.
> | t1976 touched only scanKotlin's declaration gate (a `parens` counter; ktDeclName is untouched), two tests in kotlin_test.go after TestKotlinResolution, and the version line.
