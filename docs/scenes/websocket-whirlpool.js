// Scene: WebSocket Whirlpool
// Corryvreckan Whirlpool, Scottish Inner Hebrides
window.CF.register("WebSocket Whirlpool", "Corryvreckan Whirlpool, Scottish Inner Hebrides", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Swirling tidal race particles
  var swirls=[];
  for(var i=0;i<100;i++){
    swirls.push({
      angle: Math.random() * Math.PI * 2,
      radius: 30 + Math.random() * 50,
      speed: 0.5 + Math.random() * 1,
      size: 2 + Math.random() * 2
    });
  }

  // Standing wave parameters
  var waveParams = [];
  for(var i=0; i<10; i++){
    waveParams.push({
      phase: Math.random() * Math.PI * 2,
      amplitude: 5 + Math.random() * 5,
      frequency: 0.02 + Math.random() * 0.05
    });
  }

  // Seabird positions and parameters
  var birds=[];
  for(var i=0; i<5; i++){
    birds.push({
      x: Math.random() * W,
      y: Math.random() * 40 + 20,
      speed: 0.5 + Math.random() * 0.5,
      direction: Math.random() > 0.5 ? 1 : -1
    });
  }

  return function(t){
    // Background gradient - deep ocean color
    for(var y=0; y<H; y++){
      var p = y / H;
      var col = lerp('#264653', '#2a9d8f', p);
      rect(0, y, W, 1, col);
    }

    // Standing waves
    for(var y=200; y<H; y+=5){
      for(var i=0; i<waveParams.length; i++){
        var wave = waveParams[i];
        var waveY = y + Math.sin(t * wave.frequency + wave.phase) * wave.amplitude;
        rect(0, waveY, W, 2, '#6c757d');
      }
    }

    // Tidal whirlpool effect
    for(var s of swirls){
      var x = W/2 + Math.cos(s.angle) * s.radius;
      var y = H/2 + Math.sin(s.angle) * s.radius;
      circle(x, y, s.size, '#48cae4');
      s.angle += s.speed;
      s.radius += Math.sin(t * 0.1) * 0.2; // effect to create fluctuation
    }

    // Sea cliff
    rect(0, H - 100, W, 100, '#264653'); // cliff color

    // Seagulls flying
    for(var bird of birds){
      bird.x += bird.speed * bird.direction;
      if(bird.x < 0 || bird.x > W) bird.direction *= -1; // bounce back
      var birdY = bird.y + Math.sin(t * bird.speed) * 2;
      px(bird.x, birdY, '#e9ecef');
      px(bird.x - 1, birdY - 1, '#e9ecef');
      px(bird.x + 1, birdY - 1, '#e9ecef');
    }

    // Bottom glow line
    rect(0, H-1, W, 1, rgba('#48cae4', 0.4));
    rect(0, H-2, W, 1, rgba('#48cae4', 0.1));
  };
});