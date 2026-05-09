// Scene: Fjord Partition Table
// Milford Sound, South Island, New Zealand
window.CF.register("Fjord Partition Table", "Milford Sound, South Island, New Zealand", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Waterfall particles
  var waterfallParticles=[];
  for(var i=0;i<50;i++){
    waterfallParticles.push({
      x:Math.random()*W, y:Math.random()*H,
      vy:1 + Math.random() * 0.5,
      vx:(Math.random()-0.5) * 0.1,
      life:0, maxLife:Math.floor(Math.random() * 10) + 10
    });
  }

  // Reflections on water
  var reflections=[];
  for(var i=0;i<10;i++){
    reflections.push({
      x:Math.random() * (W-60) + 30, y:Math.random() * (H-40) + 60,
      width:Math.random() * 20 + 20, height:Math.random() * 3 + 2
    });
  }

  // Mount Mitre Peak
  function drawMitrePeak(x, y) {
    for(var i=0; i<20; i++) {
      px(x, y-i, '#264653');
      if(i < 7) {
        px(x-1, y-i, rgba('#2a9d8f', 0.4));
        px(x+1, y-i, rgba('#2a9d8f', 0.4));
      }
    }
  }

  return function(t){
    // Background gradient for sky
    for(var y=0; y<H; y+=2){
      var col=lerp('#264653', '#1b4332', y/H);
      rect(0,y,W,2,col);
    }

    // Draw Mitre Peak
    drawMitrePeak(240, 150);

    // Rainforest walls
    for(var x=0; x<W; x+=10){
      rect(x, H/2, 10, H/2, '#6c757d');
    }

    // Waterfall veils
    for(var i=0; i<4; i++){
      var wx = 225 + Math.sin(t * 2 + i) * 10;
      var wz = 30 + i * 10;
      rect(wx, 100, 5, wz, rgba('#e9ecef', 0.5));
      for(var j=0; j<5; j++){
        px(wx + Math.floor(Math.random()*2), 100 + wz + j, rgba('#e9ecef', 0.2));
      }
    }

    // Draw still water
    rect(0, H-60, W, 60, '#2a9d8f');

    // Reflections
    for(var ref of reflections){
      rect(ref.x, H-60, ref.width, ref.height, rgba('#e9ecef', 0.5));
    }

    // Waterfall particles animation
    for(var p of waterfallParticles){
      p.y += p.vy;
      p.x += p.vx;
      if(p.y > H){
        p.y = 0;
        p.x = Math.random() * W;
      }
      if(p.life < p.maxLife){
        p.life++;
        px(p.x, p.y, rgba('#e9ecef', 0.8));
      }
    }

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#2a9d8f',0.6));
    rect(0,H-2,W,1,rgba('#1b4332',0.2));
  };
});