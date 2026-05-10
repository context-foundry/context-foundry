// Scene: .env Variable Hot Springs
// Jigokudani Monkey Park, Nagano, Japan
window.CF.register(".env Variable Hot Springs", "Jigokudani Monkey Park, Nagano, Japan", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Snow monkeys
  var monkeys = [];
  for(var i=0; i<5; i++){
    monkeys.push({
      x: Math.random() * (W - 40) + 20,
      y: Math.random() * (H - 40) + 140,
      sway: Math.random() * 0.5,
      velocity: 0,
      bathing: true
    });
  }

  // Steam particles
  var steamParticles = [];
  for(var i=0; i<80; i++){
    steamParticles.push({
      x: Math.random() * (W - 40) + 20,
      y: H - 60 + Math.random() * 40,
      life: Math.random() * 20 + 20,
      vy: Math.random()*-0.5 - 0.1,
      size: Math.random() * 2 + 1
    });
  }

  // Rocks
  var rocks = [];
  for(var i=0; i<15; i++){
    rocks.push({
      x: Math.random() * (W - 40) + 20,
      y: H - 40 - Math.random() * 20,
      width: Math.random() * 10 + 10,
      height: Math.random() * 5 + 5
    });
  }

  return function(t){
    // Background gradient
    for(var y=0; y<H; y+=2){
      var p=y/H;
      var col=lerp('#e63946','#ffffff',p);
      rect(0,y,W,2,col);
    }

    // Draw rocks
    for(var rock of rocks){
      rect(rock.x, rock.y, rock.width, rock.height, '#6c757d');
    }

    // Draw steam particles
    for(var steam of steamParticles){
      if(steam.life > 0){
        steam.x += (Math.sin(t + steam.x * 0.1) * 0.15);
        steam.y += steam.vy;
        steam.life--;
        var alpha = steam.life / 40;
        circle(steam.x, steam.y, steam.size, rgba('#ffffff', alpha * 0.5));
      }
    }

    // Draw snow monkeys
    for(var monkey of monkeys){
      if(monkey.bathing) {
        monkey.velocity = Math.sin(t * monkey.sway) * 0.3;
        monkey.y += monkey.velocity;

        for(var dy=-3; dy<=3; dy++){
          for(var dx=-5; dx<=5; dx++){
            if(dy === 0 && dx === 0){
              px(monkey.x + dx, monkey.y + dy, '#2d6a4f');
            } else if(Math.abs(dy) < 2 && Math.abs(dx) < 2){
              px(monkey.x + dx, monkey.y + dy, '#ffffff');
            }
          }
        }

        // Face and features
        px(monkey.x, monkey.y - 1, '#2d6a4f'); // Eyes
        px(monkey.x + 1, monkey.y, '#ffffff'); // Head
      }
    }

    // Bamboo fence
    for(var x=0; x<W; x+=30){
      rect(x, H - 40, 5, 20, '#48cae4');
      rect(x + 2, H - 30, 15, 5, '#6c757d');
    }

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#48cae4',0.3));
    rect(0,H-2,W,1,rgba('#2d6a4f',0.1));
  };
});