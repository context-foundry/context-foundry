// Scene: print('Hello, Bioluminescence')
// Luminous Lagoon, Falmouth, Jamaica
window.CF.register("print('Hello, Bioluminescence')", "Luminous Lagoon, Falmouth, Jamaica", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,W=api.W,H=api.H;

  // Dinoflagellate shimmer particles
  var shimmerParticles=[];
  for(var i=0;i<100;i++){
    shimmerParticles.push({x:Math.random()*W,y:Math.random()*H,life:Math.random()*60+40});
  }

  // Glowing boat wake particles
  var wakeParticles=[];
  for(var j=0;j<30;j++){
    wakeParticles.push({x:0,y:0,vx:0,vy:0,life:0});
  }

  function emitWake(px, py){
    for(var wp of wakeParticles){
      if(wp.life<=0){
        wp.x=px; wp.y=py;
        wp.vx=(Math.random()-0.5)*3;
        wp.vy=-Math.random()*2;
        wp.life=30+Math.random()*30;
        break;
      }
    }
  }

  return function(t){
    // Background gradient -- night sky
    for(var y=0;y<H;y++){
      var p=y/H;
      var col=lerp('#0b0c2a','#023e8a',p);
      rect(0,y,W,1,col);
    }

    // Mangrove shore
    rect(0,H-30,W,30,'#1a1a2e');
    for(var i=0;i<10;i++){
      var mangroveX=i*48;
      rect(mangroveX,H-50,12,20,'#3c3c4a');
      circle(mangroveX+6,H-52,6,'#292b2f');
    }

    // Fisherman silhouette
    rect(W/2-5,H-40,10,12,'#3c3c4a');
    rect(W/2-2,H-34,4,4,'#3c3c4a');

    // Simulating glowing dinoflagellates
    for(var sp of shimmerParticles){
      sp.y -= 0.1; // Floating effect
      if(sp.y < 0) sp.y = H + Math.random()*20;
      sp.x += Math.sin(sp.y * 0.05) * 0.5; // Gentle sway
      var alpha = Math.max(0,1 - (sp.life--)/60);
      px(sp.x, sp.y, rgba('#00e5ff', alpha * 0.8));
    }

    // Boat wake animation
    var boatX = (t * 60) % W;
    var boatY = H - 30 + Math.sin(t * 2) * 2;
    for(var i = -3; i <= 3; i++){
      px(boatX + i, boatY, rgba('#00ff87', 0.6));
    }
    emitWake(boatX, boatY);

    // Update wake particles
    for(var wp of wakeParticles){
      if(wp.life>0){
        wp.x += wp.vx; wp.y += wp.vy;
        wp.vy += 0.05; // Gravity effect
        wp.life--;
        var alpha = Math.max(0, wp.life / 30);
        px(wp.x, wp.y, rgba('#00e5ff', alpha * 0.5));
        if(wp.life <= 0) emitWake(boatX, boatY);
      }
    }

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#00e5ff',0.3));
    rect(0,H-2,W,1,rgba('#00ff87',0.15));
  };
});