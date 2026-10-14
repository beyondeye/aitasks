package main

// pindiff compares two matrix directories case by case (t1954_4 post-phase
// baseline_rerun_at_landed_commit). The baseline pin moved; every subject
// runs through the snapshot's grammar and rewriter, so a difference in any
// subject's row is attributed to the annot change between the two pins only
// when both directories were produced on the same corpus — the caller's job,
// stated in the report header.

import (
	"bufio"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

func init() { extraVerbs["pindiff"] = cmdPinDiff }

// matrixFile is one parsed matrix_<subject>.md.
type matrixFile struct {
	Identity string            // the "baseline: commit=…" line
	Rows     map[string]string // "lang/case" → the Per case table row
	Notes    map[string]string // "lang/case" → its Notes per case block (sub-bullets)
}

func parseMatrixFile(path string) (matrixFile, error) {
	f, err := os.Open(path)
	if err != nil {
		return matrixFile{}, err
	}
	defer f.Close()
	m := matrixFile{Rows: map[string]string{}, Notes: map[string]string{}}
	section, noteKey := "", ""
	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 1<<20), 1<<24)
	for sc.Scan() {
		line := sc.Text()
		switch {
		case strings.HasPrefix(line, "baseline: commit="):
			if m.Identity == "" {
				m.Identity = line
			}
			continue
		case strings.HasPrefix(line, "## "):
			section, noteKey = strings.TrimPrefix(line, "## "), ""
			continue
		}
		switch section {
		case "Per case":
			cells := strings.Split(line, "|")
			if len(cells) < 4 || !strings.HasPrefix(line, "| ") {
				continue
			}
			lang, cs := strings.TrimSpace(cells[1]), strings.TrimSpace(cells[2])
			if lang == "lang" || strings.HasPrefix(lang, "---") {
				continue
			}
			m.Rows[lang+"/"+cs] = line
		case "Notes per case":
			if strings.HasPrefix(line, "- `") {
				noteKey = strings.TrimSuffix(strings.TrimPrefix(line, "- `"), "`")
				m.Notes[noteKey] = ""
			} else if noteKey != "" && strings.HasPrefix(line, "  ") {
				m.Notes[noteKey] += line + "\n"
			}
		}
	}
	return m, sc.Err()
}

// safetyCells sums the four safety columns (FP-W, DS-W, SIL-U, REC-C) of a row.
func safetyCells(row string) [4]int {
	var s [4]int
	cells := strings.Split(row, "|")
	for i := 0; i < 4 && 4+i < len(cells); i++ {
		s[i], _ = strconv.Atoi(strings.TrimSpace(cells[4+i]))
	}
	return s
}

