// Scene: Lunar Landing Page
// Sea of Tranquility, Moon
window.CF.register("Lunar Landing Page", "Sea of Tranquility, Moon", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Boot print particles
  var bootPrints=[];
  for(var i=0;i<10;i++){
    bootPrints.push({x:0,y:0,life:0,maxLife:10});
  }
  function createBootPrint(x,y){
    for(var bp of bootPrints){
      if(bp.life <= 0){
        bp.x = x;
        bp.y = y;
        bp.life = bp.maxLife;
        break;
      }
    }
  }

  // Earth position for twinkling effect
  var earthX = 400, earthY = 50;

  return function(t){
    // Night sky 
    rect(0, 0, W, H, rgba('#0b0c2a', 1));
    
    // Distant Earth
    var earthGlow = 0.3 + osc(t, 5, 0) * 0.2;
    circle(earthX, earthY, 12, rgba('#adb5bd', earthGlow));

    // Lunar surface with subtle craters
    var craterNoise = srand(123);
    for(var x = 0; x < W; x += 15){
      for(var y = H - 60; y < H; y += 15){
        var h = 5 + Math.floor(craterNoise() * 5);
        for(var cy = 0; cy < h; cy++){
          for(var cx = 0; cx < h; cx++){
            if(Math.sqrt(cx * cx + cy * cy) < h){
              px(x + cx, y + cy, rgba('#6c757d', 0.5));
            }
          }
        }
      }
    }

    // Lunar module
    var lmX = W / 2 - 20, lmY = H - 70;
    rect(lmX, lmY, 40, 20, '#495057');
    rect(lmX + 5, lmY - 15, 30, 15, '#343a40'); // Upper part

    // Create boot print on landing module
    createBootPrint(lmX + 10, lmY + 20);

    // Draw boot prints
    for(var bp of bootPrints){
      if(bp.life > 0){
        px(bp.x, bp.y, rgba('#adb5bd', 0.8));
        bp.life--;
      }
    }

    // Create small craters around the scene
    for(var i = 0; i < 5; i++){
      var cx = Math.random() * W;
      var cy = H - 60 - Math.random() * 40;
      for(var r = 0; r < 5; r++){
        for(var angle = 0; angle < Math.PI * 2; angle += 0.1){
          var dx = Math.cos(angle) * 5;
          var dy = Math.sin(angle) * 5;
          px(cx + dx, cy + dy, rgba('#495057', 0.6));
        }
      }
    }

    // Bottom glow line
    rect(0, H - 1, W, 1, rgba('#adb5bd', 0.3));
    rect(0, H - 2, W, 1, rgba('#adb5bd', 0.1));
  };
});