// Scene: Dry Run Only
// Atacama Desert, Chile
window.CF.register("Dry Run Only", "Atacama Desert, Chile", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,W=api.W,H=api.H;

  // Initialize flamingos and terrain particles
  var flamingos=[];
  for(var i=0;i<5;i++){
    flamingos.push({x:Math.random()*W,y:H-70+Math.random()*20, phase:Math.random()*2*Math.PI});
  }
  var terrainParticles=[];
  var sr=srand(101);
  for(var i=0;i<100;i++){
    terrainParticles.push({x:sr()*W, y:H-20+sr()*40, size:1+sr()*2});
  }

  return function(t){
    // Sky gradient from deep blue to light orange
    for(var y=0;y<H;y++){
      var p=y/H;
      rect(0,y,W,1,lerp('#22223b', '#f2e9e4', p));
    }

    // Mars-like terrain
    for(var x=0; x<W; x++){
      var height = Math.sin(x * 0.04) * 20 + (H-50);
      rect(x, height, 1, H - height, lerp('#9a8c98', '#4a4e69', 0.5 + Math.sin(t * 0.1 + x * 0.05) * 0.1));
    }

    // Draw particles for terrain texture
    for(var p of terrainParticles){
      px(p.x, p.y, rgba('#c9ada7', 0.4));
      p.y += Math.sin(t * 0.1 + p.x * 0.05) * 0.1; // slight upward movement to simulate wind
      p.x += (Math.random() - 0.5) * 2; // random sideways drift
      if(p.x < 0 || p.x > W || p.y < 0 || p.y > H) {
        p.x = sr() * W;
        p.y = H - 20 + sr() * 40;
      }
    }
    
    // Flamingos at the salt lake
    for(var f of flamingos){
      // Flamingo body
      var fSize = 4;
      for(var dx=-fSize; dx<=fSize; dx++){
        for(var dy=-fSize; dy<=fSize; dy++){
          if(dx*dx+dy*dy<=fSize*fSize){
            px(f.x+dx, f.y+dy, '#f2e9e4');
          }
        }
      }
      // Flamingo neck
      for(var neck=0; neck<5; neck++){
        px(f.x, f.y-neck, '#9a8c98');
      }
      f.phase += 0.1; // subtle movement
      f.x += Math.sin(f.phase) * 0.2; // sideways bobbing
      if(f.x < 0) f.x = W;
      if(f.x > W) f.x = 0;
    }

    // Observatory domes in the distance
    var observatories = [[W / 4, H - 80], [3 * W / 4, H - 85], [W / 2, H - 75]];
    for(var o of observatories){
      var domeX = o[0];
      var domeY = o[1];
      circle(domeX, domeY, 10, '#c9ada7');
      rect(domeX - 12, domeY, 24, 6, '#9a8c98');
      rect(domeX - 2, domeY - 10, 4, 10, '#4a4e69');
    }

    // Shooting stars
    if(Math.random() < 0.05){
      var starX = Math.random() * W;
      var starY = Math.random() * H / 2;
      for(var i=0; i<3; i++){
        px(starX - i, starY + i, '#f2e9e4');
      }
    }

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#f2e9e4',0.3));
    rect(0,H-2,W,1,rgba('#f2e9e4',0.1));
  };
});