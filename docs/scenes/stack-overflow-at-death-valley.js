// Scene: Stack Overflow at Death Valley
// Badwater Basin, Death Valley, California, USA
window.CF.register("Stack Overflow at Death Valley", "Badwater Basin, Death Valley, California, USA", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,W=api.W,H=api.H;

  // Initialize variables for salt flats and heat shimmer
  var hexagons=[], shimmers=[];

  // Generate salt flat hexagons
  function generateHexagons() {
    var hexSize = 20;
    for (var x = 0; x < W; x += hexSize * 1.5) {
      for (var y = 100; y < H; y += Math.sqrt(3) * hexSize) {
        hexagons.push({x: x, y: y});
      }
    }
  }

  // Generate heat shimmer
  function generateShimmers() {
    for (var i = 0; i < 15; i++) {
      shimmers.push({
        x: Math.random() * W,
        y: Math.random() * 40 + 180,
        amplitude: Math.random() * 15 + 5,
        speed: Math.random() * 0.2 + 0.1
      });
    }
  }

  generateHexagons();
  generateShimmers();

  return function(t){
    // Clear background
    rect(0, 0, W, H, '#e5e5e5');

    // Draw the cracked earth texture
    var crackDensity = 300;
    for (var i = 0; i < crackDensity; i++) {
      var x = Math.random() * W;
      var y = Math.random() * (H - 50) + 100;
      if (Math.random() < 0.1) {
        px(x, y, '#073b4c');
        if (Math.random() < 0.5) {
          for (var j = -2; j <= 2; j++) {
            px(x + j, y, '#f78c6b');
          }
        }
      }
    }

    // Draw salt flat hexagons
    for (var hex of hexagons) {
      var cx = hex.x, cy = hex.y;
      for (var i = 0; i < 6; i++) {
        var angle = Math.PI / 3 * i;
        var xOffset = Math.cos(angle) * 20;
        var yOffset = Math.sin(angle) * 20;
        if (i === 0) {
          px(cx + xOffset, cy + yOffset, '#ffd166');
        }
        if (i > 0) {
          px(cx + xOffset, cy + yOffset, '#ef476f');
        }
      }
    }

    // Draw Telescope Peak (background)
    for (var i = 0; i < 150; i++) {
      var peakX = (W / 3) - 30 + Math.random() * 100;
      var peakY = 30 + Math.random() * 20;
      px(peakX, 80 + peakY, '#f78c6b');
    }

    // Draw heat shimmer effect
    for (var shimmer of shimmers) {
      shimmer.y += shimmer.speed;
      if (shimmer.y > H) shimmer.y = Math.random() * 40 + 180;
      var shimmerIntensity = osc(t * 1.5, shimmer.amplitude, shimmer.y) * 0.5;
      circle(shimmer.x, shimmer.y, shimmerIntensity, rgba('#ffd166', 0.3));
    }

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#ffd166',0.4));
    rect(0,H-2,W,1,rgba('#ffd166',0.1));
  };
});