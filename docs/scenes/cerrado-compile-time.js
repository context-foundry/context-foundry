// Scene: Cerrado Compile Time
// Cerrado Biome, Goias, Brazil
window.CF.register("Cerrado Compile Time", "Cerrado Biome, Goias, Brazil", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Pre-compute twisted tree positions
  var trees=[];
  var treeCount=10;
  var treeRng=srand(1001);
  for(var i=0;i<treeCount;i++){
    var xPos=treeRng()*W;
    trees.push({
      x: xPos, 
      baseY: H - 50 - treeRng()*20,
      swayMult: treeRng()*5 + 2, // sway multiplier
      swayOffset: treeRng()*Math.PI*2 
    });
  }

  // Maned wolf position and state
  var wolfX = 60;
  var wolfY = H - 60;
  var wolfDirection = 1; // indicating movement direction
  var wolfSpeed = 0.5;

  // Particle systems for dust and termite mound
  var dustParticles = [];
  for (var i = 0; i < 30; i++) {
    dustParticles.push({
      x: treeRng() * W,
      y: H - 10 - treeRng() * 30,
      vx: (treeRng() - 0.5) * 0.5,
      vy: (treeRng() - 1) * 0.3,
      life: 20 + Math.floor(treeRng() * 40),
      maxLife: 20 + Math.floor(treeRng() * 40)
    });
  }

  return function(t){
    // === SKY ===
    for(var y=0;y<50;y++){
      rect(0,y,W,1,lerp('#fefae0','#283618',y/50));
    }

    // === RED LATERITE SOIL ===
    rect(0, H - 40, W, H - 40, '#bc6c25');

    // === TWISTED CERRADO TREES ===
    for (var tree of trees) {
      var sway = Math.sin(t * 2 + tree.swayOffset) * tree.swayMult;
      var treeY = tree.baseY + sway;
      rect(tree.x - 2, treeY, 4, 20, '#606c38'); // trunk
      circle(tree.x, treeY, 8, rgba('#283618', 0.2)); // foliage
    }

    // === TERMITE MOUND ===
    var moundX = W * 0.75;
    var moundY = H - 50;
    rect(moundX - 10, moundY, 20, 15, '#e76f51');
    circle(moundX, moundY, 10, rgba('#fefae0', 0.5));

    // === MANED WOLF ===
    wolfX += wolfDirection * wolfSpeed;
    if (wolfX > W - 20 || wolfX < 20) { wolfDirection *= -1; }
    circle(wolfX, wolfY, 5, '#e76f51'); // body
    circle(wolfX - 5, wolfY - 5, 3, '#606c38'); // head
    px(wolfX - 6, wolfY - 6, '#606c38'); // eye
    
    // === DUST PARTICLES ===
    for (var i = 0; i < dustParticles.length; i++) {
      var dust = dustParticles[i];
      dust.x += dust.vx;
      dust.y += dust.vy;
      dust.life--;
      if(dust.life <= 0 || dust.y < H - 40){
        dust.x = treeRng() * W;
        dust.y = H - 10 - treeRng() * 30;
        dust.life = dust.maxLife;
      }
      var alpha = dust.life / dust.maxLife * 0.3;
      px(dust.x, dust.y, rgba('#fefae0', alpha));
    }

    // === BOTTOM GLOW ===
    rect(0,H-1,W,1,rgba('#fefae0',0.3));
    rect(0,H-2,W,1,rgba('#bc6c25',0.1));
  };
});