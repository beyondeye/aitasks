"""core.py - fixture model and writer for the t1954 research corpus.

A fixture is source text whose lines may end with ONE hand-oracle marker:

    W  a writable annotation: a real comment `testmap:` line (its record is
       derived from the line text: key, args, stamp; member = the last
       preceding W `unit` line)
    L  a look-alike: testmap-shaped data, never read, never writable
    R  a read-only docstring line (its record is given explicitly in docrecs,
       with the DECODED value)
    C  a plain comment line (lexically a comment, not an annotation)

written as the characters U+27E6 X U+27E7 at the very end of the line. The
markers are the hand oracle; the generator only strips them and formats the
.expect/.edits files (format: the t1954 shared design, "Oracle files").

Edits are an ordered list of ops. Each op names its expected outcome and,
for an applied op, the expected change as ("ins", after_line, text) or
("rep", line, text) - text carries its own marker. The generator checks
that every applied change touches exactly one line.
"""

import os
import re
import stat

MARK = re.compile("⟦([WLRC])⟧$")
ANNOT = re.compile(r"^[ \t]*(#|//)[ \t]*testmap:([a-z]+)(.*)$")

ANNOT_LANG = {
    ".sh": "bash", ".bash": "bash", ".py": "python", ".go": "go", ".kt": "kotlin", ".kts": "kotlin",
    ".ts": "typescript", ".tsx": "typescript", ".mts": "typescript",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript",
    ".java": "java", ".rs": "rust", ".swift": "swift",
}


def ext_of(name):
    return os.path.splitext(name)[1]


class Rec:
    def __init__(self, line, member, key, value, stamp="", origin="comment"):
        self.line, self.member, self.key, self.value, self.stamp, self.origin = line, member, key, value, stamp, origin

    def __str__(self):
        v = self.value
        plain = v == v.strip() and " stamp=" not in v and not v.startswith('"') and all(0x20 <= ord(c) <= 0x7E for c in v)
        if not plain:
            v = go_quote(v)
        return "line=%d member=%s key=%s value=%s stamp=%s origin=%s" % (self.line, self.member, self.key, v, self.stamp, self.origin)


def go_quote(s):
    """strconv.Quote-compatible quoting for the characters fixtures use."""
    out = ['"']
    for c in s:
        o = ord(c)
        if c == '"':
            out.append('\\"')
        elif c == "\\":
            out.append("\\\\")
        elif c == "\n":
            out.append("\\n")
        elif c == "\t":
            out.append("\\t")
        elif c == "\r":
            out.append("\\r")
        elif o < 0x20 or o == 0x7F:
            out.append("\\x%02x" % o)
        elif o == 0xFFFD or o == 0xA0 or 0x80 <= o < 0xA0 or o in (0x2028, 0x2029, 0xFEFF):
            out.append("\\u%04x" % o)
        else:
            out.append(c)
    out.append('"')
    return "".join(out)


def split_marked(text):
    """-> (clean lines, {line_no: mark})"""
    lines, marks = [], {}
    for i, l in enumerate(text.split("\n")):
        m = MARK.search(l)
        if m:
            marks[i + 1] = m.group(1)
            l = l[: m.start()]
        lines.append(l)
    return lines, marks


def records_of(lines, marks, docrecs=()):
    recs, member = [], ""
    for n in sorted(marks):
        if marks[n] != "W":
            continue
        text = lines[n - 1].rstrip("\r")
        if n == 1:
            text = text.lstrip("\ufeff")  # a leading BOM is not part of line 1 (the marks decide whether it counts)
        m = ANNOT.match(text)
        if not m:
            raise ValueError("line %d marked W but not an annotation: %r" % (n, lines[n - 1]))
        key, args = m.group(2), m.group(3).split()
        if key == "unit":
            member = args[0]
            recs.append(Rec(n, member, "unit", member))
        elif key == "covers":
            recs.append(Rec(n, member, "covers", args[0], args[1] if len(args) > 1 else ""))
        else:
            recs.append(Rec(n, member, key, " ".join(args)))
    recs.extend(docrecs)
    recs.sort(key=lambda r: (r.line, r.key))
    return recs


def resolve(lines, n):
    """A line given as an int, or as a substring naming exactly one line."""
    if isinstance(n, int):
        return n
    hits = [i + 1 for i, l in enumerate(lines) if n in l]
    if len(hits) != 1:
        raise ValueError("anchor %r matches lines %s" % (n, hits))
    return hits[0]


def fmt_lines(ns):
    ns = sorted(set(ns))
    if not ns:
        return ""
    out, i = [], 0
    while i < len(ns):
        j = i
        while j + 1 < len(ns) and ns[j + 1] == ns[j] + 1:
            j += 1
        out.append(str(ns[i]) if i == j else "%d-%d" % (ns[i], ns[j]))
        i = j + 1
    return ",".join(out)


