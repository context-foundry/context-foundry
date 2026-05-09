// Scene: The Great Firewall
// Great Wall at Jinshanling, Hebei, China
window.CF.register("The Great Firewall", "Great Wall at Jinshanling, Hebei, China", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Initialize persistent state
  var wallPoints = [];
  var towers = [];
  var hills = [];
  var fog = [];
  var r = srand(1234);

  // Pre-compute wall points
  (function() {
    for (var i = 0; i < W; i++) {
      wallPoints.push(Math.sin(i * 0.02) * 15 + 100 + Math.random() * 10);
    }
  })();

  // Pre-compute watchtower positions
  (function() {
    for (var i = 0; i < 5; i++) {
      towers.push({
        x: Math.random() * W,
        y: wallPoints[Math.floor(Math.random() * W)] - 15
      });
    }
  })();

  // Pre-compute hills
  (function() {
    for (var i = 0; i < 10; i++) {
      hills.push({
        x: Math.random() * W,
        height: Math.random() * 30 + 40
      });
    }
  })();

  // Pre-compute fog particles
  (function() {
    for (var i = 0; i < 50; i++) {
      fog.push({
        x: Math.random() * W,
        y: Math.random() * (H - 100),
        alpha: Math.random() * 0.5 + 0.2
      });
    }
  })();

  return function(t) {
    // === SKY GRADIENT ===
    for (var y = 0; y < 80; y++) {
      var p = y / 80;
      rect(0, y, W, 1, lerp('#6c757d', '#e9c46a', p));
    }

    // === MORNING FOG ===
    for (var fp of fog) {
      px(fp.x, fp.y, rgba('#ffffff', fp.alpha));
      // Slight vertical jitter
      fp.y += Math.sin(t * 0.5) * 0.1;
      if (fp.y > H - 100) fp.y = 0; 
    }

    // === DRAW AUTUMN HILLS ===
    for (var hill of hills) {
      rect(hill.x, H - hill.height, 40, hill.height, '#495057');
    }

    // === DRAW THE GREAT WALL ===
    for (var i = 0; i < W; i++) {
      var wallY = wallPoints[i];
      px(i, wallY, '#2d6a4f');
      // Draw bricks
      if (i % 3 === 0) px(i, wallY, '#40916c');
    }

    // === DRAW WATCHTOWERS ===
    for (var tower of towers) {
      rect(tower.x - 2, tower.y, 5, 15, '#494949');
      rect(tower.x - 3, tower.y + 10, 10, 5, '#2d6a4f');
      px(tower.x, tower.y + 17, '#495057');
    }

    // === ADD A BOTTOM GLOW LINE ===
    rect(0, H - 1, W, 1, rgba('#e9c46a', 0.3));
    rect(0, H - 2, W, 1, rgba('#e9c46a', 0.1));
  };
});