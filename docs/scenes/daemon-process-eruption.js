// Scene: Daemon Process Eruption
// Mount Etna, Sicily, Italy
window.CF.register("Daemon Process Eruption", "Mount Etna, Sicily, Italy", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Lava fountain particles
  var lavaParticles=[];
  for(var i=0;i<100;i++){
    lavaParticles.push({
      x:Math.random() * W/2 + W/4, 
      y:Math.random() * H/2 + H/4,
      vy:-(Math.random() * 2 + 1), 
      vx:(Math.random() - 0.5),
      life:Math.random() * 20 + 20
    });
  }

  // Ash cloud particles
  var ashParticles=[];
  for(var i=0;i<150;i++){
    ashParticles.push({
      x:Math.random() * W, 
      y:Math.random() * H/3,
      vy:-(Math.random() * 0.5 + 0.5), 
      vx:(Math.random() - 0.5) * 2,
      life:Math.random() * 30 + 30
    });
  }

  // Vineyard slopes
  var vineyards = [];
  for(var i=0; i<12; i++){
    vineyards.push({x:50 + i*35, y:H-40 + Math.sin(i * 0.5) * 10});
  }

  return function(t){
    // Background gradient -- dark volcanic landscape
    for(var y=0; y<H; y+=2){
      var p=y/H;
      var col=lerp('#370617', '#495057', p);
      rect(0, y, W, 2, col);
    }

    // Summit crater
    var craterX = W/2;
    var craterY = 50;
    var craterRadius = 40;
    circle(craterX, craterY, craterRadius, rgba('#6a040f', 1));

    // Lava fountain emission
    for(var i=0; i<lavaParticles.length; i++){
      var p = lavaParticles[i];
      if(p.life > 0){
        p.y += p.vy;
        p.x += p.vx;
        p.vy += 0.1; // Gravity effect
        p.life--;
        var lavaColor = '#d00000';
        if(p.life < 20) lavaColor = lerp('#d00000', '#e85d04', 1 - (p.life/20));
        px(p.x, p.y, rgba(lavaColor, 1));
      } else {
        p.x = Math.random() * W/2 + W/4; 
        p.y = Math.random() * H/2 + H/4;
        p.vy = -(Math.random() * 2 + 1); 
        p.vx = (Math.random() - 0.5);
        p.life = Math.random() * 20 + 20;
      }
    }

    // Ash cloud generation
    for(var i=0; i<ashParticles.length; i++){
      var p = ashParticles[i];
      if(p.life > 0){
        p.y += p.vy;
        p.x += p.vx;
        p.life--;
        if(p.y < 0) {
          p.y = H;
          p.x = Math.random() * W;
        }
        px(p.x, p.y, rgba('#d0d0d0', 0.6));
      } else {
        p.x = Math.random() * W; 
        p.y = Math.random() * H/3;
        p.vy = -(Math.random() * 0.5 + 0.5); 
        p.vx = (Math.random() - 0.5) * 2;
        p.life = Math.random() * 30 + 30;
      }
    }

    // Drawing vineyard slopes
    for(var v of vineyards){
      rect(v.x, H-20, 25, 15, rgba('#495057', 0.8));
      rect(v.x+5, H-20, 15, 5, rgba('#6a040f', 1));
    }

    // Bottom glow line
    rect(0, H-1, W, 1, rgba('#e85d04', 0.6));
    rect(0, H-2, W, 1, rgba('#e85d04', 0.3));
  };
});