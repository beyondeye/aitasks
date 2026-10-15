package annot

// The annot conformance gate (t1991): the bash, Python, Go and Kotlin part of
// the t1954 parser-research corpus, replayed through the real ParseFile →
// PlanCovers → Apply on scratch copies, scored the way the research harness
// scored its `baseline` subject. The research kept these hand readers on the
// condition that a reader regression fails `go test`; this is that gate.
//
// testdata/conformance/<lang>/ holds byte-for-byte copies of the research
// fixtures (<case>.<ext>.in, .expect, optional .edits). PROVENANCE names the
// corpus commit they came from and a sha256 per file. Refresh after the
// research corpus changes:
//
//	R=aidocs/testing_engine/t1954_parser_research/corpus
//	D=goengines/internal/testmap/annot/testdata/conformance
//	rm -r "$D"/bash "$D"/python "$D"/go "$D"/kotlin
//	cp -p -r "$R"/bash "$R"/python "$R"/go "$R"/kotlin "$D"/
//	# PROVENANCE: keep the header, set commit: to the corpus commit, then
//	(cd "$D" && find bash python go kotlin -type f | LC_ALL=C sort | xargs sha256sum)
//
// tests/test_annot_conformance_corpus_sync.sh fails while the copy and the
// research corpus differ.
//
// The rule: every deviation from a fixture's oracle is a finding, and every
// finding must be pinned in confKnown — never skipped. A pinned finding that
// stops occurring fails too, so a reader fix shows up as a test change. A
// safety finding may be pinned only with the task that removes it.

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io/fs"
	"maps"
	"os"
	"path/filepath"
	"regexp"
	"slices"
	"sort"
	"strconv"
	"strings"
	"testing"
)

const confDir = "testdata/conformance"

var confLangs = []string{"bash", "python", "go", "kotlin"}

// confProbeStamp is the stamp of every write probe (the research raw ops use it too).
var confProbeStamp = Stamp{Date: "2026-02-02", Blob: "bbbbbbbbbb"}

// confSafety are the finding categories that are a safety failure: a write
// into data, a silent certainty, a corrupted record or file, or a harness
// error. Every other category is a cost (recall, over-refusal) or a policy
// reading.
var confSafety = []string{
	"FP-writable", "docstring-write", "silent-uncertain", "record-corruption",
	"fidelity", "error", "probe-error",
}

// confPin is one case's measured deviations from its oracle.
type confPin struct {
	why      string   // the classification, in one line
	tracking string   // the task that removes it; required for a safety finding
	findings []string // the exact finding texts
}

// confKnown pins every measured deviation, by case. The over-refusals are the
// research's measured costs (results/t4/matrix_baseline.md): a refusal writes
// nothing. The x-policy lines are real comments to a native tool that the
// M2.2 policy never treats as annotation lines; their class is pinned so a
// policy change shows up here.
var confKnown = map[string]confPin{
	"bash/heredoc_in_backtick_subst.sh": {
		why: "over-refusal: the bash reader refuses a heredoc inside backticks (unsupported construct)",
		findings: []string{
			"over-refusal: valid file uncertain at line 2 (heredoc inside backticks)",
			"refusal: got uncertain@2, want none",
			"cost: probe line 3: refused:uncertain, want refused:not-comment",
		},
	},
	"bash/lex_arith_or_subshell_across_lines.sh": {
		why:      "over-refusal: the bash reader refuses the ambiguous `$((` form by design",
		findings: []string{"over-refusal: valid file uncertain at line 1 (arithmetic or subshell)"},
	},
	"bash/lex_heredoc_escape_in_quoted_delimiter.sh": {
		why: "over-refusal: the bash reader refuses ANSI-C escapes in a heredoc delimiter by design",
		findings: []string{
			"over-refusal: valid file uncertain at line 1 (heredoc delimiter)",
			"refusal: got uncertain@1, want none",
		},
	},
	"bash/lex_backtick_spanning.sh": {
		why:      "x-policy: a comment inside a backtick substitution is data to the reader",
		findings: []string{"policy: line 2 classed Literal"},
	},
	"bash/lex_continuation_line_is_code.sh": {
		why:      "x-policy: after a `\\` continuation the line is a trailing comment of the command, never an annotation line",
		findings: []string{"policy: line 2 classed Code"},
	},
	"python/lex_continuation.py": {
		why:      "x-policy: after a `\\` continuation the line is a comment trailing an incomplete expression",
		findings: []string{"policy: line 2 classed Code"},
	},
	"python/tstrings_314.py": {
		why:      "x-policy: a comment inside a multi-line t-string field is not an annotation line",
		findings: []string{"policy: line 5 classed Literal"},
	},
}

// confSensitiveProbes is how many protected lines per language get a write
// probe that a misclassification would let through (see confBuildProbe), so
// probe coverage cannot shrink silently.
var confSensitiveProbes = map[string]int{"bash": 39, "python": 16, "go": 13, "kotlin": 16}

func confCategory(finding string) string {
	cat, _, _ := strings.Cut(finding, ": ")
	return cat
}

func confFindingf(cat, format string, a ...any) string {
	return cat + ": " + fmt.Sprintf(format, a...)
}

