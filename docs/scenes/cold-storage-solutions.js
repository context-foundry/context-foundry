// Scene: Cold Storage Solutions
// Svalbard Global Seed Vault, Svalbard, Norway
window.CF.register("Cold Storage Solutions", "Svalbard Global Seed Vault, Svalbard, Norway", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Snowflakes particles
  var snowflakes=[];
  for(var i=0;i<100;i++){
    snowflakes.push({
      x:Math.random()*W, 
      y:Math.random()*H,
      vy:Math.random()*0.5+0.5, 
      vx:(Math.random()-0.5)*0.2,
      size:Math.random()*2+1
    });
  }

  // Polar twilight background gradient
  function drawTwilight(t) {
    for(var y=0;y<H;y+=2){
      var p=y/H;
      var col=lerp('#2a9d8f', '#264653', p);
      rect(0,y,W,2,col);
    }
  }

  // Draw vault entrance
  function drawVaultEntrance(t) {
    var entranceWidth = 70, entranceHeight = 40;
    var x = W / 2 - entranceWidth / 2;
    var y = H - 100;

    rect(x, y, entranceWidth, entranceHeight, '#6c757d');
    rect(x + 5, y + 5, entranceWidth - 10, entranceHeight - 10, '#343a40');
    for(var i=0; i<entranceWidth; i+=10) {
      px(x + i, y + entranceHeight, '#e9ecef');
    }
  }

  // Draw geometric concrete patterns
  function drawConcretePatterns() {
    for(var x=0; x<W; x+=15){
      for(var y=H-50; y<H; y+=15){
        px(x + Math.random() * 5, y + Math.random() * 5, '#6c757d');
      }
    }
  }

  return function(t){
    // Draw twilight background
    drawTwilight(t);

    // Draw snowflakes
    for(var flake of snowflakes){
      flake.x += flake.vx;
      flake.y += flake.vy;
      if(flake.y > H){
        flake.y = -5;
        flake.x = Math.random()*W;
      }
      circle(flake.x, flake.y, flake.size, rgba('#ffffff', 0.8));
    }

    // Draw vault entrance
    drawVaultEntrance(t);

    // Draw ground and snowdrift
    rect(0,H-50,W,50,'#f0f0f0');
    for(var x=0; x<W; x+=10){
      rect(x, H-50 + Math.sin(x * 0.1 + t * 2) * 3, 10, 10, rgba('#ffffff', 0.5));
    }

    // Draw concrete patterns
    drawConcretePatterns();

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#2a9d8f',0.3));
    rect(0,H-2,W,1,rgba('#2a9d8f',0.1));
  };
});