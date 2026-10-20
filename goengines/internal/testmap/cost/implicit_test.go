package cost

import (
	"os"
	"os/exec"
	"path"
	"path/filepath"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/runner"
)

// unitRunner lists and passes the one unit UNIT.
const unitRunner = `#!/usr/bin/env bash
case "$1" in
describe) printf 'unit: file\ntimeouts: batch\n';;
list) printf 'UNIT\tfile\tu\n';;
run) R=$(sed -n 's/^  "results": "\(.*\)",$/\1/p' "$3")
  printf '{"id":"UNIT","status":"pass","duration_ms":3}\n' >> "$R";;
*) exit 64;;
esac
`

// implicitRepo commits a minimal fixture whose only unit is unit, run by a
// shadow runner, with exclude as the config's `exclude:` list; files are
// written over the defaults. Gitignored files are written but never
// committed.
func implicitRepo(t *testing.T, unit, exclude string, files map[string]string) *fixture.Repo {
	t.Helper()
	t.Setenv("XDG_CACHE_HOME", t.TempDir())
	r := fixture.New(t)
	all := map[string]string{
		"aitestmap/config.yaml":        "contract: 1\nhost_class: ci\nexclude: [" + exclude + "]\n",
		".gitignore":                   ".aitask-testmap/\n",
		"docs/readme.md":               "r\n",
		runner.RunnersPath:             "contract: 1\nrunners:\n  - name: unit\n    bind: ['" + unit + "']\n    timeout_s: 30\n    batch_timeout_s: 30\n",
		runner.RunnersDir + "/unit.sh": strings.ReplaceAll(unitRunner, "UNIT", unit),
	}
	for k, v := range files {
		all[k] = v
	}
	for p, c := range all {
		r.Write(t, p, c)
	}
	if err := os.Chmod(filepath.Join(r.Dir, filepath.FromSlash(runner.RunnersDir+"/unit.sh")), 0o755); err != nil {
		t.Fatal(err)
	}
	r.Commit(t, "1", "test", "fixture")
	return r
}

// touch edits each path with a change its language still parses.
func touch(t *testing.T, r *fixture.Repo, paths ...string) {
	t.Helper()
	for _, p := range paths {
		var line string
		switch path.Ext(p) {
		case ".go", ".kt", ".kts", ".gradle", ".mod":
			line = "// dirty\n"
		case ".json", ".sum", "":
			line = "\n"
		default:
			line = "# dirty\n"
		}
		old, _ := os.ReadFile(filepath.Join(r.Dir, filepath.FromSlash(p)))
		r.Write(t, p, string(old)+line)
	}
}

// verdict asserts unit's row on r after editing paths (plus an unrelated
// docs file, so the tree is dirty even when paths is empty).
func verdict(t *testing.T, r *fixture.Repo, unit, want string, paths ...string) {
	t.Helper()
	touch(t, r, append(paths, "docs/readme.md")...)
	row := reasonOf(t, judgedIDs(t, r.Dir, false, []string{unit}), unit)
	eligible := want == ""
	if row.Clean != eligible || row.Anchor != eligible || row.AnchorReason != want {
		t.Fatalf("clean %v anchor %v reason %q, want reason %q", row.Clean, row.Anchor, row.AnchorReason, want)
	}
}

// goEnv isolates the go list the scan runs: no toolchain download, no user
// flags, no workspace.
func goEnv(t *testing.T) {
	t.Helper()
	t.Setenv("GOTOOLCHAIN", "local")
	t.Setenv("GOFLAGS", "")
	t.Setenv("GOWORK", "off")
	t.Setenv("GOPROXY", "off")
	if _, err := exec.LookPath("go"); err != nil {
		t.Skip("no go toolchain")
	}
}

const (
	pyUnit = "tests/test_p.py"
	goUnit = "pkg/a_test.go"
	ktUnit = "app/src/test/kotlin/com/x/ATest.kt"
)