func TestConformance(t *testing.T) {
	cases := confLoad(t)
	ids := map[string]bool{}
	for _, c := range cases {
		ids[c.ID()] = true
		t.Run(c.ID(), func(t *testing.T) {
			confComparePins(t, confCheck(t, c), confKnown[c.ID()].findings)
		})
	}
	for _, id := range slices.Sorted(maps.Keys(confKnown)) {
		if !ids[id] {
			t.Errorf("confKnown pins %s, which is not a case", id)
		}
	}
}

// TestConformanceProbeCoverage counts the sensitive write probes over every
// case, whichever TestConformance subtests a -run pattern selects. It only
// builds the probes; TestConformance runs them.
func TestConformanceProbeCoverage(t *testing.T) {
	sensitive := map[string]int{}
	for _, c := range confLoad(t) {
		lang, ok := LangOf(c.Name, c.Data)
		if !ok {
			t.Fatalf("%s: no language", c.ID())
		}
		f, _ := ParseFile(c.Name, c.Data)
		for _, n := range confProtected(c) {
			if confBuildProbe(c, lang, f, n).Sensitive {
				sensitive[c.Lang]++
			}
		}
	}
	if !maps.Equal(sensitive, confSensitiveProbes) {
		t.Errorf("sensitive write probes per language: got %v, want %v (confSensitiveProbes)", sensitive, confSensitiveProbes)
	}
}

// TestConformanceKnownTable: a pin explains itself, and "safety = 0" holds
// except for named, tracked defects.
func TestConformanceKnownTable(t *testing.T) {
	for _, id := range slices.Sorted(maps.Keys(confKnown)) {
		p := confKnown[id]
		if p.why == "" || len(p.findings) == 0 {
			t.Errorf("%s: a pin needs a why and at least one finding", id)
		}
		for _, f := range p.findings {
			if slices.Contains(confSafety, confCategory(f)) && p.tracking == "" {
				t.Errorf("%s: safety finding pinned without a tracking task: %s", id, f)
			}
		}
	}
}

// confComparePins fails on every unpinned finding and every pin not observed.
func confComparePins(t *testing.T, got, pinned []string) {
	t.Helper()
	left := map[string]int{}
	for _, p := range pinned {
		left[p]++
	}
	for _, f := range got {
		if left[f] > 0 {
			left[f]--
			continue
		}
		t.Errorf("unpinned finding: %s", f)
	}
	for _, p := range slices.Sorted(maps.Keys(left)) {
		for range left[p] {
			t.Errorf("pinned but not observed (fixed? update confKnown): %s", p)
		}
	}
}

// confLoad reads every case and checks the count against PROVENANCE.
func confLoad(t *testing.T) []confCase {
	t.Helper()
	cases, err := loadConfCases(confDir)
	if err != nil {
		t.Fatal(err)
	}
	_, sums := confProvenance(t)
	ins := 0
	for p := range sums {
		if strings.HasSuffix(p, ".in") {
			ins++
		}
	}
	if len(cases) == 0 || len(cases) != ins {
		t.Fatalf("loaded %d cases, PROVENANCE lists %d .in files", len(cases), ins)
	}
	return cases
}

// confProvenance parses PROVENANCE: the corpus commit and <lang>/<file> -> sha256.
func confProvenance(t *testing.T) (commit string, sums map[string]string) {
	t.Helper()
	data, err := os.ReadFile(filepath.Join(confDir, "PROVENANCE"))
	if err != nil {
		t.Fatal(err)
	}
	sums = map[string]string{}
	for i, l := range strings.Split(strings.TrimSuffix(string(data), "\n"), "\n") {
		switch {
		case l == "" || strings.HasPrefix(l, "#"):
		case strings.HasPrefix(l, "commit: "):
			commit = strings.TrimPrefix(l, "commit: ")
		case strings.HasPrefix(l, "source: "), strings.HasPrefix(l, "research-pin: "):
		default:
			sum, p, ok := strings.Cut(l, "  ")
			if !ok || len(sum) != 64 {
				t.Fatalf("PROVENANCE:%d: want <sha256>  <lang>/<file>, got %q", i+1, l)
			}
			if _, dup := sums[p]; dup {
				t.Fatalf("PROVENANCE:%d: %s listed twice", i+1, p)
			}
			sums[p] = sum
		}
	}
	return commit, sums
}

// TestConformanceProvenance: the fixtures are exactly the listed bytes, and
// nothing unlisted sits beside them.
func TestConformanceProvenance(t *testing.T) {
	commit, sums := confProvenance(t)
	if !regexp.MustCompile(`^[0-9a-f]{40}$`).MatchString(commit) {
		t.Errorf("PROVENANCE commit: %q, want a 40-hex commit id", commit)
	}
	top, err := os.ReadDir(confDir)
	if err != nil {
		t.Fatal(err)
	}
	for _, e := range top {
		if e.Name() != "PROVENANCE" && !(e.IsDir() && slices.Contains(confLangs, e.Name())) {
			t.Errorf("unexpected entry %s in %s", e.Name(), confDir)
		}
	}
	seen := map[string]bool{}
	for _, lang := range confLangs {
		err := filepath.WalkDir(filepath.Join(confDir, lang), func(p string, d fs.DirEntry, err error) error {
			if err != nil || d.IsDir() {
				return err
			}
			rel := filepath.ToSlash(strings.TrimPrefix(p, confDir+string(filepath.Separator)))
			seen[rel] = true
			want, ok := sums[rel]
			if !ok {
				t.Errorf("%s is not listed in PROVENANCE", rel)
				return nil
			}
			data, err := os.ReadFile(p)
			if err != nil {
				return err
			}
			sum := sha256.Sum256(data)
			if got := hex.EncodeToString(sum[:]); got != want {
				t.Errorf("%s: sha256 %s, PROVENANCE says %s", rel, got, want)
			}
			return nil
		})
		if err != nil {
			t.Fatal(err)
		}
	}
	for _, p := range slices.Sorted(maps.Keys(sums)) {
		if !seen[p] {
			t.Errorf("PROVENANCE lists %s, which is missing", p)
		}
	}
}

