#!/usr/bin/env python3
"""cd_guard_scan.py — find bash-test `cd`/`pushd` sites that can fall through (t1826).

A test that changes into a fixture directory and then writes relative paths is
safe only while that `cd` succeeds. When it fails, execution carries on in
whatever the cwd already was — the invoking directory, or the live repository if
the file returned there earlier (`cd "$PROJECT_DIR"`) — and the fixture writes,
`git init`, `git add`, `git commit` land in the real tree. t1815 proved this
happened (fixture task files and commits in the live `aitask-data` branch).

`set -e` is not a guard: errexit is suppressed inside `$( … )`, in
`if`/`while`/`||`/`&&`/`!` contexts and after `set +e`. `|| return` is not a
guard either: it relies on every caller checking, and the common
`setup_project` shape (`pushd` inside a function, relative writes in the caller)
shows callers do not. And a target's NAME says nothing about safety — `$REPO` is
a fixture in some files and `$REPO_ROOT` the live repo in others — so the rule
never looks at the target.

ACCEPTED forms (anything else is a violation):
  guarded            cd "$X" || exit 1      /  cd "$X" || { …; exit 1; }
                     Narrow on purpose: `exit` must be real code with at most a
                     numeric/`$?` status, be the LAST command of the braces, and
                     be followed by a real terminator. A pipeline, `&`, or a
                     redirection on the exit or the group is rejected -- e.g.
                     `|| exit 1 | cat` exits only a pipeline subshell, and
                     `|| exit 1 >log` never runs exit if the redirection fails.
  subshell-andchain  (cd "$X" && a && b)    /  "$(cd "$d" && pwd)"
                     the cd is the first command inside `(` or `$(` and only
                     `&&` (or a `|` pipeline inside one `&&` element) leads to
                     that group's closing `)` — a failed cd runs
                     nothing else in the group, and the group never moved the
                     caller's cwd
  exempt             a `# cd-guard: <reason>` COMMENT on the same line (the same
                     text inside a string does not count)

VIOLATION classes:
  unguarded            no guard at all (includes `cd X; …` and a trailing `)`)
  unconfined-andchain  `cd X && …` outside a `(`/`$(` group (top level or `{ }`),
                       or a group that continues past `;`/`||`/`|`
  conditional          `if`/`elif`/`while`/`until`/`!` before the cd — a failed
                       `if cd` with no `else` continues after `fi` in the old cwd
  weak-or              `|| true`, `|| return …`, `|| { … }` not ending in `exit`
  unquoted             an unquoted `$VAR` target (empty → `cd` goes to $HOME, rc 0)

Line-based, not a shell parser: it joins `\\`-continued lines, skips comment
lines and heredoc bodies, and ignores text inside quotes except `$( … )`.
False negatives remain (`eval`, computed command names); `tests/lib/scratch_cwd.sh`
is the second layer for those.

Usage:
  cd_guard_scan.py --check PATH...         violations as `path:line:class: text`; exit 1 if any
  cd_guard_scan.py --json PATH...          every site as JSON lines (used by one-off rewrites)
  cd_guard_scan.py --needs-helper PATH...  files with a cwd-changing cd outside `$( … )`
  cd_guard_scan.py --helper-order PATH...  those files' enter_scratch_cwd placement problems; exit 1 if any
"""

import bisect
import json
import re
import sys

ACCEPTED = {"guarded", "subshell-andchain", "exempt"}
_COND_WORDS = ("if", "elif", "while", "until", "!")
_POS_WORDS = ("then", "do", "else", "time") + _COND_WORDS
_EXEMPT = re.compile(r"#\s*cd-guard:\s*\S")
_HEREDOC_WORD = re.compile(r"-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")

CODE, TEXT, COMMENT = 1, 0, None


