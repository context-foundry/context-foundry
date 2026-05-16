// Scene: Rebase the Reef
// Great Barrier Reef, Australia
window.CF.register("Rebase the Reef", "Great Barrier Reef, Australia", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Coral structure
  var corals=[];
  for(var i=0;i<8;i++){
    corals.push({
      x:60 + Math.random() * 360,
      y:H - 50 - Math.random() * 40,
      size:10 + Math.random() * 20,
      sway:Math.random() * Math.PI,
    });
  }

  // Clownfish
  var clownfish=[
    {x:100, y:180, vx:0.3, direction:1},
    {x:120, y:170, vx:0.4, direction:-1},
    {x:140, y:190, vx:0.3, direction:1},
  ];

  // Sea Turtle
  var turtle={x:300, y:200, vx:0.2};

  return function(t){
    // === OCEAN BACKGROUND ===
    for(var y=0; y<H; y++){
      var p=y/H;
      var col=lerp('#0077b6', '#00b4d8', p);
      rect(0,y,W,1,col);
    }

    // === SUNLIGHT RAYS ===
    var sunX = W * 0.5, sunY = 60;
    for(var r=0; r<15; r++){
      var angle = r * (Math.PI / 15);
      var sx = sunX + Math.cos(angle) * 250;
      var sy = sunY + Math.sin(angle) * 250;
      var alpha = 0.1 * (1 - (r / 15));
      ctx.save();
      ctx.globalAlpha = alpha;
      rect(sunX, sunY, sx-sunX, sy-sunY, rgba('#ffd166', alpha));
      ctx.restore();
    }

    // === DRAW CORAL ===
    for(var coral of corals){
      coral.y += Math.sin(t + coral.sway) * 0.2;
      coral.y = Math.min(coral.y, H - 50);
      rect(coral.x, coral.y, coral.size, coral.size * 0.6, '#90e0ef');
      for(var k=0; k<3; k++){
        var branchX = coral.x + Math.random() * coral.size - (coral.size / 2);
        var branchY = coral.y - (k * 4);
        px(branchX, branchY, '#ff6b6b');
      }
    }

    // === MOVE AND DRAW CLOWNFISH ===
    for(var fish of clownfish){
      fish.x += fish.vx * fish.direction;
      if(fish.x < 80 || fish.x > 180) fish.direction *= -1; // Bounce
      px(fish.x, fish.y, '#FF6B6B');
      px(fish.x+1, fish.y, rgba('#FF6B6B', 0.8));
    }

    // === MOVE AND DRAW SEA TURTLE ===
    turtle.x += turtle.vx;
    if(turtle.x > W + 20) turtle.x = -20;
    px(turtle.x, turtle.y, '#90e0ef');
    circle(turtle.x, turtle.y-3, 5, '#00b4d8');

    // === BUBBLES ===
    for(var i=0; i<3; i++){
      var bubbleX = Math.random() * W;
      for(var j=0; j<3; j++){
        var bubbleY = H - 10 - Math.random() * 20;
        circle(bubbleX, bubbleY, 1 + Math.random() * 2, rgba('#ffffff', 0.4));
      }
    }

    // REQUIRED: bottom glow line
    rect(0,H-1,W,1,rgba('#0077b6',0.3));
    rect(0,H-2,W,1,rgba('#0077b6',0.1));
  };
});