// confCheck scores one case at every level and returns its findings.
func confCheck(t *testing.T, c confCase) (findings []string) {
	t.Helper()
	add := func(cat, format string, a ...any) { findings = append(findings, confFindingf(cat, format, a...)) }
	lang, ok := LangOf(c.Name, c.Data)
	if !ok || lang.Name != c.Exp.Lang {
		t.Fatalf("%s: LangOf gives %q (ok=%v), .expect says lang: %s", c.ID(), lang.Name, ok, c.Exp.Lang)
	}
	policy, err := parseConfLines(c.Exp.Extra["x-policy"])
	if err != nil {
		t.Fatalf("%s: x-policy: %v", c.ID(), err)
	}
	confLexical(c, lang, policy, add)
	confReadLevel(c, policy, add)
	if len(c.Edits) > 0 {
		confEdits(t, c, add)
	}
	confProbes(t, c, lang, policy, add)
	return findings
}

func confClassName(c LineClass) string {
	switch c {
	case Comment:
		return "Comment"
	case Literal:
		return "Literal"
	}
	return "Code"
}

// confLexical scores the line classes. When the context is uncertain its
// classes are never used (ParseFile and Apply refuse), so only the refusal is
// scored.
func confLexical(c confCase, lang Lang, policy []int, add func(string, string, ...any)) {
	ctx := Classify(lang, c.Data)
	class := func(n int) LineClass {
		if n < 1 || n > len(ctx.Class) {
			return Code
		}
		return ctx.Class[n-1]
	}
	certain := ctx.Uncertain == nil
	for _, n := range policy {
		add("policy", "line %d classed %s", n, confClassName(class(n)))
	}
	for _, n := range append(slices.Clone(c.Exp.Lookalikes), c.Exp.Readonly...) {
		if !slices.Contains(policy, n) && certain && class(n) == Comment {
			add("FP-writable", "line %d classed Comment (look-alike/read-only)", n)
		}
	}
	for _, n := range c.Exp.Writable {
		if certain && class(n) != Comment {
			add("missed-writable", "line %d classed %s", n, confClassName(class(n)))
		}
	}
	if certain {
		for _, n := range c.Exp.Comments {
			if class(n) != Comment && !slices.Contains(c.Exp.Writable, n) {
				add("missed-comment", "line %d classed %s", n, confClassName(class(n)))
			}
		}
	}
	switch {
	case c.Exp.Uncertain && certain:
		add("silent-uncertain", "expect uncertain, got certain")
	case !c.Exp.Uncertain && !certain:
		add("over-refusal", "valid file uncertain at line %d (%s)", ctx.Uncertain.Line, ctx.Uncertain.Construct)
	}
}

func confRefusalOf(err error) string {
	var se *SyntaxError
	switch {
	case err == nil:
		return ""
	case errors.Is(err, ErrNoLeader):
		return "no-leader"
	case errors.As(err, &se):
		if strings.HasPrefix(se.Reason, "cannot determine comment context") {
			return fmt.Sprintf("uncertain@%d", se.Line)
		}
		return fmt.Sprintf("syntax@%d", se.Line)
	}
	return "error:" + confOneLine(err.Error())
}

// confSameRefusal: an uncertain-context refusal matches without its line; a
// refusal the oracle gives without a line matches on its kind.
func confSameRefusal(got, want string) bool {
	if strings.HasPrefix(got, "uncertain") && strings.HasPrefix(want, "uncertain") {
		return true
	}
	if want != "" && !strings.Contains(want, "@") {
		kind, _, _ := strings.Cut(got, "@")
		return kind == want
	}
	return got == want
}

func confNone(s string) string {
	if s == "" {
		return "none"
	}
	return s
}

func confOneLine(s string) string { return strings.NewReplacer("\n", " ", "|", "/").Replace(s) }