def _mask(s):
    """Per-character role for a whole file: CODE, TEXT (quoted/heredoc) or COMMENT.

    Double-quoted text is TEXT, but a `$( … )` inside it is CODE again, so
    `"$(cd "$d" && pwd)"` is scanned. Heredoc bodies (and their terminator line)
    are TEXT. A `# …` comment runs to the end of its physical line.
    """
    n = len(s)
    mask = [CODE] * n
    stack = ["code"]  # code | squote | dquote | subst
    depth = []  # paren depth per subst frame
    pending = []  # heredoc terminators opened on the current line
    i = 0
    while i < n:
        c = s[i]
        top = stack[-1]
        if top == "squote":
            mask[i] = TEXT
            if c == "'":
                stack.pop()
            i += 1
            continue
        if top == "dquote":
            if c == "\\":
                mask[i:i + 2] = [TEXT] * len(mask[i:i + 2])
                i += 2
                continue
            if c == '"':
                mask[i] = TEXT
                stack.pop()
                i += 1
                continue
            if s.startswith("$(", i) and not s.startswith("$((", i):
                stack.append("subst")
                depth.append(1)
                i += 2
                continue
            mask[i] = TEXT
            i += 1
            continue
        # code or subst
        if c == "\\":
            i += 2
            continue
        if c == "'":
            mask[i] = TEXT
            stack.append("squote")
            i += 1
            continue
        if c == '"':
            mask[i] = TEXT
            stack.append("dquote")
            i += 1
            continue
        if c == "#" and (i == 0 or s[i - 1] in " \t\n;(|&"):
            j = s.find("\n", i)
            j = n if j < 0 else j
            mask[i:j] = [COMMENT] * (j - i)
            i = j
            continue
        if c == "\n" and pending:
            # skip heredoc bodies: every line up to and including each terminator
            k = i + 1
            while pending and k < n:
                e = s.find("\n", k)
                e = n if e < 0 else e
                mask[k:e] = [TEXT] * (e - k)
                if s[k:e].strip() == pending[0]:
                    pending.pop(0)
                k = e + 1
            pending = []
            i = k
            continue
        if s.startswith("<<", i) and not s.startswith("<<<", i):
            m = _HEREDOC_WORD.match(s, i + 2)
            if m:
                pending.append(m.group(2))
                i = m.end()
                continue
        if top == "subst":
            if c == "(":
                depth[-1] += 1
            elif c == ")":
                depth[-1] -= 1
                if depth[-1] == 0:
                    stack.pop()
                    depth.pop()
                    i += 1
                    continue
        if s.startswith("$(", i) and not s.startswith("$((", i):
            stack.append("subst")
            depth.append(1)
            i += 2
            continue
        i += 1
    return mask


def _is_blank(s, i):
    """Blank for command-structure purposes: space, tab, or a line continuation."""
    return s[i] in " \t" or (s[i] == "\\" and s.startswith("\\\n", i)) or (
        s[i] == "\n" and i > 0 and s[i - 1] == "\\")


def _prev_token(s, mask, pos):
    """The token before pos, if pos is a command position; None if it is not."""
    j = pos - 1
    while j >= 0 and _is_blank(s, j):
        j -= 1
    if j < 0 or s[j] == "\n":
        return ""
    if mask[j] is not CODE:
        return None
    if s[j] in ";|&({`":
        if s[j] == "(" and j > 0 and s[j - 1] == "$":
            return "$("
        if s[j] in "|&" and j > 0 and s[j - 1] == s[j]:
            return s[j] * 2
        return s[j]
    if s[j] == "!":
        return "!"
    k = j
    while k >= 0 and mask[k] is CODE and (s[k].isalnum() or s[k] == "_"):
        k -= 1
    word = s[k + 1:j + 1]
    return word if word in _POS_WORDS else None


def _skip_blank(s, i):
    while i < len(s) and _is_blank(s, i):
        i += 1
    return i


def _args_end(s, mask, i):
    """End index of the command's arguments and redirections."""
    n = len(s)
    last = i
    nest = 0
    while i < n:
        role = mask[i]
        if role is COMMENT:
            break
        if role is TEXT:
            i += 1
            last = i
            continue
        c = s[i]
        if _is_blank(s, i):
            i += 1
            continue
        if s.startswith("$(", i):
            nest += 1
            i += 2
            last = i
            continue
        if c == ")" and nest:
            nest -= 1
            i += 1
            last = i
            continue
        if c in ";)\n|":
            break
        if c == "&" and not (i > 0 and s[i - 1] in "<>"):
            break
        i += 1
        last = i
    return last


