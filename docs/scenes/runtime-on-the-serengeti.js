// Scene: Runtime on the Serengeti
// Serengeti National Park, Tanzania
window.CF.register("Runtime on the Serengeti", "Serengeti National Park, Tanzania", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Initialize persistent state here (arrays, pre-computed data)
  var wildebeests = [];
  var grassHeight = 0.6 * H;

  // Create wildebeests
  for (var i = 0; i < 10; i++) {
    wildebeests.push({
      x: Math.random() * 400 + 50,
      y: grassHeight + Math.random() * 30,
      speed: Math.random() * 0.8 + 0.2,
      phase: Math.random() * Math.PI * 2,
      size: Math.floor(Math.random() * 2) + 2
    });
  }

  return function(t){
    // Background gradient for the sky
    for (var y = 0; y < H; y++) {
      var p = y / H;
      rect(0, y, W, 1, lerp('#283618', '#fefae0', p));
    }

    // Distant Kilimanjaro at the horizon
    rect(100, 60, 280, 90, lerp('#606c38', '#fefae0', 0.4));
    rect(150, 40, 180, 40, '#606c38');
    
    // Draw savanna grass
    for (var x = 0; x < W; x += 2) {
      var h = grassHeight + Math.sin(t + x * 0.1) * 3;
      px(x, h, '#bc6c25');
      px(x + 1, h + 1, '#bc6c25');
    }

    // Draw acacia tree silhouette
    function drawAcaciaTree(x, y) {
      var treeHeight = 20;
      for (var i = 0; i < treeHeight; i++) {
        px(x, y - i, '#606c38');
        if (i < treeHeight - 5) {
          px(x - 3, y - i, '#606c38');
          px(x + 3, y - i, '#606c38');
        }
      }
      for (var j = -4; j <= 4; j++) {
        for (var k = -1; k <= 1; k++) {
          px(x + j, y - treeHeight + k, '#606c38');
        }
      }
    }
    drawAcaciaTree(80, grassHeight);

    // Draw wildebeests
    for (var w of wildebeests) {
      w.x += w.speed;
      if (w.x > W) w.x = -10; // Wrap around
      var bob = Math.sin(t * 2 + w.phase) * 2;

      // Body
      for (var dy = 0; dy < w.size; dy++) {
        for (var dx = -w.size; dx <= w.size; dx++) {
          px(w.x + dx, w.y + dy + bob, '#dda15e');
        }
      }
      
      // Head
      px(w.x, w.y - 1 + bob, '#bc6c25');
      px(w.x - 1, w.y - 1 + bob, '#bc6c25');
      
      // Legs
      for (var l = 0; l < 3; l++) {
        px(w.x - 1 + l, w.y + w.size - 1, '#283618');
      }
    }

    // Bottom glow line
    rect(0, H-1, W, 1, rgba('#dda15e', 0.3));
    rect(0, H-2, W, 1, rgba('#bc6c25', 0.1));
  };
});