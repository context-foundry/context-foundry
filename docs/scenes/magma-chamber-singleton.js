// Scene: Magma Chamber Singleton
// Mount Yasur, Tanna, Vanuatu
window.CF.register("Magma Chamber Singleton", "Mount Yasur, Tanna, Vanuatu", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Pre-compute volcanic bombs
  var bombs = [];
  (function(){
    var r = srand(1001);
    for (var i = 0; i < 20; i++) {
      bombs.push({
        x: r() * W,
        y: H - 20 - r() * 30,
        vy: -0.2 - r() * 0.3,
        life: 60 + Math.floor(r() * 60),
        color: '#d00000'
      });
    }
  })();

  // Initialize lava pit variables
  var lavaPitY = H - 70, lavaPitRadius = 50;

  return function(t){
    // === NIGHT SKY ===
    for (var y = 0; y < 100; y++) {
      var p = y / 100;
      rect(0, y, W, 1, lerp('#0b0c2a', '#370617', p));
    }

    // === STARS ===
    for (var i = 0; i < 50; i++) {
      var x = Math.random() * W;
      var y = Math.random() * 100;
      px(x, y, rgba('#ff6b35', 0.2 + Math.random() * 0.2));
    }

    // === MAGMA PIT ===
    for (var dy = -lavaPitRadius; dy <= 0; dy++) {
      var spread = Math.sqrt(lavaPitRadius * lavaPitRadius - dy * dy);
      for (var dx = -spread; dx <= spread; dx++) {
        px(W / 2 + dx, lavaPitY + dy, rgba('#faa307', 0.8));
      }
    }

    // === VOLCANIC BOMBS ===
    for (var bomb of bombs) {
      if (bomb.life > 0) {
        bomb.y += bomb.vy;
        bomb.life--;
        var size = (bomb.life / 60) * 3;
        px(bomb.x, bomb.y, rgba(bomb.color, 0.8));
        if (size > 0) {
          circle(bomb.x, bomb.y, size, rgba(bomb.color, 0.5));
        }
        if (bomb.y < 0) {
          bomb.y = H - 20 - Math.random() * 30;
          bomb.x = Math.random() * W;
          bomb.life = 60 + Math.floor(Math.random() * 60);
        }
      }
    }

    // === ASH-COVERED SLOPE ===
    for (var x = 0; x < W; x++) {
      var slopeY = Math.sin(x * 0.02) * 10 + (H - 30);
      px(x, slopeY, '#370617');
      for (var y = slopeY; y < H; y++) {
        px(x, y, rgba('#0b0c2a', 0.2));
      }
    }
    
    // === GLOW EFFECT ===
    for (var y = lavaPitY; y < lavaPitY + 20; y++) {
      var glowA = (y - lavaPitY) * 0.05;
      rect(W / 2 - lavaPitRadius, y, lavaPitRadius * 2, 1, rgba('#faa307', glowA));
    }

    // Bottom glow line
    rect(0, H - 1, W, 1, rgba('#ff6b35', 0.3));
    rect(0, H - 2, W, 1, rgba('#d00000', 0.1));
  };
});