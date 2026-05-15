// Scene: Read-Only Petrified Forest
// Petrified Forest National Park, Arizona, USA
window.CF.register("Read-Only Petrified Forest", "Petrified Forest National Park, Arizona, USA", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,W=api.W,H=api.H;

  // Initialize persistent state for crystals and logs
  var logs = [];
  var crystals = [];
  var stripes = [];
  var logCount = 10;
  var crystalCount = 20;
  var stripeCount = 30;

  var rand = srand(0);
  for (var i = 0; i < logCount; i++) {
    logs.push({
      x: rand() * W,
      y: H - 70 - rand() * 50,
      width: 8 + rand() * 12,
      height: 5 + rand() * 15,
      color: rgba('#e76f51', rand() * 0.8 + 0.2)
    });
  }

  for (var i = 0; i < crystalCount; i++) {
    crystals.push({
      x: rand() * W,
      y: H - 90 - rand() * 20,
      size: 5 + rand() * 5,
      color: rgba('#c9ada7', rand() * 0.6 + 0.1)
    });
  }

  for (var i = 0; i < stripeCount; i++) {
    stripes.push({
      x: rand() * W,
      y: H - 40 - rand() * 80,
      width: 20 + rand() * 30,
      height: 3 + rand() * 7,
      color: '#' + Math.floor(Math.random() * 16777215).toString(16) // random color
    });
  }

  return function(t) {
    // Background - Desert Gradient
    for (var y = 0; y < H; y++) {
      var p = y / H;
      rect(0, y, W, 1, lerp('#264653', '#f4a261', p));
    }

    // Draw Painted Desert Stripes
    for (var s of stripes) {
      rect(s.x, s.y, s.width, s.height, s.color);
    }

    // Draw Petrified Logs
    for (var log of logs) {
      rect(log.x, log.y, log.width, log.height, log.color);
      // Adding some additional texture
      for (var j = 0; j < 5; j++) {
        px(log.x + rand() * log.width, log.y + rand() * log.height, '#666');
      }
    }

    // Draw Crystal Cross-Sections
    for (var crystal of crystals) {
      for (var i = 0; i < 6; i++) {
        circle(crystal.x + rand() * crystal.size, crystal.y + rand() * crystal.size, crystal.size, crystal.color);
      }
    }

    // Draw Badlands Terrain
    for (var y = H - 50; y < H; y += 2) {
      for (var x = 0; x < W; x++) {
        var terrainHeight = 5 + Math.sin((x + t * 20) * 0.05) * 2;
        px(x, y, lerp('#9a8c98', '#c9ada7', (y - (H - 50)) / 50));
        if (y > H - 60) 
          px(x, y, rgba('#5c4551', 0.2 + Math.random() * 0.3));
        if (y === H - 50) 
          px(x, y - terrainHeight, '#e76f51');
      }
    }

    // Bottom glow line for atmosphere
    rect(0, H - 1, W, 1, rgba('#e76f51', 0.3));
    rect(0, H - 2, W, 1, rgba('#264653', 0.2));
  };
});