// Scene: Lava Tube Localhost
// Kazumura Cave, Big Island, Hawaii, USA
window.CF.register("Lava Tube Localhost", "Kazumura Cave, Big Island, Hawaii, USA", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Lava particles
  var lavaParticles=[];
  for(var i=0;i<50;i++){
    lavaParticles.push({
      x:Math.random()*W,
      y:Math.random()*H,
      vy:-Math.random()*3-1,
      life:0,
      maxLife:Math.random()*30 + 10,
      color:'#6a040f'
    });
  }

  // Tree root intrusions
  var roots=[];
  for(var j=0;j<5;j++){
    roots.push({
      x:Math.random() * (W - 50) + 25,
      y:Math.random() * (H - 50) + 25,
      length:Math.floor(Math.random() * 20) + 10
    });
  }

  return function(t){
    // Background - dark cave walls
    for(var y=0; y<H; y++){
      var p=y/H;
      var col=lerp('#1d1d1d','#370617', p);
      rect(0, y, W, 1, col);
    }

    // Smooth lava tube walls
    for(var x=0; x<W; x++){
      var wallHeight = Math.sin(x * 0.05) * 4 + 24;
      for(var y=H-wallHeight; y<H; y++){
        px(x, y, rgba('#495057', 0.9));
      }
    }

    // Lava shelf - a glowing surface
    var lavaY = H - 30 + Math.sin(t * 2) * 2;
    rect(0, lavaY, W, 10, rgba('#6a040f', 0.8));
    for(var x=0; x<W; x+=4){
      if(Math.random() > 0.8){
        rect(x, lavaY-2, 2, 2, rgba('#ff6c40', 0.7));
      }
    }

    // Emit lava particles
    for(var p of lavaParticles){
      if(p.life > 0){
        p.y += p.vy;
        p.x += ((Math.random() - 0.5) * 2);
        p.life--;
        px(p.x, p.y, rgba(p.color, p.life / p.maxLife));
      } else if(Math.random() < 0.02){
        p.x = Math.random() * W;
        p.y = lavaY;
        p.vy = -Math.random() * 3 - 1;
        p.life = p.maxLife;
      }
    }

    // Tree roots
    for(var root of roots){
      for(var i=0; i<root.length; i++){
        px(root.x, root.y - i, '#370617');
      }
    }

    // Distant light source
    var lightX = W - 100 + Math.sin(t * 0.5) * 20;
    for(var y=20; y<40; y++){
      var a = Math.max(0, 1 - (y - 20) / 20);
      px(lightX, y, rgba('#fffd82', a * 0.5));
    }

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#6c757d',0.4));
    rect(0,H-2,W,1,rgba('#495057',0.1));
  };
});