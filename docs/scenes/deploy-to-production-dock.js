// Scene: Deploy to Production Dock
// Container Port, Rotterdam, Netherlands
window.CF.register("Deploy to Production Dock", "Container Port, Rotterdam, Netherlands", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Cargo ship position
  var shipX = W / 3;
  var shipY = H - 50;

  // Crane and containers
  var containers = [];
  var containerColor = ['#e76f51', '#0077b6', '#264653', '#e9c46a', '#6c757d'];

  for(var i = 0; i < 5; i++){
    containers.push({
      x: 80 + i * 30,
      y: H - 100 - Math.floor(Math.random() * 60),
      color: containerColor[Math.floor(Math.random() * containerColor.length)]
    });
  }

  // Water ripples
  var ripples = [];
  for(var i = 0; i < 20; i++){
    ripples.push({
      x: Math.random() * W,
      y: H - 50 + Math.random() * 10,
      radius: 2 + Math.random() * 3,
      life: Math.floor(Math.random() * 30)
    });
  }

  return function(t){
    // Background gradient
    for(var y = 0; y < H; y += 2){
      var p = y / H;
      var col = lerp('#264653', '#0077b6', p);
      rect(0, y, W, 2, col);
    }

    // Water surface
    var waterHeight = H - 50 + Math.sin(t * 1.5) * 2;
    rect(0, waterHeight, W, 10, rgba('#0077b6', 0.6));

    // Ship
    rect(shipX, shipY, 100, 10, '#264653');
    rect(shipX + 20, shipY - 15, 20, 15, '#6c757d');
    rect(shipX + 50, shipY - 15, 20, 12, '#6c757d');

    // Cranes
    for(var i = 0; i < 3; i++){
      var craneBaseX = 50 + i * 150;
      rect(craneBaseX, H - 60, 10, 20, '#6c757d');
      rect(craneBaseX - 30, H - 60, 60, 5, '#6c757d');
    }

    // Draw containers
    for(var container of containers){
      rect(container.x, container.y, 25, 30, container.color);
    }

    // Ripples animation
    for(var ripple of ripples){
      if(ripple.life > 0){
        circle(ripple.x, ripple.y, ripple.radius, rgba('#ffffff', 0.1));
        ripple.life--;
        ripple.radius += Math.sin(t) * 0.05;
      } else {
        ripple.x = Math.random() * W;
        ripple.y = waterHeight + Math.random() * 10;
        ripple.radius = 2 + Math.random() * 3;
        ripple.life = 30 + Math.floor(Math.random() * 20);
      }
    }

    // Bottom glow line
    rect(0, H - 1, W, 1, rgba('#e9c46a', 0.4));
    rect(0, H - 2, W, 1, rgba('#e9c46a', 0.1));
  };
});