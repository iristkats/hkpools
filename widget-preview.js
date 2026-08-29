#!/usr/bin/env node
/* =====================================================================
   widget-preview.js — runs hkpools-widget.js outside Scriptable.

   Scriptable's API is mocked just enough to execute the widget and print
   what it would draw, reading the local pools.json instead of the network.
   Two things it is for: seeing the layout without an iPhone, and giving CI
   a smoke test of the widget's own code (parity.js only covers the shared
   status engine inside it).

     node widget-preview.js                    both sizes, default pools
     node widget-preview.js small "sha tin"    one size, chosen pools
     node widget-preview.js --at 2026-08-25T10:30
     node widget-preview.js --warn            with an HKO signal up

   Exits non-zero if the widget throws or draws nothing.
   ===================================================================== */
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ROOT = __dirname;
const WIDGET = path.join(ROOT, "hkpools-widget.js");

/* ---- argument handling --------------------------------------------- */

const argv = process.argv.slice(2);
let at = null;
let warn = false;
const rest = [];
for (let i = 0; i < argv.length; i++) {
  if (argv[i] === "--at") at = new Date(argv[++i]);
  else if (argv[i] === "--warn") warn = true;   // pretend HKO has a signal up
  else rest.push(argv[i]);
}
const sizes = ["small", "medium"].includes(rest[0]) ? [rest.shift()]
                                                    : ["small", "medium"];
const param = rest.join(" ") || null;
if (at && isNaN(at)) {
  console.error("--at: unreadable date");
  process.exit(2);
}

/* ---- the mock ------------------------------------------------------ */

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const pad = (n) => String(n).padStart(2, "0");

function makeText(s) {
  return { _text: String(s), _kind: "text", font: null, textColor: null,
           lineLimit: 0, minimumScaleFactor: 1, rightAlignText() {},
           leftAlignText() {}, centerAlignText() {} };
}

function makeStack() {
  const kids = [];
  return {
    _kind: "stack", _kids: kids,
    addText(s) { const t = makeText(s); kids.push(t); return t; },
    addStack() { const st = makeStack(); kids.push(st); return st; },
    addSpacer(n) { kids.push({ _kind: "spacer", _n: n }); },
    addImage() { return {}; },
    setPadding() {}, centerAlignContent() {}, topAlignContent() {},
    bottomAlignContent() {}, layoutHorizontally() {}, layoutVertically() {},
  };
}

function scriptableMock(now, family, widgetParameter, warnings) {
  const root = makeStack();
  root._kind = "widget";
  root.backgroundGradient = null;
  root.refreshAfterDate = null;
  root.presentSmall = async () => {};
  root.presentMedium = async () => {};
  root.presentLarge = async () => {};

  const seen = { widget: null };

  function Color(hex, alpha) { this.hex = hex; this.alpha = alpha; }
  function LinearGradient() { this.colors = []; this.locations = []; }

  const fontStub = () => ({});
  const Font = new Proxy({}, { get: () => fontStub });

  function DateFormatter() {
    this.dateFormat = "";
    this.string = (d) => this.dateFormat
      .replace("EEE", DAYS[d.getDay()])
      .replace("HH", pad(d.getHours()))
      .replace("mm", pad(d.getMinutes()));
  }

  function Request(url) {
    this.url = url;
    this.timeoutInterval = 0;
    this.loadJSON = async () => {
      if (this.url.includes("weather.gov.hk")) return warnings;
      // the widget's own DATA_URL is a placeholder here; serve the repo copy
      return JSON.parse(fs.readFileSync(path.join(ROOT, "pools.json"), "utf8"));
    };
  }

  const files = new Map();
  const FileManager = {
    local: () => ({
      cacheDirectory: () => "/cache",
      joinPath: (a, b) => a + "/" + b,
      fileExists: (p) => files.has(p),
      readString: (p) => files.get(p),
      writeString: (p, s) => files.set(p, s),
      modificationDate: () => new Date(),
    }),
  };

  return {
    ctx: {
      console, Color, LinearGradient, Font, DateFormatter, Request, FileManager,
      ListWidget: function () { return root; },
      config: { runsInWidget: true, widgetFamily: family },
      args: { widgetParameter },
      Script: { setWidget: (w) => { seen.widget = w; }, complete: () => {} },
    },
    seen,
  };
}

