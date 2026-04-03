// Scene: Legacy Codebase Ruins
// Angkor Wat, Siem Reap, Cambodia
window.CF.register("Legacy Codebase Ruins", "Angkor Wat, Siem Reap, Cambodia", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Temple spires positions and heights
  var spires = [
    {x: 100, height: 80},
    {x: 150, height: 70},
    {x: 200, height: 90},
    {x: 250, height: 65},
    {x: 300, height: 80}
  ];

  // Tree roots positions and roots
  var roots = [];
  for(var i=0; i<10; i++){
    roots.push({
      x: Math.random() * W,
      y: H - 20 + Math.random() * 10,
      wiggle: Math.random() * 2
    });
  }

  // Morning mist particles
  var mistParticles = [];
  for(var i=0; i<50; i++){
    mistParticles.push({
      x: Math.random() * W,
      y: Math.random() * H * 0.5,
      alpha: Math.random() * 0.4 + 0.1,
      drift: (Math.random() - 0.5) * 0.5
    });
  }

  return function(t){
    // Background gradient for the sky
    for(var y=0; y<H; y+=2){
      var p = y/H;
      var col = lerp('#ffffff', '#6b705c', p);
      rect(0, y, W, 2, col);
    }

    // Temple spires
    for(var spire of spires){
      var baseY = H - 20 - spire.height;
      rect(spire.x - 5, baseY, 10, spire.height, '#2d6a4f');
      rect(spire.x - 3, baseY + spire.height/2, 6, spire.height/2, '#40916c');
      for(var h=0; h<spire.height; h+=5){
        px(spire.x + Math.floor(Math.sin(t * 2 + spire.x) * 2), baseY - h, rgba('#b7b7a4', 0.4 + osc(t, 2, spire.x) * 0.1));
      }
    }

    // Tree roots
    for(var root of roots){
      var baseY = root.y + Math.sin(t * 2 + root.x / 50) * root.wiggle;
      rect(root.x - 3, baseY, 6, 3, '#40916c');
      rect(root.x - 2, baseY + 3, 4, 2, rgba('#a5a58d', 0.5));
    }

    // Moat reflection -- simple horizontal lines
    for(var y=H-40; y<H-20; y+=2){
      rect(0, y, W, 1, rgba('#a5a58d', 0.2));
    }

    // Morning mist particles
    for(var mist of mistParticles){
      mist.y += 0.1;
      if(mist.y > H * 0.5) mist.y = Math.random() * H * 0.5; 
      mist.x += mist.drift;
      if(mist.x < 0 || mist.x > W) mist.x = Math.random() * W;

      px(Math.floor(mist.x), Math.floor(mist.y), rgba('#ffffff', mist.alpha));
    }

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#2d6a4f',0.3));
    rect(0,H-2,W,1,rgba('#2d6a4f',0.1));
  };
});