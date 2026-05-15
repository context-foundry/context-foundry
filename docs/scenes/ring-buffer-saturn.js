// Scene: Ring Buffer Saturn
// Saturn's Rings, Outer Solar System
window.CF.register("Ring Buffer Saturn", "Saturn's Rings, Outer Solar System", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Initialize particle rings
  var particles=[];
  var random=srand(123);
  for(var i=0;i<100;i++){
    particles.push({
      z:random()*0.6, // depth for layering
      angle:random()*Math.PI*2,
      radius:80 + random()*40,
      speed:0.02 + random()*0.03,
      size:2 + random()*2
    });
  }

  // Initialize Titan moon
  var titan = {
    angle: random() * Math.PI * 2,
    distance: 200,
    speed: 0.005,
    size: 3
  };

  return function(t){
    // === BACKGROUND ===
    rect(0, 0, W, H, '#0b0c2a');

    // === SATURN ===
    var saturnSize = 60;
    var saturnX = W / 2;
    var saturnY = H / 2;
    circle(saturnX, saturnY, saturnSize, rgba('#caf0f8', 0.3));
    
    // Draw Saturn's atmosphere
    for (var i=0; i<10; i++) {
      circle(saturnX, saturnY, saturnSize + i, rgba('#e9c46a', 0.1 - i * 0.01));
    }

    // === RINGS ===
    for(var p of particles){
      var x = saturnX + Math.cos(p.angle) * p.radius;
      var y = saturnY + Math.sin(p.angle) * p.radius;
      px(Math.floor(x), Math.floor(y), rgba('#f4a261', 0.7));
      p.angle += p.speed;
      p.radius += Math.sin(t * p.speed) * 0.1; // slight oscillation
      if(p.radius > 120) p.radius = 80 + random() * 40; // reset ring
    }

    // === CASSINI DIVISION GAP ===
    for(var angle=0; angle<Math.PI*2; angle+=0.1){
      var x = saturnX + Math.cos(angle) * (saturnSize + 10);
      var y = saturnY + Math.sin(angle) * (saturnSize + 10);
      if (Math.abs(Math.sin(angle * 7)) < 0.1) continue; // skip for empty space
      px(Math.floor(x), Math.floor(y), '#0b0c2a');
    }

    // === TITAN MOON ===
    titan.angle += titan.speed;
    var titanX = saturnX + Math.cos(titan.angle) * titan.distance;
    var titanY = saturnY + Math.sin(titan.angle) * titan.distance;
    circle(titanX, titanY, titan.size, '#dda15e');

    // === STARS ===
    var starRandom=srand(456);
    for(var i=0;i<50;i++){
      var sx = starRandom() * W;
      var sy = starRandom() * H;
      var starSize = starRandom() < 0.5 ? 1 : 2;
      px(Math.floor(sx), Math.floor(sy), rgba('#e9c46a', starRandom() * 0.3));
      px(Math.floor(sx + 1), Math.floor(sy), rgba('#e9c46a', starRandom() * 0.2));
      px(Math.floor(sx), Math.floor(sy + 1), rgba('#e9c46a', starRandom() * 0.2));
    }

    // === BOTTOM GLOW LINE ===
    rect(0,H-1,W,1,rgba('#f4a261',0.4));
    rect(0,H-2,W,1,rgba('#f4a261',0.1));
  };
});