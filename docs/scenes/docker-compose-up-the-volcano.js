// Scene: docker compose up the Volcano
// Mount Bromo, East Java, Indonesia
window.CF.register("docker compose up the Volcano", "Mount Bromo, East Java, Indonesia", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Smoke particles from crater
  var smokeParticles=[];
  for(var i=0;i<50;i++){
    smokeParticles.push({
      x:Math.random()*W,y:Math.random()*H,
      vy:Math.random()*-0.5-0.5,
      vx:(Math.random()-0.5)*0.2,
      life:0,maxLife:30,
      hue:'#ffffff'
    });
  }
  
  function emitSmoke(sx,sy){
    for(var p of smokeParticles){
      if(p.life<=0){
        p.x=sx; p.y=sy;
        p.vx=(Math.random()-0.5)*0.2;
        p.vy=-Math.random()*0.5-0.5;
        p.maxLife=30+Math.random()*60;
        p.life=p.maxLife;
        break;
      }
    }
  }
  
  return function(t){
    // Background gradient - dawn sky
    for(var y=0; y<H; y+=2){
      var p=y/H;
      var col=lerp('#264653', '#495057', p);
      rect(0, y, W, 2, col);
    }

    // Sunrise light
    var sunY = H - 120 + Math.sin(t * 0.3) * 15;
    var sunX = 100;
    var sunGlow = 0.5 + Math.sin(t * 1) * 0.2;
    circle(sunX, sunY, 20, rgba('#faa307', sunGlow));

    // Crater of the volcano
    var craterX = W / 2;
    var craterY = H - 80;
    var craterRadius = 40;
    for(var angle=0; angle < Math.PI; angle+=0.1) {
      var dx = Math.cos(angle) * craterRadius;
      var dy = Math.sin(angle) * craterRadius;
      px(craterX + dx, craterY + dy, rgba('#e85d04', 0.8));
    }
    
    // Temple structure at the base
    rect(craterX - 30, craterY + 10, 60, 20, '#6c757d');
    rect(craterX - 40, craterY + 30, 80, 10, '#495057');
    rect(craterX - 10, craterY + 30, 20, 15, '#6c757d');

    // Emit smoke from the crater
    emitSmoke(craterX, craterY - 10);
    for(var p of smokeParticles){
      if(p.life > 0){
        p.x += p.vx;
        p.y += p.vy;
        p.life--;
        var a = (p.life / p.maxLife);
        px(p.x, p.y, rgba(p.hue, a * 0.7));
        if(a > 0.3) px(p.x + 1, p.y, rgba(p.hue, a * 0.4));
      }
    }

    // Sea of sand in the caldera
    for(var x=0; x<W; x+=2){
      for(var y=H-20; y<H; y++){
        px(x, y, '#f8f4e3');
      }
    }

    // Glowing bottom line for brand consistency
    rect(0,H-1,W,1,rgba('#e85d04',0.3));
    rect(0,H-2,W,1,rgba('#e85d04',0.1));
  };
});