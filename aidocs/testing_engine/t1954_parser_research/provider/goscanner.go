package provider

import (
	"bytes"
	"go/scanner"
	"go/token"
)

func init() { register("goscanner", func() (Provider, error) { return GoScanner{}, nil }) }

// GoScanner is the standard library go/scanner as a provider (Go only).
type GoScanner struct{}

func (GoScanner) Name() string    { return "goscanner" }
func (GoScanner) Langs() []string { return []string{"go"} }
func (GoScanner) Caps(string) Capabilities {
	return Capabilities{TokenRanges: true, Errors: true, Anchors: APackage | AImportEnd}
}

// Analyze scans src with comments kept. Comment and raw-string literals have
// '\r' removed by go/scanner, so their ends are recomputed from src.
func (GoScanner) Analyze(_ string, src []byte) (Result, error) {
	var res Result
	fset := token.NewFileSet()
	file := fset.AddFile("", fset.Base(), len(src))
	var s scanner.Scanner
	s.Init(file, src, func(pos token.Position, msg string) {
		res.Diags = append(res.Diags, Diag{Start: pos.Offset, End: pos.Offset, Reason: msg})
	}, scanner.ScanComments)
	starts := LineStarts(src)
	line := func(off int) int { return LineOf(starts, off) }
	importDepth, inImport := 0, false
	for {
		pos, tok, lit := s.Scan()
		if tok == token.EOF {
			break
		}
		off := file.Offset(pos)
		switch tok {
		case token.COMMENT:
			if bytes.HasPrefix(src[off:], []byte("//")) {
				end := off
				for end < len(src) && src[end] != '\n' {
					end++
				}
				if end > off && src[end-1] == '\r' {
					end--
				}
				res.Spans = append(res.Spans, Span{off, end, LineComment})
			} else {
				end := len(src)
				if i := bytes.Index(src[off+2:], []byte("*/")); i >= 0 {
					end = off + 2 + i + 2
				}
				res.Spans = append(res.Spans, Span{off, end, BlockComment})
			}
		case token.STRING, token.CHAR:
			end := off + len(lit)
			if src[off] == '`' {
				end = len(src)
				if i := bytes.IndexByte(src[off+1:], '`'); i >= 0 {
					end = off + 1 + i + 1
				}
			}
			res.Spans = append(res.Spans, Span{off, end, String})
			if inImport && importDepth == 0 {
				res.Anchors.ImportEnd = line(off)
				inImport = false
			}
		case token.PACKAGE:
			if res.Anchors.Package == 0 {
				res.Anchors.Package = line(off)
			}
		case token.IMPORT:
			inImport, importDepth = true, 0
		case token.LPAREN:
			if inImport {
				importDepth++
			}
		case token.RPAREN:
			if inImport && importDepth > 0 {
				importDepth--
				if importDepth == 0 {
					res.Anchors.ImportEnd = line(off)
					inImport = false
				}
			}
		}
	}
	return res, nil
}
