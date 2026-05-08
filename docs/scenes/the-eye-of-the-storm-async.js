// Scene: Await the Eye of the Storm
// Hurricane Alley, Caribbean Sea
window.CF.register("Await the Eye of the Storm", "Hurricane Alley, Caribbean Sea", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Spiral cloud generation
  var clouds = [];
  var r = srand(1001);
  var spiralCount = 120;
  for (var i = 0; i < spiralCount; i++) {
    var angle = i * (Math.PI * 2 / spiralCount);
    var rad = 70 + Math.sin(angle * 2) * 20 + r()*10; // dynamic radius
    clouds.push({
      x: W / 2 + Math.cos(angle) * rad,
      y: H / 2 + Math.sin(angle) * rad,
      offset: r() * Math.PI * 2,
      size: 4 + r() * 3
    });
  }

  // Ocean surface waves
  var waves = [];
  for (var j = 0; j < 240; j++) {
    waves.push({
      x: j,
      y: H / 2 + Math.sin(j * 0.05) * 5,
      phase: r()
    });
  }

  // Wind effect
  var windParticles = [];
  for (var k = 0; k < 50; k++) {
    windParticles.push({
      x: r() * W,
      y: r() * H / 2,
      vx: (0.1 + r() * 0.2),
      vy: (0.1 + r() * 0.2),
    });
  }

  return function(t){
    // === SKY ===
    rect(0, 0, W, H, rgba('#023e8a', 1));

    // === SPIRAL CLOUD WALL ===
    for (var cloud of clouds) {
      var angleOffset = cloud.offset + t * 0.5;
      var cx = W / 2 + Math.cos(angleOffset) * (Math.cos(t * 0.5) * 20 + 70);
      var cy = H / 2 + Math.sin(angleOffset) * (Math.cos(t * 0.5) * 20 + 70);
      circle(cx, cy, cloud.size, rgba('#caf0f8', 0.5));
    }

    // === EYE CENTER ===
    circle(W / 2, H / 2, 20, rgba('#adb5bd', 0.8));

    // === OCEAN SURFACE CHAOS ===
    for (var wave of waves) {
      wave.y += Math.sin(t + wave.phase) * 0.5; // dynamic movement
      px(wave.x, wave.y, rgba('#0077b6', 0.6));
      // Adding some foam effect
      if (wave.y < H / 2 + 3) {
        px(wave.x, wave.y - 1, rgba('#caf0f8', 0.8));
      }
    }

    // === WIND PARTICLES ===
    for (var p of windParticles) {
      p.x += p.vx;
      p.y += p.vy * 0.3 + Math.sin(t * 0.15) * 0.2;
      if (p.x > W) {
        p.x = 0;
        p.y = r() * H / 2;
      }
      px(p.x, p.y, rgba('#343a40', 0.3));
    }

    // Bottom glow line
    rect(0, H - 1, W, 1, rgba('#343a40', 0.3));
    rect(0, H - 2, W, 1, rgba('#0077b6', 0.1));
  };
});