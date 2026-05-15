// Scene: The Original Cloud Computing
// Monteverde Cloud Forest, Costa Rica
window.CF.register("The Original Cloud Computing", "Monteverde Cloud Forest, Costa Rica", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,W=api.W,H=api.H;

  // Persistent data
  var mossSprites = [];
  var fogSprites = [];
  var orchids = [];
  var birds = [];
  var mossCount = 15;
  var fogCount = 10;
  var orchidCount = 5;
  var birdCount = 3;

  var mossSeed = srand(1);
  var fogSeed = srand(2);
  var orchidSeed = srand(3);
  var birdSeed = srand(4);

  // Generate moss positions
  for(var i = 0; i < mossCount; i++){
    mossSprites.push({x: mossSeed() * W, y: H - 50 - mossSeed() * 40});
  }

  // Generate fog positions
  for(var i = 0; i < fogCount; i++){
    fogSprites.push({x: fogSeed() * W, y: H - 120 - fogSeed() * 20, offset: fogSeed() * 20});
  }

  // Generate orchids positions
  for(var i = 0; i < orchidCount; i++){
    orchids.push({x: orchidSeed() * W, y: H - 70 - orchidSeed() * 40});
  }

  // Generate birds positions
  for(var i = 0; i < birdCount; i++){
    birds.push({x: birdSeed() * W, y: H - 150 - birdSeed() * 30, phase: birdSeed() * Math.PI * 2});
  }

  return function(t){
    // Background gradient
    for(var y = 0; y < H; y++){
      var p = y / H;
      var col = lerp('#b7e4c7', '#95d5b2', p);
      rect(0, y, W, 1, col);
    }

    // Draw fog
    for(var fog of fogSprites){
      var fogOpacity = osc(t * 2, 1, fog.offset) * 0.4;
      rect(fog.x, fog.y, W * 0.1, 1, rgba('#e9edc9', fogOpacity));
    }

    // Draw moss
    for(var moss of mossSprites){
      rect(moss.x, moss.y, 5, 2, '#74c69d');
    }

    // Draw orchid clusters
    for(var orchid of orchids){
      rect(orchid.x, orchid.y, 8, 5, '#ccd5ae');
      px(orchid.x + 2, orchid.y + 2, '#e9edc9');
      px(orchid.x + 3, orchid.y + 2, '#e9edc9');
    }

    // Draw quetzal birds
    for(var bird of birds){
      bird.x += Math.sin(t + bird.phase) * 0.5; // Horizontal movement
      bird.y += Math.sin(t * 1.5 + bird.phase) * 0.2; // Vertical bobbing
      rect(bird.x, bird.y, 7, 3, '#4a8e1d'); // Body
      px(bird.x + 1, bird.y - 2, '#e9edc9'); // Head
      px(bird.x + 6, bird.y + 0.5, '#4a8e1d'); // Tail
    }

    // Bottom glow line
    rect(0, H - 1, W, 1, rgba('#95d5b2', 0.4));
    rect(0, H - 2, W, 1, rgba('#b7e4c7', 0.1));
  };
});
