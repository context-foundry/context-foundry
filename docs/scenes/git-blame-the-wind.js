// Scene: git blame the Wind
// Sahara Desert, Erg Chebbi, Morocco
window.CF.register("git blame the Wind", "Sahara Desert, Erg Chebbi, Morocco", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Pre-compute sand dunes and camels
  var dunes = [];
  var camelCaravan = [];
  var sandR = srand(1001);
  
  for (var i = 0; i < 5; i++) {
    dunes.push({
      x: (i + 1) * (W / 6),
      height: 50 + Math.random() * 30,
      base: H - 50,
    });
  }
  
  for (var i = 0; i < 3; i++) {
    camelCaravan.push({
      x: 100 + i * 80,
      y: H - 80 + Math.sin(i) * 2,
      size: 6,
      phase: Math.random() * Math.PI * 2,
    });
  }

  // Sun position
  var sunY = 40;
  
  return function(t){
    // === SKY ===
    for (var y = 0; y < 100; y++) {
      var p = y / 100;
      rect(0, y, W, 1, lerp('#264653', '#2a9d8f', p));
    }

    // === SUN ===
    var sunX = W - 60;
    for (var dx = -10; dx <= 10; dx++) {
      for (var dy = -10; dy <= 10; dy++) {
        if (Math.sqrt(dx * dx + dy * dy) < 10) {
          px(sunX + dx, sunY + dy, rgba('#f4a261', 0.05 * (10 - Math.sqrt(dx * dx + dy * dy))));
        }
      }
    }
    circle(sunX, sunY, 10, '#f4a261');

    // === SAND DUNES ===
    for (var dune of dunes) {
      for (var x = 0; x < W; x++) {
        var y = dune.base - Math.sin((x - dune.x) * 0.05) * dune.height;
        px(x, y, '#e9c46a');
      }
    }

    // === CAMEL CARAVAN ===
    function drawCamel(camel) {
      for (var dx = -camel.size; dx <= camel.size; dx++) {
        for (var dy = 0; dy <= camel.size / 2; dy++) {
          px(camel.x + dx, camel.y - dy, '#e76f51');
        }
      }
      // Camel humps
      circle(camel.x, camel.y - camel.size / 2, camel.size / 2, '#f4a261');
    }

    for (var camel of camelCaravan) {
      camel.x += Math.sin(t + camel.phase) * 0.1; // Swaying effect
      drawCamel(camel);
    }

    // === WIND-CARVED RIDGELINES ===
    for (var x = 0; x < W; x++) {
      var yBase = H - 50;
      var yWave = yBase - Math.sin(x * 0.05 + t) * 5;
      px(x, yWave, '#264653');
    }

    // === HORIZON GLOW ===
    for (var y = 100; y < 120; y++) {
      var glowA = 0.02 * (120 - y);
      rect(0, y, W, 1, rgba('#f4a261', glowA));
    }

    // === DESERT FLOOR ===
    for (var y = 120; y < H; y++) {
      for (var x = 0; x < W; x++) {
        px(x, y, rgba('#e9c46a', (H - y) / (H - 120)));
      }
    }

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#e9c46a',0.3));
    rect(0,H-2,W,1,rgba('#2a9d8f',0.1));
  };
});