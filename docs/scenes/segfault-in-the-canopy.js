// Scene: Segfault in the Canopy
// Amazon Rainforest, Manaus, Brazil
window.CF.register("Segfault in the Canopy", "Amazon Rainforest, Manaus, Brazil", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Epiphyte array
  var epiphytes=[];
  for(var i=0;i<20;i++){
    epiphytes.push({
      x: Math.random() * W,
      y: Math.random() * (H - 100) + 50,
      size: Math.random() * 3 + 2,
      sway: Math.random() * Math.PI * 2
    });
  }

  // Macaw flight
  var macaw = {
    x: 0,
    y: 60 + Math.random() * 30,
    wingPhase: 0
  };

  // River flow
  var riverWave = [];
  for(var i=0; i<W; i++) {
    riverWave.push(Math.sin(i * 0.02) * 2);
  }

  return function(t){
    // Background gradient for canopy
    for(var y=0; y<H; y+=2){
      var p=y/H;
      var col=lerp('#081c15', '#1b4332', p);
      rect(0, y, W, 2, col);
    }

    // Canopy layers (darker above, lighter below)
    for(var i=0; i<5; i++){
      var layerOffset = i * 20;
      var layerHeight = Math.random() * 15 + 15;
      rect(0, layerOffset, W, layerHeight, lerp('#1b4332', '#2d6a4f', i / 5));
    }

    // Draw river below
    for(var i=0; i<W; i++){
      px(i, H - 30 + riverWave[i], '#40916c');
    }
    rect(0, H - 28, W, 2, '#52b788');

    // Epiphytes animation
    for(var e of epiphytes){
      e.sway += 0.02;
      var swayOffset = Math.sin(e.sway) * 2;
      circle(e.x + swayOffset, e.y, e.size, '#52b788');
      circle(e.x + swayOffset + 1, e.y + 1, e.size * 0.8, '#2d6a4f');
    }

    // Macaw flight
    macaw.x += 2;
    if(macaw.x > W) {
      macaw.x = -20;
      macaw.y = 60 + Math.random() * 30;
    }
    
    // Wing flap animation
    macaw.wingPhase += 0.1;
    var wingFlap = Math.sin(macaw.wingPhase) * 2;

    // Draw the macaw
    rect(macaw.x, macaw.y - 4, 15, 4, '#e63946'); // body
    rect(macaw.x + 12, macaw.y - 6 + wingFlap, 8, 4, '#f1faee'); // wing
    circle(macaw.x + 3, macaw.y - 2, 2, '#f1faee'); // head
    circle(macaw.x + 1, macaw.y - 3, 2, '#f1faee'); // eye

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#40916c',0.4));
    rect(0,H-2,W,1,rgba('#52b788',0.1));
  };
});