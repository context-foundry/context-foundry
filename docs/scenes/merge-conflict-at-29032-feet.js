// Scene: Merge Conflict at 29,032 Feet
// Mount Everest, Nepal-China Border
window.CF.register("Merge Conflict at 29,032 Feet", "Mount Everest, Nepal-China Border", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Jet stream clouds
  var clouds = [];
  for(var i = 0; i < 10; i++){
    clouds.push({
      x: Math.random() * W,
      y: Math.random() * 50,
      speed: 0.1 + Math.random() * 0.2
    });
  }

  // South col tents
  var tents = [];
  for(var i = 0; i < 5; i++){
    tents.push({
      x: Math.random() * (W - 40) + 20,
      y: H - 70 - Math.random() * 20,
      color: i % 2 === 0 ? '#e9ecef' : '#adb5bd'
    });
  }

  // Prayer flags
  var flags = [];
  for(var i = 0; i < 4; i++){
    flags.push({
      x: 50 + i * 80,
      y: H - 110 + Math.sin(i) * 5,
      sway: Math.random() * 2,
      color: ['#264653', '#48cae4'][i % 2]
    });
  }

  return function(t){
    // Background gradient
    for(var y=0; y<H; y+=2){
      var p=y/H;
      var col=lerp('#264653', '#6c757d', p);
      rect(0, y, W, 2, col);
    }

    // Summit pyramid
    var peakColor = '#adb5bd';
    var peakX = W / 2;
    var peakY = 50;
    for(var x = -20; x <= 20; x++){
      for(var y = 0; y <= (20 - Math.abs(x)) * 2; y++){
        px(peakX + x, peakY - y, peakColor);
      }
    }

    // Draw clouds
    for(var cloud of clouds){
      cloud.x += cloud.speed;
      if(cloud.x > W) cloud.x = -20;
      rect(cloud.x, cloud.y, 40, 10, rgba('#ffffff', 0.5));
      rect(cloud.x + 10, cloud.y + 2, 20, 6, rgba('#e9ecef', 0.8));
    }

    // Draw tents
    for(var tent of tents){
      rect(tent.x, tent.y, 40, 20, tent.color);
      rect(tent.x + 10, tent.y + 10, 20, 10, rgba('#6c757d', 0.3));
    }

    // Draw prayer flags
    for(var flag of flags){
      flag.y += Math.sin(t + flag.sway) * 0.5;
      rect(flag.x, flag.y, 6, 2, flag.color);
      for(var i = 0; i < 4; i++){
        rect(flag.x + 6, flag.y + i * 4, 1, 1, flag.color);
      }
    }

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#48cae4',0.6));
    rect(0,H-2,W,1,rgba('#264653',0.3));
  };
});