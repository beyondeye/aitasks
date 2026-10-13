#!/usr/bin/env node
// textmate_oracle.js — TextMate grammars (vscode-textmate + vscode-oniguruma,
// the grammars of shiki's `tm-grammars` package) as a t1954_3 provider helper.
//
// Protocol (one long-lived process; NODE_PATH = a node_modules holding
// vscode-textmate, vscode-oniguruma and tm-grammars): each stdin line is
// {"lang": "<research lang>", "src": "<base64 UTF-8>"} or {"version": true};
// each stdout line answers
//   {"tokens": [[start, end, class, text_b64], ...]}   BYTE offsets of the original source
// or {"error": "..."}. class: string | comment.line | comment.block | code | eol:<class>.
//
// vscode-textmate tokenises LINE BY LINE (the end-of-line bytes are never
// part of a token) and reports UTF-16 indices within the line. This helper
// converts each index to bytes (t1954_3 position contract) and emits each
// line break as an explicit `eol` token — classed as the construct it sits
// inside when the last token of its line and the first token of the next
// line share that class (a multi-line string or block comment), else code —
// so the tokens partition the file (Layer 1) and a literal continued across
// lines stays one construct (Layer 2). A token is a literal when ANY scope in
// its stack starts with `string.` (template interpolations included, the
// t1954_2 policy), a comment when any scope starts with `comment.`. TextMate
// has no error model (`invalid.*` scopes are grammar-optional), so nothing
// here is a diagnostic. The input is a BOM-stripped UTF-8 body; the Go side
// adds the BOM offset.
"use strict";

const fs = require("fs");
const path = require("path");
const readline = require("readline");
const vsctm = require("vscode-textmate");
const oniguruma = require("vscode-oniguruma");

const GRAMMAR = {
  bash: "shellscript", python: "python", go: "go", kotlin: "kotlin", typescript: "typescript",
  tsx: "tsx", javascript: "javascript", java: "java", rust: "rust", swift: "swift",
};

// Package directories from NODE_PATH (tm-grammars exports no package.json).
function pkgDir(name) {
  for (const d of (process.env.NODE_PATH || "").split(path.delimiter)) {
    if (d && fs.existsSync(path.join(d, name, "package.json"))) return path.join(d, name);
  }
  throw new Error(name + " not found on NODE_PATH");
}
const pkgVersion = (name) => JSON.parse(fs.readFileSync(path.join(pkgDir(name), "package.json"), "utf8")).version;
const tmDir = pkgDir("tm-grammars");
const byScope = new Map();
for (const f of fs.readdirSync(path.join(tmDir, "grammars"))) {
  if (!f.endsWith(".json")) continue;
  const p = path.join(tmDir, "grammars", f);
  const m = /"scopeName"\s*:\s*"([^"]+)"/.exec(fs.readFileSync(p, "utf8"));
  if (m) byScope.set(m[1], p);
}
const nameScope = (n) => JSON.parse(fs.readFileSync(path.join(tmDir, "grammars", n + ".json"), "utf8")).scopeName;

const wasm = fs.readFileSync(path.join(path.dirname(require.resolve("vscode-oniguruma")), "onig.wasm")).buffer;
const ready = oniguruma.loadWASM(wasm).then(() => new vsctm.Registry({
  onigLib: Promise.resolve({ createOnigScanner: (s) => new oniguruma.OnigScanner(s), createOnigString: (s) => new oniguruma.OnigString(s) }),
  loadGrammar: async (scope) => {
    const p = byScope.get(scope);
    return p ? vsctm.parseRawGrammar(fs.readFileSync(p, "utf8"), p) : null;
  },
}));
const grammars = new Map();

function classOf(scopes) {
  let cls = "code";
  for (const s of scopes) {
    if (s.startsWith("comment.block") || s.startsWith("comment.documentation")) return "comment.block";
    if (s.startsWith("comment.")) return "comment.line";
    if (s.startsWith("string.")) cls = "string";
  }
  return cls;
}

async function analyze(lang, text) {
  const registry = await ready;
  if (!grammars.has(lang)) grammars.set(lang, await registry.loadGrammar(nameScope(GRAMMAR[lang])));
  const grammar = grammars.get(lang);
  if (!grammar) throw new Error("no grammar for " + lang);
  const buf = Buffer.from(text, "utf8");
  const out = [];
  let stack = vsctm.INITIAL;
  let pos = 0; // UTF-16 index of the current line start
  let b = 0; // byte offset of the current line start
  const lines = [];
  while (pos <= text.length) {
    const nl = text.indexOf("\n", pos);
    const end = nl < 0 ? text.length : nl;
    let content = end;
    if (content > pos && text[content - 1] === "\r") content--;
    lines.push({ s: pos, c: content, e: nl < 0 ? end : nl + 1 });
    if (nl < 0) break;
    pos = nl + 1;
  }
  const perLine = [];
  for (const ln of lines) {
    const lineText = text.slice(ln.s, ln.c);
    const r = grammar.tokenizeLine(lineText, stack);
    stack = r.ruleStack;
    const toks = r.tokens.map((t, i) => ({
      s: t.startIndex, e: i + 1 < r.tokens.length ? r.tokens[i + 1].startIndex : lineText.length, cls: classOf(t.scopes),
    }));
    perLine.push({ ln, lineText, toks });
  }
  for (let li = 0; li < perLine.length; li++) {
    const { ln, lineText, toks } = perLine[li];
    let lb = b;
    for (const t of toks) {
      if (t.e <= t.s) continue;
      const bs = lb + Buffer.byteLength(lineText.slice(0, t.s), "utf8");
      const be = lb + Buffer.byteLength(lineText.slice(0, t.e), "utf8");
      out.push([bs, be, t.cls, buf.slice(bs, be).toString("base64")]);
    }
    const contentEnd = lb + Buffer.byteLength(lineText, "utf8");
    const lineEnd = b + Buffer.byteLength(text.slice(ln.s, ln.e), "utf8");
    if (lineEnd > contentEnd) {
      const last = toks.length ? toks[toks.length - 1].cls : "code";
      const next = li + 1 < perLine.length && perLine[li + 1].toks.length ? perLine[li + 1].toks[0].cls : "code";
      const cls = last === next && (last === "string" || last === "comment.block") ? last : "code";
      out.push([contentEnd, lineEnd, "eol:" + cls, buf.slice(contentEnd, lineEnd).toString("base64")]);
    }
    b = lineEnd;
  }
  return { tokens: out };
}

function serve() {
  const rl = readline.createInterface({ input: process.stdin });
  let chain = Promise.resolve();
  rl.on("line", (line) => {
    chain = chain.then(async () => {
      let resp;
      try {
        const req = JSON.parse(line);
        if (req.version) {
          resp = { version: "vscode-textmate " + pkgVersion("vscode-textmate") + " / vscode-oniguruma " +
            pkgVersion("vscode-oniguruma") + " / tm-grammars " + pkgVersion("tm-grammars") };
        } else {
          resp = await analyze(req.lang, Buffer.from(req.src, "base64").toString("utf8"));
        }
      } catch (e) {
        resp = { error: String(e && e.message || e) };
      }
      process.stdout.write(JSON.stringify(resp) + "\n");
    });
  });
}

serve();