var (
	pyFiles = map[string]string{
		pyUnit:              "def test_p():\n    pass\n",
		"tests/__init__.py": "from . import initdep\n",
		"tests/initdep.py":  "X = 1\n",
		"tests/pytest.ini":  "[pytest]\n",
		"pyproject.toml":    "[tool.pytest.ini_options]\n",
		"other/pytest.ini":  "[pytest]\n",
		"tests/conftest.py": "X = 1\n",
	}
	goFiles = map[string]string{
		"go.mod":               "module m\n\ngo 1.21\n",
		"go.sum":               "",
		"pkg/a.go":             "package pkg\n\nvar A = 1\n",
		goUnit:                 "package pkg\n\nimport \"testing\"\n\nfunc TestA(t *testing.T) {}\n",
		"pkg/a_ext_test.go":    "package pkg_test\n\nimport (\n\t\"testing\"\n\n\t\"m/xdep\"\n)\n\nfunc TestX(t *testing.T) { _ = xdep.X }\n",
		"xdep/x.go":            "package xdep\n\nvar X = 1\n",
		"pkg/vendor/x.txt":     "v\n",
		"other/o.go":           "package other\n",
		"pkg/b.go":             "package pkg\n\nvar B = 1\n",
		"pkg/testdata/bad.txt": "case\n",
		"xdep/y.go":            "package xdep\n\nvar Y = 2\n",
	}
	ktFiles = map[string]string{
		"settings.gradle.kts":                      "include(\":app\")\n",
		"build.gradle.kts":                         "// testmap:reads config/*.yml\nsubprojects { }\n",
		"config/x.yml":                             "a: 1\n",
		"scripts/extra.gradle":                     "ext { }\n",
		"included/settings.gradle.kts":             "\n",
		"included/src/main/kotlin/I.kt":            "package inc\n\nclass I\n",
		"gradlew":                                  "#!/bin/sh\necho\n",
		"app/build.gradle.kts":                     "plugins { }\n",
		"app/gradle.properties":                    "a=1\n",
		"gradle/wrapper/gradle-wrapper.properties": "distributionUrl=x\n",
		"app/src/test/resources/f.json":            "{}\n",
		"build-logic/src/main/kotlin/Conv.kt":      "package conv\n\nclass Conv\n",
		ktUnit:                                     "package com.x\n\nclass ATest\n",
	}
)

// ktBuildSrc adds a buildSrc source: a build input whose own module (the root
// project) pulls the root build script into every Kotlin closure, so it is
// kept out of the shared map.
var ktBuildSrc = func() map[string]string {
	m := map[string]string{"buildSrc/src/main/kotlin/B.kt": "package b\n\nclass B\n"}
	for k, v := range ktFiles {
		m[k] = v
	}
	return m
}()