// confReadLevel scores ParseFile: the refusal, the read records, placement.
func confReadLevel(c confCase, policy []int, add func(string, string, ...any)) {
	f, err := ParseFile(c.Name, c.Data)
	got := confRefusalOf(err)
	if !confSameRefusal(got, c.Exp.Refuse) {
		if strings.HasPrefix(got, "error:") {
			add("error", "ParseFile: %s", got)
		} else {
			add("refusal", "got %s, want %s", confNone(got), confNone(c.Exp.Refuse))
		}
	}
	if err != nil {
		return
	}
	want := map[string]int{}
	for _, r := range c.Exp.Read {
		want[r.String()]++
	}
	for _, r := range confRecords(f) {
		k := r.String()
		if want[k] > 0 {
			want[k]--
			continue
		}
		add("read", "extra %s", k)
		protected := slices.Contains(c.Exp.Lookalikes, r.Line) || slices.Contains(c.Exp.Readonly, r.Line)
		if r.Origin == "comment" && protected && !slices.Contains(policy, r.Line) {
			add("FP-writable", "look-alike/read-only line %d read as a comment annotation", r.Line)
		}
	}
	for _, k := range slices.Sorted(maps.Keys(want)) {
		for range want[k] {
			add("read", "missing %s", k)
		}
	}
	for _, m := range slices.Sorted(maps.Keys(c.Exp.Placement)) {
		block := "file"
		if m != "" {
			block = "member:" + m
		}
		if _, ok := f.Unit(m); !ok {
			add("placement", "%s: no such block", block)
			continue
		}
		after, _, _, err := f.Placement(m)
		switch {
		case err != nil:
			add("placement", "%s: %v", block, err)
		case after != c.Exp.Placement[m]:
			add("placement", "%s: got after %d, want %d", block, after, c.Exp.Placement[m])
		}
	}
}

// confRecords flattens a parsed file into records, in line order.
func confRecords(f *File) []confRecord {
	var out []confRecord
	origin := func(l Line) string {
		if l.Docstring {
			return "docstring"
		}
		return "comment"
	}
	for _, u := range f.Units {
		if u.Member != "" {
			out = append(out, confRecord{Line: u.Opener.No, Member: u.Member, Key: "unit", Value: u.Member, Origin: origin(u.Opener)})
		}
		kv := func(k *KeyVal) {
			if k != nil {
				out = append(out, confRecord{Line: k.Line.No, Member: u.Member, Key: k.Key, Value: strings.Join(k.Args, " "), Origin: origin(k.Line)})
			}
		}
		kv(u.Kind)
		kv(u.Runner)
		kv(u.Batch)
		kv(u.Reviewed)
		for _, list := range [][]KeyVal{u.Areas, u.Scopes, u.Triggers, u.Reads, u.Needs, u.Axes} {
			for i := range list {
				kv(&list[i])
			}
		}
		for _, cv := range u.Covers {
			st := ""
			if !cv.Stamp.IsZero() {
				st = cv.Stamp.String()
			}
			out = append(out, confRecord{Line: cv.Line.No, Member: u.Member, Key: "covers", Value: cv.Source, Stamp: st, Origin: origin(cv.Line)})
		}
	}
	sort.SliceStable(out, func(i, j int) bool {
		if out[i].Line != out[j].Line {
			return out[i].Line < out[j].Line
		}
		return out[i].Key < out[j].Key
	})
	return out
}

// confDiffRecords compares two record lists, order included.
func confDiffRecords(want, got []confRecord) string {
	str := func(rs []confRecord) []string {
		out := make([]string, len(rs))
		for i, r := range rs {
			out[i] = r.String()
		}
		return out
	}
	w, g := str(want), str(got)
	if slices.Equal(w, g) {
		return ""
	}
	gm, wm := map[string]int{}, map[string]int{}
	for _, x := range g {
		gm[x]++
	}
	for _, x := range w {
		wm[x]++
	}
	var parts []string
	for _, x := range w {
		if gm[x] == 0 {
			parts = append(parts, "missing "+x)
		} else {
			gm[x]--
		}
	}
	for _, x := range g {
		if wm[x] == 0 {
			parts = append(parts, "extra "+x)
		} else {
			wm[x]--
		}
	}
	if len(parts) == 0 {
		parts = append(parts, "order differs")
	}
	return strings.Join(parts, "; ")
}

// confOutcomeOf names what Apply (or the planning before it) did.
func confOutcomeOf(changed bool, err error) string {
	var ce *ConflictError
	var se *SyntaxError
	switch {
	case err == nil && changed:
		return "applied"
	case err == nil:
		return "unchanged"
	case errors.Is(err, ErrDocstring):
		return "refused:docstring"
	case errors.Is(err, ErrNotComment):
		return "refused:not-comment"
	case errors.Is(err, ErrUncertainContext):
		return "refused:uncertain"
	case errors.Is(err, ErrNoMemberBlock):
		return "refused:no-member-block"
	case errors.Is(err, ErrByteOrderMark):
		return "refused:byte-order-mark"
	case errors.As(err, &ce):
		return "refused:conflict"
	case errors.As(err, &se):
		if strings.HasPrefix(se.Reason, "cannot determine comment context") {
			return "refused:uncertain"
		}
		return "refused:syntax"
	}
	return "error:" + confOneLine(err.Error())
}

// confWriteFixture (re)creates a scratch copy with the fixture's mode.
func confWriteFixture(t *testing.T, abs string, data []byte, mode os.FileMode) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(abs), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(abs, data, 0o600); err != nil {
		t.Fatal(err)
	}
	if err := os.Chmod(abs, mode); err != nil {
		t.Fatal(err)
	}
}

