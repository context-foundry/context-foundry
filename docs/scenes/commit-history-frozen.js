// Scene: Commit History: Frozen
// Ross Ice Shelf, Antarctica
window.CF.register("Commit History: Frozen", "Ross Ice Shelf, Antarctica", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Ice particle snow
  var iceParticles = [];
  for(var i = 0; i < 100; i++){
    iceParticles.push({
      x: Math.random() * W, 
      y: Math.random() * H,
      vx: (Math.random() - 0.5) * 0.2, 
      vy: (Math.random() * 0.5 + 0.2)
    });
  }

  // Wind streaks
  var windStreaks = [];
  for(var j = 0; j < 5; j++){
    windStreaks.push({
      x: Math.random() * W, 
      y: Math.random() * (H - 40) + 20, 
      length: Math.random() * 20 + 30,
      angle: Math.random() * Math.PI
    });
  }

  // Emperor penguins
  var penguins = [];
  for(var k = 0; k < 4; k++){
    penguins.push({
      x: Math.random() * (W - 50) + 25, 
      y: H - 40 - Math.random() * 10,
      sway: Math.random() * 1,
      direction: Math.random() * 0.5 + 0.5
    });
  }

  return function(t){
    // Background gradient
    for(var y = 0; y < H; y += 2){
      var p = y / H;
      var col = lerp('#e9ecef', '#dee2e6', p);
      rect(0, y, W, 2, col);
    }

    // Draw ice shelf edge
    rect(0, H - 30, W, 30, rgba('#adb5bd', 1));

    // Draw tabular iceberg
    rect(150, H - 80, 200, 50, rgba('#6c757d', 1));

    // Draw emperor penguins
    for(var p of penguins){
      p.x += Math.sin(t * 0.5) * p.sway * p.direction;
      if(p.direction > 0) p.direction -= 0.002;
      else p.direction += 0.002;

      rect(p.x, p.y, 5, 10, '#000');
      rect(p.x + 1, p.y - 10, 3, 10, rgba('#ffffff', 1)); // Body
      px(p.x + 2, p.y - 9, '#000'); // Eye
    }

    // Draw wind streaks
    for(var wind of windStreaks){
      var startX = wind.x;
      var startY = wind.y;
      for(var l = 0; l < wind.length; l++){
        var x = startX + l * Math.cos(wind.angle);
        var y = startY + l * Math.sin(wind.angle);
        px(x, y, rgba('#48cae4', Math.random() * 0.3 + 0.2)); 
      }
    }

    // Update ice particles
    for(var ice of iceParticles){
      ice.x += ice.vx;
      ice.y += ice.vy;
      if(ice.y > H){
        ice.y = Math.random() * 20;
        ice.x = Math.random() * W;
      }
      px(ice.x, ice.y, rgba('#ffffff', 0.5));
    }

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#48cae4',0.3));
    rect(0,H-2,W,1,rgba('#adb5bd',0.2));
  };
});