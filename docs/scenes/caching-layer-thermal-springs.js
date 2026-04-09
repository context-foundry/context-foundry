// Scene: Caching Layer: Thermal Springs
// Blue Lagoon, Grindavik, Iceland
window.CF.register("Caching Layer: Thermal Springs", "Blue Lagoon, Grindavik, Iceland", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Steam particle system
  var steamParticles = [];
  (function(){
    var r = srand(100);
    for (var i = 0; i < 30; i++) {
      steamParticles.push({
        x: r() * W,
        y: H - 80 - r() * 30,
        size: 2 + r() * 2,
        life: 40 + r() * 20,
        age: 0,
        risingSpeed: -0.5 - r() * 0.5,
        alpha: 0.3 + r() * 0.5
      });
    }
  })();

  // Lava field
  var lavaField = [];
  (function(){
    var r = srand(200);
    for (var x = 0; x < W; x++) {
      var lavaHeight = Math.floor(180 + Math.sin(x * 0.05) * 10);
      lavaField[x] = lavaHeight;
      for (var y = lavaHeight; y < H; y++) {
        px(x, y, rgba('#495057', 0.8));
      }
    }
  })();

  // Wooden walkway
  var walkwaySegments = [];
  (function(){
    var r = srand(300);
    for (var i = 0; i < 15; i++) {
      var segmentX = Math.floor(i * (W / 14));
      var baseY = H - 50 - Math.floor(r() * 20);
      walkwaySegments.push({ x: segmentX, y: baseY });
      rect(segmentX - 3, baseY, 6, 5, '#264653');
    }
  })();

  return function(t){
    // === SKY ===
    for (var y = 0; y < 80; y++) {
      var p = y / 80;
      rect(0, y, W, 1, lerp('#caf0f8', '#90e0ef', p));
    }

    // === MILKY BLUE WATER ===
    for (var y = 80; y < 140; y++) {
      for (var x = 0; x < W; x++) {
        var waterWave = Math.sin(x * 0.03 + t * 3) * 2;
        var waterColor = lerp('#48cae4', '#90e0ef', (y - 80) / 60);
        px(x, y, waterColor);
        if (waterWave > 0) {
          pixelatedWaterShade(x, y, waterWave);
        }
      }
    }

    // === STEAM ===
    for (var i = 0; i < steamParticles.length; i++) {
      var p = steamParticles[i];
      p.age++;
      if (p.age > p.life) {
        p.x = Math.random() * W;
        p.y = H - 80 - Math.random() * 30;
        p.age = 0;
      } else {
        p.y += p.risingSpeed;
        px(p.x, p.y, rgba('#ffffff', p.alpha * (1 - p.age / p.life)));
      }
    }

    // === LAVA FIELD ===
    for (var x = 0; x < W; x++) {
      var lavaHeight = lavaField[x];
      for (var y = lavaHeight - 6; y < lavaHeight; y++) {
        if (y >= 180) {
          px(x, y, '#e63946');
        }
      }
    }

    // === WOODEN WALKWAY ===
    for (var segment of walkwaySegments) {
      rect(segment.x - 3, segment.y, 6, 4, rgba('#264653', 0.8));
      for (var i = -2; i <= 2; i++) {
        px(segment.x + i, segment.y + 2, '#e9c46a');
      }
    }

    // Bottom glow line
    rect(0, H - 1, W, 1, rgba('#48cae4', 0.3));
    rect(0, H - 2, W, 1, rgba('#90e0ef', 0.1));
  };

  function pixelatedWaterShade(x, y, wave) {
    for (var dy = -1; dy <= 1; dy++) {
      for (var dx = -1; dx <= 1; dx++) {
        if (dx === 0 && dy === 0) continue;
        px(x + dx, y + dy + wave, rgba('#ffffff', 0.1));
      }
    }
  }
});