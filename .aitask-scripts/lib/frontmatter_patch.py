#!/usr/bin/env python3
"""frontmatter_patch.py - surgical mutation of a block-style YAML list-of-mappings
field in a markdown file's frontmatter (t1030_2; the task `attachments:` block).

Why line-based, not a YAML round-trip: a full pyyaml load/dump would reformat the
WHOLE frontmatter (drop comments, reorder keys, restyle scalars), violating
byte-preservation of unrelated metadata. So this edits ONLY the target field's
block, leaving every other line untouched, and bumps `updated_at`.

Output is consumed by yaml_utils.sh `read_yaml_mappings`, whose scalar reader
strips surrounding matching quotes and an inline `<whitespace>#` comment. The
writer here quotes a value exactly when needed so the reader reproduces it
verbatim (leading/trailing space, a whitespace-preceded `#`, a leading quote or
YAML indicator). Values containing a newline, or both quote styles, are rejected
(out of scope, matching the reader's documented limits).

Usage:
  frontmatter_patch.py append <file> <field> [--now <ts>] key=value [key=value ...]
  frontmatter_patch.py remove <file> <field> --match-key <k> --match-val <v> [--now <ts>]

Subcommands exit non-zero with a message on misuse / unrepresentable input.
"""

import re
import sys

# Emission order for attachment mapping fields (design §3 schema order).
FIELD_ORDER = ["hash", "name", "mime", "size", "added_at", "backend", "url"]

ITEM_RE = re.compile(r"^\s*-\s+(.*)$")
KV_RE = re.compile(r"^\s*-?\s*([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$")
TOPKEY_RE = re.compile(r"^\S")


def die(msg):
    sys.stderr.write("frontmatter_patch.py: " + msg + "\n")
    sys.exit(1)


def now_stamp(explicit):
    if explicit:
        return explicit
    import datetime
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def needs_quote(value):
    if value == "":
        return True
    if value != value.strip():
        return True
    if re.search(r"\s#", value):           # inline-comment ambiguity
        return True
    if re.search(r":(\s|$)", value):       # colon-space -> YAML mapping ambiguity
        return True
    if value[0] in "\"'[]{}#&*!|>%@`,:-?":  # leading YAML indicator
        return True
    return False


def quote(value):
    if "\n" in value or "\r" in value:
        die("value contains a newline (unsupported): " + repr(value))
    if not needs_quote(value):
        return value
    if '"' not in value:
        return '"' + value + '"'
    if "'" not in value:
        return "'" + value + "'"
    die("value cannot be safely quoted (contains both quote types): " + value)


def scalar_value(raw):
    """Mirror yaml_utils.sh _yaml_scalar_value for round-trip-correct matching."""
    val = raw.lstrip()
    if val.startswith('"'):
        return val[1:].split('"', 1)[0]
    if val.startswith("'"):
        return val[1:].split("'", 1)[0]
    val = re.sub(r"\s#.*$", "", val)
    return val.rstrip()


def find_frontmatter(lines):
    if not lines or lines[0].rstrip("\n") != "---":
        die("file has no YAML frontmatter (must start with '---')")
    for i in range(1, len(lines)):
        if lines[i].rstrip("\n") == "---":
            return 0, i
    die("unterminated frontmatter (no closing '---')")


def find_field_header(lines, fm_start, fm_end, field):
    pat = re.compile(r"^" + re.escape(field) + r":\s*(.*)$")
    for i in range(fm_start + 1, fm_end):
        m = pat.match(lines[i].rstrip("\n"))
        if m:
            return i, m.group(1).strip()
    return None, None


def block_extent(lines, header, fm_end):
    """Lines [header+1, end) that belong to the field's list block."""
    end = header + 1
    for i in range(header + 1, fm_end):
        if TOPKEY_RE.match(lines[i].rstrip("\n")):
            break
        end = i + 1
    return end


def parse_items(lines, header, block_end):
    """Yield (start, end_inclusive, fields_dict) for each list item."""
    items = []
    i = header + 1
    while i < block_end:
        line = lines[i].rstrip("\n")
        m = ITEM_RE.match(line)
        if not m:
            i += 1
            continue
        start = i
        fields = {}
        kv = KV_RE.match(line)
        if kv:
            fields[kv.group(1)] = scalar_value(kv.group(2))
        end = i
        j = i + 1
        while j < block_end:
            jline = lines[j].rstrip("\n")
            if ITEM_RE.match(jline):
                break
            if re.match(r"^\s+\S", jline) and not re.match(r"^\s*#", jline):
                kvj = KV_RE.match(jline)
                if kvj:
                    fields[kvj.group(1)] = scalar_value(kvj.group(2))
                end = j
                j += 1
                continue
            break
        items.append((start, end, fields))
        i = end + 1
    return items


