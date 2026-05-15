// Scene: Recursive Ridgeline
// Torres del Paine, Patagonia, Chile
window.CF.register("Recursive Ridgeline", "Torres del Paine, Patagonia, Chile", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Guanacos
  var guanacos = [];
  for(var i=0; i<5; i++){
    guanacos.push({
      x: 100 + i * 80,
      y: H - 50 - Math.random() * 30,
      dx: (Math.random() - 0.5) * 2,
      phase: Math.random() * Math.PI * 2
    });
  }

  // Floating debris (clouds)
  var clouds = [];
  for(var i=0; i<3; i++){
    clouds.push({
      x: Math.random() * W,
      y: Math.random() * 70,
      speed: Math.random() * 0.2 + 0.1
    });
  }

  // Glacial lake properties
  var lakeWave = 0;

  return function(t){
    // Sky gradient
    for(var y=0; y<H; y+=2){
      var p = y/H;
      var col = lerp('#264653', '#e9c46a', p);
      rect(0, y, W, 2, col);
    }

    // Draw granite towers
    var towerX = [50, 130, 220, 370];
    var towerHeight = [100, 120, 140, 160];
    for(var i=0; i<towerX.length; i++){
      var x = towerX[i];
      rect(x, H - 100 - towerHeight[i], 30, towerHeight[i], '#adb5bd');
    }
    
    // Windswept lenga trees
    for(var i=0; i<5; i++){
      var treeX = 60 + i * 60;
      var treeHeight = Math.random() * 20 + 30;
      rect(treeX, H - treeHeight - 10, 5, treeHeight, '#2a9d8f');
      for(var j=0; j<3; j++){
        var leafX = treeX + (Math.random() - 0.5) * 10;
        var leafY = H - treeHeight - (Math.random() * 5);
        px(leafX, leafY, '#e9c46a');
      }
    }

    // Animate Guanacos
    for(var g of guanacos){
      g.x += g.dx;
      if(g.x < -20 || g.x > W + 20){
        g.dx = -g.dx; // Reverse direction
      }
      g.y += 0.5 * Math.sin(g.phase);
      g.phase += 0.05;

      // Draw guanacos
      rect(g.x, g.y, 10, 5, '#e9ecef');
    }

    // Glacial lake
    rect(0, H - 50, W, 50, '#2a9d8f');
    lakeWave += 0.05;
    for(var x=0; x<W; x+=5){
      var w = 2 + Math.sin(lakeWave + x * 0.1) * 2;
      rect(x, H - 50 + 5 - w, 5, w, '#264653');
    }

    // Clouds animation
    for(var c of clouds){
      c.x += c.speed;
      if(c.x > W){
        c.x = -20;
        c.y = Math.random() * 70;
      }
      rect(c.x, c.y, 50, 20, rgba('#e9c46a', 0.2));
    }

    // Bottom glow line
    rect(0, H-1, W, 1, rgba('#e9c46a', 0.3));
    rect(0, H-2, W, 1, rgba('#e9c46a', 0.1));
  };
});