// The implicit inputs of each framework: every rule names its own path; an
// unrelated edit (and, per language, a non-ancestor namesake) anchors. A
// deleted input (del) is in the modified set but in no graph: only a path
// rule can name it.
func TestEligibilityImplicitInputs(t *testing.T) {
	for _, c := range []struct {
		name, unit      string
		files           map[string]string
		edit, del, want string
	}{
		{"py-control", pyUnit, pyFiles, "", "", ""},
		{"py-non-ancestor-ini", pyUnit, pyFiles, "other/pytest.ini", "", ""},
		{"py-pyproject", pyUnit, pyFiles, "pyproject.toml", "", "implicit:pyproject.toml"},
		{"py-ancestor-ini", pyUnit, pyFiles, "tests/pytest.ini", "", "implicit:tests/pytest.ini"},
		{"py-package-init", pyUnit, pyFiles, "tests/__init__.py", "", "implicit:tests/__init__.py"},
		{"py-init-closure", pyUnit, pyFiles, "tests/initdep.py", "", "closure:tests/initdep.py"},
		{"py-deleted-conftest", pyUnit, pyFiles, "", "tests/conftest.py", "implicit:tests/conftest.py"},
		{"go-control", goUnit, goFiles, "", "", ""},
		{"go-other-package", goUnit, goFiles, "other/o.go", "", ""},
		{"go-mod", goUnit, goFiles, "go.mod", "", "implicit:go.mod"},
		{"go-sum", goUnit, goFiles, "go.sum", "", "implicit:go.sum"},
		{"go-xtest", goUnit, goFiles, "pkg/a_ext_test.go", "", "implicit:pkg/a_ext_test.go"},
		{"go-xtest-closure", goUnit, goFiles, "xdep/x.go", "", "closure:xdep/x.go"},
		{"go-vendor", goUnit, goFiles, "pkg/vendor/x.txt", "", "implicit:pkg/vendor/x.txt"},
		{"go-deleted-sibling", goUnit, goFiles, "", "pkg/b.go", "implicit:pkg/b.go"},
		{"go-deleted-testdata", goUnit, goFiles, "", "pkg/testdata/bad.txt", "implicit:pkg/testdata/bad.txt"},
		{"go-deleted-dep-member", goUnit, goFiles, "", "xdep/y.go", "implicit:xdep/y.go"},
		{"kt-control", ktUnit, ktFiles, "", "", ""},
		{"kt-root-build", ktUnit, ktFiles, "build.gradle.kts", "", "implicit:build.gradle.kts"},
		{"kt-wrapper", ktUnit, ktFiles, "gradle/wrapper/gradle-wrapper.properties", "", "implicit:gradle/wrapper/gradle-wrapper.properties"},
		{"kt-module-properties", ktUnit, ktFiles, "app/gradle.properties", "", "implicit:app/gradle.properties"},
		{"kt-test-resource", ktUnit, ktFiles, "app/src/test/resources/f.json", "", "implicit:app/src/test/resources/f.json"},
		{"kt-build-logic", ktUnit, ktFiles, "build-logic/src/main/kotlin/Conv.kt", "", "implicit:build-logic/src/main/kotlin/Conv.kt"},
		{"kt-script-reads", ktUnit, ktFiles, "config/x.yml", "", "reads:config/*.yml"},
		{"kt-deleted-script", ktUnit, ktFiles, "", "scripts/extra.gradle", "implicit:scripts/extra.gradle"},
		{"kt-included-build", ktUnit, ktFiles, "included/src/main/kotlin/I.kt", "", "implicit:included/src/main/kotlin/I.kt"},
		{"kt-gradlew", ktUnit, ktFiles, "gradlew", "", "implicit:gradlew"},
		{"kt-deleted-buildsrc", ktUnit, ktBuildSrc, "", "buildSrc/src/main/kotlin/B.kt", "implicit:buildSrc/src/main/kotlin/B.kt"},
	} {
		t.Run(c.name, func(t *testing.T) {
			if c.unit == goUnit {
				goEnv(t)
			}
			r := implicitRepo(t, c.unit, "", c.files)
			if c.del != "" {
				r.Remove(t, c.del)
			}
			var edits []string
			if c.edit != "" {
				edits = append(edits, c.edit)
			}
			verdict(t, r, c.unit, c.want, edits...)
		})
	}
}

// A test reaches a local dependency in another module (a replace to a
// sibling directory): that module's go.mod decides the language version its
// code compiles under, so editing only it rejects, as does the test's own.
func TestEligibilityGoDependencyModule(t *testing.T) {
	files := map[string]string{
		"app/go.mod":      "module example.com/app\n\ngo 1.21\n\nrequire example.com/lib v0.0.0\n\nreplace example.com/lib => ../lib\n",
		"lib/go.mod":      "module example.com/lib\n\ngo 1.21\n",
		"lib/l.go":        "package lib\n\nvar L = 1\n",
		"app/p/a_test.go": "package p\n\nimport (\n\t\"testing\"\n\n\t\"example.com/lib\"\n)\n\nfunc TestA(t *testing.T) { _ = lib.L }\n",
	}
	for _, c := range []struct{ name, edit, want string }{
		{"control", "", ""},
		{"closure", "lib/l.go", "closure:lib/l.go"},
		{"dependency-module", "lib/go.mod", "implicit:lib/go.mod"},
		{"own-module", "app/go.mod", "implicit:app/go.mod"},
	} {
		t.Run(c.name, func(t *testing.T) {
			goEnv(t)
			r := implicitRepo(t, "app/p/a_test.go", "", files)
			var edits []string
			if c.edit != "" {
				edits = append(edits, c.edit)
			}
			verdict(t, r, "app/p/a_test.go", c.want, edits...)
		})
	}
}

