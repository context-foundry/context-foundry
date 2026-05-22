// Scene: Deadlock in Dead Vlei
// Deadvlei, Namib-Naukluft Park, Namibia
window.CF.register("Deadlock in Dead Vlei", "Deadvlei, Namib-Naukluft Park, Namibia", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Pre-compute tree positions
  var trees=[];
  var treeCount=8;
  for(var i=0;i<treeCount;i++){
    var x=srand(i+1)() * W;
    var h=50 + Math.random() * 30;
    trees.push({x:x, h:h});
  }

  // Shadow gradients
  var shadowGradients = [];
  for(var i=0; i<W; i++){
    shadowGradients[i] = rgba('#1d1d1d', Math.max(0, 0.6 - (i / W) * 0.3));
  }

  return function(t){
    // === SKY -- stark blue gradient ===
    for(var y=0;y<100;y++){
      var col = lerp('#fefae0', '#264653', y/100);
      rect(0,y,W,1,col);
    }

    // === ORANGE DUNE WALL ===
    rect(0,100,W,50,rgba('#f4a261', 0.9));
    
    // === WHITE CLAY PAN ===
    rect(0,150,W,80,rgba('#ffffff', 0.9));

    // === HARSH SHADOWS ===
    for(var y=150; y<H; y++){
      var shadowAlpha = 0.1 + Math.sin((y - 150) * 0.1) * 0.05;
      rect(0,y,W,1,rgba('#1d1d1d', shadowAlpha));
    }

    // === DEAD CAMELTHORN TREES ===
    for(var tree of trees){
      var x = tree.x;
      var height = tree.h;
      for(var y = 0; y < height; y++){
        px(x, 150 - y, '#1d1d1d');
      }
      // Draw branches
      px(x-2, 150 - height, '#1d1d1d');
      px(x+2, 150 - height, '#1d1d1d');
      px(x, 150 - height - 1, '#fefae0');
    }

    // === DUST PARTICLES ===
    var dustParticles = [];
    for(var i=0; i<40; i++){
      dustParticles.push({
        x: Math.random() * W,
        y: Math.random() * 150,
        vx: (Math.random() - 0.5) * 0.5,
        life: Math.floor(Math.random() * 50)
      });
    }

    for(var i=0; i<dustParticles.length; i++){
      var dp = dustParticles[i];
      if(dp.life > 0){
        px(dp.x, dp.y, rgba('#f4a261', 0.5));
        dp.x += dp.vx;
        dp.y += 0.1; // Falling effect
        dp.life--;
      }
      if(dp.life <= 0){
        dp.x = Math.random() * W;
        dp.y = Math.random() * 150;
        dp.life = Math.floor(Math.random() * 50);
      }
    }

    // === BOTTOM GLOW LINE ===
    rect(0,H-1,W,1,rgba('#e76f51',0.6));
    rect(0,H-2,W,1,rgba('#e76f51',0.3));
  };
});