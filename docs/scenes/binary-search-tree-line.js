// Scene: Binary Search Treeline
// Dolomites, South Tyrol, Italy
window.CF.register("Binary Search Treeline", "Dolomites, South Tyrol, Italy", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Pre-compute wildflower positions
  var flowers = [];
  var flowerCount = 100;
  var flowerRng = srand(1001);
  for (var i = 0; i < flowerCount; i++) {
    flowers.push({
      x: flowerRng() * W,
      y: H - 70 + flowerRng() * 30,
      size: 1 + flowerRng() * 2,
      sway: flowerRng() * Math.PI * 2
    });
  }

  // Pre-compute mountain peak positions
  var peaks = [];
  var peakCount = 5;
  var peakRng = srand(1002);
  for (var i = 0; i < peakCount; i++) {
    peaks.push({
      x: (i + 1) * (W / (peakCount + 1)),
      height: 20 + peakRng() * (H / 4)
    });
  }

  // Hut position and animation variables
  var hutX = W * 0.5 - 15, hutY = H - 90;
  var smokeParticles = [];
  var smokeCount = 10;
  for (var i = 0; i < smokeCount; i++) {
    smokeParticles.push({
      x: hutX + 15,
      y: hutY - 10,
      vy: -(0.1 + Math.random() * 0.05),
      life: 0
    });
  }

  return function(t) {
    // === SKY GRADIENT ===
    for (var y = 0; y < H; y++) {
      var col = lerp('#e9ecef', '#a3b18a', y / H);
      rect(0, y, W, 1, col);
    }

    // === MOUNTAIN PEAKS ===
    for (var p of peaks) {
      for (var y = H - 50; y > H - p.height; y--) {
        px(p.x, y, '#264653');
        px(p.x + 1, y, '#264653');
        px(p.x - 1, y, '#264653');
      }
    }

    // === ALPINE TREELINE ===
    for (var i = 0; i < W; i++) {
      var h = Math.sin(i * 0.02 + t) * 5 + H - 70;
      px(i, h, '#588157');
    }

    // === ROCKY BASE ===
    rect(0, H - 50, W, 50, '#adb5bd');

    // === MOUNTAIN HUT ===
    rect(hutX, hutY, 30, 20, '#8B4513');
    rect(hutX + 10, hutY - 10, 10, 10, '#FFD700'); // Hut roof

    // === SMOKE ANIMATION ===
    for (var s of smokeParticles) {
      if (s.life > 0) {
        s.y += s.vy;
        s.life--;
        var alpha = s.life / 20;
        px(s.x, s.y, rgba('#ffffff', alpha));
      }
      if (s.life <= 0 && Math.random() > 0.95) {
        s.life = 20 + Math.random() * 30; // Reset smoke life
        s.y = hutY - 10; // Reset smoke position
      }
    }

    // === WILDFLOWER SLOPE ===
    for (var f of flowers) {
      px(f.x, f.y, '#e9ecef'); // Draw flower base
      px(f.x, f.y - 1, '#FFC0CB'); // Draw flower top
      f.x += Math.sin(t + f.sway) * 0.1; // Sway effect
      if (f.x < 0) f.x = W;
      else if (f.x > W) f.x = 0;
    }

    // REQUIRED: bottom glow line (brand consistency)
    rect(0,H-1,W,1,rgba('#264653',0.3));
    rect(0,H-2,W,1,rgba('#588157',0.1));
  };
});