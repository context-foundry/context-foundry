// Scene: Root Access Granted
// Redwood National Park, California, USA
window.CF.register("Root Access Granted", "Redwood National Park, California, USA", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Pre-compute tree positions
  var trees=[];
  for(var i=0;i<10;i++){
    trees.push({
      x:Math.random()*W,
      height:150 + Math.random() * 50,
      sway:0.1 + Math.random() * 0.4,
      offset:Math.random() * Math.PI * 2
    });
  }

  // Pre-compute fern positions
  var ferns=[];
  srand(123);
  for(var i=0;i<30;i++){
    ferns.push({
      x:Math.random() * W,
      y:Math.random() * 50 + 180,
      size:2 + Math.random() * 4
    });
  }

  // Fog particles
  var fogParticles=[];
  for(var i=0;i<50;i++){
    fogParticles.push({
      x:Math.random() * W,
      y:Math.random() * H * 0.5,
      vy:Math.random() * 0.1 + 0.02,
      life:Math.random() * 50 + 50
    });
  }

  // Tiny human for scale
  var human={x:220, y:200, height:10};

  return function(t){
    // === BACKGROUND ===
    var fogColor=rgba('#FFFFFF', 0.1);
    rect(0,0,W,H,rgba('#A3B18A', 0.5));
    for(var i=0;i<fogParticles.length;i++){
      var fp=fogParticles[i];
      if(fp.life>0){
        px(fp.x,fp.y,fogColor);
        fp.y+=fp.vy;
        if(fp.y > H) {
          fp.x = Math.random() * W;
          fp.y = Math.random() * H * 0.5;
          fp.life = Math.random() * 50 + 50;
        }
        fp.life--;
      }
    }

    // === FERN UNDERSTORY ===
    for(var fern of ferns){
      var alpha = 0.5;
      for(var dy=0;dy<fern.size;dy++){
        px(fern.x, fern.y - dy, rgba('#588157', alpha));
      }
    }

    // === DRAW REDWOOD TREES ===
    for(var tree of trees){
      var trunkWidth = 10;
      for(var h=0;h<tree.height;h++){
        var swayOffset = Math.sin(t * tree.sway + tree.offset) * 2;
        var trunkX = tree.x + swayOffset;
        rect(trunkX, H - h, trunkWidth, 1, '#6B3A0A');
      }
    }

    // === DRAW TINY HUMAN ===
    for(var dy=0;dy<human.height;dy++){
      px(human.x, human.y - dy, '#4A2C0A');
    }
    // Head
    circle(human.x, human.y - human.height - 2, 2, '#A3B18A');

    // === BOTTOM GLOW LINE ===
    rect(0,H-1,W,1,rgba('#2D6A4F',0.3));
    rect(0,H-2,W,1,rgba('#2D6A4F',0.1));
  };
});