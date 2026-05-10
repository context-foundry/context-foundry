// Scene: Bamboo Array Forest
// Arashiyama Bamboo Grove, Kyoto, Japan
window.CF.register("Bamboo Array Forest", "Arashiyama Bamboo Grove, Kyoto, Japan", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Initialize bamboo state
  var bamboos = [];
  (function(){
    var r = srand(100);
    for(var i = 0; i < 20; i++){
      var x = Math.floor(r() * W);
      var height = 80 + Math.floor(r() * 80);
      bamboos.push({ x: x, height: height });
    }
  })();

  // Initialize stones for the path
  var stones = [];
  (function(){
    var r = srand(200);
    for(var i = 0; i < 15; i++){
      stones.push({
        x: Math.floor(r() * W), 
        y: H - 20 + Math.floor(r() * 10), 
        size: 3 + Math.floor(r() * 3)
      });
    }
  })();

  // Light filter particles
  var lightParticles = [];
  (function(){
    var r = srand(300);
    for(var i = 0; i < 30; i++){
      lightParticles.push({
        x: Math.floor(r() * W), 
        y: Math.floor(r() * H),
        alpha: 0.1 + r() * 0.4
      });
    }
  })();

  // Fence state
  var fenceWidth = 5;
  var fenceStart = 50;
  
  return function(t){
    // Background gradient
    for(var y = 0; y < H; y++){
      var p = y / H;
      rect(0, y, W, 1, lerp('#e3e0d3', '#b3c4b0', p));
    }

    // Draw bamboo
    for(var bamboo of bamboos){
      for(var h = 0; h < bamboo.height; h++){
        px(bamboo.x, H - h - 1, '#588157');
      }
    }

    // Draw stones
    for(var stone of stones){
      for(var dx = -stone.size; dx <= stone.size; dx++){
        for(var dy = -1; dy <= 1; dy++){
          px(stone.x + dx, stone.y + dy, '#a3b18a');
        }
      }
    }

    // Draw light particles
    for(var particle of lightParticles){
      particle.y += Math.sin(t * 2 + particle.x * 0.05) * 0.05;
      px(particle.x, particle.y, rgba('#ffffff', particle.alpha));
    }

    // Draw wooden fence
    for(var i = fenceStart; i < W - fenceStart; i += fenceWidth * 2){
      rect(i, H - 25, fenceWidth, 20, '#344e41');
      for(var j = 0; j < 20; j++){
        px(i, H - 25 + j, '#3a5a40');
      }
    }

    // Bottom glow line
    rect(0, H - 1, W, 1, rgba('#3a5a40', 0.2));
    rect(0, H - 2, W, 1, rgba('#588157', 0.1));
  };
});