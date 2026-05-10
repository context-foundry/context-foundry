// Scene: Delta Force Merge
// Mekong Delta, Vietnam
window.CF.register("Delta Force Merge", "Mekong Delta, Vietnam", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Precompute floating market boats
  var boats=[];
  function createBoat() {
    return {
      x: Math.random() * W,
      y: 200 + Math.random() * 40,
      width: 8 + Math.random() * 8,
      height: 4 + Math.random() * 4,
      floatSpeed: 0.02 + Math.random() * 0.03,
      waveOffset: Math.random() * Math.PI * 2
    };
  }
  for (var i = 0; i < 5; i++) {
    boats.push(createBoat());
  }

  // Palm trees
  var palms=[];
  function createPalm() {
    return {
      x: Math.random() * W,
      y: H - 40 - Math.random() * 20,
      height: 12 + Math.random() * 8
    };
  }
  for (var i = 0; i < 6; i++) {
    palms.push(createPalm());
  }

  // Waterway animations
  var waypoints = [];
  for (var i = 0; i < 50; i++) {
    waypoints.push({ x: (i / 50) * W, y: 180 + Math.sin(i * 0.15) * 10 });
  }

  return function(t){
    // Background gradient
    for (var y = 0; y < H; y++) {
      var p = y / H;
      rect(0, y, W, 1, lerp('#B7E4C7', '#74C69D', p));
    }

    // Waterway
    for (var i = 1; i < waypoints.length; i++) {
      px(waypoints[i-1].x, waypoints[i-1].y, '#2D6A4F');
      px(waypoints[i].x, waypoints[i].y, '#2D6A4F');
      waypoints[i].y += Math.sin(t * 0.5 + i) * 0.5;
    }

    // Floating market boats
    for (var boat of boats) {
      boat.y += Math.sin(t * boat.floatSpeed + boat.waveOffset);
      rect(boat.x - boat.width / 2, boat.y, boat.width, boat.height, '#40916C'); // Boat body
      circle(boat.x, boat.y - 2, 3, '#D4A373'); // Boat roof
    }

    // Palm trees
    for (var palm of palms) {
      for (var i = 0; i < palm.height; i++) {
        px(palm.x, palm.y - i, '#6A993A');
      }
      // Fronds
      for (var f = -2; f <= 2; f++) {
        px(palm.x + f, palm.y - palm.height + 3, '#40916C');
      }
    }

    // Rice paddies (foreground)
    for (var x = 0; x < W; x++) {
      for (var y = 220; y < H; y++) {
        var col = lerp('#D4A373', '#B7E4C7', (y - 220) / (H - 220));
        px(x, y, col);
      }
    }

    // Bottom glow line
    rect(0, H - 1, W, 1, rgba('#74C69D', 0.3));
    rect(0, H - 2, W, 1, rgba('#2D6A4F', 0.1));
  };
});