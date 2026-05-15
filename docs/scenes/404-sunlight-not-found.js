// Scene: 404: Sunlight Not Found
// Eisriesenwelt Ice Cave, Werfen, Austria
window.CF.register("404: Sunlight Not Found", "Eisriesenwelt Ice Cave, Werfen, Austria", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Ice columns
  var iceColumns=[];
  (function(){
    var r=srand(1001);
    for(var i=0;i<10;i++){
      var x=Math.floor(r()*W);
      var height=Math.floor(r()*50)+30;
      iceColumns.push({x:x,baseY:H,height:height});
    }
  })();

  // Icicle formations
  var icicles=[];
  (function(){
    var r=srand(2002);
    for(var i=0;i<60;i++){
      var x=Math.floor(r()*W);
      var y=Math.floor(r()*H);
      var length=Math.floor(r()*15)+5;
      icicles.push({x:x,baseY:y,length:length});
    }
  })();

  // Frozen waterfall
  var waterfallParticles=[];
  (function(){
    var r=srand(3003);
    for(var i=0;i<100;i++){
      waterfallParticles.push({
        x:Math.floor(r()*W), y:Math.floor(r()*50)+150,
        vy:Math.random()*1 + 0.5,
        alpha:0.5+Math.random()*0.3
      });
    }
  })();

  return function(t){
    // === CAVE BACKGROUND ===
    for(var y=0;y<H;y++){
      var p=y/H;
      rect(0,y,W,1,lerp('#0b0c2a','#1a3a5e',p));
    }

    // === ICE COLUMNS ===
    for(var col of iceColumns){
      for(var h=0;h<col.height;h++){
        px(col.x,col.baseY-h,'#48cae4');
      }
    }

    // === ICICLE FORMATIONS ===
    for(var icicle of icicles){
      for(var l=0;l<icicle.length;l++){
        px(icicle.x,icicle.baseY-l,'#caf0f8');
      }
    }

    // === FROZEN WATERFALL ===
    for(var p of waterfallParticles){
      p.y += p.vy;
      if(p.y > H){
        p.y = 0;
        p.x = Math.floor(Math.random()*W);
      }
      var alpha = p.alpha * Math.sin(t * 2 + p.x * 0.1);
      px(p.x, p.y, rgba('#ffffff',alpha));
    }

    // === CAVE ENTRANCE GLOW ===
    for(var i=0;i<W;i++){
      var glow = osc(t,10,(i * 0.05)) * 0.5;
      px(i,0,rgba('#caf0f8',glow * 0.5));
    }

    // === BOTTOM GLOW LINE ===
    rect(0,H-1,W,1,rgba('#48cae4',0.3));
    rect(0,H-2,W,1,rgba('#caf0f8',0.1));
  };
});