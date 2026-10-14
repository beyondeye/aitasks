package deps

import (
	"errors"
	"unicode"
	"unicode/utf8"
)

// ktok is one Kotlin token: 'n' identifier (backticked names unquoted),
// 'o' operator ("." "::" "@" "(" "{" …), 's' a string literal without
// templates (its content), 'S' any other string (content unknown), 'd'
// number.
type ktok struct {
	kind byte
	text string
	line int
}

var errUntokenizable = errors.New("untokenizable")

// ktLex tokenizes Kotlin. Comments (nested block comments included) and
// string contents are skipped; the code inside string templates (`${…}`,
// `$ident`) is kept as tokens. A construct that never closes, or a Kotlin
// multi-dollar string, is an error: the file is opaque.
func ktLex(src string) ([]ktok, error) {
	l := &ktLexer{src: src, line: 1}
	if err := l.code(false); err != nil {
		return l.toks, err
	}
	return l.toks, nil
}

type ktLexer struct {
	src  string
	i    int
	line int
	toks []ktok
}

func (l *ktLexer) emit(kind byte, text string, line int) {
	l.toks = append(l.toks, ktok{kind, text, line})
}

// code lexes code until EOF, or — inTemplate — until the '}' closing a
// `${` template.
func (l *ktLexer) code(inTemplate bool) error {
	depth := 0
	for l.i < len(l.src) {
		c := l.src[l.i]
		switch {
		case c == '\n':
			l.line++
			l.i++
		case c == ' ' || c == '\t' || c == '\r' || c == '\f':
			l.i++
		case c == '/' && l.peek(1) == '/':
			for l.i < len(l.src) && l.src[l.i] != '\n' {
				l.i++
			}
		case c == '/' && l.peek(1) == '*':
			if err := l.blockComment(); err != nil {
				return err
			}
		case c == '"':
			if err := l.str(); err != nil {
				return err
			}
		case c == '\'':
			if err := l.char(); err != nil {
				return err
			}
		case c == '`':
			j := l.i + 1
			for j < len(l.src) && l.src[j] != '`' && l.src[j] != '\n' {
				j++
			}
			if j >= len(l.src) || l.src[j] != '`' {
				return errUntokenizable
			}
			l.emit('n', l.src[l.i+1:j], l.line)
			l.i = j + 1
		case c == '{':
			depth++
			l.emit('o', "{", l.line)
			l.i++
		case c == '}':
			if inTemplate && depth == 0 {
				l.i++
				return nil
			}
			depth--
			l.emit('o', "}", l.line)
			l.i++
		case c == ':' && l.peek(1) == ':':
			l.emit('o', "::", l.line)
			l.i += 2
		case c >= '0' && c <= '9':
			j := l.i
			for j < len(l.src) && (isIdentChar(l.src[j]) || l.src[j] == '.' && j+1 < len(l.src) && l.src[j+1] >= '0' && l.src[j+1] <= '9') {
				j++
			}
			l.emit('d', l.src[l.i:j], l.line)
			l.i = j
		case isIdentStart(c) || c >= utf8.RuneSelf:
			j := l.ident(l.i)
			if j == l.i {
				l.i++ // an unrelated non-ASCII symbol
				continue
			}
			l.emit('n', l.src[l.i:j], l.line)
			l.i = j
		case c == '$':
			// $$"…" is a multi-dollar string (Kotlin 2.2): a single ${ inside
			// it is literal text. Its interpolation threshold is not
			// modelled, and lexing it as a plain string would read that ${ as
			// template code.
			j := l.i
			for j < len(l.src) && l.src[j] == '$' {
				j++
			}
			if j < len(l.src) && l.src[j] == '"' {
				return errUntokenizable
			}
			for ; l.i < j; l.i++ {
				l.emit('o', "$", l.line)
			}
		default:
			l.emit('o', string(c), l.line)
			l.i++
		}
	}
	if inTemplate {
		return errUntokenizable
	}
	return nil
}

func (l *ktLexer) peek(n int) byte {
	if l.i+n < len(l.src) {
		return l.src[l.i+n]
	}
	return 0
}

// ident returns the end of the identifier starting at i.
func (l *ktLexer) ident(i int) int {
	j := i
	for j < len(l.src) {
		r, size := utf8.DecodeRuneInString(l.src[j:])
		if r == '_' || unicode.IsLetter(r) || (j > i && unicode.IsDigit(r)) {
			j += size
			continue
		}
		break
	}
	return j
}

func (l *ktLexer) blockComment() error {
	depth := 0
	for l.i < len(l.src) {
		switch {
		case l.src[l.i] == '/' && l.peek(1) == '*':
			depth++
			l.i += 2
		case l.src[l.i] == '*' && l.peek(1) == '/':
			depth--
			l.i += 2
			if depth == 0 {
				return nil
			}
		case l.src[l.i] == '\n':
			l.line++
			l.i++
		default:
			l.i++
		}
	}
	return errUntokenizable
}

func (l *ktLexer) char() error {
	j := l.i + 1
	for j < len(l.src) && j < l.i+12 {
		switch l.src[j] {
		case '\\':
			j += 2
			continue
		case '\'':
			l.emit('S', "", l.line)
			l.i = j + 1
			return nil
		case '\n':
			return errUntokenizable
		}
		j++
	}
	return errUntokenizable
}

// str lexes a string literal (plain or raw) with its templates.
func (l *ktLexer) str() error {
	line := l.line
	raw := len(l.src) >= l.i+3 && l.src[l.i:l.i+3] == `"""`
	if raw {
		l.i += 3
	} else {
		l.i++
	}
	start := l.i
	plain := true
	for l.i < len(l.src) {
		c := l.src[l.i]
		switch {
		case !raw && c == '\\':
			plain = false
			l.i += 2
		case !raw && c == '\n':
			return errUntokenizable
		case c == '\n':
			l.line++
			l.i++
		case c == '$' && l.peek(1) == '{':
			plain = false
			l.i += 2
			if err := l.code(true); err != nil {
				return err
			}
		case c == '$' && (isIdentStart(l.peek(1)) || l.peek(1) >= utf8.RuneSelf):
			plain = false
			j := l.ident(l.i + 1)
			l.emit('n', l.src[l.i+1:j], l.line)
			l.i = j
		case c == '"':
			if !raw {
				l.emitStr(plain, l.src[start:l.i], line)
				l.i++
				return nil
			}
			if len(l.src) >= l.i+3 && l.src[l.i:l.i+3] == `"""` {
				// A run of more than three quotes: the last three close.
				j := l.i
				for j < len(l.src) && l.src[j] == '"' {
					j++
				}
				l.emitStr(plain, l.src[start:j-3], line)
				l.i = j
				return nil
			}
			l.i++
		default:
			l.i++
		}
	}
	return errUntokenizable
}

func (l *ktLexer) emitStr(plain bool, content string, line int) {
	if plain {
		l.emit('s', content, line)
	} else {
		l.emit('S', "", line)
	}
}
