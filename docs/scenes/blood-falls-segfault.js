// Scene: Blood Falls Segfault
// Blood Falls, Taylor Glacier, Antarctica
window.CF.register("Blood Falls Segfault", "Blood Falls, Taylor Glacier, Antarctica", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Initialize red iron oxide flow
  var flowParticles=[];
  for(var i=0;i<80;i++){
    flowParticles.push({
      x:Math.random()*50+175,
      y:Math.random()*40+80,
      vy:Math.random()*0.5+0.2,
      life:Math.floor(Math.random()*40)+30,
      maxLife:Math.floor(Math.random()*40)+30
    });
  }

  // Initialize the glacier face
  var glacierFace = [];
  for(var x=0;x<50;x++){
    glacierFace.push(Math.floor(Math.random() * 30) + 70);
  }

  return function(t){
    // === BACKGROUND ===
    rect(0,0,W,H,rgba('#e9ecef',1));

    // === FROZEN LAKE ===
    for(var y=200;y<H;y++){
      for(var x=0;x<W;x++){
        var p=(y-200)/(H-200);
        var col=lerp('#ffffff','#e9ecef',p);
        px(x,y,col);
      }
    }

    // === GLACIER FACE ===
    for(var x=0;x<50;x++){
      var height=glacierFace[x];
      for(var y=0;y<height;y++){
        px(x+175,H-y-80,'#ffffff');
      }
    }

    // === RED IRON OXIDE FLOW ===
    for(var p of flowParticles){
      p.y += p.vy;
      if(p.y > H-80) {
        p.y = 80 + Math.random() * 20;
      }
      var a = (p.life / p.maxLife) * 0.6;
      if(a > 0.1) {
        px(p.x, p.y, rgba('#d00000', a));
        p.life--;
      }
    }

    // === OMINOUS CLOUDS ===
    for(var i=0;i<6;i++){
      var cloudY = 40 + Math.sin((t + i) * 0.5) * 5;
      var cloudX = 70 + i * 50;
      for(var dx=-15;dx<=15;dx++){
        for(var dy=-5;dy<=5;dy++){
          var a = 1 - Math.sqrt(dx*dx + dy*dy)/15;
          if(a > 0) {
            px(cloudX+dx, cloudY+dy, rgba('#6a040f', a * 0.5));
          }
        }
      }
    }

    // === FROZEN ICICLES ===
    for(var x=150;x<200;x+=6){
      for(var h=0; h<20; h++){
        px(x, 60-h, '#ffffff');
      }
    }

    // === GLOWING ICE EDGE ===
    for(var y=80; y<H; y+=2){
      for(var x=175; x<225; x+=2){
        px(x, y, rgba('#48cae4', 0.1 + Math.sin(t*2 + x/10)*0.05));
      }
    }

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#d00000',0.3));
    rect(0,H-2,W,1,rgba('#6a040f',0.1));
  };
});