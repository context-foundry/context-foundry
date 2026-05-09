// Scene: Ctrl+Z the Ice Age
// Vatnajokull Glacier, Iceland
window.CF.register("Ctrl+Z the Ice Age", "Vatnajokull Glacier, Iceland", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Particle systems
  var meltwaterParticles=[];
  for(var i=0;i<30;i++){
    meltwaterParticles.push({x:Math.random()*W,y:Math.random()*H,vy:0.5+Math.random(),life:60+Math.random()*20});
  }
  
  // Snowfall particles
  var snowflakes=[];
  for(var i=0;i<200;i++){
    snowflakes.push({x:Math.random()*W,y:Math.random()*H,vy:Math.random()*0.5+0.2,life:Math.random()*200+60});
  }

  // Function to draw crevasses
  function drawCrevasse(x, y, width, height) {
    rect(x, y, width, height, '#343a40');
    for (var j = 0; j < height; j++) {
      px(x + Math.floor(Math.random() * width), y + j, rgba('#ffffff', Math.random() * 0.5));
    }
  }

  return function(t){
    // Background gradient (sky)
    for(var y=0;y<H;y++){
      rect(0,y,W,1,lerp('#caf0f8','#ade8f4',y/H));
    }

    // Ice wall face
    for(var x=50; x<200; x+=3){
      for(var y=20; y<160; y+=3){
        px(x,y,rgba('#ffffff',0.3 + Math.random() * 0.2));
      }
    }
    
    // Draw crevasses
    for(var x=30; x<W; x+=100){
      drawCrevasse(x, H-150, 20 + Math.random() * 40, 40 + Math.random() * 15);
    }
    
    // Volcanic ash layers on glaciers
    for(var x=0; x<W; x+=10){
      var ashY = H - Math.random() * 80 - 40;
      rect(x, ashY, 10, 5, '#6c757d');
    }

    // Meltwater stream
    for(var y=200; y<250; y+=2){
      for(var x=20; x<W-20; x+=10){
        var width = Math.sin(t + y * 0.05) * 3 + 2;
        rect(x, y, width, 2, '#ade8f4');
      }
    }

    // Snowfall
    for (var flake of snowflakes) {
      if (flake.life > 0) {
        px(flake.x, flake.y, '#ffffff');
        flake.y += flake.vy;
        flake.x += (Math.random() - 0.5) * 0.5; // slight horizontal drift
        flake.life--;
        if (flake.y > H) {
          flake.x = Math.random() * W;
          flake.y = 0;
          flake.life = Math.random() * 200 + 60;
        }
      }
    }

    // Meltwater particles
    for (var particle of meltwaterParticles) {
      if (particle.life > 0) {
        circle(particle.x, particle.y, 2, rgba('#ffffff', 0.5));
        particle.y += particle.vy;
        particle.life--;
        if (particle.y > H) {
          particle.x = Math.random() * W;
          particle.y = Math.random() * H / 2;
          particle.life = 60 + Math.random() * 20;
        }
      }
    }

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#ade8f4',0.3));
    rect(0,H-2,W,1,rgba('#caf0f8',0.1));
  };
});