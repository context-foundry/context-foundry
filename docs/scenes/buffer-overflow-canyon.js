// Scene: Buffer Overflow Canyon
// Antelope Canyon, Arizona, USA
window.CF.register("Buffer Overflow Canyon", "Antelope Canyon, Arizona, USA", function(api){
  var px = api.px, rect = api.rect, rgba = api.rgba, lerp = api.lerp, osc = api.osc, srand = api.srand, circle = api.circle, ctx = api.ctx, W = api.W, H = api.H;

  // Pre-compute canyon wall points
  var canyon = [];
  var rand = srand(1001);
  for (var x = 0; x < W; x++) {
    canyon[x] = H - 60 + Math.sin(x * 0.04) * 20 + rand() * 15;
  }

  // Sand wave parameters
  var sandWaves = 8; // Number of waves
  var waveAmplitude = 2; // Wave height
  var waveSpeed = 0.05; // Wave speed

  // Light beam parameters
  var lightBeams = [];
  for (var i = 0; i < 5; i++) {
    lightBeams.push({
      x: rand() * W,
      y: 0,
      angle: Math.PI / 2 + (rand() - 0.5) * 0.2,
      length: 50 + rand() * 30
    });
  }

  return function(t) {
    // === BACKGROUND SKY ===
    for (var y = 0; y < H; y++) {
      var p = y / H;
      rect(0, y, W, 1, lerp('#240046', '#f48c06', p));
    }

    // === CANYON WALLS ===
    for (var x = 0; x < W; x++) {
      var wallHeight = canyon[x];
      var color = lerp('#e85d04', '#faa307', x / W);
      for (var y = 0; y < wallHeight; y++) {
        px(x, y, color);
      }
    }

    // === SAND FLOOR ===
    for (var x = 0; x < W; x++) {
      for (var y = canyon[x]; y < H; y++) {
        var sandColor = lerp('#e85d04', '#f48c06', (y - canyon[x]) / (H - canyon[x]));
        px(x, y, sandColor);
      }
    }

    // === SAND WAVES ANIMATION ===
    for (var x = 0; x < W; x++) {
      var yWave = Math.floor(canyon[x] + Math.sin((x + t * 40) * waveSpeed) * waveAmplitude);
      px(x, yWave, '#faa307');
    }

    // === LIGHT BEAMS ANIMATION ===
    for (var beam of lightBeams) {
      var startX = beam.x;
      var startY = beam.y;
      for (var length = 0; length < beam.length; length++) {
        var beamY = startY + Math.sin(t * 2 + beam.x * 0.01) * 10; // Sway effect
        px(Math.floor(startX), Math.floor(beamY), rgba('#ffffff', 0.08));
        startY += Math.sin((length + t) * beam.angle);
      }
    }

    // === LIGHT BEAM APPEARANCE ===
    for (var beam of lightBeams) {
      var beamGlow = 0.2 + osc(t, 4, beam.x * 0.01) * 0.3;
      for (var length = 0; length < beam.length; length += 2) {
        px(Math.floor(beam.x), Math.floor(beam.y + length), rgba('#ffffff', beamGlow));
      }
    }

    // === BOTTOM GLOW LINE ===
    rect(0, H - 1, W, 1, rgba('#faa307', 0.3));
    rect(0, H - 2, W, 1, rgba('#f48c06', 0.1));
  };
});