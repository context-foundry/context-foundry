// Scene: Cenote Connection Pool
// Cenote Ik Kil, Yucatan, Mexico
window.CF.register("Cenote Connection Pool", "Cenote Ik Kil, Yucatan, Mexico", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Water ripples and particles
  var particles=[];
  for(var i=0;i<100;i++){
    particles.push({
      x:Math.random()*W, y:H-40 + Math.random()*30,
      size:1 + Math.random()*2,
      life:Math.random()*30,
    });
  }

  // Vines state
  var vines = [];
  for(var i=0; i<8; i++){
    vines.push({
      x: 30 + i*50 + Math.random()*10,
      maxY: 60 + Math.random()*40,
      sway: Math.random() * Math.PI * 2,
    });
  }

  return function(t){
    // === BACKGROUND ===
    rect(0, 0, W, H, rgba('#343a40', 0.9)); // Dark limestone walls
    for(var y=0; y<H-50; y+=2){
      rect(0, y, W, 2, lerp('#0077b6', '#00b4d8', y / (H - 50))); // Water gradient
    }

    // === CIRCULAR SINKHOLE ===
    var centerX = W * 0.5, centerY = H * 0.1;
    for(var r=100; r>0; r--){
      var a = Math.sqrt(10000 - r * r);
      for(var x = -a; x <= a; x++){
        var dy = Math.floor(Math.sqrt(10000 - x * x));
        px(centerX + x, centerY + dy, rgba('#2d6a4f', 0.6));
        px(centerX + x, centerY - dy, rgba('#2d6a4f', 0.6));
      }
    }

    // === VINES ANIMATION ===
    for(var vine of vines){
      var swayOffset = Math.sin(t + vine.sway) * 2; 
      for(var h=0; h<vine.maxY; h++){
        px(vine.x + swayOffset, h + 20, rgba('#00b4d8', 0.8));
        px(vine.x + swayOffset + 1, h + 20, rgba('#00b4d8', 0.8));
      }
      vine.sway += 0.02; // Swaying motion
    }

    // === WATER DISTORTION ===
    for(var p of particles){
      p.y -= 0.2 + (Math.random() * 0.5); // Move upward
      if(p.y < H - 80) p.y = H - 40 + Math.random() * 30; // Reset position
      circle(p.x, p.y, p.size, rgba('#0077b6', (1 - p.life / 30) * 0.5));
      p.life--;
      if(p.life < 0) p.size = 2 + Math.random(); // Reset size
    }

    // === LIMESTONE WALLS ===
    for(var y=H-50; y<H; y++){
      for(var x=0; x<W; x+=4){
        if(Math.random() < 0.1){
          px(x+Math.random()*2, y, rgba('#2d6a4f', 0.5));
        }
      }
    }

    // === ANIMATED LIGHT RAYS ===
    for(var ray=0; ray<5; ray++){
      var rx = 20 + ray * (W / 6); 
      if(Math.random() < 0.3){
        for(var y=10; y<40; y++){
          var spread = Math.sin((y / 10) + t) * 3; 
          for(var dx=-spread; dx<=spread; dx++){
            px(rx + dx, y, rgba('#00b4d8', 0.1));
          }
        }
      }
    }

    // REQUIRED: bottom glow line (brand consistency)
    rect(0,H-1,W,1,rgba('#00b4d8',0.3));
    rect(0,H-2,W,1,rgba('#00b4d8',0.1));
  };
});