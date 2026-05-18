// Scene: Hello World from Orbit
// International Space Station, Low Earth Orbit
window.CF.register("Hello World from Orbit", "International Space Station, Low Earth Orbit", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Solar panel state
  var panelLength = 80, panelWidth = 10;
  var panelAngle = Math.PI / 8;

  // City lights below
  var cityLights = [];
  var numLights = 400;
  var random = srand(1234);
  for (var i = 0; i < numLights; i++) {
    cityLights.push({
      x: Math.floor(random() * W),
      y: Math.floor(H - random() * 60),
      intensity: random() * 0.5 + 0.5
    });
  }

  return function(t){
    // === SPACE BACKGROUND ===
    rect(0, 0, W, H, '#0b0c2a');

    // === EARTH CURVATURE ===
    for (var x = 0; x < W; x++) {
      var y = H - Math.sqrt(250 * 250 - (x - W/2) * (x - W/2));
      var color;
      if (y < H) {
        color = lerp('#0b0c2a', '#023e8a', (y - H + 250) / 250);
        rect(x, y, 1, H - y, color);
      }
    }

    // === THIN ATMOSPHERE GLOW ===
    for (var a = 0; a < 70; a++) {
      var glowY = H - 250 + a * 0.04;
      var glowAlpha = 0.05 + Math.cos(a * 0.1 + t * 3) * 0.02;
      px(W/2, glowY, rgba('#48cae4', glowAlpha));
      rect(W/2 - a, glowY, a * 2, 1, rgba('#48cae4', glowAlpha));
      rect(W/2 + a, glowY, a * 2, 1, rgba('#48cae4', glowAlpha));
    }

    // === ISS SOLAR PANELS ===
    var issX = W/2 - 20;
    var issY = H - 120;
    for (var i = -1; i <= 1; i += 2) {
      ctx.save();
      ctx.translate(issX + 10, issY);
      ctx.rotate(panelAngle * i);
      rect(-panelLength / 2, -panelWidth / 2, panelLength, panelWidth, '#0077b6');
      ctx.restore();
    }
    rect(issX - 10, issY, 20, 10, '#f8f9fa'); // ISS body

    // === CITY LIGHTS BELOW ===
    for (var light of cityLights) {
      var alpha = light.intensity * 0.8;
      px(light.x, light.y, rgba('#f8f9fa', alpha));
      if (Math.random() < light.intensity * 0.01) {
        var flickerSize = Math.floor(random() * 3) + 1;
        for (var dy = -flickerSize; dy <= flickerSize; dy++) {
          for (var dx = -flickerSize; dx <= flickerSize; dx++) {
            if (dx*dx + dy*dy <= flickerSize*flickerSize) {
              var fx = light.x + dx;
              var fy = light.y + dy;
              if (fx >= 0 && fx < W && fy >= 0 && fy < H) {
                px(fx, fy, rgba('#f8f9fa', alpha * 0.3));
              }
            }
          }
        }
      }
    }

    // === BOTTOM GLOW LINE ===
    rect(0, H-1, W, 1, rgba('#48cae4', 0.3));
    rect(0, H-2, W, 1, rgba('#48cae4', 0.1));
  };
});