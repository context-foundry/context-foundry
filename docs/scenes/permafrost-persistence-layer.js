// Scene: Permafrost Persistence Layer
// Siberian Tundra, Yakutsk, Russia
window.CF.register("Permafrost Persistence Layer", "Siberian Tundra, Yakutsk, Russia", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Musk ox herd settings
  var muskOxen = [];
  var oxCount = 5;
  for(var i = 0; i < oxCount; i++) {
    muskOxen.push({
      x: Math.random() * W, 
      y: H - 40 + Math.random() * 10, 
      direction: Math.random() < 0.5 ? -1 : 1,
      offset: Math.random() * Math.PI * 2
    });
  }

  // Low clouds
  var cloudCount = 15;
  var clouds = [];
  for (var i = 0; i < cloudCount; i++) {
    clouds.push({
      x: Math.random() * W,
      y: Math.random() * 40,
      speed: Math.random() * 0.2 + 0.1
    });
  }
  
  return function(t) {
    // === SKY (y: 0-60) ===
    for (var y = 0; y < 61; y++) {
      var p = y / 60;
      rect(0, y, W, 1, lerp('#adb5bd', '#6c757d', p));
    }

    // === PERMAFROST CLIFF ===
    rect(0, H - 50, W, 50, '#495057');
    for (var x = 0; x < W; x += 5) {
      px(x, H - 50 - (Math.sin(x * 0.1) * 5), '#343a40');
    }

    // === FLAT TUNDRA EXPANSE ===
    rect(0, H - 1, W, 1, '#e9ecef');

    // === LOW CLOUDS ===
    for (var cloud of clouds) {
      cloud.x += cloud.speed;
      if (cloud.x > W) cloud.x = -20;
      for (var dx = -30; dx <= 30; dx += 2) {
        var opacity = Math.max(0, 0.1 - Math.abs(dx) / 30);
        px(cloud.x + dx, cloud.y, rgba('#adb5bd', opacity));
      }
    }

    // === MUSK OX HERD ===
    for (var ox of muskOxen) {
      ox.x += ox.direction * 0.2;
      if (ox.x < -20 || ox.x > W + 20) {
        ox.x = Math.random() * W;
        ox.y = H - 40 + Math.random() * 10;
        ox.direction = ox.direction === 1 ? -1 : 1;
      }
      // Draw the musk ox body
      for (var bx = -3; bx <= 3; bx++) {
        for (var by = -1; by <= 1; by++) {
          if (bx * bx + by * by < 9) px(ox.x + bx, ox.y + by, '#495057');
        }
      }
      // Draw the musk ox head
      circle(ox.x, ox.y - 2, 2, '#6c757d');
      // Add some movement to the oxen
      ox.y += Math.sin(t + ox.offset) * 0.1;
      if (ox.y < H - 40) ox.y = H - 40; // limit their position
    }

    // === BOTTOM GLOW LINE ===
    rect(0, H - 1, W, 1, rgba('#343a40', 0.3));
    rect(0, H - 2, W, 1, rgba('#adb5bd', 0.1));
  };
});