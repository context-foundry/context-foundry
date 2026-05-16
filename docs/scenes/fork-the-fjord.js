// Scene: Fork the Fjord
// Geirangerfjord, Norway
window.CF.register("Fork the Fjord", "Geirangerfjord, Norway", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Pre-compute cliff coordinates
  var cliffs = [];
  for(var x = 0; x < W; x++) {
    var height = Math.sin(x * 0.03) * 40 + 130;
    cliffs.push(height);
  }

  // Water properties
  var waves = [];
  for(var x = 0; x < W; x++) {
    waves.push(100 + Math.sin(x * 0.1) * 3);
  }

  // Ferries
  var ferryPos = 0;
  var ferryX = 0;
  var ferryY = 0; 

  return function(t){
    // === SKY (y: 0-70) ===
    for(var y=0;y<71;y++){
      var p=y/70;
      rect(0,y,W,1,lerp('#B2EBF2','#80DEEA',p));
    }

    // === SUN ===
    var sunX=W-50, sunY=40;
    circle(sunX, sunY, 15, rgba('#FFEB3B', 0.8));
    circle(sunX, sunY, 10, rgba('#FFF176', 0.9));

    // === WATER SURFACE (y: 71-120) ===
    for(var y=71; y<120; y++){
      for(var x=0; x<W; x++){
        var waveHeight = Math.sin((x + t * 10) * 0.1) * 3;
        px(x, y, lerp('#1b3a4b', '#3d6b7e', (y-71)/49 + waveHeight * 0.02));
      }
    }

    // === WATERFALL ===
    for(var y = 40; y < 130; y++){
      var waterfallX = 300;
      if (y < 100) {
        var heightOffset = Math.max(0, waterfallX * 0.02 - y);
        for(var x=waterfallX-5; x<waterfallX+5; x++){
          var cascadeCol = rgba('#d4edda', heightOffset * 0.1);
          px(x, y, cascadeCol);
        }
      }
    }

    // === CLIFFS ===
    for(var x=0; x<W; x++) {
      for(var y=cliffs[x]; y<H; y++) {
        px(x, y, rgba('#3d6b7e', 0.9));
      }
    }

    // === FERRY ===
    ferryPos += 0.2;
    ferryX = (t * 30) % W;
    ferryY = waves[Math.floor(ferryX)];

    // Ferry body
    rect(ferryX - 8, ferryY, 16, 4, '#7fc8a9');
    circle(ferryX - 10, ferryY + 2, 2, '#5d6d7e');
    circle(ferryX + 10, ferryY + 2, 2, '#5d6d7e');

    // === AIRBORNE PARTICLES ===
    var particleCount = 10;
    var particles = [];
    var r = srand(1000);
    for (var i = 0; i < particleCount; i++) {
      particles.push({x: r() * W, y: r() * 70});
    }
    for (var p of particles) {
      circle(p.x, p.y, 1, rgba('#fff', 0.5));
      p.y += 0.2;
      if (p.y > 70) {
        p.x = r() * W;
        p.y = 0;
      }
    }

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#f0f7f4',0.3));
    rect(0,H-2,W,1,rgba('#d4edda',0.1));
  };
});