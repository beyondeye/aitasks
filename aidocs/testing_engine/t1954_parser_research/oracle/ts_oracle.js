#!/usr/bin/env node
// ts_oracle.js — parser-aware TypeScript/JavaScript comment extraction for the
// t1954 parser research (amendment A1 of the t1954_1 plan).
//
// A bare ts.createScanner loop is context-free: only the PARSER rescans
// template continuations (reScanTemplateToken), regex literals
// (reScanSlashToken) and JSX text, so a scan loop reads a `}` after `${x}` as a
// brace and reports comments inside templates. This oracle therefore:
//   1. parses with ts.createSourceFile (setParentNodes) and the script kind of
//      the file extension;
//   2. walks every token LEAF via node.getChildren(sf) — template heads /
//      middles / tails, regex literals and JsxText are single parser-produced
//      leaves, so none of their bytes is ever lexed as trivia;
//   3. takes comments only from each leaf's trivia [leaf.pos, leaf.getStart()):
//      the union of forEachTrailingCommentRange and forEachLeadingCommentRange
//      (leading collection skips comments before the first newline when
//      pos > 0), skipping JsxText leaves, and including EndOfFileToken;
//   4. self-checks FULL COVER: leaves + comments + whitespace must partition
//      the file; an unaccounted byte is an oracle error, never a silent result;
//   5. reports syntactic diagnostics from a one-file program.
// Offsets are converted from UTF-16 code units to UTF-8 BYTES.
//
// Usage:
//   node ts_oracle.js --serve            JSON lines {lang, src(base64)} -> {comments, diags, error}
//   node ts_oracle.js --selftest         pinned cases + the naive-scan negative control
//   node ts_oracle.js --file <path>      one file, human-readable
// typescript is resolved through NODE_PATH (the scratch node_modules).
"use strict";

const ts = require("typescript");
const fs = require("fs");
const path = require("path");
const readline = require("readline");

function scriptKind(name) {
  const ext = path.extname(name);
  return { ".ts": ts.ScriptKind.TS, ".mts": ts.ScriptKind.TS, ".tsx": ts.ScriptKind.TSX,
           ".js": ts.ScriptKind.JS, ".mjs": ts.ScriptKind.JS, ".jsx": ts.ScriptKind.JSX }[ext] || ts.ScriptKind.TS;
}

// UTF-16 index -> UTF-8 byte offset.
function byteMap(text) {
  const map = new Array(text.length + 1);
  let b = 0;
  for (let i = 0; i < text.length; i++) {
    map[i] = b;
    const c = text.charCodeAt(i);
    if (c < 0x80) b += 1;
    else if (c < 0x800) b += 2;
    else if (c >= 0xd800 && c <= 0xdbff && i + 1 < text.length) { map[i + 1] = b; b += 4; i++; continue; }
    else b += 3;
  }
  map[text.length] = b;
  return map;
}

function leaves(sf) {
  const out = [];
  (function walk(n) {
    const kids = n.getChildren(sf);
    if (kids.length === 0) { out.push(n); return; }
    for (const k of kids) walk(k);
  })(sf);
  return out;
}

function analyze(name, text) {
  const sf = ts.createSourceFile(name, text, ts.ScriptTarget.Latest, true, scriptKind(name));
  const comments = new Map();
  const add = (pos, end, kind) => { comments.set(pos + ":" + end, { pos, end, kind }); };
  const ls = leaves(sf);
  const covered = new Uint8Array(text.length);
  for (const leaf of ls) {
    const start = leaf.getStart(sf);
    for (let i = start; i < leaf.end; i++) covered[i] = 1;
    if (leaf.kind === ts.SyntaxKind.JsxText || leaf.kind === ts.SyntaxKind.JsxTextAllWhiteSpaces) {
      for (let i = leaf.pos; i < leaf.end; i++) covered[i] = 1;
      continue;
    }
    const cb = (pos, end, kind) => {
      if (pos >= leaf.pos && end <= start) add(pos, end, kind);
    };
    ts.forEachTrailingCommentRange(text, leaf.pos, cb);
    ts.forEachLeadingCommentRange(text, leaf.pos, cb);
  }
  // Shebang (only at 0; TS keeps it out of the trivia comment ranges).
  const shebang = /^#![^\n]*/.exec(text);
  if (shebang) for (let i = 0; i < shebang[0].length; i++) covered[i] = 1;
  for (const c of comments.values()) for (let i = c.pos; i < c.end; i++) covered[i] = 1;
  const unaccounted = [];
  for (let i = 0; i < text.length; i++) {
    if (!covered[i] && !/\s|﻿/.test(text[i])) unaccounted.push(i);
  }
  const prog = ts.createProgram({
    rootNames: [name], options: { noResolve: true, noLib: true, allowJs: true, jsx: ts.JsxEmit.Preserve, noEmit: true },
    host: Object.assign(ts.createCompilerHost({}), {
      getSourceFile: (f) => (f === name ? sf : undefined), fileExists: (f) => f === name,
      readFile: (f) => (f === name ? text : undefined),
    }),
  });
  const diags = prog.getSyntacticDiagnostics(sf).map((d) => ({ pos: d.start, msg: ts.flattenDiagnosticMessageText(d.messageText, " ") }));
  const bm = byteMap(text);
  return {
    comments: [...comments.values()].sort((a, b) => a.pos - b.pos)
      .map((c) => [bm[c.pos], bm[c.end], c.kind === ts.SyntaxKind.SingleLineCommentTrivia ? "line" : "block"]),
    diags: diags.map((d) => [bm[d.pos] || 0, d.msg]),
    unaccounted: unaccounted.slice(0, 5).map((i) => bm[i]),
  };
}

