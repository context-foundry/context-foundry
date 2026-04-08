// Scene: Savanna Garbage Collector
// Masai Mara, Kenya
window.CF.register("Savanna Garbage Collector", "Masai Mara, Kenya", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,W=api.W,H=api.H;

  // Vulture parameters
  var vultures=[];
  var vultureCount = 5;
  for(var i=0;i<vultureCount;i++){
    vultures.push({
      x: Math.random() * W,
      y: Math.random() * 100,
      phase: Math.random() * Math.PI * 2,
      size: 3 + Math.random() * 2
    });
  }
  
  // Lion pride parameters
  var lions = [];
  for(var i = 0; i < 3; i++) {
    lions.push({
      x: 200 + Math.random() * 100,
      y: H - 100 + Math.random() * 30,
      size: 5 + Math.random() * 3,
      sleeping: true
    });
  }

  // Baobab tree position
  var baobabX = 100;
  var baobabY = H - 60;

  // Dry riverbed
  var riverY = H - 30;

  return function(t){
    // Sky color gradient
    for(var y=0;y<H;y++){
      var p=y/H;
      rect(0,y,W,1,lerp('#f0e3df', '#bc6c25', p));
    }

    // Draw dry riverbed
    rect(0, riverY, W, 10, rgba('#f4a261', 0.8));
    for(var i = 0; i < W; i += 10) {
      var hOffset = Math.sin(i * 0.1 + t) * 2;
      rect(i, riverY + hOffset, 10, 5, rgba('#dda15e', 0.6));
    }

    // Draw baobab tree
    rect(baobabX, baobabY, 20, 30, '#606c38');
    for(var i = 0; i < 30; i++) {
      var branchX = baobabX - 15 + Math.random() * 50;
      var branchY = baobabY - 20 - Math.random() * 15;
      circle(branchX, branchY, 5 + Math.random() * 5, '#f4a261');
    }

    // Draw lions
    for(var lion of lions) {
      rect(lion.x, lion.y, lion.size, lion.size / 2, '#f4a261');
      if (lion.sleeping) {
        rect(lion.x, lion.y + 3, lion.size, lion.size / 4, '#dda15e');
      }
    }

    // Draw vultures
    for(var vulture of vultures) {
      vulture.y += Math.sin(t * 0.5 + vulture.phase) * 0.3;
      vulture.x += Math.cos(t * 0.2 + vulture.phase) * 0.5;
      vulture.x = (vulture.x + W) % W; // Wrap around
      for(var dy = -vulture.size; dy <= vulture.size; dy++){
        for(var dx = -vulture.size; dx <= vulture.size; dx++){
          if(dx * dx + dy * dy <= vulture.size * vulture.size) {
            px(vulture.x + dx, vulture.y + dy, rgba('#606c38', 0.9));
          }
        }
      }
    }

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#264653',0.3));
    rect(0,H-2,W,1,rgba('#264653',0.1));
  };
});