func confReadStat(t *testing.T, abs string) ([]byte, os.FileMode) {
	t.Helper()
	data, err := os.ReadFile(abs)
	if err != nil {
		t.Fatal(err)
	}
	st, err := os.Stat(abs)
	if err != nil {
		t.Fatal(err)
	}
	return data, st.Mode().Perm()
}

// confEdits runs the .edits ops on one scratch copy: `from=original` resets
// it, every other op builds on the file the previous one left.
func confEdits(t *testing.T, c confCase, add func(string, string, ...any)) {
	t.Helper()
	root := t.TempDir()
	rel := "tests/" + c.Name
	abs := filepath.Join(root, "tests", c.Name)
	confWriteFixture(t, abs, c.Data, c.Mode)
	for i, op := range c.Edits {
		tag := fmt.Sprintf("op %d (%s)", i+1, op.Text)
		if op.Args["from"] == "original" {
			confWriteFixture(t, abs, c.Data, c.Mode)
		}
		_, mode := confReadStat(t, abs) // the mode before the op
		got, cur := confRunOp(t, root, rel, abs, op)
		now, nmode := confReadStat(t, abs)
		if got != op.Outcome {
			switch {
			case strings.HasPrefix(got, "error:"):
				add("error", "%s: %s", tag, got)
			case op.Outcome == "refused:docstring" && got == "applied":
				add("docstring-write", "%s: outcome %s, want %s", tag, got, op.Outcome)
			case op.Outcome == "refused:not-comment" && got == "applied":
				add("FP-writable", "%s: outcome %s, want %s", tag, got, op.Outcome)
			case op.Outcome == "refused:uncertain" && got == "applied":
				add("silent-uncertain", "%s: outcome %s, want %s", tag, got, op.Outcome)
			case op.Outcome == "applied" && strings.HasPrefix(got, "refused"):
				add("over-refusal", "%s: outcome %s, want %s", tag, got, op.Outcome)
			case strings.HasPrefix(op.Outcome, "refused") && strings.HasPrefix(got, "refused"):
				add("cost", "%s: refused for a different reason (%s, want %s)", tag, got, op.Outcome)
			default:
				add("record-corruption", "%s: outcome %s, want %s", tag, got, op.Outcome)
			}
		}
		// The complete record list after the op.
		var recs []confRecord
		if nf, err := ParseFile(c.Name, now); err == nil {
			recs = confRecords(nf)
		}
		if d := confDiffRecords(op.After, recs); d != "" {
			if bytes.Equal(cur, now) {
				add("cost", "%s: records after differ (file untouched): %s", tag, d)
			} else {
				add("record-corruption", "%s: records after differ: %s", tag, d)
			}
		}
		if got == "applied" {
			for _, v := range confFidelity(cur, now, mode, nmode) {
				add("fidelity", "%s: %s", tag, v)
			}
			continue
		}
		if !bytes.Equal(cur, now) {
			add("record-corruption", "%s: file changed although the op was %s", tag, got)
		}
		if mode != nmode {
			add("record-corruption", "%s: mode %v -> %v although the op was %s", tag, mode, nmode, got)
		}
	}
}

// confRunOp performs one op on the scratch file and returns its outcome and
// the bytes Apply saw (a stale op's mutation included).
func confRunOp(t *testing.T, root, rel, abs string, op confOp) (outcome string, seen []byte) {
	t.Helper()
	data, _ := confReadStat(t, abs)
	if op.Kind == "raw" {
		return confRawOp(t, root, rel, data, op), data
	}
	stamp, err := ParseStamp(op.Args["stamp"])
	if err != nil {
		t.Fatalf("%s: stamp: %v", op.Text, err)
	}
	f, err := ParseFile(filepath.Base(rel), data)
	if err != nil {
		return confOutcomeOf(false, err), data
	}
	e, err := PlanCovers(f, op.Args["member"], op.Args["source"], stamp)
	if err != nil {
		return confOutcomeOf(false, err), data
	}
	set := EditSet{Path: rel, Snapshot: f.Snapshot(), Edits: []Edit{e}}
	if op.Kind == "stale" {
		confMutate(t, abs, data, op.Args["mutate"])
		data, _ = confReadStat(t, abs)
	}
	changed, err := Apply(root, set)
	return confOutcomeOf(changed, err), data
}

// confRawOp hands Apply a direct edit, as a buggy caller would.
func confRawOp(t *testing.T, root, rel string, data []byte, op confOp) string {
	t.Helper()
	n, err := strconv.Atoi(op.Args["line"])
	if err != nil {
		t.Fatalf("%s: line: %v", op.Text, err)
	}
	lines := strings.Split(strings.TrimSuffix(string(data), "\n"), "\n")
	want := ""
	if n > 0 && n <= len(lines) {
		want = strings.TrimSuffix(lines[n-1], "\r")
	}
	e := Edit{Line: n, Want: want, New: op.Args["new"], Member: op.Args["member"], Source: op.Args["source"]}
	switch op.Args["kind"] {
	case "replace":
		e.Kind = Replace
	case "insert-after":
		e.Kind = InsertAfter
	default:
		t.Fatalf("%s: raw kind %q", op.Text, op.Args["kind"])
	}
	changed, err := Apply(root, EditSet{Path: rel, Edits: []Edit{e}})
	return confOutcomeOf(changed, err)
}

