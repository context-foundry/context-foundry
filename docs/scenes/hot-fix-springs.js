// Scene: Hot Fix Springs
// Grand Prismatic Spring, Yellowstone, USA
window.CF.register("Hot Fix Springs", "Grand Prismatic Spring, Yellowstone, USA", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Pre-compute bacterial mats and steam
  var bacteriaMats = [];
  var steamParticles = [];
  var bacteriaR = srand(123);
  for(var i = 0; i < 50; i++) {
    bacteriaMats.push({
      x: Math.floor(bacteriaR() * W),
      y: Math.floor(H * 0.5 + bacteriaR() * 60),
      life: 30 + Math.floor(bacteriaR() * 50)
    });
  }
  for(var i = 0; i < 100; i++) {
    steamParticles.push({
      x: Math.floor(bacteriaR() * W),
      y: H - Math.floor(bacteriaR() * 20),
      vy: -Math.random() * 0.5 - 0.2,
      life: 50 + Math.floor(bacteriaR() * 50)
    });
  }

  return function(t){
    // === BACKGROUND GRADIENT ===
    for(var y=0; y<H; y++){
      var p = y / H;
      rect(0, y, W, 1, lerp('#00b4d8', '#2d6a4f', p));
    }

    // === PRISMATIC RINGS ===
    for(var ring=0; ring<5; ring++){
      var rSize = 20 + (ring * 30);
      var color = lerp('#ff6b35', '#ffd700', ring / 4);
      for(var p=0; p<360; p+=1){
        var rad = p * Math.PI / 180;
        var x = W / 2 + Math.cos(rad) * rSize;
        var y = H - (H / 2 + Math.sin(rad) * rSize);
        px(Math.floor(x), Math.floor(y), rgba(color, 1 - (ring * 0.2)));
      }
    }

    // === STEAM PARTICLES ===
    for(var s of steamParticles){
      s.y += s.vy;
      s.life--;
      if(s.life <= 0 || s.y < H * 0.1) {
        s.x = Math.floor(Math.random() * W);
        s.y = H - Math.floor(Math.random() * 20) - 10;
        s.life = 50 + Math.floor(Math.random() * 50);
        s.vy = -Math.random() * 0.5 - 0.2;
      }
      var a = (s.life / 50) * 0.4;
      circle(s.x + Math.sin(t * 2 + s.x) * 2, s.y, 2, rgba('#ffffff', a));
    }

    // === BACTERIAL MATS ===
    for(var b of bacteriaMats){
      px(b.x, b.y, rgba('#f7a523', 0.5));
      px(b.x + 1, b.y, rgba('#ffd700', 0.4));
      px(b.x + 1, b.y + 1, rgba('#00b4d8', 0.3));
      b.life--;
      if(b.life <= 0) {
        b.x = Math.floor(bacteriaR() * W);
        b.y = Math.floor(H * 0.5 + bacteriaR() * 60);
        b.life = 30 + Math.floor(bacteriaR() * 50);
      }
    }

    // === BOARDWALK ===
    var boardwalkHeight = H * 0.4;
    rect(0, boardwalkHeight, W, 15, rgba('#8B4513', 0.8));
    for(var x = 0; x < W; x += 20){
      rect(x, boardwalkHeight + 5, 15, 10, rgba('#542E1C', 0.9));
    }

    // === BOTTOM GLOW LINE ===
    rect(0,H-1,W,1,rgba('#ff6b35',0.3));
    rect(0,H-2,W,1,rgba('#f7a523',0.1));
  };
});