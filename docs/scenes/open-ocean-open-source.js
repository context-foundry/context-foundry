// Scene: Open Ocean, Open Source
// Sargasso Sea, Atlantic Ocean
window.CF.register("Open Ocean, Open Source", "Sargasso Sea, Atlantic Ocean", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Sargassum mats particles
  var sargassumMats=[];
  for(var i=0;i<20;i++){
    sargassumMats.push({
      x:Math.random()*W,
      y:H-20-Math.random()*20,
      sway:Math.random()*4,
      life:20+Math.random()*60
    });
  }

  // Eel migration particles
  var eels=[];
  for(var i=0;i<8;i++){
    eels.push({
      x:Math.random()*W,
      y:H-40-Math.random()*20,
      vy:-Math.random()*0.5-0.5,
      life:80+Math.random()*40
    });
  }

  return function(t){
    // Deep blue ocean gradient
    for(var y=0;y<H;y+=2){
      var p=y/H;
      var col=lerp('#023e8a','#0096c7',p);
      rect(0,y,W,2,col);
    }

    // Distant clouds
    for(var i=0;i<5;i++){
      var cx=Math.random()*W;
      var cy=Math.random()*30+20;
      for(var dx=-20;dx<=20;dx++){
        for(var dy=-5;dy<=5;dy++){
          var a=1-Math.abs(dx)/20-Math.abs(dy)/5;
          if(a>0)px(cx+dx,cy+dy,rgba('#ffffff',a*0.3));
        }
      }
    }

    // Sargassum mats
    for(var mat of sargassumMats){
      mat.x += Math.sin(t + mat.sway) * 0.2;
      if (mat.x < -20) mat.x = W + 20;
      if (mat.x > W + 20) mat.x = -20;

      rect(mat.x, mat.y, 20, 5, '#48cae4');
      rect(mat.x + 3, mat.y - 2, 14, 3, '#90e0ef');
    }

    // Eel migration
    for(var eel of eels){
      eel.y += eel.vy;
      if(eel.y < -10) {
        eel.y = H + 10 + Math.random()*20;
        eel.x = Math.random()*W;
      }
      rect(eel.x, eel.y, 4, 1, '#0077b6');
    }

    // Light rays for atmosphere
    var raysCount = 3;
    for(var i=0; i<raysCount; i++){
      var rayX = Math.random() * W;
      for(var y = 0; y < 30; y++){
        var alpha = 0.1 * (1 - y / 30);
        px(rayX + Math.sin(t * 0.5 + i) * 10, y, rgba('#90e0ef', alpha));
      }
    }

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#0077b6',0.3));
    rect(0,H-2,W,1,rgba('#0077b6',0.1));
  };
});