// Scene: Dead Code Elimination Forest
// Hoia Baciu Forest, Cluj-Napoca, Romania
window.CF.register("Dead Code Elimination Forest", "Hoia Baciu Forest, Cluj-Napoca, Romania", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,W=api.W,H=api.H;

  // Twisted tree trunks and canopy positions
  var trees = [];
  const numTrees = 10;
  for (var i = 0; i < numTrees; i++) {
    trees.push({
      x: Math.random() * W,
      height: 30 + Math.random() * 50,
      sway: Math.random() * 5 + 2,
      offset: Math.random() * Math.PI * 2
    });
  }

  // Clearing circle
  var clearingCenterX = W / 2;
  var clearingCenterY = H / 2;
  var clearingRadius = 40;

  // Fog particles
  var fogParticles = [];
  for (var i = 0; i < 20; i++) {
    fogParticles.push({
      x: Math.random() * W,
      y: Math.random() * H,
      alpha: 0.05 + Math.random() * 0.15
    });
  }

  return function(t) {
    // Background gradient representing fog
    for (var y = 0; y < H; y++) {
      var p = y / H;
      var col = lerp('#0d1117', '#343a40', p);
      rect(0, y, W, 1, col);
    }

    // Clearing circle
    for (var dy = -clearingRadius; dy <= clearingRadius; dy++) {
      for (var dx = -clearingRadius; dx <= clearingRadius; dx++) {
        if (dx * dx + dy * dy <= clearingRadius * clearingRadius) {
          px(clearingCenterX + dx, clearingCenterY + dy, rgba('#f0f0f0', 0.2));
        }
      }
    }

    // Draw trees
    for (var tree of trees) {
      var swayAmount = Math.sin(t * tree.sway + tree.offset) * 3;
      var baseX = tree.x;
      var baseY = H - 30; // Base height of trees

      // Draw trunk
      rect(baseX - 2, baseY - tree.height, 4, tree.height, '#495057');

      // Draw canopy
      var canopyY = baseY - tree.height - Math.sin(t * 0.5 + tree.offset) * 2;
      var canopyRadius = 10 + Math.random() * 10;
      for (var dy = -canopyRadius; dy <= canopyRadius; dy++) {
        for (var dx = -canopyRadius; dx <= canopyRadius; dx++) {
          if (dx * dx + dy * dy <= canopyRadius * canopyRadius) {
            px(baseX + dx + swayAmount, canopyY + dy, rgba('#2d6a4f', 0.7));
          }
        }
      }
    }

    // Fog animation
    for (var fog of fogParticles) {
      fog.x += (Math.random() - 0.5) * 2; // Slight horizontal movement
      fog.y += 0.5; // Slight vertical movement
      if (fog.y > H) {
        fog.y = Math.random() * H;
        fog.x = Math.random() * W;
      }
      px(fog.x, fog.y, rgba('#ffffff', fog.alpha));
    }

    // Eerie ambiance -- additional fog layer
    for (var y = 0; y < H; y += 2) {
      for (var x = 0; x < W; x += 2) {
        if (Math.random() < 0.01) {
          px(x + Math.random() * 2, y + Math.random() * 2, rgba('#ffffff', 0.1));
        }
      }
    }

    // Bottom glow line (brand consistency)
    rect(0, H - 1, W, 1, rgba('#1b4332', 0.3));
    rect(0, H - 2, W, 1, rgba('#1b4332', 0.1));
  };
});