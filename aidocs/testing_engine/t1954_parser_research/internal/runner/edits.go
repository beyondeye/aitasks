package runner

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/annot"
	"github.com/beyondeye/aitasks/goengines/t1954research/internal/corpus"
	"github.com/beyondeye/aitasks/goengines/t1954research/provider"
)

// OpKind is what an annotate op does, classified from the parsed file before
// planning — the requirement follows the real rewriter path: only a fresh
// file-level insertion reaches fixedPosition (and its anchors).
type OpKind string

const (
	OpRestamp      OpKind = "restamp"
	OpMemberInsert OpKind = "member-insert"
	OpFileAppend   OpKind = "file-append"
	OpFreshFile    OpKind = "fresh-file-insert"
	OpNoBlock      OpKind = "no-member-block"
)

// ClassifyOp names the rewriter path PlanCovers will take for member/source.
func ClassifyOp(f *annot.File, member, source string) OpKind {
	u, ok := f.Unit(member)
	if !ok {
		return OpNoBlock
	}
	for _, c := range u.Covers {
		if c.Source == source {
			return OpRestamp
		}
	}
	switch {
	case member != "":
		return OpMemberInsert
	case u.Last > 0:
		return OpFileAppend
	}
	return OpFreshFile
}

// NeedFor is what the op kind requires of a provider.
func NeedFor(k OpKind) provider.Need {
	if k == OpFreshFile {
		return provider.NeedWrite | provider.NeedFreshFileInsert
	}
	return provider.NeedWrite
}

func outcomeOf(changed bool, err error) string {
	var ce *annot.ConflictError
	var se *annot.SyntaxError
	switch {
	case err == nil && changed:
		return "applied"
	case err == nil:
		return "unchanged"
	case errors.Is(err, annot.ErrDocstring):
		return "refused:docstring"
	case errors.Is(err, annot.ErrNotComment):
		return "refused:not-comment"
	case errors.Is(err, annot.ErrUncertainContext):
		return "refused:uncertain"
	case errors.Is(err, annot.ErrNoMemberBlock):
		return "refused:no-member-block"
	case errors.As(err, &ce):
		return "refused:conflict"
	case errors.As(err, &se):
		if strings.HasPrefix(se.Reason, "cannot determine comment context") {
			return "refused:uncertain"
		}
		return "refused:syntax"
	}
	return "error:" + oneLine(err.Error())
}

