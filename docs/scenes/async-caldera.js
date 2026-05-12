// Scene: Async Caldera
// Crater Lake, Oregon, USA
window.CF.register("Async Caldera", "Crater Lake, Oregon, USA", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Pine tree states
  var pineTrees=[];
  (function(){
    var r=srand(1001);
    for(var i=0;i<20;i++){
      var x = r() * W;
      var height = 15 + r() * 15;
      pineTrees.push({x:x, height:height, sway: r() * Math.PI * 2});
    }
  })();

  // Snow patches
  var snowPatches=[];
  (function(){
    var r=srand(2002);
    for(var i=0;i<10;i++){
      var x = r() * W;
      var y = r() * (H - 20);
      var size = 5 + r() * 10;
      snowPatches.push({x:x, y:y, size:size});
    }
  })();

  // Water ripples
  var rippleCount = 50;
  var ripples = [];
  for(var i=0; i<rippleCount; i++){
    ripples.push({
      x: Math.random() * W,
      y: H - 30 + Math.sin(i) * 2,
      size: Math.random() * 5 + 2
    });
  }
  
  return function(t){
    // === CALDERA LAKE ===
    for(var y=0; y<H; y++){
      var p = y / H;
      var col = lerp('#023e8a', '#0077b6', p);
      rect(0, y, W, 1, col);
    }

    // === WIZARD ISLAND ===
    var wizardIslandX = W * 0.65;
    var wizardIslandY = H - 50;
    for(var dx=-15; dx<=15; dx++){
      for(var dy=-10; dy<=3; dy++){
        var col = dy<0 ? '#264653' : '#588157';
        px(wizardIslandX + dx, wizardIslandY + dy, col);
      }
    }

    // === PINE TREES ===
    for(var tree of pineTrees){
      var swayOffset = Math.sin(t * 2 + tree.sway) * 1;
      for(var h=0; h<tree.height; h++){
        px(tree.x + swayOffset, H - 30 - h, '#588157');
      }
    }

    // === SNOW PATCHES ===
    for(var patch of snowPatches){
      for(var dy=0; dy<patch.size; dy++){
        for(var dx=-patch.size; dx<=patch.size; dx++){
          if(Math.abs(dx) + dy <= patch.size) {
            px(patch.x + dx, patch.y + dy, '#e9ecef');
          }
        }
      }
    }

    // === RIPPLES ===
    for(var ripple of ripples){
      px(ripple.x, ripple.y, rgba('#0077b6', 0.1));
      for(var r=0; r<ripple.size; r++){
        px(ripple.x+r, ripple.y, rgba('#0077b6', 0.05));
        px(ripple.x-r, ripple.y, rgba('#0077b6', 0.05));
      }
      ripple.y += -0.1 + Math.sin(t * 2 + ripple.x) * 0.1;
      if(ripple.y < H - 30){
        ripple.y = H - 30 + Math.random() * 2;
      }
    }

    // REQUIRED: bottom glow line for brand consistency
    rect(0,H-1,W,1,rgba('#0077b6',0.3));
    rect(0,H-2,W,1,rgba('#0077b6',0.1));
  };
});