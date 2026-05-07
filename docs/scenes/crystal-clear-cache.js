// Scene: Crystal Clear Cache
// Naica Mine Crystal Cave, Chihuahua, Mexico
window.CF.register("Crystal Clear Cache", "Naica Mine Crystal Cave, Chihuahua, Mexico", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Cave ceiling stalactites
  var stalactites=[];
  for(var i=0;i<20;i++){
    stalactites.push({
      x:Math.random()*W*0.9 + 30, 
      h:Math.random()*30 + 10,
      sway:Math.random()*2
    });
  }

  // Crystal beams
  var crystals=[];
  for(var i=0;i<10;i++){
    crystals.push({
      x:Math.random() * W,
      y:Math.random() * 50,
      sway:Math.random()*0.5,
      height:Math.random()*60 + 20,
      brightness: Math.random() * 0.3 + 0.7
    });
  }

  // Exploring Character
  var explorerX = W / 2;
  var explorerY = H - 20;

  return function(t){
    // Background gradient for the cave
    for(var y=0; y<H; y+=2){
      var p = y / H;
      var col = lerp('#343a40', '#6c757d', p);
      rect(0, y, W, 2, col);
    }

    // Cave ceiling stalactites
    for(var stal of stalactites){
      for(var y=0; y<stal.h; y++){
        var a = (y / stal.h);
        var col = rgba('#f8f9fa', Math.max(0, 0.5 - a*0.5));
        px(stal.x, y, col);
        if(Math.random() < 0.02) {
          circle(stal.x + (Math.random()*2 - 1), y, 1, rgba('#caf0f8', a*0.5));
        }
      }
    }

    // Crystal beams
    for(var crystal of crystals){
      for(var y=H; y>H - crystal.height; y--){
        var a = (H - y) / crystal.height;
        var col = rgba('#ade8f4', a * crystal.brightness);
        rect(crystal.x, y, 3, 1, col);
      }
      var swayOffset = Math.sin(t * 2 + crystal.sway) * crystal.sway;
      circle(crystal.x + swayOffset, H - crystal.height, 4, rgba('#caf0f8', crystal.brightness * 0.6));
    }

    // Mineral pool
    var poolY = H - 30;
    rect(50, poolY, 100, 10, rgba('#caf0f8', 0.5));
    rect(60, poolY + 5, 80, 5, rgba('#76c1df', 0.3));

    // Drawing the cave explorer
    px(explorerX - 1, explorerY, '#f8f9fa'); // body
    px(explorerX, explorerY - 1, '#6c757d'); // head
    px(explorerX, explorerY + 1, '#f8f9fa'); // legs
    px(explorerX + 1, explorerY, '#343a40'); // gear

    // Cave Ceiling Shadows
    for(var x=0; x<W; x+=20){
      rect(x, 0, 20, 10, rgba('#3a3a40', 0.2));
    }

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#caf0f8',0.4));
    rect(0,H-2,W,1,rgba('#f8f9fa',0.1));
  };
});