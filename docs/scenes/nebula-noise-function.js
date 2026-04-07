// Scene: Nebula Noise Function
// Pillars of Creation, Eagle Nebula, M16
window.CF.register("Nebula Noise Function", "Pillars of Creation, Eagle Nebula, M16", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Pre-compute stars
  var stars=[];
  (function(){
    var r=srand(1001);
    for(var i=0;i<150;i++){
      stars.push({
        x:Math.floor(r()*W),y:Math.floor(r()*H*0.5),
        size:r()>0.85?3:(r()>0.6?2:1),
        baseAlpha:0.05+r()*0.6,
        period:1.5+r()*3,phase:r()*Math.PI*2
      });
    }
  })();

  // Pre-compute gas pillars
  var pillars=[];
  var pillarCount=5;
  for(var i=0;i<pillarCount;i++){
    pillars.push({
      x:Math.random()*W, y:Math.random()*(H-50)+50,
      width:Math.random()*10+2, height:Math.random()*70+40,
      sway: Math.random() * Math.PI * 2
    });
  }

  // Generate cosmic dust particles
  var dustParticles=[];
  for(var i=0;i<200;i++){
    dustParticles.push({
      x: Math.random()*W, y: Math.random()*H,
      vx: (Math.random()-0.5)*0.5, vy: (Math.random()-0.5)*0.5,
      life: Math.floor(Math.random()*50)
    });
  }

  return function(t){
    // === NIGHTS SKY BACKGROUND ===
    rect(0,0,W,H,rgba('#370617', 1));

    // === DRAW GAS PILLARS ===
    for(var pillar of pillars){
      var x = pillar.x;
      var baseY = H - pillar.height;
      for(var h=0;h<pillar.height;h++){
        var alpha = Math.sin(t*0.2 + pillar.sway + h*0.1) * 0.5; 
        px(x, baseY + h, rgba('#6a040f', alpha > 0 ? alpha : 0));
      }
      rect(x - pillar.width/2, baseY + pillar.height, pillar.width, 5, rgba('#e85d04', 0.1));
    }

    // === DRAW STARS ===
    for(var star of stars){
      var twinkle = osc(t, star.period, star.phase);
      var a = star.baseAlpha * twinkle;
      px(star.x, star.y, rgba('#faa307', a));
      if (star.size === 3) {
        rect(star.x - 1, star.y - 1, 3, 3, rgba('#faa307', a * 0.5));
      } else if (star.size === 2) {
        px(star.x, star.y, rgba('#faa307', a));
      }
    }

    // === COSMIC DUST ANIMATION ===
    for(var dust of dustParticles){
      px(dust.x, dust.y, rgba('#7b2ff7', 0.1));
      dust.x += dust.vx;
      dust.y += dust.vy;
      if(dust.x < 0 || dust.x > W || dust.y < 0 || dust.y > H) {
        dust.x = Math.random() * W;
        dust.y = Math.random() * H;
      }
    }

    // === EMISSION GLOW ===
    for(var i=0;i<40;i++){
      var glowX = Math.random() * W;
      var glowY = Math.random() * H;
      var glowRadius = Math.random() * 5 + 5;
      for(var r=0; r<glowRadius; r++){
        var alphaGlow = (glowRadius - r) / glowRadius * 0.5;
        circle(glowX, glowY, glowRadius - r, rgba('#faa307', alphaGlow));
      }
    }

    // REQUIRED: bottom glow line (brand consistency)
    rect(0,H-1,W,1,rgba('#e85d04',0.3));
    rect(0,H-2,W,1,rgba('#e85d04',0.1));
  };
});