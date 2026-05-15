// Scene: Blue Screen of Death Valley
// Racetrack Playa, Death Valley, California, USA
window.CF.register("Blue Screen of Death Valley", "Racetrack Playa, Death Valley, California, USA", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Sailing stones -- persistent array
  var stones=[];
  for(var i=0;i<8;i++){
    stones.push({
      x:Math.random()*W,
      y:H-50-Math.random()*20,
      direction:(Math.random()-0.5)*2,
      speed:0.1+Math.random()*0.3,
      trail: []
    });
  }

  // Mystery trails
  var trails=[];
  for(var i=0;i<15;i++){
    trails.push({
      x:0,
      y:0,
      life:0,
      maxLife:Math.floor(Math.random()*20+5)
    });
  }

  function emitTrail(sx,sy){
    for(var t of trails){
      if(t.life <= 0){
        t.x = sx;
        t.y = sy;
        t.life = t.maxLife;
        break;
      }
    }
  }

  return function(t){
    // Sky gradient
    for(var y=0;y<H;y+=2){
      var p=y/H;
      var col=lerp('#f8f9fa','#264653',p);
      rect(0,y,W,2,col);
    }

    // Mountain ring
    for(var x=0;x<W;x+=8){
      var height = H - 100 + Math.sin(x * 0.02) * 10;
      rect(x, height, 8, 50, '#6c757d');
    }

    // Cracked playa surface
    var crackedPattern = srand(100);
    for(var x=0;x<W;x+=5){
      for(var y=H-50;y<H;y+=5){
        if(crackedPattern() < 0.1){
          rect(x, y, 5, 2, '#adb5bd');
        }
      }
    }

    // Draw sailing stones and their trails
    for(var s of stones){
      s.x += s.direction * s.speed;
      if(s.x < 0 || s.x > W) s.direction *= -1; // Bounce off walls
      s.y += Math.sin(t + s.x * 0.05) * 0.2; // Slight vertical oscillation

      // Draw stone
      circle(s.x, s.y, 3, '#dee2e6');

      // Emit trail behind
      emitTrail(s.x, s.y);
    }

    // Update and draw trails
    for(var t of trails){
      if(t.life > 0){
        t.life--;
        var trailAlpha = t.life / t.maxLife;
        px(t.x, t.y, rgba('#6c757d', trailAlpha * 0.5));
        // Move the trail upwards to simulate fading
        t.y -= 0.2;
      }
    }

    // Add dynamic trails where stones have passed
    var trailSpawnChance = 0.02;
    for(var s of stones){
      if(Math.random() < trailSpawnChance){
        emitTrail(s.x, s.y);
      }
    }

    // Bottom glow line to enhance visibility of the scene
    rect(0,H-1,W,1,rgba('#264653',0.4));
    rect(0,H-2,W,1,rgba('#264653',0.1));
  };
});