class Fx:
    """One corpus fixture."""

    def __init__(self, name, src, uncertain=False, refuse=None, docrecs=(), placement=None, native=(),
                 exec_=None, notes=(), edits=(), mode=0o644, crlf=False, bom=False, nonl=False,
                 encoding="utf-8", origin=None, extra=None, expect_bytes=None):
        self.name, self.src = name, src
        self.uncertain, self.refuse, self.docrecs = uncertain, refuse, list(docrecs)
        self.placement, self.native, self.exec = placement or {}, list(native), exec_
        self.notes, self.edits, self.mode = list(notes), list(edits), mode
        self.crlf, self.bom, self.nonl, self.encoding = crlf, bom, nonl, encoding
        self.origin, self.extra = origin, extra or {}
        self.expect_bytes = expect_bytes

    def encode(self, lines):
        text = ("\r\n" if self.crlf else "\n").join(lines)
        data = text.encode(self.encoding)
        if self.bom:
            data = b"\xef\xbb\xbf" + data
        return data

    def write(self, lang_dir):
        lines, marks = split_marked(self.src)
        if self.nonl:
            if lines and lines[-1] == "":
                lines = lines[:-1]
        elif not lines or lines[-1] != "":
            raise ValueError("%s: source must end with a newline (or set nonl=True)" % self.name)
        lang = ANNOT_LANG[ext_of(self.name)]
        for i, l in enumerate(lines):
            if "testmap" in l and (i + 1) not in marks:
                raise ValueError("%s line %d mentions testmap but has no hand-oracle marker: %r" % (self.name, i + 1, l))
        base = os.path.join(lang_dir, self.name)
        data = self.encode(lines)
        if self.expect_bytes is not None and data != self.expect_bytes:
            raise ValueError("%s: regenerated bytes differ from the landed fixture" % self.name)
        with open(base + ".in", "wb") as f:
            f.write(data)
        os.chmod(base + ".in", self.mode)
        recs = records_of(lines, marks, self.docrecs)
        e = ["lang: %s" % lang, "expect: %s" % ("uncertain" if self.uncertain else "certain"), "read:"]
        e += ["  - %s" % r for r in recs]
        e.append("writable: %s" % fmt_lines(n for n, m in marks.items() if m == "W"))
        e.append("readonly: %s" % fmt_lines(n for n, m in marks.items() if m == "R"))
        e.append("lookalikes: %s" % fmt_lines(n for n, m in marks.items() if m == "L"))
        e.append("comments: %s" % fmt_lines(n for n, m in marks.items() if m in "WC"))
        e.append("refuse: %s" % (self.refuse or "none"))
        if self.placement:
            e.append("placement: " + " ".join(("file=%d" % resolve(lines, v)) if k == "" else ("member:%s=%d" % (k, resolve(lines, v)))
                                             for k, v in sorted(self.placement.items())))
        if self.native:
            e.append("native: " + "+".join(self.native))
        if self.exec:
            e.append("exec: " + self.exec)
        if self.origin:
            e.append("note: origin: " + self.origin)
        for n in self.notes:
            e.append("note: " + n)
        for k, v in sorted(self.extra.items()):
            e.append("%s: %s" % (k, v))
        with open(base + ".expect", "w") as f:
            f.write("\n".join(e) + "\n")
        if self.edits:
            self.write_edits(base, lines, marks)

    def write_edits(self, base, lines0, marks0):
        out = []
        lines, marks = list(lines0), dict(marks0)
        for op in self.edits:
            text, outcome, change = op[0], op[1], (op[2] if len(op) > 2 else None)
            if " from=original" in text:
                lines, marks = list(lines0), dict(marks0)
            if outcome == "applied":
                if change is None:
                    raise ValueError("%s: applied op %r needs a change" % (self.name, text))
                kind, n, new = change
                n = resolve(lines, n)
                nl, nm = split_marked(new)
                assert len(nl) == 1, "change text must be one line"
                new_line, new_mark = nl[0], nm.get(1)
                if kind == "ins":
                    lines = lines[:n] + [new_line] + lines[n:]
                    marks = {(k + 1 if k > n else k): v for k, v in marks.items()}
                    if new_mark:
                        marks[n + 1] = new_mark
                elif kind == "rep":
                    if lines[n - 1] == new_line:
                        raise ValueError("%s: rep at %d changes nothing" % (self.name, n))
                    lines = list(lines)
                    lines[n - 1] = new_line
                    marks.pop(n, None)
                    if new_mark:
                        marks[n] = new_mark
                else:
                    raise ValueError(kind)
            elif change is not None:
                raise ValueError("%s: op %r is %s but has a change" % (self.name, text, outcome))
            if text.startswith("stale ") and " mutate=" in text:
                # The mutation lands before Apply refuses: the file keeps it.
                how, _, arg = text.split(" mutate=", 1)[1].partition(":")
                if how == "append":
                    lines = (lines[:-1] if lines and lines[-1] == "" else lines) + [arg, ""]
                    if ANNOT.match(arg):
                        marks[len(lines) - 1] = "W"
                elif how == "replace":
                    ns, _, mtext = arg.partition(":")
                    n = int(ns)
                    lines = list(lines)
                    lines[n - 1] = mtext
                    marks.pop(n, None)
                    if ANNOT.match(mtext):
                        marks[n] = "W"
                else:
                    raise ValueError("%s: mutate %r" % (self.name, how))
            # docstring records never move in these fixtures (writes into them are refused)
            recs = records_of(lines, marks, self.docrecs)
            out += ["op: " + text, "outcome: " + outcome, "after:"] + ["  - %s" % r for r in recs] + [""]
        with open(base + ".edits", "w") as f:
            f.write("\n".join(out))


def write_all(corpus_dir, by_lang):
    names = set()
    for lang_dir, fixtures in by_lang.items():
        d = os.path.join(corpus_dir, lang_dir)
        os.makedirs(d, exist_ok=True)
        for fx in fixtures:
            key = (lang_dir, fx.name)
            if key in names:
                raise ValueError("duplicate fixture %s/%s" % key)
            names.add(key)
            fx.write(d)
    return len(names)
