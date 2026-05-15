// Scene: API Gateway to Paradise
// Maldives Overwater Bungalows, North Male Atoll
window.CF.register("API Gateway to Paradise", "Maldives Overwater Bungalows, North Male Atoll", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Pre-computed parameters
  var coral = [];
  var villa = [];
  var particles = [];
  var r = srand(1001);
  
  // Create coral
  for(var i = 0; i < 20; i++){
    coral.push({
      x: r() * W, 
      y: H - 60 + r() * 10, 
      size: 2 + r() * 3
    });
  }
  
  // Create overwater villas
  for(var i = 0; i < 5; i++){
    villa.push({
      baseX: 90 + i * 70, 
      baseY: H - 100, 
      sway: r() * Math.PI * 2
    });
  }

  // Create particles (bubbles)
  for(var i = 0; i < 50; i++){
    particles.push({
      x: r() * W, 
      y: H - 50 + r() * 50, 
      vy: -0.5 - r() * 0.2,
      life: 100 + Math.floor(r() * 100)
    });
  }

  return function(t){
    // === SKY GRADIENT ===
    for(var y = 0; y < H / 2; y++){
      var p = y / (H / 2);
      rect(0, y, W, 1, lerp('#FFB74D', '#FFAB40', p));
    }
    
    // === SUNSET HORIZON ===
    var sunY = 130 + Math.sin(t * 0.4) * 5;
    var sunBrightness = Math.max(0, Math.sin((t - 2) * Math.PI / 3));
    circle(W * 0.75, sunY, 20, rgba('#FFC107', sunBrightness * 0.5));

    // === TRANSPARENT LAGOON ===
    rect(0, H / 2, W, H / 2, rgba('#00b4d8', 0.4));

    // === VILLAS ===
    for(var v of villa){
      var swayX = Math.sin(t * 0.5 + v.sway) * 2;
      rect(v.baseX + swayX, v.baseY, 60, 20, '#FFFFFF'); // Roof
      rect(v.baseX + swayX + 10, v.baseY + 10, 40, 15, '#90e0ef'); // Walls
    }

    // === CORAL ===
    for(var c of coral){
      for(var i = 0; i < c.size; i++){
        px(c.x + i, c.y - 2, '#264653');
        px(c.x + i, c.y, '#dda15e');
      }
    }

    // === BUBBLES ===
    for(var p of particles){
      if(p.life > 0){
        p.y += p.vy;
        p.x += Math.sin(t * 2 + p.x * 0.1) * 0.1;
        if(p.y < 0){
          p.y = H - 1;
          p.x = r() * W;
        }
        var alpha = p.life / 100;
        circle(p.x, p.y, 1.5, rgba('#90e0ef', alpha));
        p.life--;
      }
    }

    // === WATER SURFACE EFFECT ===
    for(var y = H / 2; y < H; y+=2){
      var wave = Math.sin(y * 0.05 + t) * 2;
      rect(0, y, W, 2, rgba('#00b4d8', 0.6 + wave * 0.1));
    }

    // REQUIRED: bottom glow line (brand consistency)
    rect(0,H-1,W,1,rgba('#00b4d8',0.3));
    rect(0,H-2,W,1,rgba('#90e0ef',0.1));
  };
});