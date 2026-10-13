// Package report renders runner rows as the committed markdown matrices:
// safety columns first, then recall/cost, fidelity, behaviour, range and
// edit accounting; every unsupported or not-measured cell is shown, never
// omitted. Output is deterministic (no times, no temp paths) so the guard
// can compare two builds byte for byte.
package report

import (
	"fmt"
	"sort"
	"strings"

	"github.com/beyondeye/aitasks/goengines/t1954research/internal/runner"
)

// Agg sums rows of one language.
type Agg struct {
	Lang                                         string
	Cases, Supported, Errors                     int
	FP, DW, SU, RC, SUNA                         int
	MW, MC, RM, OR, PL, FI, BE, BENM             int
	RangePass, RangeFail, RangeNA                int
	Ops, Applied, Refused, Unsupported, NotMeasd int
	RecNV                                        int
}

// Aggregate groups rows by language, in the order langs gives.
func Aggregate(rows []runner.Row, langs []string) []Agg {
	by := map[string]*Agg{}
	for _, l := range langs {
		by[l] = &Agg{Lang: l}
	}
	for _, r := range rows {
		a, ok := by[r.Lang]
		if !ok {
			a = &Agg{Lang: r.Lang}
			by[r.Lang] = a
			langs = append(langs, r.Lang)
		}
		a.Cases++
		switch {
		case r.Status == "ok":
			a.Supported++
		case strings.HasPrefix(r.Status, "error"):
			a.Errors++
		}
		a.FP += r.FPWritable
		a.DW += r.DocstringWrite
		a.SU += r.SilentUncertain
		if r.SilentUncertainNA {
			a.SUNA++
		}
		a.RC += r.RecordCorruption
		a.MW += r.MissedWritable
		a.MC += r.MissedComment
		a.RM += r.ReadMismatch
		a.OR += r.OverRefusal
		a.PL += r.PlacementMiss
		a.FI += r.Fidelity
		a.BE += r.Behaviour
		a.BENM += r.BehaviourNotMeasured
		switch {
		case r.Status != "ok":
		case strings.HasPrefix(r.Range, "pass"):
			a.RangePass++
		case strings.HasPrefix(r.Range, "fail"):
			a.RangeFail++
		default:
			a.RangeNA++
		}
		a.Ops += r.Ops
		a.Applied += r.OpsApplied
		a.Refused += r.OpsRefused
		a.Unsupported += r.OpsUnsupported
		a.NotMeasd += r.OpsNotMeasured
		a.RecNV += r.RecordsNotVerified
	}
	out := make([]Agg, 0, len(langs))
	for _, l := range langs {
		if a := by[l]; a != nil && a.Cases > 0 {
			out = append(out, *a)
		}
	}
	return out
}

func su(a Agg) string {
	if a.SUNA > 0 {
		return fmt.Sprintf("%d (+%d n/a: no error reporting)", a.SU, a.SUNA)
	}
	return fmt.Sprint(a.SU)
}

func beh(n, notMeasured int) string {
	if notMeasured > 0 {
		return fmt.Sprintf("%d (+%d not measured)", n, notMeasured)
	}
	return fmt.Sprint(n)
}

func rng(a Agg) string {
	if a.RangePass+a.RangeFail == 0 {
		return "n/a — not exposed"
	}
	return fmt.Sprintf("%d pass / %d fail", a.RangePass, a.RangeFail)
}

// SummaryHeader / SummaryRow are the per-language summary table.
const SummaryHeader = "| lang | cases | supported | FP-writable | Docstring-write | Silent-uncertain | Record-corruption | Missed-writable | Missed-comment | Read-mismatch | Over-refusal | Placement | Fidelity | Behaviour | Range | edit ops: applied / refused / unsupported / not measured |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"

func SummaryRow(a Agg) string {
	sup := fmt.Sprint(a.Supported)
	if a.Supported == 0 {
		sup = "0 (unsupported)"
	}
	if a.Errors > 0 {
		sup += fmt.Sprintf(" (%d error)", a.Errors)
	}
	return fmt.Sprintf("| %s | %d | %s | %d | %d | %s | %d | %d | %d | %d | %d | %d | %d | %s | %s | %s |\n",
		a.Lang, a.Cases, sup, a.FP, a.DW, su(a), a.RC, a.MW, a.MC, a.RM, a.OR, a.PL, a.FI, beh(a.BE, a.BENM), rng(a),
		ops(a.Applied, a.Refused, a.Unsupported, a.NotMeasd, a.RecNV, " / "))
}

