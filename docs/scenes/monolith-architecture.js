// Scene: Monolith Architecture
// Uluru, Northern Territory, Australia
window.CF.register("Monolith Architecture", "Uluru, Northern Territory, Australia", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Spinifex grass particles
  var grasses=[];
  for(var i=0;i<50;i++){
    grasses.push({
      x:Math.random()*W,
      y:H-30+Math.random()*10,
      sway:Math.sin(Math.random()*Math.PI*2),
      height:5+Math.random()*10
    });
  }

  // Sunset gradient colors
  var sunsetColors=[
    '#f4a261', '#e76f51', '#d00000', '#264653', '#dda15e'
  ];

  return function(t){
    // === SKY GRADIENT ===
    for(var y=0;y<H;y+=2){
      var p=y/H;
      var col=lerp(sunsetColors[Math.floor((p)*sunsetColors.length)], '#264653', p);
      rect(0,y,W,2,col);
    }

    // === DESERT OAK ===
    var oakX=100, oakY=H-50;
    rect(oakX,oakY,8,12,'#264653');
    rect(oakX-2,oakY-6,12,6,'#3b8a45');
    circle(oakX+4,oakY-12,5,'#3b8a45');
    
    // === SANDSTONE MONOLITH ===
    var monolithX=W/2-20, monolithY=H-70;
    rect(monolithX,monolithY,40,70,'#d00000');
    for(var i=0;i<5;i++){
      rect(monolithX+i*8,monolithY,4,70,'#f4a261');
    }
    
    // === SPINIFEX GRASS ===
    for(var g of grasses){
      var swayOffset = Math.sin(t*2 + g.sway) * 1;
      for(var h=0;h<g.height;h++){
        px(g.x+swayOffset, g.y-h, '#a48d5c');
      }
    }

    // === GROUND ===
    rect(0,H-20,W,20,'#d0c4b0');

    // === ANIMATED SUN ===
    var sunPhase = Math.sin(t * 0.2) * 15; // oscillating sun position
    circle(W-100, H-120 + sunPhase, 15, rgba('#f4a261', 0.8));

    // === MOOD ENHANCEMENTS ===
    var moodParticles=[];
    for(var j=0;j<30;j++){
      moodParticles.push({
        x:Math.random()*W,
        y:Math.random()*H,
        life:Math.random() * 20 + 10,
        vx:(Math.random()-0.5)*0.4,
        vy:(Math.random()-0.5)*0.4
      });
    }

    for(var p of moodParticles){
      if(p.life > 0){
        px(p.x, p.y, rgba('#dda15e', 0.6));
        p.x += p.vx;
        p.y += p.vy;
        p.life--;
      }
    }

    // === BOTTOM GLOW LINE ===
    rect(0,H-1,W,1,rgba('#f4a261',0.3));
    rect(0,H-2,W,1,rgba('#f4a261',0.1));
  };
});