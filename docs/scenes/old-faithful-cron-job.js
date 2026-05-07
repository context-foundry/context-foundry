// Scene: Old Faithful Cron Job
// Old Faithful Geyser, Yellowstone, Wyoming, USA
window.CF.register("Old Faithful Cron Job", "Old Faithful Geyser, Yellowstone, Wyoming, USA", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Initialize geyser state
  var geyserActive = false;
  var eruptionHeight = 0;
  var eruptionInterval = 10;
  var eruptionTimer = 0;

  // Initialize steam particles
  var steamParticles = [];
  for (var i = 0; i < 50; i++) {
    steamParticles.push({
      x: Math.random() * 480,
      y: H - 20 + Math.random() * 20,
      vy: -Math.random() * 0.5 - 0.5,
      vx: (Math.random() - 0.5) * 0.2,
      life: Math.random() * 60 + 40
    });
  }

  return function(t){
    // === SKY ===
    rect(0, 0, W, H, rgba('#caf0f8', 1));
    
    // === GROUND ===
    rect(0, H - 80, W, 80, rgba('#6b705c', 1));

    // === MINERAL TERRACE ===
    rect(50, H - 60, 380, 10, rgba('#a3b18a', 1));
    rect(70, H - 50, 340, 30, rgba('#a3b18a', 0.8));

    // === TOURIST BOARDWALK ===
    rect(180, H - 70, 120, 5, '#ffffff');
    rect(185, H - 75, 110, 5, '#ffffff');

    // === Geyser logic ===
    eruptionTimer++;
    if (eruptionTimer >= eruptionInterval) {
      geyserActive = true;
      eruptionHeight = 0;
      eruptionTimer = 0;
    }
    
    if (geyserActive) {
      eruptionHeight += 2; // Increment height
      if (eruptionHeight >= 60) {
        geyserActive = false; // Stop eruping when height limit reaches
      }
    }

    // Draw geyser eruption
    if (eruptionHeight > 0) {
      for (var y = 0; y < eruptionHeight; y++) {
        px(240, H - 80 - y, '#48cae4');
      }
      // Draw the top of the geyser plume with dynamic color
      var topColor = rgba('#ffffff', Math.max(0, (60 - eruptionHeight) / 60));
      for (var i = -5; i <= 5; i++) {
        px(240 + i, H - 80 - eruptionHeight, topColor);
      }
    }

    // === STEAM PARTICLES ===
    for (var p of steamParticles) {
      p.x += p.vx;
      p.y += p.vy;
      p.life--;
      if (p.life <= 0) {
        p.x = Math.random() * 480;
        p.y = H - 20 + Math.random() * 20;
        p.vy = -Math.random() * 0.5 - 0.5;
        p.life = Math.random() * 60 + 40;
      }
      px(p.x, p.y, rgba('#ffffff', 0.3));
    }

    // === BOTTOM GLOW LINE ===
    rect(0, H-1, W, 1, rgba('#48cae4', 0.3));
    rect(0, H-2, W, 1, rgba('#48cae4', 0.1));
  };
});