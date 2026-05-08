// Scene: Infinite Loop Atoll
// Bora Bora, French Polynesia
window.CF.register("Infinite Loop Atoll", "Bora Bora, French Polynesia", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Initialize reef and bungalow positions
  var bungalows = [];
  for (var i = 0; i < 5; i++) {
    bungalows.push({
      x: 90 + i * 60 + Math.sin(i * 0.5) * 10,
      y: H / 2 + 40 + Math.cos(i * 0.5) * 10,
      width: 8,
      height: 12,
      sway: Math.random() * 1.5
    });
  }

  // Water particles for the lagoon
  var waterParticles = [];
  for (var i = 0; i < 100; i++) {
    waterParticles.push({
      x: Math.random() * W,
      y: Math.random() * H / 2,
      vx: (Math.random() - 0.5) * 2,
      vy: Math.random() * 0.5 - 0.5,
      life: 0
    });
  }

  function emitWaterParticle(lagoonX, lagoonY) {
    for (var p of waterParticles) {
      if (p.life <= 0) {
        p.x = lagoonX + (Math.random() - 0.5) * 20;
        p.y = lagoonY + Math.random() * 20;
        p.vx = (Math.random() - 0.5) * 1.5;
        p.vy = -Math.random() * 2 - 1;
        p.life = 20 + Math.random() * 40;
        break;
      }
    }
  }

  return function(t) {
    // Draw the gradient background for the sky
    for (var y = 0; y < H; y += 2) {
      var p = y / H;
      var col = lerp('#00b4d8', '#90e0ef', p);
      rect(0, y, W, 2, col);
    }

    // Lagoon
    var lagoonY = H / 2 + 20;
    rect(0, lagoonY, W, H - lagoonY, rgba('#52b788', 0.9));

    // Ring-shaped reef
    var reefY = H / 2 + 10;
    for (var angle = 0; angle < 360; angle += 10) {
      var rad = angle * Math.PI / 180;
      var x = W / 2 + Math.cos(rad) * 120;
      var y = reefY + Math.sin(rad) * 120;
      px(x, y, '#264653');
    }

    // Draw Mount Otemanu
    var peakX = W / 2;
    var peakY = H / 4;
    rect(peakX - 20, peakY, 40, H - peakY, '#dda15e');
    rect(peakX - 7, peakY - 10, 14, 10, '#264653');

    // Draw overwater bungalows
    for (var bungalow of bungalows) {
      rect(bungalow.x, bungalow.y, bungalow.width, bungalow.height, '#dda15e');
      rect(bungalow.x, bungalow.y - 2, bungalow.width, 2, rgba('#264653', 0.5));
      bungalow.x += Math.sin(t + bungalow.sway) * 0.1; // Bungalow sway
    }

    // Emit water particles into the lagoon
    if (Math.random() < 0.1) emitWaterParticle(W / 2, lagoonY);

    // Update and draw water particles
    for (var p of waterParticles) {
      if (p.life > 0) {
        p.x += p.vx;
        p.y += p.vy;
        p.life--;
        var a = p.life / 20;
        px(p.x, p.y, rgba('#90e0ef', a * 0.5));
        if (p.life <= 0) {
          p.x = Math.random() * W;
          p.y = Math.random() * (H / 2);
        }
      }
    }

    // Bottom glow line
    rect(0, H - 1, W, 1, rgba('#52b788', 0.3));
    rect(0, H - 2, W, 1, rgba('#52b788', 0.1));
  };
});