// Scene: Danakil Kernel Temperature
// Danakil Depression, Afar Region, Ethiopia
window.CF.register("Danakil Kernel Temperature", "Danakil Depression, Afar Region, Ethiopia", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Random seed for deterministic particles
  var saltCrystals = [];
  var springs = [];
  for(var i = 0; i < 20; i++) {
    saltCrystals.push({x:Math.random()*W, y:Math.random()*(H-50)+150, size:Math.random()*3+2, life:Math.random()*20+10});
  }
  for(var i = 0; i < 15; i++) {
    springs.push({x:Math.random()*W, y:Math.random()*H, size:Math.random()*10+5, sway:Math.random()*Math.PI*2});
  }

  // Acid pool positions
  var acidPools = [
    {x: 100, y: 190, radius: 20},
    {x: 300, y: 210, radius: 15},
    {x: 150, y: 230, radius: 25}
  ];

  // Volcanic Crust
  var crustPatterns = [];
  for(var i = 0; i < W; i++) {
    var height = Math.sin(i * 0.02) * 10 + 220 + Math.random() * 5;
    crustPatterns.push({x: i, y: height});
  }

  return function(t){
    // Background Gradient
    for(var y = 0; y < H; y++) {
      var p = y / H;
      var col = lerp('#370617', '#ffffff', p);
      rect(0, y, W, 1, col);
    }

    // Volcanic Crust
    for(var p of crustPatterns) {
      if(p.y < H) {
        rect(p.x, p.y, 1, H - p.y, '#e85d04');
      }
    }

    // Acid Pools
    for(var pool of acidPools) {
      circle(pool.x, pool.y, pool.radius, rgba('#52b788', 0.5));
      for(var i = 0; i < 10; i++) {
        var angle = Math.random() * Math.PI * 2;
        var dist = Math.random() * pool.radius;
        px(pool.x + Math.cos(angle) * dist, pool.y + Math.sin(angle) * dist, '#52b788');
      }
    }

    // Draw Sulfur Springs
    for(var spring of springs) {
      circle(spring.x, spring.y, spring.size, rgba('#ffd166', 0.8));
      spring.y += Math.sin(t + spring.sway) * 0.5;
      spring.x += Math.sin(t + spring.sway) * 0.2;
      if(spring.y > H) spring.y = 0;
    }

    // Salt Formations
    for(var crystal of saltCrystals) {
      px(crystal.x, crystal.y, '#ffffff');
      crystal.y -= Math.sin(t) * 0.5;
      crystal.life--;
      if(crystal.life <= 0) {
        crystal.x = Math.random() * W;
        crystal.y = Math.random() * (H - 50) + 150;
        crystal.size = Math.random() * 3 + 2;
        crystal.life = Math.random() * 20 + 10;
      }
    }

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#ffd166',0.3));
    rect(0,H-2,W,1,rgba('#e85d04',0.1));
  };
});