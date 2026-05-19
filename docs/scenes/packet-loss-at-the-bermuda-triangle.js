// Scene: Packet Loss at the Bermuda Triangle
// Bermuda Triangle, North Atlantic Ocean
window.CF.register("Packet Loss at the Bermuda Triangle", "Bermuda Triangle, North Atlantic Ocean", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Initialize persistent state here (arrays, pre-computed data)
  var shipX = 240, shipY = 140; // Position of abandoned ship
  var compassAngle = 0; // Spinning compass angle

  // Pre-compute storm clouds
  var clouds = [];
  (function(){
    var r = srand(1001);
    for (var i = 0; i < 15; i++) {
      clouds.push({
        x: r() * W,
        y: r() * 60 + 30,
        drift: r() * 0.1
      });
    }
  })();

  // Return function for drawing each frame
  return function(t) {
    // === OCEAN BACKGROUND ===
    rect(0, 0, W, H, rgba('#0077b6', 0.9));

    // === DEEP TRENCH ===
    for (var y = 130; y < H; y++) {
      var p = (y - 130) / (H - 130);
      px(240, y, lerp('#0096c7', '#6c757d', p));
      if (p > 0.5) {
        px(240 + Math.floor(Math.sin(y * 0.05) * 15), y, rgba('#343a40', p * 0.2));
      }
    }

    // === STORM CLOUDS ===
    for (var cloud of clouds) {
      var shadow = (Math.sin(t * 0.7 + cloud.x) + 1) * 0.5;
      for (var dx = -20; dx <= 20; dx++) {
        for (var dy = -5; dy <= 5; dy++) {
          px(cloud.x + dx, cloud.y + dy, rgba('#343a40', shadow * 0.5));
        }
      }
      cloud.x += cloud.drift;
      if (cloud.x > W) cloud.x = -20;
    }

    // === ABANDONED SHIP ===
    function drawShip(x, y) {
      rect(x - 10, y, 20, 5, '#6c757d');
      rect(x - 12, y + 5, 24, 4, '#343a40');
      rect(x - 8, y + 9, 16, 6, '#6c757d');
      rect(x - 6, y + 15, 12, 2, '#343a40');
    }
    drawShip(shipX, shipY);

    // === COMPASS ===
    ctx.save();
    ctx.translate(60, 60);
    ctx.rotate(compassAngle);
    ctx.fillStyle = '#023e8a';
    circle(0, 0, 15, '#0096c7');
    for (var i = 0; i < 4; i++) {
      var angle = i * Math.PI / 2;
      px(Math.cos(angle) * 12, Math.sin(angle) * 12, '#023e8a');
    }
    ctx.restore();
    
    // Increment compass angle for spinning effect
    compassAngle += 0.05;

    // === HORIZON LIGHT ===
    for (var y = 120; y < 130; y++) {
      var a = (y - 120) / 10;
      rect(0, y, W, 1, rgba('#0077b6', a * 0.3));
    }

    // === BOTTOM GLOW LINE ===
    rect(0, H - 1, W, 1, rgba('#343a40', 0.3));
    rect(0, H - 2, W, 1, rgba('#6c757d', 0.2));
  };
});