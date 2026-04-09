// Scene: Sinkhole Stack Underflow
// Great Blue Hole, Belize
window.CF.register("Sinkhole Stack Underflow", "Great Blue Hole, Belize", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Initialize dive boats
  var boats=[];
  for(var i=0;i<5;i++){
    boats.push({
      x: Math.random() * W,
      y: H - 40 - Math.random() * 20,
      vy: Math.random() * 0.5 + 0.5,
      angle: Math.random() * Math.PI * 2
    });
  }

  // Initialize particles for the surface
  var particles=[];
  for(var j=0;j<100;j++){
    particles.push({
      x: Math.random() * W,
      y: Math.random() * H,
      vx: (Math.random() - 0.5) * 2,
      vy: -Math.random() * 0.5 - 0.5,
      life: 100 + Math.random() * 300
    });
  }

  return function(t){
    // === BACKGROUND GRADIENT ===
    for(var y=0; y<H; y+=2){
      var p=y/H;
      var col=lerp('#023e8a', '#0096c7', p);
      rect(0, y, W, 2, col);
    }

    // === CIRCULAR SINKHOLE ===
    var centerX = W / 2, centerY = H / 2;
    for(var y=-80; y<=80; y++){
      for(var x=-80; x<=80; x++){
        var d = Math.sqrt(x * x + y * y);
        if(d < 80){
          var col = d < 60 ? lerp('#48cae4', '#caf0f8', d / 60) : '#0096c7';
          px(centerX + x, centerY + y, col);
        }
      }
    }

    // === DEEP BLUE CENTER ===
    circle(centerX, centerY, 40, '#0077b6');

    // === REEF RING ===
    var reefGlow = osc(t, 3, 0) * 0.2;
    circle(centerX, centerY, 80, rgba('#0096c7', 0.6 + reefGlow));

    // === DIVE BOATS ===
    for(var boat of boats){
      boat.x += Math.sin(t + boat.angle) * 0.2;
      boat.y += Math.sin(t + boat.angle * 0.5) * 0.1;
      if(boat.y > H - 40) boat.y = H - 40;
      rect(boat.x - 10, boat.y - 3, 20, 6, '#caf0f8');
      rect(boat.x - 5, boat.y - 10, 10, 10, '#0077b6');
    }

    // === PARTICLES ===
    for(var particle of particles){
      particle.x += particle.vx;
      particle.y += particle.vy;
      particle.life--;
      if(particle.life <= 0){
        particle.x = Math.random() * W;
        particle.y = H;
        particle.vx = (Math.random() - 0.5) * 2;
        particle.vy = -Math.random() * 0.5 - 0.5;
        particle.life = 150 + Math.random() * 150;
      }
      var alpha = particle.life / 150;
      px(particle.x, particle.y, rgba('#caf0f8', alpha * 0.8)); 
    }

    // === BOTTOM GLOW ===
    rect(0, H - 1, W, 1, rgba('#0077b6', 0.6));
    rect(0, H - 2, W, 1, rgba('#0096c7', 0.3));
  };
});