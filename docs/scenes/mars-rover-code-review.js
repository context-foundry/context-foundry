// Scene: Mars Rover Code Review
// Jezero Crater, Mars
window.CF.register("Mars Rover Code Review", "Jezero Crater, Mars", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Pre-compute dust devils
  var dustDevils = [];
  (function(){
    var r = srand(1001);
    for (var i = 0; i < 5; i++) {
      dustDevils.push({
        x: Math.floor(r() * W),
        y: Math.floor(r() * (H - 60)),
        size: 5 + Math.floor(r() * 10),
        phase: r() * Math.PI * 2
      });
    }
  })();

  // Initialize rover tracks
  var tracks = [];
  (function(){
    var r = srand(2001);
    for (var i = 0; i < 8; i++) {
      var x = Math.floor(r() * (W - 100));
      var y = H - 30 + Math.floor(r() * 10);
      tracks.push({x: x, y: y});
    }
  })();

  // Ancient river delta
  var riverDelta = [];
  for (var i = 0; i < W; i++) {
    var y = H - 80 + Math.sin(i * 0.05) * 10;
    riverDelta.push(y);
  }

  return function(t){
    // === SKY ===
    for (var y = 0; y < 80; y++) {
      var p = y / 80;
      rect(0, y, W, 1, lerp('#000000', '#264653', p));
    }

    // === ROCKY TERRAIN ===
    for (var y = 80; y < H; y++) {
      var p = (y - 80) / (H - 80);
      var col = lerp('#9a8c98', '#c9ada7', p);
      rect(0, y, W, 1, col);
    }

    // === RIVER DELTA ===
    for (var i = 0; i < W; i++) {
      px(i, riverDelta[i], '#f4a261');
    }

    // === ROVER TRACKS ===
    for (var track of tracks) {
      for (var j = 0; j < 5; j++) {
        px(track.x + j, track.y, '#e76f51');
        px(track.x + j + 1, track.y + 1, '#c9ada7');
      }
    }

    // === DUST DEVILS ===
    for (var devil of dustDevils) {
      var swirl = Math.sin(t * 2 + devil.phase) * 2;
      for (var i = -devil.size; i <= devil.size; i++) {
        px(devil.x + i, devil.y + swirl, rgba('#f4a261', 0.3));
        px(devil.x + i, devil.y + swirl + 1, rgba('#e76f51', 0.2));
      }
      devil.y += 0.1; // move upwards
      if (devil.y > H) {
        devil.y = 0;
        devil.x = Math.floor(Math.random() * W);
      }
    }

    // Bottom glow line
    rect(0, H - 1, W, 1, rgba('#264653', 0.3));
    rect(0, H - 2, W, 1, rgba('#264653', 0.1));
  };
});