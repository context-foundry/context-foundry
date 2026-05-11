// Scene: Kubernetes Pod of Dolphins
// Kaikoura, South Island, New Zealand
window.CF.register("Kubernetes Pod of Dolphins", "Kaikoura, South Island, New Zealand", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,W=api.W,H=api.H;

  // Dolphin parameters
  var dolphins = [];
  for(var i = 0; i < 6; i++){
    dolphins.push({
      x: 50 + Math.random() * 360,
      y: 150 + Math.sin(i * 0.5) * 30,
      phase: Math.random() * Math.PI * 2,
      speed: 0.05 + Math.random() * 0.1
    });
  }

  // Whale parameters
  var whale = {
    x: 300,
    y: 100,
    phase: Math.random() * Math.PI * 2,
    breach: false
  };

  // Particle parameters for bubbles
  var bubbles = [];
  for(var i = 0; i < 20; i++){
    bubbles.push({
      x: Math.random() * W,
      y: H - 80 + Math.random() * 20,
      vy: -Math.random() * 0.5,
      life: 40 + Math.random() * 20
    });
  }

  return function(t){
    // Sky gradient
    for(var y = 0; y < 130; y++){
      var p = y / 130;
      rect(0, y, W, 1, lerp('#00b4d8', '#264653', p));
    }

    // Water gradient
    for(var y = 130; y < H; y++){
      var p = (y - 130) / (H - 130);
      rect(0, y, W, 1, lerp('#0077b6', '#90e0ef', p));
    }

    // Snow-capped Kaikouras
    var mountains = [40, 100, 160];
    for(var mx of mountains){
      rect(mx, 70, 20 + Math.random() * 30, 70, rgba('#e9ecef', 1));
      for(var j = 0; j < Math.floor(Math.random() * 3); j++){
        px(mx + Math.random() * 20, 70 - Math.random() * 10, '#ffffff');
      }
    }

    // Draw dolphins
    for(var d of dolphins){
      d.x += d.speed * 30;
      d.y = 150 + Math.sin(t * d.speed * 5 + d.phase) * 10;
      if(d.x > W) d.x = 0;
      // Draw dolphin body
      px(d.x, d.y, '#90e0ef');
      px(d.x - 1, d.y - 1, '#0077b6');
      px(d.x + 1, d.y - 1, '#0077b6');
      px(d.x, d.y - 1, '#0077b6');
      // Snout
      px(d.x + 2, d.y - 1, '#0077b6');
      // Fins
      px(d.x - 2, d.y, '#90e0ef');
    }

    // Draw whale
    var breachingHeight = Math.sin(t * 2) * 15;
    if (breachingHeight > 10) {
      whale.breach = true;
      whale.y = 90 - breachingHeight;
    } else {
      whale.breach = false;
      whale.y = 100;
    }
    px(whale.x, whale.y, '#264653');
    if (whale.breach) {
      px(whale.x, whale.y - 5, '#264653');
      px(whale.x + 1, whale.y - 5, '#264653');
    }

    // Draw fishing boat
    rect(120, H - 50, 50, 20, '#e9ecef');
    rect(130, H - 70, 10, 20, '#264653');
    rect(160, H - 70, 10, 20, '#264653');

    // Bubbles
    for(var b of bubbles){
      b.y += b.vy;
      b.life--;
      if(b.life <= 0 || b.y < 100){
        b.x = 50 + Math.random() * 380;
        b.y = H - 80 + Math.random() * 20;
        b.life = 40 + Math.random() * 20;
      }
      var a = b.life / 40;
      circle(b.x, b.y, 1, rgba('#ffffff', a * 0.8));
    }

    // Bottom glow line
    rect(0, H - 1, W, 1, rgba('#264653', 0.3));
    rect(0, H - 2, W, 1, rgba('#0077b6', 0.1));
  };
});