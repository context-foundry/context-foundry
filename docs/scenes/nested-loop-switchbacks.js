// Scene: Nested Loop Switchbacks
// Trollstigen, More og Romsdal, Norway
window.CF.register("Nested Loop Switchbacks", "Trollstigen, More og Romsdal, Norway", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Pre-compute zigzag road points
  var roadPoints = [];
  (function(){
    var segments = 8;
    var segmentLength = W / segments;
    for(var i=0; i<=segments; i++){
      var y = H - (i % 2 === 0 ? 40 : 80) - (i * 20);
      roadPoints.push(i * segmentLength, y);
    }
  })();

  // Waterfall properties
  var fallX = 100, fallY = H - 70;

  // Fog particles
  var fogParticles = [];
  var fogCount = 40;
  for(var i=0; i<fogCount; i++){
    fogParticles.push({
      x: Math.random() * W, 
      y: Math.random() * H, 
      vy: 0.2 + Math.random() * 0.2,
      alpha: 0.1 + Math.random() * 0.4,
    });
  }

  return function(t){
    // === SKY ===
    rect(0, 0, W, H, rgba('#e9ecef', 1));

    // === FOG ANIMATION ===
    for(var fog of fogParticles) {
      fog.y += fog.vy;
      if(fog.y > H) {
        fog.y = -10;
        fog.x = Math.random() * W;
      }
      px(fog.x, fog.y, rgba('#344e41', fog.alpha));
    }

    // === SHEER MOUNTAIN WALL ===
    for(var x = 0; x < W; x+=2) {
      var h = Math.sin(x * 0.02) * 50 + 150;
      for(var y = h; y < H; y++) {
        px(x, y, rgba('#adb5bd', 0.2));
      }
    }

    // === ZIGZAG ROAD ===
    ctx.fillStyle = '#588157';
    ctx.beginPath();
    ctx.moveTo(roadPoints[0], roadPoints[1]);
    for(var i = 2; i < roadPoints.length; i += 2){
      ctx.lineTo(roadPoints[i], roadPoints[i + 1]);
    }
    ctx.lineTo(W, H);
    ctx.lineTo(0, H);
    ctx.closePath();
    ctx.fill();

    // === WATERFALL ===
    for(var dy = 0; dy < 50; dy++) {
      var waterfallY = fallY + dy;
      var waterfallAlpha = 1 - (dy / 50);
      px(fallX, waterfallY, rgba('#48cae4', waterfallAlpha * 0.8));
      if(dy > 0) {
        px(fallX + 1, waterfallY, rgba('#48cae4', waterfallAlpha * 0.6));
        px(fallX - 1, waterfallY, rgba('#48cae4', waterfallAlpha * 0.6));
      }
    }

    // === BOTTOM GLOW LINE ===
    rect(0, H - 1, W, 1, rgba('#344e41', 0.3));
    rect(0, H - 2, W, 1, rgba('#344e41', 0.1));
  };
});