def render_item(kv):
    out = ["  - "]
    first = True
    keys = [k for k in FIELD_ORDER if k in kv] + \
           [k for k in kv if k not in FIELD_ORDER]
    lines = []
    for k in keys:
        rendered = "%s: %s" % (k, quote(kv[k]))
        if first:
            lines.append("  - " + rendered + "\n")
            first = False
        else:
            lines.append("    " + rendered + "\n")
    return lines


def bump_updated_at(lines, fm_start, fm_end, stamp):
    for i in range(fm_start + 1, fm_end):
        if re.match(r"^updated_at:\s*", lines[i]):
            lines[i] = "updated_at: %s\n" % stamp
            return fm_end
    # No updated_at field — insert one just before the closing '---'.
    lines.insert(fm_end, "updated_at: %s\n" % stamp)
    return fm_end + 1


def parse_kv(args):
    out = {}
    for arg in args:
        if "=" not in arg:
            die("expected key=value, got: " + arg)
        key, val = arg.split("=", 1)
        out[key] = val
    return out


def cmd_append(path, field, stamp, kv):
    if not kv:
        die("append needs at least one key=value")
    with open(path, "r", encoding="utf-8") as fh:
        lines = fh.readlines()
    fm_start, fm_end = find_frontmatter(lines)
    header, header_val = find_field_header(lines, fm_start, fm_end, field)
    item_lines = render_item(kv)

    if header is None:
        # Field absent: insert "<field>:" + the item just before closing '---'.
        block = ["%s:\n" % field] + item_lines
        lines[fm_end:fm_end] = block
        fm_end += len(block)
    else:
        if header_val and header_val not in ("[]", "[ ]"):
            die("field '%s' is an inline flow list (%r); block-style mutation only"
                % (field, header_val))
        if header_val in ("[]", "[ ]"):
            lines[header] = "%s:\n" % field  # convert inline-empty to block
        block_end = block_extent(lines, header, fm_end)
        insert_at = header + 1
        for j in range(header + 1, block_end):
            if lines[j].strip() != "":
                insert_at = j + 1
        lines[insert_at:insert_at] = item_lines
        fm_end += len(item_lines)

    fm_end = bump_updated_at(lines, fm_start, fm_end, stamp)
    with open(path, "w", encoding="utf-8") as fh:
        fh.writelines(lines)


def cmd_remove(path, field, match_key, match_val, stamp):
    with open(path, "r", encoding="utf-8") as fh:
        lines = fh.readlines()
    fm_start, fm_end = find_frontmatter(lines)
    header, header_val = find_field_header(lines, fm_start, fm_end, field)
    if header is None:
        die("field '%s' not present" % field)
    block_end = block_extent(lines, header, fm_end)
    items = parse_items(lines, header, block_end)
    target = None
    for start, end, fields in items:
        if fields.get(match_key) == match_val:
            target = (start, end)
            break
    if target is None:
        die("no '%s' item with %s=%s" % (field, match_key, match_val))
    start, end = target
    del lines[start:end + 1]
    fm_end -= (end + 1 - start)
    bump_updated_at(lines, fm_start, fm_end, stamp)
    with open(path, "w", encoding="utf-8") as fh:
        fh.writelines(lines)


def main(argv):
    if len(argv) < 3:
        die("usage: frontmatter_patch.py <append|remove> <file> <field> ...")
    cmd, path, field = argv[0], argv[1], argv[2]
    rest = argv[3:]
    stamp = None
    if "--now" in rest:
        idx = rest.index("--now")
        stamp = rest[idx + 1]
        del rest[idx:idx + 2]
    stamp = now_stamp(stamp)

    if cmd == "append":
        cmd_append(path, field, stamp, parse_kv(rest))
    elif cmd == "remove":
        mk = mv = None
        if "--match-key" in rest:
            i = rest.index("--match-key")
            mk = rest[i + 1]
            del rest[i:i + 2]
        if "--match-val" in rest:
            i = rest.index("--match-val")
            mv = rest[i + 1]
            del rest[i:i + 2]
        if mk is None or mv is None:
            die("remove needs --match-key and --match-val")
        cmd_remove(path, field, mk, mv, stamp)
    else:
        die("unknown subcommand: " + cmd)


if __name__ == "__main__":
    main(sys.argv[1:])
