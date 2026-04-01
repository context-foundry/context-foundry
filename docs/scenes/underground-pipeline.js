// Scene: Underground Pipeline
// Waitomo Glowworm Caves, North Island, New Zealand
window.CF.register("Underground Pipeline", "Waitomo Glowworm Caves, North Island, New Zealand", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,W=api.W,H=api.H;

  // Glowworm particles
  var glowworms=[];
  for(var i=0;i<100;i++){
    glowworms.push({
      x:Math.random()*W, 
      y:Math.random()*H*0.5,
      life:10+Math.random()*20,
      maxLife:0,
      brightness:Math.random()*0.5+0.5
    });
  }

  // Limestone formations
  var formations=[];
  var formationCount = 15;
  var sr=srand(101);
  for(var i=0; i<formationCount; i++){
    formations.push({
      x: Math.random()*W,
      baseHeight: H/2 + sr()*20,
      width: 10 + sr()*30,
      height: 20 + sr()*40,
    });
  }

  return function(t){
    // Background gradient - dark to a lighter top
    for(var y=0; y<H; y++){
      var p = y/H;
      rect(0, y, W, 1, lerp('#0b0c2a', '#1a1a5e', p));
    }

    // Draw limestone formations
    for(var f of formations){
      rect(f.x, H - f.baseHeight, f.width, f.height, '#343a40');
    }

    // Draw underground river
    for(var y=H/2; y<H; y+=3){
      var riverWidth = 20 + Math.sin(y*0.03 + t)*10;
      rect(0, y, W, 2, lerp('#1a1a5e', '#00e5ff', (y - H/2) / (H/2)));
      for(var x = 0; x<W; x+= riverWidth){
        px(x, y, rgba('#00e5ff', 0.6));
      }
    }

    // Draw boat silhouette
    var boatY = H - 70 + Math.sin(t * 1.5) * 5;
    rect(W/2 - 15, boatY, 30, 10, '#343a40'); 
    rect(W/2 - 5, boatY - 5, 10, 5, '#1a1a5e'); 

    // Draw glowworms
    for(var worm of glowworms){
      if(worm.life > 0){
        worm.y -= 0.1; // drifting upwards
        worm.life--;
        px(worm.x, worm.y, rgba('#00e5ff', worm.brightness));
        if(worm.y < 0) {
          worm.x = Math.random() * W;
          worm.y = Math.random() * (H * 0.5);
          worm.life = 10 + Math.random() * 20;
        }
      }
    }
    
    // Draw glowworm galaxy ceiling
    for(var gy = 0; gy < 50; gy++){
      for(var gx = 0; gx < W; gx+=3){
        var a = osc(t, 2 + gx * 0.001, gy) * 0.5;
        if(a > 0.2) {
          px(gx, gy, rgba('#00e5ff', a));
        }
      }
    }

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#00e5ff',0.3));
    rect(0,H-2,W,1,rgba('#00e5ff',0.1));
  };
});