func edits(row *Row, s Subject, c corpus.Case, lang string, opt Options) {
	root, err := os.MkdirTemp(opt.Scratch, "t1954-edit-")
	if err != nil {
		row.Status = "error:" + err.Error()
		return
	}
	defer os.RemoveAll(root)
	rel := "tests/" + c.Name
	abs := filepath.Join(root, rel)
	reset := func() error {
		if err := os.MkdirAll(filepath.Dir(abs), 0o755); err != nil {
			return err
		}
		if err := os.WriteFile(abs, c.Data, 0o600); err != nil {
			return err
		}
		return os.Chmod(abs, c.Mode)
	}
	if err := reset(); err != nil {
		row.Status = "error:" + err.Error()
		return
	}
	var before *execResult
	if opt.Behaviour && c.Exp.Exec != "" {
		before = runExec(c.Exp.Exec, abs)
	}
	blocked := "" // set when an op that later ops build on could not run
	for i, op := range c.Edits {
		row.Ops++
		tag := fmt.Sprintf("op %d (%s)", i+1, op.Text)
		if op.Args["from"] == "original" {
			if err := reset(); err != nil {
				row.Status = "error:" + err.Error()
				return
			}
			blocked = ""
		}
		if blocked != "" {
			row.OpsNotMeasured++
			row.note("%s: not measured — follows %s", tag, blocked)
			continue
		}
		// The mode BEFORE the op: fidelity compares it with the mode after.
		st, serr := os.Stat(abs)
		if serr != nil {
			row.Status = "error:" + serr.Error()
			return
		}
		got, kind, cur, err := runOp(s, lang, rel, root, abs, op)
		if err != nil {
			var u *provider.UnsupportedCapabilityError
			var pe *ProviderError
			switch {
			case errors.As(err, &u):
				row.OpsUnsupported++
				row.note("%s [%s]: %s", tag, kind, u.Error())
				blocked = fmt.Sprintf("unsupported op %d", i+1)
				continue
			case errors.As(err, &pe):
				row.OpsNotMeasured++
				row.note("%s [%s]: not measured — %s", tag, kind, pe.Error())
				blocked = fmt.Sprintf("op %d (provider error)", i+1)
				continue
			}
			row.Status = "error:" + oneLine(err.Error())
			return
		}
		if kind != "" {
			tag += " [" + string(kind) + "]"
		}
		switch {
		case strings.HasPrefix(got, "applied"):
			row.OpsApplied++
		case strings.HasPrefix(got, "refused"):
			row.OpsRefused++
		}
		if got != op.Outcome {
			row.note("%s: outcome %q, want %q", tag, got, op.Outcome)
			now, _ := os.ReadFile(abs)
			switch {
			case op.Outcome == "refused:docstring" && got == "applied" && inDocstring(c.Exp.Readonly, firstChanged(cur, now)):
				row.DocstringWrite++
			case op.Outcome == "refused:not-comment" && got == "applied":
				row.FPWritable++
			case op.Outcome == "refused:uncertain" && got == "applied":
				row.SilentUncertain++
			case strings.HasPrefix(op.Outcome, "refused") && got == "applied":
				row.RecordCorruption++
			case op.Outcome == "applied" && strings.HasPrefix(got, "refused"):
				row.OverRefusal++
			default:
				row.RecordCorruption++
			}
		}
		// The complete record list after the op, parsed by the same subject.
		// If the subject fails on the re-read, the records are NOT verified
		// (never compared as an empty list); the write itself stands and
		// the independent fidelity/behaviour checks below still run.
		now, _ := os.ReadFile(abs)
		f, rfails, perr := s.parse(c.Name, now, provider.NeedRecords)
		var recs []corpus.Record
		if perr == nil {
			recs = corpus.Records(f)
		}
		if ferr := failErr(rfails); ferr != nil {
			row.RecordsNotVerified++
			row.note("%s: records after not verified — %s", tag, ferr.Error())
		} else if d := diffRecords(op.After, recs); d != "" {
			// A wrong record list counts as corruption only when the file
			// changed; a refused (or unsupported) op leaves it untouched and
			// is scored by its outcome above.
			if !bytes.Equal(cur, now) {
				row.RecordCorruption++
			}
			row.note("%s: records after differ: %s", tag, d)
		}
		if got == "applied" {
			nst, _ := os.Stat(abs)
			for _, v := range fidelity(cur, now, st.Mode(), nst.Mode()) {
				row.Fidelity++
				row.note("%s: fidelity: %s", tag, v)
			}
			if c.Exp.Exec != "" && !opt.Behaviour {
				row.BehaviourNotMeasured++
				row.note("%s: behaviour not measured — disabled (--behaviour=false)", tag)
			}
			if before != nil {
				after := runExec(c.Exp.Exec, abs)
				d, nm := before.diff(after)
				switch {
				case nm != "":
					row.BehaviourNotMeasured++
					row.note("%s: behaviour not measured — %s", tag, nm)
				case d != "":
					row.Behaviour++
					row.note("%s: behaviour changed: %s", tag, d)
				}
			}
		} else if !bytes.Equal(cur, now) {
			row.RecordCorruption++
			row.note("%s: file changed although the op was %s", tag, got)
		}
	}
}

// runOp performs one op on the scratch file and returns its outcome and the
// bytes Apply saw (after a stale op's mutation).
func runOp(s Subject, lang, rel, root, abs string, op corpus.Op) (string, OpKind, []byte, error) {
	data, err := os.ReadFile(abs)
	if err != nil {
		return "", "", nil, err
	}
	seen := data
	out, kind, err := runOpOn(s, lang, rel, root, abs, data, op, &seen)
	return out, kind, seen, err
}