_STATUS = re.compile(r"\d+|\$\?")


def _terminator_ok(s, mask, k):
    """True if position k ends a command outright.

    End of input, a newline, `;`, a closing `)` / `}`, or an `&&` / `||` chain:
    `exit` runs either way, so what follows it never executes. Everything else
    -- `|`, `&` and any redirection -- means the command is piped, backgrounded
    or redirected, and then the exit may never run at all.
    """
    k = _skip_blank(s, k)
    if k >= len(s) or mask[k] is COMMENT:
        return True
    if mask[k] is not CODE:
        return False
    if s.startswith("&&", k) or s.startswith("||", k):
        # `exit` runs either way, so the rest of the chain is dead code.
        # Backgrounding the list later does not change that: `&` puts the WHOLE
        # list -- the cd included -- in a subshell, so the exit ends that
        # subshell before anything else in it runs, and the parent's cwd was
        # never moved. test_cd_guard_lint.sh probes this directly.
        return True
    return s[k] in ";\n)}"


def _terminating_exit(s, mask, j):
    """Index of the terminator after an `exit` command at j that really ends the
    shell, else None.

    Deliberately narrow, and everything unrecognised is rejected: the word must
    be shell code, its only argument may be a numeric status or `$?`, and it must
    be followed by a real terminator. So `exit 1 | cat` (pipeline subshell),
    `exit 1 &`, `exit 1 >log` (a redirection that fails stops the exit from
    running) and `exit"_missing" 1` (bash concatenates it into `exit_missing`)
    are all rejected rather than parsed.
    """
    j = _skip_blank(s, j)
    if not s.startswith("exit", j) or any(mask[k] is not CODE for k in range(j, j + 4)):
        return None
    k = j + 4
    if k < len(s) and not (_is_blank(s, k) or (mask[k] is CODE and s[k] in ";\n)}")
                           or mask[k] is COMMENT):
        return None
    k = _skip_blank(s, k)
    if k < len(s) and mask[k] is CODE:
        m = _STATUS.match(s, k)
        if m:
            after = m.end()
            if after < len(s) and not (_is_blank(s, after)
                                       or (mask[after] is CODE and s[after] in ";\n)}")
                                       or mask[after] is COMMENT):
                return None
            k = _skip_blank(s, after)
    return k if _terminator_ok(s, mask, k) else None


def _or_rhs_class(s, mask, i):
    """Classify what follows the `||` at index i.

    `guarded` only for `|| exit [status]`, or a `{ …; }` group whose LAST command
    -- split on real (unquoted) separators -- is such an exit and whose closing
    `}` is itself followed by a real terminator (so the group is not piped,
    backgrounded or redirected). Anything else is `weak-or`: the rule fails
    closed rather than growing into a shell parser.
    """
    j = _skip_blank(s, i + 2)
    if _terminating_exit(s, mask, j) is not None:
        return "guarded"
    if j < len(s) and s[j] == "{" and mask[j] is CODE:
        depth = 0
        seg_start = j + 1
        last = None
        k = j + 1
        close = None
        while k < len(s):
            if mask[k] is CODE:
                c = s[k]
                if c in "({":
                    depth += 1
                elif c == ")":
                    depth -= 1
                elif c == "}":
                    if depth == 0:
                        close = k
                        break
                    depth -= 1
                elif depth == 0 and (c == ";" or (c == "\n" and s[k - 1] != "\\")):
                    if s[seg_start:k].strip():
                        last = seg_start
                    seg_start = k + 1
            k += 1
        if close is None:
            return "weak-or"
        if s[seg_start:close].strip():
            last = seg_start
        if last is not None and _terminating_exit(s, mask, last) is not None \
                and _terminator_ok(s, mask, close + 1):
            return "guarded"
    return "weak-or"


