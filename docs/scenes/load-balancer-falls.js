// Scene: Load Balancer Falls
// Victoria Falls, Zambia-Zimbabwe Border
window.CF.register("Load Balancer Falls", "Victoria Falls, Zambia-Zimbabwe Border", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Initialize rain particles
  var rain = [];
  for(var i = 0; i < 100; i++){
    rain.push({
      x: Math.random() * W,
      y: Math.random() * H,
      speed: 2 + Math.random() * 3,
      life: Math.floor(Math.random() * 60) + 20
    });
  }

  // Initialize mist particles
  var mist = [];
  for(var i = 0; i < 50; i++){
    mist.push({
      x: Math.random() * W,
      y: Math.random() * (H - 100),
      speed: Math.random() * 0.5 + 0.1,
      life: Math.floor(Math.random() * 40) + 10
    });
  }

  return function(t){
    // Background gradient for sky
    for(var y = 0; y < H; y++){
      var p = y / H;
      rect(0, y, W, 1, lerp('#90e0ef', '#1b4332', p));
    }

    // Draw water curtain
    var waterfallBase = H - 80;
    var waterfallHeight = 220 + Math.sin(t * 2) * 20;
    for(var x = 140; x <= 340; x++){
      for(var y = waterfallBase; y < waterfallBase + waterfallHeight; y++){
        px(x, y, '#ffffff');
      }
    }

    // Draw rainbow
    for(var r = 10; r >= 1; r--){
      var alpha = 0.1;
      rect(190 - r, waterfallBase + waterfallHeight - r * 10, 260 + r * 2, 8, rgba('#48cae4', alpha));
    }

    // Draw mist rising
    for(var m of mist){
      m.y -= m.speed;
      if(m.y < 0) m.y = H - Math.random() * 50;
      px(m.x, m.y, rgba('#ffffff', 0.2));
    }

    // Draw baobab tree
    var baobabX = 80, baobabY = 150;
    rect(baobabX - 10, baobabY, 20, 50, '#2d6a4f'); // trunk
    var fronds = [-20, -10, 0, 10, 20];
    for(var f of fronds){
      circle(baobabX + f, baobabY - 20, 15, '#48cae4'); // leaves
    }

    // Draw rain
    for(var r of rain){
      if(r.life > 0){
        r.y += r.speed;
        if(r.y > H) r.y = 0;
        px(r.x, r.y, rgba('#1b4332', 0.6));
        r.life--;
      }
    }

    // Draw thunderous atmosphere
    for(var i = 0; i < 20; i++){
      var x = Math.random() * W;
      var y = Math.random() * H;
      var opacity = Math.random() * 0.8 + 0.2;
      px(x, y, rgba('#ffffff', opacity));
    }

    // Bottom glow line
    rect(0, H - 1, W, 1, rgba('#90e0ef', 0.3));
    rect(0, H - 2, W, 1, rgba('#2d6a4f', 0.1));
  };
});