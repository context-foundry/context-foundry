// Scene: Terraform the Terraces
// Pamukkale Travertine Terraces, Denizli, Turkey
window.CF.register("Terraform the Terraces", "Pamukkale Travertine Terraces, Denizli, Turkey", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Pre-compute thermal pool data
  var pools = [];
  (function(){
    var r = srand(1001);
    for (var i = 0; i < 5; i++) {
      pools.push({
        x: r() * (W - 60) + 30,
        y: H - 70 + r() * 20,
        width: 50 + r() * 30,
        height: 20 + r() * 10,
        color: rgba('#90e0ef', 0.8 + r() * 0.2)
      });
    }
  })();

  // Pre-compute ancient ruins
  var ruins = [];
  (function(){
    var r = srand(2002);
    for (var i = 0; i < 4; i++) {
      ruins.push({
        x: r() * (W - 80) + 40,
        y: H - 80 - r() * 60,
        width: 15 + r() * 10,
        height: 30 + r() * 20,
        color: '#dda15e'
      });
    }
  })();

  // Initialize sunset glow
  var sunY = H - 200 + Math.sin(0) * 20;
  var sunX = W / 2;
  var sunGlow = 1;

  return function(t){
    // === BACKGROUND GRADIENT ===
    for (var y = 0; y < H; y++) {
      var p = y / H;
      var col = lerp('#caf0f8', '#48cae4', p);
      rect(0, y, W, 1, col);
    }

    // === THERMAL POOLS ===
    for (var pool of pools) {
      rect(pool.x, pool.y, pool.width, pool.height, pool.color);
    }

    // === TERRACES ===
    var terraceHeight = 14;
    for (var y = H - 70; y < H; y += terraceHeight) {
      rect(0, y, W, terraceHeight, rgba('#ffffff', 0.9));
      for (var x = 0; x < W; x += 60) {
        rect(x, y - 2, 60, 8, rgba('#dddddd', 0.7));
      }
    }

    // === RENDER ANCIENT RUINS ===
    for (var ruin of ruins) {
      rect(ruin.x, ruin.y, ruin.width, ruin.height, ruin.color);
      for (var j = 0; j < 4; j++) {
        px(ruin.x + 1 + j, ruin.y + ruin.height - 1, '#ffffff');
      }
    }

    // === SUNSET RAY ===
    sunY = H - 200 + Math.sin(t * 0.5) * 20;
    for (var i = 0; i < 40; i++) {
      var offsetX = Math.sin(t + i) * 50;
      var offsetY = Math.cos(t + i) * 20;
      px(sunX + offsetX, sunY + offsetY, rgba('#FFA500', sunGlow));
    }
    circle(sunX, sunY, 20, rgba('#FFA500', 0.8));

    // === SUNSET GLOW ===
    for (var y = sunY; y < sunY + 20; y++) {
      var alpha = (20 - (y - sunY)) / 20;
      rect(0, y, W, 1, rgba('#FFA500', alpha * 0.2));
    }

    // === BOTTOM GLOW LINE ===
    rect(0,H-1,W,1,rgba('#FFA500',0.3));
    rect(0,H-2,W,1,rgba('#FFA500',0.1));
  };
});