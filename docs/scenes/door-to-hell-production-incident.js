// Scene: Door to Hell (Production Incident)
// Darvaza Gas Crater, Turkmenistan
window.CF.register("Door to Hell (Production Incident)", "Darvaza Gas Crater, Turkmenistan", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Burning crater particles
  var fireParticles = [];
  var fireCount = 150;
  for (var i = 0; i < fireCount; i++) {
    fireParticles.push({
      x: (Math.random() * 60) + 210, 
      y: Math.random() * 20 + 150,
      vy: Math.random() * -1.5 - 0.5,
      vx: (Math.random() - 0.5) * 0.5,
      life: Math.random() * 25 + 15,
      color: '#e85d04'
    });
  }

  // Campfire particles
  var campfireParticles = [];
  var campfireCount = 30;
  for (var i = 0; i < campfireCount; i++) {
    campfireParticles.push({
      x: Math.random() * 50 + 210, 
      y: Math.random() * 10 + 140,
      vy: Math.random() * -1 + 0.5,
      vx: (Math.random() - 0.5) * 0.2,
      life: Math.random() * 15 + 10,
      color: '#faa307'
    });
  }

  // Initialize glow function
  function drawGlow(cx, cy, radius, alpha) {
    for (var r = 0; r < radius; r++) {
      px(cx, cy, rgba('#d00000', alpha * (1 - r / radius)));
    }
  }

  return function(t){
    // === NIGHT SKY ===
    rect(0, 0, W, H - 100, '#1d1d1d');

    // === DESERT GROUND ===
    rect(0, H - 100, W, 100, '#370617');

    // === BURNING GAS CRATER ===
    var craterX = 240;
    var craterY = 150;
    circle(craterX, craterY, 20, rgba('#d00000', 0.8));
    drawGlow(craterX, craterY, 30, 0.3);
    
    // Burn particles around the crater
    for (var p of fireParticles) {
      if (p.life > 0) {
        p.y += p.vy;
        p.x += p.vx;
        p.life--;
        var alpha = Math.max(0, p.life / 15);
        px(Math.floor(p.x), Math.floor(p.y), rgba(p.color, alpha));
      }
    }

    // === CAMPFIRE ON RIM ===
    var campfireX = 200;
    var campfireY = 140;
    for (var p of campfireParticles) {
      if (p.life > 0) {
        p.y += p.vy;
        p.x += p.vx;
        p.life--;
        var alpha = Math.max(0, p.life / 10);
        px(Math.floor(p.x), Math.floor(p.y), rgba(p.color, alpha));
      }
    }

    // Draw campsite area
    rect(campfireX - 10, campfireY, 20, 5, '#e85d04');

    // === NIGHT GLOW AROUND CAMP ===
    drawGlow(campfireX, campfireY - 2, 15, 0.2);

    // === BOTTOM GLOW LINE ===
    rect(0, H - 1, W, 1, rgba('#e85d04', 0.3));
    rect(0, H - 2, W, 1, rgba('#d00000', 0.1));
  };
});