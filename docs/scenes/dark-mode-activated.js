// Scene: Dark Mode Activated
// Mammoth Cave, Kentucky, USA
window.CF.register("Dark Mode Activated", "Mammoth Cave, Kentucky, USA", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Pre-compute limestone columns
  var columns=[];
  (function(){
    var r=srand(1001);
    for(var i=0;i<10;i++){
      columns.push({
        x:Math.random() * W,
        height:20 + r() * 40,
        baseY:H - (20 + r() * 20)
      });
    }
  })();

  // Pre-compute bat colony
  var bats=[];
  (function(){
    var r=srand(2002);
    for(var i=0;i<20;i++){
      bats.push({
        x:Math.random() * W,
        y:Math.random() * (H * 0.4), // Bats hover in the upper quarter
        flap: r() * Math.PI * 2 // Random flap phase
      });
    }
  })();

  // River state
  var riverWaveOffset = 0;

  return function(t){
    // === CAVE BACKGROUND ===
    rect(0, 0, W, H, '#1d1d1d');

    // === LIMESTONE COLUMNS ===
    for(var col of columns){
      rect(col.x - 2, col.baseY - col.height, 4, col.height, '#343a40');
      rect(col.x - 1, col.baseY - col.height + 5, 2, col.height, '#495057');
    }

    // === RIVER STYX CROSSING ===
    for(var x=0;x<W;x+=2){
      var wave=osc(t + riverWaveOffset + x * 0.05, 30, 0) * 3;
      px(x, H - 10 + wave, rgba('#343a40', 0.8));
      px(x + 1, H - 10 + wave, rgba('#6c757d', 0.5));
    }
    riverWaveOffset += 0.02;

    // === BAT COLONY ANIMATION ===
    for(var bat of bats){
      bat.y += Math.sin(t * 3 + bat.flap) * 0.3;
      bat.x += Math.cos(t * 2 + bat.flap) * 0.2;

      if(bat.x < 0) bat.x = W;
      if(bat.x > W) bat.x = 0;

      px(bat.x, bat.y, '#adb5bd');
      circle(bat.x, bat.y - 2, 3, '#495057'); // Bat body
      circle(bat.x - 2, bat.y, 2, '#6c757d'); // Bat wing left
      circle(bat.x + 2, bat.y, 2, '#6c757d'); // Bat wing right
    }

    // === GROUND DETAIL ===
    for(var x=0;x<W;x+=4){
      var groundY=H-10 + Math.sin(x * 0.1) * 2;
      px(x, groundY, '#343a40');
    }

    // === ENDLESS PASSAGE ===
    for(var x=0;x<W;x+=20){
      var yOffset = Math.sin(x * 0.03 + t) * 5;
      rect(x, 0, 10, H + yOffset, '#1d1d1d');
    }

    // === BOTTOM GLOW LINE ===
    rect(0,H-1,W,1,rgba('#adb5bd',0.3));
    rect(0,H-2,W,1,rgba('#495057',0.1));
  };
});