// A tracked input under a reached package replaced by a symbolic link — or
// reached through a linked directory — still exists, but the scan's
// no-follow universe drops it: it must reject, not vanish.
func TestEligibilityGoSymlinkedInput(t *testing.T) {
	files := map[string]string{"pkg/testdata/good.txt": "ok\n", "alt/bad.txt": "ok\n", "alt/good.txt": "ok\n"}
	for k, v := range goFiles {
		files[k] = v
	}
	// ancestor-dir-hidden gitignores the link itself, so only the tracked
	// paths under it are modified — and each still resolves through the link.
	for _, c := range []struct {
		name, link, target, want string
		hide                     bool
	}{
		{"final-component", "pkg/testdata/bad.txt", "good.txt", "implicit:pkg/testdata/bad.txt", false},
		{"ancestor-dir", "pkg/testdata", "../alt", "implicit:pkg/testdata", false},
		{"ancestor-dir-hidden", "pkg/testdata", "../alt", "implicit:pkg/testdata/bad.txt", true},
	} {
		t.Run(c.name, func(t *testing.T) {
			goEnv(t)
			r := implicitRepo(t, goUnit, "", files)
			full := filepath.Join(r.Dir, filepath.FromSlash(c.link))
			if err := os.RemoveAll(full); err != nil {
				t.Fatal(err)
			}
			if err := os.Symlink(c.target, full); err != nil {
				t.Fatal(err)
			}
			if c.hide {
				r.Write(t, ".gitignore", ".aitask-testmap/\n/"+c.link+"\n")
			}
			verdict(t, r, goUnit, c.want)
		})
	}
}

// An unchanged excluded conftest imports a helper (through a sys.path
// bootstrap): with exclude lifted the conftest is scanned, so the helper is a
// closure file. A gitignored conftest cannot be scanned and fails closed.
func TestEligibilityExcludedConftestHelper(t *testing.T) {
	conftest := "import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).resolve().parent.parent / \"src\"))\nimport helper\n"
	files := func(conf string) map[string]string {
		return map[string]string{
			pyUnit:              "def test_p():\n    pass\n",
			"tests/conftest.py": conf,
			"src/helper.py":     "X = 1\n",
		}
	}
	t.Run("control", func(t *testing.T) {
		r := implicitRepo(t, pyUnit, "'tests/conftest.py'", files("X = 1\n"))
		verdict(t, r, pyUnit, "", "src/helper.py")
	})
	t.Run("excluded", func(t *testing.T) {
		r := implicitRepo(t, pyUnit, "'tests/conftest.py'", files(conftest))
		verdict(t, r, pyUnit, "closure:src/helper.py", "src/helper.py")
	})
	t.Run("gitignored", func(t *testing.T) {
		f := files(conftest)
		f[".gitignore"] = ".aitask-testmap/\n/tests/conftest.py\n"
		r := implicitRepo(t, pyUnit, "", f)
		verdict(t, r, pyUnit, "opaque:implicit-unscanned:tests/conftest.py", "src/helper.py")
	})
}

// A package embeds an asset under an excluded directory: with exclude lifted
// the embed is a closure edge. A gitignored asset cannot be followed: the
// test is unresolved.
func TestEligibilityExcludedEmbed(t *testing.T) {
	files := map[string]string{
		"go.mod":                 "module m\n\ngo 1.21\n",
		"pkg/a.go":               "package pkg\n\nimport _ \"embed\"\n\n//go:embed assets/message.txt\nvar Msg string\n",
		"pkg/assets/message.txt": "hi\n",
		goUnit:                   "package pkg\n\nimport \"testing\"\n\nfunc TestA(t *testing.T) {}\n",
	}
	t.Run("excluded", func(t *testing.T) {
		goEnv(t)
		r := implicitRepo(t, goUnit, "'pkg/assets/**'", files)
		verdict(t, r, goUnit, "closure:pkg/assets/message.txt", "pkg/assets/message.txt")
	})
	t.Run("gitignored", func(t *testing.T) {
		goEnv(t)
		f := map[string]string{".gitignore": ".aitask-testmap/\n/pkg/assets/\n"}
		for k, v := range files {
			f[k] = v
		}
		r := implicitRepo(t, goUnit, "", f)
		verdict(t, r, goUnit, "opaque:unresolved:"+goUnit)
	})
}

