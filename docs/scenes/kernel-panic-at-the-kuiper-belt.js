// Scene: Kernel Panic at the Kuiper Belt
// Kuiper Belt, Outer Solar System
window.CF.register("Kernel Panic at the Kuiper Belt", "Kuiper Belt, Outer Solar System", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Pre-compute star field
  var stars=[];
  (function(){
    var r=srand(1001);
    for(var i=0;i<150;i++){
      stars.push({
        x:Math.floor(r()*W),y:Math.floor(r()*H),
        size:r()>0.9?2:(r()>0.6?1:1),
        baseAlpha:0.1+r()*0.8,
        period:1.5+r()*5,phase:r()*Math.PI*2
      });
    }
  })();

  // Ice bodies
  var iceBodies=[];
  (function(){
    var r=srand(2002);
    for(var i=0; i<30; i++){
      iceBodies.push({
        x: r() * W, 
        y: r() * H,
        size: 2 + r() * 3,
        speed: 0.1 + r() * 0.5,
        angle: r() * Math.PI * 2
      });
    }
  })();

  // Animation for Pluto rotation
  var plutoAngle = 0;

  return function(t){
    // === BACKGROUND ===
    rect(0, 0, W, H, '#0b0c2a'); // Dark space background

    // === STARS ===
    for(var s of stars){
      var twinkle=osc(t,s.period,s.phase);
      var a=s.baseAlpha*0.3+s.baseAlpha*0.7*twinkle;
      var col='#ffffff';
      if(s.size===2){
        rect(s.x,s.y,2,2,rgba(col,a*0.5));
        px(s.x,s.y,rgba(col,a));
        px(s.x+1,s.y,rgba(col,a*0.7));
      } else {
        px(s.x,s.y,rgba(col,a));
      }
    }

    // === ICE BODIES ===
    for(var ice of iceBodies){
      ice.x += Math.cos(ice.angle) * ice.speed;
      ice.y += Math.sin(ice.angle) * ice.speed;
      
      // Wrap around the screen
      if (ice.x < 0) ice.x += W;
      if (ice.x > W) ice.x -= W;
      if (ice.y < 0) ice.y += H;
      if (ice.y > H) ice.y -= H;

      px(Math.floor(ice.x), Math.floor(ice.y), '#6c757d');
      circle(ice.x, ice.y, ice.size, '#ffffff');
    }

    // === DISTANT SUN POINT ===
    var sunX = W - 50 + Math.sin(t * 0.5) * 10;
    var sunY = 30 + Math.cos(t * 0.5) * 5;
    circle(sunX, sunY, 4, rgba('#ffffff', 0.7));

    // === PLUTO SILHOUETTE ===
    plutoAngle += 0.02;
    var plutoX = W * 0.5 + Math.sin(plutoAngle) * 20;
    var plutoY = H * 0.5 + Math.cos(plutoAngle) * 10;
    for (var dx = -5; dx <= 5; dx++) {
      for (var dy = -5; dy <= 5; dy++) {
        if (Math.sqrt(dx * dx + dy * dy) < 5) {
          px(plutoX + dx, plutoY + dy, '#1d1d1d');
        }
      }
    }

    // === BOTTOM GLOW LINE ===
    rect(0,H-1,W,1,rgba('#6c757d',0.3));
    rect(0,H-2,W,1,rgba('#6c757d',0.1));
  };
});