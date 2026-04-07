// Scene: SSH Tunnel to Paradise
// Phong Nha Cave, Quang Binh, Vietnam
window.CF.register("SSH Tunnel to Paradise", "Phong Nha Cave, Quang Binh, Vietnam", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Boat state
  var boatX=0, boatY=H/2, boatWidth=20, boatHeight=10;

  // Water wave states
  var waveCount=30;
  var waves=[];
  for(var i=0;i<waveCount;i++){
    waves.push({
      x:i*(W/waveCount),
      displacement:Math.random()*3,
      angle:Math.random()*Math.PI*2
    });
  }

  // Stalactite settings
  var stalactites=[];
  var stalactiteCount=15;
  for(var i=0;i<stalactiteCount;i++){
    stalactites.push({
      x:Math.random()*W,
      length:5 + Math.random()*10,
      sway:Math.random()*2
    });
  }

  return function(t){
    // === CAVE BACKGROUND GRADIENT ===
    for(var y=0;y<H;y++){
      rect(0,y,W,1,lerp('#264653','#343a40',y/H));
    }

    // === UNDERGROUND RIVER ===
    for(var w=0;w<waveCount;w++){
      var waveY=H/2 + Math.sin(t*2+w) + waves[w].displacement;
      rect(waves[w].x,waveY,W/waveCount,1,rgba('#48cae4',0.6));
      waves[w].displacement=osc(t,waveCount/2,waves[w].angle);
    }

    // === BOAT ===
    boatX += 1; 
    if (boatX > W) boatX = -boatWidth; 
    for (var y=0; y<boatHeight; y++) {
      for (var x=0; x<boatWidth; x++) {
        px(boatX+x, boatY+y, '#2a9d8f');
      }
    }
    // Boat shadow
    for(var i=0; i<7; i++) {
      px(boatX+i, boatY+boatHeight, rgba('#000000',0.2));
    }

    // === SPOTLIGHT BEAM ===
    var spotlightX=W/3;
    var spotlightY=H/4;
    for(var dy=-20;dy<20;dy++){
      var alpha=1-Math.abs(dy)/20;
      ctx.globalAlpha=alpha;
      rect(spotlightX-10, spotlightY+dy, 20, 1, '#caf0f8');
    }
    ctx.globalAlpha=1;

    // === STALACTITES ===
    for(var stal of stalactites){
      for(var i=0;i<stal.length;i++){
        px(stal.x, i, '#343a40');
        px(stal.x+1, i, rgba('#343a40', 0.8));
      }
      stal.x += stal.sway;
      if(stal.x > W) stal.x = 0;
      else if(stal.x < 0) stal.x = W;
    }

    // Bottom glow line (brand consistency)
    rect(0,H-1,W,1,rgba('#2a9d8f',0.3));
    rect(0,H-2,W,1,rgba('#264653',0.1));
  };
});