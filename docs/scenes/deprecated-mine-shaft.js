// Scene: Deprecated Mine Shaft
// Wieliczka Salt Mine, Krakow, Poland
window.CF.register("Deprecated Mine Shaft", "Wieliczka Salt Mine, Krakow, Poland", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Pre-compute chandelier positions
  var chandeliers = [];
  (function() {
    var r = srand(1001);
    for (var i = 0; i < 3; i++) {
      chandeliers.push({
        x: 100 + r() * 280,
        y: 100 + r() * 100,
        flicker: r() * 3 + 0.5
      });
    }
  })();

  // Carved statue positions
  var statues = [];
  (function() {
    var r = srand(2002);
    for (var i = 0; i < 5; i++) {
      statues.push({
        x: 50 + r() * 380,
        y: H - 30 - r() * 60,
        height: 10 + r() * 20
      });
    }
  })();

  // Pre-compute beam positions
  var beams = [];
  (function() {
    var r = srand(3003);
    for (var i = 0; i < 10; i++) {
      beams.push({
        x: r() * W,
        y: H - 10
      });
    }
  })();

  return function(t) {
    // === BACKGROUND ===
    for (var y = 0; y < H; y++) {
      rect(0, y, W, 1, lerp('#6c757d', '#343a40', y / H));
    }

    // === BEAMS ===
    for (var beam of beams) {
      rect(beam.x, beam.y, 5, 40, '#adb5bd');
    }

    // === STATS ===
    for (var statue of statues) {
      for (var h = 0; h < statue.height; h++) {
        px(statue.x, statue.y - h, '#f4a261');
      }
      // Statue base
      rect(statue.x - 1, statue.y, 3, 1, '#dda15e');
    }

    // === CHAPEL ===
    var chapelBaseY = 170;
    rect(90, chapelBaseY, 300, 60, '#6c757d');
    for (var y = 0; y < 30; y++) {
      for (var x = 0; x < 80; x++) {
        px(90 + x, chapelBaseY - y, rgba('#adb5bd', (30 - y) * 0.03));
      }
    }

    // === CHANDELIERS ===
    for (var chandelier of chandeliers) {
      var flickerAlpha = osc(t * chandelier.flicker, 1, chandelier.flicker);
      circle(chandelier.x, chandelier.y, 10, rgba('#f4a261', flickerAlpha));
      circle(chandelier.x, chandelier.y, 8, rgba('#dda15e', flickerAlpha * 0.5));
      for (var i = -4; i <= 4; i++) {
        if (i !== 0) {
          px(chandelier.x + i, chandelier.y + 6, '#f4a261');
        }
      }
    }

    // === LIGHT RAYS ===
    for (var ray = 0; ray < 5; ray++) {
      var rayX = 120 + ray * 60;
      for (var y = 0; y < 20; y++) {
        var spread = Math.sin(t * 0.5 + ray) * 5;
        px(rayX - spread, y + 30, rgba('#FFFFFF', 0.05));
        px(rayX + spread, y + 30, rgba('#FFFFFF', 0.05));
      }
    }

    // === BOTTOM GLOW ===
    rect(0, H - 1, W, 1, rgba('#f4a261', 0.3));
    rect(0, H - 2, W, 1, rgba('#dda15e', 0.1));
  };
});