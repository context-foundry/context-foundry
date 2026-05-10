// Scene: Shipping Code from the Abyss
// Mariana Trench, Pacific Ocean
window.CF.register("Shipping Code from the Abyss", "Mariana Trench, Pacific Ocean", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Pre-compute sediment
  var sediment = [];
  var sedimentR = srand(1001);
  for(var x = 0; x < W; x++) {
    sediment[x] = H - 10 + Math.floor(sedimentR() * 5);
  }

  // Pre-compute bioluminescent fish
  var fish = [];
  var fishR = srand(2002);
  for(var i = 0; i < 10; i++){
    fish.push({
      x: fishR() * W,
      y: H - 60 - fishR() * 50,
      size: 2 + Math.floor(fishR() * 3),
      phase: fishR() * Math.PI * 2,
      speed: 0.2 + fishR() * 0.5,
      depth: 100 + fishR() * 80,
      glow: fishR() * 0.5 + 0.5
    });
  }

  // Hydrothermal vent state
  var ventX = Math.floor(W * 0.5);
  var ventY = H - 40;
  var ventPulse = 0;

  return function(t){
    // === BACKGROUND ===
    rect(0, 0, W, H, '#0a1628');

    // === HIMALAYAN WALLS ===
    for(var x = 0; x < W; x++) {
      var wallY = Math.sin(x * 0.02 + t * 0.5) * 10 + H - 100;
      px(x, wallY, lerp('#0d2847', '#1a4a6e', (wallY - (H - 100)) / 40));
    }

    // === ABYSSAL SEDIMENT ===
    for(var x = 0; x < W; x++) {
      for(var y = sediment[x]; y < H; y++) {
        px(x, y, lerp('#0d2847', '#1a4a6e', (y - sediment[x]) / (H - sediment[x])));
      }
    }

    // === HYDROTHERMAL VENT ===
    ventPulse = osc(t, 0.5, 0) * 5;
    circle(ventX, ventY - ventPulse, 10, rgba('#4fb8c4', 0.8 - ventPulse / 40));
    circle(ventX, ventY - ventPulse, 8, '#1a4a6e');

    // === BIOLUMINESCENT FISH ===
    for(var f of fish){
      f.x += Math.sin(t * f.speed + f.phase) * 0.5;
      f.y += Math.sin(t * f.speed + f.phase + Math.PI) * 0.2;

      if(f.x < 0) f.x = W;
      if(f.x > W) f.x = 0;

      if(f.y < H - f.depth) {
        f.y = H - f.depth;
      }

      for(var dx = -f.size; dx <= f.size; dx++) {
        for(var dy = -f.size; dy <= f.size; dy++) {
          if(dx * dx + dy * dy < f.size * f.size) {
            px(f.x + dx, f.y + dy, rgba('#4fb8c4', f.glow));
          }
        }
      }
    }

    // === BOTTOM GLOW LINE ===
    rect(0, H - 1, W, 1, rgba('#4fb8c4', 0.3));
    rect(0, H - 2, W, 1, rgba('#4fb8c4', 0.1));
  };
});