// Scene: Oasis Dependency Injection
// Huacachina Oasis, Ica, Peru
window.CF.register("Oasis Dependency Injection", "Huacachina Oasis, Ica, Peru", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Constants for colors
  var colors = {
    lagoon: '#fefae0',
    duneLight: '#dda15e',
    duneDark: '#bc6c25',
    palmTrunk: '#606c38',
    palmFrond: '#283618',
    building: '#fefae0',
    roof: '#bc6c25',
  };

  // Palm trees data
  var palms = [];
  for (var i = 0; i < 8; i++) {
    palms.push({
      x: 50 + i * 45 + Math.sin(i) * 20,
      y: H - 100 - Math.random() * 30,
      sway: Math.random() * Math.PI * 2,
    });
  }

  // Paddle boats data
  var boats = [];
  for (var i = 0; i < 4; i++) {
    boats.push({
      x: 100 + i * 80,
      y: H - 80 + Math.sin(i) * 10,
      phase: Math.random() * Math.PI,
    });
  }

  return function(t) {
    // Draw the sky gradient
    for (var y = 0; y < H - 100; y++) {
      var p = y / (H - 100);
      rect(0, y, W, 1, lerp('#efefef', '#b0d8d8', p));
    }

    // Draw sand dunes
    for (var y = H - 100; y < H; y++) {
      for (var x = 0; x < W; x++) {
        var duneHeight = Math.sin((x + t * 10) * 0.03) * 5;
        var pColor = (y%10 === 0) ? colors.duneDark : colors.duneLight;
        px(x, y, pColor);
        if (y < H - duneHeight) {
          px(x, y, rgba(colors.duneLight, 0.2));
        }
      }
    }

    // Draw water lagoon
    rect(100, H - 80, 280, 70, colors.lagoon);
    rect(100, H - 60, 280, 10, rgba(colors.lagoon, 0.6));

    // Draw palm trees
    for (var palm of palms) {
      var swayOffset = Math.sin(t + palm.sway) * 2;
      var trunkHeight = 40;
      // Draw trunk
      rect(palm.x, palm.y, 5, trunkHeight, colors.palmTrunk);
      // Draw fronds
      for (var j = 0; j < 3; j++) {
        px(palm.x + swayOffset + j * 2, palm.y - j * 10, colors.palmFrond);
        px(palm.x - swayOffset - j * 2, palm.y - j * 10, colors.palmFrond);
      }
    }

    // Draw adobe buildings
    for (var i = 0; i < 3; i++) {
      var buildingX = 50 + i * 120;
      var buildingY = H - 120 + Math.random() * 40;
      rect(buildingX, buildingY, 60, 60, colors.building);
      rect(buildingX - 10, buildingY - 10, 80, 10, colors.roof);
    }

    // Draw paddle boats
    for (var boat of boats) {
      boat.y += Math.sin(t + boat.phase) * 0.5;
      rect(boat.x, boat.y, 40, 12, rgba(colors.lagoon, 0.8));
      // Boat oar
      px(boat.x + 20, boat.y - 2, colors.palmTrunk);
    }

    // Bottom glow line
    rect(0, H - 1, W, 1, rgba('#fefae0', 0.3));
    rect(0, H - 2, W, 1, rgba('#fefae0', 0.1));
  };
});