// Scene: Epoch Timestamp Desert
// Wadi Rum, Jordan
window.CF.register("Epoch Timestamp Desert", "Wadi Rum, Jordan", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Sandstorm particles
  var sandParticles=[];
  for(var i=0;i<100;i++){
    sandParticles.push({
      x:Math.random()*W, y:Math.random()*H, vx:(Math.random()-0.5)*0.5, vy:(Math.random()-0.5)*0.5, life:0, maxLife:60
    });
  }

  // Function to update sand particle position
  function updateSandParticles() {
    for(var p of sandParticles){
      if(p.life > 0){
        p.x += p.vx;
        p.y += p.vy;
        p.life--;
        if(p.life <= 0) {
          p.x = Math.random()*W;
          p.y = -10; 
          p.vx = (Math.random()-0.5)*0.5;
          p.vy = (Math.random()-0.5)*0.5;
          p.maxLife = 60 + Math.random() * 40;
          p.life = p.maxLife;
        }
      } else {
        p.x = Math.random()*W;
        p.y = -10; 
        p.vx = (Math.random()-0.5)*0.5;
        p.vy = (Math.random()-0.5)*0.5;
        p.maxLife = 60 + Math.random() * 40;
        p.life = p.maxLife;
      }
    }
  }

  return function(t){
    // Background gradient - dusk sky
    for(var y=0; y<H; y+=2){
      var p=y/H;
      var col=lerp('#264653', '#e9c46a', p);
      rect(0, y, W, 2, col);
    }

    // Sand dunes 
    for(var x=0; x<W; x++){
      var dh = 5 * Math.sin((x + t * 10) * 0.01);
      rect(x, H - 20 + dh, 1, 20 - dh, '#f4a261');
    }

    // Sandstone arches
    rect(100, H-80, 20, 30, '#e76f51');
    rect(120, H-90, 40, 10, '#e76f51');
    rect(120, H-50, 10, 20, '#e76f51');
    rect(160, H-90, 40, 10, '#e76f51');

    // Bedouin camp
    rect(250, H-50, 50, 10, '#3b3b3b');
    rect(235, H-55, 10, 40, '#264653');
    rect(275, H-55, 10, 40, '#264653');

    // Camel train
    var camelX = 350 + Math.sin(t*0.5) * 5;
    for(var i=0; i<3; i++){
      rect(camelX + i*15, H-50, 12, 8, '#7b2ff7');
      rect(camelX + i*15 + 3, H-52, 6, 2, '#e76f51'); // Hump
    }

    // Update sand particles
    updateSandParticles();

    // Draw sand particles
    for(var p of sandParticles){
      if(p.life > 0) {
        px(p.x, p.y, rgba('#e9c46a', p.life / p.maxLife * 0.6));
      }
    }
    
    // Stars
    var starRand = srand(42);
    for(var i=0; i<50; i++){
      var sx = Math.floor(starRand() * W);
      var sy = Math.floor(starRand() * (H / 2));
      rect(sx, sy, 1, 1, rgba('#ffffff', 0.8));
    }

    // Moon
    var mx = W - 50, my = 40;
    for(var dy=-5; dy<=5; dy++){
      for(var dx=-5; dx<=5; dx++){
        var d = Math.sqrt(dx*dx + dy*dy);
        if(d <= 5) {
          rect(mx + dx, my + dy, 1, 1, rgba('#f4a261', d <= 3 ? 0.8 : 0.3));
        }
      }
    }

    // Bottom glow line
    rect(0, H-1, W, 1, rgba('#f4a261', 0.6));
    rect(0, H-2, W, 1, rgba('#e76f51', 0.3));
  };
});