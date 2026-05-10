// Scene: Hash Map of Rice Terraces
// Banaue Rice Terraces, Ifugao, Philippines
window.CF.register("Hash Map of Rice Terraces", "Banaue Rice Terraces, Ifugao, Philippines", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,ctx=api.ctx,W=api.W,H=api.H;

  // Initialize persistent state here
  var huts = [];
  var terraces = [];
  
  // Create huts
  for (var i = 0; i < 5; i++) {
    huts.push({x: 70 + i * 60, y: H - 80 - Math.random() * 20});
  }
  
  // Create terraces
  for (var i = 0; i < 10; i++) {
    terraces.push({y: H - 50 - i * 15});
  }

  // Initialize particle array for water reflection
  var reflections = [];

  function createReflection() {
    if (Math.random() < 0.08) {
      reflections.push({
        x: Math.random() * W,
        y: H - 75 + Math.random() * 10,
        life: 20 + Math.random() * 30,
        vx: (Math.random() - 0.5) * 2
      });
    }
  }

  return function(t){
    // Draw background
    rect(0, 0, W, H, '#95d5b2');

    // Draw mountains
    for (var m = 0; m < 5; m++) {
      var mx = 100 + m * 80;
      var my = H - 160 - Math.random() * 40;
      rect(mx, my, 100, H - my, '#40916c');
    }

    // Draw terraces
    for (var terrace of terraces) {
      var terraceHeight = 12;
      rect(0, terrace.y, W, terraceHeight, '#52b788');
      terrace.y += Math.sin(t * 0.5 + terrace.y / H * Math.PI) * 0.1; // animate terrace
    }

    // Draw flooded paddies
    for (var terrace of terraces) {
      rect(0, terrace.y + 10, W, terraceHeight - 10, rgba('#b7e4c7', 0.5));
    }

    // Draw thatched huts
    for (var hut of huts) {
      rect(hut.x, hut.y, 20, 15, '#dda15e'); // hut body
      for (var i = -10; i < 10; i += 5) {
        px(hut.x + i, hut.y - 5, '#3f120f'); // hut roof
      }
    }

    // Create water reflections
    createReflection();
    
    // Draw reflections
    for (var i = reflections.length - 1; i >= 0; i--) {
      var reflection = reflections[i];
      reflection.y += reflection.life > 0 ? Math.sin(t * 0.3 + reflection.x / 10) * 0.2 : 0;
      if (reflection.life > 0) {
        px(reflection.x, reflection.y, rgba('#ffffff', reflection.life / 50));
        reflection.x += reflection.vx;
        reflection.life--;
      } else {
        reflections.splice(i, 1);
      }
    }

    // Bottom glow line
    rect(0,H-1,W,1,rgba('#dda15e',0.3));
    rect(0,H-2,W,1,rgba('#b7e4c7',0.1));
  };
});