// A test imports a package whose every file is gitignored, and that package
// imports a tracked one: go list reports it, no facts exist inside it, so
// the importer carries the mark and the dirty tracked package cannot anchor.
func TestEligibilityGitignoredGoPackage(t *testing.T) {
	files := map[string]string{
		".gitignore":       ".aitask-testmap/\n/hidden/\n",
		"go.mod":           "module m\n\ngo 1.21\n",
		"a/a_test.go":      "package a\n\nimport (\n\t\"testing\"\n\n\t_ \"m/hidden\"\n)\n\nfunc TestA(t *testing.T) {}\n",
		"hidden/hidden.go": "package hidden\n\nimport _ \"m/c\"\n",
		"c/c.go":           "package c\n",
	}
	t.Run("gitignored", func(t *testing.T) {
		goEnv(t)
		r := implicitRepo(t, "a/a_test.go", "", files)
		verdict(t, r, "a/a_test.go", "opaque:unresolved:a/a_test.go", "c/c.go")
	})
	t.Run("tracked", func(t *testing.T) {
		goEnv(t)
		f := map[string]string{".gitignore": ".aitask-testmap/\n"}
		for k, v := range files {
			if k != ".gitignore" {
				f[k] = v
			}
		}
		r := implicitRepo(t, "a/a_test.go", "", f)
		verdict(t, r, "a/a_test.go", "closure:c/c.go", "c/c.go")
	})
}

// An unchanged excluded helper declares what it reads, and reads it
// dynamically: the declaration is the only guard, so dirtying only the data
// is named by it; an unreadable declaration fails closed.
func TestEligibilityExcludedHelperReadsDeclaration(t *testing.T) {
	src := testA + "source \"$SCRIPT_DIR/../vendor/lib.sh\"\n"
	noPlugin := "#!/bin/sh\ncat >/dev/null\n"
	for _, c := range []struct{ name, lib, want string }{
		{"control", "#!/usr/bin/env bash\ncat \"$DATA\"\n", ""},
		{"declared", "#!/usr/bin/env bash\n# testmap:reads fixtures/*.json\ncat \"$DATA\"\n", "reads:fixtures/*.json"},
		{"unreadable", "#!/usr/bin/env bash\n# testmap:frobnicate x\ncat \"$DATA\"\n", "opaque:annotations:vendor/lib.sh"},
	} {
		t.Run(c.name, func(t *testing.T) {
			r := eligRepo(t, "", map[string]string{"tests/test_a.sh": src, "vendor/lib.sh": c.lib, "aitestmap/scanners/fx": noPlugin})
			dirty(t, r, "fixtures/y.json")
			if row := reasonOf(t, judged(t, r.Dir, false), "tests/test_a.sh"); row.Anchor != (c.want == "") || row.AnchorReason != c.want {
				t.Fatalf("%+v, want %q", row, c.want)
			}
		})
	}
}