// ops is the edit-accounting cell; ops whose post-op records could not be
// read back are flagged, never folded into a verified count.
func ops(applied, refused, unsupported, notMeasured, recNV int, sep string) string {
	c := fmt.Sprintf("%d%s%d%s%d%s%d", applied, sep, refused, sep, unsupported, sep, notMeasured)
	if recNV > 0 {
		c += fmt.Sprintf(" (records not verified after %d)", recNV)
	}
	return c
}

// Matrix renders one subject's full matrix.
func Matrix(subject, header string, rows []runner.Row, langs []string) string {
	var b strings.Builder
	fmt.Fprintf(&b, "# Matrix: %s\n\n", subject)
	fmt.Fprintf(&b, "%s\n\n", header)
	b.WriteString("Safety columns (must be 0): FP-writable, Docstring-write, Silent-uncertain, Record-corruption. ")
	b.WriteString("Recall/cost: Missed-writable, Missed-comment (a plain comment line not classed Comment), Read-mismatch, Over-refusal, Placement. Fidelity and Behaviour count applied edits that changed other bytes / program behaviour. ")
	b.WriteString("Definitions: the t1954 shared design, *Metrics*.\n\n## Summary by language\n\n")
	b.WriteString(SummaryHeader)
	for _, a := range Aggregate(rows, langs) {
		b.WriteString(SummaryRow(a))
	}
	b.WriteString("\n## Per case\n\n| lang | case | status | FP-W | DS-W | SIL-U | REC-C | MISS-W | MISS-C | READ-M | OVER-R | PLACE | FID | BEH | range | ops a/r/u/nm |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")
	sorted := append([]runner.Row(nil), rows...)
	sort.SliceStable(sorted, func(i, j int) bool {
		if sorted[i].Lang != sorted[j].Lang {
			return sorted[i].Lang < sorted[j].Lang
		}
		return sorted[i].Case < sorted[j].Case
	})
	for _, r := range sorted {
		sil := fmt.Sprint(r.SilentUncertain)
		if r.SilentUncertainNA {
			sil = "n/a"
		}
		fmt.Fprintf(&b, "| %s | %s | %s | %d | %d | %s | %d | %d | %d | %d | %d | %d | %d | %s | %s | %s |\n",
			r.Lang, r.Case, esc(r.Status), r.FPWritable, r.DocstringWrite, sil, r.RecordCorruption,
			r.MissedWritable, r.MissedComment, r.ReadMismatch, r.OverRefusal, r.PlacementMiss, r.Fidelity, beh(r.Behaviour, r.BehaviourNotMeasured),
			esc(r.Range), ops(r.OpsApplied, r.OpsRefused, r.OpsUnsupported, r.OpsNotMeasured, r.RecordsNotVerified, "/"))
	}
	b.WriteString("\n## Notes per case\n\n")
	for _, r := range sorted {
		if len(r.Notes) == 0 {
			continue
		}
		fmt.Fprintf(&b, "- `%s/%s`\n", r.Lang, r.Case)
		for _, n := range r.Notes {
			fmt.Fprintf(&b, "  - %s\n", esc(n))
		}
	}
	return b.String()
}

func esc(s string) string { return strings.ReplaceAll(s, "|", "\\|") }

// Combined renders the provider × language safety overview.
func Combined(header string, bySubject map[string][]runner.Row, order []string, langs []string) string {
	var b strings.Builder
	b.WriteString("# Matrix: all subjects\n\n")
	fmt.Fprintf(&b, "%s\n\n", header)
	b.WriteString("Per-subject detail: `matrix_<subject>.md`. Columns as there; safety columns first.\n\n")
	head, sep, _ := strings.Cut(strings.TrimSuffix(SummaryHeader, "\n"), "\n")
	b.WriteString("| subject " + head + "\n|---" + sep + "\n")
	for _, s := range order {
		for _, a := range Aggregate(bySubject[s], langs) {
			b.WriteString("| " + s + " " + SummaryRow(a))
		}
	}
	return b.String()
}
