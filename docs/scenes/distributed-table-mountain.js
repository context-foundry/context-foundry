// Scene: Distributed Table Mountain
// Table Mountain, Cape Town, South Africa
window.CF.register("Distributed Table Mountain", "Table Mountain, Cape Town, South Africa", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Pre-compute cloud positions
  var clouds = [];
  var cloudCount = 5;
  (function(){
    var r = srand(1000);
    for(var i=0; i < cloudCount; i++){
      clouds.push({
        x: r() * W,
        y: 10 + r() * 20,
        size: 10 + r() * 30
      });
    }
  })();

  // Pre-compute city lights
  var cityLights = [];
  (function(){
    var r = srand(2000);
    for(var i=0; i < 100; i++){
      cityLights.push({
        x: Math.floor(r() * (W - 50)),
        y: Math.floor(r() * (H - 100)) + 150,
        size: r() * 3 + 1
      });
    }
  })();

  // Cable car state
  var carX = -20, carY = 120, carSpeed = 1;

  return function(t){
    // === SKY ===
    rect(0, 0, W, H, rgba('#264653', 1));
    
    // === CLOUDS ===
    for(var cloud of clouds){
      rect(cloud.x, cloud.y, cloud.size, 10, rgba('#ffffff', 0.6));
    }

    // Move clouds down
    for(var cloud of clouds){
      cloud.y += 0.1;
      if(cloud.y > H) {
        cloud.y = 0;
        cloud.x = Math.random() * W;
      }
    }

    // === MOUNTAIN ===
    var baseY = 150;
    for(var x = 0; x < W; x++){
      var peak = Math.sin((x / W) * Math.PI * 2) * 40; // Peak height
      px(x, baseY - peak, '#6c757d'); // Mountain color
      for(var y = baseY - peak + 1; y < baseY; y++){
        px(x, y, '#264653'); // Mountain base
      }
    }

    // === FLAT SUMMIT PLATEAU ===
    var plateauHeight = 10;
    rect(0, baseY - 24, W, plateauHeight, '#e9c46a');

    // === CABLE CAR ===
    carX += carSpeed;
    if(carX > W + 20) {
      carX = -20;
      carY = 120 + Math.sin(carX * 0.1) * 10; // Random drop effect
    }
    rect(carX, carY, 11, 4, '#2a9d8f'); // Cable car rectangle
    px(carX + 5, carY - 3, '#e9c46a'); // Window light

    // === CITY LIGHTS ===
    for(var light of cityLights){
      rect(light.x, light.y, light.size, light.size, rgba('#ffffff', 0.8));
    }

    // === BOTTOM GLOW ===
    rect(0, H - 1, W, 1, rgba('#2a9d8f', 0.3));
    rect(0, H - 2, W, 1, rgba('#264653', 0.1));
  };
});