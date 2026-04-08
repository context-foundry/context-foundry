// Scene: git blame the Tectonic Plates
// Thingvellir Rift, Iceland
window.CF.register("git blame the Tectonic Plates", "Thingvellir Rift, Iceland", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Pre-compute random functions
  var r1 = srand(1001), r2 = srand(2002);

  // Lava pool particles
  var lavaParticles = [];
  for (var i = 0; i < 50; i++) {
    lavaParticles.push({
      x: r1() * W,
      y: H - 30 + r1() * 20,
      vy: -r1() * 0.5,
      life: 20 + Math.floor(r1() * 10)
    });
  }

  // Fissure water parameters
  var waterRipples = [];
  for (var j = 0; j < 60; j++) {
    waterRipples.push({
      x: j * 8,
      y: H - 105 + r2() * 10,
      dx: 0,
      amplitude: 2 + r2() * 2,
      speed: 1 + r2() * 0.5
    });
  }

  // Blighted moss parameters
  var mossCoordinates = [];
  for (var k = 0; k < 30; k++) {
    mossCoordinates.push({
      x: Math.floor(r1() * W),
      y: H - 40 + Math.floor(r1() * 10),
      size: Math.floor(1 + r1() * 3)
    });
  }

  return function(t) {
    // Background
    rect(0, 0, W, H, rgba('#344e41', 1));

    // Drawing the tectonic plates rift
    var riftY = H - 130 + Math.sin(t) * 10;
    rect(0, riftY, W, 15, '#6c757d');
    
    // Lava fields with animated particles
    for (var p of lavaParticles) {
      if (p.life > 0) {
        p.y += p.vy;
        p.life--;
        px(p.x, p.y, rgba('#e9ecef', 0.8));
      } else {
        p.x = r1() * W;
        p.y = H - 30 + r1() * 20;
        p.life = 20 + Math.floor(r1() * 10);
      }
    }

    // Drawing moss on rocks
    for (var moss of mossCoordinates) {
      rect(moss.x, moss.y, moss.size, moss.size, rgba('#588157', 0.9));
    }

    // Drawing the Althing ruins
    var ruinX = W / 4;
    var ruinY = H - 90;
    for (var i = 0; i < 10; i++) {
      rect(ruinX + i, ruinY - 3, 2, 3, rgba('#adb5bd', 1));
    }
    
    // Fissure water with ripples
    for (var ripple of waterRipples) {
      ripple.dx = Math.sin(t * ripple.speed) * ripple.amplitude;
      rect(ripple.x + ripple.dx, ripple.y, 8, 3, rgba('#e9ecef', 0.5));
    }

    // Bottom glow line
    rect(0, H - 1, W, 1, rgba('#344e41', 0.3));
    rect(0, H - 2, W, 1, rgba('#588157', 0.1));
  };
});