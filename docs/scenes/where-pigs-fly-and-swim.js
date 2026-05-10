// Scene: Where Pigs Fly (and Swim)
// Big Major Cay, Exuma, Bahamas
window.CF.register("Where Pigs Fly (and Swim)", "Big Major Cay, Exuma, Bahamas", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Swimming pigs
  var pigs=[];
  (function(){
    var r=srand(1001);
    for(var i=0;i<5;i++){
      pigs.push({
        x: Math.random() * (W - 50),
        y: 200 + r() * 20,
        vx: 0.5 + r() * 0.5,
        phase: r() * Math.PI * 2,
        size: 3 + r() * 2
      });
    }
  })();

  // Palm trees
  var palmTrees = [];
  (function(){
    var r=srand(1002);
    for(var i=0; i<8; i++){
      palmTrees.push({
        x: 50 + i * 60 + r() * 20,
        baseY: H - 20 - Math.random()*10,
        sway: r() * 0.5
      });
    }
  })();

  // Crystal clear water particles
  var waterParticles = [];
  (function(){
    for(var i=0; i<60; i++){
      waterParticles.push({
        x: Math.random() * W,
        y: H - 22 - Math.random() * 10,
        vx: (Math.random() - 0.5) * 0.3,
        life: Math.random() * 30
      });
    }
  })();

  // Background gradient
  function drawGradient(){
    for(var y=0; y<H; y++){
      var p=y/H;
      var col=lerp('#00b4d8', '#90e0ef', p);
      rect(0, y, W, 1, col);
    }
  }

  // Draw beach
  function drawBeach(){
    rect(0, H-20, W, 20, '#fefae0');
  }

  return function(t){
    // === DRAW SCENE ===
    drawGradient();
    drawBeach();

    // === SWIMMING PIGS ===
    for(var pig of pigs){
      pig.x += pig.vx;
      if(pig.x > W + 20) pig.x = -20;
      pig.y += Math.sin(t + pig.phase) * 0.1;

      // Draw pig
      rect(pig.x, pig.y, pig.size, pig.size * 0.6, '#dda15e');
      circle(pig.x + pig.size * 0.2, pig.y - pig.size * 0.2, pig.size * 0.2, '#fefae0');
    }

    // === PALM TREES ===
    for(var palm of palmTrees){
      var swayOffset = Math.sin(t * 0.5 + palm.sway) * 2;

      // Draw trunk
      rect(palm.x, palm.baseY, 3, 10, '#52b788');
      // Draw leaves
      for(var j=-1; j<=1; j++){
        circle(palm.x + swayOffset + j * 5, palm.baseY - 10, 8, '#52b788');
      }
    }

    // === CRYSTAL CLEAR WATER ===
    for(var p of waterParticles){
      p.y += 0.2 + Math.sin(t * 0.5 + p.x * 0.02) * 0.1;
      p.x += p.vx;
      if(p.y > H) {
        p.y = H - 22 - Math.random() * 10;
        p.x = Math.random() * W;
      }
      rect(p.x, p.y, 2, 2, rgba('#90e0ef', 0.2));
    }

    // === BOTTOM GLOW LINE ===
    rect(0,H-1,W,1,rgba('#dda15e',0.3));
    rect(0,H-2,W,1,rgba('#dda15e',0.1));
  };
});