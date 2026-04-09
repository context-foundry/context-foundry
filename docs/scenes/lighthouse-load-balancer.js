// Scene: Lighthouse Load Balancer
// Tower of Hercules, A Coruna, Spain
window.CF.register("Lighthouse Load Balancer", "Tower of Hercules, A Coruna, Spain", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Pre-compute wave parameters
  var waveCount = 70;
  var waves = [];
  for (var i = 0; i < waveCount; i++) {
    waves.push({
      shift: Math.random() * Math.PI * 2,
      height: 1 + Math.random() * 2,
      period: 1 + Math.random() * 3
    });
  }

  // Stormy wave particles
  var stormWaves = [];
  for (var i = 0; i < 50; i++) {
    stormWaves.push({
      x: Math.random() * W,
      y: Math.random() * 40 + H - 40,
      vy: -Math.random() * 0.5 - 0.5,
      life: Math.random() * 20 + 10
    });
  }

  // Lighthouse state
  var lightAngle = 0;

  return function(t){
    // === SKY: Gradient Background ===
    for (var y = 0; y < H; y++) {
      rect(0, y, W, 1, lerp('#264653', '#2a9d8f', y / H));
    }

    // === OCEAN WAVES ===
    for (var i = 0; i < waveCount; i++) {
      var wave = waves[i];
      for (var x = 0; x < W; x++) {
        var yWave = H - (H * 0.2 + Math.sin((x * 0.01 + wave.shift) * wave.period) * wave.height);
        px(x, yWave, '#ffffff');
      }
    }

    // === ROCKY COASTLINE ===
    for (var x = 0; x < W; x++) {
      if (Math.random() < 0.02) {
        px(x, H - 20 + Math.floor(Math.random() * 5), '#e76f51');
      }
    }

    // === STORMY WAVE PARTICLES ===
    for (var wave of stormWaves) {
      if (wave.life > 0) {
        px(wave.x, wave.y, rgba('#e76f51', 0.6));
        wave.y += wave.vy;
        wave.life--;
        if (wave.y < 0) {
          wave.y = H;
          wave.x = Math.random() * W;
          wave.life = Math.random() * 20 + 10;
        }
      }
    }

    // === LIGHTHOUSE TOWER ===
    rect(W / 2 - 10, H - 60, 20, 60, '#ffffff');
    rect(W / 2 - 5, H - 30, 10, 30, '#e9c46a');
    rect(W / 2 - 4, H - 70, 8, 10, '#e9c46a');

    // === LIGHT BEAM SWEEPING ===
    lightAngle += 0.04;
    var beamLength = 100;
    var beamX = W / 2 + Math.cos(lightAngle) * beamLength;
    var beamY = H - 65 + Math.sin(lightAngle) * beamLength;
    for (var i = -1; i <= 1; i++) {
      rect(W / 2, H - 65, beamX + i, beamY, rgba('#e9c46a', 0.6));
    }

    // === BOTTOM GLOW LINE ===
    rect(0, H - 1, W, 1, rgba('#264653', 0.3));
    rect(0, H - 2, W, 1, rgba('#2a9d8f', 0.1));
  };
});