// A project-script runner's helper declares what it reads: its data, and
// only its data, dirty is named under runner-config — the same guards as
// the test side, over the script's closure.
func TestEligibilityScriptRunnerHelperReads(t *testing.T) {
	runnerScript := func(lib string) string {
		return "#!/usr/bin/env bash\nSCRIPT_DIR=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)\"\nsource \"$SCRIPT_DIR/" + lib + "\"\n" + strings.SplitN(shellRunner, "\n", 2)[1]
	}
	declared := "#!/usr/bin/env bash\n# testmap:reads runnerdata/*.json\ncat \"$DATA\"\n"
	plugin := "#!/bin/sh\ncat >/dev/null\necho '{\"file\":\"tests/test_a.sh\",\"reads\":[\"fixtures/*.json\"]}'\necho '{\"file\":\"tools/run.sh\",\"reads\":[\"runnerdata/*.json\"]}'\n"
	for _, c := range []struct {
		name, lib, libPath, plugin, want string
	}{
		{"control", "#!/usr/bin/env bash\ncat \"$DATA\"\n", "vendor/runner-lib.sh", "", ""},
		{"excluded-declared", declared, "vendor/runner-lib.sh", "", "runner-config:reads:runnerdata/*.json"},
		{"in-universe-declared", declared, "tools/runner-lib.sh", "", "runner-config:reads:runnerdata/*.json"},
		{"unreadable", "#!/usr/bin/env bash\n# testmap:frobnicate x\n", "vendor/runner-lib.sh", "", "runner-config:annotations:vendor/runner-lib.sh"},
		{"plugin-declared", "#!/usr/bin/env bash\ncat \"$DATA\"\n", "vendor/runner-lib.sh", plugin, "runner-config:plugin-reads:runnerdata/*.json"},
	} {
		t.Run(c.name, func(t *testing.T) {
			rel := "../" + c.libPath
			extra := map[string]string{
				runner.RunnersPath:  "contract: 1\nrunners:\n  - name: tool\n    script: tools/run.sh\n    bind: ['tests/*.sh']\n    timeout_s: 30\n    batch_timeout_s: 30\n",
				"tools/run.sh":      runnerScript(rel),
				c.libPath:           c.lib,
				"runnerdata/x.json": "{}\n",
			}
			if c.plugin != "" {
				extra["aitestmap/scanners/fx"] = c.plugin
			}
			r := eligRepo(t, "", extra)
			if err := os.Remove(filepath.Join(r.Dir, runner.RunnersDir, "shell.sh")); err != nil {
				t.Fatal(err)
			}
			r.Commit(t, "2", "test", "script runner")
			dirty(t, r, "runnerdata/x.json")
			if row := reasonOf(t, judged(t, r.Dir, false), "tests/test_a.sh"); row.Anchor != (c.want == "") || row.AnchorReason != c.want {
				t.Fatalf("%+v, want %q", row, c.want)
			}
		})
	}
}

// A dynamic source runs a file no closure can follow.
func TestEligibilityDynamicSourceIsOpaque(t *testing.T) {
	r := eligRepo(t, "", map[string]string{"tests/test_a.sh": testA + "source \"$DYN\"\n"})
	dirty(t, r, "docs/readme.md")
	if row := reasonOf(t, judged(t, r.Dir, false), "tests/test_a.sh"); row.Anchor || row.AnchorReason != "opaque:unresolved:tests/test_a.sh" {
		t.Fatalf("%+v", row)
	}
}

// The D12 counterexample: an unchanged helper outside the scan universe
// (gitignored), reached through an unresolved ref, itself reads a dirty file
// inside the universe. Nothing but the unresolved rule stands between that
// edit and an anchor — the control, without the ref, anchors — so it must
// stay opaque. Excluded instead of gitignored, the lifted scan follows it.
func TestEligibilityUnscannedHelperReadsDirtyFile(t *testing.T) {
	helper := "#!/usr/bin/env bash\nsource \"$(dirname \"${BASH_SOURCE[0]}\")/../../src/c.sh\"\n"
	for _, c := range []struct{ name, ref, ignore, want string }{
		{"control", "", "", ""},
		{"gitignored", "source \"$SCRIPT_DIR/gen/lib.sh\"\n", "/tests/gen/\n", "opaque:unresolved:tests/test_a.sh"},
		{"excluded", "source \"$SCRIPT_DIR/gen/lib.sh\"\n", "", "closure:src/c.sh"},
	} {
		t.Run(c.name, func(t *testing.T) {
			extra := map[string]string{
				"tests/test_a.sh":  testA + c.ref,
				"tests/gen/lib.sh": helper,
				"src/c.sh":         "echo c\n",
				".gitignore":       ".aitask-testmap/\n" + c.ignore,
			}
			if c.name == "excluded" {
				extra["aitestmap/config.yaml"] = "contract: 1\nhost_class: ci\nexclude: ['vendor/**', 'tests/gen/**']\n"
			}
			r := eligRepo(t, "", extra)
			dirty(t, r, "src/c.sh")
			if row := reasonOf(t, judged(t, r.Dir, false), "tests/test_a.sh"); row.Anchor != (c.want == "") || row.AnchorReason != c.want {
				t.Fatalf("%+v, want %q", row, c.want)
			}
		})
	}
}
