// Scene: Cherry Blossom Release Branch
// Meguro River, Tokyo, Japan
window.CF.register("Cherry Blossom Release Branch", "Meguro River, Tokyo, Japan", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Initialize persistent state here (arrays, pre-computed data)
  var blossoms = [];
  var glow = [
    { x: 100, y: 50, size: 5 },
    { x: 250, y: 70, size: 4 },
    { x: 400, y: 60, size: 3 }
  ];
  
  // Pre-compute cherry blossom petal positions
  (function(){
    var r = srand(1000);
    for (var i = 0; i < 100; i++) {
      blossoms.push({
        x: r() * W,
        y: r() * 100,
        life: 60 + Math.floor(r() * 120),
        maxLife: 60 + Math.floor(r() * 120),
        speed: 0.5 + r() * 1.5,
        angle: r() * Math.PI * 2
      });
    }
  })();

  return function(t){
    // === SKY ===
    for (var y = 0; y < 100; y++) {
      var color = lerp('#E8F5E9', '#B2DFDB', y / 100);
      rect(0, y, W, 1, color);
    }

    // === WATER ===
    for (var y = 100; y < 190; y++) {
      for (var x = 0; x < W; x++) {
        var wave = Math.sin((x + t * 10) * 0.05) * 2;
        var color = lerp('#A5D6A7', '#80CBC4', (y - 100) / 90 + wave / 20);
        px(x, y, color);
      }
    }

    // === CHERRY BLOSSOM CANOPY ===
    for (var i = 0; i < W; i++) {
      var height = 40 + Math.sin(i * 0.05 + t) * 5;
      px(i, height, rgba('#ffc8dd', 0.6));
      px(i, height + 1, rgba('#ffafcc', 0.6));
    }

    // === PETALS ===
    for (var b of blossoms) {
      b.y += b.speed;
      if (b.y > 190) {
        b.x = Math.random() * W;
        b.y = Math.random() * 60;
      }
      var a = (b.life / b.maxLife) * 0.3;
      px(b.x, b.y, rgba('#ffafcc', a));
      b.life--;
    }

    // === STONE LANTERNS ===
    var lanterOffset = 40;
    function drawLantern(x, y) {
      rect(x - 3, y, 6, 12, '#6c757d');
      rect(x - 5, y + 12, 10, 5, '#264653');
      rect(x - 7, y + 17, 14, 2, '#ffafcc');
    }
    drawLantern(120, 140);
    drawLantern(300, 140);

    // === ARCHED BRIDGE ===
    ctx.fillStyle = '#264653';
    ctx.beginPath();
    ctx.moveTo(200, 100);
    ctx.bezierCurveTo(150, 50, 330, 50, 280, 100);
    ctx.lineTo(280, 120);
    ctx.lineTo(200, 120);
    ctx.fill();

    // === GLOW EFFECT ===
    for (var g of glow) {
      var a = Math.sin(t + g.x) * 0.25 + 0.5;
      circle(g.x, g.y, g.size, rgba('#ffc8dd', a * 0.5));
    }

    // REQUIRED: bottom glow line (brand consistency)
    rect(0, H - 1, W, 1, rgba('#264653', 0.3));
    rect(0, H - 2, W, 1, rgba('#6c757d', 0.1));
  };
});