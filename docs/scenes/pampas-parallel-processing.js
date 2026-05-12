// Scene: Pampas Parallel Processing
// Argentine Pampas, Buenos Aires Province, Argentina
window.CF.register("Pampas Parallel Processing", "Argentine Pampas, Buenos Aires Province, Argentina", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Gaucho state
  var gauchoX = 100, gauchoY = H - 50, gauchoSpeed = 0.2;
  var horseY = gauchoY + 2;

  // Cattle herd state
  var herd = [];
  var herdSize = 8;
  for (var i = 0; i < herdSize; i++) {
    herd.push({
      x: 50 + i * 50 + Math.random() * 20,
      y: H - 30 + Math.sin(i * 0.5 + Math.random()) * 2,
      dir: Math.random() < 0.5 ? 1 : -1
    });
  }

  // Windmill state
  var windmillRotation = 0;

  return function(t){
    // === SKY (y: 0-60) ===
    for(var y=0;y<60;y++){
      var p=y/60;
      rect(0,y,W,1,lerp('#48cae4','#a3b18a',p));
    }

    // === HORIZON ===
    rect(0,60,W,1,'#dad7cd');

    // === GROUND (y: 60-H) ===
    for(var y=60;y<H;y++){
      rect(0,y,W,1,'#606c38');
    }

    // === WINDMILL ===
    var windmillX = 360, windmillHeight = 40;
    rect(windmillX, H - windmillHeight, 5, windmillHeight, '#dda15e');
    for (var blade = 0; blade < 4; blade++) {
      ctx.save();
      ctx.translate(windmillX + 2.5, H - windmillHeight);
      ctx.rotate(windmillRotation + (blade * Math.PI / 2));
      rect(-1, -20, 8, 20, '#dad7cd');
      ctx.restore();
    }
    windmillRotation += 0.05;

    // === CATTLE HERD ===
    for (var cow of herd) {
      if (cow.x <= 0 || cow.x >= W) cow.dir *= -1; // Change direction if out of bounds
      cow.x += cow.dir * 0.2;
      px(cow.x, cow.y, '#ddd');

      // Draw cow shape
      for(var dy=-2;dy<0;dy++){
        for(var dx=-3;dx<=3;dx++){
          if(dx*dx+dy*dy<4){
            px(cow.x+dx,cow.y+dy,rgba('#606c38',0.8));
          }
        }
      }
      circle(cow.x, cow.y - 1, 1, '#606c38');  // Head
    }

    // === GAUCHO ON HORSE ===
    gauchoX += gauchoSpeed;
    if (gauchoX > W + 20) gauchoX = -20;  // Reset to left side
    px(gauchoX, gauchoY, '#000');  // Gaucho body
    rect(gauchoX - 2, horseY, 4, 4, '#dda15e');  // Horse body

    // Gaucho Hat
    px(gauchoX, gauchoY - 6, '#a3b18a');  // Head
    rect(gauchoX - 5, gauchoY - 6, 10, 3, '#000');  // Hat

    // === BOTTOM GLOW LINE ===
    rect(0,H-1,W,1,rgba('#dad7cd',0.3));
    rect(0,H-2,W,1,rgba('#dda15e',0.1));
  };
});