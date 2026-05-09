// Scene: Tidal Bore Race Condition
// Severn Bore, Gloucestershire, England
window.CF.register("Tidal Bore Race Condition", "Severn Bore, Gloucestershire, England", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Define color palette
  var colors = {
    mud: '#6b705c',
    bank: '#a5a58d',
    water: '#0077b6',
    wave: '#48cae4',
    tree: '#b7b7a4'
  };

  // Surfer state
  var surfers = [];
  for(var i = 0; i < 5; i++){
    surfers.push({
      x: Math.random() * W,
      y: H - 50 + Math.random() * 20,
      speed: 0.5 + Math.random() * 1,
      phase: Math.random() * Math.PI * 2
    });
  }

  // Tree state
  var trees = [];
  var treeCount = 15;
  for(var i = 0; i < treeCount; i++){
    trees.push({
      x: Math.random() * (W - 40),
      height: 20 + Math.random() * 40
    });
  }

  return function(t){
    // === SKY ===
    for(var y=0; y<80; y++){
      rect(0,y,W,1,lerp('#00BFFF', '#003366', y / 80));
    }

    // === RIVER ===
    for(var y=80; y<160; y++){
      var col = lerp(colors.water, '#003366', (y - 80) / 80);
      rect(0, y, W, 1, col);
    }

    // === UPSTREAM WAVE WALL ===
    var waveHeight = 30 + Math.sin(t * 2) * 5;
    for(var x = 0; x < W; x++){
      var y = 80 + waveHeight + Math.sin(x * 0.1 + t) * 3;
      px(x, y, colors.wave);
    }

    // === MUDFLAT ===
    for(var y=160; y<H; y++){
      rect(0, y, W, 1, colors.mud);
    }

    // === RIVERBANK TREES ===
    for(var tree of trees){
      for(var h = 0; h < tree.height; h++){
        px(tree.x, H - h - 1, colors.tree);
      }
      px(tree.x, H - tree.height - 1, colors.tree);
      if(tree.height > 30){
        px(tree.x - 1, H - tree.height - 2, colors.tree);
        px(tree.x + 1, H - tree.height - 2, colors.tree);
      }
    }

    // === SURFERS ===
    for(var surfer of surfers){
      surfer.x += Math.sin(t * surfer.speed + surfer.phase) * 0.5;
      if (surfer.x < 0) surfer.x += W;
      if (surfer.x > W) surfer.x -= W;
      var surfY = H - 50 + Math.sin(t * 0.7 + surfer.phase) * 2;
      circle(surfer.x, surfY, 3, '#FFD700'); // Surfer body
      px(surfer.x - 3, surfY + 1, '#000000'); // Board left
      px(surfer.x + 3, surfY + 1, '#000000'); // Board right
    }

    // === Bottom Glow Line ===
    rect(0,H-1,W,1,rgba('#48cae4',0.3));
    rect(0,H-2,W,1,rgba('#0077b6',0.1));
  };
});