// runOpOn does the op; for a stale op *seen becomes the mutated bytes.
func runOpOn(s Subject, lang, rel, root, abs string, data []byte, op corpus.Op, seen *[]byte) (string, OpKind, error) {
	name := filepath.Base(rel)
	switch op.Kind {
	case "raw":
		return rawOp(s, lang, rel, root, abs, data, op)
	case "annotate", "stale":
	default:
		return "", "", fmt.Errorf("unknown op %q", op.Kind)
	}
	stamp, err := annot.ParseStamp(op.Args["stamp"])
	if err != nil {
		return "", "", fmt.Errorf("op stamp: %w", err)
	}
	member, source := op.Args["member"], op.Args["source"]
	// Parse at NeedWrite: certainty is required for every write.
	if !s.IsBaseline() {
		if err := provider.Check(lang, s.Caps(lang), provider.NeedWrite); err != nil {
			return "", "", err
		}
	}
	f, fails, perr := s.parse(name, data, provider.NeedWrite)
	if err := failErr(fails); err != nil {
		return "", "", err
	}
	if perr != nil {
		return outcomeOf(false, perr), "", nil
	}
	kind := ClassifyOp(f, member, source)
	need := NeedFor(kind)
	if !s.IsBaseline() {
		if err := provider.Check(lang, s.Caps(lang), need); err != nil {
			return "", kind, err
		}
	} else if kind == OpFreshFile && provider.IsResearch(lang) {
		return "", kind, &provider.UnsupportedCapabilityError{Missing: []string{"placement-rule(baseline)"}}
	}
	var e annot.Edit
	if kind == OpFreshFile && provider.IsResearch(lang) {
		anchors, err := s.anchors(lang, data)
		if err != nil {
			return "", kind, err
		}
		after, _ := provider.ProposedFilePlacement(f, lang, provider.Mask(anchors, s.Caps(lang).Anchors))
		want := ""
		if after > 0 {
			want = strings.TrimSuffix(f.Lines[after-1], "\r")
		}
		e = annot.Edit{Kind: annot.InsertAfter, Line: after, Want: want,
			New:    f.Lang.Leader + " " + annot.Token + "covers " + source + " " + stamp.String(),
			Member: member, Source: source}
	} else {
		var perr2 error
		err := s.withSubject(need, &fails, func() error {
			e, perr2 = annot.PlanCovers(f, member, source, stamp)
			return nil
		})
		if err != nil {
			return "", kind, err
		}
		if err := failErr(fails); err != nil {
			return "", kind, err
		}
		if perr2 != nil {
			return outcomeOf(false, perr2), kind, nil
		}
	}
	set := annot.EditSet{Path: rel, Snapshot: f.Snapshot(), Edits: []annot.Edit{e}}
	if op.Kind == "stale" {
		if err := mutate(abs, data, op.Args["mutate"]); err != nil {
			return "", kind, err
		}
		if b, err := os.ReadFile(abs); err == nil {
			*seen = b
		}
	}
	var changed bool
	var aerr error
	err = s.withSubject(need, &fails, func() error {
		changed, aerr = annot.Apply(root, set)
		return nil
	})
	if err != nil {
		return "", kind, err
	}
	if afterApply != nil && aerr == nil {
		afterApply(abs)
	}
	if err := failErr(fails); err != nil {
		return "", kind, err
	}
	return outcomeOf(changed, aerr), kind, nil
}

// afterApply is a test seam: it runs after every Apply that returned no
// error (a test uses it to simulate a write that loses the file's mode).
var afterApply func(abs string)

// ProviderError is a provider failure during an edit: the op is not
// measured, never scored as a refusal.
type ProviderError struct{ Msg string }

func (e *ProviderError) Error() string { return "provider error: " + e.Msg }

// failErr turns the failures the seam hooks recorded during an op into the
// op's accounting: a missing capability is unsupported, anything else a
// provider error. Without this, Apply would see the fail-closed Uncertain
// context and the op would be mis-scored as refused:uncertain.
func failErr(fails []string) error {
	for _, f := range fails {
		if m, ok := strings.CutPrefix(f, "unsupported:"); ok {
			return &provider.UnsupportedCapabilityError{Missing: strings.Split(m, ",")}
		}
	}
	if len(fails) > 0 {
		return &ProviderError{Msg: fails[0]}
	}
	return nil
}

// rawOp hands Apply a direct edit (to probe its refusals on look-alikes,
// docstrings and code lines).
func rawOp(s Subject, lang, rel, root, abs string, data []byte, op corpus.Op) (string, OpKind, error) {
	// A raw write needs what every write needs (Errors; DocLiterals for Python).
	if !s.IsBaseline() {
		if err := provider.Check(lang, s.Caps(lang), provider.NeedWrite); err != nil {
			return "", "raw", err
		}
	}
	n, err := strconv.Atoi(op.Args["line"])
	if err != nil {
		return "", "", fmt.Errorf("raw op line: %w", err)
	}
	lines := strings.Split(strings.TrimSuffix(string(data), "\n"), "\n")
	want := ""
	if n > 0 && n <= len(lines) {
		want = strings.TrimSuffix(lines[n-1], "\r")
	}
	e := annot.Edit{Line: n, Want: want, New: op.Args["new"], Member: op.Args["member"], Source: op.Args["source"]}
	switch op.Args["kind"] {
	case "replace":
		e.Kind = annot.Replace
	case "insert-after":
		e.Kind = annot.InsertAfter
	default:
		return "", "", fmt.Errorf("raw op kind %q", op.Args["kind"])
	}
	var fails []string
	var changed bool
	var aerr error
	err = s.withSubject(provider.NeedWrite, &fails, func() error {
		changed, aerr = annot.Apply(root, annot.EditSet{Path: rel, Edits: []annot.Edit{e}})
		return nil
	})
	if err != nil {
		return "", "raw", err
	}
	if afterApply != nil && aerr == nil {
		afterApply(abs)
	}
	if err := failErr(fails); err != nil {
		return "", "raw", err
	}
	return outcomeOf(changed, aerr), "raw", nil
}

