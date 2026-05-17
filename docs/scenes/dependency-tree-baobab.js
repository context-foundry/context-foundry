// Scene: Dependency Tree: Baobab
// Avenue of the Baobabs, Morondava, Madagascar
window.CF.register("Dependency Tree: Baobab", "Avenue of the Baobabs, Morondava, Madagascar", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Zebu cart particles
  var zebuParticles=[];
  for(var i=0;i<20;i++){
    zebuParticles.push({
      x:Math.random()*W, y:H-20+Math.random()*5,
      vy:-Math.random()*0.5, life:0, maxLife:30
    });
  }

  // Baobab tree parameters
  var baobabHeight = 80;
  var baobabWidth = 20;
  var baobabPositions = [50, 120, 230, 300, 370];

  return function(t){
    // Sky gradient for sunset effect
    for(var y=0;y<H;y++){
      var p=y/H;
      var col=lerp('#fefae0','#bc6c25',p);
      rect(0,y,W,1,col);
    }

    // Ground
    rect(0,H-40,W,40,'#dda15e');

    // Dirt road
    for(var x=0;x<W;x+=10){
      rect(x,H-30,6,2,'#b58b0f');
    }

    // Baobab trees
    for(var i=0; i<baobabPositions.length; i++){
      var x = baobabPositions[i];
      var y = H - baobabHeight;
      rect(x - baobabWidth / 2, y, baobabWidth, baobabHeight, '#606c38');
      for(var leavesY=-10; leavesY<0; leavesY+=5){
        rect(x - 15 + i*5, y + leavesY, 10 + Math.random()*15, 5, '#e76f51');
        rect(x + 5 + i*5, y + leavesY, 10 + Math.random()*15, 5, '#e76f51');
      }
    }

    // Zebu cart moving left to right
    var cartX = (t * 10) % (W + 50) - 50;
    rect(cartX, H - 35, 40, 10, '#606c38'); // Cart body
    rect(cartX + 5, H - 40, 30, 5, '#fefae0'); // Cart top

    // Draw zebu particles
    for(var p of zebuParticles){
      if(p.life > 0){
        p.x += (Math.random()-0.5);
        p.y += p.vy;
        p.vy += 0.1; // gravity effect
        p.life--;
        var a = p.life/p.maxLife;
        px(p.x, p.y, rgba('#fefae0', a));
      }
    }

    // Emit particles from cart
    if(Math.random() < 0.3) {
      for(var z of zebuParticles){
        if(z.life <= 0){
          z.x = cartX + 20 + (Math.random()*10);
          z.y = H - 35 + (Math.random()*5);
          z.vy = -Math.random()*1.5;
          z.life = Math.floor(Math.random()*30) + 20;
          break;
        }
      }
    }

    // Bottom glow line for sunset consistency
    rect(0,H-1,W,1,rgba('#bc6c25',0.4));
    rect(0,H-2,W,1,rgba('#bc6c25',0.1));
  };
});