/* ---- printing ------------------------------------------------------ */

function flatten(node) {
  const out = [];
  for (const k of node._kids || []) {
    if (k._kind === "text") out.push({ text: k._text, limit: k.lineLimit });
    else if (k._kind === "spacer") out.push({ spacer: k._n });
    else if (k._kind === "stack") {
      const row = flatten(k);
      out.push({ row, limit: row.some((i) => i.limit === 1) ? 1 : 0 });
    }
  }
  return out;
}

/* A stack lays out left-to-right; an argument-less spacer is the flexible one
   that pushes what follows to the right edge. A leading fixed spacer is an
   indent. Anything else just runs on. */
function renderRow(items, width) {
  const flex = items.findIndex((i) => "spacer" in i && i.spacer === undefined);
  const run = (list) => list.map((i) => {
    if (i.text !== undefined) return i.text;
    if (i.row) return renderRow(i.row, width);
    return " ".repeat(Math.max(1, Math.round((i.spacer || 0) / 6)));
  }).join("");

  if (flex < 0) return run(items);
  const left = run(items.slice(0, flex));
  const right = run(items.slice(flex + 1));
  if (!right) return left;
  return left + " ".repeat(Math.max(1, width - left.length - right.length)) + right;
}

function print(widget, family) {
  const width = family === "small" ? 34 : 60;
  const items = flatten(widget);
  console.log("+" + "-".repeat(width) + "+");
  let drawn = 0;
  for (const it of items) {
    if ("spacer" in it) continue;                 // vertical spacing
    const line = it.row ? renderRow(it.row, width) : it.text;
    if (line === undefined) continue;
    drawn++;
    // lineLimit 1 means the device shrinks then truncates it, never wraps —
    // so an overflowing line shows here as it will there
    for (const chunk of (it.limit === 1 ? [clip(line, width)] : wrap(line, width)))
      console.log("|" + chunk.padEnd(width) + "|");
  }
  console.log("+" + "-".repeat(width) + "+");
  return drawn;
}

const clip = (s, width) => (s.length > width ? s.slice(0, width - 1) + "…" : s);

function wrap(s, width) {
  const out = [];
  let line = s;
  while (line.length > width) { out.push(line.slice(0, width)); line = line.slice(width); }
  out.push(line);
  return out;
}

/* ---- run ----------------------------------------------------------- */

async function main() {
  if (!fs.existsSync(WIDGET)) {
    console.error("hkpools-widget.js is missing — run `python build.py`");
    process.exit(1);
  }
  let src = fs.readFileSync(WIDGET, "utf8");
  // read the repo's pools.json rather than whatever the widget points at,
  // and wrap the top-level await so a plain script can host it
  src = src.replace(/^const DATA_URL =[\s\S]*?;$/m,
                    'const DATA_URL = "file://pools.json";');
  src = "(async () => {\n" + src + "\n})()";

  // no warning in force by default, so the weather row stays off
  const warnings = warn
    ? { WTS: { name: "Thunderstorm Warning", code: "WTS",
               actionCode: "ISSUE", type: "Thunderstorm Warning" } }
    : {};

  let drawn = 0;
  for (const family of sizes) {
    const now = at || new Date();
    const { ctx, seen } = scriptableMock(now, family, param, warnings);
    // pin the engine's clock so --at is honoured all the way down
    ctx.__fixedNow = at;
    let code = src;
    if (at)
      code = code.replace("function hkNow(){",
        "function hkNow(){ if(typeof __fixedNow!=='undefined'&&__fixedNow) return __fixedNow;");

    try {
      await vm.runInNewContext(code, ctx, { filename: "hkpools-widget.js" });
    } catch (e) {
      console.error(`widget threw in ${family}: ${e.stack || e.message}`);
      process.exit(1);
    }
    if (!seen.widget) {
      console.error(`widget drew nothing in ${family}`);
      process.exit(1);
    }
    console.log(`\n${family}${at ? "  @ " + at.toISOString().slice(0, 16) : ""}`);
    drawn += print(seen.widget, family);
  }

  if (!drawn) {
    console.error("widget produced no content");
    process.exit(1);
  }
}

main();
