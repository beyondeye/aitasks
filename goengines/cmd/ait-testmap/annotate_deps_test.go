package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

// depsRepo is a stamping repository whose scans use a private cache.
func depsRepo(t *testing.T, files map[string]string) *fixture.Repo {
	t.Helper()
	t.Setenv("XDG_CACHE_HOME", t.TempDir())
	return stampRepo(t, files)
}

func TestSuggestThroughRun(t *testing.T) {
	depsRepo(t, map[string]string{
		"tests/t.sh": "#!/bin/bash\n" +
			"# testmap:covers .aitask-scripts/aitask_b.sh\n" +
			"SCRIPT_DIR=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)\"\n" +
			". \"$SCRIPT_DIR/lib/helper.sh\"\n" +
			"bash ./.aitask-scripts/aitask_a.sh\n" +
			"bash ./.aitask-scripts/aitask_b.sh\n",
		"tests/lib/helper.sh":         "#!/bin/bash\n./.aitask-scripts/aitask_h.sh\n",
		".aitask-scripts/aitask_a.sh": "#!/bin/sh\n",
		".aitask-scripts/aitask_b.sh": "#!/bin/sh\n",
		".aitask-scripts/aitask_h.sh": "#!/bin/sh\n",
	})
	code, out, errs := call("annotate", "--suggest", "tests/t.sh")
	want := "SUGGEST:tests/t.sh|.aitask-scripts/aitask_a.sh|static:invocation|tests/t.sh:5|exec|new\n" +
		"SUGGEST:tests/t.sh|.aitask-scripts/aitask_b.sh|static:invocation|tests/t.sh:6|exec|covered\n" +
		"SUGGEST:tests/t.sh|.aitask-scripts/aitask_h.sh|closure|tests/lib/helper.sh:2|helper:tests/lib/helper.sh|new\n" +
		"SUGGESTS:2|1\n"
	if code != 0 || errs != "" || out != want {
		t.Fatalf("%d %q\n got %q\nwant %q", code, errs, out, want)
	}
	code, out, _ = call("annotate", "--suggest", "--json", "tests/t.sh")
	var j struct {
		Suggestions []struct{ Source string } `json:"suggestions"`
	}
	if code != 0 || json.Unmarshal([]byte(out), &j) != nil || len(j.Suggestions) != 3 {
		t.Fatalf("json: %d %q", code, out)
	}
	if code, out, _ := call("annotate", "--suggest", "tests/missing.sh"); code != 1 || out != "SUGGEST_REFUSED:tests/missing.sh|missing\n" {
		t.Fatalf("refusal: %d %q", code, out)
	}
	if code, _, errs := call("annotate", "--suggest"); code != 64 || !strings.HasPrefix(errs, "USAGE:") {
		t.Fatalf("usage: %d %q", code, errs)
	}
}

func TestSuggestErrors(t *testing.T) {
	r := depsRepo(t, map[string]string{"tests/t.sh": "#!/bin/sh\n"})
	r.Write(t, "aitestmap/scanners/bad", "#!/bin/sh\necho broken >&2\nexit 1\n")
	if err := os.Chmod(filepath.Join(r.Dir, "aitestmap/scanners/bad"), 0o755); err != nil {
		t.Fatal(err)
	}
	if code, _, errs := call("annotate", "--suggest", "tests/t.sh"); code != 3 || !strings.HasPrefix(errs, "SCANNER_ERROR:bad|") {
		t.Fatalf("plugin failure: %d %q", code, errs)
	}
	t.Chdir(fixture.New(t).Dir) // no aitestmap/
	if code, _, errs := call("annotate", "--suggest", "tests/t.sh"); code != 2 || errs != "TESTMAP_ABSENT:aitestmap/\n" {
		t.Fatalf("absent: %d %q", code, errs)
	}
}

const fixtures = "package com.x.test\n" +
	"\n" +
	"import com.x.ui.OtherScreen\n" +
	"import com.x.ui.WelcomeScreen\n" +
	"import com.x.vm.WelcomeViewModel\n" +
	"\n" +
	"// testmap:unit Welcome\n" +
	"fun welcome() = WelcomeScreen(WelcomeViewModel())\n" +
	"\n" +
	"// testmap:unit Other\n" +
	"fun other() = OtherScreen()\n"

func kotlinRepo(t *testing.T) *fixture.Repo {
	t.Helper()
	return depsRepo(t, map[string]string{
		"tests/ScreenFixtures.kt":    fixtures,
		"src/ui/WelcomeScreen.kt":    "package com.x.ui\n\nclass WelcomeScreen(val vm: Any)\n",
		"src/ui/OtherScreen.kt":      "package com.x.ui\n\nclass OtherScreen\n",
		"src/vm/WelcomeViewModel.kt": "package com.x.vm\n\nclass WelcomeViewModel\n",
	})
}