// confMutate changes the scratch file between planning and Apply (a stale plan).
func confMutate(t *testing.T, abs string, data []byte, spec string) {
	t.Helper()
	eol := "\n"
	if bytes.Contains(data, []byte("\r\n")) {
		eol = "\r\n"
	}
	var out []byte
	how, arg, _ := strings.Cut(spec, ":")
	switch how {
	case "append":
		out = slices.Clone(data)
		if len(out) > 0 && !bytes.HasSuffix(out, []byte("\n")) {
			out = append(out, eol...)
		}
		out = append(out, (arg + eol)...)
	case "replace":
		ns, text, _ := strings.Cut(arg, ":")
		n, err := strconv.Atoi(ns)
		lines := strings.SplitAfter(string(data), "\n")
		if err != nil || n < 1 || n > len(lines) {
			t.Fatalf("mutate %q: bad line", spec)
		}
		end := ""
		if strings.HasSuffix(lines[n-1], "\n") {
			end = eol
		}
		lines[n-1] = text + end
		out = []byte(strings.Join(lines, ""))
	default:
		t.Fatalf("mutate %q: want append:<text> or replace:<n>:<text>", spec)
	}
	if err := os.WriteFile(abs, out, 0o600); err != nil {
		t.Fatal(err)
	}
}

// confFidelity checks an applied single-line edit independently of Apply's
// own checks: one line inserted or replaced, every other line byte-identical,
// and the BOM, CRLF convention, final-newline state and mode preserved.
func confFidelity(old, now []byte, oldMode, newMode os.FileMode) []string {
	var v []string
	if bytes.HasPrefix(old, []byte(bom)) != bytes.HasPrefix(now, []byte(bom)) {
		v = append(v, "BOM changed")
	}
	if bytes.HasSuffix(old, []byte("\n")) != bytes.HasSuffix(now, []byte("\n")) {
		v = append(v, "final-newline state changed")
	}
	if oldMode.Perm() != newMode.Perm() {
		v = append(v, fmt.Sprintf("mode %v -> %v", oldMode.Perm(), newMode.Perm()))
	}
	ol := strings.Split(strings.TrimSuffix(string(old), "\n"), "\n")
	nl := strings.Split(strings.TrimSuffix(string(now), "\n"), "\n")
	allCR := func(ls []string, finalNL bool) bool {
		for i, l := range ls {
			if i == len(ls)-1 && !finalNL {
				continue
			}
			if !strings.HasSuffix(l, "\r") {
				return false
			}
		}
		return len(ls) > 0
	}
	if allCR(ol, bytes.HasSuffix(old, []byte("\n"))) && !allCR(nl, bytes.HasSuffix(now, []byte("\n"))) {
		v = append(v, "CRLF convention broken")
	}
	switch len(nl) - len(ol) {
	case 0:
		diffs := 0
		for i := range ol {
			if ol[i] != nl[i] {
				diffs++
			}
		}
		if diffs != 1 {
			v = append(v, fmt.Sprintf("replace changed %d lines", diffs))
		}
	case 1:
		i := 0
		for i < len(ol) && ol[i] == nl[i] {
			i++
		}
		if strings.Join(ol[i:], "\n") != strings.Join(nl[i+1:], "\n") {
			v = append(v, "insert changed other lines")
		}
	default:
		v = append(v, fmt.Sprintf("line count changed by %d", len(nl)-len(ol)))
	}
	return v
}

// confProbe is a direct Replace aimed at one line, as a buggy caller would
// send it.
type confProbe struct {
	Line int
	Edit Edit
	// Sensitive: the line is a covers line in all but its lexical context, so
	// if the reader misclassified it as a comment, Apply would write it.
	Sensitive bool
}

// confCoversShaped returns the source of a line that reads as a covers
// annotation once its lexical context is ignored: indent, the language's
// leader, blanks, `testmap:covers <path>`.
func confCoversShaped(lang Lang, n int, text string) (string, bool) {
	s := text
	if n == 1 && lang.SkipsBOM {
		s = strings.TrimPrefix(s, bom)
	}
	rest, ok := strings.CutPrefix(strings.TrimLeft(s, " \t"), lang.Leader)
	if !ok {
		return "", false
	}
	rest, ok = strings.CutPrefix(strings.TrimLeft(rest, " \t"), Token+"covers")
	if !ok || rest == "" || (rest[0] != ' ' && rest[0] != '\t') {
		return "", false
	}
	fields := strings.Fields(rest)
	if len(fields) == 0 {
		return "", false
	}
	return fields[0], true
}

// confMemberAt is the block that owns a line at n: the member of the last
// unit opener above it, "" (the file-level block) when there is none.
func confMemberAt(f *File, n int) string {
	m := ""
	if f == nil {
		return m
	}
	for _, u := range f.Units {
		if u.Member != "" && u.Opener.No < n {
			m = u.Member
		}
	}
	return m
}

