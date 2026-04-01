// Scene: Singleton Peak
// Mount Fuji, Shizuoka, Japan
window.CF.register("Singleton Peak", "Mount Fuji, Shizuoka, Japan", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Pre-compute cherry blossom particles
  var blossoms=[];
  var blossomCount = 50;
  var r=srand(1001);
  for(var i=0; i<blossomCount; i++){
    blossoms.push({
      x: Math.random() * W,
      y: Math.random() * H * 0.5,
      size: 2 + Math.random() * 3,
      speed: 0.1 + Math.random() * 0.2,
      angle: Math.random() * Math.PI * 2
    });
  }

  // Lake surface
  var lakeY = H - 60;
  var lakeWaves = [];

  return function(t){
    // === SKY GRADIENT ===
    for(var y=0; y<H*0.5; y++){
      var col=lerp('#ffffff', '#caf0f8', y/(H*0.5));
      rect(0, y, W, 1, col);
    }

    // === VOLCANIC CONE ===
    var coneHeight = 150;
    for(var x=130; x<350; x++){
      var height = coneHeight - Math.abs(250 - x) * 0.7 + Math.sin(t + x * 0.05) * 3;
      for(var y=lakeY; y<lakeY - height; y++){
        px(x, y, '#264653');
      }
    }

    // === TORII GATE ===
    var gateX = 230;
    for(var i=0; i<6; i++){
      px(gateX, H - 40 - i, '#e63946'); // Vertical posts
      px(gateX + 1, H - 40 - i, '#e63946');
      if(i === 1) {
        px(gateX - 1, H - 39, '#e63946'); // Crossbar
        px(gateX + 2, H - 39, '#e63946');
      }
    }

    // === LAKE KAWAGUCHI ===
    for(var x=0; x<W; x++){
      for(var y=lakeY; y<H; y++){
        var waveHeight = Math.sin(t + x * 0.02) * 2;
        px(x, y, rgba('#f1faee', 0.4 + waveHeight * 0.05));
      }
    }

    // === LAKE SURFACE REFLECTION ===
    for(var x=135; x<345; x++){
      var reflectionColor = osc(t, 5, x * 0.01);
      px(x, lakeY - 20, rgba('#264653', reflectionColor * 0.3)); // Reflection of the cone
    }

    // === CHERRY BLOSSOM PARTICLES ===
    for(var blossom of blossoms){
      blossom.x += Math.cos(blossom.angle) * blossom.speed;
      blossom.y += Math.sin(blossom.angle) * blossom.speed;
      if(blossom.x > W) blossom.x = 0;
      if(blossom.y > H * 0.5) blossom.y = Math.random() * (H * 0.5);
      
      var alpha = Math.max(0, 1 - (blossom.y / (H * 0.5)));
      circle(blossom.x, blossom.y, blossom.size, rgba('#e63946', alpha));
    }

    // === BOTTOM GLOW LINE ===
    rect(0,H-1,W,1,rgba('#e63946',0.3));
    rect(0,H-2,W,1,rgba('#caf0f8',0.1));
  };
});