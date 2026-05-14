// Scene: Neon City Never Sleeps
// Shibuya Crossing, Tokyo, Japan
window.CF.register("Neon City Never Sleeps", "Shibuya Crossing, Tokyo, Japan", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Crowd umbrellas
  var umbrellas=[];
  for(var i=0;i<50;i++){
    umbrellas.push({
      x:Math.random()*W,
      y:H-40+Math.random()*10,
      open:Math.random() > 0.5,
      sway:Math.random()*2
    });
  }

  // LED billboards
  var billboards=[];
  for(var i=0;i<5;i++){
    billboards.push({
      x:Math.random() * (W - 150),
      y:Math.random() * 70 + 20,
      width:Math.random() * 150 + 50,
      height:20 + Math.random() * 30,
      color: ['#ff006e', '#ffd166', '#00e5ff'][Math.floor(Math.random() * 3)]
    });
  }

  // Create reflections on pavement
  var createReflection = function(x, y, width, height, color, alpha) {
    for(var dy=0;dy<height;dy++){
      rect(x, y + dy, width, 1, rgba(color, alpha * (1 - dy / height)));
    }
  };

  return function(t){
    // Background gradient
    for(var y=0;y<H;y+=2){
      var p=y/H;
      var col=lerp('#0b0c2a','#1b1b1b',p);
      rect(0,y,W,2,col);
    }

    // Ground reflection
    for(var y=H-30;y<H;y++){
      var p=1 - (y-(H-30))/30;
      rect(0,y,W,1,rgba('#0b0c2a',p * 0.5));
    }

    // Draw billboards
    for(var b of billboards){
      rect(b.x, b.y, b.width, b.height, b.color);
      for(var i=0;i<5;i++){
        ctx.fillStyle=rgba('#ffffff', 0.2 + Math.random() * 0.3);
        ctx.font='10px Arial';
        ctx.fillText("AD "+(i+1), b.x + 5, b.y + 15 + i * 3);
      }
    }

    // Draw umbrellas
    var umbrellaColors = ['#ff006e', '#00e5ff', '#ffd166'];
    for(var u of umbrellas){
      if(u.open){
        circle(u.x, u.y - 10, 8, umbrellaColors[Math.floor(Math.random() * umbrellaColors.length)]);
      }
      // Swaying motion
      u.x += Math.sin(t + u.sway) * 0.5;
      // Keep umbrellas within bounds
      u.x = (u.x + W) % W;
    }

    // Create reflections from the billboards
    for(var b of billboards){
      createReflection(b.x, H - 1, b.width, 10, b.color, 0.1);
    }

    // Draw moving vehicles
    for(var i=0;i<3;i++){
      var vehicleX = (t * 20 + i * 150) % W;
      rect(vehicleX, H - 35, 40, 20, '#ff006e');
      rect(vehicleX + 5, H - 20, 30, 5, '#ffd166');
    }

    // Stars in the urban sky
    var starRand=srand(24);
    for(var i=0;i<30;i++){
      var sx=Math.floor(starRand()*W);
      var sy=Math.floor(starRand()*50);
      var a=0.2+osc(t,1+i*0.1,i)*0.5;
      px(sx,sy,rgba('#ffffff',a));
    }

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#ff006e',0.4));
    rect(0,H-2,W,1,rgba('#00e5ff',0.2));
  };
});