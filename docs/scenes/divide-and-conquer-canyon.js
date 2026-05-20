// Scene: Divide and Conquer Canyon
// Grand Canyon, Arizona, USA
window.CF.register("Divide and Conquer Canyon", "Grand Canyon, Arizona, USA", function(api){
  var px=api.px,rect=api.rect,rgba=api.rgba,lerp=api.lerp,osc=api.osc,srand=api.srand,circle=api.circle,W=api.W,H=api.H;

  // Ground and canyon walls
  function drawCanyon() {
    for (var y = 120; y < 260; y++) {
      var p = (y - 120) / (260 - 120);
      var color = lerp('#264653', '#48cae4', p);
      rect(0, y, W, 1, color);
    }
    for (var x = 0; x < W; x += 10) {
      var canyonHeight = 20 + Math.sin(x * 0.1) * 10;
      rect(x, 120 - canyonHeight, 10, canyonHeight, '#e76f51');
      rect(x - 5, 120 - canyonHeight + 10, 10, 5, '#f4a261');
    }
  }

  // River
  function drawRiver() {
    for (var y = 150; y < 210; y++) {
      var riverColor = rgba('#48cae4', 0.7 + Math.sin((y - 150) * 0.1) * 0.1);
      rect(0, y, W, 1, riverColor);
    }
    for (var x = 0; x < W; x += 4) {
      px(x, 160 + Math.sin(x * 0.15) * 2, rgba('#e9c46a', 0.3));
    }
  }

  // Condor
  var condorX = W + 20;
  var condorY = Math.random() * 30 + 30;

  function drawCondor(t) {
    condorX -= 1;
    if (condorX < -20) {
      condorX = W + 20;
      condorY = Math.random() * 30 + 30;
    }
    var wingPhase = Math.sin(t * 2 + condorX * 0.05) * 2;
    px(condorX, condorY, '#000000');
    px(condorX + 1, condorY - 1 + wingPhase, '#000000');
    px(condorX - 1, condorY - 1 - wingPhase, '#000000');
    px(condorX + 1, condorY, '#000000');
    px(condorX - 1, condorY, '#000000');
  }

  // Mule trail
  var muleTrail = [];

  function updateMuleTrail() {
    if (Math.random() < 0.05) {
      muleTrail.push({ x: Math.random() * W, y: 250, life: 20 });
    }
    for (var i = 0; i < muleTrail.length; i++) {
      var mule = muleTrail[i];
      mule.y -= 0.5;
      if (mule.y < 200) {
        muleTrail.splice(i, 1);
        i--;
        continue;
      }
      for (var j = -3; j <= 3; j++) {
        px(mule.x + j, mule.y, '#e9c46a');
      }
    }
  }

  return function(t) {
    // Draw background and canyon
    drawCanyon();
    drawRiver();
    drawCondor(t);
    updateMuleTrail();

    // REQUIRED: bottom glow line (brand consistency)
    rect(0, H-1, W, 1, rgba('#e9c46a', 0.3));
    rect(0, H-2, W, 1, rgba('#e9c46a', 0.1));
  };
});