def _confined_andchain(s, mask, after_and):
    """True if only `&&` separates after_and from the enclosing group's `)`.

    A newline may appear only right before that `)` (e.g. after a heredoc
    body), never between two commands.
    """
    depth = 1
    i = after_and
    n = len(s)
    crossed_newline = False
    while i < n:
        role = mask[i]
        if role is not CODE:
            i += 1
            continue
        c = s[i]
        if _is_blank(s, i):
            i += 1
            continue
        if c == "\n":
            if depth == 1:
                crossed_newline = True
            i += 1
            continue
        if s.startswith("$(", i):
            depth += 1
            i += 2
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return True
        elif depth == 1:
            if crossed_newline:
                return False
            if s.startswith("&&", i):
                i += 2
                continue
            if s.startswith("||", i) or c == ";":
                return False
            if c == "|":
                # a pipeline binds tighter than `&&`: `cd X && a | b` is `cd X && (a | b)`
                i += 2 if s.startswith("|&", i) else 1
                continue
            if c == "&" and s[i - 1] not in "<>|":
                return False
        i += 1
    return False


def _words(s, mask, i, end):
    """(start, text) of each shell word in s[i:end]; quoted chars stay in their word."""
    words = []
    while i < end:
        i = _skip_blank(s, i)
        if i >= end:
            break
        j = i
        while j < end and not (mask[j] is CODE and _is_blank(s, j)):
            j += 1
        words.append((i, s[i:j]))
        i = j
    return words


_OPTION = re.compile(r"^-[LPe@]+$")
_REDIR = re.compile(r"^[0-9]*(>>?|<>|<|>&|<&|&>>?|>\|)")
# a redirection operator written as its own word takes the NEXT word as target
_REDIR_ALONE = re.compile(r"[0-9]*(>>?|<>|<|>&|<&|&>>?|>\|)")


def _unquoted_operand(s, mask, i, end):
    """True if the directory operand -- after options, `--` and redirections --
    is missing or begins with an unquoted `$` expansion. Either way an empty
    value makes `cd` go to $HOME and return 0, so no exit guard fires."""
    words = _words(s, mask, i, end)
    k = 0
    options_done = False
    while k < len(words):
        start, w = words[k]
        if _REDIR.match(w):
            k += 2 if _REDIR_ALONE.fullmatch(w) else 1
            continue
        if not options_done and w == "--":
            options_done = True
            k += 1
            continue
        if not options_done and _OPTION.match(w):
            k += 1
            continue
        return w.startswith("$") and mask[start] is CODE
    return True


def _chain_opener(s, mask, pos):
    """True if the `&&` chain containing the command at pos starts right after a
    `(` or `$(` opener, i.e. every element before it is joined by `&&` only."""
    depth = 0
    i = pos - 1
    while i >= 0:
        role = mask[i]
        if role is not CODE or _is_blank(s, i):
            i -= 1
            continue
        c = s[i]
        if c == ")":
            depth += 1
        elif c == "(":
            if depth == 0:
                return True
            depth -= 1
        elif depth == 0:
            if c == "&" and i > 0 and s[i - 1] == "&":
                i -= 2
                continue
            if c in ";{\n" or c == "|" and i > 0 and s[i - 1] == "|":
                return False
            if c == "&" and not (i > 0 and s[i - 1] in "<>"):
                return False
        i -= 1
    return False


