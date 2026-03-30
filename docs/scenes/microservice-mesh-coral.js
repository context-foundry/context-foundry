// Scene: Microservice Mesh Coral
// Tubbataha Reef, Sulu Sea, Philippines
window.CF.register("Microservice Mesh Coral", "Tubbataha Reef, Sulu Sea, Philippines", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Pre-compute coral structures
  var corals = [];
  for (var i = 0; i < 5; i++) {
    corals.push({ 
      x: 40 + i * 80 + Math.random() * 20, 
      y: H - 70 - Math.random() * 10, 
      size: 10 + Math.random() * 15, 
      phase: Math.random() * Math.PI * 2 
    });
  }

  // Pre-compute fish schools
  var fishSchools = [];
  for (var i = 0; i < 3; i++) {
    fishSchools.push({
      count: 5 + Math.floor(Math.random() * 5),
      baseY: 120 + Math.random() * 20,
      phase: Math.random() * Math.PI * 2,
      fishData: []
    });
    for (var j = 0; j < fishSchools[i].count; j++) {
      fishSchools[i].fishData.push({ 
        x: Math.random() * 100 + i * 160, 
        y: fishSchools[i].baseY + Math.sin(j) * 2 
      });
    }
  }

  // Shark patrol variables
  var sharkX = Math.random() * W;
  var sharkY = Math.random() * (H - 70) + 40;
  var sharkSpeed = 0.1 + Math.random() * 0.1;

  return function(t) {
    // === SKY ===
    rect(0, 0, W, 80, rgba('#00b4d8', 1));
    
    // === OCEAN GRADIENT ===
    for (var y = 80; y < 180; y++) {
      var p = (y - 80) / 100;
      rect(0, y, W, 1, lerp('#0077b6', '#00b4d8', p));
    }

    // === REEF DROP-OFF ===
    for (var y = 180; y < H; y++) {
      var col = rgba('#52b788', 0.6 + Math.sin(t * 0.1 + y * 0.05) * 0.1);
      rect(0, y, W, 1, col);
    }

    // === TABLE CORALS ===
    for (var c of corals) {
      var coralHeight = Math.sin(t * 0.5 + c.phase) * 2 + c.size;
      for (var w = -c.size; w <= c.size; w++) {
        for (var h = 0; h <= coralHeight; h++) {
          px(c.x + w, c.y - h, rgba('#ffd166', 0.9 - Math.abs(w) * 0.1));
        }
      }
    }

    // === ANTHIAS SCHOOL ===
    for (var school of fishSchools) {
      for (var fish of school.fishData) {
        fish.x += Math.sin(t * 2 + school.phase) * 0.3;
        fish.y += Math.cos(t * 2 + school.phase) * 0.1;
        px(fish.x, fish.y, '#ff6b6b');
        px(fish.x - 1, fish.y, '#ff6b6b');
      }
    }

    // === REEF SHARK PATROL ===
    sharkX += sharkSpeed;
    if (sharkX > W) sharkX = -20; // Reset shark position
    sharkY += Math.sin(t * 0.5) * 1; // Shark vertical movement
    circle(sharkX, sharkY, 4, rgba('#ffd166', 0.8));
    
    // === LIGHT RAYS ===
    for (var i = 0; i < 5; i++) {
      var rayX = Math.random() * W;
      var rayY = Math.random() * 30 + 60;
      for (var dy = 0; dy < 40; dy++) {
        rect(rayX - 1, rayY + dy, 2, 1, rgba('#ffffff', 0.02 * (40 - dy) / 40));
      }
    }

    // Bottom glow line
    rect(0, H - 1, W, 1, rgba('#0077b6', 0.3));
    rect(0, H - 2, W, 1, rgba('#005f73', 0.15));
  };
});