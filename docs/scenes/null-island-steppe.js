// Scene: Null Island Steppe
// Mongolian Steppe, Khentii, Mongolia
window.CF.register("Null Island Steppe", "Mongolian Steppe, Khentii, Mongolia", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Grass particles
  var grasses=[];
  for(var i=0;i<100;i++){
    grasses.push({
      x: Math.random() * W, 
      y: H - 60 + Math.random() * 20,
      sway: Math.random() * Math.PI * 2 // Random sway angle
    });
  }

  // Wild horses (simple shapes)
  var horses=[];
  for(var i=0;i<5;i++){
    horses.push({
      x: Math.random() * (W - 80), 
      y: H - 50 + Math.random() * 20,
      phase: Math.random() * Math.PI * 2
    });
  }

  // Initialize eagles
  var eagles=[];
  for(var i=0;i<2;i++){
    eagles.push({
      x: Math.random() * W,
      y: Math.random() * 70,
      phase: Math.random() * Math.PI * 2
    });
  }

  // Ger tent position
  var gerX = W / 2 - 25;
  var gerY = H - 70;

  return function(t){
    // Clear the canvas with the sky color
    rect(0, 0, W, H, '#48cae4');

    // Draw the grassland background
    for(var i=0; i<H; i+=2){
      var col = lerp('#606c38', '#fefae0', i/H);
      rect(0, i, W, 2, col);
    }

    // Draw the ger tent
    rect(gerX, gerY, 50, 30, '#dda15e'); // body
    rect(gerX + 10, gerY - 10, 30, 10, '#fefae0'); // top
    rect(gerX + 20, gerY + 20, 10, 10, '#283618'); // door

    // Animate grass sway
    for(var grass of grasses){
      grass.y += Math.sin(t + grass.sway) * 0.5; // sway effect
      px(grass.x, grass.y, '#606c38'); // Draw grass
      px(grass.x + 1, grass.y, '#606c38'); // Add depth
      px(grass.x + 2, grass.y, '#606c38');
    }

    // Draw wild horses
    for(var horse of horses){
      horse.x += Math.sin(t + horse.phase) * 0.3; // slight horizontal movement
      horse.y += Math.sin(t + horse.phase) * 0.1; // slight vertical movement
      rect(horse.x, horse.y, 10, 4, '#fefae0'); // body
      rect(horse.x - 3, horse.y, 4, 2, '#283618'); // head
      rect(horse.x + 8, horse.y, 2, 1, '#606c38'); // tail
    }

    // Draw eagles
    for(var eagle of eagles){
      eagle.x += Math.cos(t + eagle.phase) * 0.5; // horizontal movement
      eagle.y += Math.sin(t + eagle.phase) * 0.3; // vertical movement
      px(eagle.x, eagle.y, '#283618'); // body
      px(eagle.x + 1, eagle.y - 1, '#fefae0'); // wing
      px(eagle.x - 1, eagle.y - 1, '#fefae0'); // wing
      if(eagle.x > W) { // Wrap around
        eagle.x = 0;
      }
      if(eagle.x < 0) {
        eagle.x = W;
      }
    }

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#48cae4',0.4));
    rect(0,H-2,W,1,rgba('#48cae4',0.2));
  };
});