// The context-free scan loop the oracle must NOT be: the negative control.
function naiveComments(name, text) {
  const sc = ts.createScanner(ts.ScriptTarget.Latest, false, ts.LanguageVariant.Standard, text);
  const out = [];
  for (let t = sc.scan(); t !== ts.SyntaxKind.EndOfFileToken; t = sc.scan()) {
    if (t === ts.SyntaxKind.SingleLineCommentTrivia || t === ts.SyntaxKind.MultiLineCommentTrivia) {
      out.push([sc.getTokenStart(), sc.getTokenEnd()]);
    }
  }
  return out;
}

// Self-test: each case lists the exact text of every comment (hand-checked).
const SELFTEST = [
  { name: "template_repro.ts", text: "const x = 1;\nconst a = `${x}\n// testmap:covers fake\n`; // real\n// real2\n",
    want: ["// real", "// real2"] },
  { name: "nested_templates.ts", text: "const b = `o ${`i ${1}\n// fake\n`} d\n// fake2\n`;\n// real\n",
    want: ["// real"] },
  { name: "regex.ts", text: "const r = /\\/\\/ fake/;\nconst r3 = /x\\/*/;\n// real\n", want: ["// real"] },
  { name: "division.ts", text: "const d = 4 / 2 / 1; // c1\nconst e = d /* c2 */ / 2;\n", want: ["// c1", "/* c2 */"] },
  { name: "jsx.tsx", text: "export const C = () => (\n  <div>\n    // fake /* fake */\n    {/* real */}\n  </div>\n);\n// real2\n",
    want: ["/* real */", "// real2"] },
  { name: "shebang.js", text: "#!/usr/bin/env node\n// real\nconsole.log(1);\n", want: ["// real"] },
  // A type assertion is valid only in .ts; parsed as .tsx it would be JSX and lose the comment.
  { name: "type_assertion.ts", text: "const x = <number>1;\n// real\n", want: ["// real"] },
  { name: "unterminated.ts", text: "const s = `abc\n// fake\n", want: [], wantDiag: true },
];

function selftest() {
  let ok = true;
  const lines = [];
  for (const c of SELFTEST) {
    const r = analyze(c.name, c.text);
    const buf = Buffer.from(c.text, "utf8");
    const got = r.comments.map(([s, e]) => buf.slice(s, e).toString("utf8"));
    const pass = JSON.stringify(got) === JSON.stringify(c.want) && (!c.wantDiag || r.diags.length > 0) &&
      (c.wantDiag || r.diags.length === 0) && (c.wantDiag || r.unaccounted.length === 0);
    const naive = naiveComments(c.name, c.text).map(([s, e]) => c.text.slice(s, e));
    const naiveOk = JSON.stringify(naive) === JSON.stringify(c.want);
    lines.push(`${pass ? "PASS" : "FAIL"} ${c.name}: oracle=${JSON.stringify(got)} diags=${r.diags.length} | naive-scan ${naiveOk ? "agrees" : "WRONG"}=${JSON.stringify(naive)}`);
    if (!pass) ok = false;
    c.naiveWrong = !naiveOk;
  }
  const control = SELFTEST.find((c) => c.name === "template_repro.ts").naiveWrong;
  lines.push(`NEGATIVE-CONTROL ${control ? "PASS" : "FAIL"}: the naive scan loop ${control ? "fails" : "does not fail"} the template case`);
  if (!control) ok = false;
  lines.push(`TYPESCRIPT ${ts.version}`);
  lines.push(ok ? "SELFTEST:PASS" : "SELFTEST:FAIL");
  console.log(lines.join("\n"));
  process.exit(ok ? 0 : 1);
}

function serve() {
  const rl = readline.createInterface({ input: process.stdin });
  rl.on("line", (line) => {
    let resp;
    try {
      const req = JSON.parse(line);
      // The file name selects the script kind (.ts parses `<T>x` as a type
      // assertion, .tsx as JSX): never guessed.
      if (!req.name) throw new Error("request without a file name");
      const text = Buffer.from(req.src, "base64").toString("utf8");
      const r = analyze("input" + path.extname(req.name), text);
      resp = r.unaccounted.length ? { error: "unaccounted bytes at " + r.unaccounted.join(",") } : { comments: r.comments.map(([s, e]) => [s, e]), diags: r.diags };
    } catch (e) {
      resp = { error: String(e && e.message || e) };
    }
    process.stdout.write(JSON.stringify(resp) + "\n");
  });
}

const arg = process.argv[2];
if (arg === "--selftest") selftest();
else if (arg === "--serve") serve();
else if (arg === "--file") {
  const f = process.argv[3];
  const text = fs.readFileSync(f, "utf8");
  console.log(JSON.stringify(analyze(f.replace(/\.in$/, ""), text)));
} else {
  console.error("usage: ts_oracle.js --serve | --selftest | --file <path>");
  process.exit(64);
}
