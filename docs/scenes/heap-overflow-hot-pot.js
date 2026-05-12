// Scene: Heap Overflow Hot Pot
// Boiling Lake, Dominica
window.CF.register("Heap Overflow Hot Pot", "Boiling Lake, Dominica", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Volcanic crater rim
  var craterHeight = 40;
  var craterWidth = 160;
  
  // Boiling lake surface
  var bubbles = [];
  for (var i = 0; i < 50; i++) {
    bubbles.push({
      x: Math.random() * W,
      y: H - craterHeight + Math.random() * 20,
      size: Math.random() * 3 + 2,
      life: Math.random() * 10 + 5
    });
  }

  // Steam cloud particles
  var steamClouds = [];
  for (var i = 0; i < 20; i++) {
    steamClouds.push({
      x: Math.random() * W,
      y: H - craterHeight - 10 + Math.random() * 20,
      vx: (Math.random() - 0.5) * 0.5,
      vy: -Math.random() * 1 - 1,
      alpha: Math.random() * 0.4 + 0.3
    });
  }

  // Jungle approach trail
  var trailPoints = [];
  for (var i = 0; i < 10; i++) {
    trailPoints.push({ x: Math.random() * (W - 40) + 20, y: H - 60 + i * 8 });
  }

  return function(t){
    // === GRADIENT BACKGROUND ===
    for (var y = 0; y < H; y += 2) {
      var p = y / H;
      var col = lerp('#6c757d', '#adb5bd', p);
      rect(0, y, W, 2, col);
    }

    // === CRATER RIM ===
    rect(70, H - craterHeight, craterWidth, craterHeight, '#2d6a4f');
    for (var x = 70; x < 70 + craterWidth; x++) {
      px(x, H - craterHeight + Math.sin((x - 70) * 0.1) * 5, '#adb5bd');
    }

    // === BOILING LAKE ===
    rect(70, H - craterHeight + 10, craterWidth, 20, '#48cae4');
    
    // === BUBBLE ANIMATION ===
    for (var b of bubbles) {
      b.y -= 0.1; // bubbles float up
      if (b.y < H - craterHeight) b.y = H - craterHeight + Math.random() * 10;
      for (var j = 0; j < 3; j++) {
        circle(b.x + (Math.random() - 0.5) * b.size, b.y, b.size, rgba('#ffffff', 0.2));
      }
    }

    // === STEAM CLOUDS ===
    for (var cloud of steamClouds) {
      cloud.x += cloud.vx;
      cloud.y += cloud.vy;
      cloud.alpha = Math.max(cloud.alpha - 0.01, 0);
      if (cloud.y < 0 || cloud.alpha <= 0) {
        cloud.x = Math.random() * W;
        cloud.y = H - craterHeight - 10 + Math.random() * 20;
        cloud.vx = (Math.random() - 0.5) * 0.5;
        cloud.vy = -Math.random() * 1 - 1;
        cloud.alpha = Math.random() * 0.4 + 0.3;
      }
      circle(cloud.x, cloud.y, 3, rgba('#ffffff', cloud.alpha));
    }

    // === JUNGLE APPROACH TRAIL ===
    for (var point of trailPoints) {
      rect(point.x, point.y, 4, 4, '#adb5bd');
    }

    // === BOTTOM GLOW LINE ===
    rect(0, H - 1, W, 1, rgba('#e9ecef', 0.3));
    rect(0, H - 2, W, 1, rgba('#e9ecef', 0.1));
  };
});