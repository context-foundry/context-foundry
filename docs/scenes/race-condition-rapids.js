// Scene: Race Condition Rapids
// Zambezi River Rapids, Victoria Falls, Zambia
window.CF.register("Race Condition Rapids", "Zambezi River Rapids, Victoria Falls, Zambia", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Kayak state
  var kayakX = W / 2, kayakY = H - 50, kayakSpeed = 0.5;
  
  // Spray mist particles
  var mistParticles = [];
  for(var i = 0; i < 50; i++) {
    mistParticles.push({
      x: Math.random() * W,
      y: Math.random() * (H - 100),
      size: Math.random() * 3 + 1,
      alpha: Math.random() * 0.3 + 0.1,
      vy: Math.random() * 1 + 0.5
    });
  }

  // Initialize rocks in rapids
  var rocks = [];
  for(var i = 0; i < 30; i++) {
    rocks.push({
      x: Math.random() * W,
      y: Math.random() * (H - 70) + 50,
      size: Math.random() * 10 + 5
    });
  }

  return function(t){
    // === SKY ===
    rect(0, 0, W, H - 100, '#264653');

    // === RAPID WATER ===
    for(var y = H - 100; y < H; y++){
      var p = (y - (H - 100)) / 100;
      var waterColor = lerp('#2a9d8f', '#48cae4', p);
      rect(0, y, W, 1, waterColor);
    }

    // === MIST PARTICLES ===
    for(var p of mistParticles) {
      p.y += p.vy;
      if(p.y > H) p.y = -5;
      px(p.x, p.y, rgba('#FFFFFF', p.alpha));
    }

    // === ROCKS IN RAPIDS ===
    for(var rock of rocks){
      for(var dy = -rock.size; dy <= 0; dy++){
        for(var dx = -rock.size; dx <= rock.size; dx++){
          var d = Math.sqrt(dx * dx + dy * dy);
          if(d < rock.size) px(rock.x + dx, rock.y + dy, '#1b4332');
        }
      }
    }

    // === KAYAKER ANIMATION ===
    kayakX += Math.sin(t * 2) * kayakSpeed;
    kayakY -= Math.sin(t * 1) * 0.5; // simulate rapid movements

    // Draw kayak
    rect(kayakX - 5, kayakY, 10, 5, '#FFFFFF'); // kayak body
    px(kayakX, kayakY - 2, '#264653'); // paddle blade up

    // === BASALT GORGE WALL ===
    rect(0, H - 100, 20, 100, '#1b4332');
    rect(W - 20, H - 100, 20, 100, '#1b4332');

    // === SPRAY FROM RAPIDS ===
    for(var i = 0; i < 15; i++){
      var sprayX = Math.random() * W;
      var sprayY = H - 100 - Math.random() * 40;
      circle(sprayX, sprayY, Math.random() * 3 + 1, rgba('#ffffff', 0.5));
    }

    // === BOTTOM GLOW LINE ===
    rect(0, H - 1, W, 1, rgba('#48cae4', 0.2));
    rect(0, H - 2, W, 1, rgba('#264653', 0.1));
  };
});