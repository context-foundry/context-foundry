// Scene: Aurora Borealis Broadcast
// Tromso, Norway
window.CF.register("Aurora Borealis Broadcast", "Tromso, Norway", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Pre-compute star field
  var stars=[];
  (function(){
    var r=srand(1001);
    for(var i=0;i<200;i++){
      stars.push({
        x:Math.floor(r()*W),y:Math.floor(r()*H*0.5),
        size:r()>0.95?2:(r()>0.85?1:1),
        baseAlpha:0.1+r()*0.9,
        period:1+r()*2,phase:r()*Math.PI*2
      });
    }
  })();

  // Pre-compute snow-covered pines
  var pines=[];
  (function(){
    var r=srand(2002);
    for(var i=0;i<50;i++){
      var x = Math.floor(r() * W);
      var height = 15 + Math.floor(r() * 20);
      pines.push({x: x, height: height});
    }
  })();

  // Wind direction for aurora animation
  var auroraWindOffset = 0;

  return function(t){
    // === NIGHT SKY ===
    rect(0, 0, W, H*0.5, rgba('#0b0c2a', 1));

    // === STARS ===
    for(var s of stars){
      var twinkle = osc(t, s.period, s.phase);
      var a = s.baseAlpha * 0.5 + s.baseAlpha * 0.5 * twinkle;
      var col = s.size === 2 ? '#00e5ff' : '#00ff87';
      if(s.size === 2){
        rect(s.x, s.y, 2, 2, rgba(col, a * 0.7));
        px(s.x, s.y, rgba(col, a));
        px(s.x + 1, s.y, rgba(col, a * 0.5));
      } else {
        px(s.x, s.y, rgba(col, a));
      }
    }

    // === AURORA BOREALIS ===
    auroraWindOffset += 0.03; // Slow horizontal motion
    for(var y=0; y<H*0.5; y+=2){
      var alpha = Math.cos((y/2 + auroraWindOffset) * 0.1) * 0.5 + 0.5;
      var col = lerp('#00ff87', '#7b2ff7', alpha);
      rect(0, y, W, 2, rgba(col, 0.5 * alpha));
    }

    // === FROZEN LAKE REFLECTION ===
    var lakeY = H*0.5 - 20;
    rect(0, lakeY, W, H*0.5, rgba('#0b0c2a', 0.8));
    for(var y=lakeY; y<H; y+=3){
      for(var x=0; x<W; x+=5){
        px(x + osc(t, 5, x) * 2, y, rgba('#1a1a5e', 0.1));
      }
    }

    // === SNOW-COVERED PINES ===
    for(var pine of pines){
      var baseY = H*0.5 + 20;
      for(var h=0; h<pine.height; h++){
        px(pine.x, baseY - h, '#00e5ff');
        if(h > 4){
          px(pine.x - 1, baseY - h, '#00ff87');
          px(pine.x + 1, baseY - h, '#00ff87');
        }
      }
    }

    // === BOTTOM GLOW FOR CONSISTENCY ===
    rect(0,H-1,W,1,rgba('#00e5ff',0.3));
    rect(0,H-2,W,1,rgba('#00e5ff',0.1));
  };
});