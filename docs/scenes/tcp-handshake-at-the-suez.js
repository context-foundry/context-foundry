// Scene: TCP Handshake at the Suez
// Suez Canal, Ismailia, Egypt
window.CF.register("TCP Handshake at the Suez", "Suez Canal, Ismailia, Egypt", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Initialize persistent state
  var ships=[];
  var sandParticles=[];
  var convoyLength=10;

  // Generate initial positions for the ships
  for(var i=0;i<5;i++){
    ships.push({
      x:-i*120,
      y:H/2,
      width:80,
      height:20,
      color:'#0077b6'
    });
  }

  // Generate initial positions for sand particles
  for(var i=0;i<50;i++){
    sandParticles.push({
      x:Math.random() * W,
      y:H - 20 + Math.random() * 20,
      life:Math.random() * 50 + 50
    });
  }

  return function(t){
    // === SKY (y: 0-100) ===
    for(var y=0;y<100;y++){
      rect(0,y,W,1,lerp('#264653','#f0f0f0',y/100));
    }

    // Distant horizon
    rect(0,100,W,40,rgba('#e9c46a',0.5));

    // === SANDY BANKS ===
    rect(0,H-20,W,-(H-20),rgba('#dda15e',0.8));
    rect(0,H-15,W,-(H-15),rgba('#dda15e',0.6));

    // === SHIPS ===
    for(var ship of ships){
      ship.x += 0.3; // Moving towards the right
      if(ship.x > W) ship.x = -80;
      rect(ship.x, ship.y, ship.width, ship.height, ship.color);
      // Container crates
      for(var j=0;j<4;j++){
        rect(ship.x + (j * 18), ship.y - 10, 12, 10, '#e9c46a');
      }
    }

    // === CONVOY QUEUE ===
    for(var j=0;j<convoyLength;j++){
      var convoyX = W/2 - j * 30;
      rect(convoyX, H-40, 20, 10, '#6c757d');
      rect(convoyX + 2, H-42, 16, 8, rgba('#0077b6', 0.6));
    }

    // === CANAL BRIDGE ===
    rect(W/2 - 80, H/2 - 20, 160, 10, '#6c757d');
    
    // === SAND PARTICLES ===
    for(var p of sandParticles){
      p.y -= 0.1; // Simulate drift
      p.life--;
      if(p.life <= 0){
        p.x = Math.random() * W;
        p.y = H - 20 + Math.random() * 20;
        p.life = Math.random() * 50 + 50;
      }
      var alpha = p.life / 100;
      px(p.x, p.y, rgba('#dda15e', alpha));
    }

    // BOTTOM GLOW
    rect(0,H-1,W,1,rgba('#264653',0.3));
    rect(0,H-2,W,1,rgba('#264653',0.1));
  };
});