// Scene: Syntax Highlighting: Northern Lights
// Abisko, Swedish Lapland, Sweden
window.CF.register("Syntax Highlighting: Northern Lights", "Abisko, Swedish Lapland, Sweden", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Auroras
  var auroras = [];
  for(var i = 0; i < 5; i++){
    auroras.push({
      y: Math.random() * 50,
      phase: Math.random() * Math.PI * 2,
      amplitude: 40 + Math.random() * 30
    });
  }

  // Frozen lake sparkle
  var lakeSparkles = [];
  for(var i = 0; i < 50; i++){
    lakeSparkles.push({
      x: Math.random() * W,
      y: H - 10 + Math.random() * 5,
      alpha: 0.2 + Math.random() * 0.3,
      life: Math.floor(Math.random() * 20) + 10
    });
  }

  // Birch trees
  var birchTrees = [];
  for (var i = 0; i < 10; i++) {
    var x = Math.random() * W;
    birchTrees.push({
      x: x, 
      height: 30 + Math.random() * 20, 
      sway: Math.sin(Math.random() * Math.PI * 2)
    });
  }

  // Sami tent
  var tentPosX = W * 0.5 - 15;
  
  return function(t){
    // === BACKGROUND ===
    rect(0, 0, W, H, '#0b0c2a');

    // === AURORAS ===
    for (var aurora of auroras) {
      for (var x = 0; x < W; x++) {
        var intensity = Math.sin((x / W) * Math.PI * 2 + aurora.phase) * aurora.amplitude;
        var y = H/2 + aurora.y - intensity;
        if (y > 0) {
          px(x, y, '#00ff87');
          px(x, y + 1, '#0b0c2a');
        }
      }
      aurora.phase += 0.005; // Animate the aurora phase
    }

    // === FROZEN LAKE ===
    for (var x = 0; x < W; x++) {
      var lakeY = H - 10 + Math.sin(t * 2 + x * 0.1) * 2;
      for (var y = lakeY; y < H; y++) {
        px(x, y, '#caf0f8');
      }
    }

    // === BIRCH TREES ===
    for (var tree of birchTrees) {
      var swayAmount = Math.sin(t * 2 + tree.x) * 2;
      rect(tree.x, H - tree.height - swayAmount, 5, tree.height, '#ffffff');
      rect(tree.x + 1, H - tree.height - swayAmount, 3, tree.height, '#7b2ff7');
    }

    // === SAMI TENT ===
    rect(tentPosX, H - 30, 30, 5, '#ff006e');
    rect(tentPosX - 5, H - 30, 5, 15, '#ff006e');
    rect(tentPosX + 30, H - 30, 5, 15, '#ff006e');

    // === LAKE SPARKLES ===
    for (var sparkle of lakeSparkles) {
      if (sparkle.life > 0) {
        px(sparkle.x, sparkle.y, rgba('#ffffff', sparkle.alpha));
        sparkle.life--;
      } else {
        sparkle.x = Math.random() * W;
        sparkle.y = H - 10 + Math.random() * 5;
        sparkle.life = Math.floor(Math.random() * 20) + 10;
      }
    }

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#00ff87',0.3));
    rect(0,H-2,W,1,rgba('#00ff87',0.1));
  };
});