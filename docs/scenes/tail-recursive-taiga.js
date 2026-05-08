// Scene: Tail Recursive Taiga
// Taiga Forest, Yakutia, Siberia, Russia
window.CF.register("Tail Recursive Taiga", "Taiga Forest, Yakutia, Siberia, Russia", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Pre-compute spruce tree positions
  var spruces = [];
  var r = srand(1001);
  for (var i = 0; i < W; i += 24) {
    spruces.push({
      x: i,
      height: 40 + Math.floor(r() * 20),
      sway: r() * 0.5
    });
  }

  // Snow particle array
  var snowflakes = [];
  for (var i = 0; i < 100; i++) {
    snowflakes.push({
      x: Math.random() * W,
      y: Math.random() * H,
      vy: 0.5 + Math.random() * 1.2,
      alpha: 0.1 + Math.random() * 0.3
    });
  }

  // Lynx tracks
  var tracks = [];
  for (var i = 0; i < 10; i++) {
    tracks.push({
      x: Math.random() * (W - 100) + 50,
      y: H - 20 - Math.random() * 10
    });
  }

  return function(t) {
    // === BACKGROUND SKY ===
    rect(0, 0, W, H, rgba('#e9ecef', 1));

    // === FOREST GROUND ===
    rect(0, H - 50, W, 50, rgba('#adb5bd', 1));

    // === FROZEN STREAM ===
    rect(0, H - 40, W, 10, rgba('#344e41', 0.6));
    
    // === SPRUCES ===
    for (var tree of spruces) {
      var swayAmount = Math.sin(t * 0.5 + tree.sway) * 2;
      // Draw spruce tree
      for (var h = 0; h < tree.height; h++) {
        px(tree.x + swayAmount, H - 50 - h, '#3a5a40');
        if (h > tree.height - 10) {
          px(tree.x + swayAmount, H - 50 - h, '#588157'); // Dusted snow at top
        }
      }
      // Ground shadow
      px(tree.x + swayAmount, H - 40, rgba('#344e41', 0.6));
    }

    // === SNOW PARTICLES ===
    for (var flake of snowflakes) {
      flake.y += flake.vy;
      flake.x += (Math.sin(t * 0.5 + flake.x) * 0.2);
      if (flake.y > H) {
        flake.y = -5;
        flake.x = Math.random() * W;
      }
      px(flake.x, flake.y, rgba('#ffffff', flake.alpha));
    }

    // === LYNX TRACKS ===
    for (var track of tracks) {
      for (var dx = -2; dx <= 2; dx++) {
        for (var dy = -2; dy <= 0; dy++) {
          px(track.x + dx, track.y + dy, '#3a5a40');
        }
      }
    }

    // === BOTTOM GLOW LINE ===
    rect(0, H - 1, W, 1, rgba('#588157', 0.3));
    rect(0, H - 2, W, 1, rgba('#344e41', 0.1));
  };
});