func TestFromBodyThroughRun(t *testing.T) {
	r := kotlinRepo(t)
	r.Commit(t, "1", "test", "fixtures")
	code, out, errs := call("annotate", "--from-body", "--dry-run", "tests/ScreenFixtures.kt#Welcome")
	wantRefs := "FROM_BODY:tests/ScreenFixtures.kt#Welcome|src/ui/WelcomeScreen.kt|WelcomeScreen|8\n" +
		"FROM_BODY:tests/ScreenFixtures.kt#Welcome|src/vm/WelcomeViewModel.kt|WelcomeViewModel|8\n"
	if code != 0 || errs != "" || out != wantRefs {
		t.Fatalf("dry run: %d %q\n got %q", code, errs, out)
	}
	if got, _ := os.ReadFile(filepath.Join(r.Dir, "tests/ScreenFixtures.kt")); string(got) != fixtures {
		t.Fatal("--dry-run wrote")
	}
	code, out, errs = call("annotate", "--from-body", "tests/ScreenFixtures.kt#Welcome")
	if code != 0 || errs != "" {
		t.Fatalf("%d %q %q", code, out, errs)
	}
	matchOut(t, "from-body", out, regexp.QuoteMeta(wantRefs)+
		`STAMP:tests/ScreenFixtures.kt#Welcome\|src/ui/WelcomeScreen.kt\|`+stampRe+`\|added\n`+
		`STAMP:tests/ScreenFixtures.kt#Welcome\|src/vm/WelcomeViewModel.kt\|`+stampRe+`\|added\n`+
		// M2.6: the automated first stamps' provenance lands first.
		`WROTE:aitestmap/registry/adopted.yaml\nWROTE:tests/ScreenFixtures.kt\nSTAMPS:2\|0\|0\|0\n`)
	if adopted, _ := os.ReadFile(filepath.Join(r.Dir, registry.AdoptedPath)); strings.Count(string(adopted), "origin: ['"+fromBodyOrigin+"']") != 2 ||
		strings.Count(string(adopted), "by: auto") != 2 {
		t.Fatalf("adopted.yaml:\n%s", adopted)
	}
	// Only covers lines were added, right after the Welcome opener.
	diff := r.Run(t, "diff", "-U0", "--", "tests/ScreenFixtures.kt")
	var plus []string
	for _, l := range strings.Split(diff, "\n") {
		if strings.HasPrefix(l, "+") && !strings.HasPrefix(l, "+++") {
			plus = append(plus, l)
		}
		if strings.HasPrefix(l, "-") && !strings.HasPrefix(l, "---") {
			t.Errorf("removed line: %q", l)
		}
		if strings.HasPrefix(l, "@@") && !strings.Contains(l, "+8,2 @@") {
			t.Errorf("hunk outside the Welcome block: %q", l)
		}
	}
	if len(plus) != 2 || !strings.HasPrefix(plus[0], "+// testmap:covers src/ui/WelcomeScreen.kt @") ||
		!strings.HasPrefix(plus[1], "+// testmap:covers src/vm/WelcomeViewModel.kt @") {
		t.Fatalf("diff:\n%s", diff)
	}
	// The hook received the automated actor and the scanner provenance.
	last := hookCalls[len(hookCalls)-1]
	if last.actor != "auto" || len(last.edges) != 2 || last.edges[0].Origin != fromBodyOrigin {
		t.Fatalf("hook: %+v", last)
	}
	t.Setenv("AIT_AGENT_STRING", "claudecode/opus5_5")
	call("annotate", "--from-body", "tests/ScreenFixtures.kt#Other")
	if last := hookCalls[len(hookCalls)-1]; last.actor != "agent:claudecode/opus5_5" {
		t.Fatalf("actor %q", last.actor)
	}
	call("annotate", "--from-body", "--by", "human:x@example.invalid", "tests/ScreenFixtures.kt#Other")
	if last := hookCalls[len(hookCalls)-1]; last.actor != "human:x@example.invalid" || last.edges[0].Origin != fromBodyOrigin {
		t.Fatalf("explicit actor: %+v", last)
	}
}