def scan_text(text):
    mask = _mask(text)
    line_starts = [0] + [m.end() for m in re.finditer("\n", text)]

    def pos(idx):
        ln = bisect.bisect_right(line_starts, idx) - 1
        return ln + 1, idx - line_starts[ln]

    sites = []
    for m in re.finditer(r"(?<![\w./$-])(cd|pushd)(?=[ \t;]|$)", text, re.M):
        start = m.start()
        if mask[start] is not CODE:
            continue
        prev = _prev_token(text, mask, start)
        if prev is None:
            continue
        args_end = _args_end(text, mask, m.end())
        nxt = _skip_blank(text, args_end)
        line, col = pos(start)
        phys = text[line_starts[line - 1]:(text.find("\n", start) + 1 or len(text) + 1) - 1]
        ls = line_starts[line - 1]
        if any(mask[ls + e.start()] is COMMENT for e in _EXEMPT.finditer(phys)):
            cls = "exempt"
        elif prev in _COND_WORDS:
            cls = "conditional"
        elif text.startswith("||", nxt):
            cls = _or_rhs_class(text, mask, nxt)
        elif text.startswith("&&", nxt):
            if _chain_opener(text, mask, start) and _confined_andchain(text, mask, nxt + 2):
                cls = "subshell-andchain"
            else:
                cls = "unconfined-andchain"
        else:
            cls = "unguarded"
        unquoted = _unquoted_operand(text, mask, m.end(), args_end)
        if cls in ("guarded", "subshell-andchain") and unquoted:
            cls = "unquoted"
        iline, icol = pos(args_end)
        sites.append({
            "line": line,
            "col": col,
            "insert_line": iline,
            "insert_col": icol,
            "class": cls,
            "unquoted": bool(unquoted),
            "in_subst": prev == "$(",
            "opener": prev,
            "text": phys.strip()[:160],
        })
    return sites


def scan_file(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return scan_text(fh.read())


_CALL = re.compile(r"^[ \t]*enter_scratch_cwd[ \t]*$", re.M)
_CAPTURE = re.compile(r'=\s*"?(\$\(\s*pwd\s*\)|\$PWD\b|\$\{PWD\})')
_DERIVE = re.compile(r'dirname\s+"?\$(\{BASH_SOURCE|BASH_SOURCE|0\b)')


def helper_order(path):
    """Problems with a cwd-changing test's enter_scratch_cwd call, as strings.

    The call must exist in code (not a heredoc or string), precede the first
    cwd-changing cd, follow every `$(pwd)`/`$PWD` capture (else the capture
    records the invoking directory), and precede no relative `dirname
    "$BASH_SOURCE"`/`dirname "$0"` derivation (which would resolve against the
    scratch dir once the cwd has moved).
    """
    with open(path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    sites = [x for x in scan_text(text) if not x["in_subst"]]
    if not sites:
        return []
    first = min(x["line"] for x in sites)
    mask = _mask(text)

    def line_of(idx):
        return text.count("\n", 0, idx) + 1

    calls = [m.start() for m in _CALL.finditer(text)
             if mask[m.start() + len(m.group()) - len(m.group().lstrip())] is CODE]
    if not calls:
        return [f"no enter_scratch_cwd call (first cd at line {first})"]
    call = calls[0]
    out = []
    if line_of(call) > first:
        out.append(f"enter_scratch_cwd at line {line_of(call)} comes after the first cd at line {first}")
    for m in _CAPTURE.finditer(text, 0, call):
        if mask[m.start()] is CODE:
            out.append(f"line {line_of(m.start())} captures the invoking cwd before enter_scratch_cwd")
    for m in _DERIVE.finditer(text, call):
        if mask[m.start()] is CODE:
            out.append(f"line {line_of(m.start())} derives a path from a relative script name after enter_scratch_cwd")
    return out


def main(argv):
    if len(argv) < 2 or argv[0] not in ("--check", "--json", "--needs-helper", "--helper-order"):
        sys.stderr.write(__doc__)
        return 2
    mode, paths = argv[0], argv[1:]
    bad = 0
    for path in paths:
        sites = scan_file(path)
        if mode == "--json":
            for site in sites:
                print(json.dumps(dict(site, path=path)))
        elif mode == "--check":
            for site in sites:
                if site["class"] not in ACCEPTED:
                    bad += 1
                    print(f"{path}:{site['line']}:{site['class']}: {site['text']}")
        elif mode == "--needs-helper":
            first = [s["line"] for s in sites if not s["in_subst"]]
            if first:
                print(f"{path}:{min(first)}")
        else:
            for problem in helper_order(path):
                bad += 1
                print(f"{path}: {problem}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
