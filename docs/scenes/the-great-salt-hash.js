// Scene: The Great Salt Hash
// Salar de Uyuni, Bolivia
window.CF.register("The Great Salt Hash", "Salar de Uyuni, Bolivia", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Pre-compute hexagonal salt tiles
  var saltTiles=[];
  for(var x=0;x<W;x+=30){
    for(var y=0;y<H;y+=30){
      saltTiles.push({
        x:x + (y % 60 === 0 ? 15 : 0),
        y:y,
        animationOffset: Math.random() * Math.PI * 2
      });
    }
  }

  // Distant volcano state
  var volcanoX = W - 80, volcanoY = H - 50;

  // Sky gradient colors
  var skyGradientColors = ['#caf0f8', '#ade8f4', '#90e0ef', '#ffffff'];

  return function(t){
    // === SKY ===
    for(var y=0; y < H; y++){
      var p = y / H;
      var col = lerp(skyGradientColors[0], skyGradientColors[skyGradientColors.length - 1], p);
      rect(0, y, W, 1, col);
    }

    // === MIRROR-FLAT SALT ===
    for(var y=H/2; y<H; y+=2){
      var p = (y-H/2)/ (H/2);
      rect(0, y, W, 2, rgba('#ffffff', 0.1 * (1-p)));
    }

    // === DISTANT VOLCANO ===
    for(var dx=-20; dx<=20; dx++){
      for(var dy=-15; dy<=0; dy++){
        if(dx*dx + dy*dy <= 20*20) {
          px(volcanoX + dx, volcanoY + dy, rgba('#3A3B3C', 0.5));
        }
      }
    }

    // === HEXAGONAL SALT TILES ===
    for(var tile of saltTiles){
      var hexHeight = 30 * Math.sin(t + tile.animationOffset) * 0.2 + 15;
      rect(tile.x, tile.y, 30, hexHeight, rgba('#48cae4', 1));
      px(tile.x + 15, tile.y + hexHeight - 1, rgba('#48cae4', 0.4));
    }

    // === REFLECTIVE SURFACE PARTICLES ===
    var particles = [];
    for(var i=0; i<30; i++){
      particles.push({
        x: Math.random() * W,
        y: Math.random() * (H/2) + (H/2),
        vx: (Math.random() - 0.5) * 2,
        vy: -Math.random() * 2,
        life: Math.random() * 40 + 20
      });
    }
    
    for(var p of particles){
      if(p.life > 0){
        px(p.x, p.y, rgba('#ffffff', 0.8));
        p.x += p.vx;
        p.y += p.vy;
        p.vy += 0.05; // gravity
        p.life--;
      }
    }

    // === BOTTOM GLOW LINE ===
    rect(0,H-1,W,1,rgba('#48cae4',0.3));
    rect(0,H-2,W,1,rgba('#90e0ef',0.1));
  };
});