#!/usr/bin/env node
// Validates a generated scene file for syntax, structure, and runtime safety.
// Usage: node validate-scene.js <path-to-scene.js>
// Exit 0 = valid, Exit 1 = invalid (errors printed to stderr)

import { readFileSync } from 'fs';
import { createCanvas } from 'canvas';

var file = process.argv[2];
if (!file) { console.error('Usage: node validate-scene.js <scene.js>'); process.exit(1); }

var code = readFileSync(file, 'utf8');
var errors = [];

// 1. Line count
var lines = code.split('\n').length;
if (lines < 80) errors.push('Too short: ' + lines + ' lines (min 80)');
if (lines > 500) errors.push('Too long: ' + lines + ' lines (max 500)');

// 2. Structural checks
if (!/window\.CF\.register\(/.test(code)) errors.push('Missing window.CF.register() call');
if (!/return\s+function\s*\(\s*t\s*\)/.test(code)) errors.push('Missing return function(t)');
if (!/rect\(0\s*,\s*H\s*-\s*[12]/.test(code)) errors.push('Missing bottom glow line');

// 3. Animation check -- at least 2 animation expressions
var animCount = 0;
if (/osc\(/.test(code)) animCount++;
if (/Math\.sin\(\s*t/.test(code)) animCount++;
if (/Math\.cos\(\s*t/.test(code)) animCount++;
if (/\.life/.test(code)) animCount++; // particle systems
if (animCount < 2) errors.push('Insufficient animation: found ' + animCount + ' animation patterns (need 2+)');

// 4. Forbidden patterns
var forbidden = [
  [/\bfetch\s*\(/, 'fetch()'],
  [/\bimport\s+/, 'import statement'],
  [/\brequire\s*\(/, 'require()'],
  [/\beval\s*\(/, 'eval()'],
  [/XMLHttpRequest/, 'XMLHttpRequest'],
  [/new\s+Image\s*\(/, 'new Image()'],
  [/new\s+Audio\s*\(/, 'new Audio()'],
];
for (var check of forbidden) {
  if (check[0].test(code)) errors.push('Forbidden: ' + check[1]);
}

// 5. Syntax check
try {
  new Function(code);
} catch (e) {
  errors.push('Syntax error: ' + e.message);
}

// 6. Runtime smoke test (5 frames)
if (errors.length === 0) {
  try {
    // Set up a fake CF namespace
    var scenes = [];
    var CF = { scenes: scenes, register: function(name, loc, factory) { scenes.push({ name: name, loc: loc, factory: factory }); } };

    // Create a real canvas context via node-canvas
    var canvas = createCanvas(480, 260);
    var ctx = canvas.getContext('2d');

    // Build the API
    function px(x, y, col) { ctx.fillStyle = col; ctx.fillRect(Math.floor(x), Math.floor(y), 1, 1); }
    function rect(x, y, w, h, col) { ctx.fillStyle = col; ctx.fillRect(Math.floor(x), Math.floor(y), Math.ceil(w), Math.ceil(h)); }
    function hexRgb(h) { var n = parseInt(h.slice(1), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; }
    function rgba(h, a) { var c = hexRgb(h); return 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',' + a + ')'; }
    function lerp(a, b, t) { var ar = hexRgb(a), br = hexRgb(b); return 'rgb(' + Math.round(ar[0] + (br[0] - ar[0]) * t) + ',' + Math.round(ar[1] + (br[1] - ar[1]) * t) + ',' + Math.round(ar[2] + (br[2] - ar[2]) * t) + ')'; }
    function osc(t, p, ph) { return (Math.sin((t / p) * Math.PI * 2 + (ph || 0)) + 1) / 2; }
    function srand(a) { return function() { a |= 0; a = a + 0x6D2B79F5 | 0; var t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
    function circle(cx, cy, r, col) { for (var dy = -r; dy <= r; dy++) for (var dx = -r; dx <= r; dx++) if (dx * dx + dy * dy <= r * r) px(cx + dx, cy + dy, col); }

    var api = { px: px, rect: rect, hexRgb: hexRgb, rgba: rgba, lerp: lerp, osc: osc, srand: srand, circle: circle, ctx: ctx, W: 480, H: 260 };

    // Execute the scene file in a VM-like context
    var fn = new Function('window', code);
    fn({ CF: CF });

    if (scenes.length === 0) {
      errors.push('Runtime: scene did not register');
    } else {
      var draw = scenes[0].factory(api);
      if (typeof draw !== 'function') {
        errors.push('Runtime: factory did not return a function');
      } else {
        // Run 5 frames
        for (var f = 0; f < 5; f++) {
          draw(f / 15);
        }
        console.log('Runtime: 5 frames OK');
      }
    }
  } catch (e) {
    errors.push('Runtime error: ' + e.message);
  }
}

// Report
if (errors.length > 0) {
  console.error('VALIDATION FAILED (' + errors.length + ' error' + (errors.length > 1 ? 's' : '') + '):');
  for (var err of errors) console.error('  - ' + err);
  process.exit(1);
} else {
  console.log('VALIDATION PASSED (' + lines + ' lines)');
  process.exit(0);
}
