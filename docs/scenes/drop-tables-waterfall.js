// Scene: DROP TABLE Waterfall
// Iguazu Falls, Argentina-Brazil Border
window.CF.register("DROP TABLE Waterfall", "Iguazu Falls, Argentina-Brazil Border", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Mist clouds -- persistent array
  var mist=[];
  for(var i=0;i<20;i++){
    mist.push({x:Math.random()*W, y:Math.random()*H, alpha:0.3 + Math.random()*0.5});
  }

  // Rainbow settings
  var rainbowSteps = 14;
  var rainbowY = 60; // Starting height for the rainbow
  var rainbowColors = ['#ff0000', '#ff7f00', '#ffff00', '#7fff00', '#00ff00', '#00ff7f', '#00ffff', '#007fff', '#0000ff', '#7f00ff', '#ff00ff', '#ff007f', '#ff0000'];

  return function(t){
    // Background gradient -- deep ocean to light sky
    for(var y=0;y<H;y+=2){
      var p=y/H;
      var col=lerp('#1b4332','#95d5b2',(p));
      rect(0,y,W,2,col);
    }

    // Horseshoe falls simulation
    for(var x=0; x<W; x+=2){
      var h = Math.sin((x/W) * Math.PI) * 80;  // Sinusoidal waterfall effect
      var dropY = H - 40 - h; // Height adjustment
      rect(x, dropY, 2, h, rgba('#ffffff', 0.8)); // Main fall
      if (h > 20) {
        rect(x-1, dropY, 4, 10, rgba('#95d5b2', Math.random() * 0.3)); // Mist at base
      }
    }

    // Mist clouds animation
    for(var m of mist){
      m.y += 0.5 * Math.random();
      if(m.y > H) m.y = 0;
      m.x += (Math.random() - 0.5) * 2;  // Slight drift
      px(m.x, m.y, rgba('#ffffff', m.alpha));
    }
    
    // Rainbow arc - draw arcs
    for(var i=0; i<rainbowSteps; i++){
      var r = 200 - i * 9; // Radius shrinking for arc
      ctx.fillStyle = rainbowColors[i % rainbowColors.length];
      ctx.beginPath();
      ctx.arc(W/2, rainbowY, r, Math.PI, 2 * Math.PI, false);
      ctx.lineTo(W/2 - r, rainbowY);
      ctx.fill();
      ctx.closePath();
    }

    // Tropical foliage
    var foliageCount = 5;
    for(var i=0; i<foliageCount; i++){
      var fx = Math.random() * W;
      var fy = H - (40 + Math.random() * 40);
      var h = 20 + Math.random() * 20;
      var w = 10 + Math.random() * 10;
      rect(fx-5, fy-h, w, h, '#2d6a4f'); // Main stem
      for(var j=0; j<5; j++){
        var leafX = fx - 5 + Math.random() * w;
        var leafY = fy - h + Math.random() * (h/2);
        triangle(leafX, leafY, leafX + 5, leafY - 10, leafX + 10, leafY, '#52b788'); // Leaves
      }
    }

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#52b788',0.4));
    rect(0,H-2,W,1,rgba('#52b788',0.1));
  };

  function triangle(x1, y1, x2, y2, x3, y3, color) {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.lineTo(x3, y3);
    ctx.lineTo(x1, y1);
    ctx.fill();
  }
});