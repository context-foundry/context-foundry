// Scene: Rooftop Container Garden
// Singapore Skyline, Marina Bay, Singapore
window.CF.register("Rooftop Container Garden", "Singapore Skyline, Marina Bay, Singapore", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Initialize persistent state
  var stars=[], cityLights=[], supertrees=[], sparkles=[];
  var r=srand(100);

  // Pre-compute stars
  for(var i=0;i<100;i++){
    stars.push({x:Math.random()*W, y:Math.random()*100, alpha:0.2+r()*0.8});
  }

  // Pre-compute city lights
  for(var i=0;i<150;i++){
    cityLights.push({x:Math.random()*W, y:Math.random()*(H-100)+100, blinkRate:0.1+r()*0.1});
  }

  // Pre-compute supertrees
  for(var i=0;i<4;i++){
    supertrees.push({x:100+100*i, y:H-40-Math.random()*20});
  }

  // Pre-compute sparkle particles
  for(var i=0;i<50;i++){
    sparkles.push({
      x:Math.random()*W,
      y:H-Math.random()*60-20,
      vy:-Math.random()*1.5,
      alpha:0.2+r()*0.5,
      size:2+Math.random()*3
    });
  }

  return function(t){
    // === SKY ===
    rect(0, 0, W, H, lerp('#0077b6', '#52b788', H/260));

    // === STARS ===
    for(var star of stars){
      px(star.x, star.y, rgba('#ffffff', star.alpha));
    }

    // === CITY LIGHTS ===
    for(var light of cityLights){
      var glow = Math.sin(t*light.blinkRate*10) * 0.6 + 0.4;
      px(light.x, light.y, rgba('#ffd166', glow));
    }

    // === SUPERTREE GROVE ===
    for(var tree of supertrees){
      // Draw tree trunk
      rect(tree.x, tree.y, 10, 20, '#7b2ff7');
      // Draw tree foliage
      rect(tree.x-20, tree.y-40, 40, 20, rgba('#95d5b2', 0.9));
      circle(tree.x, tree.y-45, 25, rgba('#52b788', 0.7));
    }

    // === MARINA BAY SANDS ===
    var mbsX = W - 200, mbsY = H - 60;
    rect(mbsX, mbsY, 150, 20, '#95d5b2');
    rect(mbsX-30, mbsY-40, 210, 40, '#0077b6');

    // === GARDEN TERRACES ===
    var terraceY = H - 80;
    for(var i=0;i<3;i++){
      rect(50 + i * 140, terraceY, 120, 15, '#52b788');
      circle(50 + i * 140 + 60, terraceY-10, 10, '#ffd166');
    }

    // === SPARKLES ===
    for(var sparkle of sparkles){
      sparkle.y += sparkle.vy;
      sparkle.alpha = Math.max(0, sparkle.alpha - 0.01);
      if(sparkle.y < 0){
        sparkle.y = H - Math.random()*60 - 20;
        sparkle.alpha = 0.2 + r() * 0.5;
      }
      circle(sparkle.x, sparkle.y, sparkle.size, rgba('#ffd166', sparkle.alpha));
    }

    // === BOTTOM GLOW ===
    rect(0, H-1, W, 1, rgba('#0077b6', 0.3));
    rect(0, H-2, W, 1, rgba('#0077b6', 0.1));
  };
});