func TestFromBodyRefusals(t *testing.T) {
	kotlinRepo(t)
	stampRepoFile := func(p, c string) {
		t.Helper()
		if err := os.WriteFile(p, []byte(c), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	stampRepoFile("t.sh", "#!/bin/sh\n# testmap:unit M\necho\n")
	stampRepoFile("tests/Empty.kt", "package e\n\n// testmap:unit Nothing\nfun f() = 1\n")
	for target, reason := range map[string]string{
		"t.sh#M":                         "not-kotlin",
		"tests/ScreenFixtures.kt":        "no-member",
		"tests/ScreenFixtures.kt#Absent": "no-member-block",
		"tests/Empty.kt#Nothing":         "no-symbols",
		"tests/Missing.kt#M":             "missing",
	} {
		code, out, _ := call("annotate", "--from-body", target)
		if code != 1 || out != "FROM_BODY_REFUSED:"+target+"|"+reason+"\n" {
			t.Errorf("%s: %d %q", target, code, out)
		}
	}
}

// The inference and the write are one guarded transaction: a member edited
// in between is re-inferred once (no stale mapping is ever written), and an
// edit on every attempt is REWRITE_CONFLICT with nothing written.
func TestFromBodyInferenceRace(t *testing.T) {
	r := kotlinRepo(t)
	path := filepath.Join(r.Dir, "tests/ScreenFixtures.kt")
	edited := strings.Replace(fixtures, "fun welcome() = WelcomeScreen(WelcomeViewModel())", "fun welcome() = OtherScreen()", 1)
	old := afterFromBodyInference
	t.Cleanup(func() { afterFromBodyInference = old })

	calls := 0
	afterFromBodyInference = func() {
		calls++
		if calls == 1 {
			if err := os.WriteFile(path, []byte(edited), 0o644); err != nil {
				t.Fatal(err)
			}
		}
	}
	code, out, errs := call("annotate", "--from-body", "tests/ScreenFixtures.kt#Welcome")
	if code != 0 || errs != "" || calls != 2 {
		t.Fatalf("recompute: %d %q %q calls=%d", code, out, errs, calls)
	}
	got, _ := os.ReadFile(path)
	if strings.Contains(string(got), "WelcomeScreen.kt") || !strings.Contains(string(got), "testmap:covers src/ui/OtherScreen.kt") {
		t.Fatalf("a stale mapping was written:\n%s", got)
	}

	if err := os.WriteFile(path, []byte(fixtures), 0o644); err != nil {
		t.Fatal(err)
	}
	flip := false
	afterFromBodyInference = func() {
		flip = !flip
		c := fixtures
		if flip {
			c = edited
		}
		if err := os.WriteFile(path, []byte(c+"// touched\n"), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	code, _, errs = call("annotate", "--from-body", "tests/ScreenFixtures.kt#Welcome")
	if code != 75 || !strings.HasPrefix(errs, "REWRITE_CONFLICT:tests/ScreenFixtures.kt|") {
		t.Fatalf("conflict: %d %q", code, errs)
	}
	got, _ = os.ReadFile(path)
	if string(got) != fixtures+"// touched\n" {
		t.Fatalf("written under conflict:\n%s", got)
	}
}

// Extension functions and properties resolve at receiver positions — by an
// explicit import, its alias, the file's own package or a star import — and
// a mixed body maps every source, so a partial mapping cannot silently omit
// the extension.
func TestFromBodyExtensions(t *testing.T) {
	depsRepo(t, map[string]string{
		"tests/ExtFixtures.kt": "package com.x.test\n" +
			"\n" +
			"import com.x.ui.WelcomeScreen\n" +
			"import com.x.text.render\n" +
			"import com.x.text.shout as yell\n" +
			"import com.x.fmt.*\n" +
			"\n" +
			"// testmap:unit Mixed\n" +
			"fun mixed() = WelcomeScreen(\"hi\".render() + \"a\".yell() + 3.padded + listOf(\"b\").map(String::local))\n" +
			"\n" +
			"// testmap:unit Plain\n" +
			"fun plain() = \"x\".length\n",
		"tests/Local.kt":          "package com.x.test\n\nfun String.local() = this\n",
		"src/ui/WelcomeScreen.kt": "package com.x.ui\n\nclass WelcomeScreen(val s: String)\n",
		"src/text/Render.kt":      "package com.x.text\n\nfun String.render() = this\n",
		"src/text/Shout.kt":       "package com.x.text\n\nfun String.shout() = uppercase()\n",
		"src/fmt/Pad.kt":          "package com.x.fmt\n\nval Int.padded: String get() = toString()\n",
		"src/fmt/Other.kt":        "package com.x.fmt\n\nfun length() = 0\n",
	})
	code, out, errs := call("annotate", "--from-body", "--dry-run", "tests/ExtFixtures.kt#Mixed")
	want := "FROM_BODY:tests/ExtFixtures.kt#Mixed|src/ui/WelcomeScreen.kt|WelcomeScreen|9\n" +
		"FROM_BODY:tests/ExtFixtures.kt#Mixed|src/text/Render.kt|render|9\n" +
		"FROM_BODY:tests/ExtFixtures.kt#Mixed|src/text/Shout.kt|yell|9\n" +
		"FROM_BODY:tests/ExtFixtures.kt#Mixed|src/fmt/Pad.kt|padded|9\n" +
		"FROM_BODY:tests/ExtFixtures.kt#Mixed|tests/Local.kt|local|9\n"
	if code != 0 || errs != "" || out != want {
		t.Fatalf("%d %q\n got %q\nwant %q", code, errs, out, want)
	}
	// A member call is not an extension: `"x".length` names no source
	// (src/fmt/Other.kt declares a non-extension `length`).
	if code, out, _ := call("annotate", "--from-body", "--dry-run", "tests/ExtFixtures.kt#Plain"); code != 1 ||
		out != "FROM_BODY_REFUSED:tests/ExtFixtures.kt#Plain|no-symbols\n" {
		t.Fatalf("plain: %d %q", code, out)
	}
}
