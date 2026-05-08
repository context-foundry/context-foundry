// Scene: Every Commit Reaches the Stars
// Mauna Kea Observatory, Hawaii, USA
window.CF.register("Every Commit Reaches the Stars", "Mauna Kea Observatory, Hawaii, USA", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Pre-compute star field
  var stars=[];
  (function(){
    var r=srand(1001);
    for(var i=0;i<300;i++){
      stars.push({
        x:Math.floor(r()*W),y:Math.floor(r()*H*0.6),
        size:r()>0.95?3:(r()>0.8?2:1),
        baseAlpha:0.1+r()*0.9,
        period:1+r()*3,phase:r()*Math.PI*2
      });
    }
  })();
  
  // Observatories
  var observatories = [
    {x:120, y:H-50, width:40, height:20},
    {x:300, y:H-50, width:45, height:25},
    {x:400, y:H-50, width:35, height:20}
  ];

  // Cinder cone summit
  var coneX = 250, coneTopY = 110, coneHeight = 120;

  return function(t){
    // === NIGHT SKY BACKGROUND ===
    rect(0,0,W,H,rgba('#0b0c2a',1));

    // === MILKY WAY BAND ===
    var milkyWayY = 70;
    for(var x=-50; x<W+50; x+=2){
      var p = Math.sin((x + t * 10) * 0.02) * 10;
      px(x, milkyWayY + p, rgba('#1a1a5e', 0.1 + 0.5 * Math.sin(t * 0.5 + x * 0.03)));
    }

    // === STARS ===
    for(var s of stars){
      var twinkle = osc(t, s.period, s.phase);
      var a = s.baseAlpha * (0.3 + 0.7 * twinkle);
      px(s.x, s.y, rgba('#ffffff', a));
      if(s.size === 3){
        px(s.x, s.y, rgba('#ffd166', a));
      }
    }

    // === CINDER CONE SUMMIT ===
    for(var y=H-coneHeight; y<H; y++){
      var width = Math.max(0, (coneHeight - (H-y)) * 0.15);
      rect(coneX-width/2, y, width, 1, rgba('#1a1a5e', 1));
    }

    // === OBSERVATORY DOMES ===
    for(var obs of observatories){
      rect(obs.x, obs.y, obs.width, obs.height, '#A5A5A5');
      var domeY = obs.y - 10;
      for(var j=0; j<obs.width; j++){
        var domeRadius = 5;
        circle(obs.x + j, domeY, domeRadius, '#7b2ff7');
      }
    }

    // === STAR TRAILS ===
    for(var s of stars){
      var trailLength = 10 + Math.floor(s.size * 3);
      for(var trail=0; trail<trailLength; trail++){
        var xTrail = s.x - trail;
        var yTrail = s.y - (trail * 0.5);
        if(yTrail > 0 && xTrail > 0 && xTrail < W){
          px(xTrail, yTrail, rgba('#ffd166', 0.2));
        }
      }
    }

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#1a1a5e',0.3));
    rect(0,H-2,W,1,rgba('#ffd166',0.1));
  };
});