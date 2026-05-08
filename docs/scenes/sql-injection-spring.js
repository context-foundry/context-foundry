// Scene: SQL Injection Spring
// Son Doong Cave, Quang Binh, Vietnam
window.CF.register("SQL Injection Spring", "Son Doong Cave, Quang Binh, Vietnam", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Pre-compute stalagmite positions
  var stalagmites=[];
  var stalagmiteR=srand(1234);
  for(var i=0;i<15;i++){
    var baseX=20 + i * 30 + Math.floor(stalagmiteR()*10);
    var height=10 + Math.floor(stalagmiteR()*20);
    stalagmites.push({x:baseX, height:height});
  }

  // River particles
  var riverParticles=[];
  for(var i=0;i<20;i++){
    riverParticles.push({
      x:Math.random()*W,y:Math.random()*H,
      vy:0.1+Math.random()*0.2,
      vx:(Math.random()-0.5)*0.05,
      alpha:0.5+Math.random()*0.5
    });
  }

  // Create a function to draw stalagmites
  function drawStalagmite(s){
    for(var y=0;y<s.height;y++){
      px(s.x,H-y-1,'#1b4332');
      if(y < s.height - 2){
        px(s.x+1,H-y-1,'#2d6a4f');
        px(s.x-1,H-y-1,'#2d6a4f');
      }
    }
    // Top cap of stalagmite
    if(s.height > 3) px(s.x,H-s.height,'#343a40');
  }

  return function(t){
    // === BACKGROUND GRADIENT ===
    for(var y=0;y<H;y++){
      var color=lerp('#0c0c0c','#1b4332',y/H);
      rect(0,y,W,1,color);
    }

    // === SUNBEAM SHAFT ===
    var sunBeamX=320;
    for(var y=0;y<100;y++){
      var intensity=1 - (y/100);
      px(sunBeamX,y,rgba('#caf0f8',intensity*0.15));
      if(y < 50) {
        for(var dx=-1;dx<=1;dx++){
          px(sunBeamX+dx,y,rgba('#caf0f8',intensity*0.1));
        }
      }
    }

    // === UNDERGROUND RIVER ===
    var riverY=180 + Math.sin(t*0.5)*2;
    for(var x=0;x<W;x+=2){
      var col=rgba('#e9ecef',0.3 + Math.sin(t*1 + x * 0.02) * 0.2);
      rect(x,riverY,2,1,col);
    }

    // === RIVER PARTICLE ANIMATION ===
    for(var p of riverParticles){
      p.y += p.vy;
      p.x += p.vx;
      if(p.y > H) {
        p.y = Math.random() * 30;
        p.x = Math.random() * W;
      }
      px(p.x,p.y,rgba('#caf0f8',p.alpha));
    }

    // === STALAGMITES ===
    for(var s of stalagmites){
      drawStalagmite(s);
    }

    // === CAVE MONOLITH ===
    var monolithX=100, monolithHeight=40;
    for(var y=0; y<monolithHeight; y++){
      px(monolithX, H-y-1, '#1b4332');
    }
    for(var y=5; y<monolithHeight-5; y++){
      px(monolithX-1, H-y-1, '#2d6a4f');
      px(monolithX+1, H-y-1, '#2d6a4f');
    }

    // === CAVE DETAILS ===
    for(var i=0;i<50;i++){
      var rockX=Math.floor(Math.random() * W);
      var rockY=H-Math.floor(Math.random() * 50);
      if(rockY < H) {
        px(rockX, rockY, '#343a40');
      }
    }

    // === BOTTOM GLOW LINE ===
    rect(0,H-1,W,1,rgba('#1b4332',0.3));
    rect(0,H-2,W,1,rgba('#2d6a4f',0.1));
  };
});