// confBuildProbe builds the Replace probe for line n of c. The edit is well
// formed for the line's position, so a refusal can only come from the
// reader's protection (TestConformanceCheckerCatches proves the same builder
// is accepted on real annotation lines).
func confBuildProbe(c confCase, lang Lang, f *File, n int) confProbe {
	lines := strings.Split(strings.TrimSuffix(string(c.Data), "\n"), "\n")
	text := ""
	if n >= 1 && n <= len(lines) {
		text = strings.TrimSuffix(lines[n-1], "\r")
	}
	p := confProbe{Line: n, Edit: Edit{Kind: Replace, Line: n, Want: text}}
	if src, ok := confCoversShaped(lang, n, text); ok {
		nl, _ := RestampLine(text, confProbeStamp)
		p.Edit.New, p.Edit.Member, p.Edit.Source, p.Sensitive = nl, confMemberAt(f, n), src, true
		return p
	}
	member, source := confMemberAt(f, n), "src/conformance_probe"
	for _, r := range c.Exp.Read {
		if r.Line == n && r.Origin == "docstring" && r.Key == "covers" {
			member, source = r.Member, r.Value
		}
	}
	p.Edit.New = indentOf(text) + lang.Leader + " " + Token + "covers " + source + " " + confProbeStamp.String()
	p.Edit.Member, p.Edit.Source = member, source
	return p
}

// confRunProbe applies a probe to a fresh scratch copy of c and returns the
// outcome with the bytes and mode before and after.
func confRunProbe(t *testing.T, c confCase, p confProbe) (got string, after []byte, afterMode os.FileMode) {
	t.Helper()
	root := t.TempDir()
	abs := filepath.Join(root, "tests", c.Name)
	confWriteFixture(t, abs, c.Data, c.Mode)
	changed, err := Apply(root, EditSet{Path: "tests/" + c.Name, Edits: []Edit{p.Edit}})
	after, afterMode = confReadStat(t, abs)
	return confOutcomeOf(changed, err), after, afterMode
}

// confProbeWant is the refusal that protects every labelled line of c.
func confProbeWant(c confCase) string {
	switch {
	case c.Exp.Uncertain || strings.HasPrefix(c.Exp.Refuse, "uncertain"):
		return "refused:uncertain"
	case strings.HasPrefix(c.Exp.Refuse, "syntax"):
		return "refused:syntax"
	}
	return "refused:not-comment"
}

// confJudgeProbe turns a probe's outcome into findings. An accepted probe is
// a write into data; a conflict or an error is a harness mistake and never
// passes as a protective refusal.
func confJudgeProbe(c confCase, policy []int, p confProbe, got string, after []byte, afterMode os.FileMode) []string {
	var out []string
	tag := fmt.Sprintf("probe line %d", p.Line)
	want := confProbeWant(c)
	switch {
	case got == "applied" || got == "unchanged":
		switch {
		case slices.Contains(policy, p.Line):
			out = append(out, confFindingf("policy", "%s %s", tag, got))
		case slices.Contains(c.Exp.Readonly, p.Line):
			out = append(out, confFindingf("docstring-write", "%s %s", tag, got))
		default:
			out = append(out, confFindingf("FP-writable", "%s %s", tag, got))
		}
		return out
	case got == "refused:conflict" || strings.HasPrefix(got, "error:"):
		out = append(out, confFindingf("probe-error", "%s: %s", tag, got))
	case got != want:
		out = append(out, confFindingf("cost", "%s: %s, want %s", tag, got, want))
	}
	if !bytes.Equal(after, c.Data) {
		out = append(out, confFindingf("record-corruption", "%s: %s but the file changed", tag, got))
	}
	if afterMode != c.Mode {
		out = append(out, confFindingf("record-corruption", "%s: %s but the mode changed %v -> %v", tag, got, c.Mode, afterMode))
	}
	return out
}

// confProtected is every labelled look-alike and read-only line of c, sorted.
func confProtected(c confCase) []int {
	var protected []int
	for _, n := range append(slices.Clone(c.Exp.Lookalikes), c.Exp.Readonly...) {
		if !slices.Contains(protected, n) {
			protected = append(protected, n)
		}
	}
	slices.Sort(protected)
	return protected
}

// confProbes sends one direct Replace at every labelled look-alike and
// read-only line, each on its own fresh copy: the write path itself, for
// fixtures whose .edits never touch those lines (or have no .edits).
func confProbes(t *testing.T, c confCase, lang Lang, policy []int, add func(string, string, ...any)) {
	t.Helper()
	f, _ := ParseFile(c.Name, c.Data) // nil on a refused file: the probes are refused anyway
	for _, n := range confProtected(c) {
		p := confBuildProbe(c, lang, f, n)
		got, after, mode := confRunProbe(t, c, p)
		for _, fd := range confJudgeProbe(c, policy, p, got, after, mode) {
			add(confCategory(fd), "%s", strings.TrimPrefix(fd, confCategory(fd)+": "))
		}
	}
}

