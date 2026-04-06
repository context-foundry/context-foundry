// Scene: Mangrove Memory Leak
// Sundarbans, Bangladesh-India Border
window.CF.register("Mangrove Memory Leak", "Sundarbans, Bangladesh-India Border", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Initialize particle systems for mudflat crabs and tidal bubbles
  var crabs=[], bubbles=[];
  var mudflatHeight = H - 50; // Mudflat height can be adjusted
  for(var i=0; i<10; i++){
    crabs.push({x:Math.random()*480, y:mudflatHeight+Math.random()*20, life:60+Math.random()*120});
  }
  for(var i=0; i<30; i++){
    bubbles.push({x:Math.random()*480, y:mudflatHeight - Math.random()*10, vy:-0.1 - Math.random()*0.3, life:Math.random()*80 + 40});
  }

  function drawTiger(x, y) {
    // Draw a silhouette of a Bengal tiger
    ctx.fillStyle = '#2d6a4f'; // Tiger color
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(x - 10, y + 20);
    ctx.lineTo(x + 10, y + 20);
    ctx.lineTo(x, y);
    ctx.fill();
  }

  return function(t){
    // === SKY ===
    for(var y=0; y<H*0.5; y++){
      var p=y/(H*0.5);
      rect(0,y,W,1,lerp('#4FC3F7', '#E0F7FA', p));
    }
    
    // === TREES ===
    var treeCount = 15;
    for(var i=0; i<treeCount; i++){
      var treeX = Math.random() * W;
      var treeHeight = Math.random() * 40 + 30; 
      rect(treeX, H - treeHeight, 8, treeHeight, '#6b705c');
      circle(treeX + 4, H - treeHeight, 15, '#40916c');
    }

    // === TIDAL WATER ===
    for(var y=H*0.5; y<mudflatHeight; y++){
      var p = (y - (H*0.5)) / (mudflatHeight - (H*0.5));
      rect(0,y,W,1,lerp('#6b705c', '#2d6a4f', p));
    }

    // === BENGAL TIGER SILHOUETTE ===
    drawTiger(W/2 - 15, mudflatHeight - 30);

    // === MUDFLAT ===
    rect(0, mudflatHeight, W, H - mudflatHeight, '#b7b7a4');

    // === CRABS MOVEMENT ===
    for(var crab of crabs){
      if(crab.life > 0){
        px(crab.x, crab.y, '#4e5d6f'); // Color of a crab
        crab.x += (Math.random() - 0.5) * 0.5; 
        crab.y += Math.sin(t + crab.x * 0.03) * 0.1; 
        crab.life--;
      }
    }

    // === BUBBLES ===
    for(var bubble of bubbles){
      if(bubble.life > 0){
        bubble.y += bubble.vy;
        bubble.y = Math.max(bubble.y, mudflatHeight - 10);
        bubble.life--;
        circle(bubble.x, bubble.y, Math.sin(t * 2) * 2 + 2, rgba('#ffffff', 0.5));
      } else {
        // Reuse bubble when life is done
        bubble.x = Math.random() * W;
        bubble.y = mudflatHeight - Math.random() * 10;
        bubble.vy = -0.1 - Math.random() * 0.3;
        bubble.life = Math.random() * 80 + 40;
      }
    }

    // === ROOT SYSTEMS ===
    var roots = srand(101);
    for(var i=0; i<30; i++){
      var rootX = Math.random() * W;
      var rootY = mudflatHeight - Math.random() * 30;
      for(var j=0; j<10; j++){
        var offsetY = j * 2;
        var rWidth = Math.sin((t + j * 0.5) * 0.5) * 3;
        rect(rootX, rootY + offsetY, rWidth, 1, '#40916c');
      }
    }

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#a5a58d',0.3));
    rect(0,H-2,W,1,rgba('#b7b7a4',0.1));
  };
});