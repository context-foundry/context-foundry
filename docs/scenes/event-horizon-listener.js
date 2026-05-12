// Scene: Event Horizon Listener
// M87 Black Hole, Virgo Cluster
window.CF.register("Event Horizon Listener", "M87 Black Hole, Virgo Cluster", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Pre-compute star field
  var stars=[];
  (function(){
    var r=srand(1111);
    for(var i=0;i<300;i++){
      stars.push({
        x:Math.floor(r()*W), y:Math.floor(r()*H * 0.5),
        size:r()>0.95?2:(r()>0.7?1:1),
        baseAlpha:0.05+r()*0.9
      });
    }
  })();

  // Accretion disk properties
  var diskRadius = 150;
  var photons = [];
  for (var i = 0; i < 100; i++) {
    photons.push({
      angle: Math.random() * Math.PI * 2,
      radius: diskRadius + Math.random() * 10,
      speed: Math.random() * 0.02 + 0.01,
      alpha: Math.random()
    });
  }

  // Relativistic jet state
  var jetX = -30;
  var jetY = H / 2;
  var jetWidth = 2;

  return function(t){
    // === SPACE BG ===
    rect(0,0,W,H,rgba('#0b0c2a', 1));

    // === STARS ===
    for(var s of stars){
      var twinkle = osc(t, 0.5 + s.x * 0.001, s.y * 0.001);
      var a = s.baseAlpha * twinkle;
      var col = '#ffffff';
      if(s.size === 2){
        rect(s.x, s.y, 2, 2, rgba(col, a*0.6));
        px(s.x, s.y, rgba(col, a));
        px(s.x + 1, s.y, rgba(col, a * 0.8));
      } else {
        px(s.x, s.y, rgba(col, a));
      }
    }

    // === ACCRETION DISK ===
    for (var p of photons) {
      var x = W / 2 + Math.cos(p.angle) * p.radius;
      var y = H / 2 + Math.sin(p.angle) * p.radius;
      px(x, y, rgba('#ff6b35', p.alpha));
      p.angle += p.speed;
    }

    // === PHOTON SPHERE ===
    var photonSphereRadius = diskRadius + 20;
    for (var angle = 0; angle < Math.PI * 2; angle += Math.PI / 30) {
      var x = W / 2 + Math.cos(angle) * photonSphereRadius;
      var y = H / 2 + Math.sin(angle) * photonSphereRadius;
      px(x, y, rgba('#faa307', 0.4));
    }

    // === RELATIVISTIC JET ===
    for(var j = 0; j < 60; j++) {
      var jetAlpha = Math.max(0, 1 - (j / 60));
      px(jetX, jetY - j, rgba('#ffd166', jetAlpha));
      px(jetX + jetWidth, jetY - j - Math.sin(j * 0.2) * 2, rgba('#ffd166', jetAlpha * 0.6));
    }
    jetX += 1;
    if(jetX > W) jetX = -30;

    // === WARPED STARLIGHT ===
    for(var angle = 0; angle < Math.PI * 2; angle += Math.PI / 50) {
      var x = W / 2 + Math.cos(angle) * (diskRadius + 40);
      var y = H / 2 + Math.sin(angle) * (diskRadius + 40);
      var warpAlpha = osc(t, 1 + angle, 0) * 0.2;
      px(x, y, rgba('#1d1d1d', warpAlpha));
    }

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#faa307',0.4));
    rect(0,H-2,W,1,rgba('#ff6b35',0.1));
  };
});