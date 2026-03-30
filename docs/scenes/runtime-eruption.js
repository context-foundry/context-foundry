// Scene: Runtime Eruption
// Kilauea, Big Island, Hawaii, USA
window.CF.register("Runtime Eruption", "Kilauea, Big Island, Hawaii, USA", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Lava flow simulation
  var lavaFlow = [];
  for(var i=0;i<50;i++){
    lavaFlow.push({
      x:Math.random()*W, 
      y:H-50-Math.random()*30, 
      vy:Math.random()*0.1+0.2, 
      w:Math.random()*30+5
    });
  }

  // Steam plume particles
  var steamPlume = [];
  for(var i=0;i<20;i++){
    steamPlume.push({
      x:Math.random()*W,
      y:H-120-Math.random()*20, 
      vy:Math.random()*0.1+0.1, 
      life:Math.floor(Math.random()*30)+20
    });
  }

  // Glowing fissure state
  var fissureFrames = 5;
  var fissureGlow = [];
  for(var i=0; i<fissureFrames; i++){
    fissureGlow.push({
      phase: Math.random()*Math.PI*2,
      size: Math.random()*5 + 5,
      brightness: Math.random()*0.3 + 0.5
    });
  }

  return function(t){
    // === SKY ===
    rect(0, 0, W, H*0.5, rgba('#1d1d1d', 1));
    
    // === OCEAN ===
    rect(0, H*0.5, W, H*0.5, rgba('#0d0d0d', 1));

    // === LAVA FLOW ===
    for(var lava of lavaFlow){
      lava.y += lava.vy;
      if(lava.y > H){
        lava.y = H-50-Math.random()*30;
        lava.x = Math.random() * W;
      }
      rect(lava.x, lava.y, lava.w, 2, rgba('#d00000', 1));
    }

    // === STEAM PLUMES ===
    for(var s of steamPlume){
      if(s.life > 0){
        s.life--;
        s.y -= s.vy;
        px(s.x, s.y, rgba('#faa307', 0.1));
        for(var d=-3; d<=3; d++){
          px(s.x+d, s.y, rgba('#faa307', 0.05));
        }
      } else {
        s.x = Math.random() * W;
        s.y = H - 120 - Math.random() * 20;
        s.life = Math.floor(Math.random() * 30) + 20;
      }
    }

    // === GLOWING FISSURE ===
    for(var i=0; i<fissureFrames; i++){
      var f = fissureGlow[i];
      var xOffset = Math.sin(t + f.phase) * 10;
      var yOffset = Math.sin(t - f.phase) * 5;
      rect(240 + xOffset, H-30 + yOffset, f.size, 2, rgba('#e85d04', f.brightness));
    }
    
    // === BLACK BASALT COAST ===
    rect(0, H - 20, W, 20, rgba('#370617', 1));

    // === BOTTOM GLOW LINE ===
    rect(0,H-1,W,1,rgba('#e85d04',0.3));
    rect(0,H-2,W,1,rgba('#d00000',0.1));
  };
});
