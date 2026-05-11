// Scene: Peak Performance Meadow
// Grindelwald, Bernese Alps, Switzerland
window.CF.register("Peak Performance Meadow", "Grindelwald, Bernese Alps, Switzerland", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Pre-compute flowers
  var flowers=[];
  var flowerColors = ['#ffd166', '#52b788', '#95d5b2'];
  var flowerCount = 50;
  var r = srand(1001);
  
  for (var i=0; i<flowerCount; i++) {
    flowers.push({
      x: Math.floor(r() * W),
      y: Math.floor(H - (r() * 40 + 180)),
      color: flowerColors[Math.floor(r() * flowerColors.length)],
      size: Math.floor(1 + r() * 2)
    });
  }

  // Cowbells
  var cows = [];
  for (var j = 0; j < 3; j++) {
    cows.push({
      x: Math.floor(r() * (W - 50)),
      y: H - 30 + Math.floor(r() * 20),
      bob: r() * Math.PI * 2,
      speed: 0.02 + r() * 0.02
    });
  }

  // Snow-capped Eiger
  var eigerBase = H - 80;
  var eigerHeight = 80;
  
  return function(t){
    // === SKY ===
    rect(0, 0, W, H * 0.5, '#264653'); // Sky color
    
    // === GRASS ===
    rect(0, H * 0.5, W, H * 0.5, '#95d5b2'); // Grass color

    // === SNOW-CAPPED EIGER ===
    for(var y = 0; y < eigerHeight; y++) {
      var peakWidth = Math.max(0, Math.floor((eigerHeight - y) / 2));
      for (var x = -peakWidth; x <= peakWidth; x++) {
        px(W/2 + x, eigerBase - y, y > 30 ? '#ffffff' : '#c0c0c0'); // Snow and rock
      }
    }

    // === FLOWERS ===
    for (var flower of flowers) {
      px(flower.x, flower.y, flower.color);
      for (var i = 1; i < flower.size; i++) {
        px(flower.x + i, flower.y, flower.color);
        px(flower.x - i, flower.y, flower.color);
      }
    }

    // === COWBELLS ===
    for (var cow of cows) {
      cow.bob += cow.speed;
      var bobOffset = Math.sin(cow.bob) * 2;
      rect(cow.x, cow.y + bobOffset, 10, 5, '#ffa500'); // Cow
      circle(cow.x + 5, cow.y - 3 + bobOffset, 3, '#3d3d3d'); // Bell
    }

    // === WOODEN CHALET ===
    var chaletX = 350;
    var chaletY = H - 120;
    rect(chaletX, chaletY, 30, 20, '#8B4513'); // Chalet body
    rect(chaletX + 5, chaletY - 10, 20, 10, '#deb887'); // Chalet roof

    // === ADDITIONAL GRASS DETAILS ===
    for (var x = 0; x < W; x += 2) {
      px(x, H - 1, '#52b788'); // Grass line
      if (x % 10 === 0) {
        px(x, H - 2, '#5f9ea0'); // Slight variation
      }
    }

    // === BOTTOM GLOW ===
    rect(0, H-1, W, 1, rgba('#ffd166', 0.3));
    rect(0, H-2, W, 1, rgba('#ffd166', 0.1));
  };
});