func cmdPinDiff(args []string) int {
	fs := flag.NewFlagSet("pindiff", flag.ExitOnError)
	oldDir := fs.String("old", "", "matrix directory at the old pin")
	newDir := fs.String("new", "", "matrix directory at the new pin")
	out := fs.String("out", filepath.Join("results", "t4", "pin_compare.md"), "output file")
	note := fs.String("note", "", "a sentence on how both directories were produced (corpus, binary)")
	_ = fs.Parse(args)
	if *oldDir == "" || *newDir == "" {
		fail(64, fmt.Errorf("pindiff: --old and --new are required"))
	}
	subjects := map[string]bool{}
	for _, d := range []string{*oldDir, *newDir} {
		ms, _ := filepath.Glob(filepath.Join(d, "matrix_*.md"))
		for _, m := range ms {
			subjects[strings.TrimSuffix(strings.TrimPrefix(filepath.Base(m), "matrix_"), ".md")] = true
		}
	}
	var order []string
	for s := range subjects {
		if s != "baseline" {
			order = append(order, s)
		}
	}
	sort.Strings(order)
	if subjects["baseline"] {
		order = append([]string{"baseline"}, order...)
	}
	var sum, detail strings.Builder
	var oldID, newID string
	totalDiff := 0
	sum.WriteString("| subject | cases (old / new) | rows differ | notes differ | only old | only new | safety FP-W/DS-W/SIL-U/REC-C old → new |\n|---|---|---|---|---|---|---|\n")
	for _, s := range order {
		om, oerr := parseMatrixFile(filepath.Join(*oldDir, "matrix_"+s+".md"))
		nm, nerr := parseMatrixFile(filepath.Join(*newDir, "matrix_"+s+".md"))
		if oerr != nil || nerr != nil {
			fmt.Fprintf(&sum, "| %s | missing in %s | | | | | |\n", s, map[bool]string{true: "old", false: "new"}[oerr != nil])
			continue
		}
		if oldID == "" {
			oldID, newID = om.Identity, nm.Identity
		}
		keys := map[string]bool{}
		for k := range om.Rows {
			keys[k] = true
		}
		for k := range nm.Rows {
			keys[k] = true
		}
		var ks []string
		for k := range keys {
			ks = append(ks, k)
		}
		sort.Strings(ks)
		var rowDiff, noteDiff, onlyOld, onlyNew int
		var os4, ns4 [4]int
		var blocks []string
		for _, k := range ks {
			or, oin := om.Rows[k]
			nr, nin := nm.Rows[k]
			if oin {
				a := safetyCells(or)
				for i := range os4 {
					os4[i] += a[i]
				}
			}
			if nin {
				a := safetyCells(nr)
				for i := range ns4 {
					ns4[i] += a[i]
				}
			}
			switch {
			case !oin:
				onlyNew++
				blocks = append(blocks, fmt.Sprintf("- `%s` — only at the new pin\n  - new: `%s`\n%s", k, strings.TrimSpace(nr), indentNotes("new", nm.Notes[k])))
				continue
			case !nin:
				onlyOld++
				blocks = append(blocks, fmt.Sprintf("- `%s` — only at the old pin\n  - old: `%s`\n%s", k, strings.TrimSpace(or), indentNotes("old", om.Notes[k])))
				continue
			}
			rd, nd := or != nr, om.Notes[k] != nm.Notes[k]
			if rd {
				rowDiff++
			}
			if nd {
				noteDiff++
			}
			if rd || nd {
				b := fmt.Sprintf("- `%s`\n  - old: `%s`\n  - new: `%s`\n", k, strings.TrimSpace(or), strings.TrimSpace(nr))
				if nd {
					b += indentNotes("old", om.Notes[k]) + indentNotes("new", nm.Notes[k])
				}
				blocks = append(blocks, b)
			}
		}
		totalDiff += len(blocks) // distinct differing cases: a changed row and note count once
		fmt.Fprintf(&sum, "| %s | %d / %d | %d | %d | %d | %d | %v → %v |\n", s, len(om.Rows), len(nm.Rows), rowDiff, noteDiff, onlyOld, onlyNew, os4, ns4)
		if len(blocks) > 0 {
			fmt.Fprintf(&detail, "### %s\n\n%s\n", s, strings.Join(blocks, ""))
		}
	}
	var b strings.Builder
	fmt.Fprintf(&b, "# Pin comparison (t1954_4 post-phase baseline_rerun_at_landed_commit)\n\n%s\n\n", id.Header())
	fmt.Fprintf(&b, "- old: `%s` — %s\n- new: `%s` — %s\n\n", *oldDir, oldID, *newDir, newID)
	if *note != "" {
		b.WriteString(*note + "\n\n")
	}
	b.WriteString("Every subject is scored through the snapshot's own grammar and rewriter (`ParseFile → PlanCovers → Apply`), so moving the pin can change any subject's row, not only the baseline's. Rows are keyed by `lang/case`; a case present at one pin only is listed as such. Generated by `t1954 pindiff`.\n\n## Summary\n\n")
	b.WriteString(sum.String())
	fmt.Fprintf(&b, "\nDiffering cases in total: %d.\n\n## Differing cases\n\n", totalDiff)
	if detail.Len() == 0 {
		b.WriteString("None.\n")
	} else {
		b.WriteString(detail.String())
	}
	if err := os.MkdirAll(filepath.Dir(*out), 0o755); err != nil {
		fail(1, err)
	}
	if err := os.WriteFile(*out, []byte(b.String()), 0o644); err != nil {
		fail(1, err)
	}
	fmt.Printf("WROTE:%s\nPINDIFF:%d differing cases\n", *out, totalDiff)
	return 0
}

func indentNotes(label, notes string) string {
	if notes == "" {
		return ""
	}
	var b strings.Builder
	fmt.Fprintf(&b, "  - %s notes:\n", label)
	for _, l := range strings.Split(strings.TrimRight(notes, "\n"), "\n") {
		b.WriteString("  " + l + "\n")
	}
	return b.String()
}
