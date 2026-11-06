/* pick_ui.js - the frame picker's page behaviour (DOM).
 *
 * Grid, selection (click, shift-click range, keyboard), start/end marks, a
 * rectangle dragged on the large preview, per-frame notes, and the copy block,
 * which comes from VPPick.copyBlock (pick_logic.js) alone.
 *
 * State is kept in localStorage under a key bound to a fingerprint of the
 * snapshot's bytes, so a rebuild with new pixels starts clean; every storage
 * access is wrapped, and the page works without storage.
 *
 * Self-test: "#selftest=<json>" in the URL dispatches real events at the page's
 * own elements and records the copy block after each step on <body> (used by
 * tests/test_screen_recording_cli.py under headless chromium). It reads only
 * this page's own location hash.
 */
(function () {
  "use strict";
  var P = window.VPPick;
  var data = JSON.parse(document.getElementById("vp-data").textContent);
  var frames = data.frames;
  var byRel = Object.create(null);
  frames.forEach(function (f, i) { byRel[f.rel] = i; });

  var selftest = parseSelftest();
  if (selftest && selftest.nostorage) {
    try {
      Object.defineProperty(window, "localStorage", {
        configurable: true,
        get: function () { throw new Error("storage blocked (self-test)"); }
      });
    } catch (e) { /* the getter could not be replaced; storage stays as it is */ }
  }

  var selected = Object.create(null);
  var marks = { start: null, end: null };
  var notes = Object.create(null);
  var rect = null;
  var focus = 0;
  var anchor = null;

  var grid = document.getElementById("grid");
  var pvImg = document.getElementById("pv-img");
  var pvRect = document.getElementById("pv-rect");
  var preview = document.getElementById("preview");
  var pvInfo = document.getElementById("pv-info");
  var roiStatus = document.getElementById("roi-status");
  var noteInput = document.getElementById("note");
  var statusEl = document.getElementById("status");
  var copyText = document.getElementById("copy-text");
  var cards = [];

  // ------------------------------------------------------------------ state

  function blockState() {
    var sel = frames.filter(function (f) { return selected[f.rel] === true; })
      .map(function (f) { return f.rel; });
    var n = {};
    Object.keys(notes).forEach(function (k) { n[k] = notes[k]; });
    return { selected: sel, marks: { start: marks.start, end: marks.end }, notes: n,
      rect: rect ? { rel: rect.rel, x0: rect.x0, y0: rect.y0, x1: rect.x1, y1: rect.y1 } : null };
  }

  function storage() {
    try { return window.localStorage || null; } catch (e) { return null; }
  }

  function save() {
    var s = storage();
    if (!s) { return; }
    try { s.setItem(P.storageKey(data), JSON.stringify(blockState())); } catch (e) { /* full or blocked */ }
  }

  function isRel(v) { return typeof v === "string" && v in byRel; }

  function load() {
    var s = storage(), raw = null;
    if (!s) { return; }
    try { raw = s.getItem(P.storageKey(data)); } catch (e) { return; }
    if (!raw) { return; }
    var st;
    try { st = JSON.parse(raw); } catch (e) { return; }
    if (!st || typeof st !== "object") { return; }
    (Array.isArray(st.selected) ? st.selected : []).forEach(function (r) {
      if (isRel(r)) { selected[r] = true; }
    });
    if (st.marks && typeof st.marks === "object") {
      marks.start = isRel(st.marks.start) ? st.marks.start : null;
      marks.end = isRel(st.marks.end) ? st.marks.end : null;
    }
    if (st.notes && typeof st.notes === "object") {
      Object.keys(st.notes).forEach(function (k) {
        if (isRel(k) && typeof st.notes[k] === "string") { notes[k] = st.notes[k]; }
      });
    }
    var r = st.rect;
    if (r && typeof r === "object" && isRel(r.rel) && P.normRect(r, null, null)) {
      rect = { rel: r.rel, x0: r.x0, y0: r.y0, x1: r.x1, y1: r.y1 };
    }
  }

  // ------------------------------------------------------------------ grid

  function build() {
    var showHeads = data.groups.length > 1 || (data.groups[0] && data.groups[0].label);
    data.groups.forEach(function (g) {
      var sec = document.createElement("div");
      sec.className = "group";
      if (showHeads) {
        var h = document.createElement("h2");
        h.textContent = (g.label || "frames") + " (" + g.frames + ")";
        sec.appendChild(h);
      }
      var box = document.createElement("div");
      box.className = "cards";
      sec.appendChild(box);
      grid.appendChild(sec);
      frames.forEach(function (f, i) {
        if (f.group !== g.label) { return; }
        var card = document.createElement("button");
        card.type = "button";
        card.className = "card";
        card.dataset.index = String(i);
        card.setAttribute("aria-pressed", "false");
        var img = document.createElement("img");
        img.loading = "lazy";
        img.alt = "";
        img.draggable = false;
        img.src = f.url;
        var name = document.createElement("span");
        name.className = "name";
        name.textContent = "#" + f.order + " " + f.display_name;
        name.title = f.display_name;
        var label = document.createElement("span");
        label.className = "label";
        label.textContent = f.label;
        var badges = document.createElement("span");
        badges.className = "badges";
        card.appendChild(img);
        card.appendChild(name);
        card.appendChild(label);
        card.appendChild(badges);
        card.addEventListener("click", onCardClick);
        // the browser can move focus without a click (Tab, a screen reader, a script):
        // the focused card is the active frame
        card.addEventListener("focus", function () {
          var k = parseInt(this.dataset.index, 10);
          if (k !== focus) { focus = k; paintCards(); paintPreview(); }
        });
        card.addEventListener("keyup", function (ev) {
          if (ev.key === " ") { ev.preventDefault(); }   // Space is handled on keydown
        });
        box.appendChild(card);
        cards[i] = card;
      });
    });
  }

  function badge(cls, text) {
    var b = document.createElement("span");
    b.className = "badge " + cls;
    b.textContent = text;
    return b;
  }

  function paintCards() {
    cards.forEach(function (card, i) {
      var f = frames[i];
      var on = selected[f.rel] === true;
      card.classList.toggle("selected", on);
      card.classList.toggle("focused", i === focus);
      card.setAttribute("aria-pressed", on ? "true" : "false");
      var b = card.querySelector(".badges");
      while (b.firstChild) { b.removeChild(b.firstChild); }
      if (on) { b.appendChild(badge("check", "+")); }
      if (marks.start === f.rel) { b.appendChild(badge("start", "S")); }
      if (marks.end === f.rel) { b.appendChild(badge("end", "E")); }
      if (notes[f.rel]) { b.appendChild(badge("note", "N")); }
    });
  }

  // ------------------------------------------------------------------ preview

  function paintPreview() {
    var f = frames[focus];
    if (!f) { return; }
    if (pvImg.getAttribute("src") !== f.url) { pvImg.src = f.url; }
    var size = (f.w && f.h) ? (f.w + "x" + f.h) : "";
    pvInfo.textContent = "#" + f.order + " " + f.display_name + "  |  " + f.label +
      (size ? "  |  " + size + " px" : "");
    if (f.geom) {
      roiStatus.className = "";
      roiStatus.textContent = "A rectangle drawn here becomes a source-video --roi (frames.tsv " +
        "geometry, SHA-256 verified).";
    } else {
      roiStatus.className = "off";
      roiStatus.textContent = "Source --roi disabled: " + f.roi_disabled +
        ". A rectangle stays in this image's own pixels.";
    }
    if (document.activeElement !== noteInput) { noteInput.value = notes[f.rel] || ""; }
    paintRect();
  }

  function paintRect() {
    var f = frames[focus];
    if (!rect || !f || rect.rel !== f.rel || !pvImg.naturalWidth) {
      pvRect.hidden = true;
      return;
    }
    var r = pvImg.getBoundingClientRect();
    var sx = r.width / pvImg.naturalWidth, sy = r.height / pvImg.naturalHeight;
    pvRect.style.left = (Math.min(rect.x0, rect.x1) * sx) + "px";
    pvRect.style.top = (Math.min(rect.y0, rect.y1) * sy) + "px";
    pvRect.style.width = (Math.abs(rect.x1 - rect.x0) * sx) + "px";
    pvRect.style.height = (Math.abs(rect.y1 - rect.y0) * sy) + "px";
    pvRect.hidden = false;
  }

  function toNatural(ev) {
    var r = pvImg.getBoundingClientRect();
    var x = Math.floor((ev.clientX - r.left) * pvImg.naturalWidth / r.width);
    var y = Math.floor((ev.clientY - r.top) * pvImg.naturalHeight / r.height);
    return { x: Math.max(0, Math.min(x, pvImg.naturalWidth - 1)),
      y: Math.max(0, Math.min(y, pvImg.naturalHeight - 1)) };
  }

  var drag = null;

  preview.addEventListener("pointerdown", function (ev) {
    if (!pvImg.naturalWidth || !frames[focus]) { return; }
    ev.preventDefault();
    drag = { start: toNatural(ev), before: rect, rel: frames[focus].rel };
    try { preview.setPointerCapture(ev.pointerId); } catch (e) { /* synthetic pointer */ }
  });

  function dragTo(ev) {
    var c = toNatural(ev), s = drag.start;
    rect = { rel: drag.rel, x0: Math.min(s.x, c.x), y0: Math.min(s.y, c.y),
      x1: Math.max(s.x, c.x) + 1, y1: Math.max(s.y, c.y) + 1 };
    return c;
  }

  preview.addEventListener("pointermove", function (ev) {
    if (!drag) { return; }
    dragTo(ev);
    paintRect();
  });

  preview.addEventListener("pointerup", function (ev) {
    if (!drag) { return; }
    var c = dragTo(ev);
    if (c.x === drag.start.x && c.y === drag.start.y) { rect = drag.before; }  // a click, not a drag
    drag = null;
    try { preview.releasePointerCapture(ev.pointerId); } catch (e) { /* synthetic pointer */ }
    update();
  });

  pvImg.addEventListener("load", paintRect);
  window.addEventListener("resize", paintRect);

  // ------------------------------------------------------------------ actions

  function setFocus(i) {
    if (!cards.length) { return; }
    focus = Math.max(0, Math.min(i, cards.length - 1));
    try { cards[focus].focus({ preventScroll: true }); } catch (e) { cards[focus].focus(); }
    try { cards[focus].scrollIntoView({ block: "nearest" }); } catch (e) { /* old browser */ }
  }

  function toggle(i) {
    var rel = frames[i].rel;
    if (selected[rel] === true) { delete selected[rel]; } else { selected[rel] = true; }
  }

  function selectRange(a, b) {
    for (var k = Math.min(a, b); k <= Math.max(a, b); k += 1) { selected[frames[k].rel] = true; }
  }

  function onCardClick(ev) {
    var i = parseInt(this.dataset.index, 10);
    if (ev.shiftKey && anchor !== null) {
      selectRange(anchor, i);
    } else {
      toggle(i);
      anchor = i;
    }
    setFocus(i);
    update();
  }

  function vertical(dir) {
    var cur = cards[focus].getBoundingClientRect(), best = null, bestD = Infinity, rowTop = null;
    for (var k = focus + dir; k >= 0 && k < cards.length; k += dir) {
      var r = cards[k].getBoundingClientRect();
      if (Math.abs(r.top - cur.top) < 2) { continue; }
      if (rowTop === null) { rowTop = r.top; }
      if (Math.abs(r.top - rowTop) >= 2) { break; }
      var d = Math.abs(r.left - cur.left);
      if (d < bestD) { bestD = d; best = k; }
    }
    return best === null ? focus : best;
  }

  function moveTo(i, extend) {
    if (extend) {
      if (anchor === null) { anchor = focus; }
      selectRange(anchor, Math.max(0, Math.min(i, cards.length - 1)));
    }
    setFocus(i);
    update();
  }

  function mark(which) {
    var rel = frames[focus].rel;
    marks[which] = rel;
    selected[rel] = true;
    update();
  }

  function status(text, warn) {
    statusEl.textContent = text;
    statusEl.className = warn ? "warn" : "";
  }

  function selectBlock() {
    try {
      var range = document.createRange();
      range.selectNodeContents(copyText);
      var s = window.getSelection();
      s.removeAllRanges();
      s.addRange(range);
    } catch (e) { /* nothing more to do: the text is on screen */ }
  }

  function copy() {
    var text = P.copyBlock(data, blockState());
    var fail = function () {
      selectBlock();
      status("Copy did not work here. The text below is selected: press Ctrl+C (Cmd+C on a " +
        "Mac), then paste it into the agent.", true);
    };
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function () {
          status("Copied. Paste it into the agent.", false);
        }, fail);
        return;
      }
    } catch (e) { /* fall through */ }
    fail();
  }

  function cardIndex(el) {
    return (el && el.classList && el.classList.contains("card")) ?
      parseInt(el.dataset.index, 10) : null;
  }

  document.addEventListener("keydown", function (ev) {
    var t = ev.target;
    if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA")) {
      if (ev.key === "Escape" || ev.key === "Enter") { t.blur(); setFocus(focus); }
      return;
    }
    if (ev.ctrlKey || ev.metaKey || ev.altKey) { return; }
    var ci = cardIndex(t);
    if (ci !== null) {
      focus = ci;                       // act on the card the browser has focused
    } else if (t && t !== document.body && t !== document.documentElement &&
               (ev.key === " " || ev.key === "Enter")) {
      return;                           // a button or link keeps its native activation
    }
    var handled = true;
    switch (ev.key) {
      case "ArrowRight": moveTo(focus + 1, ev.shiftKey); break;
      case "ArrowLeft": moveTo(focus - 1, ev.shiftKey); break;
      case "ArrowDown": moveTo(vertical(1), ev.shiftKey); break;
      case "ArrowUp": moveTo(vertical(-1), ev.shiftKey); break;
      case "Home": moveTo(0, ev.shiftKey); break;
      case "End": moveTo(cards.length - 1, ev.shiftKey); break;
      case " ": toggle(focus); anchor = focus; update(); break;
      case "s": case "S": mark("start"); break;
      case "e": case "E": mark("end"); break;
      case "x": case "X": marks.start = null; marks.end = null; update(); break;
      case "Escape": rect = null; update(); break;
      case "c": case "C": copy(); break;
      default: handled = false;
    }
    if (handled) { ev.preventDefault(); }
  });

  noteInput.addEventListener("input", function () {
    var rel = frames[focus].rel;
    if (noteInput.value) { notes[rel] = noteInput.value; } else { delete notes[rel]; }
    update();
  });

  document.getElementById("btn-start").addEventListener("click", function () { mark("start"); });
  document.getElementById("btn-end").addEventListener("click", function () { mark("end"); });
  document.getElementById("btn-clear-marks").addEventListener("click", function () {
    marks.start = null; marks.end = null; update();
  });
  document.getElementById("btn-clear-rect").addEventListener("click", function () {
    rect = null; update();
  });
  document.getElementById("btn-clear-sel").addEventListener("click", function () {
    selected = Object.create(null); anchor = null; update();
  });
  document.getElementById("btn-copy").addEventListener("click", copy);

  function update() {
    paintCards();
    paintPreview();
    copyText.textContent = P.copyBlock(data, blockState());
    save();
  }

  // ------------------------------------------------------------------ self-test

  function parseSelftest() {
    var h = window.location.hash || "";
    if (h.indexOf("#selftest=") !== 0) { return null; }
    try { return JSON.parse(decodeURIComponent(h.slice("#selftest=".length))); } catch (e) {
      return { error: String(e) };
    }
  }

  function imageReady(img) {
    return new Promise(function (resolve) {
      if (img.complete && img.naturalWidth) { resolve(); return; }
      img.addEventListener("load", function () { resolve(); }, { once: true });
      img.addEventListener("error", function () { resolve(); }, { once: true });
    });
  }

  function pointer(type, x, y) {
    var r = pvImg.getBoundingClientRect();
    var cx = r.left + (x + 0.5) * r.width / pvImg.naturalWidth;
    var cy = r.top + (y + 0.5) * r.height / pvImg.naturalHeight;
    preview.dispatchEvent(new PointerEvent(type, { bubbles: true, cancelable: true, pointerId: 1,
      isPrimary: true, pointerType: "mouse", clientX: cx, clientY: cy, buttons: 1 }));
  }

  async function runSelftest(spec) {
    var trace = [], events = [];
    var body = document.body;
    try {
      if (spec.error) { throw new Error(spec.error); }
      var steps = Array.isArray(spec.steps) ? spec.steps : [];
      for (var k = 0; k < steps.length; k += 1) {
        var s = steps[k], cancelled = null;
        if (typeof s.click === "number") {
          cards[s.click].dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true,
            shiftKey: !!s.shift }));
        } else if (typeof s.key === "string") {
          cancelled = !(document.activeElement || document.body).dispatchEvent(
            new KeyboardEvent("keydown", { key: s.key, shiftKey: !!s.shift, bubbles: true,
              cancelable: true }));
        } else if (typeof s.note === "string") {
          noteInput.focus();
          noteInput.value = s.note;
          noteInput.dispatchEvent(new Event("input", { bubbles: true }));
          noteInput.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true,
            cancelable: true }));
        } else if (typeof s.focusCard === "number") {
          cards[s.focusCard].focus();              // focus moves without a click
        } else if (typeof s.focusButton === "string") {
          document.getElementById(s.focusButton).focus();
        } else if (typeof s.clickButton === "string") {
          document.getElementById(s.clickButton).click();
          for (var w = 0; w < 40 && !statusEl.textContent; w += 1) {
            await new Promise(function (r) { setTimeout(r, 25); });   // the clipboard answers later
          }
        } else if (Array.isArray(s.drag)) {
          await imageReady(pvImg);
          pointer("pointerdown", s.drag[0], s.drag[1]);
          pointer("pointermove", s.drag[2], s.drag[3]);
          pointer("pointerup", s.drag[2], s.drag[3]);
        } else {
          throw new Error("unknown self-test step " + JSON.stringify(s));
        }
        trace.push(copyText.textContent);
        var ae = document.activeElement;
        events.push({ cancelled: cancelled, status: statusEl.textContent,
          active: cardIndex(ae) !== null ? "card:" + cardIndex(ae) : (ae && ae.id) || "" });
      }
      body.dataset.trace = JSON.stringify(trace);
      body.dataset.events = JSON.stringify(events);
      body.dataset.state = JSON.stringify(blockState());
      body.dataset.selftest = "done";
    } catch (e) {
      body.dataset.trace = JSON.stringify(trace);
      body.dataset.selftest = "error: " + String(e && e.message || e);
    }
  }

  // ------------------------------------------------------------------ start

  build();
  load();
  setFocus(0);
  update();
  if (selftest) { runSelftest(selftest); }
})();
