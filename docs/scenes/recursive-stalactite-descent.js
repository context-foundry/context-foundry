// Scene: Recursive Stalactite Descent
// Lechuguilla Cave, Carlsbad, New Mexico, USA
window.CF.register("Recursive Stalactite Descent", "Lechuguilla Cave, Carlsbad, New Mexico, USA", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Gypsum formations and chandelier parameters
  var stalactites = [], chandeliers = [];
  var maxStalactites = 30, chandelierCount = 5;

  for(var i=0; i<maxStalactites; i++) {
    stalactites.push({
      x: Math.random() * W,
      y: Math.random() * H / 2,
      length: 5 + Math.random() * 30
    });
  }
  
  for(var i=0; i<chandelierCount; i++) {
    chandeliers.push({
      x: Math.random() * (W - 40) + 20,
      y: Math.random() * 30 + 30,
      size: 8 + Math.random() * 12
    });
  }

  // Pool parameters
  var poolY = H - 40, poolWidth = W * 0.8;
  var reflections = [];
  for (var i = 0; i < 15; i++) {
    reflections.push({ x: Math.random() * poolWidth + (W - poolWidth) / 2, y: poolY + Math.random() * 10 - 10 });
  }

  return function(t) {
    // Background gradient (dark cave walls)
    for(var y = 0; y < H; y++) {
      var col = lerp('#343a40', '#6c757d', y / H);
      rect(0, y, W, 1, col);
    }

    // Draw stalactites
    for (var stalagmite of stalactites) {
      var stalactiteX = stalagmite.x;
      for (var length = 0; length < stalagmite.length; length++) {
        var drawY = stalagmite.y + length;
        var color = '#f4a261';
        px(stalactiteX, drawY, color);
      }
    }

    // Draw chandeliers
    for (var chandelier of chandeliers) {
      var chandX = chandelier.x;
      var chandY = chandelier.y;
      circle(chandX, chandY, chandelier.size, '#e9c46a');
      circle(chandX, chandY, chandelier.size - 2, '#ffffff');
    }

    // Draw reflections in the pool
    for (var reflection of reflections) {
      var poolRefX = reflection.x;
      var poolRefY = reflection.y;
      px(poolRefX, poolRefY, rgba('#ffffff', 0.3));
      if (Math.random() > 0.5) {
        px(poolRefX + 1, poolRefY + 1, rgba('#e9c46a', 0.2));
      }
    }

    // Draw the pool
    rect((W - poolWidth) / 2, poolY, poolWidth, 40, rgba('#2f3542', 0.7));
    rect((W - poolWidth) / 2 + 5, poolY + 5, poolWidth - 10, 30, rgba('#4f545c', 0.9));

    // Animate stalactites
    for (var stalagmite of stalactites) {
      stalagmite.y += Math.sin(t) * 0.1;
      if (stalagmite.y > H / 2) stalagmite.y = (H / 2) - stalagmite.length;
      if (stalagmite.y < 0) stalagmite.y = 0;
    }

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#f4a261',0.3));
    rect(0,H-2,W,1,rgba('#f4a261',0.1));
  };
});