// mutate changes the scratch file between planning and Apply (stale plan).
func mutate(abs string, data []byte, spec string) error {
	how, arg, _ := strings.Cut(spec, ":")
	eol := "\n"
	if bytes.Contains(data, []byte("\r\n")) {
		eol = "\r\n"
	}
	switch how {
	case "append":
		out := append([]byte(nil), data...)
		if len(out) > 0 && !bytes.HasSuffix(out, []byte("\n")) {
			out = append(out, eol...)
		}
		out = append(out, (arg + eol)...)
		return os.WriteFile(abs, out, 0o600)
	case "replace":
		ns, text, _ := strings.Cut(arg, ":")
		n, err := strconv.Atoi(ns)
		if err != nil {
			return err
		}
		lines := strings.SplitAfter(string(data), "\n")
		if n < 1 || n > len(lines) {
			return fmt.Errorf("mutate replace: line %d out of range", n)
		}
		end := ""
		if strings.HasSuffix(lines[n-1], "\n") {
			end = eol
		}
		lines[n-1] = text + end
		return os.WriteFile(abs, []byte(strings.Join(lines, "")), 0o600)
	}
	return fmt.Errorf("mutate %q: want append:<text> or replace:<n>:<text>", spec)
}

// firstChanged is the 1-based first line where a and b differ.
func firstChanged(a, b []byte) int {
	al := strings.Split(string(a), "\n")
	bl := strings.Split(string(b), "\n")
	for i := 0; i < len(al) && i < len(bl); i++ {
		if al[i] != bl[i] {
			return i + 1
		}
	}
	return min(len(al), len(bl)) + 1
}

// inDocstring reports whether line n lies within the span of the expected
// read-only (docstring) lines.
func inDocstring(readonly []int, n int) bool {
	if len(readonly) == 0 {
		return false
	}
	lo, hi := readonly[0], readonly[0]
	for _, r := range readonly {
		lo, hi = min(lo, r), max(hi, r)
	}
	return n >= lo && n <= hi
}

func diffRecords(want, got []corpus.Record) string {
	w := make([]string, len(want))
	for i, r := range want {
		w[i] = r.String()
	}
	g := make([]string, len(got))
	for i, r := range got {
		g[i] = r.String()
	}
	if strings.Join(w, "\n") == strings.Join(g, "\n") {
		return ""
	}
	var parts []string
	gm := map[string]int{}
	for _, x := range g {
		gm[x]++
	}
	wm := map[string]int{}
	for _, x := range w {
		wm[x]++
	}
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

var bom = []byte{0xEF, 0xBB, 0xBF}

// fidelity checks an applied single-line edit independently of Apply's own
// checks: one line inserted or replaced, every other line byte-identical,
// BOM, CRLF convention, final-newline state and mode preserved.
func fidelity(old, now []byte, oldMode, newMode os.FileMode) []string {
	var v []string
	if bytes.HasPrefix(old, bom) != bytes.HasPrefix(now, bom) {
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
	allCR := func(ls []string, last bool) bool {
		for i, l := range ls {
			if i == len(ls)-1 && !last {
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

type execResult struct {
	out  string
	code int
	note string
}

// diff compares two runs. notMeasured is set when either run could not
// happen (a missing tool, a launch failure): that is never "unchanged".
func (a *execResult) diff(b *execResult) (diff, notMeasured string) {
	switch {
	case a.note != "":
		return "", "before the edit: " + a.note
	case b.note != "":
		return "", "after the edit: " + b.note
	case a.code != b.code:
		return fmt.Sprintf("exit %d -> %d", a.code, b.code), ""
	case a.out != b.out:
		return fmt.Sprintf("output %q -> %q", trunc(a.out), trunc(b.out)), ""
	}
	return "", ""
}

func trunc(s string) string {
	if len(s) > 120 {
		return s[:120] + "…"
	}
	return s
}

// runExec runs a controlled fixture's exec: command in its scratch dir.
// {file} is the fixture's path; nothing outside the scratch copy is run.
func runExec(cmdline, abs string) *execResult {
	dir := filepath.Dir(abs)
	cmdline = strings.ReplaceAll(cmdline, "{file}", filepath.Base(abs))
	first := strings.Fields(cmdline)[0]
	if _, err := exec.LookPath(first); err != nil {
		return &execResult{note: "tool missing: " + first}
	}
	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, "bash", "-c", cmdline)
	cmd.Dir = dir
	cmd.Env = append(os.Environ(), "GOFLAGS=-mod=mod", "GO111MODULE=auto")
	out, err := cmd.CombinedOutput()
	code := 0
	var ee *exec.ExitError
	if errors.As(err, &ee) {
		code = ee.ExitCode()
	} else if err != nil {
		return &execResult{note: err.Error()}
	}
	return &execResult{out: string(out), code: code}
}
