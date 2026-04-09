// Scene: Bridge Over Troubled Bandwidth
// Golden Gate Bridge, San Francisco, USA
window.CF.register("Bridge Over Troubled Bandwidth", "Golden Gate Bridge, San Francisco, USA", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Initialize fog and water waves
  var fog = [];
  var wave = [];
  (function(){
    var r = srand(1001);
    for(var i=0; i<300; i++){
      fog.push({
        x: r() * W,
        y: r() * (H-100),
        alpha: 0.15 + r() * 0.15
      });
    }
    for(var i=0; i<100; i++){
      wave.push({
        x: r() * W,
        y: H - 30 + r() * 5,
        speed: 0.5 + r() * 1
      });
    }
  })();

  // Initialize Marin headlands
  var headlands = [];
  (function(){
    var r = srand(2001);
    for(var x=0; x<W; x+=20){
      headlands.push({
        x: x,
        h: H - (150 + r() * 40)
      });
    }
  })();

  return function(t){
    // === BACKGROUND SKY ===
    rect(0, 0, W, H - 30, rgba('#f1faee', 1));
    
    // === FOG ROLLING IN ===
    for(var f of fog){
      f.y += 0.1 * Math.sin(t * 0.5 + f.x * 0.005);
      rect(f.x, f.y, 10, 1, rgba('#ffffff', f.alpha * osc(t, 3, f.x * 0.01)));
    }

    // === BAY WATER ===
    for(var w of wave){
      w.y += w.speed;
      if(w.y > H - 25) w.y = H - 30 + Math.random() * 5;
      px(w.x, w.y, rgba('#a8dadc', 0.8));
    }

    // === MARIN HEADLANDS ===
    for(var hl of headlands){
      var baseY = hl.h;
      for(var y=baseY; y<H; y++){
        var p = (y - baseY) / (H - baseY);
        px(hl.x, y, lerp('#457b9d', '#6c757d', p));
      }
      // Add texture
      if(Math.random() > 0.8) {
        px(hl.x + Math.floor(Math.random() * 20), baseY - Math.floor(Math.random() * 15), '#6c757d');
      }
    }

    // === GOLDEN GATE BRIDGE ===
    var bridgeHeight = 70;
    for(var x=0; x<W; x+=10){
      if(x % 40 === 0){
        rect(x - 2, H - bridgeHeight - 10, 4, 20, '#e63946'); // Towers
      }
      rect(x - 5, H - bridgeHeight, 10, 10, '#e63946'); // Bridge
    }

    // Suspension cables
    for(var x=20; x<W-20; x+=30){
      px(x, H - bridgeHeight - 10, '#e63946'); // Suspension cable
      px(x + 1, H - bridgeHeight - 10, '#e63946');
      px(x - 1, H - bridgeHeight - 10, '#e63946');
    }

    // Bottom glow line
    rect(0, H-1, W, 1, rgba('#e63946', 0.3));
    rect(0, H-2, W, 1, rgba('#457b9d', 0.1));
  };
});