/* pick_logic.js - the frame picker's pure rules (no DOM).
 *
 * Mirrors vp_pick.py: copyBlock = copy_block, roiToSource = roi_to_source,
 * normRect = norm_rect, sanitizeNote = sanitize_note, seconds = seconds,
 * storageKey = storage_key. Every sentence comes from data.text (written by
 * vp_pick.py), so this file only does arithmetic and concatenation. The two
 * implementations must agree byte for byte; tests/test_screen_recording_core.py
 * (PickLogicJs) runs both over the same scenarios under node.
 */
(function (root) {
  "use strict";

  var NOTE_MAX = 200;

  function isControl(code) {
    return code < 32 || code === 127 || (code >= 0x80 && code < 0xA0) ||
      code === 0x2028 || code === 0x2029;
  }

  function fmt(template, values) {
    return template.replace(/\{(\w+)\}/g, function (m, key) {
      return Object.prototype.hasOwnProperty.call(values, key) ? String(values[key]) : m;
    });
  }

  function seconds(ms) {
    var whole = Math.floor(ms / 1000);
    var frac = String(ms % 1000);
    while (frac.length < 3) { frac = "0" + frac; }
    return whole + "." + frac;
  }

  function stripSpaces(chars) {
    var a = 0, b = chars.length;
    while (a < b && chars[a] === " ") { a += 1; }
    while (b > a && chars[b - 1] === " ") { b -= 1; }
    return chars.slice(a, b);
  }

  function sanitizeNote(text) {
    if (typeof text !== "string") { return ""; }
    var chars = [];
    for (var ch of text) {                      // code points, as Python counts them
      chars.push(isControl(ch.codePointAt(0)) ? " " : ch);
    }
    chars = stripSpaces(chars).slice(0, NOTE_MAX);
    return stripSpaces(chars).join("");
  }

  function toInt(v) {
    if (typeof v === "number" && isFinite(v)) { return Math.trunc(v) || 0; }
    if (typeof v === "string" && /^[ ]*[-+]?[0-9]+[ ]*$/.test(v)) { return parseInt(v, 10); }
    return null;
  }

  function normRect(rect, w, h) {
    if (!rect || typeof rect !== "object") { return null; }
    var a = toInt(rect.x0), b = toInt(rect.y0), c = toInt(rect.x1), d = toInt(rect.y1);
    if (a === null || b === null || c === null || d === null) { return null; }
    var x0 = Math.min(a, c), x1 = Math.max(a, c), y0 = Math.min(b, d), y1 = Math.max(b, d);
    if (w !== null && w !== undefined && h !== null && h !== undefined) {
      x0 = Math.max(0, Math.min(x0, w)); x1 = Math.max(0, Math.min(x1, w));
      y0 = Math.max(0, Math.min(y0, h)); y1 = Math.max(0, Math.min(y1, h));
    }
    if (x1 - x0 < 1 || y1 - y0 < 1) { return null; }
    return [x0, y0, x1, y1];
  }

  function roiToSource(r, g) {
    var X0 = g.crop_x + Math.floor(r[0] * g.crop_w / g.out_w);
    var X1 = g.crop_x + Math.ceil(r[2] * g.crop_w / g.out_w);
    var Y0 = g.crop_y + Math.floor(r[1] * g.crop_h / g.out_h);
    var Y1 = g.crop_y + Math.ceil(r[3] * g.crop_h / g.out_h);
    X0 = Math.max(0, Math.min(X0, g.src_w - 1));
    Y0 = Math.max(0, Math.min(Y0, g.src_h - 1));
    X1 = Math.max(X0 + 1, Math.min(X1, g.src_w));
    Y1 = Math.max(Y0 + 1, Math.min(Y1, g.src_h));
    return [X0, Y0, X1 - X0, Y1 - Y0];
  }

  function storageKey(data) {
    return "vp-pick:v" + data.version + ":" + data.fingerprint;
  }

  function copyBlock(data, state) {
    var T = data.text, frames = data.frames, byRel = Object.create(null), i;
    for (i = 0; i < frames.length; i += 1) { byRel[frames[i].rel] = frames[i]; }
    state = state || {};
    var sel = Object.create(null), selected = state.selected || [];
    for (i = 0; i < selected.length; i += 1) {
      if (typeof selected[i] === "string") { sel[selected[i]] = true; }
    }
    var chosen = frames.filter(function (f) { return sel[f.rel] === true; });
    if (!chosen.length) { return fmt(T.none_selected, { page: data.page }) + "\n"; }
    var n = chosen.length;
    var lines = [fmt(T.picked, { n: n, frames: n === 1 ? "frame" : "frames", page: data.page,
      set: data.fingerprint.slice(0, 8) })];
    var timed = chosen.filter(function (f) { return f.ms !== null; })
      .map(function (f) { return f.ms; });
    if (timed.length) {
      lines.push(fmt(T.view, { a: seconds(Math.min.apply(null, timed)),
        b: seconds(Math.max.apply(null, timed)) }));
    } else {
      lines.push(T.view_unknown);
    }
    var notes = state.notes || {}, prev = null;
    chosen.forEach(function (f) {
      var parts = [f.path];
      if (f.ms === null) {
        parts.push("t=unknown");
      } else {
        parts.push("t=" + f.ms + " ms");
        if (prev === null) {
          parts.push("first");
        } else {
          var d = f.ms - prev;
          parts.push((d >= 0 ? "+" : "") + d + " ms");
        }
        prev = f.ms;
      }
      var note = sanitizeNote((notes && typeof notes === "object" && !Array.isArray(notes) &&
        Object.prototype.hasOwnProperty.call(notes, f.rel)) ? notes[f.rel] : undefined);
      if (note) { parts.push("note: " + note); }
      lines.push(parts.join("\t"));
    });

    var marks = (state.marks && typeof state.marks === "object") ? state.marks : {};
    var sRel = marks.start, eRel = marks.end;
    if (sRel || eRel) {
      var fs = (typeof sRel === "string" && sRel in byRel) ? byRel[sRel] : undefined;
      var fe = (typeof eRel === "string" && eRel in byRel) ? byRel[eRel] : undefined;
      var why = null;
      if (!fs || !fe) {
        why = T.why_one_mark;
      } else if (fs === fe) {
        why = T.why_same;
      } else if (fs.ms === null || fe.ms === null) {
        why = T.why_untimed;
      } else if (fs.ms >= fe.ms) {
        why = T.why_order;
      }
      if (why) {
        lines.push(fmt(T.no_window, { why: why }));
      } else {
        var extra = (fs.time_source === "pts_time" || fe.time_source === "pts_time") ?
          T.window_pts_time : "";
        lines.push(fmt(T.window, { a: fs.window_start, b: fe.window_end,
          start: fs.display_name, sms: fs.ms, end: fe.display_name, ems: fe.ms, extra: extra }));
      }
    }

    var rect = state.rect;
    if (rect && typeof rect === "object" && typeof rect.rel === "string" && rect.rel in byRel) {
      var f = byRel[rect.rel], r = normRect(rect, f.w, f.h);
      if (r) {
        if (f.geom) {
          var s = roiToSource(r, f.geom);
          lines.push(fmt(T.roi, { x: s[0], y: s[1], w: s[2], h: s[3], name: f.display_name }));
        } else {
          lines.push(fmt(T.own_rect, { x: r[0], y: r[1], w: r[2] - r[0], h: r[3] - r[1],
            name: f.display_name, why: f.roi_disabled }));
        }
      }
    }
    lines.push(data.source_line);
    return lines.join("\n") + "\n";
  }

  root.VPPick = {
    copyBlock: copyBlock, roiToSource: roiToSource, normRect: normRect,
    sanitizeNote: sanitizeNote, seconds: seconds, storageKey: storageKey
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
