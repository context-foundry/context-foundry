// Scene: Penguin Cluster Manager
// South Georgia Island, South Atlantic
window.CF.register("Penguin Cluster Manager", "South Georgia Island, South Atlantic", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Penguin colony positions
  var penguins = [];
  var penguinCount = 30;
  for (var i = 0; i < penguinCount; i++) {
    penguins.push({
      x: Math.random() * W,
      y: H - 50 + Math.random() * 10,
      sway: Math.random() * Math.PI * 2
    });
  }

  // Elephant seals
  var seals = [];
  var sealCount = 6;
  for (var i = 0; i < sealCount; i++) {
    seals.push({
      x: Math.random() * (W - 60) + 30,
      y: H - 10 + Math.random() * 15,
      offset: Math.random() * 0.2
    });
  }

  // Grass tufts
  var grassTufts = [];
  var grassCount = 40;
  for (var i = 0; i < grassCount; i++) {
    grassTufts.push({
      x: Math.random() * W,
      y: H - 30 + Math.random() * 10,
      height: Math.random() * 10 + 5
    });
  }

  return function(t){
    // === BACKGROUND ===
    rect(0, 0, W, H, '#1d1d1d');

    // === SNOWY MOUNTAINS ===
    for (var i = 0; i < W; i++) {
      var mountainHeight = 100 * Math.sin(i * 0.01 + 5) + 40;
      rect(i, H - mountainHeight, 1, mountainHeight, '#f4a261');
    }

    // === PENGUIN COLONY ===
    for (var p of penguins) {
      var pxBase = p.x;
      var pyBase = p.y;

      // Body
      px(pxBase, pyBase, '#ffffff');
      px(pxBase - 1, pyBase + 1, '#ffffff');
      px(pxBase + 1, pyBase + 1, '#ffffff');
      
      // Belly
      px(pxBase, pyBase + 1, '#f4a261');

      // Beak
      px(pxBase, pyBase, '#ff6600');
      
      // Swaying body
      p.y += Math.sin(t * 2 + p.sway) * 0.1;
    }

    // === ELEPHANT SEALS ===
    for (var s of seals) {
      var sxBase = s.x;
      var syBase = s.y + Math.sin(t * 0.5 + s.offset) * 0.1;
      
      // Body
      rect(sxBase, syBase, 15, 5, '#6c757d');

      // Flippers
      rect(sxBase - 3, syBase + 3, 15, 2, '#6c757d');
      
      // Head
      circle(sxBase + 5, syBase - 2, 3, '#6c757d');
    }

    // === TUSSOCK GRASS ===
    for (var g of grassTufts) {
      var baseX = g.x;
      var baseY = g.y;
      for (var h = 0; h < g.height; h++) {
        px(baseX, baseY - h, '#48cae4');
      }
    }

    // === BOTTOM GLOW LINE ===
    rect(0, H - 1, W, 1, rgba('#48cae4', 0.3));
    rect(0, H - 2, W, 1, rgba('#f4a261', 0.1));
  };
});