// TestConformanceCheckerCatches: a gate that flags nothing proves nothing.
// Each check above is fed a deliberately wrong oracle or a known-bad input
// and must report it — without touching the readers.
func TestConformanceCheckerCatches(t *testing.T) {
	load := func(t *testing.T, id string) confCase {
		t.Helper()
		c, err := loadConfCase(filepath.Join(confDir, id+".in"))
		if err != nil {
			t.Fatal(err)
		}
		return c
	}
	has := func(t *testing.T, got []string, want string) {
		t.Helper()
		if !slices.Contains(got, want) {
			t.Errorf("missing finding %q in %q", want, got)
		}
	}
	const id = "go/ordinary.go"
	if got := confCheck(t, load(t, id)); len(got) != 0 {
		t.Fatalf("%s must be clean for these controls, got %q", id, got)
	}

	t.Run("look-alike classed Comment", func(t *testing.T) {
		c := load(t, id)
		c.Exp.Writable = slices.DeleteFunc(c.Exp.Writable, func(n int) bool { return n == 4 })
		c.Exp.Read = slices.DeleteFunc(c.Exp.Read, func(r confRecord) bool { return r.Line == 4 })
		c.Exp.Lookalikes = append(c.Exp.Lookalikes, 4)
		got := confCheck(t, c)
		has(t, got, "FP-writable: line 4 classed Comment (look-alike/read-only)")
		has(t, got, "FP-writable: look-alike/read-only line 4 read as a comment annotation")
		has(t, got, "FP-writable: probe line 4 applied")
	})
	t.Run("silent uncertain", func(t *testing.T) {
		c := load(t, id)
		c.Exp.Uncertain = true
		got := confCheck(t, c)
		has(t, got, "silent-uncertain: expect uncertain, got certain")
	})
	t.Run("refused op applied", func(t *testing.T) {
		c := load(t, id)
		c.Edits[0].Outcome = "refused:conflict"
		got := confCheck(t, c)
		has(t, got, fmt.Sprintf("record-corruption: op 1 (%s): outcome applied, want refused:conflict", c.Edits[0].Text))
	})
	t.Run("records after an op", func(t *testing.T) {
		c := load(t, id)
		last := c.Edits[1].After[len(c.Edits[1].After)-1]
		c.Edits[1].After = c.Edits[1].After[:len(c.Edits[1].After)-1]
		got := confCheck(t, c)
		has(t, got, fmt.Sprintf("record-corruption: op 2 (%s): records after differ: extra %s", c.Edits[1].Text, last))
	})
	t.Run("fidelity", func(t *testing.T) {
		for _, tc := range []struct {
			old, now   string
			oldM, newM os.FileMode
			want       string
		}{
			{bom + "a\nb\n", "a\nb\n", 0o644, 0o644, "BOM changed"},
			{"a\nb\n", "a\nc", 0o644, 0o644, "final-newline state changed"},
			{"a\nb\n", "a\nc\n", 0o755, 0o644, "mode -rwxr-xr-x -> -rw-r--r--"},
			{"a\r\nb\r\n", "a\r\nc\n", 0o644, 0o644, "CRLF convention broken"},
			{"a\nb\nc\n", "x\ny\nc\n", 0o644, 0o644, "replace changed 2 lines"},
			{"a\nb\n", "a\nn\nx\n", 0o644, 0o644, "insert changed other lines"},
		} {
			if got := confFidelity([]byte(tc.old), []byte(tc.now), tc.oldM, tc.newM); !slices.Contains(got, tc.want) {
				t.Errorf("confFidelity(%q -> %q): %q, want %q", tc.old, tc.now, got, tc.want)
			}
		}
		if got := confFidelity([]byte("a\r\nb\r\n"), []byte("a\r\nn\r\nb\r\n"), 0o644, 0o644); len(got) != 0 {
			t.Errorf("a clean CRLF insert reported %q", got)
		}
	})
	// The probe builder is accepted on real annotation lines in every
	// language, file-level and member blocks alike: a refusal on a protected
	// line therefore comes from protection, never from a malformed probe.
	t.Run("probes are valid edits", func(t *testing.T) {
		members := 0
		for _, pid := range []string{"bash/ordinary.sh", "python/ordinary.py", "go/ordinary.go", "kotlin/ordinary.kt"} {
			c := load(t, pid)
			lang, _ := LangOf(c.Name, c.Data)
			f, err := ParseFile(c.Name, c.Data)
			if err != nil {
				t.Fatalf("%s: %v", pid, err)
			}
			probed := 0
			for _, n := range c.Exp.Writable {
				p := confBuildProbe(c, lang, f, n)
				if !p.Sensitive {
					continue // a unit or other key line: not a re-stamp target
				}
				probed++
				if p.Edit.Member != "" {
					members++
				}
				if got, _, _ := confRunProbe(t, c, p); got != "applied" {
					t.Errorf("%s: probe of writable line %d: %s, want applied", pid, n, got)
				}
			}
			if probed == 0 {
				t.Errorf("%s: no writable covers line to probe", pid)
			}
		}
		if members == 0 {
			t.Error("no probe of a member-block line")
		}
	})
	t.Run("a malformed probe is an error, not a refusal", func(t *testing.T) {
		c := load(t, id)
		lang, _ := LangOf(c.Name, c.Data)
		f, _ := ParseFile(c.Name, c.Data)
		p := confBuildProbe(c, lang, f, 4)
		p.Edit.Want = "not the line's text"
		got, after, mode := confRunProbe(t, c, p)
		has(t, confJudgeProbe(c, nil, p, got, after, mode), "probe-error: probe line 4: refused:conflict")
	})
}
