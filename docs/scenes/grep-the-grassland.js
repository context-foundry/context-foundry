// Scene: grep the Grassland
// Tallgrass Prairie, Flint Hills, Kansas, USA
window.CF.register("grep the Grassland", "Tallgrass Prairie, Flint Hills, Kansas, USA", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Grass parameters
  var grassCount = 200;
  var grasses = [];
  var bisonCount = 5;
  var bisons = [];

  // Pre-compute grass positions and heights
  var grassRandom = srand(555);
  for(var i = 0; i < grassCount; i++) {
    grasses.push({
      x: Math.floor(grassRandom() * W),
      height: Math.floor(grassRandom() * 25) + 10 // Height between 10 and 35
    });
  }

  // Pre-compute bison positions
  var bisonRandom = srand(666);
  for(var i = 0; i < bisonCount; i++) {
    bisons.push({
      x: Math.floor(bisonRandom() * W),
      y: H - 10 - Math.floor(bisonRandom() * 15),
      phase: bisonRandom() * Math.PI * 2,
      dir: bisonRandom() > 0.5 ? 1 : -1
    });
  }

  // Thunderhead cloud parameters
  var clouds = [];
  for (var i = 0; i < 3; i++) {
    clouds.push({
      x: Math.floor(bisonRandom() * W),
      y: Math.floor(bisonRandom() * 60),
      size: Math.floor(bisonRandom() * 30) + 15
    });
  }

  return function(t) {
    // === SKY (y: 0-80) ===
    for(var y = 0; y < 80; y++) {
      var p = y / 80;
      rect(0, y, W, 1, lerp('#fefae0', '#48cae4', p));
    }

    // === ROLLING HILLS ===
    for(var x = 0; x < W; x++) {
      var hillHeight = Math.sin(x * 0.03 + t) * 20 + 140;
      rect(x, hillHeight, 1, H - hillHeight, lerp('#606c38', '#bc6c25', (hillHeight / H)));
    }

    // === GRASS ===
    for (var grass of grasses) {
      for (var h = 0; h < grass.height; h++) {
        px(grass.x, H - 10 - h, '#606c38');
      }
    }

    // === BISON ===
    for (var bison of bisons) {
      bison.x += bison.dir * 0.2;
      if (bison.x < -20 || bison.x > W + 20) {
        bison.x = (bison.x < 0) ? W + 20 : -20;
      }
      var bisonY = bison.y + Math.sin(t + bison.phase) * 1.5;
      for(var dx = -5; dx <= 5; dx++) {
        for(var dy = -3; dy <= 0; dy++) {
          px(bison.x + dx, bisonY + dy, '#bc6c25');
        }
      }
    }

    // === THUNDERHEAD CLOUDS ===
    for(var cloud of clouds) {
      for(var dy = -4; dy <= 4; dy++) {
        for(var dx = -cloud.size; dx <= cloud.size; dx++) {
          if(dx * dx + dy * dy <= cloud.size * cloud.size) {
            px(cloud.x + dx, cloud.y + dy, rgba('#ddc4ad', 0.4));
          }
        }
      }
    }

    // === GROUND ===
    rect(0, H - 10, W, 10, '#dda15e');

    // REQUIRED: bottom glow line (brand consistency)
    rect(0, H - 1, W, 1, rgba('#fefae0', 0.3));
    rect(0, H - 2, W, 1, rgba('#dab86f', 0.1));
  };
});