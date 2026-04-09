// Scene: Cache Miss at the Mirage
// Namib Desert, Sossusvlei, Namibia
window.CF.register("Cache Miss at the Mirage", "Namib Desert, Sossusvlei, Namibia", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Star dune state
  var duneHeight = 50;
  var duneWidth = 120;
  var duneX = (W - duneWidth) / 2;
  
  // Heat mirage shimmer effect
  var mirageHeat = [];

  // Generate cracked vlei floor
  var cracks = [];
  var crackSeed = srand(1234);
  for(var i = 0; i < 60; i++) {
    cracks.push({ x: crackSeed() * W, y: H-10 + crackSeed() * 10, width: 5 + crackSeed() * 15 });
  }

  // Pre-compute star positions
  var stars = [];
  (function(){
    var starSeed = srand(5678);
    for(var i = 0; i < 100; i++) {
      stars.push({
        x: Math.floor(starSeed() * W),
        y: Math.floor(starSeed() * (H * 0.7)),
        size: (starSeed() > 0.95 ? 2 : 1),
        alpha: 0.1 + starSeed() * 0.9
      });
    }
  })();

  // Oryx silhouette state
  var oryxX = Math.random() * (W - 40);
  var oryxY = H - 35;

  return function(t){
    // === SKY ===
    rect(0, 0, W, H * 0.5, '#264653');

    // === DUNE ===
    for(var dy = 0; dy < duneHeight; dy++) {
      var drawY = H * 0.5 + dy;
      var drawXOffset = Math.sin((dy / duneHeight) * Math.PI) * 20;
      rect(duneX - drawXOffset, drawY, duneWidth + drawXOffset * 2, 1, '#f4a261');
    }

    // === MIRAGE SHIMMER ===
    for(var m = 0; m < 12; m++) {
      var mirageY = H * 0.5 + Math.sin(t * 3 + m) * 4;
      rect(0, mirageY, W, 1, rgba('#48cae4', 0.2 + Math.random() * 0.3));
    }

    // === STARS ===
    for(var s of stars) {
      var twinkle = osc(t, s.size === 1 ? 2 : 0.5, s.x * 0.1);
      px(s.x, s.y, rgba('#feffdf', s.alpha * twinkle));
      if(s.size === 2) {
        px(s.x + 1, s.y, rgba('#feffdf', s.alpha * twinkle));
        px(s.x - 1, s.y, rgba('#feffdf', s.alpha * twinkle));
      }
    }

    // === ORYX SILHOUETTE ===
    var oryxShape = [
      [0,0], [1,-2], [2,-2], [3,0], [2,1], [1,1], [0,0]
    ];
    for(var point of oryxShape) {
      px(oryxX + point[0], oryxY + point[1], '#3f3b3a');
    }

    // === CRACKED VLEI FLOOR ===
    for(var crack of cracks) {
      for(var j = 0; j < crack.width; j++) {
        px(crack.x + j, crack.y, '#fefae0');
      }
    }

    // Bottom glow line
    rect(0, H - 1, W, 1, rgba('#e76f51', 0.3));
    rect(0, H - 2, W, 1, rgba('#f4a261', 0.1));
  };
});