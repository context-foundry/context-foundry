// Scene: Version Control Tree Rings
// Sequoia National Park, California, USA
window.CF.register("Version Control Tree Rings", "Sequoia National Park, California, USA", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Pre-compute growth rings
  var rings = [];
  (function() {
    var baseX = 240, baseY = 130, maxRadius = 80;
    for (var i = 0; i < 15; i++) {
      var radius = (maxRadius / 15) * i;
      rings.push({
        r: radius,
        color: lerp('#6b3a0a', '#dad7cd', i / 15)
      });
    }
  })();

  // Fern carpet particles
  var ferns = [];
  for (var i = 0; i < 100; i++) {
    ferns.push({
      x: Math.random() * W,
      y: H - (Math.random() * 30 + 30),
      sway: Math.random() * Math.PI
    });
  }

  // Giant Tunnel Tree
  var treeTrunkX = 150, treeTrunkY = 100, treeTrunkWidth = 20, treeTrunkHeight = 70;

  return function(t) {
    // === BACKGROUND ===
    rect(0, 0, W, H, rgba('#a3b18a', 1));

    // === DRAW GROWTH RINGS ===
    for (var ring of rings) {
      circle(240, 130, ring.r, rgba(ring.color, 0.5));
    }

    // === DRAW TUNNEL TREE ===
    rect(treeTrunkX, treeTrunkY, treeTrunkWidth, treeTrunkHeight, '#4a2c0a');
    ctx.save();
    ctx.fillStyle = '#6b3a0a';
    ctx.globalAlpha = 0.7;
    ctx.beginPath();
    ctx.moveTo(treeTrunkX, treeTrunkY);
    ctx.lineTo(treeTrunkX + treeTrunkWidth, treeTrunkY);
    ctx.lineTo(treeTrunkX + treeTrunkWidth, treeTrunkY + treeTrunkHeight);
    ctx.lineTo(treeTrunkX, treeTrunkY + treeTrunkHeight);
    ctx.closePath();
    ctx.fill();
    ctx.restore();

    // === DRAW FERN CARPET ===
    for (var fern of ferns) {
      fern.y += Math.sin(t + fern.sway) * 0.2; // Sway effect
      if (fern.y > H) fern.y = H - 30; // Reset fern position
      px(fern.x, fern.y, rgba('#588157', 0.5));
      px(fern.x + 1, fern.y, rgba('#588157', 0.5));
    }

    // === ADD LIGHT AND SHADOW ===
    for (var y = 0; y < H; y++) {
      var brightness = Math.cos(y * Math.PI / H) * 0.2; // Light gradient
      for (var x = 0; x < W; x++) {
        px(x, y, rgba('#dad7cd', brightness));
      }
    }

    // === ADD STARS IN THE SKY ===
    for (var i = 0; i < 10; i++) {
      var starX = Math.random() * W;
      var starY = Math.random() * 40;
      px(starX, starY, rgba('#FFFFFF', Math.random() * 0.9));
    }

    // Bottom glow line
    rect(0, H - 1, W, 1, rgba('#4a2c0a', 0.5));
    rect(0, H - 2, W, 1, rgba('#6b3a0a', 0.2));
  };
});